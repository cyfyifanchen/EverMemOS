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



from infra_layer.adapters.out.persistence.document.memory.memcell import (
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
        from infra_layer.adapters.out.persistence.document.memory.memcell import (
            MemCell as DocMemCell,
            DataTypeEnum,
        )
        from common_utils.datetime_utils import (
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


# ============================================================================
# 高级检索功能（BM25 + 混合检索 + Agentic 检索）
# ============================================================================


def build_bm25_index(candidates: List[DocMemCell]):
    """构建 BM25 索引
    
    Args:
        candidates: 候选 MemCell 列表
    
    Returns:
        (bm25_index, tokenized_docs, stemmer, stop_words)
    """
    try:
        import nltk
        from nltk.corpus import stopwords
        from nltk.stem import PorterStemmer
        from nltk.tokenize import word_tokenize
        from rank_bm25 import BM25Okapi
    except ImportError as e:
        print(f"[BM25] ❌ 缺少依赖库: {e}")
        print("[BM25] 提示: 请安装 nltk 和 rank_bm25")
        print("  pip install nltk rank_bm25")
        return None, None, None, None
    
    # 确保 NLTK 数据已下载
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
    
    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)
    
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)
    
    stemmer = PorterStemmer()
    stop_words = set(stopwords.words("english"))
    
    # 提取文本并分词
    tokenized_docs = []
    for mem in candidates:
        # 优先使用 episode，回退到 summary
        text = getattr(mem, "episode", None) or getattr(mem, "summary", "") or ""
        tokens = word_tokenize(text.lower())
        processed_tokens = [
            stemmer.stem(token)
            for token in tokens
            if token.isalpha() and len(token) >= 2 and token not in stop_words
        ]
        tokenized_docs.append(processed_tokens)
    
    # 构建 BM25 索引
    bm25 = BM25Okapi(tokenized_docs)
    
    return bm25, tokenized_docs, stemmer, stop_words


async def search_with_bm25(
    query: str,
    bm25,
    candidates: List[DocMemCell],
    stemmer,
    stop_words,
    top_k: int = 50
) -> List[tuple]:
    """使用 BM25 索引执行检索
    
    Args:
        query: 查询文本
        bm25: BM25 索引
        candidates: 候选 MemCell 列表
        stemmer: 词干提取器
        stop_words: 停用词集合
        top_k: 返回结果数量
    
    Returns:
        [(MemCell, score), ...] 排序后的结果列表
    """
    if bm25 is None:
        return []
    
    try:
        from nltk.tokenize import word_tokenize
    except ImportError:
        return []
    
    # 分词查询
    tokens = word_tokenize(query.lower())
    tokenized_query = [
        stemmer.stem(token)
        for token in tokens
        if token.isalpha() and len(token) >= 2 and token not in stop_words
    ]
    
    if not tokenized_query:
        return []
    
    # 计算 BM25 分数
    scores = bm25.get_scores(tokenized_query)
    
    # 排序并返回 Top-K
    results = sorted(
        zip(candidates, scores),
        key=lambda x: x[1],
        reverse=True
    )[:top_k]
    
    return results


