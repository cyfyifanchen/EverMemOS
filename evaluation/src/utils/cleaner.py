from __future__ import annotations

from typing import Any, Dict

from bootstrap import setup_project_context
from core.di import get_bean_by_type
from infra_layer.adapters.out.persistence.document.memory.memcell import MemCell
from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
    EpisodicMemory,
)
from infra_layer.adapters.out.persistence.document.memory.event_log_record import (
    EventLogRecord,
)
from infra_layer.adapters.out.persistence.document.memory.foresight_record import (
    ForesightRecord,
)
from infra_layer.adapters.out.persistence.repository.cluster_state_raw_repository import (
    ClusterStateRawRepository,
)
from infra_layer.adapters.out.persistence.repository.conversation_meta_raw_repository import (
    ConversationMetaRawRepository,
)
from infra_layer.adapters.out.persistence.repository.conversation_status_raw_repository import (
    ConversationStatusRawRepository,
)
from infra_layer.adapters.out.persistence.repository.group_profile_raw_repository import (
    GroupProfileRawRepository,
)
from infra_layer.adapters.out.persistence.repository.group_user_profile_memory_raw_repository import (
    GroupUserProfileMemoryRawRepository,
)
from infra_layer.adapters.out.persistence.repository.memory_request_log_repository import (
    MemoryRequestLogRepository,
)
from infra_layer.adapters.out.persistence.repository.user_profile_raw_repository import (
    UserProfileRawRepository,
)
from infra_layer.adapters.out.search.elasticsearch.memory.episodic_memory import (
    EpisodicMemoryDoc,
)
from infra_layer.adapters.out.search.elasticsearch.memory.event_log import EventLogDoc
from infra_layer.adapters.out.search.elasticsearch.memory.foresight import ForesightDoc
from infra_layer.adapters.out.search.repository.episodic_memory_milvus_repository import (
    EpisodicMemoryMilvusRepository,
)
from infra_layer.adapters.out.search.repository.event_log_milvus_repository import (
    EventLogMilvusRepository,
)
from infra_layer.adapters.out.search.repository.foresight_milvus_repository import (
    ForesightMilvusRepository,
)


async def _es_alias_exists(es_client: Any, alias: str) -> bool:
    return await es_client.indices.exists_alias(name=alias)


async def _delete_es_by_group_id(group_id: str) -> Dict[str, int]:
    es_client = EpisodicMemoryDoc.get_connection()
    aliases = [
        EpisodicMemoryDoc.get_index_name(),
        ForesightDoc.get_index_name(),
        EventLogDoc.get_index_name(),
    ]
    deleted: Dict[str, int] = {}
    for alias in aliases:
        if not await _es_alias_exists(es_client, alias):
            continue
        resp = await es_client.delete_by_query(
            index=alias,
            query={"term": {"group_id": group_id}},
            refresh=True,
            conflicts="proceed",
        )
        deleted[alias] = int((resp or {}).get("deleted", 0) or 0)
    return deleted


async def _delete_milvus_by_group_id(group_id: str) -> Dict[str, int]:
    deleted: Dict[str, int] = {}
    deleted["episodic_memory"] = await EpisodicMemoryMilvusRepository().delete_by_filters(
        group_id=group_id
    )
    deleted["foresight"] = await ForesightMilvusRepository().delete_by_filters(
        group_id=group_id
    )
    deleted["event_log"] = await EventLogMilvusRepository().delete_by_filters(
        group_id=group_id
    )
    return deleted


async def clear_group_data_in_context(
    group_id: str, verbose: bool = True
) -> Dict[str, Any]:
    mongo_deleted: Dict[str, int] = {}

    meta_repo = get_bean_by_type(ConversationMetaRawRepository)
    status_repo = get_bean_by_type(ConversationStatusRawRepository)
    group_profile_repo = get_bean_by_type(GroupProfileRawRepository)
    group_user_profile_repo = get_bean_by_type(GroupUserProfileMemoryRawRepository)
    cluster_state_repo = get_bean_by_type(ClusterStateRawRepository)
    reqlog_repo = get_bean_by_type(MemoryRequestLogRepository)
    user_profile_repo = get_bean_by_type(UserProfileRawRepository)

    await meta_repo.delete_by_group_id(group_id)
    await status_repo.delete_by_group_id(group_id)
    await group_profile_repo.delete_by_group_id(group_id)
    mongo_deleted["group_user_profile_memory"] = (
        await group_user_profile_repo.delete_by_group_id(group_id)
    )
    await cluster_state_repo.delete_by_group_id(group_id)
    mongo_deleted["memory_request_logs"] = await reqlog_repo.delete_by_group_id(group_id)
    mongo_deleted["user_profiles"] = await user_profile_repo.delete_by_group(group_id)

    res = await MemCell.find({"group_id": group_id}).delete()
    mongo_deleted["memcells"] = getattr(res, "deleted_count", 0) or 0

    res = await EpisodicMemory.find({"group_id": group_id}).delete()
    mongo_deleted["episodic_memories"] = getattr(res, "deleted_count", 0) or 0

    res = await EventLogRecord.find({"group_id": group_id}).delete()
    mongo_deleted["event_log_records"] = getattr(res, "deleted_count", 0) or 0

    res = await ForesightRecord.find({"group_id": group_id}).delete()
    mongo_deleted["foresight_records"] = getattr(res, "deleted_count", 0) or 0

    es_deleted = await _delete_es_by_group_id(group_id)
    milvus_deleted = await _delete_milvus_by_group_id(group_id)

    if verbose:
        print("\n🧹 Group cleanup finished")
        print(f"   group_id={group_id}")
        print(f"   MongoDB deleted: {mongo_deleted}")
        print(f"   Elasticsearch deleted: {es_deleted}")
        print(f"   Milvus deleted: {milvus_deleted}")

    return {"mongodb": mongo_deleted, "elasticsearch": es_deleted, "milvus": milvus_deleted}


async def clear_group_data(group_id: str, verbose: bool = True) -> Dict[str, Any]:
    await setup_project_context()
    return await clear_group_data_in_context(group_id=group_id, verbose=verbose)
