from dataclasses import dataclass
import random
import time
import json
import traceback
from api_specs.dtos.memory_command import MemorizeRequest, MemorizeOfflineRequest
from memory_layer.memory_manager import MemoryManager
from api_specs.memory_types import (
    MemoryType,
    MemCell,
    Memory,
    RawDataType,
    ForesightItem,
)
from memory_layer.memory_extractor.event_log_extractor import EventLog
from memory_layer.memory_extractor.profile_memory_extractor import ProfileMemory
from core.di import get_bean_by_type
from infra_layer.adapters.out.persistence.repository.episodic_memory_raw_repository import (
    EpisodicMemoryRawRepository,
)
from infra_layer.adapters.out.persistence.repository.foresight_record_repository import (
    ForesightRecordRawRepository,
)
from infra_layer.adapters.out.persistence.repository.event_log_record_raw_repository import (
    EventLogRecordRawRepository,
)
from infra_layer.adapters.out.persistence.repository.conversation_status_raw_repository import (
    ConversationStatusRawRepository,
)
from infra_layer.adapters.out.persistence.repository.conversation_meta_raw_repository import (
    ConversationMetaRawRepository,
)
from infra_layer.adapters.out.persistence.repository.memcell_raw_repository import (
    MemCellRawRepository,
)
from infra_layer.adapters.out.persistence.repository.core_memory_raw_repository import (
    CoreMemoryRawRepository,
)
from infra_layer.adapters.out.persistence.repository.group_user_profile_memory_raw_repository import (
    GroupUserProfileMemoryRawRepository,
)
from infra_layer.adapters.out.persistence.repository.group_profile_raw_repository import (
    GroupProfileRawRepository,
)
from infra_layer.adapters.out.persistence.repository.conversation_data_raw_repository import (
    ConversationDataRepository,
)
from api_specs.memory_types import RawDataType
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import uuid
from datetime import datetime, timedelta
import os
import asyncio
from collections import defaultdict
from common_utils.datetime_utils import (
    get_now_with_timezone,
    to_iso_format,
    from_iso_format,
)
from memory_layer.memcell_extractor.base_memcell_extractor import StatusResult
import traceback

from core.lock.redis_distributed_lock import distributed_lock
from core.observation.logger import get_logger
from infra_layer.adapters.out.search.elasticsearch.converter.episodic_memory_converter import (
    EpisodicMemoryConverter,
)
from infra_layer.adapters.out.search.milvus.converter.episodic_memory_milvus_converter import (
    EpisodicMemoryMilvusConverter,
)
from infra_layer.adapters.out.search.elasticsearch.converter.foresight_converter import (
    ForesightConverter,
)
from infra_layer.adapters.out.search.milvus.converter.foresight_milvus_converter import (
    ForesightMilvusConverter,
)
from infra_layer.adapters.out.search.elasticsearch.converter.event_log_converter import (
    EventLogConverter,
)
from infra_layer.adapters.out.search.milvus.converter.event_log_milvus_converter import (
    EventLogMilvusConverter,
)
from infra_layer.adapters.out.search.repository.episodic_memory_milvus_repository import (
    EpisodicMemoryMilvusRepository,
)
from infra_layer.adapters.out.search.repository.episodic_memory_es_repository import (
    EpisodicMemoryEsRepository,
)
from infra_layer.adapters.out.search.repository.foresight_milvus_repository import (
    ForesightMilvusRepository,
)
from infra_layer.adapters.out.search.repository.event_log_milvus_repository import (
    EventLogMilvusRepository,
)
from biz_layer.mem_sync import MemorySyncService

logger = get_logger(__name__)


@dataclass
class MemoryDocPayload:
    memory_type: MemoryType
    doc: Any


def _clone_foresight_item(raw_item: Any) -> Optional[ForesightItem]:
    """将任意结构的前瞻条目转换为 ForesightItem 实例"""
    if raw_item is None:
        return None

    if isinstance(raw_item, ForesightItem):
        return ForesightItem(
            content=raw_item.content,
            evidence=getattr(raw_item, "evidence", None),
            start_time=getattr(raw_item, "start_time", None),
            end_time=getattr(raw_item, "end_time", None),
            duration_days=getattr(raw_item, "duration_days", None),
            source_episode_id=getattr(raw_item, "source_episode_id", None),
            vector=getattr(raw_item, "vector", None),
            vector_model=getattr(raw_item, "vector_model", None),
        )

    if isinstance(raw_item, dict):
        return ForesightItem(
            content=raw_item.get("content", ""),
            evidence=raw_item.get("evidence"),
            start_time=raw_item.get("start_time"),
            end_time=raw_item.get("end_time"),
            duration_days=raw_item.get("duration_days"),
            source_episode_id=raw_item.get("source_episode_id"),
            vector=raw_item.get("vector"),
            vector_model=raw_item.get("vector_model"),
        )

    return None


def _clone_event_log(raw_event_log: Any) -> Optional[EventLog]:
    """将任意结构的事件日志转换为 EventLog 实例"""
    if raw_event_log is None:
        return None

    if isinstance(raw_event_log, EventLog):
        return EventLog(
            time=getattr(raw_event_log, "time", ""),
            atomic_fact=list(getattr(raw_event_log, "atomic_fact", []) or []),
            fact_embeddings=getattr(raw_event_log, "fact_embeddings", None),
        )

    if isinstance(raw_event_log, dict):
        return EventLog.from_dict(raw_event_log)

    return None


from biz_layer.memorize_config import MemorizeConfig, DEFAULT_MEMORIZE_CONFIG


