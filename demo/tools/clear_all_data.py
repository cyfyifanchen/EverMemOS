"""清空所有记忆数据的工具函数

可以被其他测试脚本导入使用，也可以独立运行
"""


import asyncio
import time
from typing import Dict, Any, List

from pymilvus import utility, Collection

from infra_layer.adapters.out.search.milvus.memory.episodic_memory_collection import (
    EpisodicMemoryCollection,
)
from infra_layer.adapters.out.search.milvus.memory.foresight_collection import (
    ForesightCollection,
)
from infra_layer.adapters.out.search.milvus.memory.event_log_collection import (
    EventLogCollection,
)
from infra_layer.adapters.out.search.elasticsearch.memory.episodic_memory import (
    EpisodicMemoryDoc,
)
from infra_layer.adapters.out.search.elasticsearch.memory.foresight import (
    ForesightDoc,
)
from infra_layer.adapters.out.search.elasticsearch.memory.event_log import EventLogDoc
from core.di import get_bean_by_type
from component.redis_provider import RedisProvider
from component.mongodb_client_factory import MongoDBClientFactory


async def _clear_mongodb(verbose: bool = True) -> Dict[str, Any]:
    """删除 MongoDB 中所有文档，保留集合和索引"""
    result: Dict[str, Any] = {
        "database": None,
        "collections": {},
        "deleted": {},
        "errors": [],
    }
    try:
        mongo_factory = get_bean_by_type(MongoDBClientFactory)
        client_wrapper = await mongo_factory.get_default_client()
        db = client_wrapper.database
        db_name = db.name
        result["database"] = db_name

        collection_names = await db.list_collection_names()
        for coll_name in collection_names:
            if coll_name.startswith("system."):
                continue
            collection = db[coll_name]
            count = await collection.count_documents({})
            if count == 0:
                continue
            delete_result = await collection.delete_many({})
            deleted = delete_result.deleted_count if delete_result else 0
            result["collections"][coll_name] = count
            result["deleted"][coll_name] = deleted

        if verbose:
            total_deleted = sum(result["deleted"].values())
            print(
                f"      ✅ MongoDB '{db_name}': 删除 {total_deleted} 条文档（{len(result['deleted'])} 个集合）"
            )
    except Exception as exc:
        result["errors"].append(str(exc))
        if verbose:
            print(f"      ⚠️  MongoDB 清理失败: {exc}")

    return result


def _get_milvus_row_count(name: str, coll: Collection) -> int:
    """获取 Milvus 实时行数（优先 row_count，其次 segment，再兜底 num_entities）"""
    get_stats = getattr(utility, "get_collection_stats", None)
    if callable(get_stats):
        stats_info = get_stats(name)
        if isinstance(stats_info, dict):
            try:
                return int(stats_info.get("row_count", 0))
            except (ValueError, TypeError):
                pass

    try:
        segment_infos = utility.get_query_segment_info(name)
        if segment_infos:
            total = 0
            for seg in segment_infos:
                seg_rows = getattr(seg, "num_rows", None)
                if seg_rows is None:
                    seg_rows = getattr(seg, "row_count", 0)
                total += int(seg_rows or 0)
            return total
    except Exception:
        pass

    try:
        return int(coll.num_entities)
    except Exception:
        return 0


