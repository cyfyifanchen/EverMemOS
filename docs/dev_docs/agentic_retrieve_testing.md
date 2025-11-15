# Agentic 检索测试指南

## 概述

本文档说明如何测试 V3 API 的 Agentic 检索功能。Agentic 检索是一种 LLM 引导的智能多轮检索方法，能够自动判断检索结果的充分性并进行多轮优化。

## 功能特性

### Agentic 检索流程

1. **Round 1**: RRF 混合检索（Embedding + BM25）
2. **Rerank**: 使用 Reranker 优化结果质量
3. **LLM 判断**: 使用 LLM 判断结果是否充分
4. **Round 2** (如需要): 
   - LLM 生成多个改进查询
   - 并行检索所有查询
   - 融合并 Rerank 返回最终结果

### API 端点

```
POST /api/v3/agentic/retrieve_agentic
```

### 请求格式

```json
{
  "query": "用户喜欢吃什么？",
  "user_id": "default",
  "group_id": "assistant",
  "time_range_days": 365,
  "top_k": 20,
  "llm_config": {
    "api_key": "your_api_key",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini"
  }
}
```

### 响应格式

```json
{
  "status": "ok",
  "message": "Agentic 检索成功，找到 15 条记忆",
  "result": {
    "memories": [...],
    "count": 15,
    "metadata": {
      "retrieval_mode": "agentic",
      "is_multi_round": true,
      "round1_count": 20,
      "is_sufficient": false,
      "reasoning": "需要更多关于饮食偏好的具体信息",
      "refined_queries": ["用户最喜欢的菜系？", "用户不喜欢吃什么？"],
      "round2_count": 40,
      "final_count": 15,
      "total_latency_ms": 2345.67
    }
  }
}
```

## 测试说明

### 运行测试

```bash
# 启动服务
uv run python src/bootstrap.py src/run.py --port 8001

# 运行测试（在另一个终端）
uv run python src/bootstrap.py demo/test_v3_retrieve_http.py
```

### 环境配置

Agentic 检索需要配置 LLM API Key：

```bash
# .env 文件中添加
OPENROUTER_API_KEY=your_api_key
# 或
OPENAI_API_KEY=your_api_key
```

如果未配置 API Key，测试将自动跳过 Agentic 检索部分。

### 测试用例

测试文件包含以下 Agentic 检索测试用例：

1. **简单查询**: "北京旅游" - 测试单轮检索（可能充分）
2. **复杂查询**: "用户喜欢吃什么？平时的饮食习惯是什么？" - 测试多轮检索
3. **多维度查询**: "用户的性格特点和兴趣爱好" - 测试多维度检索

### 预期结果

- **单轮检索**: 如果 Round 1 结果充分，直接返回
- **多轮检索**: 如果 Round 1 结果不充分，LLM 会生成改进查询并进行 Round 2

## 性能说明

- **延迟**: 通常 2-5 秒（包含 LLM 调用）
- **成本**: 会产生 LLM API 调用费用（约 2-3 次调用）
- **准确性**: 比普通检索更准确，特别适合复杂查询

## 与聊天模块的集成

聊天模块 (`demo/chat_with_memory.py`) 已经集成了 Agentic 检索：

1. 启动聊天应用时选择 "Agentic 检索"
2. 系统会自动使用 LLM 引导的多轮检索
3. 每次对话都会输出详细的检索元数据

## 故障排除

### 问题1: API Key 错误

**现象**: 提示 "缺少 LLM API Key"

**解决方案**:
```bash
# 在 .env 文件中添加
OPENROUTER_API_KEY=your_key_here
```

### 问题2: 超时

**现象**: 请求超时（超过60秒）

**原因**: Agentic 检索包含多次 LLM 调用，在网络较慢或 LLM 响应慢时可能超时

**解决方案**:
- 检查网络连接
- 使用更快的 LLM 模型（如 gpt-4o-mini）
- 增加客户端超时时间

### 问题3: 检索结果为空

**现象**: 返回 0 条记忆

**原因**: 数据库中没有相关数据

**解决方案**:
```bash
# 先运行数据导入
uv run python src/bootstrap.py demo/extract_memory.py

# 然后再测试检索
uv run python src/bootstrap.py demo/test_v3_retrieve_http.py
```

## 参考资料

- [Agentic V3 API 文档](../api_docs/agentic_v3_api.md)
- [Agentic 检索原理](./agentic_retrieval_guide.md)
- [Memory Manager 使用指南](./api_usage_guide.md)

