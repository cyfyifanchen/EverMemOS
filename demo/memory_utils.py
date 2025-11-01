"""共享工具函数模块 - 用于记忆提取和对话系统

本模块提供公共的工具函数，供 extract_memory.py 和 chat_with_memory.py 共同使用。

主要功能：
- MongoDB 连接和初始化
- Profile 加载和管理
- MemCell 查询
- 检索策略（向量相似度）
- 时间序列化工具
- 性能监控和进度追踪（优化版新增）
"""

import json
import os
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from agentic_layer.vectorize_service import get_vectorize_service


import numpy as np
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

# 导入项目中的文档模型
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
src_path = str(PROJECT_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# 确保项目根目录在路径中
project_root = str(PROJECT_ROOT)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.infra_layer.adapters.out.persistence.document.memory.memcell import (
    MemCell as DocMemCell,
)
from demo.memory_config import MongoDBConfig, EmbeddingConfig


def cosine_similarity(vec1, vec2):
    """
    计算两个 numpy 向量的余弦相似度。

    参数:
    vec1 (np.ndarray): 第一个向量。
    vec2 (np.ndarray): 第二个向量。

    返回:
    float: 两个向量的余弦相似度。
    """
    # 计算点积
    dot_product = np.dot(vec1, vec2)

    # 计算两个向量的 L2 范数（即向量的模）
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)

    # 计算余弦相似度
    # 添加一个很小的数 (epsilon) 来防止除以零
    epsilon = 1e-8
    similarity = dot_product / (norm_vec1 * norm_vec2 + epsilon)

    return similarity


# ============================================================================
# 性能监控工具（优化版新增）
# ============================================================================


@dataclass
class PerformanceMetrics:
    """性能指标追踪器

    用于追踪和报告提取过程的性能指标，包括：
    - LLM 调用次数和耗时
    - MongoDB 写入次数和耗时
    - 向量化调用次数和耗时
    - MemCell 和 Profile 数量
    """

    total_start_time: float = 0.0
    memcell_count: int = 0
    profile_count: int = 0
    llm_calls: int = 0
    llm_total_time: float = 0.0
    mongo_writes: int = 0
    mongo_total_time: float = 0.0
    embedding_calls: int = 0
    embedding_total_time: float = 0.0

    def report(self) -> None:
        """生成并打印性能报告"""
        total_time = time.time() - self.total_start_time

        print("\n" + "=" * 80)
        print("⚡ 性能指标报告")
        print("=" * 80)
        print(f"总耗时: {total_time:.2f}秒")

        print(f"\n📊 提取结果:")
        print(f"  - MemCell 数量: {self.memcell_count}")
        print(f"  - Profile 数量: {self.profile_count}")

        print(f"\n🤖 LLM 调用:")
        print(f"  - 总调用次数: {self.llm_calls}")
        print(f"  - 总耗时: {self.llm_total_time:.2f}秒")
        if self.llm_calls > 0:
            print(f"  - 平均耗时: {self.llm_total_time/self.llm_calls:.2f}秒/次")

        print(f"\n💾 MongoDB 写入:")
        print(f"  - 总写入次数: {self.mongo_writes}")
        print(f"  - 总耗时: {self.mongo_total_time:.2f}秒")
        if self.mongo_writes > 0:
            print(f"  - 平均耗时: {self.mongo_total_time/self.mongo_writes:.3f}秒/次")

        print(f"\n🔢 向量化:")
        print(f"  - 总调用次数: {self.embedding_calls}")
        print(f"  - 总耗时: {self.embedding_total_time:.2f}秒")
        if self.embedding_calls > 0:
            print(
                f"  - 平均耗时: {self.embedding_total_time/self.embedding_calls:.3f}秒/次"
            )

        print("=" * 80 + "\n")


