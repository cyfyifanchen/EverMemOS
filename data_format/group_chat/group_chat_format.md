# 群聊格式规范

## 概述

这是一个开源的群聊数据格式规范，用于标准化存储和交换群聊对话数据。

## 格式定义

完整的格式定义请参考 [`group_chat_format.py`](../group_chat_format.py)

## 核心特性

### 1. 分离的元信息和消息列表

```json
{
  "version": "1.0.0",
  "conversation_meta": { ... },
  "conversation_list": [ ... ]
}
```

- **version**: 格式版本号（遵循语义化版本）
- **conversation_meta**: 会话元信息
- **conversation_list**: 消息列表

### 2. 场景类型和场景描述

支持两种核心对话场景：

- **company**: 人机助手对话场景，一对一对话，AI 扮演个人助理
- **work**: 工作群聊场景，多人群聊，团队协作

**Company 场景示例**:
```json
"conversation_meta": {
  "scene": "company",
  "scene_desc": {
    "bot_ids": ["robot_001"]
  },
  ...
}
```

**Work 场景示例**:
```json
"conversation_meta": {
  "scene": "work",
  "scene_desc": {},
  ...
}
```

- **scene**: 场景类型标识符（`company` 或 `work`）
- **scene_desc**: 场景描述信息
  - Company 场景：包含 `bot_ids` 列表，标注哪些用户是助手机器人
  - Work 场景：通常为空对象，表示多人协作场景

### 3. 用户详细信息

所有用户的详细信息集中存储在 `conversation_meta.user_details` 中：

```json
"user_details": {
  "user_101": {
    "full_name": "Alex",
    "role": "技术负责人",
    "department": "技术部",
    "email": "alex@example.com"
  }
}
```

### 4. 消息结构

每条消息使用用户 ID 作为 `sender`，可选的 `sender_name` 用于方便阅读：

```json
{
  "message_id": "msg_001",
  "create_time": "2025-02-01T10:00:00+08:00",
  "sender": "user_103",
  "sender_name": "Chen",
  "type": "text",
  "content": "消息内容",
  "refer_list": []
}
```

### 5. 时区感知的时间戳

- 使用 ISO 8601 格式
- 推荐包含时区信息（如 `+08:00`）
- 如果消息没有时区信息，可从 `conversation_meta.default_timezone` 获取

### 6. 消息类型

支持多种消息类型：

- **text**: 文本消息
- **image**: 图片消息
- **file**: 文件消息
- **audio**: 音频消息
- **video**: 视频消息
- **link**: 链接消息
- **system**: 系统消息

### 7. 消息引用

支持灵活的引用方式，`refer_list` 中的每个元素可以是：

**方式1：字符串引用（仅 message_id）**
```json
"refer_list": ["msg_002", "msg_005"]
```

**方式2：对象引用（只有 message_id 必需，其他字段可选）**

最简形式：
```json
"refer_list": [
  {
    "message_id": "msg_002"
  }
]
```

包含部分字段（如 content 用于预览）：
```json
"refer_list": [
  {
    "message_id": "msg_002",
    "content": "早。先对齐下目标？是能用于内测的MVP，还是直接客户试点？"
  }
]
```

包含完整信息：
```json
"refer_list": [
  {
    "message_id": "msg_002",
    "create_time": "2025-02-01T10:01:00+08:00",
    "sender": "user_102",
    "sender_name": "Betty",
    "type": "text",
    "content": "早。先对齐下目标？是能用于内测的MVP，还是直接客户试点？",
    "refer_list": []
  }
]
```

**方式3：混合使用**
```json
"refer_list": [
  "msg_001",
  {
    "message_id": "msg_002",
    "content": "部分内容..."
  }
]
```

**使用建议：**
- 字符串引用：最简洁，适合引用关系明确的场景
- 最小对象引用：仅 message_id，适合需要统一格式但不需要额外信息的场景
- 带预览内容：包含 message_id + content，适合快速预览的场景
- 完整对象引用：包含所有字段，适合导出、归档或脱离原始数据使用的场景

### 7. 扩展字段

使用 `extra` 字段存储额外信息：

```json
"extra": {
  "file_name": "UI草稿_v1.pdf",
  "file_size": 2048576,
  "file_type": "application/pdf"
}
```

## 示例文件

- [`group_chat_format_example.json`](./group_chat_format_example.json) - 完整的示例文件
- [`group_chat_compatible.json`](./group_chat_compatible.json) - 旧格式的兼容示例

## 使用方法

### Python

```python
from data.group_chat_format import GroupChatFormat, validate_group_chat_format
import json

# 读取群聊数据
with open('group_chat_example.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 验证格式
is_valid = validate_group_chat_format(data)
print(f"格式验证: {'通过' if is_valid else '失败'}")

# 访问用户信息
user_details = data['conversation_meta']['user_details']
print(f"用户列表: {list(user_details.keys())}")

# 遍历消息
for msg in data['conversation_list']:
    sender_info = user_details[msg['sender']]
    print(f"{sender_info['full_name']}: {msg['content']}")
```

### 创建新的群聊数据

```python
from data.group_chat_format import create_example_group_chat
import json

# 创建示例数据
chat_data = create_example_group_chat()

# 保存到文件
with open('my_chat.json', 'w', encoding='utf-8') as f:
    json.dump(chat_data, f, ensure_ascii=False, indent=2)
```

## 版本历史

- **1.0.0** (2025-02-01)
  - 初始版本
  - 支持基本消息类型
  - 支持用户详细信息
  - 支持消息引用
  - 支持时区感知的时间戳

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进这个格式规范。

## 许可证

开源许可证待定

