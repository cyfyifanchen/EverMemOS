"""
语义记忆 Elasticsearch 仓库

基于 BaseRepository 的语义记忆专用仓库类，提供高效的BM25文本检索和复杂查询功能。
复用 EpisodicMemoryDoc，通过 type 字段过滤为 semantic_memory。
"""

from datetime import datetime
import pprint
from typing import List, Optional, Dict, Any
from elasticsearch.dsl import Q
from core.oxm.es.base_repository import BaseRepository
from infra_layer.adapters.out.search.elasticsearch.memory.semantic_memory import (
    SemanticMemoryDoc,
)
from core.observation.logger import get_logger
from common_utils.datetime_utils import get_now_with_timezone
from common_utils.text_utils import SmartTextParser
from core.di.decorators import repository

logger = get_logger(__name__)


@repository("semantic_memory_es_repository", primary=True)
class SemanticMemoryEsRepository(BaseRepository[SemanticMemoryDoc]):
    """
    语义记忆 Elasticsearch 仓库

    基于 BaseRepository 的专用仓库类，提供：
    - 高效的BM25文本检索
    - 多词查询和过滤功能
    - 文档创建和管理
    - 手动索引刷新控制
    
    注意：复用 EpisodicMemoryDoc，通过 type 字段过滤为 semantic_memory。
    """

    def __init__(self):
        """初始化语义记忆仓库"""
        super().__init__(SemanticMemoryDoc)
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

    async def create_and_save_semantic_memory(
        self,
        id: str,
        user_id: str,
        user_name: str,
        timestamp: datetime,
        content: str,
        search_content: List[str],
        event_type: Optional[str] = None,
        parent_episode_id: Optional[str] = None,
        group_id: Optional[str] = None,
        participants: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        duration_days: Optional[int] = None,
        evidence: Optional[str] = None,
        extend: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> SemanticMemoryDoc:
        """
        创建并保存语义记忆文档

        Args:
            id: 记忆唯一标识
            user_id: 用户ID（必需）
            timestamp: 事件发生时间（必需）
            content: 语义记忆内容（必需）
            search_content: 搜索内容列表（支持多个搜索词，必需）
            parent_episode_id: 父情景记忆ID
            group_id: 群组ID
            participants: 参与者列表
            start_time: 有效期开始时间
            end_time: 有效期结束时间
            duration_days: 持续天数
            evidence: 证据（原始事实依据）
            extend: 扩展字段
            created_at: 创建时间
            updated_at: 更新时间

        Returns:
            已保存的SemanticMemoryDoc实例
        """
        try:
            # 设置默认时间戳
            now = get_now_with_timezone()
            if created_at is None:
                created_at = now
            if updated_at is None:
                updated_at = now

            # 构建 extend 字段，包含语义记忆特有信息
            semantic_extend = extend or {}
            semantic_extend.update({
                "parent_episode_id": parent_episode_id,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
                "duration_days": duration_days,
                "evidence": evidence,
            })

            # 创建文档实例
            doc = SemanticMemoryDoc(
                id=id,
                type=event_type,
                user_id=user_id,
                user_name=user_name or '',
                timestamp=timestamp,
                semantic=content,
                search_content=search_content,
                evidence=evidence or '',
                group_id=group_id,
                participants=participants or [],
                keywords=[],
                subject='',
                memcell_event_id_list=[],
                extend=semantic_extend,
                created_at=created_at,
                updated_at=updated_at,
            )

            # 保存文档（不使用refresh参数）
            client = await self.get_client()
            await doc.save(using=client)

            logger.debug(
                "✅ 创建语义记忆文档成功: id=%s, user_id=%s", id, user_id
            )
            return doc

        except Exception as e:
            logger.error("❌ 创建语义记忆文档失败: id=%s, error=%s", id, e)
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
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        使用 elasticsearch-dsl 的统一搜索接口，支持多词查询和全面过滤

        使用function_score查询实现基于匹配词数的累积评分。
        自动过滤 type="semantic_memory" 的文档。

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
            current_time: 当前时间（仅当需要按 start/end 有效期过滤时使用）

        Returns:
            搜索结果的hits部分，包含匹配的文档数据
        """
        try:
            # 创建 AsyncSearch 对象
            search = SemanticMemoryDoc.search()

            # 构建过滤条件
            filter_queries = []
            
            if user_id and user_id != "":
                filter_queries.append(Q("term", user_id=user_id))
            elif user_id is None or user_id == "":
                # 只保留 user_id 不存在的文档(群组记忆)
                filter_queries.append(Q("bool", must_not=Q("exists", field="user_id")))
            if group_id and group_id != "":
                filter_queries.append(Q("term", group_id=group_id))
            
            if group_id:
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

            logger.debug("semantic memory search query: %s", search.to_dict())

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
                    "✅ 语义记忆DSL多词搜索成功(explain模式): query=%s, user_id=%s, 找到 %d 条结果",
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
            
            # 根据 current_time 过滤有效期
            if current_time:
                current_dt = current_time
                if isinstance(current_dt, str):
                    try:
                        current_dt = datetime.fromisoformat(current_dt)
                    except ValueError:
                        try:
                            current_dt = datetime.fromisoformat(
                                current_dt.replace("Z", "+00:00")
                            )
                        except ValueError:
                            current_dt = None
                filtered_hits = []
                for hit_data in hits:
                    source = hit_data.get("_source", {}) or {}
                    extend = source.get("extend") or {}
                    start_dt = self._parse_datetime(extend.get("start_time"))
                    end_dt = self._parse_datetime(extend.get("end_time"))
                    if start_dt and current_dt and start_dt > current_dt:
                        continue
                    if end_dt and current_dt and end_dt < current_dt:
                        continue
                    filtered_hits.append(hit_data)
                hits = filtered_hits

                logger.debug(
                    "✅ 语义记忆DSL多词搜索成功: query=%s, user_id=%s, 找到 %d 条结果",
                    search.to_dict(),
                    user_id,
                    len(hits),
                )

            # 只返回hits部分
            return hits

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.error(
                "❌ 语义记忆DSL多词搜索失败: query=%s, user_id=%s, error=%s",
                query,
                user_id,
                e,
            )
            raise
        except Exception as e:
            logger.error(
                "❌ 语义记忆DSL多词搜索失败（未知错误）: query=%s, user_id=%s, error=%s",
                query,
                user_id,
                e,
            )
            raise

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """解析 ISO 日期字符串"""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None

