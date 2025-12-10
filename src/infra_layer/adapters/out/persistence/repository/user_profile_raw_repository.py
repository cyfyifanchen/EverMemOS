"""
UserProfile native CRUD repository

User profile data access layer based on Beanie ODM.
Provides ProfileStorage compatible interface (duck typing).
"""

from typing import Optional, Dict, Any, List
from core.observation.logger import get_logger
from core.di.decorators import repository
from core.oxm.mongo.base_repository import BaseRepository

from infra_layer.adapters.out.persistence.document.memory.user_profile import (
    UserProfile,
)

logger = get_logger(__name__)


@repository("user_profile_raw_repository", primary=True)
class UserProfileRawRepository(BaseRepository[UserProfile]):
    """
    UserProfile native CRUD repository

    Provides ProfileStorage compatible interfaces:
    - save_profile(user_id, profile, metadata) -> bool
    - get_profile(user_id) -> Optional[Any]
    - get_all_profiles() -> Dict[str, Any]
    - get_profile_history(user_id, limit) -> List[Dict]
    - clear() -> bool
    """

    def __init__(self):
        super().__init__(UserProfile)

    # ==================== ProfileStorage interface implementation ====================

    async def save_profile(
        self, user_id: str, profile: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        metadata = metadata or {}
        group_id = metadata.get("group_id", "default")

        if hasattr(profile, 'to_dict'):
            profile_data = profile.to_dict()
        elif isinstance(profile, dict):
            profile_data = profile
        else:
            profile_data = {"data": str(profile)}

        result = await self.upsert(user_id, group_id, profile_data, metadata)
        return result is not None

    async def get_profile(
        self, user_id: str, group_id: str = "default"
    ) -> Optional[Any]:
        user_profile = await self.get_by_user_and_group(user_id, group_id)
        if user_profile is None:
            return None
        return user_profile.profile_data

    async def get_all_profiles(self, group_id: str = "default") -> Dict[str, Any]:
        user_profiles = await self.get_all_by_group(group_id)
        return {up.user_id: up.profile_data for up in user_profiles}

    async def get_profile_history(
        self, user_id: str, group_id: str = "default", limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        user_profile = await self.get_by_user_and_group(user_id, group_id)
        if user_profile is None:
            return []

        history = [
            {
                "version": user_profile.version,
                "profile": user_profile.profile_data,
                "confidence": user_profile.confidence,
                "updated_at": user_profile.updated_at,
                "cluster_id": user_profile.last_updated_cluster,
                "memcell_count": user_profile.memcell_count,
            }
        ]
        return history[:limit] if limit else history

    async def clear(self, group_id: Optional[str] = None) -> bool:
        if group_id is None:
            await self.delete_all()
        else:
            await self.delete_by_group(group_id)
        return True

    # ==================== Native CRUD methods ====================

    async def get_by_user_and_group(
        self, user_id: str, group_id: str
    ) -> Optional[UserProfile]:
        try:
            return await self.model.find_one(
                UserProfile.user_id == user_id, UserProfile.group_id == group_id
            )
        except Exception as e:
            logger.error(
                f"Failed to retrieve user profile: user_id={user_id}, group_id={group_id}, error={e}"
            )
            return None

    async def get_all_by_group(self, group_id: str) -> List[UserProfile]:
        try:
            return await self.model.find(UserProfile.group_id == group_id).to_list()
        except Exception as e:
            logger.error(
                f"Failed to retrieve group user profiles: group_id={group_id}, error={e}"
            )
            return []

    async def get_all_by_user(self, user_id: str, limit: int = 40) -> List[UserProfile]:
        try:
            return await self.model.find(
                UserProfile.user_id == user_id
            ).sort([("version", -1)]).limit(limit).to_list()
        except Exception as e:
            logger.error(f"Failed to get user profile: user_id={user_id}, error={e}")
            return []
    
    async def upsert(
        self,
        user_id: str,
        group_id: str,
        profile_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserProfile]:
        try:
            metadata = metadata or {}
            existing = await self.get_by_user_and_group(user_id, group_id)

            if existing:
                existing.profile_data = profile_data
                existing.version += 1
                existing.confidence = metadata.get("confidence", existing.confidence)

                if "cluster_id" in metadata:
                    cluster_id = metadata["cluster_id"]
                    if cluster_id not in existing.cluster_ids:
                        existing.cluster_ids.append(cluster_id)
                    existing.last_updated_cluster = cluster_id

                if "memcell_count" in metadata:
                    existing.memcell_count = metadata["memcell_count"]

                await existing.save()
                logger.debug(
                    f"Updated user profile: user_id={user_id}, group_id={group_id}, version={existing.version}"
                )
                return existing
            else:
                user_profile = UserProfile(
                    user_id=user_id,
                    group_id=group_id,
                    profile_data=profile_data,
                    scenario=metadata.get("scenario", "group_chat"),
                    confidence=metadata.get("confidence", 0.0),
                    version=1,
                    cluster_ids=(
                        [metadata["cluster_id"]] if "cluster_id" in metadata else []
                    ),
                    memcell_count=metadata.get("memcell_count", 0),
                    last_updated_cluster=metadata.get("cluster_id"),
                )
                await user_profile.insert()
                logger.info(
                    f"Created user profile: user_id={user_id}, group_id={group_id}"
                )
                return user_profile
        except Exception as e:
            logger.error(
                f"Failed to save user profile: user_id={user_id}, group_id={group_id}, error={e}"
            )
            return None

    async def delete_by_group(self, group_id: str) -> int:
        try:
            result = await self.model.find(UserProfile.group_id == group_id).delete()
            count = result.deleted_count if result else 0
            logger.info(
                f"Deleted group user profiles: group_id={group_id}, count={count}"
            )
            return count
        except Exception as e:
            logger.error(
                f"Failed to delete group user profiles: group_id={group_id}, error={e}"
            )
            return 0

    async def delete_all(self) -> int:
        try:
            result = await self.model.delete_all()
            count = result.deleted_count if result else 0
            logger.info(f"Deleted all user profiles: {count} items")
            return count
        except Exception as e:
            logger.error(f"Failed to delete all user profiles: {e}")
            return 0