async def _trigger_clustering(
    group_id: str,
    memcell: MemCell,
    scene: Optional[str] = None,
    config: MemorizeConfig = DEFAULT_MEMORIZE_CONFIG,
) -> None:
    """触发 MemCell 聚类

    Args:
        group_id: 群组ID
        memcell: 刚保存的 MemCell
        scene: 对话场景（用于决定 Profile 提取策略）
            - None/"work"/"company" 等：使用 group_chat 场景
            - "assistant"/"companion" 等：使用 assistant 场景
    """
    logger.info(
        f"[聚类] 开始触发聚类: group_id={group_id}, event_id={memcell.event_id}, scene={scene}"
    )

    try:
        from memory_layer.cluster_manager import (
            ClusterManager,
            ClusterManagerConfig,
            ClusterState,
        )
        from memory_layer.profile_manager import ProfileManager, ProfileManagerConfig
        from infra_layer.adapters.out.persistence.repository.cluster_state_raw_repository import (
            ClusterStateRawRepository,
        )
        from infra_layer.adapters.out.persistence.repository.user_profile_raw_repository import (
            UserProfileRawRepository,
        )
        from memory_layer.llm.llm_provider import LLMProvider
        from core.di import get_bean_by_type
        import os

        logger.info(f"[聚类] 正在获取 ClusterStateRawRepository...")
        # 获取 MongoDB 存储
        cluster_storage = get_bean_by_type(ClusterStateRawRepository)
        logger.info(
            f"[聚类] ClusterStateRawRepository 获取成功: {type(cluster_storage)}"
        )

        # 创建 ClusterManager（纯计算组件）
        cluster_config = ClusterManagerConfig(
            similarity_threshold=config.cluster_similarity_threshold,
            max_time_gap_days=config.cluster_max_time_gap_days,
        )
        cluster_manager = ClusterManager(config=cluster_config)
        logger.info(f"[聚类] ClusterManager 创建成功")

        # 加载聚类状态
        state_dict = await cluster_storage.load_cluster_state(group_id)
        cluster_state = (
            ClusterState.from_dict(state_dict) if state_dict else ClusterState()
        )
        logger.info(f"[聚类] 加载聚类状态: {len(cluster_state.event_ids)} 个已聚类事件")

        # 将 MemCell 转换为聚类所需的字典格式
        memcell_dict = {
            "event_id": str(memcell.event_id),
            "episode": memcell.episode,
            "timestamp": memcell.timestamp.timestamp() if memcell.timestamp else None,
            "participants": memcell.participants or [],
            "group_id": group_id,
        }

        logger.info(f"[聚类] 开始执行聚类: {memcell_dict['event_id']}")
        print(f"[聚类] 开始执行聚类: event_id={memcell_dict['event_id']}")

        # 执行聚类（纯计算）
        cluster_id, cluster_state = await cluster_manager.cluster_memcell(
            memcell_dict, cluster_state
        )

        # 保存聚类状态
        await cluster_storage.save_cluster_state(group_id, cluster_state.to_dict())
        logger.info(f"[聚类] 聚类状态已保存")

        print(f"[聚类] 聚类完成: cluster_id={cluster_id}")

        if cluster_id:
            logger.info(
                f"[聚类] ✅ MemCell {memcell.event_id} -> Cluster {cluster_id} (group: {group_id})"
            )
            print(f"[聚类] ✅ MemCell {memcell.event_id} -> Cluster {cluster_id}")
        else:
            logger.warning(
                f"[聚类] ⚠️ MemCell {memcell.event_id} 聚类返回 None (group: {group_id})"
            )
            print(f"[聚类] ⚠️ 聚类返回 None")

        # Profile 提取
        if cluster_id:
            await _trigger_profile_extraction(
                group_id=group_id,
                cluster_id=cluster_id,
                cluster_state=cluster_state,
                memcell=memcell,
                scene=scene,
                config=config,
            )

    except Exception as e:
        # 聚类失败，打印详细错误信息并重新抛出
        import traceback

        error_msg = f"[聚类] ❌ 触发聚类失败: {e}"
        logger.error(error_msg, exc_info=True)
        print(error_msg)  # 确保在控制台能看到
        print(traceback.format_exc())
        raise  # 重新抛出异常，让调用者知道失败了


