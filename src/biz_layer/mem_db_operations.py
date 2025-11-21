"""
数据库操作和数据转换相关函数
从 mem_memorize.py 中提取的数据库操作和数据转换逻辑

本模块包含以下功能：
1. 时间处理函数：统一处理各种时间格式，确保数据库存储的时间格式一致性
2. 数据转换函数：将业务层对象转换为数据库文档格式
3. 数据库操作函数：执行具体的数据库CRUD操作
4. 状态表操作函数：管理对话状态的生命周期
"""

import time
from memory_layer.memory_manager import MemorizeRequest
from memory_layer.types import MemoryType, MemCell, Memory, RawDataType
from memory_layer.memcell_extractor.base_memcell_extractor import RawData
from memory_layer.memory_extractor.profile_memory_extractor import ProfileMemory
from memory_layer.memory_extractor.group_profile_memory_extractor import (
    GroupProfileMemory,
)
from memory_layer.memory_extractor.profile_memory_extractor import (
    GroupImportanceEvidence,
    ImportanceEvidence,
)
from core.di import get_bean_by_type
from infra_layer.adapters.out.persistence.repository.conversation_status_raw_repository import (
    ConversationStatusRawRepository,
)
from infra_layer.adapters.out.persistence.repository.group_user_profile_memory_raw_repository import (
    GroupUserProfileMemoryRawRepository,
)
from infra_layer.adapters.out.persistence.repository.group_profile_raw_repository import (
    GroupProfileRawRepository,
)
from infra_layer.adapters.out.persistence.repository.core_memory_raw_repository import (
    CoreMemoryRawRepository,
)
from infra_layer.adapters.out.persistence.repository.memcell_raw_repository import (
    MemCellRawRepository,
)
from infra_layer.adapters.out.persistence.document.memory.core_memory import CoreMemory
from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
    EpisodicMemory,
)
from infra_layer.adapters.out.persistence.document.memory.memcell import (
    MemCell as DocMemCell,
    RawData as DocRawData,
    DataTypeEnum,
)
from memory_layer.memory_extractor.profile_memory_extractor import ProjectInfo
from biz_layer.conversation_data_repo import ConversationDataRepository
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from common_utils.datetime_utils import (
    get_now_with_timezone,
    to_timezone,
    to_iso_format,
    from_iso_format,
    from_timestamp,
)
from core.observation.logger import get_logger
from infra_layer.adapters.out.persistence.document.memory.semantic_memory_record import (
    SemanticMemoryRecord,
)
from infra_layer.adapters.out.persistence.document.memory.event_log_record import (
    EventLogRecord,
)
from memory_layer.types import RawDataType
logger = get_logger(__name__)
import uuid
# ==================== 时间处理函数 ====================


def _normalize_datetime_for_storage(
    timestamp: Any, current_time: Optional[datetime] = None
) -> datetime:
    """
    将各种时间格式统一转换为本地时区时间datetime对象（带时区信息，用于数据库存储）

    使用场景：
    - 在保存数据到数据库前，确保时间字段格式统一
    - 处理来自不同来源的时间数据（字符串、时间戳、datetime对象）
    - 避免时区不一致导致的数据错误

    Args:
        timestamp: 输入的时间数据，支持datetime、str、int、float类型
        current_time: 备用时间，当转换失败时使用

    Returns:
        datetime: 带时区信息的datetime对象
    """
    try:
        if not timestamp:
            return None
        if isinstance(timestamp, datetime):
            # 如果是datetime对象，使用to_timezone转换为本地时区
            return to_timezone(timestamp)
        elif isinstance(timestamp, str):
            # 字符串格式，使用from_iso_format解析
            return from_iso_format(timestamp)
        elif isinstance(timestamp, (int, float)):
            # 数字时间戳，使用from_timestamp转换（毫秒转秒）
            return from_timestamp(timestamp / 1000)
        else:
            # 其他类型，返回当前本地时间
            return current_time if current_time else get_now_with_timezone()
    except Exception as e:
        logger.debug(f"时间格式化失败: {timestamp}, 错误: {e}")
        return current_time if current_time else get_now_with_timezone()


def _convert_timestamp_to_time(
    timestamp: Any, current_time: Optional[datetime] = None
) -> str:
    """
    将时间戳转换为ISO格式时间字符串，支持多种输入格式

    使用场景：
    - 从数据库读取的时间数据转换为标准ISO格式
    - 业务层对象时间字段的格式化输出
    - API响应中时间字段的统一格式化

    Args:
        timestamp: 输入的时间数据，支持datetime、str、int、float类型
        current_time: 备用时间，当转换失败时使用

    Returns:
        str: ISO格式的时间字符串
    """
    try:
        if not timestamp:
            return None
        if isinstance(timestamp, datetime):
            # 如果是datetime对象，使用to_iso_format转换
            return to_iso_format(timestamp)
        elif isinstance(timestamp, (int, float)):
            # 如果是数字时间戳（毫秒），先转换为datetime再转ISO
            dt = from_timestamp(timestamp / 1000)
            return to_iso_format(dt)
        elif isinstance(timestamp, str):
            # 如果是字符串，尝试解析为datetime再转ISO
            try:
                dt = from_iso_format(timestamp)
                return to_iso_format(dt)
            except:
                # 如果解析失败，直接返回字符串
                return timestamp
        else:
            # 其他类型，返回当前时间的ISO格式
            return to_iso_format(
                current_time if current_time else get_now_with_timezone()
            )
    except Exception as e:
        logger.debug(f"时间戳转换失败: {timestamp}, 错误: {e}")
        return to_iso_format(current_time if current_time else get_now_with_timezone())


# ==================== 数据转换函数 ====================


def _convert_importance_evidence_to_document(
    importance_evidence_list: List[ImportanceEvidence],
) -> List[Dict[str, Any]]:
    """
    将ImportanceEvidence转换为数据库文档格式
    """
    if not importance_evidence_list:
        return None
    return [
        {
            "user_id": importance_evidence.user_id,
            "group_id": importance_evidence.group_id,
            "speak_count": importance_evidence.speak_count,
            "refer_count": importance_evidence.refer_count,
            "conversation_count": importance_evidence.conversation_count,
        }
        for importance_evidence in importance_evidence_list
    ]


def _convert_document_to_importance_evidence(
    importance_evidence_list: List[Dict[str, Any]]
) -> List[ImportanceEvidence]:
    """
    将数据库文档格式转换为ImportanceEvidence
    """
    if not importance_evidence_list:
        return None
    return [
        ImportanceEvidence(
            user_id=importance_evidence["user_id"],
            group_id=importance_evidence["group_id"],
            speak_count=importance_evidence["speak_count"],
            refer_count=importance_evidence["refer_count"],
            conversation_count=importance_evidence["conversation_count"],
        )
        for importance_evidence in importance_evidence_list
    ]


