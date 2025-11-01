"""共享配置模块 - 用于记忆提取和对话系统

本模块定义了所有配置类，供 extract_memory.py 和 chat_with_memory.py 共同使用。

配置类：
- ScenarioType: 场景类型枚举
- RunMode: 运行模式枚举（用于提取脚本）
- LLMConfig: LLM 配置
- EmbeddingConfig: 嵌入模型配置
- MongoDBConfig: MongoDB 配置
- ExtractModeConfig: 提取模式配置
- ChatModeConfig: 对话模式配置
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from typing import Optional, Set


class ScenarioType(Enum):
    """场景类型枚举"""

    ASSISTANT = "assistant"  # 助手场景：单人对话
    GROUP_CHAT = "group_chat"  # 群聊场景：多人对话


class RunMode(Enum):
    """运行模式枚举（用于提取脚本）"""

    EXTRACT_ALL = "extract_all"  # 完整提取：MemCell + Profile
    EXTRACT_MEMCELL_ONLY = "extract_memcell"  # 仅提取 MemCell
    EXTRACT_PROFILE_ONLY = "extract_profile"  # 仅提取 Profile（从已有 MemCell）

    # 向后兼容
    EXTRACT = "extract_all"


@dataclass
class LLMConfig:
    """LLM 配置

    用于配置大语言模型的参数，包括模型选择、API 配置和生成参数。
    """

    provider: str = "openai"
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 16384

    def __post_init__(self):
        """从环境变量加载配置"""
        self.model = self.model or os.getenv("LLM_MODEL")
        self.api_key = self.api_key or os.getenv("LLM_API_KEY")
        self.base_url = self.base_url or os.getenv("LLM_BASE_URL")


@dataclass
class EmbeddingConfig:
    """嵌入模型配置

    用于配置向量嵌入服务的参数。
    """

    base_url: Optional[str] = None
    model: Optional[str] = None

    def __post_init__(self):
        """从环境变量加载配置"""
        self.base_url = (
            self.base_url
            or os.getenv("EMB_BASE_URL")
            or "http://0.0.0.0:11000/v1/embeddings"
        )
        self.model = self.model or os.getenv("EMB_MODEL") or "Qwen3-Embedding-4B"


@dataclass
class MongoDBConfig:
    """MongoDB 配置

    用于配置 MongoDB 数据库连接参数。
    """

    uri: Optional[str] = None
    host: str = "localhost"
    port: str = "27017"
    database: str = "memsys"
    username: Optional[str] = None
    password: Optional[str] = None

    def __post_init__(self):
        """从环境变量加载配置并构建 URI"""
        if not os.getenv("MONGODB_URI"):
            self.host = os.getenv("MONGODB_HOST", self.host)
            self.port = os.getenv("MONGODB_PORT", self.port)
            self.database = os.getenv("MONGODB_DATABASE", self.database)
            self.username = os.getenv("MONGODB_USERNAME")
            self.password = os.getenv("MONGODB_PASSWORD")

            if self.username and self.password:
                from urllib.parse import quote_plus

                self.uri = f"mongodb://{quote_plus(self.username)}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.database}"
            else:
                self.uri = f"mongodb://{self.host}:{self.port}/{self.database}"
        else:
            self.uri = os.getenv("MONGODB_URI")
            self.database = os.getenv("MONGODB_DATABASE", self.database)


@dataclass
class ExtractModeConfig:
    """提取模式配置

    用于配置记忆提取脚本的参数，包括数据源、输出路径、处理策略等。
    """

    # 场景类型（决定使用哪种 Profile 提取器和数据文件）
    scenario_type: ScenarioType = ScenarioType.GROUP_CHAT
    # scenario_type: ScenarioType = ScenarioType.ASSISTANT

    # 🌏 语言模式（决定数据文件和输出目录的语言后缀）
    language: str = "zh"  # "zh" 或 "en"

    # 数据文件路径（自动根据场景类型和语言绑定，也可手动覆盖）
    data_file: Optional[Path] = None

    # 输出目录
    output_dir: Path = field(
        default_factory=lambda: Path(__file__).parent / "memcell_outputs"
    )

    # 群组 ID（用于标识对话来源）
    group_id: str = "ai_group"

    # 群组名称（可选，用于 Profile 提取）
    group_name: Optional[str] = None

    # 支持的消息类型（text/image/file/audio/video/link/system 等字符串类型）
    supported_msg_types: Optional[Set[str]] = None

    # 历史消息窗口大小（控制内存使用）
    history_window_size: int = 20

    # Profile 提取配置
    profile_extract_batch_size: int = 10  # 每积累 N 个 MemCell 触发一次 Profile 提取
    enable_profile_extraction: bool = True  # 是否启用 Profile 提取

    # 🎯 Profile 提取优化配置（解决 MemCell 数量过多导致的问题）
    max_memcells_per_profile_batch: int = (
        50  # 单次 Profile 提取最多使用多少个 MemCell（避免超出 LLM token 限制）
    )
    profile_batch_strategy: str = (
        "latest_first"  # 分批策略："latest_first"（最新优先）, "distributed"（均匀分布）, "sequential"（顺序分批）
    )
    enable_token_estimation: bool = True  # 启用 Token 预估（提供警告）
    max_estimated_tokens: int = 100000  # Token 预估上限（超出时强制分批）

    # MemCell 来源配置（仅在 EXTRACT_PROFILE_ONLY 模式下使用）
    memcell_source: str = "file"  # "file": 从 JSON 文件加载, "mongodb": 从 MongoDB 加载
    memcell_input_dir: Optional[Path] = None  # MemCell 输入目录（用于 file 模式）

    # 并行处理配置
    max_concurrent_profiles: int = 4  # Profile 提取的最大并发数
    max_concurrent_memcells: int = 8  # MemCell 提取的最大并发数

    # 🚀 性能优化配置
    mongo_batch_size: int = 20  # MongoDB 批量写入大小
    embedding_batch_size: int = 32  # 向量化批量大小
    enable_progress_bar: bool = True  # 启用进度条
    enable_performance_metrics: bool = True  # 启用性能指标追踪

    enable_semantic_extraction: Optional[bool] = None

    def __post_init__(self):
        """初始化配置，自动绑定路径和默认值"""
        if self.supported_msg_types is None:
            # 默认支持常见的群聊消息类型
            self.supported_msg_types = {
                "text",
                "image",
                "file",
                "audio",
                "video",
                "link",
                "system",
            }

        # 🔥 根据场景类型和语言自动绑定数据文件（如果未手动设置）
        if self.data_file is None:
            # 获取项目根目录（demo 的父目录）
            project_root = Path(__file__).parent.parent
            data_dir = project_root / "data"

            # 数据文件格式：{scenario_type}_chat_{language}.json
            if self.scenario_type == ScenarioType.ASSISTANT:
                self.data_file = data_dir / f"assistant_chat_{self.language}.json"
            elif self.scenario_type == ScenarioType.GROUP_CHAT:
                self.data_file = data_dir / f"group_chat_{self.language}.json"

        # 🔥 根据场景类型和语言自动调整输出目录
        # 目录格式：memcell_outputs/{scenario_type}_{language}/
        scenario_name = (
            "assistant" if self.scenario_type == ScenarioType.ASSISTANT else "group_chat"
        )
        self.output_dir = self.output_dir / f"{scenario_name}_{self.language}"
        
        # 根据场景类型设置语义提取选项
        if self.scenario_type == ScenarioType.ASSISTANT:
            self.enable_semantic_extraction = True
        elif self.scenario_type == ScenarioType.GROUP_CHAT:
            self.enable_semantic_extraction = False

        # 根据场景类型自动调整默认配置
        if self.scenario_type == ScenarioType.GROUP_CHAT:
            if self.group_id == "ai_group":
                self.group_id = "group_chat_001"
            if self.group_name is None:
                self.group_name = "Project Discussion Group"
        elif self.scenario_type == ScenarioType.ASSISTANT:
            if self.group_id == "ai_group":
                self.group_id = "assistant"
            if self.group_name is None:
                self.group_name = "Personal Assistant"

        # 设置默认的 MemCell 输入目录
        if self.memcell_input_dir is None:
            self.memcell_input_dir = self.output_dir


@dataclass
class ChatModeConfig:
    """对话模式配置

    用于配置记忆增强对话系统的参数，包括对话历史、记忆检索、显示选项等。
    
    注意：scenario_type 和 language 应该在运行时由用户选择动态设置，
    不建议在配置中硬编码。路径会在 ChatSession 初始化时根据运行时参数动态确定。
    """

    # 对话历史配置
    conversation_history_size: int = 5  # 保留最近 N 轮对话

    # 记忆检索配置
    top_k_memories: int = 20  # 每次检索 N 条记忆
    time_range_days: int = 365  # 记忆检索的时间范围（天）
    retrieval_strategy: str = "vector_similarity"  # 检索策略

    # 显示配置
    show_retrieved_memories: bool = True  # 是否显示检索到的记忆
    show_profile_info: bool = True  # 是否显示使用的 Profile
    verbose_memory_display: bool = False  # 是否详细显示记忆（False=简洁版）
    show_reasoning_metadata: bool = True  # 是否显示推理元数据（置信度、引用等）

    # 路径配置（基础目录）
    chat_history_dir: Path = field(
        default_factory=lambda: Path(__file__).parent / "chat_history"
    )
    memcell_output_dir: Path = field(
        default_factory=lambda: Path(__file__).parent / "memcell_outputs"
    )

    def __post_init__(self):
        """初始化配置，确保目录存在"""
        # 确保对话历史目录存在
        self.chat_history_dir.mkdir(parents=True, exist_ok=True)
        # memcell_output_dir 不在这里调整，由 ChatSession 根据运行时参数动态确定