class ProgressTracker:
    """进度追踪器

    用于显示实时进度条、处理速度和预计完成时间。
    """

    def __init__(self, total: int, desc: str = "处理中"):
        """初始化进度追踪器

        Args:
            total: 总任务数
            desc: 任务描述
        """
        self.total = total
        self.current = 0
        self.desc = desc
        self.start_time = time.time()
        self.last_update = 0

    def update(self, n: int = 1) -> None:
        """更新进度

        Args:
            n: 本次完成的任务数
        """
        self.current += n
        current_time = time.time()

        # 每 0.5 秒或完成时更新显示
        if current_time - self.last_update > 0.5 or self.current >= self.total:
            elapsed = current_time - self.start_time
            rate = self.current / elapsed if elapsed > 0 else 0
            eta = (self.total - self.current) / rate if rate > 0 else 0

            pct = 100.0 * self.current / self.total if self.total > 0 else 0
            bar_len = 40
            filled = int(bar_len * self.current / self.total) if self.total > 0 else 0
            bar = '█' * filled + '-' * (bar_len - filled)

            print(
                f'\r{self.desc}: |{bar}| {self.current}/{self.total} [{pct:.1f}%] '
                f'{rate:.1f}it/s ETA: {eta:.0f}s',
                end='',
                flush=True,
            )

            self.last_update = current_time

            if self.current >= self.total:
                print()  # 完成后换行


# ============================================================================
# 批量 MongoDB 写入器（优化版新增）
# ============================================================================


class BatchMongoWriter:
    """批量 MongoDB 写入器

    使用缓冲区批量写入 MongoDB，减少数据库 IO 次数，提高性能。
    """

    def __init__(
        self, batch_size: int = 20, perf_metrics: Optional[PerformanceMetrics] = None
    ):
        """初始化批量写入器

        Args:
            batch_size: 批次大小
            perf_metrics: 性能指标追踪器（可选）
        """
        self.batch_size = batch_size
        self.buffer: List = []
        self.lock = asyncio.Lock()
        self.perf_metrics = perf_metrics

    async def add(self, memcell) -> None:
        """添加 MemCell 到缓冲区

        Args:
            memcell: MemCell 对象
        """
        async with self.lock:
            doc = self._create_doc(memcell)
            self.buffer.append(doc)

            # 达到批次大小时自动刷新
            if len(self.buffer) >= self.batch_size:
                await self._flush()

    async def flush(self) -> None:
        """公开的刷新接口"""
        async with self.lock:
            await self._flush()

    async def _flush(self) -> None:
        """内部刷新逻辑（无锁）"""
        if not self.buffer:
            return

        start_time = time.time()
        try:
            # 导入文档模型
            from src.infra_layer.adapters.out.persistence.document.memory.memcell import (
                MemCell as DocMemCell,
            )

            # 批量插入
            await DocMemCell.insert_many(self.buffer)

            elapsed = time.time() - start_time

            # 更新性能指标
            if self.perf_metrics:
                self.perf_metrics.mongo_writes += len(self.buffer)
                self.perf_metrics.mongo_total_time += elapsed

            print(
                f"[MongoDB] 批量写入 {len(self.buffer)} 个MemCell，耗时 {elapsed:.2f}秒"
            )
            self.buffer.clear()

        except Exception as e:
            print(f"[MongoDB] ❌ 批量写入失败: {e}")
            self.buffer.clear()

    def _create_doc(self, memcell):
        """创建 MongoDB 文档对象

        Args:
            memcell: MemCell 对象

        Returns:
            DocMemCell 文档对象
        """
        from src.infra_layer.adapters.out.persistence.document.memory.memcell import (
            MemCell as DocMemCell,
            DataTypeEnum,
        )
        from src.common_utils.datetime_utils import (
            from_iso_format,
            get_now_with_timezone,
        )

        # 解析时间戳
        ts = memcell.timestamp
        if isinstance(ts, str):
            ts_dt = from_iso_format(ts)
        elif isinstance(ts, (int, float)):
            tz = get_now_with_timezone().tzinfo
            ts_dt = datetime.fromtimestamp(float(ts), tz=tz)
        else:
            ts_dt = ts or get_now_with_timezone()

        # 获取主用户 ID
        primary_user = (
            memcell.user_id_list[0]
            if getattr(memcell, 'user_id_list', None)
            else "default"
        )

        return DocMemCell(
            user_id=primary_user,
            timestamp=ts_dt,
            summary=memcell.summary or "",
            group_id=getattr(memcell, 'group_id', None),
            participants=getattr(memcell, 'participants', None),
            type=DataTypeEnum.CONVERSATION,
            subject=getattr(memcell, 'subject', None),
            keywords=getattr(memcell, 'keywords', None),
            linked_entities=getattr(memcell, 'linked_entities', None),
            episode=getattr(memcell, 'episode', None),
            semantic_memories=getattr(memcell, 'semantic_memories', None),
            extend=getattr(memcell, 'extend', None),
        )


