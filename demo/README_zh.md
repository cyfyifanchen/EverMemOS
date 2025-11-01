# Demo - EverMemOS 交互式示例

[English](README.md) | [简体中文](README_zh.md)

本目录包含展示 EverMemOS 核心功能的交互式演示。

## 🌏 多语言支持

系统支持**中文和英文**两种语言模式，提取和对话流程完全自动绑定：

| 配置 | 数据文件 | 输出目录 |
|-----|---------|---------|
| `language="zh"` | `data/group_chat_zh.json` | `memcell_outputs/group_chat_zh/` |
| `language="en"` | `data/group_chat_en.json` | `memcell_outputs/group_chat_en/` |

**核心机制**：
- 在 `extract_memory.py` 中设置 `language` 参数（`"zh"` 或 `"en"`）
- 系统自动匹配对应的数据文件和输出目录
- 对话时选择相同的语言即可正常加载记忆和画像

> 💡 **提示**：提取和对话的语言必须一致，否则找不到 Profile 文件

## 📂 内容

### 核心演示脚本

- **`extract_memory.py`** - 从对话数据中提取记忆
  - 处理 `data/` 目录中的对话文件
  - 提取记忆单元（MemCells）并生成用户画像
  - 将结果保存到配置的数据库（MongoDB）和本地输出

- **`chat_with_memory.py`** - 与记忆增强 AI 进行交互式对话
  - 用于与 AI 智能体对话的命令行界面
  - 利用提取的记忆进行上下文感知的回应
  - 演示端到端的记忆检索和使用

### 配置文件

- **`memory_config.py`** - 记忆系统配置
- **`memory_utils.py`** - 记忆操作的工具函数

### 输出目录

- **`chat_history/`** - 保存的聊天对话记录（自动生成）
- **`memcell_outputs/`** - 提取的 MemCell 输出（自动生成）

## 🚀 快速开始

### 步骤 1：配置语言和场景

#### 选项 A：使用示例数据（推荐新手）

编辑 `extract_memory.py`，使用默认配置：

```python
# 💡 使用示例数据（默认）：
EXTRACT_CONFIG = ExtractModeConfig(
    scenario_type=ScenarioType.GROUP_CHAT,  # 场景：GROUP_CHAT（群聊）或 ASSISTANT（助手）
    language="zh",  # 🌏 语言：zh（中文）或 en（英文）
    enable_profile_extraction=True,
)
```

系统会自动使用对应的示例数据文件（如 `data/group_chat_zh.json`）。

#### 选项 B：使用自定义数据

如果您有自己的对话数据，请按以下步骤操作：

**1. 准备数据文件**

按照我们的数据格式创建 JSON 文件。格式说明请参考：
- [群聊格式规范](../data_format/group_chat/group_chat_format.md)
- [示例数据](../data/) 中的文件作为参考

**2. 修改配置**

取消注释并修改 `extract_memory.py` 中的自定义数据配置：

```python
# 💡 使用自定义数据：
EXTRACT_CONFIG = ExtractModeConfig(
    scenario_type=ScenarioType.GROUP_CHAT,
    language="zh",
    data_file=Path("/path/to/your/data.json"),  # 🔧 指定您的数据文件路径
    output_dir=Path(__file__).parent / "memcell_outputs",  # 🔧 输出目录（可选）
    group_id="my_custom_group",  # 🔧 群组 ID（可选）
    group_name="My Custom Group",  # 🔧 群组名称（可选）
    enable_profile_extraction=True,
)
```

> 💡 **提示**：使用绝对路径或相对路径指定您的数据文件位置。

### 步骤 2：提取记忆

运行提取脚本从对话数据中提取记忆：

```bash
cd demo
python extract_memory.py
# 或使用 uv: uv run python src/bootstrap.py demo/extract_memory.py
```

系统会自动：
- 读取对应的数据文件（如 `data/group_chat_zh.json`）
- 提取记忆单元（MemCells）
- 生成用户画像（Profiles）
- 保存到 MongoDB 和本地目录（如 `memcell_outputs/group_chat_zh/`）