def _clear_milvus(
    verbose: bool = True, drop_collections: bool = False
) -> Dict[str, Any]:
    """删除 Milvus 集合中的所有向量

    Args:
        verbose: 是否输出日志
        drop_collections: 是否直接删除物理集合并重建（彻底清空）
    """
    stats: Dict[str, Any] = {"cleared": [], "errors": []}
    collection_classes = [
        EpisodicMemoryCollection,
        ForesightCollection,
        EventLogCollection,
    ]
    for cls in collection_classes:
        collection = cls()
        alias = collection.name
        try:
            related_collections: List[str] = []
            all_collections = utility.list_collections(using=collection.using)
            prefix = f"{alias}_"
            for real_name in all_collections:
                if real_name == alias or real_name.startswith(prefix):
                    related_collections.append(real_name)

            if not related_collections:
                continue

            if not drop_collections:
                for real_name in related_collections:
                    coll = Collection(name=real_name, using=collection.using)
                    coll.load()
                    before_count = coll.num_entities
                    if before_count == 0:
                        continue
                    coll.delete(expr="id != ''")
                    coll.flush()

            # 删除 alias，防止 drop collection 时报错
            try:
                utility.drop_alias(alias, using=collection.using)
            except Exception:
                pass

            for real_name in related_collections:
                before_count = 0
                try:
                    coll = Collection(name=real_name, using=collection.using)
                    coll.load()
                    before_count = coll.num_entities
                except Exception:
                    before_count = 0

                utility.drop_collection(real_name, using=collection.using)
                stats["cleared"].append(
                    {"collection": real_name, "deleted": before_count, "dropped": True}
                )
                if verbose:
                    print(
                        f"      ✅ Milvus 删除集合 {real_name}（{before_count} 条向量）"
                    )

            # 清空类级别的 collection 缓存，确保重新创建时不会使用旧的实例
            cls._collection_instance = None

            # 重新创建空集合并关联 alias，避免后续依赖失败
            try:
                collection.ensure_all()
            except Exception as ensure_exc:
                if verbose:
                    print(f"      ⚠️  重新创建 Milvus 集合 {alias} 失败: {ensure_exc}")
        except Exception as exc:  # pylint: disable=broad-except
            stats["errors"].append(str(exc))
            if verbose:
                print(f"      ⚠️  无法清空 Milvus 集合 {alias}: {exc}")

    return stats


async def _clear_elasticsearch(
    verbose: bool = True, rebuild_index: bool = False
) -> Dict[str, Any]:
    """删除与记忆相关的 Elasticsearch 文档，必要时重建索引"""
    stats: Dict[str, Any] = {"cleared": [], "errors": [], "recreated": False}
    try:
        # 获取连接即可，因为已经注册了连接
        es_client = EpisodicMemoryDoc.get_connection()

        alias_names = [
            EpisodicMemoryDoc.get_index_name(),
            ForesightDoc.get_index_name(),
            EventLogDoc.get_index_name(),
        ]

        if rebuild_index:
            for alias in alias_names:
                try:
                    existing = await es_client.indices.get_alias(
                        name=alias, ignore=[404]
                    )
                    if isinstance(existing, dict):
                        for index_name in existing.keys():
                            await es_client.indices.delete(
                                index=index_name, ignore=[400, 404]
                            )
                            stats["cleared"].append(
                                {"alias": alias, "deleted_index": index_name}
                            )
                            if verbose:
                                print(f"      ✅ 删除索引: {index_name}")
                except Exception as inner_exc:
                    stats["errors"].append(str(inner_exc))
                    if verbose:
                        print(f"      ⚠️ 删除索引失败 {alias}: {inner_exc}")
            for alias in alias_names:
                await es_client.indices.delete_alias(
                    index="*", name=alias, ignore=[404]
                )
            # 使用 EsIndexInitializer 重新创建索引
            from core.oxm.es.es_utils import EsIndexInitializer
            initializer = EsIndexInitializer()
            await initializer.initialize_indices(
                [EpisodicMemoryDoc, ForesightDoc, EventLogDoc]
            )
            stats["recreated"] = True
            if verbose:
                print("      ✅ Elasticsearch 索引与别名已重新创建")
            return stats

        for alias in alias_names:
            try:
                exists = await es_client.indices.exists_alias(name=alias)
                if not exists:
                    continue
                count_resp = await es_client.count(index=alias, query={"match_all": {}})
                total_docs = count_resp.get("count", 0)
                if total_docs == 0:
                    continue
                await es_client.delete_by_query(
                    index=alias,
                    query={"match_all": {}},
                    refresh=True,
                    conflicts="proceed",
                )
                stats["cleared"].append({"alias": alias, "deleted": total_docs})
                if verbose:
                    print(f"      ✅ Elasticsearch {alias}: 删除 {total_docs} 条文档")
            except Exception as inner_exc:  # pylint: disable=broad-except
                stats["errors"].append(str(inner_exc))
                if verbose:
                    print(f"      ⚠️  无法清空 ES {alias}: {inner_exc}")

    except Exception as exc:  # pylint: disable=broad-except
        stats["errors"].append(str(exc))
        if verbose:
            print(f"      ⚠️  Elasticsearch 清理失败: {exc}")

    return stats


