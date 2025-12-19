# -*- coding: utf-8 -*-
"""
Memory 请求日志监听器

监听 RequestHistoryEvent 事件，判断是否来自 memories 请求，
如果是则提取关键信息（group_id, request_id, user_id, 原始输入）存储到 MongoDB。
"""

import json
from typing import List, Optional, Type, Dict, Any
from urllib.parse import urlparse, parse_qs

from core.di import component
from core.di.utils import get_bean_by_type
from core.events import BaseEvent, EventListener
from core.observation.logger import get_logger
from core.request.request_history_event import RequestHistoryEvent
from infra_layer.adapters.input.api.mapper.group_chat_converter import (
    extract_message_core_fields,
)
from infra_layer.adapters.out.persistence.document.request.memory_request_log import (
    MemoryRequestLog,
)
from infra_layer.adapters.out.persistence.repository.memory_request_log_repository import (
    MemoryRequestLogRepository,
)


logger = get_logger(__name__)

# Memories 接口路径模式
MEMORIES_PATH_PREFIX = "/api/v1/memories"


def _is_memories_request(url: str) -> bool:
    """
    判断是否是 memories 请求

    Args:
        url: 请求 URL

    Returns:
        bool: 是否是 memories 请求
    """
    try:
        parsed = urlparse(url)
        path = parsed.path
        return path.startswith(MEMORIES_PATH_PREFIX)
    except Exception:
        return False


