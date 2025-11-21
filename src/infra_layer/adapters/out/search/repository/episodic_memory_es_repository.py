"""
情景记忆 Elasticsearch 仓库

基于 BaseRepository 的情景记忆专用仓库类，提供高效的BM25文本检索和复杂查询功能。
主要功能包括多词搜索、过滤查询和文档管理。
"""

from datetime import datetime
import pprint
from typing import List, Optional, Dict, Any
from elasticsearch.dsl import Q
from core.oxm.es.base_repository import BaseRepository
from infra_layer.adapters.out.search.elasticsearch.memory.episodic_memory import (
    EpisodicMemoryDoc,
)
from core.observation.logger import get_logger
from common_utils.datetime_utils import get_now_with_timezone
from common_utils.text_utils import SmartTextParser
from core.di.decorators import repository

logger = get_logger(__name__)


@repository("episodic_memory_es_repository", primary=True)
class EpisodicMemoryEsRepository(BaseRepository[EpisodicMemoryDoc]):
    """
    情景记忆 Elasticsearch 仓库

    基于 BaseRepository 的专用仓库类，提供：
    - 高效的BM25文本检索
    - 多词查询和过滤功能
    - 文档创建和管理
    - 手动索引刷新控制
    """

    def __init__(self):
        """初始化情景记忆仓库"""
        super().__init__(EpisodicMemoryDoc)
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

    async def create_and_save_episodic_memory(
        self,
        event_id: str,
        user_id: str,
        timestamp: datetime,
        episode: str,
        search_content: List[str],
        user_name: Optional[str] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        group_id: Optional[str] = None,
        participants: Optional[List[str]] = None,
        event_type: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        linked_entities: Optional[List[str]] = None,
        subject: Optional[str] = None,
        memcell_event_id_list: Optional[List[str]] = None,
        extend: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> EpisodicMemoryDoc:
        """
        创建并保存情景记忆文档

        Args:
            event_id: 事件唯一标识
            user_id: 用户ID（必需）
            timestamp: 事件发生时间（必需）
            episode: 情景描述（必需）
            search_content: 搜索内容列表（支持多个搜索词，必需）
            type: 事件类型
            user_name: 用户名称
            title: 事件标题
            summary: 事件摘要
            group_id: 群组ID
            participants: 参与者列表
            event_type: 事件类型
            keywords: 关键词列表
            linked_entities: 关联实体ID列表
            subject: 事件标题（新增字段）
            memcell_event_id_list: 记忆单元事件ID列表（新增字段）
            extend: 扩展字段
            created_at: 创建时间
            updated_at: 更新时间

        Returns:
            已保存的EpisodicMemoryDoc实例
        """
        try:
            # 设置默认时间戳
            now = get_now_with_timezone()
            if created_at is None:
                created_at = now
            if updated_at is None:
                updated_at = now

            # 创建文档实例
            normalized_user_id = user_id or ""
            doc = EpisodicMemoryDoc(
                event_id=event_id,
                type=event_type,
                user_id=normalized_user_id,
                user_name=user_name or '',
                timestamp=timestamp,
                title=title or '',
                episode=episode,
                search_content=search_content,
                summary=summary or '',
                group_id=group_id,
                participants=participants or [],
                keywords=keywords or [],
                linked_entities=linked_entities or [],
                subject=subject or '',
                memcell_event_id_list=memcell_event_id_list or [],
                extend=extend or {},
                created_at=created_at,
                updated_at=updated_at,
            )

            # 保存文档（不使用refresh参数）
            client = await self.get_client()
            await doc.save(using=client)

            logger.debug(
                "✅ 创建情景记忆文档成功: event_id=%s, user_id=%s", event_id, user_id
            )
            return doc

        except Exception as e:
            logger.error("❌ 创建情景记忆文档失败: event_id=%s, error=%s", event_id, e)
            raise

    # ==================== 搜索功能 ====================

    async def multi_search(
        self,
        query: List[str],
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        event_type: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        date_range: Optional[Dict[str, Any]] = None,
        size: int = 10,
        from_: int = 0,
        explain: bool = False,
        participant_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        使用 elasticsearch-dsl 的统一搜索接口，支持多词查询和全面过滤

        这个方法使用 elasticsearch-dsl 的 AsyncSearch 类构建查询，提供与 multi_search 相同的功能，
        但使用更加 Pythonic 的 DSL 语法而不是直接使用原始的 client。

        使用function_score查询实现基于匹配词数的累积评分：
        - 每匹配一个查询词，文档得分增加1.0
        - 匹配越多词的文档排序越靠前
        - 至少匹配一个词才会返回结果(min_score=1.0)

        Args:
            query: 搜索词列表，支持多个搜索词
            user_id: 用户ID过滤
            group_id: 群组ID过滤
            event_type: 事件类型过滤
            keywords: 关键词过滤
            date_range: 时间范围过滤，格式：{"gte": "2024-01-01", "lte": "2024-12-31"}
            size: 结果数量
            from_: 分页起始位置
            explain: 是否启用得分解释模式，通过debug日志输出Elasticsearch的详细得分计算过程

        Returns:
            搜索结果的hits部分，包含匹配的文档数据

        Examples:
            # 1. 多词搜索
            await repo.multi_search(
                query=["公司", "北京", "科技"],
                user_id="user123",
                size=10
            )

            # 2. 按时间范围获取用户记忆
            await repo.multi_search(
                query=[],  # 空查询词
                user_id="user123",
                date_range={"gte": "2024-01-01", "lte": "2024-12-31"},
                size=100
            )

            # 3. 组合查询
            await repo.multi_search(
                query=["会议", "讨论"],
                user_id="user123",
                group_id="group456",
                event_type="Conversation",
                keywords=["工作", "项目"],
                date_range={"gte": "2024-01-01"}
            )
        """
        try:
            # 创建 AsyncSearch 对象
            search = EpisodicMemoryDoc.search()

            # 构建过滤条件
            filter_queries = []
            
            if user_id and user_id != "":
                filter_queries.append(Q("term", user_id=user_id))
            elif user_id is None or user_id == "":
                # 只保留 user_id 不存在的文档(群组记忆)
                filter_queries.append(Q("bool", must_not=Q("exists", field="user_id")))
            if group_id and group_id != "":
                filter_queries.append(Q("term", group_id=group_id))
            if participant_user_id:
                filter_queries.append(Q("term", participants=participant_user_id))
            if group_id:
                filter_queries.append(Q("term", group_id=group_id))
            if event_type:
                filter_queries.append(Q("term", type=event_type))
            if keywords:
                filter_queries.append(Q("terms", keywords=keywords))
            if date_range:
                filter_queries.append(Q("range", timestamp=date_range))

            # 根据是否有查询词使用不同的查询模板
            if query:
                # ========== 有查询词的情况：使用bool查询的should子句 ==========
                #
                # 查询结构：
                # bool {
                #   must: [硬性过滤条件 (user_id, group_id, type, keywords, date_range)]
                #   should: [top10查询词匹配条件]
                #   minimum_should_match: 1
                # }
                #
                # 评分规则：
                # 1. 按智能分数倒序排列查询词，保留分数最高的10个词
                # 2. should子句中每个查询词使用boost设置权重（智能文本分数）
                # 3. minimum_should_match=1 确保至少匹配1个词才返回结果
                # 4. 最终得分 = 匹配词的BM25得分 * boost权重总和

                # 按智能分数过滤查询词，保留分数最高的10个词
                query_with_scores = [
                    (word, self._calculate_text_score(word)) for word in query
                ]
                sorted_query_with_scores = sorted(
                    query_with_scores, key=lambda x: x[1], reverse=True
                )[:10]

                # 构建should子句，每个查询词使用智能文本分数作为boost权重
                should_queries = []
                for word, word_score in sorted_query_with_scores:
                    should_queries.append(
                        Q(
                            "match",
                            search_content={  # 使用主字段（standard analyzer，会分词）
                                "query": word,
                                "boost": word_score,
                            },
                        )
                    )

                # 构建bool查询
                bool_query_params = {
                    "should": should_queries,
                    "minimum_should_match": 1,  # 至少匹配1个词
                }

                # 如果有过滤条件，添加到must子句
                if filter_queries:
                    bool_query_params["must"] = filter_queries

                # 使用 bool 查询
                search = search.query(Q("bool", **bool_query_params))
            else:
                # ========== 没有查询词的情况：纯过滤查询 ==========
                #
                # 查询结构：
                # bool { filter: [过滤条件] } 或 match_all {}
                #
                # 特点：
                # 1. 不计算相关性得分，性能更好
                # 2. 按timestamp倒序排列
                # 3. 适用于：根据时间范围获取用户记忆等场景

                if filter_queries:
                    search = search.query(Q("bool", filter=filter_queries))
                else:
                    search = search.query(Q("match_all"))

                # 没有查询词时按时间倒序排列
                search = search.sort({"timestamp": {"order": "desc"}})

            # 设置分页参数
            search = search[from_ : from_ + size]

            # 限制返回字段，排除keywords、linked_entities、extend字段
            # search = search.source(excludes=['keywords', 'linked_entities', 'extend', 'timestamp'])
            # 打印search query
            logger.debug("search query: %s", search.to_dict())

            # 执行搜索
            if explain and query:
                # explain模式：使用原生客户端执行带explain参数的搜索
                client = await self.get_client()
                index_name = self.get_index_name()

                search_body = search.to_dict()
                search_response = await client.search(
                    index=index_name, body=search_body, explain=True  # 添加explain参数
                )

                # 转换为标准格式并输出explanation
                hits = []
                for hit_data in search_response["hits"]["hits"]:
                    # dict_keys(['_shard', '_node', '_index', '_id', '_score', '_source', '_explanation'])
                    hits.append(hit_data)

                    # 输出explanation信息
                    if "_explanation" in hit_data:
                        explanation = hit_data["_explanation"]
                        self._log_explanation_details(explanation, indent=2)

                logger.debug(
                    "✅ 情景记忆DSL多词搜索成功(explain模式): query=%s, user_id=%s, 找到 %d 条结果",
                    search.to_dict(),
                    user_id,
                    len(hits),
                )
            else:
                # 正常模式：使用elasticsearch-dsl
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
                    "✅ 情景记忆DSL多词搜索成功: query=%s, user_id=%s, 找到 %d 条结果",
                    search.to_dict(),
                    user_id,
                    len(hits),
                )

            # 只返回hits部分，保持与multi_search方法一致的返回格式
            return hits

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.error(
                "❌ 情景记忆DSL多词搜索失败: query=%s, user_id=%s, error=%s",
                query,
                user_id,
                e,
            )
            raise
        except Exception as e:
            logger.error(
                "❌ 情景记忆DSL多词搜索失败（未知错误）: query=%s, user_id=%s, error=%s",
                query,
                user_id,
                e,
            )
            raise

    async def append_episodic_memory(
        self,
        event_id: str,
        user_id: str,
        timestamp: datetime,
        episode: str,
        search_content: List[str],
        user_name: Optional[str] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        group_id: Optional[str] = None,
        participants: Optional[List[str]] = None,
        event_type: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        linked_entities: Optional[List[str]] = None,
        subject: Optional[str] = None,
        memcell_event_id_list: Optional[List[str]] = None,
        extend: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> EpisodicMemoryDoc:
        """
        追加情景记忆文档

        这是一个便捷方法，结合了文档创建和索引刷新。
        适用于需要立即搜索新创建文档的场景。

        Args:
            同 append_episodic_memory 方法

        Returns:
            已保存的EpisodicMemoryDoc实例
        """
        # 创建并保存文档
        doc = await self.create_and_save_episodic_memory(
            event_id=event_id,
            user_id=user_id,
            timestamp=timestamp,
            episode=episode,
            search_content=search_content,
            user_name=user_name,
            title=title,
            summary=summary,
            group_id=group_id,
            participants=participants,
            event_type=event_type,
            keywords=keywords,
            linked_entities=linked_entities,
            subject=subject,
            memcell_event_id_list=memcell_event_id_list,
            extend=extend,
            created_at=created_at,
            updated_at=updated_at,
        )
        return doc

    # ==================== 删除功能 ====================

    async def delete_by_event_id(self, event_id: str, refresh: bool = False) -> bool:
        """
        根据event_id删除情景记忆文档

        Args:
            event_id: 事件唯一标识
            refresh: 是否立即刷新索引

        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            # 使用基类的delete_by_id方法，因为我们设置文档ID为event_id
            result = await self.delete_by_id(event_id, refresh=refresh)

            if result:
                logger.debug("✅ 根据event_id删除情景记忆成功: event_id=%s", event_id)
            else:
                logger.warning(
                    "⚠️ 根据event_id删除情景记忆失败，文档不存在: event_id=%s", event_id
                )

            return result

        except Exception as e:
            logger.error(
                "❌ 根据event_id删除情景记忆失败: event_id=%s, error=%s", event_id, e
            )
            raise

    async def delete_by_filters(
        self,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        date_range: Optional[Dict[str, Any]] = None,
        refresh: bool = False,
    ) -> int:
        """
        根据过滤条件批量删除情景记忆文档

        Args:
            user_id: 用户ID过滤
            group_id: 群组ID过滤
            date_range: 时间范围过滤，格式：{"gte": "2024-01-01", "lte": "2024-12-31"}
            refresh: 是否立即刷新索引

        Returns:
            删除的文档数量

        Examples:
            # 1. 删除特定用户的所有记忆
            await repo.delete_by_filters(user_id="user123")

            # 2. 删除特定用户在特定时间范围内的记忆
            await repo.delete_by_filters(
                user_id="user123",
                date_range={"gte": "2024-01-01", "lte": "2024-12-31"}
            )

            # 3. 删除特定群组的所有记忆
            await repo.delete_by_filters(group_id="group456")

            # 4. 组合条件删除
            await repo.delete_by_filters(
                user_id="user123",
                group_id="group456",
                date_range={"gte": "2024-01-01"}
            )
        """
        try:
            # 构建过滤条件
            filter_queries = []
            if user_id is not None:  # 使用 is not None 而不是 truthy 检查，支持空字符串
                if user_id:  # 非空字符串：个人记忆
                    filter_queries.append({"term": {"user_id": user_id}})
                else:  # 空字符串：群组记忆
                    filter_queries.append({"term": {"user_id": ""}})
            if group_id:
                filter_queries.append({"term": {"group_id": group_id}})
            if date_range:
                filter_queries.append({"range": {"timestamp": date_range}})

            # 至少需要一个过滤条件，防止误删除所有数据
            if not filter_queries:
                raise ValueError(
                    "至少需要提供一个过滤条件（user_id、group_id或date_range）"
                )

            # 构建删除查询
            delete_query = {"bool": {"must": filter_queries}}

            # 执行批量删除
            client = await self.get_client()
            index_name = self.get_index_name()

            response = await client.delete_by_query(
                index=index_name, body={"query": delete_query}, refresh=refresh
            )

            deleted_count = response.get('deleted', 0)

            logger.debug(
                "✅ 根据过滤条件批量删除情景记忆成功: user_id=%s, group_id=%s, 删除了 %d 条记录",
                user_id,
                group_id,
                deleted_count,
            )

            return deleted_count

        except ValueError as e:
            logger.error("❌ 删除参数错误: %s", e)
            raise
        except Exception as e:
            logger.error(
                "❌ 根据过滤条件批量删除情景记忆失败: user_id=%s, group_id=%s, error=%s",
                user_id,
                group_id,
                e,
            )
            raise

    # ==================== 专用查询方法 ====================

    async def get_by_user_and_timerange(
        self,
        user_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        size: int = 100,
        from_: int = 0,
        explain: bool = False,
    ) -> Dict[str, Any]:
        """
        根据用户ID和时间范围获取记忆

        Args:
            user_id: 用户ID
            start_time: 开始时间
            end_time: 结束时间
            size: 结果数量
            from_: 分页起始位置

        Returns:
            搜索结果
        """
        date_range = {}
        if start_time:
            date_range["gte"] = start_time.isoformat()
        if end_time:
            date_range["lte"] = end_time.isoformat()

        return await self.multi_search(
            query=[],  # 空查询词，纯过滤
            user_id=user_id,
            date_range=date_range if date_range else None,
            size=size,
            from_=from_,
            explain=explain,
        )