async def _trigger_profile_extraction(
    group_id: str,
    cluster_id: str,
    cluster_state,  # ClusterState
    memcell: MemCell,
    scene: Optional[str] = None,
    config: MemorizeConfig = DEFAULT_MEMORIZE_CONFIG,
) -> None:
    """触发 Profile 提取

    Args:
        group_id: 群组ID
        cluster_id: 当前 memcell 被分配到的 cluster
        cluster_state: 当前聚类状态
        memcell: 当前处理的 MemCell
        scene: 对话场景
        config: 记忆提取配置
    """
    try:
        from memory_layer.profile_manager import ProfileManager, ProfileManagerConfig
        from infra_layer.adapters.out.persistence.repository.user_profile_raw_repository import (
            UserProfileRawRepository,
        )
        from memory_layer.llm.llm_provider import LLMProvider
        from core.di import get_bean_by_type
        import os

        # 获取当前 cluster 中的 memcell 数量
        cluster_memcell_count = cluster_state.cluster_counts.get(cluster_id)
        if cluster_memcell_count < config.profile_min_memcells:
            logger.debug(
                f"[Profile] Cluster {cluster_id} 只有 {cluster_memcell_count} 个 memcells "
                f"(需要 {config.profile_min_memcells})，跳过提取"
            )
            return

        logger.info(
            f"[Profile] 开始提取 Profile: cluster={cluster_id}, memcells={cluster_memcell_count}"
        )

        # 获取 Profile 存储
        profile_storage = get_bean_by_type(UserProfileRawRepository)

        # 创建 LLM Provider
        llm_provider = LLMProvider(
            provider_type=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4"),
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "16384")),
        )

        # 确定场景
        profile_scenario = (
            "assistant"
            if scene and scene.lower() in ["assistant", "companion"]
            else "group_chat"
        )

        # 创建 ProfileManager（纯计算组件）
        profile_config = ProfileManagerConfig(
            scenario=profile_scenario,
            min_confidence=config.profile_min_confidence,
            enable_versioning=config.profile_enable_versioning,
            auto_extract=True,
        )
        profile_manager = ProfileManager(
            llm_provider=llm_provider,
            config=profile_config,
            group_id=group_id,
            group_name=None,
        )

        # 获取参与者列表（排除机器人）
        user_id_list = [
            u
            for u in (memcell.participants or [])
            if "robot" not in u.lower() and "assistant" not in u.lower()
        ]

        # 加载已有的 profiles
        old_profiles_dict = await profile_storage.get_all_profiles()
        old_profiles = list(old_profiles_dict.values()) if old_profiles_dict else []

        # 执行 Profile 提取（直接传递 MemCell 对象，而不是字典）
        new_profiles = await profile_manager.extract_profiles(
            memcells=[memcell],  # 传递 MemCell 对象
            old_profiles=old_profiles,
            user_id_list=user_id_list,
        )

        # 保存新提取的 profiles
        for profile in new_profiles:
            if isinstance(profile, dict):
                user_id = profile.get('user_id')
            else:
                user_id = getattr(profile, 'user_id', None)

            if user_id:
                await profile_storage.save_profile(
                    user_id,
                    profile,
                    metadata={
                        "group_id": group_id,
                        "scenario": profile_scenario,
                        "cluster_id": cluster_id,
                        "memcell_count": cluster_memcell_count,
                        "confidence": config.profile_min_confidence,
                    },
                )
                logger.info(
                    f"[Profile] ✅ 保存 Profile: user_id={user_id}, group_id={group_id}, cluster={cluster_id}"
                )
            else:
                logger.warning(
                    f"[Profile] ⚠️ Profile 没有 user_id，跳过保存: {type(profile)}"
                )

        logger.info(
            f"[Profile] ✅ Profile 提取完成: 提取 {len(new_profiles)} 个 profiles"
        )

    except Exception as e:
        import traceback

        logger.error(f"[Profile] ❌ Profile 提取失败: {e}", exc_info=True)
        print(f"[Profile] ❌ Profile 提取失败: {e}")
        print(traceback.format_exc())
        # Profile 提取失败不应阻塞主流程


def _convert_data_type_to_raw_data_type(data_type) -> RawDataType:
    """
    将不同的数据类型枚举转换为统一的RawDataType

    Args:
        data_type: 可能是DataTypeEnum、RawDataType或字符串

    Returns:
        RawDataType: 转换后的统一数据类型
    """
    if isinstance(data_type, RawDataType):
        return data_type

    # 获取字符串值
    if hasattr(data_type, 'value'):
        type_str = data_type.value
    else:
        type_str = str(data_type)

    # 映射转换
    type_mapping = {
        "Conversation": RawDataType.CONVERSATION,
        "CONVERSATION": RawDataType.CONVERSATION,
        # 其他类型映射到CONVERSATION作为默认值
    }

    return type_mapping.get(type_str, RawDataType.CONVERSATION)


from biz_layer.mem_db_operations import (
    _convert_timestamp_to_time,
    _convert_episode_memory_to_doc,
    _convert_foresight_to_doc,
    _convert_event_log_to_docs,
    _save_memcell_to_database,
    _save_profile_memory_to_core,
    ConversationStatus,
    _update_status_for_new_conversation,
    _update_status_for_continuing_conversation,
    _update_status_after_memcell_extraction,
    _convert_original_data_for_profile_extractor,
    _save_group_profile_memory,
    _save_profile_memory_to_group_user_profile_memory,
    _convert_document_to_group_importance_evidence,
    _normalize_datetime_for_storage,
    _convert_projects_participated_list,
    _convert_group_profile_raw_to_memory_format,
)
from typing import Tuple


def if_memorize(memcell: MemCell) -> bool:
    return True


# ==================== MemCell 处理业务逻辑 ====================


@dataclass
class ExtractionState:
    """记忆提取状态，存储中间结果"""

    memcell: MemCell
    request: MemorizeRequest
    current_time: datetime
    scene: str
    is_assistant_scene: bool
    participants: List[str]
    group_episode: Optional[Memory] = None
    group_episode_memories: List[Memory] = None
    episode_memories: List[Memory] = None
    parent_docs_map: Dict[str, Any] = None

    def __post_init__(self):
        self.group_episode_memories = []
        self.episode_memories = []
        self.parent_docs_map = {}


async def process_memory_extraction(
    memcell: MemCell,
    request: MemorizeRequest,
    memory_manager: MemoryManager,
    current_time: datetime,
):
    """
    记忆提取主流程

    从 MemCell 开始，提取 Episode、Foresight、EventLog 等所有记忆类型。
    """
    # 1. 初始化状态
    state = await _init_extraction_state(memcell, request, current_time)

    # 2. 提取 Episodes
    await _extract_episodes(state, memory_manager)

    # 3. 更新 MemCell 并触发聚类
    await _update_memcell_and_cluster(state)

    # 4. 保存和提取后续记忆
    if if_memorize(memcell):
        await _process_memories(state, memory_manager)


