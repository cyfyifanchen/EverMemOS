# Chat with Memory HTTP API 迁移说明

## 📋 概述

本文档说明 `chat_with_memory.py` 从 **Python SDK 直接调用** 迁移到 **HTTP API 调用** 的变更内容。

### 迁移日期
2025-11-10

### 迁移原因
- ✅ 与生产环境架构保持一致
- ✅ 统一使用 HTTP API 接口
- ✅ 便于服务独立部署和扩展
- ✅ 提供标准化的 RESTful 接口

---

## 🔄 架构变更

### 变更前（Python SDK）

```
chat_with_memory.py
    ↓
ChatSession
    ↓
MemoryManager (直接调用)
    ↓
retrieve_agentic() / retrieve_lightweight()
```

**特点**：
- 直接函数调用，无网络开销
- 需要在同一进程中运行
- 代码耦合度高

### 变更后（HTTP API）

```
chat_with_memory.py
    ↓
ChatSession
    ↓
HTTP Client (httpx)
    ↓
V3 API Server
    ↓
MemoryManager
    ↓
retrieve_agentic() / retrieve_lightweight()
```

**特点**：
- HTTP 调用，有网络开销
- 服务独立运行，可独立扩展
- 标准化接口，解耦

---

## 📝 详细修改内容

### 1. 配置文件修改

#### `demo/memory_config.py`

新增 API 配置字段：

```python
@dataclass
class ChatModeConfig:
    # API 配置
    api_base_url: Optional[str] = None  # V3 API 基础 URL（从环境变量读取）
    
    # ... 其他配置 ...
    
    def __post_init__(self):
        # 从环境变量加载 API 配置
        if self.api_base_url is None:
            self.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8001")
```

**说明**：
- 默认值：`http://localhost:8001`
- 可通过环境变量 `API_BASE_URL` 自定义

---

### 2. 会话管理修改

#### `demo/chat/session.py`

#### 2.1 导入变更

```python
# ❌ 删除
from agentic_layer.memory_manager import MemoryManager

# ✅ 添加
import httpx
```

#### 2.2 初始化变更

```python
class ChatSession:
    def __init__(self, ...):
        # ❌ 删除
        self.memory_manager: Optional[MemoryManager] = None
        
        # ✅ 添加
        self.api_base_url = config.api_base_url
        self.retrieve_lightweight_url = f"{self.api_base_url}/api/v3/agentic/retrieve_lightweight"
        self.retrieve_agentic_url = f"{self.api_base_url}/api/v3/agentic/retrieve_agentic"
```

#### 2.3 健康检查

新增服务器健康检查方法：

```python
async def _check_api_server(self) -> None:
    """检查 API 服务器是否运行
    
    Raises:
        ConnectionError: 如果服务器未运行
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.api_base_url}/docs")
            if response.status_code >= 500:
                raise ConnectionError("API 服务器返回错误")
    except (httpx.ConnectError, httpx.TimeoutException, ConnectionError) as e:
        error_msg = (
            f"\n❌ 无法连接到 API 服务器: {self.api_base_url}\n\n"
            f"请先启动 V3 API 服务器：\n"
            f"  uv run python src/bootstrap.py src/run.py --port 8001\n\n"
            f"然后在另一个终端运行聊天应用。\n"
        )
        raise ConnectionError(error_msg) from e
```

**说明**：
- 在 `initialize()` 时自动调用
- 如果服务器未启动，给出友好的错误提示

#### 2.4 检索方法重写

```python
async def retrieve_memories(self, query: str) -> List[Dict[str, Any]]:
    """检索相关记忆 - 通过 HTTP API 调用"""
    # 根据检索模式选择不同的 HTTP API 端点
    if self.retrieval_mode == "agentic":
        result = await self._call_retrieve_agentic_api(query)
    else:
        result = await self._call_retrieve_lightweight_api(query)
    
    # 提取结果和元数据
    memories = result.get("memories", [])
    metadata = result.get("metadata", {})
    self.last_retrieval_metadata = metadata
    
    return memories
```

新增两个 HTTP API 调用方法：

**Lightweight 检索**：

```python
async def _call_retrieve_lightweight_api(self, query: str) -> Dict[str, Any]:
    """调用 Lightweight 检索 API"""
    payload = {
        "query": query,
        "user_id": "default",
        "group_id": self.group_id,
        "top_k": self.config.top_k_memories,
        "time_range_days": self.config.time_range_days,
        "retrieval_mode": self.retrieval_mode,
        "data_source": self.data_source,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(self.retrieve_lightweight_url, json=payload)
        response.raise_for_status()
        api_response = response.json()
        
        if api_response.get("status") == "ok":
            return api_response.get("result", {"memories": [], "metadata": {}})
        else:
            raise RuntimeError(f"API 返回错误: {api_response.get('message')}")
```

**Agentic 检索**：

```python
async def _call_retrieve_agentic_api(self, query: str) -> Dict[str, Any]:
    """调用 Agentic 检索 API"""
    payload = {
        "query": query,
        "user_id": "default",
        "group_id": self.group_id,
        "top_k": self.config.top_k_memories,
        "time_range_days": self.config.time_range_days,
        # LLM 配置通过环境变量传递
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(self.retrieve_agentic_url, json=payload)
        response.raise_for_status()
        api_response = response.json()
        
        if api_response.get("status") == "ok":
            return api_response.get("result", {"memories": [], "metadata": {}})
        else:
            raise RuntimeError(f"API 返回错误: {api_response.get('message')}")
```