def _convert_group_importance_evidence_to_document(
    group_importance_evidence: GroupImportanceEvidence,
) -> Dict[str, Any]:
    """
    将GroupImportanceEvidence转换为数据库文档格式
    """
    if not group_importance_evidence:
        return None
    return {
        "group_id": group_importance_evidence.group_id,
        "is_important": group_importance_evidence.is_important,
        "evidence_list": _convert_importance_evidence_to_document(
            group_importance_evidence.evidence_list
        ),
    }


def _convert_document_to_group_importance_evidence(
    group_importance_evidence: Dict[str, Any]
) -> GroupImportanceEvidence:
    """
    将数据库文档格式转换为GroupImportanceEvidence
    """
    if not group_importance_evidence:
        return None
    return GroupImportanceEvidence(
        group_id=group_importance_evidence["group_id"],
        is_important=group_importance_evidence["is_important"],
        evidence_list=_convert_document_to_importance_evidence(
            group_importance_evidence["evidence_list"]
        ),
    )


def _convert_episode_memory_to_doc(
    episode_memory: Any, current_time: Optional[datetime] = None
) -> EpisodicMemory:
    """
    将EpisodeMemory业务对象转换为EpisodicMemory数据库文档格式

    使用场景：
    - 保存情景记忆到EpisodicMemoryRawRepository之前的格式转换
    - 确保业务层Memory对象符合数据库文档模型的字段要求
    - 处理时间戳格式和扩展字段的映射

    Args:
        episode_memory: 业务层的EpisodeMemory对象
        current_time: 当前时间，用于时间戳解析失败时的备用值

    Returns:
        EpisodicMemory: 数据库文档格式的情景记忆对象
    """
    from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
        EpisodicMemory,
    )
    from agentic_layer.vectorize_service import get_vectorize_service

    # 解析时间戳为datetime对象
    if current_time is None:
        current_time = get_now_with_timezone()

    # 默认使用 current_time
    timestamp_dt = current_time

    if hasattr(episode_memory, 'timestamp') and episode_memory.timestamp:
        try:
            if isinstance(episode_memory.timestamp, datetime):
                timestamp_dt = episode_memory.timestamp
            elif isinstance(episode_memory.timestamp, str):
                timestamp_dt = from_iso_format(episode_memory.timestamp)
            elif isinstance(episode_memory.timestamp, (int, float)):
                # 如果是数字时间戳（毫秒），转换为datetime
                timestamp_dt = from_timestamp(episode_memory.timestamp / 1000)
        except Exception as e:
            logger.debug(f"时间戳转换失败，使用当前时间: {e}")
            timestamp_dt = current_time

    return EpisodicMemory(
        user_id=episode_memory.user_id,  # 保持 None 或实际值，不转换为空字符串
        user_name=episode_memory.user_name or '',
        group_id=episode_memory.group_id,
        group_name=episode_memory.group_name,
        timestamp=timestamp_dt,
        participants=episode_memory.participants,
        summary=episode_memory.summary or "",
        subject=episode_memory.subject or "",
        episode=(
            episode_memory.episode
            if hasattr(episode_memory, 'episode')
            else episode_memory.summary or ""
        ),
        type=str(episode_memory.type.value) if episode_memory.type else "",
        keywords=getattr(episode_memory, 'keywords', None),
        linked_entities=getattr(episode_memory, 'linked_entities', None),
        memcell_event_id_list=getattr(episode_memory, 'memcell_event_id_list', None),
        vector_model=getattr(episode_memory, 'vector_model', None),
        extend={
            "memory_type": episode_memory.memory_type.value,
            "ori_event_id": getattr(episode_memory, 'ori_event_id', None),
            "tags": getattr(episode_memory, 'tags', None),
        },
    )


def _convert_semantic_memory_to_doc(
    semantic_memory: Any,
    parent_doc: EpisodicMemory,
    current_time: Optional[datetime] = None,
) -> SemanticMemoryRecord:
    """
    将SemanticMemoryItem业务对象转换为统一语义记忆文档格式

    Args:
        semantic_memory: 业务层的SemanticMemoryItem对象
        parent_doc: 父情景记忆文档
        current_time: 当前时间

    Returns:
        SemanticMemoryRecord: 数据库文档格式的语义记忆对象
    """
    

    if current_time is None:
        current_time = get_now_with_timezone()

    return SemanticMemoryRecord(
        user_id=getattr(semantic_memory, "user_id", None),
        user_name=getattr(
            semantic_memory, "user_name", getattr(parent_doc, "user_name", None)
        ),
        content=semantic_memory.content,
        parent_episode_id=str(parent_doc.event_id),
        start_time=semantic_memory.start_time,
        end_time=semantic_memory.end_time,
        duration_days=semantic_memory.duration_days,
        group_id=semantic_memory.group_id,
        group_name=getattr(
            semantic_memory, "group_name", getattr(parent_doc, "group_name", None)
        ),
        participants=parent_doc.participants,
        vector=semantic_memory.embedding,
        vector_model=getattr(semantic_memory, 'vector_model', None),
        evidence=semantic_memory.evidence,
        extend={},
    )


def _convert_event_log_to_docs(
    event_log: Any, parent_doc: EpisodicMemory, current_time: Optional[datetime] = None
) -> List["EventLogRecord"]:
    """
    将EventLog业务对象转换为通用事件日志文档列表

    Args:
        event_log: 业务层的EventLog对象
        parent_doc: 父情景记忆文档
        current_time: 当前时间

    Returns:
        List[EventLogRecord]: 数据库文档格式的事件日志对象列表
    """
    if current_time is None:
        current_time = get_now_with_timezone()

    docs: List[EventLogRecord] = []
    if not event_log.atomic_fact or not event_log.fact_embeddings:
        return docs

    for i, fact in enumerate(event_log.atomic_fact):
        if i >= len(event_log.fact_embeddings):
            break

        vector = event_log.fact_embeddings[i]
        if hasattr(vector, 'tolist'):
            vector = vector.tolist()

        doc = EventLogRecord(
            user_id=event_log.user_id,
            user_name=event_log.user_name or '',
            atomic_fact=fact,
            parent_episode_id=str(parent_doc.event_id),
            timestamp=parent_doc.timestamp or current_time,
            group_id=getattr(event_log, "group_id", parent_doc.group_id),
            group_name=getattr(
                event_log, "group_name", getattr(parent_doc, "group_name", None)
            ),
            participants=parent_doc.participants,
            vector=vector,
            vector_model=getattr(event_log, 'vector_model', None),
            event_type=parent_doc.type or RawDataType.CONVERSATION.value,
            extend={},
        )
        docs.append(doc)

    return docs


