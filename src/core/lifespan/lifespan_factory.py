"""
生命周期工厂

提供动态获取和创建生命周期的工厂方法
"""

from typing import List
from abc import abstractmethod, ABC
from core.di.utils import get_beans_by_type, get_bean
from core.di.decorators import component
from .lifespan_interface import LifespanProvider
from core.observation.logger import get_logger
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = get_logger(__name__)


class AppReadyListener(ABC):
    """
    应用就绪监听器协议

    实现此协议的组件会在所有 lifespan providers 启动完成后被调用。
    这是一个解耦的钩子机制，通过 DI 容器自动发现和调用所有监听器。

    使用方式：
        1. 创建一个类实现 on_app_ready() 方法
        2. 使用 @component 装饰器注册到 DI 容器
        3. lifespan 会自动发现并调用

    Example:
        >>> from core.di.decorators import component
        >>> from core.lifespan.lifespan_factory import AppReadyListener
        >>>
        >>> @component(name="my_app_ready_listener")
        >>> class MyAppReadyListener(AppReadyListener):
        ...     def on_app_ready(self) -> None:
        ...         print("应用已就绪，执行我的逻辑")
    """

    @abstractmethod
    def on_app_ready(self) -> None:
        """应用就绪时调用"""
        ...


def create_lifespan_with_providers(providers: list[LifespanProvider]):
    """
    创建包含多个提供者的生命周期管理器

    Args:
        providers (list[LifespanProvider]): 生命周期提供者列表

    Returns:
        callable: FastAPI生命周期上下文管理器
    """
    # 按order排序
    sorted_providers = sorted(providers, key=lambda x: x.order)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """FastAPI生命周期上下文管理器"""
        lifespan_data = {}

        try:
            # 启动所有提供者
            for provider in sorted_providers:
                logger.info(
                    "启动生命周期提供者: %s (order=%d)", provider.name, provider.order
                )
                result = await provider.startup(app)
                if result is not None:
                    lifespan_data[provider.name] = result
                logger.info("生命周期提供者启动完成: %s", provider.name)

            # 将数据存储到app.state，方便获取
            app.state.lifespan_data = lifespan_data

            # 通过 DI 获取所有应用就绪监听器并调用（解耦设计）
            listeners = get_beans_by_type(AppReadyListener)
            for listener in listeners:
                try:
                    listener.on_app_ready()
                except Exception as e:
                    logger.error(
                        "应用就绪监听器执行失败: %s - %s", type(listener).__name__, e
                    )

            yield  # 应用运行期间

        finally:
            # 按逆序关闭所有提供者
            for provider in reversed(sorted_providers):
                try:
                    logger.info("关闭生命周期提供者: %s", provider.name)
                    await provider.shutdown(app)
                    logger.info("生命周期提供者关闭完成: %s", provider.name)
                except Exception as e:
                    logger.error(
                        "关闭生命周期提供者失败: %s - %s", provider.name, str(e)
                    )

    return lifespan


@component(name="lifespan_factory")
class LifespanFactory:
    """生命周期工厂"""

    def create_auto_lifespan(self):
        """
        自动创建包含所有已注册提供者的生命周期

        Returns:
            callable: FastAPI生命周期上下文管理器
        """
        providers = get_beans_by_type(LifespanProvider)
        # 按order排序
        sorted_providers = sorted(providers, key=lambda x: x.order)
        return create_lifespan_with_providers(sorted_providers)

    def create_lifespan_with_names(self, provider_names: List[str]):
        """
        根据提供者名称创建生命周期

        Args:
            provider_names (List[str]): 提供者名称列表

        Returns:
            callable: FastAPI生命周期上下文管理器
        """
        providers = []
        for name in provider_names:
            provider = get_bean(name)
            if isinstance(provider, LifespanProvider):
                providers.append(provider)

        # 按order排序
        sorted_providers = sorted(providers, key=lambda x: x.order)
        return create_lifespan_with_providers(sorted_providers)

    def create_lifespan_with_orders(self, orders: List[int]):
        """
        根据order值创建生命周期

        Args:
            orders (List[int]): order值列表

        Returns:
            callable: FastAPI生命周期上下文管理器
        """
        all_providers = get_beans_by_type(LifespanProvider)
        filtered_providers = [p for p in all_providers if p.order in orders]

        # 按order排序
        sorted_providers = sorted(filtered_providers, key=lambda x: x.order)
        return create_lifespan_with_providers(sorted_providers)

    def list_available_providers(self) -> List[LifespanProvider]:
        """
        列出所有可用的生命周期提供者

        Returns:
            List[LifespanProvider]: 提供者列表（按order排序）
        """
        providers = get_beans_by_type(LifespanProvider)
        return sorted(providers, key=lambda x: x.order)
