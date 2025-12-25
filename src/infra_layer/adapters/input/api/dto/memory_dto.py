# -*- coding: utf-8 -*-
"""
Memory API DTO

Request and response data transfer objects for Memory API.
These models are used to define OpenAPI parameter documentation.
"""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class MemorizeMessageRequest(BaseModel):
    """
    Store single message request body

    Used for POST /api/v1/memories endpoint
    """

    group_id: Optional[str] = Field(
        default=None, description="Group ID", examples=["group_123"]
    )
    group_name: Optional[str] = Field(
        default=None, description="Group name", examples=["Project Discussion Group"]
    )
    message_id: str = Field(
        ..., description="Message unique identifier", examples=["msg_001"]
    )
    create_time: str = Field(
        ...,
        description="Message creation time (ISO 8601 format)",
        examples=["2025-01-15T10:00:00+00:00"],
    )
    sender: str = Field(..., description="Sender user ID", examples=["user_001"])
    sender_name: Optional[str] = Field(
        default=None,
        description="Sender name (uses sender if not provided)",
        examples=["John"],
    )
    content: str = Field(
        ...,
        description="Message content",
        examples=["Let's discuss the technical solution for the new feature today"],
    )
    refer_list: Optional[List[str]] = Field(
        default=None,
        description="List of referenced message IDs",
        examples=[["msg_000"]],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "group_id": "group_123",
                "group_name": "Project Discussion Group",
                "message_id": "msg_001",
                "create_time": "2025-01-15T10:00:00+00:00",
                "sender": "user_001",
                "sender_name": "John",
                "content": "Let's discuss the technical solution for the new feature today",
                "refer_list": ["msg_000"],
            }
        }
    }


class FetchMemoriesParams(BaseModel):
    """
    Query parameters for fetching user memories

    Used for GET /api/v1/memories endpoint
    """

    user_id: str = Field(..., description="User ID", examples=["user_123"])
    memory_type: Optional[str] = Field(
        default="episodic_memory",
        description="""Memory type, enum values from MemoryType:
- profile: user profile
- episodic_memory: episodic memory (default)
- foresight: prospective memory
- event_log: event log (atomic facts)""",
        examples=["profile"],
    )
    limit: Optional[int] = Field(
        default=10,
        description="Maximum number of memories to return",
        ge=1,
        le=100,
        examples=[20],
    )
    offset: Optional[int] = Field(
        default=0, description="Pagination offset", ge=0, examples=[0]
    )
    sort_by: Optional[str] = Field(
        default=None, description="Sort field", examples=["created_at"]
    )
    sort_order: Optional[str] = Field(
        default="desc",
        description="""Sort direction, enum values:
- asc: ascending order
- desc: descending order (default)""",
        examples=["desc"],
    )
    version_range: Optional[List[Optional[str]]] = Field(
        default=None,
        description="Version range filter, format [start, end], closed interval",
        examples=[["v1.0", "v2.0"]],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_123",
                "memory_type": "profile",
                "limit": 20,
                "offset": 0,
                "sort_order": "desc",
            }
        }
    }


class SearchMemoriesRequest(BaseModel):
    """
    Search memories request parameters

    Used for GET /api/v1/memories/search endpoint
    Supports passing parameters via query params or body
    """

    user_id: Optional[str] = Field(
        default=None,
        description="User ID (at least one of user_id or group_id must be provided)",
        examples=["user_123"],
    )
    group_id: Optional[str] = Field(
        default=None,
        description="Group ID (at least one of user_id or group_id must be provided)",
        examples=["group_456"],
    )
    query: Optional[str] = Field(
        default=None, description="Search query text", examples=["coffee preference"]
    )
    retrieve_method: Optional[str] = Field(
        default="keyword",
        description="""Retrieval method, enum values from RetrieveMethod:
- keyword: keyword retrieval (BM25, default)
- vector: vector semantic retrieval
- hybrid: hybrid retrieval (keyword + vector)
- rrf: RRF fusion retrieval (keyword + vector + RRF ranking fusion)
- agentic: LLM-guided multi-round intelligent retrieval""",
        examples=["keyword"],
    )
    top_k: Optional[int] = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=100,
        examples=[10],
    )
    memory_types: Optional[List[str]] = Field(
        default=None,
        description="""List of memory types to retrieve, enum values from MemoryType:
- episodic_memory: episodic memory
- foresight: prospective memory
- event_log: event log (atomic facts)
Note: profile type is not supported in search interface""",
        examples=[["episodic_memory"]],
    )
    start_time: Optional[str] = Field(
        default=None,
        description="Time range start (ISO 8601 format)",
        examples=["2024-01-01T00:00:00"],
    )
    end_time: Optional[str] = Field(
        default=None,
        description="Time range end (ISO 8601 format)",
        examples=["2024-12-31T23:59:59"],
    )
    radius: Optional[float] = Field(
        default=None,
        description="COSINE similarity threshold for vector retrieval (only for vector and hybrid methods, default 0.6)",
        ge=0.0,
        le=1.0,
        examples=[0.6],
    )
    include_metadata: Optional[bool] = Field(
        default=True, description="Whether to include metadata", examples=[True]
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional filter conditions", examples=[{}]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_123",
                "query": "coffee preference",
                "retrieve_method": "keyword",
                "top_k": 10,
                "memory_types": ["episode_memory"],
            }
        }
    }