def _convert_group_profile_data_to_profile_format(
    group_profile_memory: GroupProfileMemory,
) -> Dict[str, Any]:
    """
    将GroupProfileMemory的数据格式转换为GroupProfile期望的格式

    使用场景：
    - 保存GroupProfileMemory到GroupProfileRawRepository之前的格式转换
    - 处理不同数据结构之间的字段映射和类型转换
    - 确保时间戳格式的统一性

    Args:
        group_profile_memory: 业务层的GroupProfileMemory对象

    Returns:
        dict: 包含转换后数据的字典，键为GroupProfile字段名
    """
    from infra_layer.adapters.out.persistence.document.memory.group_profile import (
        TopicInfo as DocTopicInfo,
    )

    # 处理 topics 转换：从 business TopicInfo 转为 document TopicInfo
    # 修复：初始化为空列表而不是 None，避免空列表被保存为 None
    topics = []
    if (
        hasattr(group_profile_memory, 'topics')
        and group_profile_memory.topics is not None
    ):
        for topic in group_profile_memory.topics:
            if hasattr(topic, 'name'):  # 业务层 TopicInfo 对象
                # 确保 last_active_at 是 datetime 对象
                last_active_at = topic.last_active_at
                if isinstance(last_active_at, str):
                    try:
                        from common_utils.datetime_utils import from_iso_format

                        last_active_at = from_iso_format(last_active_at)
                    except Exception:
                        from common_utils.datetime_utils import get_now_with_timezone

                        last_active_at = get_now_with_timezone()
                elif not isinstance(last_active_at, datetime):
                    from common_utils.datetime_utils import get_now_with_timezone

                    last_active_at = get_now_with_timezone()

                doc_topic = DocTopicInfo(
                    name=topic.name,
                    summary=topic.summary,
                    status=topic.status,
                    last_active_at=last_active_at,
                    id=getattr(topic, 'id', None),
                    update_type=getattr(topic, 'update_type', None),
                    old_topic_id=getattr(topic, 'old_topic_id', None),
                    evidences=getattr(topic, 'evidences', []),
                    confidence=getattr(topic, 'confidence', None),
                )
                topics.append(doc_topic)
            elif isinstance(topic, dict):
                # 已经是字典格式，直接创建 DocTopicInfo
                topics.append(DocTopicInfo(**topic))

    # 处理 roles 转换：从 Dict 转换为 RoleAssignment 对象
    from infra_layer.adapters.out.persistence.document.memory.group_profile import (
        RoleAssignment,
    )

    # 修复：初始化为空字典而不是 None，避免空字典被保存为 None
    roles = {}
    if (
        hasattr(group_profile_memory, 'roles')
        and group_profile_memory.roles is not None
    ):
        for role_name, assignments in group_profile_memory.roles.items():
            role_assignments = []
            for assignment in assignments:
                if isinstance(assignment, dict):
                    # 从字典创建 RoleAssignment 对象
                    role_assignment = RoleAssignment(
                        user_id=assignment.get('user_id', ''),
                        user_name=assignment.get('user_name', ''),
                        confidence=assignment.get('confidence'),
                        evidences=assignment.get('evidences', []),
                    )
                    role_assignments.append(role_assignment)
                else:
                    # 如果已经是对象，直接添加
                    role_assignments.append(assignment)
            if role_assignments:
                roles[role_name] = role_assignments

    # 处理时间戳：确保是整数毫秒时间戳
    # TODO: 重构专项：timestamp 应保持为datetime 而不是转为int
    timestamp = None
    if hasattr(group_profile_memory, 'timestamp') and group_profile_memory.timestamp:
        if isinstance(group_profile_memory.timestamp, datetime):
            timestamp = int(group_profile_memory.timestamp.timestamp() * 1000)
        elif isinstance(group_profile_memory.timestamp, (int, float)):
            timestamp = int(group_profile_memory.timestamp)
        elif isinstance(group_profile_memory.timestamp, str):
            try:
                from common_utils.datetime_utils import from_iso_format

                dt = from_iso_format(group_profile_memory.timestamp)
                timestamp = int(dt.timestamp() * 1000)
            except Exception:
                from common_utils.datetime_utils import get_now_with_timezone

                timestamp = int(get_now_with_timezone().timestamp() * 1000)
    else:
        # 使用当前时间作为默认值
        from common_utils.datetime_utils import get_now_with_timezone

        timestamp = int(get_now_with_timezone().timestamp() * 1000)

    # 提取其他字段
    group_name = getattr(group_profile_memory, 'group_name', None)
    subject = getattr(group_profile_memory, 'theme', None) or getattr(
        group_profile_memory, 'subject', None
    )
    summary = getattr(group_profile_memory, 'summary', None)
    extend = getattr(group_profile_memory, 'extend', None)

    return {
        "group_name": group_name,
        "topics": topics,
        "roles": roles,
        "timestamp": timestamp,
        "subject": subject,
        "summary": summary,
        "extend": extend,
    }


def _convert_document_to_project_info(project_info: Dict[str, str]) -> ProjectInfo:
    """
    将数据库文档格式转换为ProjectInfo
    """
    if not project_info:
        return None

    def _process_field_with_evidences(value):
        """处理包含 evidences 的字段，保持 List[Dict[str, Any]] 格式"""
        if value is None:
            return None

        # 如果已经是包含 value/evidences 的字典列表，直接返回
        if isinstance(value, list):
            if (
                value
                and isinstance(value[0], dict)
                and ("value" in value[0] or "evidences" in value[0])
            ):
                return value
            # 如果是普通字符串列表或其他类型列表，转换为 value/evidences 格式
            return [{"value": str(item), "evidences": []} for item in value if item]

        # 如果是字符串，尝试解析
        if isinstance(value, str):
            if not value.strip():
                return None
            try:
                import ast

                parsed_value = ast.literal_eval(value)
                if isinstance(parsed_value, list):
                    # 检查是否已经是规范格式
                    if (
                        parsed_value
                        and isinstance(parsed_value[0], dict)
                        and (
                            "value" in parsed_value[0] or "evidences" in parsed_value[0]
                        )
                    ):
                        return parsed_value
                    # 否则转换为规范格式
                    return [
                        {"value": str(item), "evidences": []}
                        for item in parsed_value
                        if item
                    ]
            except (ValueError, SyntaxError):
                # 解析失败，按逗号分割
                items = [item.strip() for item in value.split(',') if item.strip()]
                return [{"value": item, "evidences": []} for item in items]

        return None

    return ProjectInfo(
        project_id=project_info.get("project_id", ""),
        project_name=project_info.get("project_name", ""),
        entry_date=project_info.get("entry_date", ""),
        user_objective=_process_field_with_evidences(
            project_info.get("user_objective")
        ),
        contributions=_process_field_with_evidences(project_info.get("contributions")),
        subtasks=_process_field_with_evidences(project_info.get("subtasks")),
        user_concerns=_process_field_with_evidences(project_info.get("user_concerns")),
    )


