# Demo - EverMemOS Interactive Examples

[English](README.md) | [简体中文](README_zh.md)

This directory contains interactive demos showcasing the core functionality of EverMemOS.

## 🌏 Multi-language Support

The system supports **Chinese and English** language modes with fully automatic binding:

| Config | Data File | Output Directory |
|--------|-----------|------------------|
| `language="zh"` | `data/group_chat_zh.json` | `memcell_outputs/group_chat_zh/` |
| `language="en"` | `data/group_chat_en.json` | `memcell_outputs/group_chat_en/` |

**Core Mechanism**:
- Set the `language` parameter in `extract_memory.py` (`"zh"` or `"en"`)
- System automatically matches corresponding data files and output directories
- Select the same language during chat to properly load memories and profiles

> 💡 **Tip**: Extraction and chat languages must match, otherwise Profile files won't be found

## 📂 Contents

### Core Demo Scripts

- **`extract_memory.py`** - Memory extraction from conversation data
  - Processes conversation files from the `data/` directory
  - Extracts MemCells and generates user profiles
  - Saves results to configured database (MongoDB) and local outputs

- **`chat_with_memory.py`** - Interactive chat with memory-enhanced AI
  - Command-line interface for conversing with AI agents
  - Leverages extracted memories for context-aware responses
  - Demonstrates end-to-end memory retrieval and usage

### Configuration Files

- **`memory_config.py`** - Memory system configuration
- **`memory_utils.py`** - Utility functions for memory operations
- **`i18n_texts.py`** - Internationalization text resources

### Output Directory

- **`chat_history/`** - Saved chat conversation logs
- **`memcell_outputs/`** - Extracted MemCell outputs (auto-generated)

## 🚀 Quick Start

### Step 1: Configure Language and Scenario

#### Option A: Use Sample Data (Recommended for Beginners)

Edit `extract_memory.py` and use the default configuration:

```python
# 💡 Use sample data (default):
EXTRACT_CONFIG = ExtractModeConfig(
    scenario_type=ScenarioType.GROUP_CHAT,  # Scenario: GROUP_CHAT or ASSISTANT
    language="zh",  # 🌏 Language: zh (Chinese) or en (English)
    enable_profile_extraction=True,
)
```

The system will automatically use the corresponding sample data file (e.g., `data/group_chat_zh.json`).

#### Option B: Use Custom Data

If you have your own conversation data, follow these steps:

**1. Prepare Data File**

Create a JSON file following our data format. For format details, refer to:
- [Group Chat Format Specification](../data_format/group_chat/group_chat_format.md)
- Files in [Sample Data](../data/) as reference

**2. Modify Configuration**

Uncomment and modify the custom data configuration in `extract_memory.py`:

```python
# 💡 Use custom data:
EXTRACT_CONFIG = ExtractModeConfig(
    scenario_type=ScenarioType.GROUP_CHAT,
    language="zh",
    data_file=Path("/path/to/your/data.json"),  # 🔧 Specify your data file path
    output_dir=Path(__file__).parent / "memcell_outputs",  # 🔧 Output directory (optional)
    group_id="my_custom_group",  # 🔧 Group ID (optional)
    group_name="My Custom Group",  # 🔧 Group name (optional)
    enable_profile_extraction=True,
)
```

> 💡 **Tip**: Use absolute or relative path to specify your data file location.

### Step 2: Extract Memories

Run the extraction script to extract memories from conversation data:

```bash
cd demo
python extract_memory.py
# Or with uv: uv run python src/bootstrap.py demo/extract_memory.py
```

The system will automatically:
- Read the corresponding data file (e.g., `data/group_chat_zh.json`)
- Extract MemCells
- Generate user Profiles
- Save to MongoDB and local directory (e.g., `memcell_outputs/group_chat_zh/`)

### Step 3: Start Conversation

Run the chat script to start conversing with AI:

```bash
cd demo
python chat_with_memory.py
# Or with uv: uv run python src/bootstrap.py demo/chat_with_memory.py
```

**Interactive Selection**:
1. **Language**: Choose `[1] 中文` or `[2] English` (should match Step 1 config)
2. **Scenario**: Choose `[1] Assistant Mode` or `[2] Group Chat Mode`

**Chat Features**:
- 💬 Natural language conversation with memory-based context
- 🔍 Automatic retrieval of relevant memories (shows retrieval results)
- 📝 Auto-save conversation history
- 🧠 View reasoning process (type `reasoning`)

### 💡 Example Use Cases

#### Case 1: Chinese Group Chat (Default, Recommended for Beginners)

```python
# extract_memory.py - No modification needed, use default config
scenario_type=ScenarioType.GROUP_CHAT,
language="zh",
```

Run extraction → Start chat → Select `[1] 中文` + `[2] Group Chat Mode`

**Try asking**: "What did Alex do in the emotion recognition project?"

#### Case 2: English Assistant

```python
# extract_memory.py - Modify config
scenario_type=ScenarioType.ASSISTANT,
language="en",
```

Run extraction → Start chat → Select `[2] English` + `[1] Assistant Mode`

**Try asking**: "What foods might I like?"

## 📁 Data Files and Output Directories

### Data Files (Auto-binding)

The system automatically selects the corresponding data file based on configuration:

| Scenario | Language | Data File |
|----------|----------|-----------|
| Group Chat | Chinese | `data/group_chat_zh.json` |
| Group Chat | English | `data/group_chat_en.json` |
| Assistant | Chinese | `data/assistant_chat_zh.json` |
| Assistant | English | `data/assistant_chat_en.json` |

All data files follow the [GroupChatFormat](../data_format/group_chat/group_chat_format.md) specification. See [data documentation](../data/README.md) for details.

### Output Directories (Auto-created)

Extracted files are saved under `memcell_outputs/`:

