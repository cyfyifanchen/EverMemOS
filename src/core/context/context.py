from contextvars import ContextVar, Token
from typing import Optional, Dict, Any, TypedDict, TYPE_CHECKING
from sqlmodel.ext.asyncio.session import AsyncSession
import logging

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


# 创建一个 ContextVar，用于存储当前请求的数据库会话
db_session_context: ContextVar[Optional[AsyncSession]] = ContextVar(
    "db_session_context", default=None
)

# 创建一个 ContextVar，用于存储当前用户的额外信息
user_info_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "user_info_context", default=None
)

# 🔧 应用信息上下文变量，用于存储 task_id 等应用级别的上下文信息
app_info_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "app_info_context", default=None
)

# 🔧 请求上下文变量，用于存储当前请求对象
request_context: ContextVar[Optional["Request"]] = ContextVar(
    "request_context", default=None
)


# 数据库会话相关函数
def get_current_session() -> AsyncSession:
    """
    获取当前请求的数据库会话

    Returns:
        AsyncSession: 当前请求的数据库会话

    Raises:
        RuntimeError: 如果当前上下文中没有设置数据库会话
    """
    session = db_session_context.get()
    if session is None:
        raise RuntimeError(
            "数据库会话未在当前上下文中设置。请确保在请求中间件中正确初始化了会话。"
        )
    return session


def set_current_session(session: AsyncSession) -> Token:
    """
    设置当前请求的数据库会话

    Args:
        session: 要设置的数据库会话
    """
    return db_session_context.set(session)


def clear_current_session(token: Optional[Token] = None) -> None:
    """
    清除当前请求的数据库会话
    """
    if token is not None:
        db_session_context.reset(token)
    else:
        db_session_context.set(None)


class UserInfo(TypedDict):
    user_id: int


# 用户上下文相关函数 - 只保留基础的数据存储和获取
def get_current_user_info() -> Optional[UserInfo]:
    """
    获取当前用户的基础信息

    Returns:
        Optional[Dict[str, Any]]: 当前用户的基础信息，如果未设置则返回None
    """
    return user_info_context.get()


def set_current_user_info(user_info: UserInfo) -> Token:
    """
    设置当前用户的基础信息

    Args:
        user_info: 要设置的用户信息
    """
    return user_info_context.set(user_info)


def clear_current_user_context(token: Optional[Token] = None) -> None:
    """
    清除当前用户上下文
    """
    if token is not None:
        user_info_context.reset(token)
    else:
        user_info_context.set(None)


# 🔧 应用信息上下文相关函数
def get_current_app_info() -> Optional[Dict[str, Any]]:
    """
    获取当前应用信息

    Returns:
        Optional[Dict[str, Any]]: 当前应用信息，如果未设置则返回 None
    """
    return app_info_context.get()


def set_current_app_info(app_info: Dict[str, Any]) -> Token:
    """
    设置当前应用信息到上下文变量

    Args:
        app_info: 应用信息字典，包含 task_id 等

    Returns:
        Token: 上下文变量token，用于后续清理
    """
    return app_info_context.set(app_info)


def clear_current_app_info(token: Optional[Token] = None) -> None:
    """
    清理当前应用信息上下文变量

    Args:
        token: 上下文变量token
    """
    if token is not None:
        app_info_context.reset(token)
    else:
        app_info_context.set(None)


# 🔧 请求上下文相关函数
def get_current_request() -> Optional["Request"]:
    """
    获取当前请求对象

    Returns:
        Optional[Request]: 当前请求对象，如果未设置则返回 None
    """
    return request_context.get()


def set_current_request(request: "Request") -> Token:
    """
    设置当前请求对象到上下文变量

    Args:
        request: FastAPI 请求对象

    Returns:
        Token: 上下文变量token，用于后续清理
    """
    return request_context.set(request)


def clear_current_request(token: Optional[Token] = None) -> None:
    """
    清理当前请求上下文变量

    Args:
        token: 上下文变量token
    """
    if token is not None:
        request_context.reset(token)
    else:
        request_context.set(None)