def _convert_projects_participated_list(
    projects_participated: Optional[List[Dict[str, str]]]
) -> List[ProjectInfo]:
    """
    将数据库中的projects_participated (List[Dict[str, str]]) 转换为 List[ProjectInfo]
    """
    if not projects_participated:
        return []

    result = []
    for project_dict in projects_participated:
        if isinstance(project_dict, dict):
            project_info = _convert_document_to_project_info(project_dict)
            if project_info:
                result.append(project_info)

    return result


def _convert_profile_data_to_core_format(profile_memory: ProfileMemory) -> CoreMemory:
    """
    将ProfileMemory的数据格式转换为CoreMemory期望的格式

    使用场景：
    - 保存用户档案记忆到CoreMemoryRawRepository之前的数据格式转换
    - 处理技能、性格、项目等字段的数据类型转换
    - 确保数据符合CoreMemory文档模型的字段定义

    Args:
        profile_memory: 业务层的ProfileMemory对象

    Returns:
        dict: 包含转换后数据的字典，键为CoreMemory字段名
    """

    # 转换 hard_skills: 直接使用 profile_memory.hard_skills
    hard_skills = None
    if hasattr(profile_memory, 'hard_skills') and profile_memory.hard_skills:
        hard_skills = profile_memory.hard_skills

    # 转换 soft_skills: 直接使用 profile_memory.soft_skills
    soft_skills = None
    if hasattr(profile_memory, 'soft_skills') and profile_memory.soft_skills:
        soft_skills = profile_memory.soft_skills

    output_reasoning = getattr(profile_memory, 'output_reasoning', None)

    motivation_system = None
    if (
        hasattr(profile_memory, 'motivation_system')
        and profile_memory.motivation_system
    ):
        motivation_system = profile_memory.motivation_system

    fear_system = None
    if hasattr(profile_memory, 'fear_system') and profile_memory.fear_system:
        fear_system = profile_memory.fear_system

    value_system = None
    if hasattr(profile_memory, 'value_system') and profile_memory.value_system:
        value_system = profile_memory.value_system

    humor_use = None
    if hasattr(profile_memory, 'humor_use') and profile_memory.humor_use:
        humor_use = profile_memory.humor_use

    colloquialism = None
    if hasattr(profile_memory, 'colloquialism') and profile_memory.colloquialism:
        colloquialism = profile_memory.colloquialism

    # 转换 way_of_decision_making: 直接使用原始数据（已包含evidences）
    way_of_decision_making = None
    if (
        hasattr(profile_memory, 'way_of_decision_making')
        and profile_memory.way_of_decision_making
    ):
        way_of_decision_making = profile_memory.way_of_decision_making

    # 转换 personality: 直接使用原始数据（已包含evidences）
    personality = None
    if hasattr(profile_memory, 'personality') and profile_memory.personality:
        personality = profile_memory.personality

    # 转换 projects_participated: List[ProjectInfo] -> List[Dict[str, Any]]
    # 注意：ProjectInfo的各字段现在包含evidence-embedded数据，直接使用原始格式
    projects_participated = None
    if (
        hasattr(profile_memory, 'projects_participated')
        and profile_memory.projects_participated
    ):
        if isinstance(profile_memory.projects_participated, list):
            projects_participated = []
            for project in profile_memory.projects_participated:
                if hasattr(project, 'project_id'):  # ProjectInfo object
                    # 直接使用原始数据，保留evidence-embedded格式
                    user_objective = getattr(project, 'user_objective', None)
                    contributions = getattr(project, 'contributions', None)
                    subtasks = getattr(project, 'subtasks', None)
                    user_concerns = getattr(project, 'user_concerns', None)

                    project_dict = {
                        "project_id": (
                            str(project.project_id) if project.project_id else ""
                        ),
                        "project_name": (
                            str(project.project_name) if project.project_name else ""
                        ),
                        "entry_date": (
                            str(project.entry_date) if project.entry_date else ""
                        ),
                        "user_objective": user_objective,
                        "contributions": contributions,
                        "subtasks": subtasks,
                        "user_concerns": user_concerns,
                    }
                    projects_participated.append(project_dict)
                elif isinstance(project, dict):
                    projects_participated.append(project)  # 已经是正确格式

    # 提取新增字段
    user_goal = getattr(profile_memory, 'user_goal', None)
    work_responsibility = getattr(profile_memory, 'work_responsibility', None)
    working_habit_preference = getattr(profile_memory, 'working_habit_preference', None)
    interests = getattr(profile_memory, 'interests', None)
    tendency = getattr(profile_memory, 'tendency', None)
    user_name = getattr(profile_memory, 'user_name', None)
    group_importance_evidence = getattr(
        profile_memory, 'group_importance_evidence', None
    )

    return {
        "user_name": user_name,
        "output_reasoning": output_reasoning,
        "hard_skills": hard_skills,
        "soft_skills": soft_skills,
        "way_of_decision_making": way_of_decision_making,
        "personality": personality,
        "projects_participated": projects_participated,
        "user_goal": user_goal,
        "work_responsibility": work_responsibility,
        "working_habit_preference": working_habit_preference,
        "interests": interests,
        "tendency": tendency,
        "motivation_system": motivation_system,
        "fear_system": fear_system,
        "value_system": value_system,
        "humor_use": humor_use,
        "colloquialism": colloquialism,
        "group_importance_evidence": _convert_group_importance_evidence_to_document(
            group_importance_evidence
        ),
    }


