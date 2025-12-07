# ============================================================================
# 应用就绪监听器（通过 DI 自动发现）
# ============================================================================

from core.di.decorators import component
from core.lifespan.lifespan_factory import AppReadyListener
from core.observation.logger import get_logger
from core.tenants.tenant_config import get_tenant_config

logger = get_logger(__name__)


@component(name="tenant_config_app_ready_listener")
class TenantConfigAppReadyListener(AppReadyListener):
    """
    租户配置应用就绪监听器

    当应用启动完成时，自动开启租户严格检查模式。
    通过 DI 容器自动发现和调用，无需手动注册。
    """

    def on_app_ready(self) -> None:
        """应用就绪时开启严格租户检查"""
        get_tenant_config().mark_app_ready()
