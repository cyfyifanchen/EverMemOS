"""
租户配置模块

本模块提供租户相关的配置管理，包括非租户模式开关等配置项。
配置项从环境变量加载，并支持缓存以提升性能。
"""

import os
from typing import Optional
from functools import lru_cache

from core.observation.logger import get_logger

logger = get_logger(__name__)


class TenantConfig:
    """
    租户配置类

    此类负责管理租户相关的配置项，包括：
    - 非租户模式开关：用于控制是否启用租户化功能
    - 单租户ID：用于激活单租户模式的租户标识
    - 其他租户相关的配置项

    配置项从环境变量中加载，并提供缓存机制以提升性能。
    """

    def __init__(self):
        """初始化租户配置"""
        self._non_tenant_mode: Optional[bool] = None
        self._single_tenant_id: Optional[str] = None
        self._app_ready: bool = False  # 应用启动完成状态，用于严格租户检查

    @property
    def non_tenant_mode(self) -> bool:
        """
        获取非租户模式开关

        从环境变量 TENANT_NON_TENANT_MODE 读取配置：
        - "true", "1", "yes", "on" (不区分大小写) -> True
        - 其他值或未设置 -> False (默认启用租户模式)

        Returns:
            bool: True 表示禁用租户模式，False 表示启用租户模式
        """
        if self._non_tenant_mode is None:
            env_value = os.getenv("TENANT_NON_TENANT_MODE", "false").lower()
            self._non_tenant_mode = env_value in ("true", "1", "yes", "on")

            if self._non_tenant_mode:
                logger.info("🔧 租户模式已禁用（NON_TENANT_MODE=true），将使用传统模式")
            else:
                logger.info("✅ 租户模式已启用（NON_TENANT_MODE=false）")

        return self._non_tenant_mode

    @property
    def single_tenant_id(self) -> Optional[str]:
        """
        获取单租户ID配置

        从环境变量 TENANT_SINGLE_TENANT_ID 读取配置。
        当设置了此环境变量时，系统将自动激活该租户ID的租户逻辑。
        适用于单租户部署场景。

        Returns:
            单租户ID，如果未设置则返回 None

        Examples:
            >>> config = get_tenant_config()
            >>> tenant_id = config.single_tenant_id
            >>> if tenant_id:
            ...     print(f"单租户模式，租户ID: {tenant_id}")
        """
        if self._single_tenant_id is None:
            self._single_tenant_id = os.getenv("TENANT_SINGLE_TENANT_ID", "").strip()
            # 如果为空字符串，设置为 None
            if not self._single_tenant_id:
                self._single_tenant_id = None
            else:
                logger.info("🏢 单租户模式已激活，租户ID: %s", self._single_tenant_id)

        return self._single_tenant_id

    @property
    def app_ready(self) -> bool:
        """
        获取应用启动完成状态

        此状态用于严格租户检查模式：
        - False: 应用启动中，允许无租户上下文的操作（使用 fallback）
        - True: 应用已就绪，租户模式下必须有租户上下文，否则直接报错

        这是一个兜底机制，用于在生产环境中捕获遗漏租户上下文的代码错误。

        Returns:
            bool: True 表示应用已就绪，False 表示应用启动中
        """
        return self._app_ready

    def mark_app_ready(self) -> None:
        """
        标记应用启动完成

        此方法应在所有 lifespan providers 启动完成后调用。
        调用后，租户模式下如果缺少租户上下文将直接报错，而不是走 fallback 逻辑。

        注意：此方法只能设置一次，重复调用会记录警告日志。
        """
        if self._app_ready:
            logger.warning("⚠️ 应用已处于就绪状态，重复调用 mark_app_ready()")
            return

        self._app_ready = True
        logger.info("✅ 应用启动完成，租户严格检查模式已开启")

    def reload(self):
        """
        重新加载配置

        清除缓存的配置项，强制从环境变量重新读取。
        通常在测试或配置变更后使用。

        注意：reload 不会重置 app_ready 状态，因为它反映的是运行时状态而非配置。
        """
        self._non_tenant_mode = None
        self._single_tenant_id = None
        logger.info("🔄 租户配置已重新加载")

    def reset_app_ready(self) -> None:
        """
        重置应用就绪状态（仅用于测试）

        警告：此方法仅应在测试场景中使用，生产环境中不应调用。
        """
        self._app_ready = False
        logger.warning("⚠️ 应用就绪状态已重置（仅用于测试）")


@lru_cache(maxsize=1)
def get_tenant_config() -> TenantConfig:
    """
    获取租户配置单例

    使用 lru_cache 确保在整个应用生命周期中只创建一个配置实例。

    Returns:
        TenantConfig: 租户配置对象

    Examples:
        >>> config = get_tenant_config()
        >>> if config.non_tenant_mode:
        ...     print("非租户模式")
        ... else:
        ...     print("租户模式")
    """
    return TenantConfig()
