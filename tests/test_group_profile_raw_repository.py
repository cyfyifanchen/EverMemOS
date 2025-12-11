#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test version management functionality of GroupProfileRawRepository

Test contents include:
1. CRUD operations based on group_id (with version management support)
2. Version management related features
3. ensure_latest method testing
4. only_latest functionality testing for batch queries
"""

import asyncio
from datetime import datetime

from common_utils.datetime_utils import get_now_with_timezone
from core.di import get_bean_by_type
from infra_layer.adapters.out.persistence.repository.group_profile_raw_repository import (
    GroupProfileRawRepository,
)
from core.observation.logger import get_logger

logger = get_logger(__name__)


async def test_basic_crud_operations():
    """Test basic CRUD operations (with version management)"""
    logger.info("Starting test of basic CRUD operations...")

    repo = get_bean_by_type(GroupProfileRawRepository)
    group_id = "test_group_001"
    current_timestamp = int(get_now_with_timezone().timestamp() * 1000)

    try:
        # First clean up any existing test data
        await repo.delete_by_group_id(group_id)
        logger.info("✅ Cleaned up existing test data")

        # Test creating a new record (version must be provided)
        group_data = {
            "version": "v1",
            "group_name": "Technical Discussion Group",
            "subject": "Technical Exchange and Learning",
            "summary": "This group mainly discusses various technical topics to promote technical communication",
        }

        result = await repo.upsert_by_group_id(group_id, group_data, current_timestamp)
        assert result is not None
        assert result.group_id == group_id
        assert result.group_name == "Technical Discussion Group"
        assert result.version == "v1"
        assert result.is_latest == True
        assert result.timestamp == current_timestamp
        logger.info(
            "✅ Successfully tested creating new record (version=v1, is_latest=True)"
        )

        # Test querying by group_id (should return the latest version)
        queried = await repo.get_by_group_id(group_id)
        assert queried is not None
        assert queried.group_id == group_id
        assert queried.version == "v1"
        assert queried.is_latest == True
        logger.info("✅ Successfully tested querying by group_id")

        # Test updating record (without changing version)
        update_data = {
            "group_name": "Advanced Technical Discussion Group",
            "summary": "Updated group description",
        }

        updated = await repo.update_by_group_id(group_id, update_data)
        assert updated is not None
        assert updated.group_name == "Advanced Technical Discussion Group"
        assert updated.summary == "Updated group description"
        assert updated.version == "v1"  # Version unchanged
        assert (
            updated.subject == "Technical Exchange and Learning"
        )  # Unupdated fields should retain original values
        logger.info("✅ Successfully tested updating record (version unchanged)")

        # Test deleting a specific version
        deleted = await repo.delete_by_group_id(group_id, version="v1")
        assert deleted is True
        logger.info("✅ Successfully tested deleting specific version")

        # Verify deletion
        final_check = await repo.get_by_group_id(group_id)
        assert final_check is None, "Record should have been deleted"
        logger.info("✅ Verified deletion success")

    except Exception as e:
        logger.error("❌ Basic CRUD operations test failed: %s", e)
        raise

    logger.info("✅ Basic CRUD operations test completed")


async def test_version_management():
    """Test version management functionality"""
    logger.info("Starting test of version management functionality...")

    repo = get_bean_by_type(GroupProfileRawRepository)
    group_id = "test_group_version_002"
    current_timestamp = int(get_now_with_timezone().timestamp() * 1000)

    try:
        # First clean up any existing test data
        await repo.delete_by_group_id(group_id)
        logger.info("✅ Cleaned up existing test data")

        # Create first version
        v1_data = {
            "version": "202501",
            "group_name": "Tech Group v1",
            "subject": "Initial version",
        }

        v1_result = await repo.upsert_by_group_id(group_id, v1_data, current_timestamp)
        assert v1_result is not None
        assert v1_result.version == "202501"
        assert v1_result.is_latest == True
        logger.info("✅ Created version 202501 successfully, is_latest=True")

        # Create second version
        v2_data = {
            "version": "202502",
            "group_name": "Tech Group v2",
            "subject": "Second version",
        }

        v2_result = await repo.upsert_by_group_id(group_id, v2_data, current_timestamp)
        assert v2_result is not None
        assert v2_result.version == "202502"
        assert v2_result.is_latest == True
        logger.info("✅ Created version 202502 successfully, is_latest=True")

        # Create third version
        v3_data = {
            "version": "202503",
            "group_name": "Tech Group v3",
            "subject": "Third version",
        }

        v3_result = await repo.upsert_by_group_id(group_id, v3_data, current_timestamp)
        assert v3_result is not None
        assert v3_result.version == "202503"
        assert v3_result.is_latest == True
        logger.info("✅ Created version 202503 successfully, is_latest=True")

        # Test getting latest version (without specifying version_range)
        latest = await repo.get_by_group_id(group_id)
        assert latest is not None
        assert latest.version == "202503"
        assert latest.is_latest == True
        logger.info("✅ Successfully retrieved latest version: version=202503")

        # Test version range query (closed interval, returns latest version within range)
        v2_by_range = await repo.get_by_group_id(
            group_id, version_range=("202502", "202502")
        )
        assert v2_by_range is not None
        assert v2_by_range.version == "202502"
        logger.info(
            "✅ Version range query [202502, 202502] succeeded, returned version=202502"
        )

        # Test multi-version range query (returns latest version within range)
        v_multi_range = await repo.get_by_group_id(
            group_id, version_range=("202501", "202502")
        )
        assert v_multi_range is not None
        assert (
            v_multi_range.version == "202502"
        )  # Returns the latest version within the range
        logger.info(
            "✅ Version range query [202501, 202502] succeeded, returned latest version 202502"
        )

        # Test updating a specific version
        update_v2 = {"subject": "Updated second version"}

        updated_v2 = await repo.update_by_group_id(
            group_id, update_v2, version="202502"
        )
        assert updated_v2 is not None
        assert updated_v2.version == "202502"
        assert updated_v2.subject == "Updated second version"
        logger.info("✅ Successfully updated specific version 202502")

        # Test deleting a middle version
        await repo.delete_by_group_id(group_id, version="202502")
        logger.info("✅ Deleted version 202502 successfully")

        # Verify latest version remains correct after deletion
        latest_after_delete = await repo.get_by_group_id(group_id)
        assert latest_after_delete is not None
        assert latest_after_delete.version == "202503"
        assert latest_after_delete.is_latest == True
        logger.info("✅ After deleting middle version, latest version is still correct")

        # Clean up all versions
        await repo.delete_by_group_id(group_id)
        logger.info("✅ Cleaned up test data successfully")

    except Exception as e:
        logger.error("❌ Version management test failed: %s", e)
        raise

    logger.info("✅ Version management functionality test completed")


async def test_ensure_latest():
    """Test ensure_latest method"""
    logger.info("Starting test of ensure_latest method...")

    repo = get_bean_by_type(GroupProfileRawRepository)
    group_id = "test_group_ensure_003"
    current_timestamp = int(get_now_with_timezone().timestamp() * 1000)

    try:
        # First clean up any existing test data
        await repo.delete_by_group_id(group_id)
        logger.info("✅ Cleaned up existing test data")

        # Create multiple versions
        versions = ["202501", "202502", "202503", "202504"]
        for version in versions:
            data = {
                "version": version,
                "group_name": f"Tech Group {version}",
                "subject": f"Version {version}",
            }
            await repo.upsert_by_group_id(group_id, data, current_timestamp)

        logger.info("✅ Created 4 versions")

        # Manually call ensure_latest
        result = await repo.ensure_latest(group_id)
        assert result is True
        logger.info("✅ ensure_latest executed successfully")

        # Verify latest version
        latest = await repo.get_by_group_id(group_id)
        assert latest is not None
        assert latest.version == "202504"
        assert latest.is_latest == True
        logger.info(
            "✅ Verified latest version is correct: version=202504, is_latest=True"
        )

        # Verify is_latest is False for old versions
        for old_version in ["202501", "202502", "202503"]:
            # Use same start and end version to precisely query a single version
            old_doc = await repo.get_by_group_id(
                group_id, version_range=(old_version, old_version)
            )
            assert old_doc is not None
            assert old_doc.is_latest == False
            logger.info("✅ Verified old version %s has is_latest=False", old_version)

        # Test idempotency: call ensure_latest again
        result2 = await repo.ensure_latest(group_id)
        assert result2 is True
        logger.info("✅ ensure_latest idempotency verified successfully")

        # Clean up test data
        await repo.delete_by_group_id(group_id)
        logger.info("✅ Cleaned up test data successfully")

    except Exception as e:
        logger.error("❌ ensure_latest method test failed: %s", e)
        raise

    logger.info("✅ ensure_latest method test completed")


async def test_batch_query_with_only_latest():
    """Test only_latest functionality in batch query"""
    logger.info("Starting test of only_latest functionality in batch query...")

    repo = get_bean_by_type(GroupProfileRawRepository)
    base_group_id = "test_batch_group"
    current_timestamp = int(get_now_with_timezone().timestamp() * 1000)

    try:
        # Create multiple groups, each with multiple versions
        group_ids = [f"{base_group_id}_{i}" for i in range(1, 4)]

        # First clean up
        for gid in group_ids:
            await repo.delete_by_group_id(gid)
        logger.info("✅ Cleaned up existing test data")

        # Create multiple versions for each group
        for gid in group_ids:
            for version in ["202501", "202502", "202503"]:
                data = {
                    "version": version,
                    "group_name": f"{gid}_{version}",
                    "subject": f"Group {gid} version {version}",
                }
                await repo.upsert_by_group_id(gid, data, current_timestamp)

        logger.info("✅ Created 3 groups, each with 3 versions")

        # Test only_latest=True (default)
        latest_results = await repo.find_by_group_ids(group_ids, only_latest=True)
        assert len(latest_results) == 3

        for result in latest_results:
            assert result.version == "202503"
            assert result.is_latest == True

        logger.info(
            "✅ Batch query with only_latest=True succeeded, returned 3 latest versions"
        )

        # Test only_latest=False (return all versions)
        all_results = await repo.find_by_group_ids(group_ids, only_latest=False)
        assert len(all_results) == 9  # 3 groups * 3 versions
        logger.info(
            "✅ Batch query with only_latest=False succeeded, returned 9 versions"
        )

        # Clean up test data
        for gid in group_ids:
            await repo.delete_by_group_id(gid)
        logger.info("✅ Cleaned up test data successfully")

    except Exception as e:
        logger.error("❌ Batch query only_latest functionality test failed: %s", e)
        raise

    logger.info("✅ Batch query only_latest functionality test completed")


async def test_create_without_version_should_fail():
    """Test that creating without providing version should fail"""
    logger.info("Starting test that creating without version should fail...")

    repo = get_bean_by_type(GroupProfileRawRepository)
    group_id = "test_no_version_004"
    current_timestamp = int(get_now_with_timezone().timestamp() * 1000)

    try:
        # First clean up
        await repo.delete_by_group_id(group_id)

        # Try to create a record without version
        data_without_version = {
            "group_name": "No Version Group",
            "subject": "This should fail",
        }

        try:
            await repo.upsert_by_group_id(
                group_id, data_without_version, current_timestamp
            )
            assert False, "Creating a record without version should raise an exception"
        except ValueError as e:
            logger.info("✅ Correctly raised ValueError: %s", str(e))
            assert "Version field must be provided" in str(e)

        logger.info("✅ Creating without version correctly failed")

    except AssertionError:
        raise
    except Exception as e:
        logger.error("❌ Test creating without version failed: %s", e)
        raise

    logger.info("✅ Test creating without version completed")


async def run_all_tests():
    """Run all tests"""
    logger.info("🚀 Starting to run all GroupProfile tests...")

    try:
        await test_basic_crud_operations()
        await test_version_management()
        await test_ensure_latest()
        await test_batch_query_with_only_latest()
        await test_create_without_version_should_fail()
        logger.info("✅ All tests completed")
    except Exception as e:
        logger.error("❌ Error occurred during testing: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