def _convert_memcell_to_document(
    memcell: MemCell, current_time: Optional[datetime] = None
) -> DocMemCell:
    """
    将业务层MemCell转换为文档模型MemCell

    使用场景：
    - 保存MemCell到MemCellRawRepository之前的格式转换
    - 处理原始数据的嵌套结构转换，避免无限递归问题
    - 统一时间戳格式和数据类型枚举的转换

    Args:
        memcell: 业务层的MemCell对象
        current_time: 当前时间，用于时间戳转换失败时的备用值

    Returns:
        DocMemCell: 数据库文档格式的MemCell对象

    Raises:
        Exception: 当转换过程中发生错误时抛出异常
    """
    try:
        # 临时解决方案：禁用原始数据转换以避免无限递归
        # 问题：BaseModel对象的嵌套验证导致无限递归，即使最简单的结构也有问题
        # TODO: 需要找到更好的解决方案来正确转换original_data
        doc_original_data = []
        if memcell.type == RawDataType.CONVERSATION:
            for raw_data_dict in memcell.original_data:
                # 实际的数据结构是: {'speaker_id': 'user_1', 'speaker_name': 'Alice', 'content': '消息内容', 'timestamp': '...'}
                # 这里的 content 是直接的消息字符串，不是嵌套字典
                # 辅助函数：将各种类型转换为字符串
                def to_string(value):
                    if value is None:
                        return ''
                    elif isinstance(value, str):
                        return value
                    elif isinstance(value, datetime):
                        return value.isoformat()
                    elif isinstance(value, list):
                        return ','.join(str(item) for item in value) if value else ''
                    else:
                        return str(value)

                message = {
                    "content": raw_data_dict.get('content')
                    or '',  # Handle None content explicitly
                    "extend": {
                        "speaker_id": to_string(raw_data_dict.get('speaker_id', '')),
                        "speaker_name": to_string(
                            raw_data_dict.get('speaker_name', '')
                        ),
                        "timestamp": to_string(
                            _convert_timestamp_to_time(
                                raw_data_dict.get('timestamp', '')
                            )
                        ),
                        "message_id": to_string(raw_data_dict.get('data_id', '')),
                        "receiverId": to_string(raw_data_dict.get('receiverId', '')),
                        "roomId": to_string(raw_data_dict.get('roomId', '')),
                        "userIdList": to_string(raw_data_dict.get('userIdList', [])),
                        "createBy": to_string(raw_data_dict.get('createBy', '')),
                        "updateTime": to_string(raw_data_dict.get('updateTime', '')),
                        "msgType": to_string(raw_data_dict.get('msgType', '')),
                        "referList": to_string(raw_data_dict.get('referList', [])),
                        "orgId": to_string(raw_data_dict.get('orgId', '')),
                        "readStatus": to_string(raw_data_dict.get('readStatus', '')),
                        "notifyType": to_string(raw_data_dict.get('notifyType', '')),
                        "isReplySuggest": to_string(
                            raw_data_dict.get('isReplySuggest', '')
                        ),
                        "readUpdateTime": to_string(
                            raw_data_dict.get('readUpdateTime', '')
                        ),
                    },
                }

                # 创建文档模型的 RawData
                doc_raw_data = DocRawData(
                    data_type=DataTypeEnum.CONVERSATION,  # 默认设为对话类型
                    messages=[message],  # 消息列表
                    # meta=raw_data_dict.get('metadata', {})  # 元数据
                )
                doc_original_data.append(doc_raw_data)

        # 转换时间戳为timezone-aware的datetime，避免无限递归
        if current_time is None:
            current_time = get_now_with_timezone()
        timestamp_dt = current_time
        if memcell.timestamp:
            try:
                # 检查 timestamp 类型并处理
                # TODO: 重构专项：timestamp 应保持为datetime 不该做判断
                if isinstance(memcell.timestamp, datetime):
                    # 如果已经是 datetime 对象，直接使用
                    timestamp_dt = _normalize_datetime_for_storage(memcell.timestamp)
                else:
                    # 如果是数值时间戳，需要转换（假设是秒级时间戳）
                    timestamp_dt = _normalize_datetime_for_storage(
                        memcell.timestamp * 1000
                    )
            except (ValueError, TypeError) as e:
                logger.debug(f"时间戳转换失败，使用当前时间: {e}")

        logger.debug(f"MemCell保存时间戳: {timestamp_dt}")

        # 转换数据类型枚举
        doc_type = None
        if memcell.type:
            try:
                # 将RawDataType转换为DataTypeEnum
                if memcell.type == RawDataType.CONVERSATION:
                    doc_type = DataTypeEnum.CONVERSATION
            except Exception as e:
                logger.warning(f"数据类型转换失败: {e}")

        # MemCell 本身就是群组记忆，user_id 始终为 None
        primary_user_id = None

        # 准备扩展字段 - 根据MemCell的具体类型提取扩展属性
        email_fields = {}
        linkdoc_fields = {}

        # 准备 semantic_memories（转为字典列表）
        semantic_memories_list = None
        if hasattr(memcell, 'semantic_memories') and memcell.semantic_memories:
            semantic_memories_list = [
                (
                    sm.to_dict()
                    if hasattr(sm, 'to_dict')
                    else (sm if isinstance(sm, dict) else None)
                )
                for sm in memcell.semantic_memories
            ]
            semantic_memories_list = [
                sm for sm in semantic_memories_list if sm is not None
            ]

        # 准备 event_log（转为字典）
        event_log_dict = None
        if hasattr(memcell, 'event_log') and memcell.event_log:
            if hasattr(memcell.event_log, 'to_dict'):
                event_log_dict = memcell.event_log.to_dict()
            elif isinstance(memcell.event_log, dict):
                event_log_dict = memcell.event_log

        # 准备 extend 字段（包含 embedding 等扩展信息）
        extend_dict = {}
        if hasattr(memcell, 'extend') and memcell.extend:
            extend_dict = memcell.extend if isinstance(memcell.extend, dict) else {}

        # 添加 embedding 到 extend（如果有）
        if hasattr(memcell, 'embedding') and memcell.embedding:
            extend_dict['embedding'] = memcell.embedding

        # 创建文档模型 - 直接传入timezone-aware的datetime对象而不是字符串
        # 这样可以避免基类的datetime验证器触发无限递归
        doc_memcell = DocMemCell(
            event_id=memcell.event_id,
            user_id=primary_user_id,
            timestamp=timestamp_dt,  # 直接传入timezone-aware的datetime
            summary=memcell.summary,
            group_id=memcell.group_id,
            group_name=memcell.group_name,
            original_data=doc_original_data,
            participants=memcell.participants,
            type=doc_type,
            subject=memcell.subject,
            keywords=memcell.keywords,
            linked_entities=memcell.linked_entities,
            episode=memcell.episode,
            semantic_memories=semantic_memories_list,  # ✅ 添加语义记忆
            event_log=event_log_dict,  # ✅ 添加事件日志
            extend=(
                extend_dict if extend_dict else None
            ),  # ✅ 添加 extend（包含 embedding）
            # EmailMemCell 扩展字段
            clips=email_fields.get("clips") or linkdoc_fields.get("clips"),
            email_address=email_fields.get("email_address"),
            thread_id=email_fields.get("thread_id"),
            is_read=email_fields.get("is_read"),
            importance=email_fields.get("importance"),
            body_type=email_fields.get("body_type"),
            email_type=email_fields.get("email_type"),
            # LinkDocMemCell 扩展字段
            file_name=linkdoc_fields.get("file_name"),
            file_type=linkdoc_fields.get("file_type"),
            source_type=linkdoc_fields.get("source_type"),
            file_id=linkdoc_fields.get("file_id"),
            third_party_user_id=linkdoc_fields.get("third_party_user_id"),
            download_url=linkdoc_fields.get("download_url"),
            size=linkdoc_fields.get("size"),
            parent_ids=linkdoc_fields.get("parent_ids"),
        )

        return doc_memcell

    except Exception as e:
        logger.error(f"MemCell转换失败: {e}")
        import traceback

        traceback.print_exc()
        raise