```
demo/memcell_outputs/
├── group_chat_zh/          # Chinese Group Chat
│   ├── profiles/           # User Profiles
│   │   ├── profile_user_101.json
│   │   └── ...
│   └── memcell_*.json      # MemCells
├── group_chat_en/          # English Group Chat
├── assistant_zh/           # Chinese Assistant
│   └── profiles_companion/ # Companion Profiles
└── assistant_en/           # English Assistant
```

## 💬 Chat Commands

During chat sessions, the following commands are supported:

- **Normal Input**: Type questions directly, AI will answer based on memories
- `help` - Show help information
- `reasoning` - View complete reasoning process of last response
- `clear` - Clear current conversation history
- `reload` - Reload memories and profiles
- `exit` - Save conversation history and exit
- `Ctrl+C` - Interrupt and save

## ⚙️ Configuration

### Quick Configuration (Recommended)

Simply modify two parameters in `extract_memory.py`:

```python
EXTRACT_CONFIG = ExtractModeConfig(
    scenario_type=ScenarioType.GROUP_CHAT,  # Scenario type
    language="zh",                          # Language mode
)
```

### Advanced Configuration

Edit `memory_config.py` to customize:
- **LLM Config**: Model selection, API Key, temperature
- **Embedding Config**: Vectorization service URL and model
- **MongoDB Config**: Database connection settings
- **Extraction Parameters**: Batch size, concurrency, performance optimization
- **Chat Parameters**: History window size, retrieval count, display options

### Environment Variables

Create a `.env` file in the project root (refer to `env.template`):

```bash
# LLM Configuration
LLM_MODEL=your_model
LLM_API_KEY=your_api_key
LLM_BASE_URL=your_base_url

# Embedding Model Configuration
EMB_BASE_URL=http://localhost:11000/v1/embeddings
EMB_MODEL=Qwen3-Embedding-4B

# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/memsys
```

## 🔗 Related Documentation

- [Group Chat Format Specification](../data_format/group_chat/group_chat_format.md)
- [API Documentation](../docs/api_docs/agentic_v3_api.md)
- [Data Documentation](../data/README.md)
- [Internationalization Guide](../docs/dev_docs/chat_i18n_usage.md)

## 📖 Demo Data Overview

### Group Chat Scenario (group_chat_en.json / group_chat_zh.json)

**Project Context:** AI product work group documenting the complete development journey of "Smart Sales Assistant"

**Key Contents:**
- MVP development phase: RAG-based Q&A system
- Advanced feature iteration: Emotion recognition, memory system
- Team collaboration practices: Complete workflow from requirements to delivery

**Available in:** English and Chinese versions

**Good for exploring:** Team collaboration patterns, project management, technical solution evolution

### Assistant Scenario (assistant_chat_en.json / assistant_chat_zh.json)

**Conversation Context:** Personal health & lifestyle assistant documenting nearly 2 months of continuous interaction

**Key Contents:**
- Travel planning: Food recommendations, itinerary suggestions
- Health management: Weight monitoring, dietary guidance
- Exercise recovery: Training advice, post-injury rehabilitation

**Available in:** English and Chinese versions

**Good for exploring:** Personalized services, long-term memory accumulation, contextual understanding

## ❓ Recommended Questions

**Group Chat AI Scenario Examples:**
- What did Alex/Betty/... do in the emotion recognition project?
- Based on the emotion recognition project, what work capabilities does Alex/Betty/... demonstrate?
- What are the deliverable results of the emotion recognition project?
- How is the memory system project progressing?

**Assistant AI Scenario Examples:**
- Please recommend sports suitable for me.
- Please recommend food I might like.
- How is my health condition?


## 🔗 Related Documentation

- 📋 [Group Chat Format Specification](../data_format/group_chat/group_chat_format.md) - Data file format
- 🔌 [API Documentation](../docs/api_docs/agentic_v3_api.md) - API reference
- 📦 [Data Documentation](../data/README.md) - Sample data details
- 🏠 [Project Home](../README.md) - Project overview and architecture
- 📘 [Batch Memorization Guide](../docs/dev_docs/run_memorize_usage.md) - Advanced usage

## ❓ FAQ

### Q: Can't find Profile files?
**A**: Ensure the `language` parameter used during extraction matches the language selected during chat. For example: extraction with `language="zh"` → chat with `[1] 中文`

### Q: How to switch languages?
**A**: Modify the `language` parameter in `extract_memory.py`, re-run the extraction script, then select the corresponding language during chat.

### Q: What scenarios are supported?
**A**: Two scenarios are supported:
- **Group Chat Mode (GROUP_CHAT)**: Multi-person conversations, extracts group memories and user profiles
- **Assistant Mode (ASSISTANT)**: One-on-one conversations, extracts personalized companion profiles

### Q: What's the data file format?
**A**: JSON format following the [GroupChatFormat](../data_format/group_chat/group_chat_format.md) specification. We provide 4 example files for reference.

### Q: How to use my own data?
**A**: Three simple steps:
1. Prepare your JSON data file following the [Data Format Specification](../data_format/group_chat/group_chat_format.md)
2. Uncomment the "Use custom data" configuration section in `extract_memory.py`
3. Modify the `data_file` parameter to point to your data file path

### Q: What format is required for custom data?
**A**: Basic requirements:
- JSON format file
- Contains `conversation_list` array, or is directly a message array
- Each message must include at least: `sender_name` (sender), `content` (content), `create_time` (timestamp)
- Detailed specification: [GroupChatFormat](../data_format/group_chat/group_chat_format.md)

## 💡 Need Help?

- 🏠 See the main [README](../README.md) for project setup and architecture
- 💬 Open an issue on GitHub
- 📧 Contact project maintainers

---

**Happy exploring! 🧠✨**