### 步骤 3：启动对话

运行对话脚本开始与 AI 对话：

```bash
cd demo
python chat_with_memory.py
# 或使用 uv: uv run python src/bootstrap.py demo/chat_with_memory.py
```

**交互选择**：
1. **语言选择**：选择 `[1] 中文` 或 `[2] English`（应与步骤 1 的配置一致）
2. **场景选择**：选择 `[1] 助手模式` 或 `[2] 群聊模式`

**对话功能**：
- 💬 自然语言对话，AI 基于记忆上下文回答
- 🔍 自动检索相关记忆（显示检索结果）
- 📝 对话历史自动保存
- 🧠 查看推理过程（输入 `reasoning`）

### 💡 示例使用场景

#### 场景 1：中文群聊（默认，推荐新手）

```python
# extract_memory.py - 无需修改，使用默认配置
scenario_type=ScenarioType.GROUP_CHAT,
language="zh",
```

运行提取 → 启动对话 → 选择 `[1] 中文` + `[2] 群聊模式`

**试试问**：「Alex 在情绪识别项目中做了什么工作？」

#### 场景 2：英文助手

```python
# extract_memory.py - 修改配置
scenario_type=ScenarioType.ASSISTANT,
language="en",
```

运行提取 → 启动对话 → 选择 `[2] English` + `[1] Assistant Mode`

**Try asking**: "What foods might I like?"

## 📁 数据文件和输出目录

### 数据文件（自动绑定）

系统根据配置自动选择对应的数据文件：

| 场景 | 语言 | 数据文件 |
|-----|------|---------|
| 群聊 | 中文 | `data/group_chat_zh.json` |
| 群聊 | 英文 | `data/group_chat_en.json` |
| 助手 | 中文 | `data/assistant_chat_zh.json` |
| 助手 | 英文 | `data/assistant_chat_en.json` |

所有数据文件遵循 [GroupChatFormat](../data_format/group_chat/group_chat_format.md) 规范。详见[数据说明文档](../data/README_zh.md)。

### 输出目录（自动创建）

提取后的文件保存在 `memcell_outputs/` 下：

```
demo/memcell_outputs/
├── group_chat_zh/          # 中文群聊
│   ├── profiles/           # 用户画像
│   │   ├── profile_user_101.json
│   │   └── ...
│   └── memcell_*.json      # 记忆单元
├── group_chat_en/          # 英文群聊
├── assistant_zh/           # 中文助手
│   └── profiles_companion/ # 陪伴画像
└── assistant_en/           # 英文助手
```

## 💬 对话命令

在对话会话期间，支持以下命令：

- **正常输入**：直接输入问题，AI 会基于记忆回答
- `help` - 显示帮助信息
- `reasoning` - 查看上一次回答的完整推理过程
- `clear` - 清空当前对话历史
- `reload` - 重新加载记忆和画像
- `exit` - 保存对话历史并退出
- `Ctrl+C` - 中断并保存

## ⚙️ 配置说明

### 快速配置（推荐）

只需修改 `extract_memory.py` 中的两个参数：

```python
EXTRACT_CONFIG = ExtractModeConfig(
    scenario_type=ScenarioType.GROUP_CHAT,  # 场景类型
    language="zh",                          # 语言模式
)
```

### 高级配置

编辑 `memory_config.py` 可自定义：
- **LLM 配置**：模型选择、API Key、温度参数
- **嵌入配置**：向量化服务地址和模型
- **MongoDB 配置**：数据库连接设置
- **提取参数**：批量大小、并发数、性能优化选项
- **对话参数**：历史窗口大小、检索数量、显示选项

### 环境变量

在项目根目录创建 `.env` 文件（参考 `env.template`）：

```bash
# LLM 配置
LLM_MODEL=your_model
LLM_API_KEY=your_api_key
LLM_BASE_URL=your_base_url

# 嵌入模型配置
EMB_BASE_URL=http://localhost:11000/v1/embeddings
EMB_MODEL=Qwen3-Embedding-4B

# MongoDB 配置
MONGODB_URI=mongodb://localhost:27017/memsys
```

