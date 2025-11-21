from datetime import datetime
from token import OP
from typing import List, Optional, Dict, Any
from core.oxm.mongo.document_base import DocumentBase
from pydantic import Field, ConfigDict
from pymongo import IndexModel, ASCENDING, DESCENDING
from core.oxm.mongo.audit_base import AuditBase
from beanie import PydanticObjectId


class EpisodicMemory(DocumentBase, AuditBase):
    """
    情景记忆文档模型

    存储用户的情景记忆，包含事件摘要、参与者、主题等信息。
    从 MemCell 摘要直接转存而来。
    """

    user_id: Optional[str] = Field(default=None, description="当事人，None表示群组记忆")
    user_name: Optional[str] = Field(default=None, description="当事人名称")
    group_id: Optional[str] = Field(default=None, description="群组ID")
    group_name: Optional[str] = Field(default=None, description="群组名称")
    timestamp: datetime = Field(..., description="发生时间（时间戳）")
    participants: Optional[List[str]] = Field(
        default=None, description="事件参与者名字"
    )
    summary: str = Field(..., min_length=1, description="记忆单元")
    subject: Optional[str] = Field(default=None, description="记忆单元主题")
    episode: str = Field(..., min_length=1, description="情景记忆")
    type: Optional[str] = Field(default=None, description="情景类型，如Conversation等")
    keywords: Optional[List[str]] = Field(default=None, description="关键词")
    linked_entities: Optional[List[str]] = Field(
        default=None, description="关联的实体ID"
    )

    memcell_event_id_list: Optional[List[str]] = Field(
        default=None, description="记忆单元事件ID"
    )

    extend: Optional[Dict[str, Any]] = Field(default=None, description="备用拓展字段")

    vector: Optional[List[float]] = Field(default=None, description="文本向量")
    vector_model: Optional[str] = Field(default=None, description="使用的向量化模型")

    model_config = ConfigDict(
        collection="episodic_memories",
        validate_assignment=True,
        json_encoders={datetime: lambda dt: dt.isoformat()},
        json_schema_extra={
            "example": {
                "user_id": "user_12345",
                "group_id": "group_work",
                "timestamp": 1701388800,
                "participants": ["张三", "李四"],
                "summary": "讨论了项目进度和下周计划",
                "subject": "项目会议",
                "episode": "在会议室进行了项目进度讨论，确定了下周的开发任务分配",
                "type": "Conversation",
                "keywords": ["项目", "进度", "会议"],
                "linked_entities": ["proj_001", "task_123"],
                "extend": {"priority": "high", "location": "会议室A"},
            }
        },
    )

    @property
    def event_id(self) -> Optional[PydanticObjectId]:
        return self.id

    class Settings:
        """Beanie 设置"""

        name = "episodic_memories"
        indexes = [
            # 用户ID和时间戳复合索引
            IndexModel(
                [("user_id", ASCENDING), ("timestamp", DESCENDING)],
                name="idx_user_timestamp",
            ),
            # 群组ID和时间戳复合索引
            IndexModel(
                [("group_id", ASCENDING), ("timestamp", DESCENDING)],
                name="idx_group_timestamp",
            ),
            # 关键词索引
            IndexModel([("keywords", ASCENDING)], name="idx_keywords", sparse=True),
            # 关联实体索引
            IndexModel(
                [("linked_entities", ASCENDING)],
                name="idx_linked_entities",
                sparse=True,
            ),
            # 审计字段索引
            IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
            IndexModel([("updated_at", DESCENDING)], name="idx_updated_at"),
        ]
        validate_on_save = True
        use_state_management = True
