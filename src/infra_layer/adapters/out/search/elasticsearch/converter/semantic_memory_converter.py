"""
语义记忆 ES 转换器

负责将 MongoDB 的语义记忆文档转换为 Elasticsearch 的 SemanticMemoryDoc 文档。
支持个人和群组语义记忆。
"""

from typing import List
import jieba

from core.oxm.es.base_converter import BaseEsConverter
from core.observation.logger import get_logger
from core.nlp.stopwords_utils import filter_stopwords
from infra_layer.adapters.out.search.elasticsearch.memory.semantic_memory import (
    SemanticMemoryDoc,
)
from infra_layer.adapters.out.persistence.document.memory.semantic_memory_record import (
    SemanticMemoryRecord as MongoSemanticMemoryRecord,
)
from datetime import datetime

logger = get_logger(__name__)


class SemanticMemoryConverter(BaseEsConverter[SemanticMemoryDoc]):
    """
    语义记忆 ES 转换器
    
    将 MongoDB 的语义记忆文档转换为 Elasticsearch 的 SemanticMemoryDoc 文档。
    支持个人和群组语义记忆。
    """

    @classmethod
    def from_mongo(cls, source_doc: MongoSemanticMemoryRecord) -> SemanticMemoryDoc:
        """
        从 MongoDB 语义记忆文档转换为 ES SemanticMemoryDoc 文档

        Args:
            source_doc: MongoDB 语义记忆文档实例

        Returns:
            SemanticMemoryDoc: ES 文档实例
        """
        if source_doc is None:
            raise ValueError("MongoDB 文档不能为空")

        try:
            # 构建搜索内容列表，用于 BM25 检索
            search_content = cls._build_search_content(source_doc)
            
            # 解析时间
            timestamp = None
            if source_doc.start_time:
                if isinstance(source_doc.start_time, str):
                    timestamp = datetime.fromisoformat(source_doc.start_time.replace('Z', '+00:00'))
                elif isinstance(source_doc.start_time, datetime):
                    timestamp = source_doc.start_time
            
            if not timestamp:
                timestamp = source_doc.created_at or datetime.now()
            
            # 创建 ES 文档实例
            # 通过 meta 参数传递 id,确保幂等性(MongoDB _id -> ES _id)
            es_doc = SemanticMemoryDoc(
                meta={'id': str(source_doc.id)},
                user_id=source_doc.user_id,
                user_name=source_doc.user_name or "",
                # 时间字段
                timestamp=timestamp,
                # 核心内容字段
                semantic=source_doc.content,
                evidence=source_doc.evidence or "",
                search_content=search_content,  # BM25 搜索的核心字段
                # 分类和标签字段
                group_id=source_doc.group_id,
                group_name=source_doc.group_name or "",
                participants=source_doc.participants,
                type="Conversation",  # 事件类型
                keywords=None,
                linked_entities=None,
                # MongoDB 特有字段
                subject=source_doc.content[:100] if source_doc.content else "",
                memcell_event_id_list=[source_doc.parent_episode_id] if source_doc.parent_episode_id else None,
                # 扩展字段
                extend={
                    "parent_episode_id": source_doc.parent_episode_id,
                    "start_time": source_doc.start_time,
                    "end_time": source_doc.end_time,
                    "duration_days": source_doc.duration_days,
                    "vector_model": source_doc.vector_model,
                    **(source_doc.extend or {}),
                },
                # 审计字段
                created_at=source_doc.created_at,
                updated_at=source_doc.updated_at,
            )

            return es_doc

        except Exception as e:
            logger.error("从 MongoDB 语义记忆文档转换为 ES 文档失败: %s", e)
            raise

    @classmethod
    def _build_search_content(cls, source_doc: MongoSemanticMemoryRecord) -> List[str]:
        """
        构建搜索内容列表
        
        对中文文本进行分词，并过滤停用词，生成用于 BM25 检索的关键词列表。
        """
        search_content = []
        
        # 分词 content
        if source_doc.content:
            words = jieba.lcut(source_doc.content)
            words = filter_stopwords(words)
            search_content.extend(words)
        
        # # 分词 evidence
        # if source_doc.evidence:
        #     words = jieba.lcut(source_doc.evidence)
        #     words = filter_stopwords(words)
        #     search_content.extend(words)
        
        # 去重并保持顺序
        seen = set()
        unique_content = []
        for word in search_content:
            if word not in seen and word.strip():
                seen.add(word)
                unique_content.append(word)
        
        return unique_content if unique_content else [""]