async def _clear_redis(verbose: bool = True) -> Dict[str, Any]:
    """清空 Redis 当前数据库"""
    stats: Dict[str, Any] = {}
    try:
        redis_provider = get_bean_by_type(RedisProvider)
        client = await redis_provider.get_client()
        await client.flushdb()
        stats["flushed_db"] = redis_provider.redis_db
        if verbose:
            print(f"      ✅ Redis DB {redis_provider.redis_db} 已清空")
    except Exception as exc:  # pylint: disable=broad-except
        stats["error"] = str(exc)
        if verbose:
            print(f"      ⚠️  Redis 清理失败: {exc}")
    return stats


async def clear_all_memories(
    verbose: bool = True, rebuild_es: bool = False, drop_milvus: bool = False
):
    """清空所有记忆数据（MongoDB、Milvus、Elasticsearch、Redis）

    Args:
        verbose: 是否显示详细信息
        rebuild_es: 是否删除并重建 Elasticsearch 索引 (默认: False)
        drop_milvus: 是否删除并重建 Milvus 物理集合 (默认: False)
    """
    if verbose:
        print("\n🗑️  清空所有记忆数据...")

    try:
        if verbose:
            print("   📦 清空 MongoDB...")
        mongo_stats = await _clear_mongodb(verbose)

        if verbose:
            print("   🔍 清空 Milvus...")
        milvus_stats = _clear_milvus(verbose, drop_collections=drop_milvus)

        if verbose:
            print("   🔎 清空 Elasticsearch...")
        es_stats = await _clear_elasticsearch(verbose, rebuild_index=rebuild_es)

        if verbose:
            print("   💾 清空 Redis...")
        redis_stats = await _clear_redis(verbose)

        if verbose:
            print("✅ 所有记忆数据已清空！\n")
            print("📊 简要统计：")
            total_mongo_deleted = sum(mongo_stats.get("deleted", {}).values())
            print(
                f"   - MongoDB 删除文档: {total_mongo_deleted} 条（数据库: {mongo_stats.get('database')}）"
            )
            total_milvus_deleted = sum(
                item["deleted"] for item in milvus_stats.get("cleared", [])
            )
            print(f"   - Milvus 删除向量: {total_milvus_deleted} 条")
            if es_stats.get("recreated"):
                print("   - Elasticsearch: 索引与别名已重新创建")
            else:
                total_es_deleted = sum(
                    item["deleted"] for item in es_stats.get("cleared", [])
                )
                print(f"   - Elasticsearch 删除文档: {total_es_deleted} 条")
            print(f"   - Redis 清空 DB: {redis_stats.get('flushed_db')}")

        return {
            "mongodb": mongo_stats,
            "milvus": milvus_stats,
            "elasticsearch": es_stats,
            "redis": redis_stats,
        }

    except Exception as e:
        print(f"❌ 清空数据时出错: {e}")
        import traceback

        traceback.print_exc()
        raise


async def main():
    """独立运行时的入口函数"""
    print("=" * 100)
    print("🗑️  清空所有记忆数据工具")
    print("=" * 100)

    # 确保 bootstrap 初始化，以便 get_bean_by_type 能正常工作
    import sys
    import os
    from bootstrap import setup_project_context

    # 添加项目根目录到 path
    sys.path.append(os.getcwd())

    await setup_project_context()

    result = await clear_all_memories(verbose=True, rebuild_es=False)

    print("\n📊 清空统计:")
    mongo_total = sum(result["mongodb"].get("deleted", {}).values())
    print(f"   MongoDB 删除文档: {mongo_total} 条")
    milvus_total = sum(item["deleted"] for item in result["milvus"].get("cleared", []))
    print(f"   Milvus 删除向量: {milvus_total} 条")
    if result["elasticsearch"].get("recreated"):
        print("   Elasticsearch: 索引与别名已重新创建")
    else:
        es_total = sum(
            item["deleted"] for item in result["elasticsearch"].get("cleared", [])
        )
        print(f"   Elasticsearch 删除文档: {es_total} 条")
    print(f"   Redis 清空 DB: {result['redis'].get('flushed_db')}")
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