# ==================== 数据库操作函数 ====================
from core.observation.tracing.decorators import trace_logger


async def _save_memcell_to_database(
    memcell: MemCell, current_time: datetime
) -> MemCell:
    """
    将MemCell保存到数据库

    使用场景：
    - memorize流程中成功提取MemCell后的持久化操作
    - 确保对话片段的记忆单元得到保存
    - 为后续的记忆提取提供数据基础

    Args:
        memcell: 业务层的MemCell对象

    Note:
        - 函数内部会自动进行格式转换
        - 转换失败时会跳过保存并记录日志
        - 保存失败时会打印错误信息但不中断流程
    """
    try:
        # 初始化MemCell Repository
        memcell_repo = get_bean_by_type(MemCellRawRepository)
        # 将业务层MemCell转换为文档模型
        doc_memcell = _convert_memcell_to_document(memcell, current_time)

        # 检查转换是否成功
        if doc_memcell is None:
            logger.warning(f"MemCell转换跳过，无法保存: {memcell.event_id}")
            return

        # 保存到数据库
        result = await memcell_repo.append_memcell(doc_memcell)
        if result:
            memcell.event_id = str(result.event_id)
            logger.info(f"[mem_db_operations] MemCell保存成功: {memcell.event_id}")
        else:
            logger.info(f"[mem_db_operations] MemCell保存失败: {memcell.event_id}")

    except Exception as e:
        logger.error(f"MemCell保存失败: {e}")
        import traceback

        traceback.print_exc()
    return memcell


async def _save_group_profile_memory(
    group_profile_memory: GroupProfileMemory,
    group_profile_raw_repo: GroupProfileRawRepository,
    version: Optional[str] = None,
) -> None:
    """
    将GroupProfileMemory保存到GroupProfileRawRepository
    """
    try:
        # 转换数据格式
        converted_data = _convert_group_profile_data_to_profile_format(
            group_profile_memory
        )

        # 全覆盖保存GroupProfile（创建或更新）
        logger.debug(f"保存GroupProfile: {group_profile_memory.group_id}")

        # 准备保存数据（分离timestamp，因为upsert_by_group_id需要单独传递）
        save_data = {}
        timestamp = None

        # 添加非空字段，但分离timestamp
        for k, v in converted_data.items():
            if v is not None:
                if k == "timestamp":
                    timestamp = v
                else:
                    save_data[k] = v

        save_data["version"] = version

        # 使用upsert_by_group_id方法（如果存在则更新，不存在则创建）
        await group_profile_raw_repo.upsert_by_group_id(
            group_profile_memory.group_id, save_data, timestamp=timestamp
        )

    except Exception as e:
        logger.error(f"GroupProfileMemory保存失败: {e}")
        import traceback

        traceback.print_exc()


async def _save_profile_memory_to_core(
    profile_memory: ProfileMemory,
    core_memory_repo: CoreMemoryRawRepository,
    version: Optional[str] = None,
) -> None:
    """
    将ProfileMemory保存到CoreMemoryRawRepository

    使用场景：
    - memorize流程中提取的用户档案记忆需要持久化时
    - 全覆盖更新用户的核心记忆信息
    - 处理技能、性格、项目等用户特征信息的存储

    Args:
        profile_memory: 业务层的ProfileMemory对象
        core_memory_repo: CoreMemoryRawRepository实例

    Note:
        - 采用全覆盖策略，直接用新数据替换现有数据
        - 不进行数据合并，确保数据的一致性和准确性

    Raises:
        Exception: 当保存过程中发生错误时抛出异常
    """
    try:
        # 转换数据格式
        converted_data = _convert_profile_data_to_core_format(profile_memory)

        # 全覆盖保存CoreMemory（创建或更新）
        logger.debug(f"保存CoreMemory: {profile_memory.user_id}")

        # 准备保存数据（不包含user_id，因为upsert_by_user_id会自动处理）
        save_data = {"extend": getattr(profile_memory, 'extend', None)}
        # 添加非空字段
        for k, v in converted_data.items():
            if v is not None:
                save_data[k] = v

        save_data["version"] = version

        # 使用upsert_by_user_id方法（如果存在则更新，不存在则创建）
        await core_memory_repo.upsert_by_user_id(profile_memory.user_id, save_data)

    except Exception as e:
        logger.error(f"保存Profile Memory到CoreMemory失败: {e}")
        import traceback

        traceback.print_exc()
        raise


async def _save_profile_memory_to_group_user_profile_memory(
    profile_memory: ProfileMemory,
    group_user_profile_memory_repo: GroupUserProfileMemoryRawRepository,
    version: Optional[str] = None,
) -> None:
    """
    将ProfileMemory保存到CoreMemoryRawRepository

    使用场景：
    - memorize流程中提取的用户档案记忆需要持久化时
    - 全覆盖更新用户的核心记忆信息
    - 处理技能、性格、项目等用户特征信息的存储

    Args:
        profile_memory: 业务层的ProfileMemory对象
        core_memory_repo: CoreMemoryRawRepository实例

    Note:
        - 采用全覆盖策略，直接用新数据替换现有数据
        - 不进行数据合并，确保数据的一致性和准确性

    Raises:
        Exception: 当保存过程中发生错误时抛出异常
    """
    try:
        # 转换数据格式
        converted_data = _convert_profile_data_to_core_format(profile_memory)

        # 全覆盖保存CoreMemory（创建或更新）
        logger.debug(f"保存CoreMemory: {profile_memory.user_id}")

        # 准备保存数据（不包含user_id，因为upsert_by_user_id会自动处理）
        save_data = {"extend": getattr(profile_memory, 'extend', None)}
        # 添加非空字段
        for k, v in converted_data.items():
            if v is not None:
                save_data[k] = v

        save_data["version"] = version

        # 使用upsert_by_user_id方法（如果存在则更新，不存在则创建）
        await group_user_profile_memory_repo.upsert_by_user_group(
            profile_memory.user_id, profile_memory.group_id, save_data
        )

    except Exception as e:
        logger.error(f"保存Profile Memory到CoreMemory失败: {e}")
        import traceback

        traceback.print_exc()
        raise


# ==================== 状态表操作函数 ====================


@dataclass
class ConversationStatus:
    """
    对话状态表数据结构

    用于跟踪对话的处理状态和时间边界，确保消息处理的连续性和一致性

    使用场景：
    - 管理对话的生命周期状态
    - 记录已处理和待处理消息的时间边界
    - 支持对话的暂停、继续和完成状态管理
    """

    group_id: str  # 群组ID
    old_msg_start_time: Optional[str]  # 已处理消息的开始时间
    new_msg_start_time: Optional[str]  # 新消息的开始时间
    last_memcell_time: Optional[str]  # 最后提取MemCell的时间
    created_at: str  # 创建时间
    updated_at: str  # 更新时间