def _parse_body(body: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    尝试解析 body 为 JSON

    Args:
        body: 原始 body 字符串

    Returns:
        解析后的字典或 None
    """
    if not body:
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_group_id(url: str, body_parsed: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    提取 group_id

    优先从 body 中提取，其次从 query params 中提取

    Args:
        url: 请求 URL
        body_parsed: 解析后的 body

    Returns:
        group_id 或 None
    """
    # 1. 先从 body 中提取
    if body_parsed:
        group_id = body_parsed.get("group_id")
        if group_id:
            return str(group_id)

    # 2. 从 query params 中提取
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        group_id_list = query_params.get("group_id")
        if group_id_list:
            return group_id_list[0]
    except Exception:
        pass

    return None


def _extract_user_id(
    url: str, body_parsed: Optional[Dict[str, Any]], headers: Dict[str, str]
) -> Optional[str]:
    """
    提取 user_id

    优先从 body 中提取，其次从 query params，最后从 headers

    Args:
        url: 请求 URL
        body_parsed: 解析后的 body
        headers: 请求头

    Returns:
        user_id 或 None
    """
    # 1. 从 body 中提取（可能是 sender 或 user_id）
    if body_parsed:
        user_id = body_parsed.get("user_id") or body_parsed.get("sender")
        if user_id:
            return str(user_id)

    # 2. 从 query params 中提取
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        user_id_list = query_params.get("user_id")
        if user_id_list:
            return user_id_list[0]
    except Exception:
        pass

    # 3. 从 headers 中提取
    user_id = headers.get("X-User-Id") or headers.get("x-user-id")
    if user_id:
        return user_id

    return None


def _extract_request_id(headers: Dict[str, str]) -> Optional[str]:
    """
    从 headers 中提取 request_id

    Args:
        headers: 请求头

    Returns:
        request_id 或 None
    """
    return headers.get("X-Request-Id") or headers.get("x-request-id")


def _extract_tenant_from_headers(
    headers: Dict[str, str]
) -> tuple[Optional[str], Optional[str]]:
    """
    从 headers 中提取租户信息

    Args:
        headers: 请求头字典

    Returns:
        (organization_id, space_id)
    """
    org_id = headers.get("X-Organization-Id") or headers.get("x-organization-id")
    space_id = headers.get("X-Space-Id") or headers.get("x-space-id")
    return org_id, space_id


@component("memory_request_log_listener")
class MemoryRequestLogListener(EventListener):
    """
    Memory 请求日志监听器

    监听 RequestHistoryEvent 事件，判断是否来自 memories 请求。
    如果是 memories 请求，则提取以下信息并存储：
    - group_id: 会话组 ID
    - request_id: 请求 ID
    - user_id: 用户 ID
    - raw_input: 原始输入数据
    """

    def __init__(self):
        """初始化监听器"""
        self._repository: Optional[MemoryRequestLogRepository] = None
        logger.info("MemoryRequestLogListener 初始化完成")

    def _get_repository(self) -> MemoryRequestLogRepository:
        """获取 Repository（懒加载）"""
        if self._repository is None:
            self._repository = get_bean_by_type(MemoryRequestLogRepository)
        return self._repository

    def get_event_types(self) -> List[Type[BaseEvent]]:
        """获取要监听的事件类型列表"""
        return [RequestHistoryEvent]

    async def on_event(self, event: BaseEvent) -> None:
        """
        处理 RequestHistoryEvent 事件

        Args:
            event: 接收到的事件对象
        """
        if not isinstance(event, RequestHistoryEvent):
            logger.warning(
                "收到非 RequestHistoryEvent 类型的事件: %s", type(event).__name__
            )
            return

        # 判断是否是 memories 请求
        if not _is_memories_request(event.url):
            logger.debug("跳过非 memories 请求: url=%s", event.url)
            return

        await self._save_to_mongo(event)

    async def _save_to_mongo(self, event: RequestHistoryEvent) -> None:
        """
        将 memories 请求信息保存到 MongoDB

        提取 memorize 请求中的消息核心字段（message_id, create_time, sender, content 等），
        这些字段后续可用于替代 Redis 中存储的 RawData。

        Args:
            event: RequestHistoryEvent 事件
        """
        try:
            # 解析 body
            body_parsed = _parse_body(event.body)

            # 提取关键字段
            group_id = _extract_group_id(event.url, body_parsed)
            request_id = _extract_request_id(event.headers)
            user_id = _extract_user_id(event.url, body_parsed, event.headers)
            org_id, space_id = _extract_tenant_from_headers(event.headers)

            # 提取消息核心字段（使用 group_chat_converter 中的公共函数）
            message_fields = extract_message_core_fields(body_parsed)

            # group_id 和 request_id 是必须的
            if not group_id:
                logger.debug("memories 请求缺少 group_id，跳过: url=%s", event.url)
                return

            if not request_id:
                # 使用 event_id 作为备选
                request_id = event.event_id or "unknown"

            # 创建文档，包含消息核心字段
            memory_request_log = MemoryRequestLog(
                # 核心标识字段
                group_id=group_id,
                request_id=request_id,
                user_id=user_id,
                # 消息核心字段（用于替代 RawData）
                message_id=message_fields.get("message_id"),
                message_create_time=message_fields.get("message_create_time"),
                sender=message_fields.get("sender"),
                sender_name=message_fields.get("sender_name"),
                content=message_fields.get("content"),
                group_name=message_fields.get("group_name"),
                refer_list=message_fields.get("refer_list"),
                # 原始输入（保留用于调试）
                raw_input=body_parsed,
                raw_input_str=event.body,
                # 请求元信息
                version=event.version,
                endpoint_name=event.endpoint_name,
                method=event.method,
                url=event.url,
                # 租户信息
                organization_id=org_id,
                space_id=space_id,
                # 事件关联
                event_id=event.event_id,
            )

            # 保存到 MongoDB
            repo = self._get_repository()
            await repo.save(memory_request_log)

            logger.debug(
                "Memory 请求日志已保存: group_id=%s, request_id=%s, message_id=%s, content_preview=%s",
                group_id,
                request_id,
                message_fields.get("message_id"),
                (message_fields.get("content") or "")[:50],  # 只打印前50字符
            )

        except Exception as e:
            logger.error(
                "保存 Memory 请求日志到 MongoDB 失败: url=%s, error=%s", event.url, e
            )
