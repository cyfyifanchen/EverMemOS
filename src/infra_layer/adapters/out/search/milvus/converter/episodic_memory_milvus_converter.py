"""
情景记忆 Milvus 转换器

负责将 MongoDB 的 EpisodicMemory 文档转换为 Milvus Collection 实体。
主要处理字段映射、向量构建和数据格式转换。
"""

from typing import Dict, Any
import json

from core.oxm.milvus.base_converter import BaseMilvusConverter
from core.observation.logger import get_logger
from infra_layer.adapters.out.search.milvus.memory.episodic_memory_collection import (
    EpisodicMemoryCollection,
)
from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
    EpisodicMemory as MongoEpisodicMemory,
)

logger = get_logger(__name__)


class EpisodicMemoryMilvusConverter(BaseMilvusConverter[EpisodicMemoryCollection]):
    """
    EpisodicMemory Milvus 转换器

    将 MongoDB 的 EpisodicMemory 文档转换为 Milvus Collection 实体。
    主要处理字段映射、向量构建和数据格式转换。
    Milvus Collection 类型自动从泛型 BaseMilvusConverter[EpisodicMemoryCollection] 中获取。
    """

    @classmethod
    def from_mongo(cls, source_doc: MongoEpisodicMemory) -> Dict[str, Any]:
        """
        从 MongoDB EpisodicMemory 文档转换为 Milvus Collection 实体

        使用场景：
        - Milvus 索引重建时，从 MongoDB 文档转换为 Milvus 实体
        - 数据同步时，确保 MongoDB 数据正确映射到 Milvus 字段
        - 处理字段映射和数据格式转换

        Args:
            source_doc: MongoDB 的 EpisodicMemory 文档实例

        Returns:
            Dict[str, Any]: Milvus 实体字典，可直接用于插入

        Raises:
            Exception: 当转换过程中发生错误时抛出异常
        """
        # 基本验证
        if source_doc is None:
            raise ValueError("MongoDB 文档不能为空")

        try:
            # 转换时间戳为整数
            timestamp = (
                int(source_doc.timestamp.timestamp()) if source_doc.timestamp else 0
            )

            # 创建 Milvus 实体字典
            milvus_entity = {
                # 基础标识字段
                "id": str(source_doc.id),  # 使用 Beanie 的 id 属性
                "user_id": source_doc.user_id or "",  # None 转换为空字符串
                "group_id": getattr(source_doc, 'group_id', ""),
                "participants": getattr(
                    source_doc, 'participants', []
                ),  # 添加 participants
                # 时间字段 - 转换为 Unix 时间戳
                "timestamp": timestamp,
                # 核心内容字段
                "episode": source_doc.episode,
                "search_content": cls._build_search_content(source_doc),
                # 分类字段
                "event_type": (
                    str(source_doc.type)
                    if hasattr(source_doc, 'type') and source_doc.type
                    else ""
                ),
                # 元数据 JSON（详细信息）
                "metadata": json.dumps(
                    cls._build_detail(source_doc), ensure_ascii=False
                ),
                # 审计字段
                "created_at": (
                    int(source_doc.created_at.timestamp())
                    if source_doc.created_at
                    else 0
                ),
                "updated_at": (
                    int(source_doc.updated_at.timestamp())
                    if source_doc.updated_at
                    else 0
                ),
                # 向量字段 - 需要外部设置
                "vector": (
                    source_doc.vector
                    if hasattr(source_doc, 'vector') and source_doc.vector
                    else []
                ),
            }

            return milvus_entity

        except Exception as e:
            logger.error("从 MongoDB 文档转换为 Milvus 实体失败: %s", e)
            raise

    @classmethod
    def _build_detail(cls, source_doc: MongoEpisodicMemory) -> Dict[str, Any]:
        """
        构建详细信息字典

        将不适合直接存储在 Milvus 字段中的数据整合到 detail JSON 中。
        这些数据通常不用于检索，但在获取结果时可能需要展示。

        Args:
            source_doc: MongoDB 的 EpisodicMemory 文档实例

        Returns:
            Dict[str, Any]: 详细信息字典
        """
        detail = {
            # 用户信息
            "user_name": getattr(source_doc, 'user_name', None),
            # 内容相关
            "title": getattr(source_doc, 'subject', None),
            "summary": getattr(source_doc, 'summary', None),
            # 分类和标签
            "participants": getattr(source_doc, 'participants', None),
            "keywords": getattr(source_doc, 'keywords', None),
            "linked_entities": getattr(source_doc, 'linked_entities', None),
            # MongoDB 特有字段
            "subject": getattr(source_doc, 'subject', None),
            "memcell_event_id_list": getattr(source_doc, 'memcell_event_id_list', None),
            # 扩展字段
            "extend": getattr(source_doc, 'extend', None),
        }

        # 过滤掉 None 值
        return {k: v for k, v in detail.items() if v is not None}

    @staticmethod
    def _build_search_content(source_doc: MongoEpisodicMemory) -> str:
        """
        构建搜索内容

        将文档中的关键文本内容组合成搜索内容列表，返回 JSON 字符串。

        Args:
            source_doc: MongoDB 的 EpisodicMemory 文档实例

        Returns:
            str: 搜索内容 JSON 字符串（列表格式）
        """
        text_content = []

        # 收集所有文本内容（按优先级：主题 -> 摘要 -> 内容）
        if hasattr(source_doc, 'subject') and source_doc.subject:
            text_content.append(source_doc.subject)

        if hasattr(source_doc, 'summary') and source_doc.summary:
            text_content.append(source_doc.summary)

        if hasattr(source_doc, 'episode') and source_doc.episode:
            # episode 可能很长，只取前 500 字符
            text_content.append(source_doc.episode[:500])

        # 返回 JSON 字符串列表格式，保持与 MemCell 同步逻辑一致
        return json.dumps(text_content, ensure_ascii=False)