async def _update_status_for_new_conversation(
    status_repo: ConversationStatusRawRepository,
    request: MemorizeRequest,
    earliest_time: str,
    current_time: datetime,
) -> bool:
    """
    为新对话创建状态记录

    使用场景：
    - 当检测到群组的第一次对话时调用
    - 初始化对话状态管理的基础数据
    - 设置消息处理的时间边界起点

    Args:
        status_repo: ConversationStatusRawRepository实例
        request: memorize请求对象
        earliest_time: 最早消息的时间戳
        current_time: 当前时间

    Returns:
        bool: 创建成功返回True，失败返回False
    """
    try:
        # 转换为数据库格式并保存
        # earliest_time
        update_data = {
            "old_msg_start_time": None,
            "new_msg_start_time": _normalize_datetime_for_storage(earliest_time),
            "last_memcell_time": None,
            "created_at": current_time,
            "updated_at": current_time,
        }

        logger.debug(f"创建新状态记录: {update_data}")
        result = await status_repo.upsert_by_group_id(request.group_id, update_data)

        if result:
            logger.info(f"新对话状态创建成功: {result.conversation_id}")
            return True
        else:
            logger.warning(f"新对话状态创建失败")
            return False

    except Exception as e:
        logger.error(f"创建新对话状态失败: {e}")
        return False


async def _update_status_for_continuing_conversation(
    status_repo: ConversationStatusRawRepository,
    request: MemorizeRequest,
    latest_time: str,
    current_time: datetime,
) -> bool:
    """
    为继续的对话更新状态记录（更新new_msg_start_time）

    使用场景：
    - 当MemCell提取判断为非边界时调用
    - 对话仍在继续，需要累积更多消息
    - 更新new_msg_start_time为最新消息时间，为下次处理做准备

    Args:
        status_repo: ConversationStatusRawRepository实例
        request: memorize请求对象
        latest_time: 最新消息的时间戳
        current_time: 当前时间

    Returns:
        bool: 更新成功返回True，失败返回False
    """
    try:
        # 先获取现有状态
        existing_status = await status_repo.get_by_group_id(request.group_id)
        if not existing_status:
            logger.info(
                f"未找到现有状态，创建新的状态记录: group_id={request.group_id}"
            )
            # 创建新状态记录
            latest_dt = _normalize_datetime_for_storage(latest_time)
            update_data = {
                "old_msg_start_time": None,
                "new_msg_start_time": latest_dt + timedelta(milliseconds=1),
                "last_memcell_time": None,
                "created_at": _normalize_datetime_for_storage(current_time),
                "updated_at": _normalize_datetime_for_storage(current_time),
            }
            result = await status_repo.upsert_by_group_id(request.group_id, update_data)
            if result:
                logger.info(f"创建新状态成功: group_id={request.group_id}")
                return True
            else:
                logger.warning(f"创建新状态失败: group_id={request.group_id}")
                return False

        # 更新new_msg_start_time为最新消息时间+1毫秒
        latest_dt = _normalize_datetime_for_storage(latest_time)
        new_msg_start_time = latest_dt

        update_data = {
            "old_msg_start_time": (
                _normalize_datetime_for_storage(existing_status.old_msg_start_time)
                if existing_status.old_msg_start_time
                else None
            ),
            "new_msg_start_time": new_msg_start_time + timedelta(milliseconds=1),
            "last_memcell_time": (
                _normalize_datetime_for_storage(existing_status.last_memcell_time)
                if existing_status.last_memcell_time
                else None
            ),
            "created_at": _normalize_datetime_for_storage(existing_status.created_at),
            "updated_at": current_time,
        }

        logger.debug(f"对话延续，更新new_msg_start_time")
        result = await status_repo.upsert_by_group_id(request.group_id, update_data)

        if result:
            logger.info(f"对话延续状态更新成功")
            return True
        else:
            logger.warning(f"对话延续状态更新失败")
            return False

    except Exception as e:
        logger.error(f"对话延续状态更新失败: {e}")
        return False


async def _update_status_after_memcell_extraction(
    status_repo: ConversationStatusRawRepository,
    request: MemorizeRequest,
    memcell_time: str,
    current_time: datetime,
) -> bool:
    """
    MemCell提取后更新状态表（更新old_msg_start_time和new_msg_start_time）

    使用场景：
    - 当成功提取MemCell并完成记忆提取后调用
    - 更新已处理消息的时间边界，避免重复处理
    - 重置new_msg_start_time为当前时间，准备接收新消息

    Args:
        status_repo: ConversationStatusRawRepository实例
        request: memorize请求对象
        memcell_time: MemCell的时间戳
        current_time: 当前时间

    Returns:
        bool: 更新成功返回True，失败返回False

    Note:
        - old_msg_start_time更新为最后一个历史消息时间+1ms
        - new_msg_start_time重置为当前时间
        - last_memcell_time记录最新的MemCell提取时间
    """
    try:
        # 获取最后一个历史数据的时间戳
        last_history_time = None
        if request.history_raw_data_list and request.history_raw_data_list[-1]:
            last_history_data = request.history_raw_data_list[-1]
            if hasattr(last_history_data, 'content') and isinstance(
                last_history_data.content, dict
            ):
                last_history_time = last_history_data.content.get('timestamp')
            elif hasattr(last_history_data, 'timestamp'):
                last_history_time = last_history_data.timestamp

        first_new_time = None
        if request.new_raw_data_list and request.new_raw_data_list[0]:
            first_new_data = request.new_raw_data_list[0]
            if hasattr(first_new_data, 'content') and isinstance(
                first_new_data.content, dict
            ):
                first_new_time = first_new_data.content.get('timestamp')
            elif hasattr(first_new_data, 'timestamp'):
                first_new_time = first_new_data.timestamp

        last_new_time = None
        if request.new_raw_data_list and request.new_raw_data_list[-1]:
            last_new_data = request.new_raw_data_list[-1]
            if hasattr(last_new_data, 'content') and isinstance(
                last_new_data.content, dict
            ):
                last_new_time = last_new_data.content.get('timestamp')
            elif hasattr(last_new_data, 'timestamp'):
                last_new_time = last_new_data.timestamp

        if last_new_time:
            last_new_dt = _normalize_datetime_for_storage(last_new_time)
            new_msg_start_time = last_new_dt + timedelta(milliseconds=1)
        else:
            new_msg_start_time = _normalize_datetime_for_storage(current_time)

        # 计算old_msg_start_time（最后一个历史时间戳+1毫秒）
        if first_new_time:
            first_new_dt = _normalize_datetime_for_storage(first_new_time)
            old_msg_start_time = first_new_dt
        elif last_history_time:
            last_history_dt = _normalize_datetime_for_storage(last_history_time)
            old_msg_start_time = last_history_dt + timedelta(milliseconds=1)
        else:
            # 如果没有历史数据，使用现有的current_time
            old_msg_start_time = _normalize_datetime_for_storage(current_time)

        update_data = {
            "old_msg_start_time": old_msg_start_time,
            "new_msg_start_time": new_msg_start_time,  # 当前时间
            "last_memcell_time": _normalize_datetime_for_storage(memcell_time),
            "updated_at": current_time,
        }

        # TODO : clear queue

        logger.debug(f"MemCell提取后更新状态表")
        result = await status_repo.upsert_by_group_id(request.group_id, update_data)

        if result:
            logger.info(f"MemCell提取后状态更新成功")
            return True
        else:
            logger.warning(f"MemCell提取后状态更新失败")
            return False

    except Exception as e:
        logger.error(f"MemCell提取后状态更新失败: {e}")
        return False


