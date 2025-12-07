import asyncio
import contextvars
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union, List, Dict

from pymilvus import Collection, SearchResult
from pymilvus.orm.mutation import MutationResult
from pymilvus.client.types import CompactionPlans, CompactionState, Replica

T = TypeVar('T')


def async_wrap(func: Callable[..., T]) -> Callable[..., asyncio.Future[T]]:
    """将同步方法包装成异步方法的装饰器

    注意：使用 contextvars.copy_context() 确保线程池中的线程能访问到 contextvar
    （如租户上下文等），因为 run_in_executor 默认不会传递 asyncio Context。
    """

    @wraps(func)
    async def run(*args, **kwargs) -> T:
        loop = asyncio.get_running_loop()
        # 复制当前 context，确保线程池中能访问 contextvar
        ctx = contextvars.copy_context()
        return await loop.run_in_executor(None, lambda: ctx.run(func, *args, **kwargs))

    return run


class AsyncCollection:
    """异步版本的Collection类

    这个类包装了pymilvus的Collection类，提供异步接口。
    所有的同步操作都会在事件循环的默认执行器中执行。
    """

    def __init__(self, collection: Collection):
        """初始化AsyncCollection

        Args:
            collection: pymilvus的Collection实例
        """
        self._collection = collection

    def __getattr__(self, name: str) -> Any:
        """拦截所有对原始collection的属性访问

        如果是方法调用，包装成异步方法
        如果是属性访问，直接返回
        """
        attr = getattr(self._collection, name)
        if callable(attr):
            return async_wrap(attr)
        return attr

    @property
    def collection(self) -> Collection:
        """返回原始的Collection实例"""
        return self._collection

    # 以下是一些常用方法的显式异步实现
    # 虽然__getattr__也能处理这些方法，但显式定义可以提供更好的类型提示

    async def insert(
        self,
        data: Union[List, Dict],
        partition_name: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> MutationResult:
        """异步插入数据"""
        return await async_wrap(self._collection.insert)(
            data, partition_name, timeout, **kwargs
        )

    async def search(
        self,
        data: List,
        anns_field: str,
        param: Dict,
        limit: int,
        expr: Optional[str] = None,
        partition_names: Optional[List[str]] = None,
        output_fields: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        round_decimal: int = -1,
        **kwargs,
    ) -> SearchResult:
        """异步搜索"""
        return await async_wrap(self._collection.search)(
            data,
            anns_field,
            param,
            limit,
            expr,
            partition_names,
            output_fields,
            timeout,
            round_decimal,
            **kwargs,
        )

    async def query(
        self,
        expr: str,
        output_fields: Optional[List[str]] = None,
        partition_names: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> List:
        """异步查询"""
        return await async_wrap(self._collection.query)(
            expr, output_fields, partition_names, timeout, **kwargs
        )

    async def delete(
        self,
        expr: str,
        partition_name: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> MutationResult:
        """异步删除"""
        return await async_wrap(self._collection.delete)(
            expr, partition_name, timeout, **kwargs
        )

    async def flush(self, timeout: Optional[float] = None, **kwargs) -> None:
        """异步刷新"""
        return await async_wrap(self._collection.flush)(timeout, **kwargs)

    async def load(
        self,
        partition_names: Optional[List[str]] = None,
        replica_number: Optional[int] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> None:
        """异步加载"""
        return await async_wrap(self._collection.load)(
            partition_names, replica_number, timeout, **kwargs
        )

    async def release(self, timeout: Optional[float] = None, **kwargs) -> None:
        """异步释放"""
        return await async_wrap(self._collection.release)(timeout, **kwargs)

    async def compact(
        self,
        is_clustering: Optional[bool] = False,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> None:
        """异步压缩"""
        return await async_wrap(self._collection.compact)(
            is_clustering, timeout, **kwargs
        )

    async def get_compaction_state(
        self,
        timeout: Optional[float] = None,
        is_clustering: Optional[bool] = False,
        **kwargs,
    ) -> CompactionState:
        """异步获取压缩状态"""
        return await async_wrap(self._collection.get_compaction_state)(
            timeout, is_clustering, **kwargs
        )

    async def get_compaction_plans(
        self,
        timeout: Optional[float] = None,
        is_clustering: Optional[bool] = False,
        **kwargs,
    ) -> CompactionPlans:
        """异步获取压缩计划"""
        return await async_wrap(self._collection.get_compaction_plans)(
            timeout, is_clustering, **kwargs
        )

    async def get_replicas(self, timeout: Optional[float] = None, **kwargs) -> Replica:
        """异步获取副本信息"""
        return await async_wrap(self._collection.get_replicas)(timeout, **kwargs)
