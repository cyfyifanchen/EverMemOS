"""
事件日志 Elasticsearch 仓库

基于 BaseRepository 的事件日志专用仓库类，提供高效的BM25文本检索和复杂查询功能。
复用 EpisodicMemoryDoc，通过 type 字段过滤为 event_log。
"""

from datetime import datetime
import pprint
from typing import List, Optional, Dict, Any
from elasticsearch.dsl import Q
from core.oxm.es.base_repository import BaseRepository
from infra_layer.adapters.out.search.elasticsearch.memory.event_log import (
    EventLogDoc,
)
from core.observation.logger import get_logger
from common_utils.datetime_utils import get_now_with_timezone
from common_utils.text_utils import SmartTextParser
from core.di.decorators import repository

logger = get_logger(__name__)


@repository("event_log_es_repository", primary=True)
class EventLogEsRepository(BaseRepository[EventLogDoc]):
    """
    事件日志 Elasticsearch 仓库

    基于 BaseRepository 的专用仓库类，提供：
    - 高效的BM25文本检索
    - 多词查询和过滤功能
    - 文档创建和管理
    - 手动索引刷新控制
    
    注意：复用 EpisodicMemoryDoc，通过 type 字段过滤为 event_log。
    """

    def __init__(self):
        """初始化事件日志仓库"""
        super().__init__(EventLogDoc)
        # 初始化智能文本解析器，用于计算查询词的智能长度
        self._text_parser = SmartTextParser()

    def _calculate_text_score(self, text: str) -> float:
        """
        计算文本的智能分数

        使用SmartTextParser计算文本的总分数，考虑中日韩字符、英文单词等不同类型的权重。

        Args:
            text: 要计算分数的文本

        Returns:
            float: 文本的智能分数
        """
        if not text:
            return 0.0

        try:
            tokens = self._text_parser.parse_tokens(text)
            return self._text_parser.calculate_total_score(tokens)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning("计算文本分数失败，使用字符长度作为fallback: %s", e)
            return float(len(text))

    def _log_explanation_details(
        self, explanation: Dict[str, Any], indent: int = 0
    ) -> None:
        """
        递归输出explanation的详细信息

        Args:
            explanation: 解释字典
            indent: 缩进级别
        """
        pprint.pprint(explanation, indent=indent)

    # ==================== 文档创建和管理 ====================

    async def create_and_save_event_log(
        self,
        id: str,
        user_id: str,
        timestamp: datetime,
        atomic_fact: str,
        search_content: List[str],
        event_type: Optional[str] = None,
        parent_episode_id: Optional[str] = None,
        group_id: Optional[str] = None,
        group_name: str = "",
        user_name: str = "",
        participants: Optional[List[str]] = None,
        extend: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> EventLogDoc:
        """
        创建并保存事件日志文档

        Args:
            id: 日志唯一标识
            user_id: 用户ID（必需）
            timestamp: 事件发生时间（必需）
            atomic_fact: 原子事实（必需）
            search_content: 搜索内容列表（支持多个搜索词，必需）
            parent_episode_id: 父情景记忆ID
            group_id: 群组ID
            participants: 参与者列表
            extend: 扩展字段
            created_at: 创建时间
            updated_at: 更新时间

        Returns:
            已保存的EventLogDoc实例
        """
        try:
            # 设置默认时间戳
            now = get_now_with_timezone()
            if created_at is None:
                created_at = now
            if updated_at is None:
                updated_at = now

            # 构建 extend 字段，包含事件日志特有信息
            eventlog_extend = extend or {}
            eventlog_extend.update({
                "parent_episode_id": parent_episode_id,
                "atomic_fact": atomic_fact,
            })

            # 创建文档实例
            doc = EventLogDoc(
                id=id,
                type=event_type,
                user_id=user_id,
                user_name=user_name or "",
                timestamp=timestamp,
                title='',
                episode='',
                atomic_fact=atomic_fact,
                search_content=search_content,
                summary='',
                group_id=group_id,
                group_name=group_name or "",
                participants=participants or [],
                keywords=[],
                linked_entities=[],
                subject='',
                memcell_event_id_list=[],
                extend=eventlog_extend,
                created_at=created_at,
                updated_at=updated_at,
            )

            # 保存文档（不使用refresh参数）
            client = await self.get_client()
            await doc.save(using=client)

            logger.debug(
                "✅ 创建事件日志文档成功: event_id=%s, user_id=%s", event_id, user_id
            )
            return doc

        except Exception as e:
            logger.error("❌ 创建事件日志文档失败: event_id=%s, error=%s", event_id, e)
            raise

    # ==================== 搜索功能 ====================

    async def multi_search(
        self,
        query: List[str],
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        date_range: Optional[Dict[str, Any]] = None,
        size: int = 10,
        from_: int = 0,
        explain: bool = False,
        participant_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        使用 elasticsearch-dsl 的统一搜索接口，支持多词查询和全面过滤

        使用function_score查询实现基于匹配词数的累积评分。
        自动过滤 type="event_log" 的文档。

        Args:
            query: 搜索词列表，支持多个搜索词
            user_id: 用户ID过滤
            group_id: 群组ID过滤
            keywords: 关键词过滤
            date_range: 时间范围过滤，格式：{"gte": "2024-01-01", "lte": "2024-12-31"}
            size: 结果数量
            from_: 分页起始位置
            explain: 是否启用得分解释模式
            participant_user_id: 群组检索时额外要求参与者包含该用户

        Returns:
            搜索结果的hits部分，包含匹配的文档数据
        """
        try:
            # 创建 AsyncSearch 对象
            search = EventLogDoc.search()

            # 构建过滤条件
            filter_queries = []
            
            if user_id and user_id != "":
                filter_queries.append(Q("term", user_id=user_id))
            elif user_id is None or user_id == "":
                # 只保留 user_id 不存在的文档(群组记忆)
                filter_queries.append(Q("bool", must_not=Q("exists", field="user_id")))
            if group_id and group_id != "":
                filter_queries.append(Q("term", group_id=group_id))
            
            if keywords:
                filter_queries.append(Q("terms", keywords=keywords))
            if date_range:
                filter_queries.append(Q("range", timestamp=date_range))

            # 根据是否有查询词使用不同的查询模板
            if query:
                # 按智能分数过滤查询词，保留分数最高的10个词
                query_with_scores = [
                    (word, self._calculate_text_score(word)) for word in query
                ]
                sorted_query_with_scores = sorted(
                    query_with_scores, key=lambda x: x[1], reverse=True
                )[:10]

                # 构建should子句
                should_queries = []
                for word, word_score in sorted_query_with_scores:
                    should_queries.append(
                        Q(
                            "match",
                            search_content={
                                "query": word,
                                "boost": word_score,
                            },
                        )
                    )

                # 构建bool查询
                bool_query_params = {
                    "should": should_queries,
                    "minimum_should_match": 1,
                }

                # 如果有过滤条件，添加到must子句
                if filter_queries:
                    bool_query_params["must"] = filter_queries

                # 使用 bool 查询
                search = search.query(Q("bool", **bool_query_params))
            else:
                # 没有查询词的情况：纯过滤查询
                if filter_queries:
                    search = search.query(Q("bool", filter=filter_queries))
                else:
                    search = search.query(Q("match_all"))

                # 没有查询词时按时间倒序排列
                search = search.sort({"timestamp": {"order": "desc"}})

            # 设置分页参数
            search = search[from_ : from_ + size]

            logger.debug("event log search query: %s", search.to_dict())

            # 执行搜索
            if explain and query:
                # explain模式
                client = await self.get_client()
                index_name = self.get_index_name()

                search_body = search.to_dict()
                search_response = await client.search(
                    index=index_name, body=search_body, explain=True
                )

                # 转换为标准格式并输出explanation
                hits = []
                for hit_data in search_response["hits"]["hits"]:
                    hits.append(hit_data)

                    # 输出explanation信息
                    if "_explanation" in hit_data:
                        explanation = hit_data["_explanation"]
                        self._log_explanation_details(explanation, indent=2)

                logger.debug(
                    "✅ 事件日志DSL多词搜索成功(explain模式): query=%s, user_id=%s, 找到 %d 条结果",
                    search.to_dict(),
                    user_id,
                    len(hits),
                )
            else:
                # 正常模式
                response = await search.execute()

                # 转换为标准格式
                hits = []
                for hit in response.hits:
                    hit_data = {
                        "_index": hit.meta.index,
                        "_id": hit.meta.id,
                        "_score": hit.meta.score,
                        "_source": hit.to_dict(),
                    }
                    hits.append(hit_data)

                logger.debug(
                    "✅ 事件日志DSL多词搜索成功: query=%s, user_id=%s, 找到 %d 条结果",
                    search.to_dict(),
                    user_id,
                    len(hits),
                )

            # 只返回hits部分
            return hits

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.error(
                "❌ 事件日志DSL多词搜索失败: query=%s, user_id=%s, error=%s",
                query,
                user_id,
                e,
            )
            raise
        except Exception as e:
            logger.error(
                "❌ 事件日志DSL多词搜索失败（未知错误）: query=%s, user_id=%s, error=%s",
                query,
                user_id,
                e,
            )
            raise