class UserDetailRequest(BaseModel):
    """User detail request model"""

    full_name: str = Field(..., description="User full name", examples=["John Smith"])
    role: Optional[str] = Field(
        default=None, description="User role", examples=["developer"]
    )
    extra: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional information",
        examples=[{"department": "Engineering"}],
    )


class ConversationMetaCreateRequest(BaseModel):
    """
    Save conversation metadata request body

    Used for POST /api/v1/memories/conversation-meta endpoint
    """

    version: str = Field(..., description="Metadata version number", examples=["1.0"])
    scene: str = Field(
        ...,
        description="""Scene identifier, enum values from ScenarioType:
- group_chat: work/group chat scenario, suitable for group conversations such as multi-person collaboration and project discussions
- assistant: assistant scenario, suitable for one-on-one AI assistant conversations""",
        examples=["group_chat"],
    )
    scene_desc: Dict[str, Any] = Field(
        ...,
        description="Scene description object, can include fields like bot_ids",
        examples=[{"bot_ids": ["bot_001"], "type": "project_discussion"}],
    )
    name: str = Field(
        ..., description="Conversation name", examples=["Project Discussion Group"]
    )
    description: Optional[str] = Field(
        default=None,
        description="Conversation description",
        examples=["Technical discussion for new feature development"],
    )
    group_id: str = Field(
        ..., description="Group unique identifier", examples=["group_123"]
    )
    created_at: str = Field(
        ...,
        description="Conversation creation time (ISO 8601 format)",
        examples=["2025-01-15T10:00:00+00:00"],
    )
    default_timezone: Optional[str] = Field(
        default=None, description="Default timezone", examples=["UTC"]
    )
    user_details: Optional[Dict[str, UserDetailRequest]] = Field(
        default=None,
        description="Participant details, key is user ID, value is user detail object",
        examples=[
            {
                "user_001": {
                    "full_name": "John Smith",
                    "role": "developer",
                    "extra": {"department": "Engineering"},
                },
                "user_002": {
                    "full_name": "Jane Doe",
                    "role": "designer",
                    "extra": {"department": "Design"},
                },
            }
        ],
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Tag list", examples=[["work", "technical"]]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "version": "1.0",
                "scene": "group_chat",
                "scene_desc": {"bot_ids": ["bot_001"], "type": "project_discussion"},
                "name": "Project Discussion Group",
                "description": "Technical discussion for new feature development",
                "group_id": "group_123",
                "created_at": "2025-01-15T10:00:00+00:00",
                "default_timezone": "UTC",
                "user_details": {
                    "user_001": {
                        "full_name": "John Smith",
                        "role": "developer",
                        "extra": {"department": "Engineering"},
                    }
                },
                "tags": ["work", "technical"],
            }
        }
    }


class ConversationMetaPatchRequest(BaseModel):
    """
    Partial update conversation metadata request body

    Used for PATCH /api/v1/memories/conversation-meta endpoint
    """

    group_id: str = Field(
        ..., description="Group ID to update (required)", examples=["group_123"]
    )
    name: Optional[str] = Field(
        default=None,
        description="New conversation name",
        examples=["New Conversation Name"],
    )
    description: Optional[str] = Field(
        default=None,
        description="New conversation description",
        examples=["Updated description"],
    )
    scene_desc: Optional[Dict[str, Any]] = Field(
        default=None,
        description="New scene description",
        examples=[{"bot_ids": ["bot_002"]}],
    )
    tags: Optional[List[str]] = Field(
        default=None, description="New tag list", examples=[["tag1", "tag2"]]
    )
    user_details: Optional[Dict[str, UserDetailRequest]] = Field(
        default=None,
        description="New user details (will completely replace existing user_details)",
        examples=[{"user_001": {"full_name": "John Smith", "role": "lead"}}],
    )
    default_timezone: Optional[str] = Field(
        default=None, description="New default timezone", examples=["Asia/Shanghai"]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "group_id": "group_123",
                "name": "New Conversation Name",
                "tags": ["updated", "tags"],
            }
        }
    }
