"""
超时转后台执行装饰器

用于 endpoint，当业务逻辑执行超时时，自动转为后台执行并返回 202 响应。
与 AppLogicMiddleware 配合使用。

依赖 AppLogicProvider：
- 使用 get_current_request_id() 获取 request_id
- 使用 on_request_complete() 作为后台完成回调

后台模式配置：
- 默认开启后台模式（超时自动转后台）
- 可通过 request params 传入 sync_mode=true 来关闭后台模式（同步等待执行完成）
"""

from typing import Any, Callable, Coroutine, TypeVar, ParamSpec, Union, Optional
from functools import wraps
import asyncio
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

from core.observation.logger import get_logger
from core.di.utils import get_bean_by_type
from core.context.context import get_current_request

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# 默认阻塞等待超时时间（秒）
DEFAULT_BLOCKING_TIMEOUT = 5.0

# 同步模式参数名（用于关闭后台模式）
SYNC_MODE_PARAM = "sync_mode"


def is_background_mode_enabled(request: Optional[Request] = None) -> bool:
    """
    检查是否启用后台模式

    默认开启后台模式。可通过以下方式关闭：
    - request params 中传入 sync_mode=true

    Args:
        request: FastAPI 请求对象，如果为 None 则从 context 中获取

    Returns:
        bool: True 表示启用后台模式，False 表示关闭（同步执行）
    """
    if request is None:
        request = get_current_request()

    if request is None:
        # 没有请求上下文，默认开启后台模式
        return True

    # 检查 query params 中是否有 sync_mode=true
    sync_mode = request.query_params.get(SYNC_MODE_PARAM, "").lower()
    if sync_mode in ("true", "1", "yes"):
        logger.debug("[BackgroundMode] 检测到 sync_mode=%s，关闭后台模式", sync_mode)
        return False

    # 默认开启后台模式
    return True


def timeout_to_background(
    timeout: float = DEFAULT_BLOCKING_TIMEOUT,
    accepted_message: str = "Request accepted, processing in background",
) -> Callable[
    [Callable[P, Coroutine[Any, Any, T]]],
    Callable[P, Coroutine[Any, Any, Union[T, JSONResponse]]],
]:
    """
    超时转后台执行装饰器

    当被装饰的 endpoint 执行超过指定时间时：
    1. 返回 202 Accepted 响应给客户端
    2. 业务逻辑在后台继续执行
    3. 后台执行完成/失败时调用 AppLogicProvider.on_request_complete()

    与 AppLogicMiddleware 配合：
    - 正常完成（未超时）：middleware 的 on_request_complete 处理
    - 超时转后台（返回 202）：装饰器调用 on_request_complete，middleware 跳过

    后台模式配置：
    - 默认开启后台模式（超时自动转后台）
    - 可通过 request params 传入 sync_mode=true 来关闭后台模式（同步等待执行完成）

    使用示例:
    ```python
    @router.post("/memorize")
    @timeout_to_background(timeout=5.0)
    async def memorize(request: MemorizeRequest):
        # 业务逻辑...
        return {"status": "ok"}

    # 客户端可通过 query params 关闭后台模式：
    # POST /memorize?sync_mode=true
    ```

    Args:
        timeout: 阻塞等待的超时时间（秒），默认 5s
        accepted_message: 202 响应的消息内容

    Returns:
        装饰器函数
    """

    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, Union[T, JSONResponse]]]:

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Union[T, JSONResponse]:
            # 延迟导入避免循环依赖
            from component.app_logic_provider import AppLogicProvider

            # 获取 AppLogicProvider 实例
            provider = get_bean_by_type(AppLogicProvider)
            request_id = provider.get_current_request_id()
            task_name = f"{func.__name__}_{request_id}"

            # 检查是否启用后台模式
            background_enabled = is_background_mode_enabled()

            if not background_enabled:
                # 同步模式：直接执行，不使用超时机制
                logger.debug(
                    "[TimeoutBackground] 任务 '%s' 使用同步模式执行", task_name
                )
                return await func(*args, **kwargs)

            # 后台模式：创建任务并设置超时
            task = asyncio.create_task(func(*args, **kwargs))

            try:
                # 先阻塞等待指定时间
                result = await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
                logger.debug(
                    "[TimeoutBackground] 任务 '%s' 在 %ss 内完成", task_name, timeout
                )
                # 正常完成，不调用 on_request_complete，让 middleware 处理
                return result

            except asyncio.TimeoutError:
                # 超时未完成，转为后台执行
                logger.info(
                    "[TimeoutBackground] 任务 '%s' 超时(%ss)，转为后台执行",
                    task_name,
                    timeout,
                )

                # 创建后台任务继续执行
                asyncio.create_task(_run_background_task(task, task_name, provider))

                # 返回 202 Accepted
                return JSONResponse(
                    status_code=202,
                    content={"message": accepted_message, "request_id": request_id},
                )

        return wrapper

    return decorator


async def _run_background_task(
    task: asyncio.Task,
    task_name: str,
    provider: Any,  # AppLogicProvider，使用 Any 避免循环导入
) -> None:
    """
    后台任务执行器

    Args:
        task: 要等待的 asyncio.Task
        task_name: 任务名称（用于日志）
        provider: AppLogicProvider 实例
    """
    try:
        await task
        logger.info("[TimeoutBackground] 后台任务 '%s' 完成", task_name)
        # 调用 provider 的 on_request_complete
        await _call_on_request_complete(provider, http_code=200, error_message=None)
    except asyncio.CancelledError:
        logger.warning("[TimeoutBackground] 后台任务 '%s' 被取消", task_name)
    except Exception as e:
        logger.error("[TimeoutBackground] 后台任务 '%s' 执行失败: %s", task_name, e)
        traceback.print_exc()
        await _call_on_request_complete(provider, http_code=500, error_message=str(e))


async def _call_on_request_complete(
    provider: Any, http_code: int, error_message: Optional[str]
) -> None:
    """
    调用 provider 的 on_request_complete

    从 context 中获取 request。
    """
    try:
        request = provider.get_current_request()

        if request is None:
            logger.warning(
                "[TimeoutBackground] 无法获取 request，跳过 on_request_complete"
            )
            return

        await provider.on_request_complete(
            request=request, http_code=http_code, error_message=error_message
        )
    except Exception as e:
        logger.warning("[TimeoutBackground] on_request_complete 回调执行失败: %s", e)