**说明**：
- Lightweight 检索超时：30秒
- Agentic 检索超时：60秒（因为需要 LLM 调用）
- 完整的错误处理和友好的错误信息

---

### 3. 环境变量配置

#### `env.template`

新增 API 配置部分：

```bash
# ===================
# API Configuration / API配置
# ===================
# V3 API 服务器地址（用于 chat_with_memory.py）
# V3 API Server URL (for chat_with_memory.py)
API_BASE_URL=http://localhost:8001
```

---

## 🚀 使用方法

### 步骤 1: 配置环境变量

```bash
# 复制配置模板
cp env.template .env

# 编辑 .env 文件，确保包含：
# API_BASE_URL=http://localhost:8001
# LLM_API_KEY=your_key_here
# ... 其他配置 ...
```

### 步骤 2: 启动 API 服务器（终端1）

```bash
uv run python src/bootstrap.py src/run.py --port 8001
```

**输出示例**：
```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete.
```

### 步骤 3: 启动聊天应用（终端2）

```bash
uv run python src/bootstrap.py demo/chat_with_memory.py
```

**输出示例**：
```
====================================================================================================
🚀 记忆增强对话系统 / Memory-Enhanced Chat System
====================================================================================================

[加载] 正在加载 assistant 的数据...
[加载] 成功加载 150 条记忆 ✅
[加载] 成功加载 3 轮历史对话 ✅

[提示] 输入 'help' 查看可用命令
```

---

## ⚠️ 注意事项

### 1. 服务器必须先启动

如果服务器未启动，会看到友好的错误提示：

```
❌ 无法连接到 API 服务器: http://localhost:8001

请先启动 V3 API 服务器：
  uv run python src/bootstrap.py src/run.py --port 8001

然后在另一个终端运行聊天应用。
```

### 2. Agentic 检索需要 LLM API Key

确保在 `.env` 文件中配置了 LLM API Key：

```bash
# OpenRouter（推荐）
LLM_API_KEY=sk-or-v1-xxxx
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini

# 或 OpenAI
OPENAI_API_KEY=sk-xxxx
```

### 3. 网络延迟

HTTP API 调用会有轻微的网络延迟：
- Lightweight 检索：通常 < 1 秒
- Agentic 检索：通常 2-5 秒（包含 LLM 调用）

### 4. 错误处理

系统提供完整的错误处理：
- ✅ 连接失败：友好提示启动服务器
- ✅ 超时错误：明确说明超时原因
- ✅ API 错误：显示详细错误信息

---

## 🔧 故障排除

### 问题 1: 连接失败

**现象**：
```
❌ 无法连接到 API 服务器: http://localhost:8001
```

**解决方案**：
1. 确保服务器已启动：`uv run python src/bootstrap.py src/run.py --port 8001`
2. 检查端口是否被占用：`lsof -i :8001`
3. 检查 `.env` 中的 `API_BASE_URL` 配置

### 问题 2: Agentic 检索失败

**现象**：
```
❌ API 返回错误: 缺少 LLM API Key
```

**解决方案**：
在 `.env` 文件中添加：
```bash
LLM_API_KEY=your_key_here
```

### 问题 3: 超时错误

**现象**：
```
请求超时（超过60秒），Agentic 检索可能需要更长时间
```

**解决方案**：
- 检查网络连接
- 使用更快的 LLM 模型（如 gpt-4o-mini）
- 检查数据量是否过大

---

## 📊 性能对比

| 指标 | Python SDK | HTTP API |
|------|-----------|----------|
| 延迟 | 极低（< 10ms） | 低（< 100ms） |
| 吞吐量 | 高 | 中 |
| 可扩展性 | 低 | 高 |
| 独立部署 | ❌ | ✅ |
| 标准化接口 | ❌ | ✅ |
| 适用场景 | 本地开发 | 生产环境 |

---

## 📚 相关文档

- [Agentic V3 API 文档](../api_docs/agentic_v3_api.md)
- [Agentic 检索测试指南](./agentic_retrieve_testing.md)
- [API 使用指南](./api_usage_guide.md)

---

## ✅ 迁移检查清单

完成迁移后，请确认以下事项：

- [ ] 已更新 `.env` 文件，添加 `API_BASE_URL`
- [ ] 可以成功启动 API 服务器
- [ ] 聊天应用可以正常启动并连接到服务器
- [ ] Lightweight 检索正常工作（rrf/embedding/bm25）
- [ ] Agentic 检索正常工作（如果配置了 LLM API Key）
- [ ] 错误提示友好且准确
- [ ] 对话历史保存正常

---

## 🎉 总结

通过本次迁移：

1. ✅ `chat_with_memory.py` 现在完全使用 HTTP API
2. ✅ 与生产环境架构保持一致
3. ✅ 提供友好的错误提示和健康检查
4. ✅ 支持所有检索模式（rrf/embedding/bm25/agentic）
5. ✅ 完整的错误处理和超时控制

现在你可以享受标准化的 HTTP API 带来的便利！🚀

