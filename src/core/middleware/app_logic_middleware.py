"""
应用逻辑中间件
负责提取和设置应用级别的上下文信息，以及处理应用相关的逻辑（如上报等）
"""

from typing import Callable, Dict, Any, Optional

from fastapi import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.observation.logger import get_logger
from core.context.context import set_current_app_info, set_current_request
from core.di.utils import get_bean_by_type
from component.app_logic_provider import AppLogicProvider

logger = get_logger(__name__)


class AppLogicMiddleware(BaseHTTPMiddleware):
    """
    应用逻辑中间件

    负责管理请求生命周期，调用 AppLogicProvider 的回调方法：
    - setup_app_context(): 提取并设置应用上下文（每次请求都调用）
    - on_request_begin(): 请求开始时调用（受 should_process_request 控制）
    - on_request_complete(): 请求结束时调用（受 should_process_request 控制）
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._app_logic_provider = get_bean_by_type(AppLogicProvider)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # ========== 提取并设置应用上下文（每次请求都调用） ==========
        app_info = self._app_logic_provider.setup_app_context(request)

        # 设置上下文
        set_current_request(request)
        if app_info:
            set_current_app_info(app_info)

        # ========== 检查是否需要处理该请求的业务逻辑 ==========
        should_process = self._app_logic_provider.should_process_request(request)
        if not should_process:
            # 跳过业务逻辑处理，直接调用下一个中间件
            return await call_next(request)

        response: Optional[Response] = None
        error_message: Optional[str] = None

        try:
            # ========== 请求开始：调用 on_request_begin ==========
            await self._app_logic_provider.on_request_begin(request)

            # ========== 调用下一层处理 ==========
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error("应用逻辑中间件处理异常: %s", e)
            error_message = str(e)
            raise

        finally:
            # ========== 请求结束：调用 on_request_complete ==========
            # 确定 HTTP 状态码
            if response is not None:
                http_code = response.status_code
            else:
                http_code = 500

            try:
                await self._app_logic_provider.on_request_complete(
                    request=request, http_code=http_code, error_message=error_message
                )
            except Exception as callback_error:
                logger.warning("on_request_complete 执行失败: %s", callback_error)