# ==================== 数据格式转换函数 ====================


def _convert_original_data_for_profile_extractor(doc_memcell) -> List[Dict[str, Any]]:
    """
    将文档层MemCell的original_data转换为ProfileMemoryExtractor期望的格式

    使用场景：
    - 在memorize_offline流程中，将文档层MemCell转换为业务层MemCell时使用
    - 确保ProfileMemoryExtractor能正确解析对话数据

    Args:
        doc_memcell: 文档层的MemCell对象

    Returns:
        List[Dict[str, Any]]: ProfileMemoryExtractor期望的数据格式，包含：
        - speaker_name: 说话人姓名
        - speaker_id: 说话人ID
        - content: 消息内容
        - referList: 引用列表
        - timestamp: 时间戳
    """
    original_data_list = []
    if hasattr(doc_memcell, 'original_data') and doc_memcell.original_data:
        for raw_data in doc_memcell.original_data:
            if hasattr(raw_data, 'messages') and raw_data.messages:
                for message in raw_data.messages:
                    if hasattr(message, 'content') and message.content:
                        # 构建ProfileMemoryExtractor期望的数据结构
                        extend = getattr(message, 'extend', {}) or {}
                        message_data = {
                            "speaker_name": extend.get(
                                'sender', extend.get('speaker_name', '')
                            ),
                            "speaker_id": extend.get(
                                'speaker_id', extend.get('user_id', '')
                            ),
                            "content": message.content,
                            "referList": extend.get('referList', []),
                            "timestamp": extend.get('timestamp', ''),
                        }
                        original_data_list.append(message_data)

    return original_data_list


def _convert_group_profile_raw_to_memory_format(
    doc_group_profile_raw,
) -> Dict[str, Any]:
    """
    将数据库中的GroupProfile原始数据转换为GroupProfileMemory所需的格式

    Args:
        doc_group_profile_raw: 数据库中的GroupProfile原始文档

    Returns:
        Dict[str, Any]: 转换后的数据字典
    """
    from memory_layer.memory_extractor.group_profile_memory_extractor import TopicInfo
    from datetime import datetime

    # 安全地转换topics字段
    topics = None
    if hasattr(doc_group_profile_raw, 'topics') and doc_group_profile_raw.topics:
        topics = []
        for topic_data in doc_group_profile_raw.topics:
            if isinstance(topic_data, dict):
                # 从字典创建TopicInfo对象
                try:
                    topic = TopicInfo(**topic_data)
                    topics.append(topic)
                except Exception as e:
                    # 如果转换失败，跳过这个topic
                    logger.warning(f"转换topic失败: {e}, topic_data: {topic_data}")
                    continue
            elif hasattr(topic_data, '__dict__'):
                # 如果是对象，转换为TopicInfo
                try:
                    topic_dict = (
                        topic_data.__dict__ if hasattr(topic_data, '__dict__') else {}
                    )
                    topic = TopicInfo(**topic_dict)
                    topics.append(topic)
                except Exception as e:
                    logger.warning(f"转换topic对象失败: {e}")
                    continue

    # 安全地转换roles字段：从 RoleAssignment 对象转换为 dict
    roles = None
    if hasattr(doc_group_profile_raw, 'roles') and doc_group_profile_raw.roles:
        roles = {}
        if isinstance(doc_group_profile_raw.roles, dict):
            for role_name, assignments in doc_group_profile_raw.roles.items():
                role_list = []
                for assignment in assignments:
                    if hasattr(assignment, 'user_id'):
                        # RoleAssignment 对象，转换为 dict
                        role_dict = {
                            'user_id': assignment.user_id,
                            'user_name': assignment.user_name,
                            'confidence': getattr(assignment, 'confidence', None),
                            'evidences': getattr(assignment, 'evidences', []),
                        }
                        role_list.append(role_dict)
                    elif isinstance(assignment, dict):
                        # 已经是 dict，直接使用
                        role_list.append(assignment)
                if role_list:
                    roles[role_name] = role_list
        else:
            # 如果不是字典，尝试转换
            try:
                roles = (
                    dict(doc_group_profile_raw.roles)
                    if doc_group_profile_raw.roles
                    else {}
                )
            except Exception as e:
                logger.warning(f"转换roles失败: {e}")
                roles = {}

    # 安全地转换extend字段
    extend = None
    if hasattr(doc_group_profile_raw, 'extend') and doc_group_profile_raw.extend:
        if isinstance(doc_group_profile_raw.extend, dict):
            extend = doc_group_profile_raw.extend
        else:
            # 如果不是字典，尝试转换
            try:
                extend = (
                    dict(doc_group_profile_raw.extend)
                    if doc_group_profile_raw.extend
                    else {}
                )
            except Exception as e:
                logger.warning(f"转换extend失败: {e}")
                extend = {}

    # 安全地转换timestamp字段：从datetime转换为整数毫秒时间戳
    timestamp = None
    if hasattr(doc_group_profile_raw, 'timestamp') and doc_group_profile_raw.timestamp:
        if isinstance(doc_group_profile_raw.timestamp, datetime):
            # 将datetime转换为毫秒时间戳
            timestamp = int(doc_group_profile_raw.timestamp.timestamp() * 1000)
        elif isinstance(doc_group_profile_raw.timestamp, (int, float)):
            # 如果已经是数值，确保是整数
            timestamp = int(doc_group_profile_raw.timestamp)
        else:
            logger.warning(
                f"无法转换timestamp: {type(doc_group_profile_raw.timestamp)}"
            )

    return {'topics': topics, 'roles': roles, 'extend': extend, 'timestamp': timestamp}
