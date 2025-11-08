"""
开源群聊格式定义

这个模块定义了一个标准的群聊数据格式，用于存储和交换群聊对话数据。
格式设计考虑了可扩展性、易读性和数据完整性。
"""

from typing import TypedDict, List, Optional, Literal, Dict, Any


# 用户详细信息
class UserDetail(TypedDict, total=False):
    """用户详细信息

    Attributes:
        full_name: 用户全名
        role: 用户角色（如：产品经理、技术负责人等）
        email: 邮箱地址（可选）
        avatar_url: 头像URL（可选）
        department: 部门（可选）
        extra: 其他扩展信息（可选）
    """

    full_name: str
    role: Optional[str]
    email: Optional[str]
    avatar_url: Optional[str]
    department: Optional[str]
    extra: Optional[Dict[str, Any]]


# 会话元信息
class ConversationMeta(TypedDict, total=False):
    """会话元信息

    Attributes:
        scene: 场景类型，支持 "company"（人机助手对话）或 "work"（工作群聊）（可选）
        scene_desc: 场景描述信息，如 company 场景可包含 bot_ids 列表标注助手机器人（可选）
        name: 群聊名称
        description: 群聊描述
        group_id: 群聊唯一标识（可选）
        created_at: 群聊创建时间（可选）
        default_timezone: 默认时区，如果消息没有时区信息则使用此时区（可选）
        user_details: 用户详细信息字典，key为用户ID
        tags: 标签列表（可选）
        extra: 其他扩展信息（可选）
    """

    scene: Optional[str]
    scene_desc: Optional[Dict[str, Any]]
    name: str
    description: str
    group_id: Optional[str]
    created_at: Optional[str]
    default_timezone: Optional[str]
    user_details: Dict[str, UserDetail]
    tags: Optional[List[str]]
    extra: Optional[Dict[str, Any]]


# 消息类型
MessageType = Literal["text", "image", "file", "audio", "video", "link", "system"]


# 消息引用对象（只有message_id是必需的）
class MessageReference(TypedDict, total=False):
    """消息引用对象

    当 refer_list 中使用对象形式时，只有 message_id 是必需的，
    其他字段都是可选的，可以根据需要灵活添加。

    Attributes:
        message_id: 被引用消息的ID（必需）
        create_time: 消息创建时间（可选）
        sender: 发送者用户ID（可选）
        sender_name: 发送者名称（可选）
        type: 消息类型（可选）
        content: 消息内容（可选）
        refer_list: 被引用消息的引用列表（可选，支持嵌套引用）
        extra: 其他扩展信息（可选）
    """

    message_id: str  # 唯一必需字段
    create_time: Optional[str]
    sender: Optional[str]
    sender_name: Optional[str]
    type: Optional[MessageType]
    content: Optional[str]
    refer_list: Optional[List[Any]]  # 支持嵌套引用
    extra: Optional[Dict[str, Any]]


# 标记 message_id 为必需字段
MessageReference.__required_keys__ = frozenset(["message_id"])


# 消息
class Message(TypedDict, total=False):
    """单条消息

    Attributes:
        message_id: 消息唯一标识
        create_time: 消息创建时间（ISO 8601格式，建议包含时区信息）
        sender: 发送者用户ID
        sender_name: 发送者名称（可选，用于快速查看，详细信息在user_details中）
        type: 消息类型（text/image/file等）
        content: 消息内容，根据type不同可能是文本、文件URL等
        refer_list: 引用的消息列表（可选）
                   支持两种格式：
                   1. 字符串：直接使用 message_id，如 ["msg_001", "msg_002"]
                   2. 对象：MessageReference 对象，只有 message_id 是必需的，其他字段可选
                      如 [{"message_id": "msg_001", "content": "引用内容"}]
        extra: 其他扩展信息，如表情回复、编辑历史等（可选）
    """

    message_id: str
    create_time: str
    sender: str
    sender_name: Optional[str]
    type: MessageType
    content: str
    refer_list: Optional[List[Any]]  # 可以是 MessageReference 或 str (message_id)
    extra: Optional[Dict[str, Any]]


# 完整的群聊格式
class GroupChatFormat(TypedDict):
    """完整的群聊格式

    Attributes:
        version: 格式版本号（遵循语义化版本）
        conversation_meta: 会话元信息
        conversation_list: 消息列表
    """

    version: str
    conversation_meta: ConversationMeta
    conversation_list: List[Message]


def validate_group_chat_format(data: GroupChatFormat) -> bool:
    """验证群聊格式是否符合规范

    Args:
        data: 群聊数据

    Returns:
        是否符合规范
    """
    # 基本字段检查
    if (
        "version" not in data
        or "conversation_meta" not in data
        or "conversation_list" not in data
    ):
        return False

    meta = data["conversation_meta"]
    if "name" not in meta or "user_details" not in meta:
        return False

    # 检查消息中的sender是否都在user_details中
    user_ids = set(meta["user_details"].keys())
    message_ids = set()

    for msg in data["conversation_list"]:
        # 检查sender
        if msg.get("sender") not in user_ids:
            return False

        # 收集所有message_id
        if "message_id" in msg:
            message_ids.add(msg["message_id"])

    # 检查refer_list中的引用
    for msg in data["conversation_list"]:
        refer_list = msg.get("refer_list", [])
        if refer_list:
            for refer in refer_list:
                # 如果是字符串（消息ID引用）
                if isinstance(refer, str):
                    # 可以选择验证ID是否存在于conversation_list中
                    # if refer not in message_ids:
                    #     return False
                    pass
                # 如果是字典（MessageReference对象）
                elif isinstance(refer, dict):
                    # 只验证必需字段：message_id
                    if "message_id" not in refer:
                        return False
                    # 如果包含sender字段，验证是否在user_details中
                    if "sender" in refer and refer.get("sender") not in user_ids:
                        return False
                else:
                    return False

    return True


