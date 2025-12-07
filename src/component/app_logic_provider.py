from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import uuid
from fastapi import Request

from core.di.decorators import component
from core.observation.logger import get_logger
from core.context.context import get_current_app_info, get_current_request

logger = get_logger(__name__)

# 默认阻塞等待超时时间（秒）
DEFAULT_BLOCKING_TIMEOUT = 5.0


class AppLogicProvider(ABC):
    """
    应用逻辑提供者接口

    负责从请求中提取应用级别的上下文信息及处理应用逻辑。
    提供请求生命周期的钩子方法：
    - should_process_request(): 判断请求是否需要处理（用于过滤）
    - setup_app_context(): 提取并设置应用上下文（由 middleware 首先调用）
    - on_request_begin(): 请求开始时调用（业务逻辑，如投递事件）
    - on_request_complete(): 请求结束时调用（可选实现）

    辅助方法（从 context 获取）：
    - get_current_request_id(): 获取当前请求的 request_id
    - get_current_request(): 获取当前请求对象
    - get_current_app_info(): 获取当前应用信息
    """

    def should_process_request(self, request: Request) -> bool:
        """
        判断请求是否需要处理业务逻辑

        用于过滤请求，决定是否需要执行：
        - on_request_begin() 回调
        - on_request_complete() 回调

        注意：setup_app_context() 不受此方法影响，每次请求都会调用。

        子类可以重写此方法来实现自定义的过滤逻辑，
        例如只处理 /api/ 路由下的请求。

        Args:
            request: FastAPI 请求对象

        Returns:
            bool: True 表示需要处理，False 表示跳过
        """
        # 默认处理所有请求
        return True

    @abstractmethod
    def setup_app_context(self, request: Request) -> Dict[str, Any]:
        """
        提取并设置应用上下文

        从请求中提取所有上下文相关数据，例如：
        - 记录请求开始时间
        - 提取 request_id、hash_key
        - 设置租户上下文

        此方法由 middleware 首先调用，在 on_request_begin 之前。

        Args:
            request: FastAPI请求对象

        Returns:
            Dict[str, Any]: 包含上下文数据的 app_info 字典
        """
        raise NotImplementedError

    async def on_request_begin(self, request: Request) -> None:
        """
        请求开始时的回调方法

        用于处理请求开始时的业务逻辑，例如：
        - 投递请求开始事件

        注意：上下文数据已由 setup_app_context() 设置，
        可通过 self.get_current_app_info() 获取。

        Args:
            request: FastAPI请求对象
        """
        # 默认实现为空，子类可选择性重写
        _ = request  # 避免未使用参数警告

    async def on_request_complete(
        self, request: Request, http_code: int, error_message: Optional[str] = None
    ) -> None:
        """
        请求完成时的回调方法（可选实现）

        子类可以重写此方法来处理请求完成后的逻辑，
        例如：记录请求日志、投递事件等。

        注意：可通过 self.get_current_app_info() 获取 on_request_begin() 返回的 app_info。

        Args:
            request: FastAPI 请求对象
            http_code: HTTP 响应状态码
            error_message: 错误信息（可选）
        """
        # 默认实现为空，子类可选择性重写
        _ = (request, http_code, error_message)  # 避免未使用参数警告

    def get_current_request_id(self) -> str:
        """
        获取当前请求的 request_id

        从 context 中获取 app_info，然后提取 request_id。

        Returns:
            str: 当前请求的 request_id，如果未设置则返回 "unknown"
        """
        app_info = get_current_app_info()
        if app_info:
            return app_info.get("request_id", "unknown")
        return "unknown"

    def get_current_request(self) -> Optional[Request]:
        """
        获取当前请求对象

        从 context 中获取 request。

        Returns:
            Optional[Request]: 当前请求对象，如果未设置则返回 None
        """
        return get_current_request()

    def get_current_app_info(self) -> Optional[Dict[str, Any]]:
        """
        获取当前应用信息

        从 context 中获取 app_info。

        Returns:
            Optional[Dict[str, Any]]: 当前应用信息，如果未设置则返回 None
        """
        return get_current_app_info()


@component(name="app_logic_provider")
class AppLogicProviderImpl(AppLogicProvider):
    """应用逻辑提供者实现，负责从请求中提取应用级别的上下文信息"""

    def setup_app_context(self, request: Request) -> Dict[str, Any]:
        """
        提取并设置应用上下文

        Args:
            request: FastAPI请求对象

        Returns:
            Dict[str, Any]: 包含上下文数据的 app_info 字典
        """
        app_info: Dict[str, Any] = {}

        # 从请求头中获取request_id，优先X-Request-Id，兼容小写
        request_id = request.headers.get('X-Request-Id') or request.headers.get(
            'x-request-id'
        )
        if not request_id:
            request_id = str(uuid.uuid4())

        app_info['request_id'] = request_id

        return app_info
