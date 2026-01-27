#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test GlobalUserProfile functionality

Test contents include:
1. Repository CRUD operations
2. Service layer operations
3. Upsert custom profile functionality (merge logic)
"""

import asyncio

from core.di import get_bean_by_type
from core.observation.logger import get_logger
from infra_layer.adapters.out.persistence.repository.global_user_profile_raw_repository import (
    GlobalUserProfileRawRepository,
)
from service.global_user_profile_service import GlobalUserProfileService

logger = get_logger(__name__)


async def test_repository_basic_crud():
    """Test repository basic CRUD operations"""
    logger.info("Starting test of repository basic CRUD operations...")

    repo = get_bean_by_type(GlobalUserProfileRawRepository)
    user_id = "test_user_001"

    try:
        # First clean up any existing test data
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up existing test data")

        # Test creating a new profile
        result = await repo.upsert(
            user_id=user_id,
            profile_data={"role": "engineer", "skills": ["python", "java"]},
            custom_profile_data=None,
        )
        assert result is not None
        assert result.user_id == user_id
        assert result.profile_data is not None
        assert result.profile_data.get("role") == "engineer"
        # confidence and memcell_count use DB default values
        assert result.confidence == 0.0
        assert result.memcell_count == 0
        logger.info("✅ Successfully created new profile")

        # Test querying by user_id
        queried = await repo.get_by_user_id(user_id)
        assert queried is not None
        assert queried.user_id == user_id
        logger.info("✅ Successfully queried by user_id")

        # Test updating profile
        updated = await repo.upsert(
            user_id=user_id,
            profile_data={
                "role": "senior_engineer",
                "skills": ["python", "java", "go"],
            },
        )
        assert updated is not None
        assert updated.profile_data.get("role") == "senior_engineer"
        logger.info("✅ Successfully updated profile")

        # Test deletion
        deleted_count = await repo.delete_by_user_id(user_id)
        assert deleted_count == 1
        logger.info("✅ Successfully deleted profile")

        # Verify deletion
        final_check = await repo.get_by_user_id(user_id)
        assert final_check is None, "Profile should have been deleted"
        logger.info("✅ Verified deletion success")

    except Exception as e:
        logger.error("❌ Repository basic CRUD test failed: %s", e)
        raise

    logger.info("✅ Repository basic CRUD test completed")


async def test_repository_upsert_custom_profile():
    """Test repository upsert_custom_profile method"""
    logger.info("Starting test of repository upsert_custom_profile...")

    repo = get_bean_by_type(GlobalUserProfileRawRepository)
    user_id = "test_user_002"

    try:
        # First clean up any existing test data
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up existing test data")

        # Test upserting custom profile for new user
        custom_data = {
            "initial_profile": [
                "User is a data scientist",
                "User focuses on machine learning research",
                "User has 5 years of work experience",
            ]
        }

        result = await repo.upsert_custom_profile(
            user_id=user_id, custom_profile_data=custom_data
        )
        assert result is not None
        assert result.user_id == user_id
        assert (
            result.profile_data is None
        )  # profile_data should be None for new custom profiles
        assert result.custom_profile_data is not None
        assert "initial_profile" in result.custom_profile_data
        assert len(result.custom_profile_data["initial_profile"]) == 3
        # confidence and memcell_count use DB default values
        assert result.confidence == 0.0
        assert result.memcell_count == 0
        logger.info("✅ Successfully upserted custom profile for new user")

        # Test updating custom profile
        updated_custom_data = {
            "initial_profile": [
                "User is a senior data scientist",
                "User focuses on deep learning research",
                "User has 8 years of work experience",
                "User works at a big tech company",
            ]
        }

        updated = await repo.upsert_custom_profile(
            user_id=user_id, custom_profile_data=updated_custom_data
        )
        assert updated is not None
        assert len(updated.custom_profile_data["initial_profile"]) == 4
        logger.info("✅ Successfully updated custom profile")

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up test data")

    except Exception as e:
        logger.error("❌ Repository upsert_custom_profile test failed: %s", e)
        raise

    logger.info("✅ Repository upsert_custom_profile test completed")


async def test_service_upsert_custom_profile():
    """Test service layer upsert_custom_profile with merge logic"""
    logger.info("Starting test of service upsert_custom_profile...")

    service = get_bean_by_type(GlobalUserProfileService)
    repo = get_bean_by_type(GlobalUserProfileRawRepository)
    user_id = "test_user_003"

    try:
        # First clean up any existing test data
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up existing test data")

        # Test upserting custom profile via service (new user)
        custom_profile_data = {
            "initial_profile": [
                "User is a product manager",
                "User is skilled at requirements analysis",
                "User has good communication skills",
            ]
        }

        result = await service.upsert_custom_profile(
            user_id=user_id, custom_profile_data=custom_profile_data
        )

        assert result is not None
        assert result["user_id"] == user_id
        assert result["custom_profile_data"] is not None
        assert "initial_profile" in result["custom_profile_data"]
        assert (
            result["custom_profile_data"]["initial_profile"]
            == custom_profile_data["initial_profile"]
        )
        # confidence and memcell_count use DB default values
        assert result["confidence"] == 0.0
        assert result["memcell_count"] == 0
        logger.info("✅ Successfully upserted custom profile via service")

        # Test getting profile via service
        queried = await service.get_by_user_id(user_id)
        assert queried is not None
        assert queried["user_id"] == user_id
        logger.info("✅ Successfully queried profile via service")

        # Test deleting via service
        deleted_count = await service.delete_by_user_id(user_id)
        assert deleted_count == 1
        logger.info("✅ Successfully deleted profile via service")

        # Verify deletion
        final_check = await service.get_by_user_id(user_id)
        assert final_check is None, "Profile should have been deleted"
        logger.info("✅ Verified deletion success via service")

    except Exception as e:
        logger.error("❌ Service upsert_custom_profile test failed: %s", e)
        raise

    logger.info("✅ Service upsert_custom_profile test completed")


async def test_service_merge_logic():
    """Test service layer merge logic for upsert_custom_profile"""
    logger.info("Starting test of service merge logic...")

    service = get_bean_by_type(GlobalUserProfileService)
    repo = get_bean_by_type(GlobalUserProfileRawRepository)
    user_id = "test_user_merge"

    try:
        # First clean up any existing test data
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up existing test data")

        # First upsert - create initial data
        initial_data = {
            "initial_profile": ["Initial description 1", "Initial description 2"],
            "other_field": "should_be_preserved",
        }

        result1 = await service.upsert_custom_profile(
            user_id=user_id, custom_profile_data=initial_data
        )
        assert result1 is not None
        assert result1["custom_profile_data"]["initial_profile"] == [
            "Initial description 1",
            "Initial description 2",
        ]
        assert result1["custom_profile_data"]["other_field"] == "should_be_preserved"
        logger.info("✅ Created initial custom profile")

        # Second upsert - should merge and overwrite initial_profile
        updated_data = {
            "initial_profile": [
                "Updated description 1",
                "Updated description 2",
                "New description 3",
            ]
        }

        result2 = await service.upsert_custom_profile(
            user_id=user_id, custom_profile_data=updated_data
        )
        assert result2 is not None
        # initial_profile should be overwritten
        assert result2["custom_profile_data"]["initial_profile"] == [
            "Updated description 1",
            "Updated description 2",
            "New description 3",
        ]
        # other_field should be preserved (merge logic)
        assert result2["custom_profile_data"]["other_field"] == "should_be_preserved"
        logger.info(
            "✅ Verified merge logic: initial_profile overwritten, other_field preserved"
        )

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up test data")

    except Exception as e:
        logger.error("❌ Service merge logic test failed: %s", e)
        raise

    logger.info("✅ Service merge logic test completed")


async def test_profile_data_can_be_null():
    """Test that profile_data and custom_profile_data can be null"""
    logger.info("Starting test of nullable fields...")

    repo = get_bean_by_type(GlobalUserProfileRawRepository)
    user_id = "test_user_004"

    try:
        # First clean up any existing test data
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up existing test data")

        # Test creating profile with both fields as None
        result = await repo.upsert(
            user_id=user_id, profile_data=None, custom_profile_data=None
        )
        assert result is not None
        assert result.user_id == user_id
        assert result.profile_data is None
        assert result.custom_profile_data is None
        logger.info("✅ Successfully created profile with null fields")

        # Query and verify
        queried = await repo.get_by_user_id(user_id)
        assert queried is not None
        assert queried.profile_data is None
        assert queried.custom_profile_data is None
        logger.info("✅ Successfully queried profile with null fields")

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Cleaned up test data")

    except Exception as e:
        logger.error("❌ Nullable fields test failed: %s", e)
        raise

    logger.info("✅ Nullable fields test completed")


async def run_all_tests():
    """Run all tests"""
    logger.info("🚀 Starting to run all GlobalUserProfile tests...")

    try:
        await test_repository_basic_crud()
        await test_repository_upsert_custom_profile()
        await test_service_upsert_custom_profile()
        await test_service_merge_logic()
        await test_profile_data_can_be_null()
        logger.info("✅ All tests completed successfully!")
    except Exception as e:
        logger.error("❌ Error occurred during testing: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
