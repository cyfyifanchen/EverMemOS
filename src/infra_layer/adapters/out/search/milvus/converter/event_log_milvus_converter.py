"""
事件日志 Milvus 转换器

负责将 MongoDB 的EventLog文档转换为 Milvus Collection 实体，支持个人与群组。
"""

from typing import Dict, Any
import json

from core.oxm.milvus.base_converter import BaseMilvusConverter
from core.observation.logger import get_logger
from infra_layer.adapters.out.search.milvus.memory.event_log_collection import (
    EventLogCollection,
)
from infra_layer.adapters.out.persistence.document.memory.event_log_record import (
    EventLogRecord as MongoEventLogRecord,
)
from memory_layer.types import RawDataType

logger = get_logger(__name__)


class EventLogMilvusConverter(BaseMilvusConverter[EventLogCollection]):
    """
    事件日志 Milvus 转换器
    
    将 MongoDB 的EventLog文档转换为 Milvus Collection 实体。
    使用独立的 EventLogCollection，支持个人和群组事件日志。
    """

    @classmethod
    def from_mongo(cls, source_doc: MongoEventLogRecord) -> Dict[str, Any]:
        """
        从 MongoDB EventLog 文档转换为 Milvus Collection 实体

        Args:
            source_doc: MongoDB 的 EventLog 文档实例

        Returns:
            Dict[str, Any]: Milvus 实体字典，可直接用于插入
        """
        if source_doc is None:
            raise ValueError("MongoDB 文档不能为空")

        try:
            # 转换时间戳
            timestamp = (
                int(source_doc.timestamp.timestamp())
                if source_doc.timestamp
                else 0
            )
            
            # 构建搜索内容
            search_content = cls._build_search_content(source_doc)
            
            
            # 创建 Milvus 实体字典
            milvus_entity = {
                # 基础标识字段
                "id": str(source_doc.id),  # 使用 Beanie 的 id 属性
                "user_id": source_doc.user_id or "",
                "group_id": source_doc.group_id or "",
                "participants": source_doc.participants if source_doc.participants else [],
                "parent_episode_id": source_doc.parent_episode_id or "",
                # 事件类型和时间字段
                "event_type": source_doc.event_type or RawDataType.CONVERSATION.value,
                "timestamp": timestamp,
                # 核心内容字段
                "atomic_fact": source_doc.atomic_fact,
                "search_content": search_content,
                # 详细信息 JSON
                "metadata": json.dumps(cls._build_detail(source_doc), ensure_ascii=False),
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
                # 向量字段
                "vector": source_doc.vector if source_doc.vector else [],
            }

            return milvus_entity

        except Exception as e:
            logger.error("从 MongoDB EventLog 文档转换为 Milvus 实体失败: %s", e)
            raise

    @classmethod
    def _build_detail(cls, source_doc: MongoEventLogRecord) -> Dict[str, Any]:
        """构建详细信息字典"""
        detail = {
            "vector_model": source_doc.vector_model,
            "extend": source_doc.extend,
        }
        
        # 过滤掉 None 值
        return {k: v for k, v in detail.items() if v is not None}

    @staticmethod
    def _build_search_content(source_doc: MongoEventLogRecord) -> str:
        """构建搜索内容（JSON 列表格式）"""
        text_content = []
        
        if source_doc.atomic_fact:
            text_content.append(source_doc.atomic_fact)
        
        return json.dumps(text_content, ensure_ascii=False)