async def _init_extraction_state(
    memcell: MemCell, request: MemorizeRequest, current_time: datetime
) -> ExtractionState:
    """初始化提取状态"""
    conversation_meta_repo = get_bean_by_type(ConversationMetaRawRepository)
    conversation_meta = await conversation_meta_repo.get_by_group_id(request.group_id)
    scene = (
        conversation_meta.scene
        if conversation_meta and conversation_meta.scene
        else "assistant"
    )
    is_assistant_scene = scene.lower() in ["assistant", "companion"]
    participants = list(set(memcell.participants)) if memcell.participants else []

    return ExtractionState(
        memcell=memcell,
        request=request,
        current_time=current_time,
        scene=scene,
        is_assistant_scene=is_assistant_scene,
        participants=participants,
    )


async def _extract_episodes(state: ExtractionState, memory_manager: MemoryManager):
    """提取群组和个人 Episodes"""
    if state.is_assistant_scene:
        logger.info("[MemCell处理] assistant 场景，仅提取群组 Episode")
        tasks = [_create_episode_task(state, memory_manager, None)]
    else:
        logger.info(
            f"[MemCell处理] 非 assistant 场景，提取群组 + {len(state.participants)} 个个人 Episode"
        )
        tasks = [_create_episode_task(state, memory_manager, None)]
        tasks.extend(
            [
                _create_episode_task(state, memory_manager, uid)
                for uid in state.participants
            ]
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    _process_episode_results(state, results)


def _create_episode_task(
    state: ExtractionState, memory_manager: MemoryManager, user_id: Optional[str]
):
    """创建 Episode 提取任务"""
    return memory_manager.extract_memory(
        memcell=state.memcell,
        memory_type=MemoryType.EPISODIC_MEMORY,
        user_id=user_id,
        group_id=state.request.group_id,
        group_name=state.request.group_name,
    )


def _process_episode_results(state: ExtractionState, results: List[Any]):
    """处理 Episode 提取结果"""
    # 群组 Episode
    group_episode = results[0] if results else None
    if isinstance(group_episode, Exception):
        logger.error(f"[MemCell处理] ❌ 群组 Episode 异常: {group_episode}")
        group_episode = None
    elif group_episode:
        group_episode.ori_event_id_list = [state.memcell.event_id]
        group_episode.memcell_event_id_list = [state.memcell.event_id]
        state.group_episode_memories.append(group_episode)
        state.group_episode = group_episode
        state.memcell.episode = group_episode.episode
        state.memcell.subject = group_episode.subject
        logger.info("[MemCell处理] ✅ 群组 Episode 提取成功")

    # 个人 Episodes
    if not state.is_assistant_scene:
        for user_id, result in zip(state.participants, results[1:]):
            if isinstance(result, Exception):
                logger.error(f"[MemCell处理] ❌ 个人 Episode 异常: user_id={user_id}")
                continue
            if result:
                result.ori_event_id_list = [state.memcell.event_id]
                result.memcell_event_id_list = [state.memcell.event_id]
                state.episode_memories.append(result)
                logger.info(f"[MemCell处理] ✅ 个人 Episode 成功: user_id={user_id}")


async def _update_memcell_and_cluster(state: ExtractionState):
    """更新 MemCell 的 episode 字段并触发聚类"""
    if not state.request.group_id or not state.group_episode:
        return

    # 更新 MemCell
    try:
        memcell_repo = get_bean_by_type(MemCellRawRepository)
        await memcell_repo.update_by_event_id(
            event_id=state.memcell.event_id,
            update_data={
                "episode": state.group_episode.episode,
                "subject": state.group_episode.subject,
            },
        )
        logger.info(f"[MemCell处理] ✅ 更新 MemCell episode: {state.memcell.event_id}")
    except Exception as e:
        logger.error(f"[MemCell处理] ❌ 更新 MemCell 失败: {e}")

    # 触发聚类
    try:
        memcell_for_clustering = MemCell(
            event_id=state.memcell.event_id,
            user_id_list=state.memcell.user_id_list,
            original_data=state.memcell.original_data,
            timestamp=state.memcell.timestamp,
            summary=state.memcell.summary,
            group_id=state.memcell.group_id,
            group_name=state.memcell.group_name,
            participants=state.memcell.participants,
            type=state.memcell.type,
            episode=state.group_episode.episode,
        )
        await _trigger_clustering(
            state.request.group_id, memcell_for_clustering, state.scene
        )
        logger.info(f"[MemCell处理] ✅ 聚类完成 (scene={state.scene})")
    except Exception as e:
        logger.error(f"[MemCell处理] ❌ 触发聚类失败: {e}")


async def _process_memories(state: ExtractionState, memory_manager: MemoryManager):
    """保存 Episodes 并提取/保存 Foresight 和 EventLog"""
    await load_core_memories(state.request, state.participants, state.current_time)

    episodic_source = state.group_episode_memories + state.episode_memories
    episodes_to_save = list(episodic_source)

    # assistant 场景：复制群组 Episode 给每个用户
    if state.is_assistant_scene and state.group_episode_memories:
        episodes_to_save.extend(_clone_episodes_for_users(state))

    if episodes_to_save:
        await _save_episodes(state, episodes_to_save, episodic_source)

    if episodic_source:
        foresight_memories, event_logs = await _extract_foresight_and_eventlog(
            state, memory_manager, episodic_source
        )
        await _save_foresight_and_eventlog(state, foresight_memories, event_logs)

    await update_status_after_memcell(
        state.request, state.memcell, state.current_time, state.request.raw_data_type
    )


def _clone_episodes_for_users(state: ExtractionState) -> List[Memory]:
    """为每个用户复制群组 Episode"""
    from dataclasses import replace

    cloned = []
    group_ep = state.group_episode_memories[0]
    for user_id in state.participants:
        if "robot" in user_id.lower() or "assistant" in user_id.lower():
            continue
        cloned.append(replace(group_ep, user_id=user_id, user_name=user_id))
    logger.info(f"[MemCell处理] 复制群组 Episode 给 {len(cloned)} 个用户")
    return cloned


async def _save_episodes(
    state: ExtractionState,
    episodes_to_save: List[Memory],
    episodic_source: List[Memory],
):
    """保存 Episodes 到数据库"""
    for ep in episodes_to_save:
        if getattr(ep, "group_name", None) is None:
            ep.group_name = state.request.group_name
        if getattr(ep, "user_name", None) is None:
            ep.user_name = ep.user_id

    docs = [
        _convert_episode_memory_to_doc(ep, state.current_time)
        for ep in episodes_to_save
    ]
    payloads = [MemoryDocPayload(MemoryType.EPISODIC_MEMORY, doc) for doc in docs]
    saved_map = await save_memory_docs(payloads)
    saved_docs = saved_map.get(MemoryType.EPISODIC_MEMORY, [])

    for ep, saved_doc in zip(episodic_source, saved_docs):
        ep.event_id = str(saved_doc.event_id)
        state.parent_docs_map[str(saved_doc.event_id)] = saved_doc


async def _extract_foresight_and_eventlog(
    state: ExtractionState, memory_manager: MemoryManager, episodic_source: List[Memory]
) -> Tuple[List[ForesightItem], List[EventLog]]:
    """提取 Foresight 和 EventLog"""
    logger.info(
        f"[MemCell处理] 提取 Foresight/EventLog，共 {len(episodic_source)} 个 Episode"
    )

    tasks = []
    metadata = []

    for ep in episodic_source:
        if not ep.event_id:
            continue
        tasks.append(
            memory_manager.extract_memory(
                memcell=state.memcell,
                memory_type=MemoryType.FORESIGHT,
                user_id=ep.user_id,
                episode_memory=ep,
            )
        )
        metadata.append({'type': MemoryType.FORESIGHT, 'ep': ep})
        tasks.append(
            memory_manager.extract_memory(
                memcell=state.memcell,
                memory_type=MemoryType.EVENT_LOG,
                user_id=ep.user_id,
                episode_memory=ep,
            )
        )
        metadata.append({'type': MemoryType.EVENT_LOG, 'ep': ep})

    if not tasks:
        return [], []

    results = await asyncio.gather(*tasks, return_exceptions=True)

    foresight_memories = []
    event_logs = []

    for meta, result in zip(metadata, results):
        if isinstance(result, Exception) or not result:
            continue

        ep = meta['ep']
        if meta['type'] == MemoryType.FORESIGHT:
            for mem in result:
                mem.parent_event_id = ep.event_id
                mem.user_id = ep.user_id
                mem.group_id = ep.group_id
                mem.group_name = ep.group_name
                mem.user_name = ep.user_name
                foresight_memories.append(mem)
        elif meta['type'] == MemoryType.EVENT_LOG:
            result.parent_event_id = ep.event_id
            result.user_id = ep.user_id
            result.group_id = ep.group_id
            result.group_name = ep.group_name
            result.user_name = ep.user_name
            event_logs.append(result)

    return foresight_memories, event_logs


async def _save_foresight_and_eventlog(
    state: ExtractionState,
    foresight_memories: List[ForesightItem],
    event_logs: List[EventLog],
):
    """保存 Foresight 和 EventLog"""
    foresight_docs = []
    for mem in foresight_memories:
        parent_doc = state.parent_docs_map.get(str(mem.parent_event_id))
        if parent_doc:
            foresight_docs.append(
                _convert_foresight_to_doc(mem, parent_doc, state.current_time)
            )

    event_log_docs = []
    for el in event_logs:
        parent_doc = state.parent_docs_map.get(str(el.parent_event_id))
        if parent_doc:
            event_log_docs.extend(
                _convert_event_log_to_docs(el, parent_doc, state.current_time)
            )

    # assistant 场景：复制给每个用户
    if state.is_assistant_scene:
        user_ids = [
            u
            for u in state.participants
            if "robot" not in u.lower() and "assistant" not in u.lower()
        ]
        foresight_docs.extend(
            [
                doc.model_copy(update={"user_id": uid, "user_name": uid})
                for doc in foresight_docs
                for uid in user_ids
            ]
        )
        event_log_docs.extend(
            [
                doc.model_copy(update={"user_id": uid, "user_name": uid})
                for doc in event_log_docs
                for uid in user_ids
            ]
        )
        logger.info(f"[MemCell处理] 复制 Foresight/EventLog 给 {len(user_ids)} 个用户")

    payloads = []
    payloads.extend(
        MemoryDocPayload(MemoryType.FORESIGHT, doc) for doc in foresight_docs
    )
    payloads.extend(
        MemoryDocPayload(MemoryType.EVENT_LOG, doc) for doc in event_log_docs
    )
    if payloads:
        await save_memory_docs(payloads)


def extract_message_time(raw_data):
    """
    从RawData对象中提取消息时间

    Args:
        raw_data: RawData对象

    Returns:
        datetime: 消息时间，如果无法提取则返回None
    """
    # 优先从timestamp字段获取
    if hasattr(raw_data, 'timestamp') and raw_data.timestamp:
        try:
            return _normalize_datetime_for_storage(raw_data.timestamp)
        except Exception as e:
            logger.debug(f"Failed to parse timestamp from raw_data.timestamp: {e}")
            pass

    # 从extend字段获取
    if (
        hasattr(raw_data, 'extend')
        and raw_data.extend
        and isinstance(raw_data.extend, dict)
    ):
        timestamp_val = raw_data.extend.get('timestamp')
        if timestamp_val:
            try:
                return _normalize_datetime_for_storage(timestamp_val)
            except Exception as e:
                logger.debug(f"Failed to parse timestamp from extend field: {e}")
                pass

    return None


from core.observation.tracing.decorators import trace_logger


@trace_logger(operation_name="mem_memorize preprocess_conv_request", log_level="info")
async def preprocess_conv_request(
    request: MemorizeRequest, current_time: datetime
) -> MemorizeRequest:
    """
    简化版的请求预处理：
    1. 从 Redis 读取所有历史消息
    2. 将历史消息作为 history_raw_data_list
    3. 将当前新消息作为 new_raw_data_list
    4. 边界检测由后续逻辑处理（检测后会清空或保留 Redis）
    """

    logger.info(f"[preprocess] 开始处理: group_id={request.group_id}")

    # 检查是否有新数据
    if not request.new_raw_data_list:
        logger.info("[preprocess] 没有新数据，跳过处理")
        return None

    # 使用 conversation_data_repo 进行先取后存操作
    conversation_data_repo = get_bean_by_type(ConversationDataRepository)

    try:
        # 第一步：先从 conversation_data_repo 获取历史消息
        # 这里不限制时间范围，获取最近1000条历史消息（由缓存管理器的max_length控制）
        history_raw_data_list = await conversation_data_repo.get_conversation_data(
            group_id=request.group_id, start_time=None, end_time=None, limit=1000
        )

        logger.info(
            f"[preprocess] 从 conversation_data_repo 读取 {len(history_raw_data_list)} 条历史消息"
        )

        # 更新 request
        request.history_raw_data_list = history_raw_data_list
        # new_raw_data_list 保持不变（就是新传入的消息）

        logger.info(
            f"[preprocess] 完成: 历史 {len(history_raw_data_list)} 条, 新消息 {len(request.new_raw_data_list)} 条"
        )

        return request

    except Exception as e:
        logger.error(f"[preprocess] Redis 读取失败: {e}")
        traceback.print_exc()
        # Redis 失败时，使用原始 request
        return request


async def update_status_when_no_memcell(
    request: MemorizeRequest,
    status_result: StatusResult,
    current_time: datetime,
    data_type: RawDataType,
):
    if data_type == RawDataType.CONVERSATION:
        # 尝试更新状态表
        try:
            status_repo = get_bean_by_type(ConversationStatusRawRepository)

            if status_result.should_wait:
                logger.info(f"[mem_memorize] 判断为无法判断边界继续等待，不更新状态表")
                return
            else:
                logger.info(f"[mem_memorize] 判断为非边界，继续累积msg，更新状态表")
                # 获取最新消息时间戳
                latest_time = _convert_timestamp_to_time(current_time, current_time)
                if request.new_raw_data_list:
                    last_msg = request.new_raw_data_list[-1]
                    if hasattr(last_msg, 'content') and isinstance(
                        last_msg.content, dict
                    ):
                        latest_time = last_msg.content.get('timestamp', latest_time)
                    elif hasattr(last_msg, 'timestamp'):
                        latest_time = last_msg.timestamp

                if not latest_time:
                    latest_time = min(latest_time, current_time)

                # 使用封装函数更新对话延续状态
                await _update_status_for_continuing_conversation(
                    status_repo, request, latest_time, current_time
                )

        except Exception as e:
            logger.error(f"更新状态表失败: {e}")
    else:
        pass


async def update_status_after_memcell(
    request: MemorizeRequest,
    memcell: MemCell,
    current_time: datetime,
    data_type: RawDataType,
):
    if data_type == RawDataType.CONVERSATION:
        # 更新状态表中的last_memcell_time至memcell的时间戳
        try:
            status_repo = get_bean_by_type(ConversationStatusRawRepository)

            # 获取MemCell的时间戳
            memcell_time = None
            if memcell and hasattr(memcell, 'timestamp'):
                memcell_time = memcell.timestamp
            else:
                memcell_time = current_time

            # 使用封装函数更新MemCell提取后的状态
            await _update_status_after_memcell_extraction(
                status_repo, request, memcell_time, current_time
            )

            logger.info(f"[mem_memorize] 记忆提取完成，状态表已更新")

        except Exception as e:
            logger.error(f"最终状态表更新失败: {e}")
    else:
        pass


async def save_personal_profile_memory(
    profile_memories: List[ProfileMemory], version: Optional[str] = None
):
    logger.info(f"[mem_memorize] 保存 {len(profile_memories)} 个个人档案记忆到数据库")
    # 初始化Repository实例
    core_memory_repo = get_bean_by_type(CoreMemoryRawRepository)

    # 保存个人档案记忆到GroupUserProfileMemoryRawRepository
    for profile_mem in profile_memories:
        await _save_profile_memory_to_core(profile_mem, core_memory_repo, version)
        # 移除单个操作成功日志


async def save_memory_docs(
    doc_payloads: List[MemoryDocPayload], version: Optional[str] = None
) -> Dict[MemoryType, List[Any]]:
    """
    通用 Doc 保存函数，按 MemoryType 枚举自动保存并同步
    """

    grouped_docs: Dict[MemoryType, List[Any]] = defaultdict(list)
    for payload in doc_payloads:
        if payload and payload.doc:
            grouped_docs[payload.memory_type].append(payload.doc)

    saved_result: Dict[MemoryType, List[Any]] = {}

    # Episodic
    episodic_docs = grouped_docs.get(MemoryType.EPISODIC_MEMORY, [])
    if episodic_docs:
        episodic_repo = get_bean_by_type(EpisodicMemoryRawRepository)
        episodic_es_repo = get_bean_by_type(EpisodicMemoryEsRepository)
        episodic_milvus_repo = get_bean_by_type(EpisodicMemoryMilvusRepository)
        saved_episodic: List[Any] = []

        for doc in episodic_docs:
            saved_doc = await episodic_repo.append_episodic_memory(doc)
            saved_episodic.append(saved_doc)

            es_doc = EpisodicMemoryConverter.from_mongo(saved_doc)
            await episodic_es_repo.create(es_doc)

            milvus_entity = EpisodicMemoryMilvusConverter.from_mongo(saved_doc)
            vector = (
                milvus_entity.get("vector") if isinstance(milvus_entity, dict) else None
            )
            if vector and len(vector) > 0:
                await episodic_milvus_repo.insert(milvus_entity, flush=False)
            else:
                logger.warning(
                    "[mem_memorize] 跳过写入Milvus：向量为空或缺失，event_id=%s",
                    getattr(saved_doc, "event_id", None),
                )

        saved_result[MemoryType.EPISODIC_MEMORY] = saved_episodic

    # Foresight
    foresight_docs = grouped_docs.get(MemoryType.FORESIGHT, [])
    if foresight_docs:
        foresight_repo = get_bean_by_type(ForesightRecordRawRepository)
        saved_foresight = await foresight_repo.create_batch(foresight_docs)
        saved_result[MemoryType.FORESIGHT] = saved_foresight

        sync_service = get_bean_by_type(MemorySyncService)
        await sync_service.sync_batch_foresights(
            saved_foresight, sync_to_es=True, sync_to_milvus=True
        )

    # Event Log
    event_log_docs = grouped_docs.get(MemoryType.EVENT_LOG, [])
    if event_log_docs:
        event_log_repo = get_bean_by_type(EventLogRecordRawRepository)
        saved_event_logs = await event_log_repo.create_batch(event_log_docs)
        saved_result[MemoryType.EVENT_LOG] = saved_event_logs

        sync_service = get_bean_by_type(MemorySyncService)
        await sync_service.sync_batch_event_logs(
            saved_event_logs, sync_to_es=True, sync_to_milvus=True
        )

    # Profile
    profile_docs = grouped_docs.get(MemoryType.PROFILE, [])
    if profile_docs:
        group_user_profile_repo = get_bean_by_type(GroupUserProfileMemoryRawRepository)
        saved_profiles = []
        for profile_mem in profile_docs:
            try:
                await _save_profile_memory_to_group_user_profile_memory(
                    profile_mem, group_user_profile_repo, version
                )
                saved_profiles.append(profile_mem)
            except Exception as exc:
                logger.error(f"保存Profile记忆失败: {exc}")
        if saved_profiles:
            saved_result[MemoryType.PROFILE] = saved_profiles

    group_profile_docs = grouped_docs.get(MemoryType.GROUP_PROFILE, [])
    if group_profile_docs:
        group_profile_repo = get_bean_by_type(GroupProfileRawRepository)
        saved_group_profiles = []
        for mem in group_profile_docs:
            try:
                await _save_group_profile_memory(mem, group_profile_repo, version)
                saved_group_profiles.append(mem)
            except Exception as exc:
                logger.error(f"保存Group Profile记忆失败: {exc}")
        if saved_group_profiles:
            saved_result[MemoryType.GROUP_PROFILE] = saved_group_profiles

    return saved_result


async def load_core_memories(
    request: MemorizeRequest, participants: List[str], current_time: datetime
):
    logger.info(f"[mem_memorize] 读取用户数据: {participants}")
    # 初始化Repository实例
    core_memory_repo = get_bean_by_type(CoreMemoryRawRepository)

    # 读取用户CoreMemory数据
    user_core_memories = {}
    for user_id in participants:
        try:
            core_memory = await core_memory_repo.get_by_user_id(user_id)
            if core_memory:
                user_core_memories[user_id] = core_memory
            # 移除单个用户的成功/失败日志
        except Exception as e:
            logger.error(f"获取用户 {user_id} CoreMemory失败: {e}")

    logger.info(f"[mem_memorize] 获取到 {len(user_core_memories)} 个用户CoreMemory")

    # 直接从CoreMemory转换为ProfileMemory对象列表
    old_memory_list = []
    if user_core_memories:
        for user_id, core_memory in user_core_memories.items():
            if core_memory:
                # 直接创建ProfileMemory对象
                profile_memory = ProfileMemory(
                    # Memory 基类必需字段
                    memory_type=MemoryType.CORE,
                    user_id=user_id,
                    timestamp=to_iso_format(current_time),
                    ori_event_id_list=[],
                    # Memory 基类可选字段
                    subject=f"{getattr(core_memory, 'user_name', user_id)}的个人档案",
                    summary=f"用户{user_id}的基本信息：{getattr(core_memory, 'position', '未知角色')}",
                    group_id=request.group_id,
                    participants=[user_id],
                    type=RawDataType.CONVERSATION,
                    # ProfileMemory 特有字段 - 直接使用原始字典格式
                    hard_skills=getattr(core_memory, 'hard_skills', None),
                    soft_skills=getattr(core_memory, 'soft_skills', None),
                    output_reasoning=getattr(core_memory, 'output_reasoning', None),
                    motivation_system=getattr(core_memory, 'motivation_system', None),
                    fear_system=getattr(core_memory, 'fear_system', None),
                    value_system=getattr(core_memory, 'value_system', None),
                    humor_use=getattr(core_memory, 'humor_use', None),
                    colloquialism=getattr(core_memory, 'colloquialism', None),
                    projects_participated=_convert_projects_participated_list(
                        getattr(core_memory, 'projects_participated', None)
                    ),
                )
                old_memory_list.append(profile_memory)

        logger.info(
            f"[mem_memorize] 直接转换了 {len(old_memory_list)} 个CoreMemory为ProfileMemory"
        )
    else:
        logger.info(f"[mem_memorize] 没有用户CoreMemory数据，old_memory_list为空")


async def memorize(request: MemorizeRequest) -> Optional[str]:
    """
    记忆提取主流程 (全局队列版)

    流程:
    1. 提取 MemCell
    2. 保存 MemCell 到数据库
    3. 提交到全局队列由 Worker 异步处理
    4. 立即返回，不等待后续处理完成
    """
    logger.info(f"[mem_memorize] request.current_time: {request.current_time}")

    # 获取当前时间
    if request.current_time:
        current_time = request.current_time
    else:
        current_time = get_now_with_timezone() + timedelta(seconds=1)
    logger.info(f"[mem_memorize] 当前时间: {current_time}")

    memory_manager = MemoryManager()
    conversation_data_repo = get_bean_by_type(ConversationDataRepository)
    # ===== MemCell 提取阶段 =====
    if request.raw_data_type == RawDataType.CONVERSATION:
        request = await preprocess_conv_request(request, current_time)
        if request == None:
            logger.warning(f"[mem_memorize] preprocess_conv_request 返回 None")
            return None

    # 边界检测
    now = time.time()
    logger.info("=" * 80)
    logger.info(f"[边界检测] 开始检测: group_id={request.group_id}")
    logger.info(f"[边界检测] 暂存历史消息: {len(request.history_raw_data_list)} 条")
    logger.info(f"[边界检测] 新消息: {len(request.new_raw_data_list)} 条")
    logger.info("=" * 80)

    memcell_result = await memory_manager.extract_memcell(
        request.history_raw_data_list,
        request.new_raw_data_list,
        request.raw_data_type,
        request.group_id,
        request.group_name,
        request.user_id_list,
    )
    logger.debug(f"[mem_memorize] 提取 MemCell 耗时: {time.time() - now}秒")

    if memcell_result == None:
        logger.warning(f"[mem_memorize] 跳过提取MemCell")
        return None

    memcell, status_result = memcell_result

    # 检查边界检测结果
    logger.info("=" * 80)
    logger.info(f"[边界检测结果] memcell is None: {memcell is None}")
    if memcell is None:
        logger.info(
            f"[边界检测结果] 判断: {'需要等待更多消息' if status_result.should_wait else '非边界，继续累积'}"
        )
    else:
        logger.info(f"[边界检测结果] 判断: 是边界！event_id={memcell.event_id}")
    logger.info("=" * 80)

    if memcell == None:
        # 保存新消息到 conversation_data_repo
        await conversation_data_repo.save_conversation_data(
            request.new_raw_data_list, request.group_id
        )
        await update_status_when_no_memcell(
            request, status_result, current_time, request.raw_data_type
        )
        logger.warning(f"[mem_memorize] 未检测到边界，返回")
        return None
    else:
        logger.info(f"[mem_memorize] 成功提取MemCell")
        # 判断为边界，清空对话历史数据（重新开始累积）
        try:
            conversation_data_repo = get_bean_by_type(ConversationDataRepository)
            delete_success = await conversation_data_repo.delete_conversation_data(
                request.group_id
            )
            if delete_success:
                logger.info(
                    f"[mem_memorize] 判断为边界，已清空对话历史: group_id={request.group_id}"
                )
            else:
                logger.warning(
                    f"[mem_memorize] 清空对话历史失败: group_id={request.group_id}"
                )
            # 保存新消息到 conversation_data_repo
            await conversation_data_repo.save_conversation_data(
                request.new_raw_data_list, request.group_id
            )
        except Exception as e:
            logger.error(f"[mem_memorize] 清空对话历史异常: {e}")
            traceback.print_exc()
    # TODO: 读状态表，读取累积的MemCell数据表，判断是否要做memorize计算

    # MemCell存表
    memcell = await _save_memcell_to_database(memcell, current_time)
    logger.info(f"[mem_memorize] 成功保存 MemCell: {memcell.event_id}")

    # 获取当前 request_id
    from core.context.context import get_current_app_info

    app_info = get_current_app_info()
    request_id = app_info.get('request_id')

    # 直接执行记忆提取（阻塞/异步逻辑由 middleware 层面的 request_process 控制）
    try:
        await process_memory_extraction(memcell, request, memory_manager, current_time)
        logger.info(f"[mem_memorize] ✅ 记忆提取完成, request_id={request_id}")
        return request_id
    except Exception as e:
        logger.error(f"[mem_memorize] ❌ 记忆提取失败: {e}")
        traceback.print_exc()
        return None


def get_version_from_request(request: MemorizeOfflineRequest) -> str:
    # 1. 获取 memorize_to 日期
    target_date = request.memorize_to

    # 2. 倒退一天
    previous_day = target_date - timedelta(days=1)

    # 3. 格式化为 "YYYY-MM" 字符串
    return previous_day.strftime("%Y-%m")