# ============================================================================
# MongoDB 相关工具
# ============================================================================


async def ensure_mongo_beanie_ready(mongo_config: MongoDBConfig) -> None:
    """初始化 MongoDB 和 Beanie 连接

    Args:
        mongo_config: MongoDB 配置对象

    Raises:
        Exception: 如果连接失败
    """
    # 设置环境变量供 Beanie 使用
    os.environ["MONGODB_URI"] = mongo_config.uri

    # 创建 MongoDB 客户端并测试连接
    client = AsyncIOMotorClient(mongo_config.uri)
    try:
        await client.admin.command('ping')
        print(f"[MongoDB] ✅ 连接成功: {mongo_config.database}")
    except Exception as e:
        print(f"[MongoDB] ❌ 连接失败: {e}")
        raise

    # 初始化 Beanie 文档模型
    await init_beanie(
        database=client[mongo_config.database], document_models=[DocMemCell]
    )


async def query_all_groups_from_mongodb() -> List[Dict[str, Any]]:
    """查询所有群组 ID 及其记忆数量

    使用聚合管道统计每个群组的 MemCell 数量。

    Returns:
        群组列表，格式：[{"group_id": "xxx", "memcell_count": 76}, ...]
    """
    # 使用聚合管道统计每个群组的记忆数量
    pipeline = [
        {"$match": {"group_id": {"$ne": None}}},  # 过滤掉没有 group_id 的记录
        {"$group": {"_id": "$group_id", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},  # 按 group_id 排序
    ]

    # 获取 PyMongo/Motor 集合进行聚合查询
    # get_pymongo_collection() 在 Beanie 中返回 Motor 集合（异步）
    collection = DocMemCell.get_pymongo_collection()
    cursor = collection.aggregate(pipeline)
    results = await cursor.to_list(length=None)

    groups = []
    for result in results:
        groups.append({"group_id": result["_id"], "memcell_count": result["count"]})

    return groups


async def query_memcells_by_group_and_time(
    group_id: str, start_date: datetime, end_date: datetime
) -> List[DocMemCell]:
    """按群组和时间范围查询 MemCell

    Args:
        group_id: 群组 ID
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        MemCell 文档对象列表
    """
    memcells = (
        await DocMemCell.find(
            {"group_id": group_id, "timestamp": {"$gte": start_date, "$lt": end_date}}
        )
        .sort("timestamp")
        .to_list()
    )

    return memcells


# ============================================================================
# Profile 相关工具
# ============================================================================


def load_user_profiles_from_dir(output_dir: Path) -> Dict[str, Dict[str, Any]]:
    """加载目录中所有用户的个人 Profile

    从指定目录加载所有 profile_user_*.json 文件。

    Args:
        output_dir: Profile 文件所在目录

    Returns:
        用户 Profile 字典，格式：{"user_101": {...}, "user_102": {...}, ...}
    """
    profiles = {}

    # 查找所有 profile_user_*.json 文件
    for profile_file in output_dir.glob("profile_user_*.json"):
        try:
            with profile_file.open("r", encoding="utf-8") as fp:
                profile_data = json.load(fp)

                # 从文件名提取 user_id
                # 例如：profile_user_101.json -> user_101
                user_id = profile_file.stem.replace("profile_", "")
                profiles[user_id] = profile_data

        except Exception as e:
            print(f"[Profile] ⚠️ 加载失败 {profile_file.name}: {e}")
            continue

    return profiles


def get_user_name_from_profile(profile: Dict[str, Any]) -> Optional[str]:
    """从 Profile 中提取用户名称

    Args:
        profile: Profile 数据字典

    Returns:
        用户名称，如果不存在返回 None
    """
    # 尝试从不同字段提取用户名
    return profile.get("user_name") or profile.get("name") or profile.get("subject")


def get_group_name_from_profiles(profiles: Dict[str, Dict]) -> Optional[str]:
    """从 Profile 中提取群组名称（如果有）

    Args:
        profiles: 用户 Profile 字典

    Returns:
        群组名称，如果不存在返回 None
    """
    for profile in profiles.values():
        group_name = profile.get("group_name")
        if group_name:
            return group_name
    return None


# ============================================================================
# 检索策略
# ============================================================================


class RetrievalStrategy:
    """检索策略基类

    用于扩展不同的检索方法（向量相似度、BM25、混合检索等）。
    """

    def __init__(self, embedding_config: EmbeddingConfig):
        """初始化检索策略

        Args:
            embedding_config: 嵌入模型配置
        """
        self.embedding_config = embedding_config
        self.vectorize_service = get_vectorize_service()

    async def retrieve(
        self, query: str, candidates: List[DocMemCell], top_k: int
    ) -> List[Dict[str, Any]]:
        """执行检索

        Args:
            query: 查询字符串
            candidates: 候选 MemCell 列表
            top_k: 返回结果数量

        Returns:
            排序后的检索结果列表
        """
        raise NotImplementedError("子类必须实现 retrieve 方法")


class VectorSimilarityStrategy(RetrievalStrategy):
    """基于向量相似度的检索策略

    使用余弦相似度对候选 MemCell 进行排序。
    """

    async def retrieve(
        self, query: str, candidates: List[DocMemCell], top_k: int
    ) -> List[Dict[str, Any]]:
        """使用向量相似度进行检索

        Args:
            query: 查询字符串
            candidates: 候选 MemCell 列表
            top_k: 返回结果数量

        Returns:
            排序后的检索结果列表
        """
        if not candidates:
            return []

        # 获取查询的嵌入向量
        # q_vec = self._embed_texts_http([query])
        q_vec = await self.vectorize_service.get_embedding(query)
        # if not q_vec:
        #     print("[VectorSimilarity] ❌ 查询向量嵌入失败")
        #     return []

        # 获取文档的嵌入向量
        # q = np.array(q_vec[0], dtype=np.float32)
        # doc_vecs = self._embed_texts_http(texts)
        doc_episode_vecs = []
        for candidate in candidates:
            try:
                doc_episode_vecs.append(candidate.extend["embedding"])
            except:
                doc_episode_vecs.append([0 for _ in range(1024)])

        if len(doc_episode_vecs) != len(candidates):
            print(
                f"[VectorSimilarity] ⚠️ 嵌入向量数量不匹配: {len(doc_episode_vecs)} != {len(candidates)}"
            )
            return []

        # 计算余弦相似度
        scores: List[float] = []
        for v in doc_episode_vecs:
            dv = np.array(v)

            score = cosine_similarity(q_vec, dv)
            # print(score)
            scores.append(score)

        # 排序并返回 Top-K
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)[
            :top_k
        ]

        # 构建结果列表
        results: List[Dict[str, Any]] = []
        for m, s in ranked:
            item = {
                "event_id": str(getattr(m, "event_id", getattr(m, "id", ""))),
                "timestamp": (
                    getattr(m, "timestamp", None).isoformat()
                    if getattr(m, "timestamp", None)
                    else None
                ),
                "group_id": getattr(m, "group_id", None),
                "subject": getattr(m, "subject", None),
                "summary": getattr(m, "summary", None),
                "episode": getattr(m, "episode", None),
                "participants": getattr(m, "participants", []),
                "score": round(s, 4),
            }
            results.append(item)

        return results

    async def retrieve_semantic(
        self, query: str, candidates: List[DocMemCell], date_query: datetime, top_k: int
    ) -> List[Dict[str, Any]]:
        """使用语义相似度进行检索

        Args:
            query: 查询字符串
            candidates: 候选 MemCell 列表
            date_query: 日期查询条件
            top_k: 返回结果数量
        """
        # 获取查询的嵌入向量
        # q_vec = self._embed_texts_http([query])
        q_vec = await self.vectorize_service.get_embedding(query)

        # 规范化 date_query，移除时区信息以便比较
        # 这样可以兼容 offset-naive 和 offset-aware 的 datetime
        date_query_naive = (
            date_query.replace(tzinfo=None) if date_query.tzinfo else date_query
        )

        doc_semantic_memories_vecs = []
        candidate_filtered = []
        for candidate in candidates:
            # 🔥 检查 semantic_memories 是否为 None
            if not candidate.semantic_memories:
                continue
            
            semantic_memories_vecs = []
            for semantic_memory in candidate.semantic_memories:
                # 获取 end_time 并规范化为 naive datetime 以便比较
                end_time = semantic_memory['end_time']

                # 兼容多种数据格式：字符串或datetime对象
                if isinstance(end_time, str):
                    # 字符串格式，解析为 datetime
                    try:
                        end_time_dt = datetime.strptime(end_time, "%Y-%m-%d")
                    except ValueError:
                        # 尝试解析带时区的ISO格式
                        try:
                            end_time_dt = datetime.fromisoformat(end_time)
                            # 移除时区信息
                            end_time_dt = end_time_dt.replace(tzinfo=None)
                        except ValueError:
                            # 如果解析失败，跳过此记忆
                            continue
                elif isinstance(end_time, datetime):
                    # 已经是 datetime 对象，移除时区信息
                    end_time_dt = (
                        end_time.replace(tzinfo=None) if end_time.tzinfo else end_time
                    )
                else:
                    # 不支持的类型，跳过
                    continue

                # 比较日期（都是 naive datetime）
                if end_time_dt < date_query_naive:
                    continue
                semantic_memories_vecs.append(semantic_memory["embedding"])
            if len(semantic_memories_vecs) == 0:
                continue
            else:
                doc_semantic_memories_vecs.append(semantic_memories_vecs)
                candidate_filtered.append(candidate)

        # 计算余弦相似度
        scores: List[float] = []
        for v in doc_semantic_memories_vecs:
            max_score = 0
            for semantic_memory_vec in v:
                score = cosine_similarity(q_vec, np.array(semantic_memory_vec))
                if score > max_score:
                    max_score = score
            scores.append(float(max_score))
        # 排序并返回 Top-K
        ranked = sorted(
            zip(candidate_filtered, scores), key=lambda x: x[1], reverse=True
        )[:top_k]

        # 构建结果列表
        results: List[Dict[str, Any]] = []
        for m, s in ranked:
            item = {
                "event_id": str(getattr(m, "event_id", getattr(m, "id", ""))),
                "timestamp": (
                    getattr(m, "timestamp", None).isoformat()
                    if getattr(m, "timestamp", None)
                    else None
                ),
                "group_id": getattr(m, "group_id", None),
                "subject": getattr(m, "subject", None),
                "summary": getattr(m, "summary", None),
                "episode": getattr(m, "episode", None),
                "participants": getattr(m, "participants", []),
                "score": round(s, 4),
            }
            results.append(item)

        return results

    def _embed_texts_http(self, texts: List[str]) -> List[np.ndarray]:
        """通过 HTTP 调用嵌入服务

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        try:
            resp = requests.post(
                self.embedding_config.base_url,
                json={"input": texts, "model": self.embedding_config.model},
                timeout=30,  # 30秒超时
            ).json()

            vecs = [
                np.array(item.get("embedding", []), dtype=np.float32)
                for item in resp.get("data", [])
            ]
            return vecs

        except requests.exceptions.Timeout:
            print(f"[Embedding] ❌ 请求超时")
            return []
        except requests.exceptions.RequestException as e:
            print(f"[Embedding] ❌ 请求失败: {e}")
            return []
        except Exception as e:
            print(f"[Embedding] ❌ 未知错误: {e}")
            return []


# ============================================================================
# 时间序列化工具
# ============================================================================


def serialize_datetime(obj: Any) -> Any:
    """递归序列化 datetime 对象为 ISO 格式字符串

    Args:
        obj: 要序列化的对象（可以是任意类型）

    Returns:
        序列化后的对象
    """
    # 如果已经是字符串，直接返回（避免处理已序列化的时间戳）
    if isinstance(obj, str):
        return obj
    # datetime 对象转为 ISO 字符串
    elif isinstance(obj, datetime):
        return obj.isoformat()
    # 递归处理字典
    elif isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    # 递归处理列表
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    # 处理对象（转换 __dict__）
    elif hasattr(obj, '__dict__'):
        return serialize_datetime(obj.__dict__)
    # 其他类型直接返回
    else:
        return obj