def reciprocal_rank_fusion(
    results1: List[tuple],
    results2: List[tuple],
    k: int = 60
) -> List[tuple]:
    """RRF 融合两个检索结果
    
    使用 Reciprocal Rank Fusion (RRF) 算法融合两个检索结果。
    RRF 公式: score = sum(1 / (k + rank))
    
    Args:
        results1: 第一个检索结果 [(doc, score), ...]
        results2: 第二个检索结果 [(doc, score), ...]
        k: RRF 参数（默认 60）
    
    Returns:
        融合后的结果 [(doc, rrf_score), ...]
    """
    doc_rrf_scores = {}  # {doc_id: rrf_score}
    doc_map = {}         # {doc_id: doc}
    
    # 处理第一个结果集
    for rank, (doc, score) in enumerate(results1, start=1):
        doc_id = id(doc)
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
        doc_rrf_scores[doc_id] = doc_rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    
    # 处理第二个结果集
    for rank, (doc, score) in enumerate(results2, start=1):
        doc_id = id(doc)
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
        doc_rrf_scores[doc_id] = doc_rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    
    # 按 RRF 分数排序
    sorted_docs = sorted(doc_rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    # 转换回 (doc, score) 格式
    fused_results = [(doc_map[doc_id], rrf_score) for doc_id, rrf_score in sorted_docs]
    
    return fused_results


async def lightweight_retrieval(
    query: str,
    candidates: List[DocMemCell],
    embedding_config: EmbeddingConfig,
    emb_top_n: int = 50,
    bm25_top_n: int = 50,
    final_top_n: int = 20
) -> tuple:
    """轻量级检索（Embedding + BM25 + RRF 融合）
    
    流程：
    1. 并行执行 Embedding 和 BM25 检索
    2. 各取 Top-N 候选
    3. 使用 RRF 融合
    4. 返回 Top-K 结果
    
    Args:
        query: 用户查询
        candidates: 候选 MemCell 列表
        embedding_config: 嵌入模型配置
        emb_top_n: Embedding 检索数量
        bm25_top_n: BM25 检索数量
        final_top_n: 最终返回数量
    
    Returns:
        (results, metadata)
    """
    import time
    start_time = time.time()
    
    metadata = {
        "retrieval_mode": "lightweight",
        "emb_count": 0,
        "bm25_count": 0,
        "final_count": 0,
        "total_latency_ms": 0.0,
    }
    
    if not candidates:
        metadata["total_latency_ms"] = (time.time() - start_time) * 1000
        return [], metadata
    
    # 构建 BM25 索引
    bm25, tokenized_docs, stemmer, stop_words = build_bm25_index(candidates)
    
    # 并行执行 Embedding 和 BM25 检索
    vectorize_service = get_vectorize_service()
    
    # Embedding 检索
    emb_results = []
    try:
        query_vec = await vectorize_service.get_embedding(query)
        query_norm = np.linalg.norm(query_vec)
        
        if query_norm > 0:
            scores = []
            for mem in candidates:
                try:
                    doc_vec = np.array(mem.extend.get("embedding", []))
                    if len(doc_vec) > 0:
                        doc_norm = np.linalg.norm(doc_vec)
                        if doc_norm > 0:
                            sim = np.dot(query_vec, doc_vec) / (query_norm * doc_norm)
                            scores.append((mem, float(sim)))
                except:
                    continue
            
            emb_results = sorted(scores, key=lambda x: x[1], reverse=True)[:emb_top_n]
    except Exception as e:
        print(f"[Embedding] ⚠️ 检索失败: {e}")
    
    metadata["emb_count"] = len(emb_results)
    
    # BM25 检索
    bm25_results = []
    if bm25 is not None:
        bm25_results = await search_with_bm25(
            query, bm25, candidates, stemmer, stop_words, top_k=bm25_top_n
        )
    
    metadata["bm25_count"] = len(bm25_results)
    
    # RRF 融合
    if not emb_results and not bm25_results:
        metadata["total_latency_ms"] = (time.time() - start_time) * 1000
        return [], metadata
    elif not emb_results:
        final_results = bm25_results[:final_top_n]
    elif not bm25_results:
        final_results = emb_results[:final_top_n]
    else:
        fused_results = reciprocal_rank_fusion(emb_results, bm25_results, k=60)
        final_results = fused_results[:final_top_n]
    
    metadata["final_count"] = len(final_results)
    metadata["total_latency_ms"] = (time.time() - start_time) * 1000
    
    return final_results, metadata


async def agentic_retrieval(
    query: str,
    candidates: List[DocMemCell],
    embedding_config: EmbeddingConfig,
    llm_provider,
    config,
) -> tuple:
    """Agentic 多轮检索（LLM 引导）
    
    流程：
    1. Round 1: 轻量级检索 Top 20
    2. LLM 判断充分性（使用前 5 条）
    3. 如果不充分：生成改进查询 → Round 2 → 合并
    4. 返回最终结果
    
    Args:
        query: 用户查询
        candidates: 候选 MemCell 列表
        embedding_config: 嵌入模型配置
        llm_provider: LLM 提供者
        config: 配置对象
    
    Returns:
        (results, metadata)
    """
    import time
    start_time = time.time()
    
    metadata = {
        "retrieval_mode": "agentic",
        "is_multi_round": False,
        "round1_count": 0,
        "round2_count": 0,
        "is_sufficient": None,
        "reasoning": None,
        "final_count": 0,
        "total_latency_ms": 0.0,
    }
    
    if not candidates:
        metadata["total_latency_ms"] = (time.time() - start_time) * 1000
        return [], metadata
    
    # ========== Round 1: 轻量级检索 ==========
    round1_results, round1_meta = await lightweight_retrieval(
        query=query,
        candidates=candidates,
        embedding_config=embedding_config,
        emb_top_n=50,
        bm25_top_n=50,
        final_top_n=20
    )
    
    metadata["round1_count"] = len(round1_results)
    
    if not round1_results:
        metadata["total_latency_ms"] = (time.time() - start_time) * 1000
        return [], metadata
    
    # ========== LLM 充分性检查（使用前 5 条）==========
    top5_for_check = round1_results[:5]
    
    try:
        is_sufficient, reasoning = await check_sufficiency_simple(
            query=query,
            results=top5_for_check,
            llm_provider=llm_provider
        )
        
        metadata["is_sufficient"] = is_sufficient
        metadata["reasoning"] = reasoning
        
        # 如果充分，直接返回 Round 1 结果
        if is_sufficient:
            metadata["final_count"] = len(round1_results)
            metadata["total_latency_ms"] = (time.time() - start_time) * 1000
            return round1_results, metadata
    
    except Exception as e:
        print(f"[Agentic] ⚠️ LLM 充分性检查失败: {e}，回退到 Round 1 结果")
        metadata["final_count"] = len(round1_results)
        metadata["total_latency_ms"] = (time.time() - start_time) * 1000
        return round1_results, metadata
    
    # ========== Round 2: 生成改进查询并重新检索 ==========
    metadata["is_multi_round"] = True
    
    try:
        refined_query = await generate_refined_query_simple(
            original_query=query,
            results=top5_for_check,
            llm_provider=llm_provider
        )
        
        metadata["refined_query"] = refined_query
        
        # 使用改进查询进行第二轮检索
        round2_results, round2_meta = await lightweight_retrieval(
            query=refined_query,
            candidates=candidates,
            embedding_config=embedding_config,
            emb_top_n=50,
            bm25_top_n=50,
            final_top_n=20
        )
        
        metadata["round2_count"] = len(round2_results)
        
        # 合并两轮结果（去重）
        round1_ids = {id(doc) for doc, _ in round1_results}
        round2_unique = [(doc, score) for doc, score in round2_results if id(doc) not in round1_ids]
        
        # Round1 Top20 + Round2 去重后的文档（最多 40 个）
        combined_results = round1_results.copy()
        needed_from_round2 = 40 - len(combined_results)
        combined_results.extend(round2_unique[:needed_from_round2])
        
        # 取前 20 个作为最终结果
        final_results = combined_results[:20]
        
        metadata["final_count"] = len(final_results)
        metadata["total_latency_ms"] = (time.time() - start_time) * 1000
        
        return final_results, metadata
    
    except Exception as e:
        print(f"[Agentic] ⚠️ Round 2 失败: {e}，回退到 Round 1 结果")
        metadata["final_count"] = len(round1_results)
        metadata["total_latency_ms"] = (time.time() - start_time) * 1000
        return round1_results, metadata


async def check_sufficiency_simple(
    query: str,
    results: List[tuple],
    llm_provider
) -> tuple:
    """简化版充分性检查
    
    Args:
        query: 用户查询
        results: 检索结果 [(MemCell, score), ...]
        llm_provider: LLM 提供者
    
    Returns:
        (is_sufficient, reasoning)
    """
    # 构建提示词
    memories_text = []
    for i, (mem, score) in enumerate(results, start=1):
        episode = getattr(mem, "episode", None) or getattr(mem, "summary", "")
        memories_text.append(f"[{i}] {episode}")
    
    memories_str = "\n".join(memories_text)
    
    prompt = f"""Given a user query and retrieved memories, determine if the memories are sufficient to answer the query.

User Query: {query}

Retrieved Memories:
{memories_str}

Task: Analyze if these memories contain enough information to answer the query.
- If YES: Return "SUFFICIENT" and briefly explain why
- If NO: Return "INSUFFICIENT" and briefly explain what's missing

Output format (JSON):
{{
  "is_sufficient": true/false,
  "reasoning": "brief explanation"
}}"""
    
    try:
        # 调用 LLM
        response = await llm_provider.generate(prompt)
        
        # 解析 JSON 响应
        import json
        import re
        
        # 尝试提取 JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            is_sufficient = result.get("is_sufficient", False)
            reasoning = result.get("reasoning", "")
            return is_sufficient, reasoning
        else:
            # 回退：简单判断
            if "sufficient" in response.lower():
                return True, "Memories appear sufficient"
            else:
                return False, "Memories appear insufficient"
    
    except Exception as e:
        print(f"[LLM] ⚠️ 充分性检查异常: {e}")
        # 默认认为充分（保守策略）
        return True, "Sufficiency check failed, assuming sufficient"


async def generate_refined_query_simple(
    original_query: str,
    results: List[tuple],
    llm_provider
) -> str:
    """简化版查询改进
    
    Args:
        original_query: 原始查询
        results: 检索结果 [(MemCell, score), ...]
        llm_provider: LLM 提供者
    
    Returns:
        改进后的查询
    """
    # 构建提示词
    memories_text = []
    for i, (mem, score) in enumerate(results, start=1):
        episode = getattr(mem, "episode", None) or getattr(mem, "summary", "")
        memories_text.append(f"[{i}] {episode}")
    
    memories_str = "\n".join(memories_text)
    
    prompt = f"""Given a user query and insufficient retrieved memories, generate an improved query to find more relevant information.

Original Query: {original_query}

Retrieved Memories (insufficient):
{memories_str}

Task: Generate a better query that might retrieve more relevant memories.
- Focus on missing aspects
- Use synonyms or related terms
- Be more specific or more general as needed

Output format (JSON):
{{
  "refined_query": "your improved query here"
}}"""
    
    try:
        # 调用 LLM
        response = await llm_provider.generate(prompt)
        
        # 解析 JSON 响应
        import json
        import re
        
        # 尝试提取 JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            refined_query = result.get("refined_query", original_query)
            return refined_query
        else:
            # 回退：返回原始查询
            return original_query
    
    except Exception as e:
        print(f"[LLM] ⚠️ 查询改进异常: {e}")
        # 默认返回原始查询
        return original_query
