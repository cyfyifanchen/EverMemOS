"""
前瞻 Milvus 仓库

基于 BaseMilvusRepository 的前瞻专用仓库类，提供高效的向量存储和检索功能。
主要功能包括向量存储、相似性搜索、过滤查询和文档管理。
支持个人前瞻和群组前瞻。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import json
from core.oxm.milvus.base_repository import BaseMilvusRepository
from infra_layer.adapters.out.search.milvus.memory.foresight_collection import (
    ForesightCollection,
)
from core.observation.logger import get_logger
from common_utils.datetime_utils import get_now_with_timezone
from core.di.decorators import repository


logger = get_logger(__name__)

# Milvus 检索配置（None 表示不启用半径过滤）
MILVUS_SIMILARITY_RADIUS = None  # COSINE 相似度阈值，可选范围 [-1, 1]


@repository("foresight_milvus_repository", primary=False)
class ForesightMilvusRepository(BaseMilvusRepository[ForesightCollection]):
    """
    前瞻 Milvus 仓库

    基于 BaseMilvusRepository 的专用仓库类，提供：
    - 高效的向量存储和检索
    - 相似性搜索和过滤功能
    - 文档创建和管理
    - 向量索引管理
    
    同时支持个人前瞻和群组前瞻。
    """

    def __init__(self):
        """初始化前瞻仓库"""
        super().__init__(ForesightCollection)

    # ==================== 文档创建和管理 ====================
    # TODO:添加 username 
    async def create_and_save_foresight_mem(
        self,
        id: str,
        user_id: Optional[str],
        content: str,
        parent_episode_id: str,
        vector: List[float],
        group_id: Optional[str] = None,
        event_type: Optional[str] = None,
        participants: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        duration_days: Optional[int] = None,
        evidence: Optional[str] = None,
        search_content: Optional[List[str]] = None,
        extend: Optional[Dict[str, Any]] = None,
        vector_model: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        创建并保存个人前瞻文档

        Args:
            id: 前瞻唯一标识
            user_id: 用户ID（必需）
            content: 前瞻内容（必需）
            parent_episode_id: 父情景记忆ID（必需）
            vector: 文本向量（必需）
            group_id: 群组ID
            participants: 相关参与者列表
            start_time: 前瞻开始时间
            end_time: 前瞻结束时间
            duration_days: 持续天数
            evidence: 支持该前瞻的证据
            search_content: 搜索内容列表
            extend: 扩展字段
            vector_model: 向量化模型
            created_at: 创建时间
            updated_at: 更新时间

        Returns:
            已保存的文档信息
        """
        try:
            # 设置默认时间戳
            now = get_now_with_timezone()
            if created_at is None:
                created_at = now
            if updated_at is None:
                updated_at = now

            # 构建搜索内容
            if search_content is None:
                search_content = [content]
                if evidence:
                    search_content.append(evidence)

            # 准备元数据
            metadata = {"vector_model": vector_model or "", "extend": extend or {}}

            # 准备实体数据
            entity = {
                "id": id,
                "vector": vector,
                "user_id": user_id or "",
                "group_id": group_id or "",
                "participants": participants or [],
                "parent_episode_id": parent_episode_id,
                "start_time": int(start_time.timestamp()) if start_time else 0,
                "end_time": int(end_time.timestamp()) if end_time else 0,
                "duration_days": duration_days or 0,
                "content": content,
                "evidence": evidence or "",
                "event_type": event_type,
                "search_content": json.dumps(search_content, ensure_ascii=False),
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "created_at": int(created_at.timestamp()),
                "updated_at": int(updated_at.timestamp()),
            }

            # 插入数据
            await self.insert(entity)

            logger.debug(
                "✅ 创建个人前瞻文档成功: memory_id=%s, user_id=%s", id, user_id,
            )

            return {
                "id": id,
                "user_id": user_id,
                "content": content,
                "parent_episode_id": parent_episode_id,
                "search_content": search_content,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error("❌ 创建个人前瞻文档失败: id=%s, error=%s", id, e)
            raise

    # ==================== 搜索功能 ====================

    async def vector_search(
        self,
        query_vector: List[float],
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        parent_episode_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        current_time: Optional[datetime] = None,
        limit: int = 10,
        score_threshold: float = 0.0,
        radius: Optional[float] = None,
        participant_user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        向量相似性搜索

        Args:
            query_vector: 查询向量
            user_id: 用户ID过滤
            group_id: 群组ID过滤
            parent_episode_id: 父情景记忆ID过滤
            start_time: 前瞻开始时间过滤
            end_time: 前瞻结束时间过滤
            current_time: 当前时间，用于过滤有效期内的前瞻
            limit: 返回结果数量
            score_threshold: 相似度阈值
            radius: COSINE 相似度阈值（可选，默认使用 MILVUS_SIMILARITY_RADIUS）
            participant_user_id: 群组检索时额外要求参与者包含该用户

        Returns:
            搜索结果列表
        """
        try:
            # 构建过滤表达式
            filter_expr = []

            if user_id:
                filter_expr.append(f'user_id == "{user_id}"')
            else:
                # 如果没有传 user_id,则过滤所有非空 user_id
                filter_expr.append('user_id == ""')
            if group_id:
                filter_expr.append(f'group_id == "{group_id}"')

            if participant_user_id:
                filter_expr.append(
                    f'array_contains(participants, "{participant_user_id}")'
                )
            if group_id:
                filter_expr.append(f'group_id == "{group_id}"')
            if parent_episode_id:
                filter_expr.append(f'parent_episode_id == "{parent_episode_id}"')
            if start_time:
                filter_expr.append(f"start_time >= {int(start_time.timestamp())}")
            if end_time:
                filter_expr.append(f"end_time <= {int(end_time.timestamp())}")
            if current_time:
                # 过滤出当前时间在有效期内的前瞻
                current_ts = int(current_time.timestamp())
                filter_expr.append(
                    f"(start_time <= {current_ts} and end_time >= {current_ts})"
                )

            filter_str = " and ".join(filter_expr) if filter_expr else None

            # 执行搜索
            # 动态调整 ef 参数：必须 >= limit，通常设为 limit 的 1.5-2 倍
            ef_value = max(128, limit * 2)  # 确保 ef >= limit，至少 128
            # 使用 COSINE 相似度，radius 表示只返回相似度 >= 阈值的结果
            # 优先使用传入的 radius 参数，否则使用默认配置
            similarity_radius = (
                radius if radius is not None else MILVUS_SIMILARITY_RADIUS
            )
            search_params = {"metric_type": "COSINE", "params": {"ef": ef_value}}
            # 不设置 radius 参数!
            # Milvus 的 radius 是相似度下限,设置过低的值反而可能导致问题
            # 只在明确指定且 > -1.0 时才设置
            if radius is not None and radius > -1.0:
                search_params["params"]["radius"] = radius
            elif similarity_radius is not None and similarity_radius > -1.0:
                search_params["params"]["radius"] = similarity_radius

            results = await self.collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=limit,
                expr=filter_str,
                output_fields=self.all_output_fields,
            )

            # 处理结果
            search_results = []
            raw_hit_count = sum(len(hits) for hits in results)
            logger.info(
                f"Milvus 原始返回: {raw_hit_count} 条结果, "
                f"limit={limit}, filter_str={filter_str}, "
            )

            for hits in results:
                for hit in hits:
                    if hit.score >= score_threshold:
                        # 解析元数据
                        metadata_json = hit.entity.get("metadata", "{}")
                        metadata = json.loads(metadata_json) if metadata_json else {}

                        # 解析 search_content（统一为 JSON 数组格式）
                        search_content_raw = hit.entity.get("search_content", "[]")
                        search_content = (
                            json.loads(search_content_raw) if search_content_raw else []
                        )

                        # 构建结果
                        result = {
                            "id": hit.entity.get("id"),
                            "score": float(hit.score),
                            "user_id": hit.entity.get("user_id"),
                            "group_id": hit.entity.get("group_id"),
                            "parent_episode_id": hit.entity.get("parent_episode_id"),
                            "start_time": datetime.fromtimestamp(
                                hit.entity.get("start_time", 0)
                            ),
                            "end_time": datetime.fromtimestamp(
                                hit.entity.get("end_time", 0)
                            ),
                            "duration_days": hit.entity.get("duration_days"),
                            "content": hit.entity.get("content"),
                            "evidence": hit.entity.get("evidence"),
                            "search_content": search_content,
                            "metadata": metadata,
                        }
                        search_results.append(result)

            logger.debug("✅ 向量搜索成功: 找到 %d 条结果", len(search_results))
            return search_results

        except Exception as e:
            logger.error("❌ 向量搜索失败: %s", e)
            raise

    # ==================== 删除功能 ====================

    async def delete_by_id(self, memory_id: str) -> bool:
        """
        根据memory_id删除前瞻文档

        Args:
            memory_id: 前瞻唯一标识

        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            success = await super().delete_by_id(memory_id)
            if success:
                logger.debug(
                    "✅ 根据memory_id删除前瞻成功: memory_id=%s", memory_id
                )
            return success
        except Exception as e:
            logger.error(
                "❌ 根据memory_id删除前瞻失败: memory_id=%s, error=%s", memory_id, e
            )
            return False

    async def delete_by_parent_episode_id(self, parent_episode_id: str) -> int:
        """
        根据父情景记忆ID删除所有关联的前瞻

        Args:
            parent_episode_id: 父情景记忆ID

        Returns:
            删除的文档数量
        """
        try:
            expr = f'parent_episode_id == "{parent_episode_id}"'

            # 先查询要删除的文档数量
            results = await self.collection.query(expr=expr, output_fields=["id"])
            delete_count = len(results)

            if delete_count > 0:
                # 执行删除
                await self.collection.delete(expr)

            logger.debug(
                "✅ 根据parent_episode_id删除前瞻成功: 删除了 %d 条记录", delete_count
            )
            return delete_count

        except Exception as e:
            logger.error("❌ 根据parent_episode_id删除前瞻失败: %s", e)
            raise

    async def delete_by_filters(
        self,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        根据过滤条件批量删除前瞻文档

        Args:
            user_id: 用户ID过滤
            group_id: 群组ID过滤
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            删除的文档数量
        """
        try:
            # 构建过滤表达式
            filter_expr = []
            if user_id is not None:  # 使用 is not None 而不是 truthy 检查，支持空字符串
                if user_id:  # 非空字符串：个人记忆
                    # 同时检查 user_id 字段和 participants 数组
                    user_filter = f'(user_id == "{user_id}" or array_contains(participants, "{user_id}"))'
                    filter_expr.append(user_filter)
                else:  # 空字符串：群组记忆
                    filter_expr.append('user_id == ""')
            if group_id:
                filter_expr.append(f'group_id == "{group_id}"')
            if start_time:
                filter_expr.append(f"start_time >= {int(start_time.timestamp())}")
            if end_time:
                filter_expr.append(f"end_time <= {int(end_time.timestamp())}")

            if not filter_expr:
                raise ValueError("至少需要提供一个过滤条件")

            expr = " and ".join(filter_expr)

            # 先查询要删除的文档数量
            results = await self.collection.query(expr=expr, output_fields=["id"])
            delete_count = len(results)

            # 执行删除
            await self.collection.delete(expr)

            logger.debug(
                "✅ 根据过滤条件批量删除前瞻成功: 删除了 %d 条记录", delete_count
            )
            return delete_count

        except Exception as e:
            logger.error("❌ 根据过滤条件批量删除前瞻失败: %s", e)
            raise