def create_example_group_chat() -> GroupChatFormat:
    """创建一个示例群聊数据

    Returns:
        示例群聊数据
    """
    return {
        "version": "1.0.0",
        "conversation_meta": {
            "name": "智能销售助手项目组",
            "description": "智能销售助手项目的开发讨论群",
            "group_id": "group_sales_ai_2025",
            "created_at": "2025-02-01T09:00:00+08:00",
            "default_timezone": "Asia/Shanghai",
            "user_details": {
                "user_101": {
                    "full_name": "Alex",
                    "role": "技术负责人",
                    "department": "技术部",
                },
                "user_102": {
                    "full_name": "Betty",
                    "role": "产品经理",
                    "department": "产品部",
                },
                "user_103": {
                    "full_name": "Chen",
                    "role": "项目经理",
                    "department": "项目管理部",
                },
                "user_104": {
                    "full_name": "Dylan",
                    "role": "后端工程师",
                    "department": "技术部",
                },
                "user_105": {
                    "full_name": "Emily",
                    "role": "前端工程师",
                    "department": "技术部",
                },
            },
            "tags": ["AI", "销售", "项目开发"],
        },
        "conversation_list": [
            {
                "message_id": "msg_001",
                "create_time": "2025-02-01T10:00:00+08:00",
                "sender": "user_103",
                "sender_name": "Chen",
                "type": "text",
                "content": "大家早，\"智能销售助手\"现在进展如何？",
                "refer_list": [],
            },
            {
                "message_id": "msg_002",
                "create_time": "2025-02-01T10:01:00+08:00",
                "sender": "user_102",
                "sender_name": "Betty",
                "type": "text",
                "content": "早。先对齐下目标？是能用于内测的MVP，还是直接客户试点？",
                "refer_list": [],
            },
            {
                "message_id": "msg_003",
                "create_time": "2025-02-01T10:01:30+08:00",
                "sender": "user_103",
                "sender_name": "Chen",
                "type": "text",
                "content": "先MVP，3月出能跑的，4月底收尾。",
                # 方式1：仅引用消息ID（简单引用）
                "refer_list": ["msg_002"],
            },
            {
                "message_id": "msg_004",
                "create_time": "2025-02-01T10:02:00+08:00",
                "sender": "user_101",
                "sender_name": "Alex",
                "type": "text",
                "content": "技术建议RAG为主。",
                "refer_list": [],
            },
            {
                "message_id": "msg_005",
                "create_time": "2025-02-01T10:02:30+08:00",
                "sender": "user_101",
                "sender_name": "Alex",
                "type": "text",
                "content": "当前的方法：BM25(ES)+向量检索(bge-base-zh，HNSW，topK=8)+交叉编码重排(先base版)，温度0.3，长度512。",
                "refer_list": [],
            },
            {
                "message_id": "msg_006",
                "create_time": "2025-02-01T10:03:30+08:00",
                "sender": "user_102",
                "sender_name": "Betty",
                "type": "text",
                "content": "指标先定：- 有效命中率≥0.8；- 首次响应P95≤1.5s；- 幻觉率≤8%。",
                # 方式2：对象引用，可以只包含 message_id
                "refer_list": [{"message_id": "msg_004"}],
            },
            {
                "message_id": "msg_007",
                "create_time": "2025-02-01T10:04:00+08:00",
                "sender": "user_101",
                "sender_name": "Alex",
                "type": "text",
                "content": "源头数据：产品手册v3.2、价格政策Q1、交付SLA文档。",
                # 方式3：对象引用，可以选择性地包含一些字段（如 content 用于预览）
                "refer_list": [
                    {
                        "message_id": "msg_006",
                        "content": "指标先定：- 有效命中率≥0.8；- 首次响应P95≤1.5s；- 幻觉率≤8%。",
                    }
                ],
            },
            {
                "message_id": "msg_008",
                "create_time": "2025-02-01T10:05:00+08:00",
                "sender": "user_101",
                "sender_name": "Alex",
                "type": "text",
                "content": "我把多个技术点都考虑进去了。",
                # 方式4：混合使用字符串和对象
                "refer_list": [
                    "msg_004",  # 简单引用
                    {
                        "message_id": "msg_005",
                        "sender": "user_101",
                        "content": "当前的方法：BM25(ES)+向量检索...",
                    },  # 带部分信息的引用
                ],
            },
        ],
    }


if __name__ == "__main__":
    import json

    # 创建示例数据
    example = create_example_group_chat()

    # 验证格式
    is_valid = validate_group_chat_format(example)
    print(f"格式验证: {'通过' if is_valid else '失败'}")

    # 输出示例JSON
    print("\n示例JSON:")
    print(json.dumps(example, ensure_ascii=False, indent=2))