## 🔗 相关文档

- [群聊格式规范](../data_format/group_chat/group_chat_format.md)
- [API 文档](../docs/api_docs/agentic_v3_api_zh.md)
- [数据说明文档](../data/README_zh.md)
- [国际化使用指南](../docs/dev_docs/chat_i18n_usage.md)

## 📖 演示数据说明

### 群聊场景 (group_chat_en.json / group_chat_zh.json)

**项目背景：** AI 产品工作群，记录团队开发"智能销售助手"的完整历程

**核心内容：**
- MVP 开发阶段：基于 RAG 的问答系统
- 高级功能迭代：情绪识别、记忆系统
- 团队协作实践：从需求到交付的完整流程

**可用语言：** 英文和中文版本

**适合探索：** 团队协作模式、项目管理、技术方案演进

### 助手场景 (assistant_chat_en.json / assistant_chat_zh.json)

**对话背景：** 个人健康与生活助手，记录近 2 个月的连续交互

**核心内容：**
- 旅行规划：美食推荐、行程建议
- 健康管理：体重监测、饮食指导
- 运动康复：训练建议、伤后恢复

**可用语言：** 英文和中文版本

**适合探索：** 个性化服务、长期记忆积累、上下文理解

## ❓ 推荐问题示例

**群聊 AI 场景问题推荐：**
- Alex/Betty/... 在情绪识别项目中做了什么工作？
- 从情绪识别项目中，可以看出 Alex/Betty/... 具备什么样的工作能力？
- 情绪识别项目的交付结果如何？
- 记忆系统项目的进展如何？

**助手 AI 场景问题推荐：**
- 请为我推荐适合我的运动。
- 请为我推荐我可能喜欢的食物。
- 我的健康状况如何？

## 🔗 相关文档

- 📋 [群聊格式规范](../data_format/group_chat/group_chat_format.md) - 数据文件格式说明
- 🔌 [API 文档](../docs/api_docs/agentic_v3_api_zh.md) - API 接口文档
- 📦 [数据说明](../data/README_zh.md) - 示例数据详细说明
- 🏠 [项目主页](../README_zh.md) - 项目概述和架构
- 📘 [批量记忆化使用指南](../docs/dev_docs/run_memorize_usage.md) - 高级用法

## ❓ 常见问题

### Q: 找不到 Profile 文件？
**A**: 确保提取时的 `language` 参数与对话时选择的语言一致。例如：提取用 `language="zh"` → 对话选 `[1] 中文`

### Q: 如何切换语言？
**A**: 修改 `extract_memory.py` 中的 `language` 参数，重新运行提取脚本，然后对话时选择对应语言。

### Q: 支持哪些场景？
**A**: 支持两种场景：
- **群聊模式（GROUP_CHAT）**：多人对话，提取群组记忆和用户画像
- **助手模式（ASSISTANT）**：一对一对话，提取个性化陪伴画像

### Q: 数据文件格式是什么？
**A**: JSON 格式，遵循 [GroupChatFormat](../data_format/group_chat/group_chat_format.md) 规范。我们提供了 4 个示例文件供参考。

### Q: 如何使用自己的数据？
**A**: 三步操作：
1. 按照 [数据格式规范](../data_format/group_chat/group_chat_format.md) 准备您的 JSON 数据文件
2. 在 `extract_memory.py` 中取消注释"使用自定义数据"部分的配置
3. 修改 `data_file` 参数指向您的数据文件路径

### Q: 自定义数据需要什么格式？
**A**: 基本要求：
- JSON 格式文件
- 包含 `conversation_list` 数组，或直接是消息数组
- 每条消息至少包含：`sender_name`（发送者）、`content`（内容）、`create_time`（时间）
- 详细规范请查看 [GroupChatFormat](../data_format/group_chat/group_chat_format.md)

## 💡 需要帮助？

- 🏠 查看主 [README](../README_zh.md) 了解项目设置和架构
- 💬 在 GitHub 上提交问题
- 📧 联系项目维护者

---

**祝您探索愉快！🧠✨**

