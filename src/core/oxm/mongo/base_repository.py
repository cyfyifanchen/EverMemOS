"""
MongoDB 基础仓库类

基于 Beanie ODM 的基础仓库类，提供通用的事务管理和基础 CRUD 操作。
所有 MongoDB 仓库都应该继承这个基类以获得统一的事务支持。
"""

from abc import ABC
from contextlib import asynccontextmanager
from typing import Optional, TypeVar, Generic, Type, Union, List
from beanie import PydanticObjectId
from core.oxm.mongo.document_base import DocumentBase
from motor.motor_asyncio import AsyncIOMotorClientSession
from core.observation.logger import get_logger

logger = get_logger(__name__)

# 泛型类型变量
T = TypeVar('T', bound=DocumentBase)


class BaseRepository(ABC, Generic[T]):
    """
    MongoDB 基础仓库类

    提供通用的事务管理和基础操作，所有 MongoDB 仓库都应该继承这个类。

    特性：
    - 事务上下文管理器
    - 会话管理
    - 基础 CRUD 操作模板
    - 统一的错误处理和日志记录
    """

    def __init__(self, model: Type[T]):
        """
        初始化基础仓库

        Args:
            model: Beanie 文档模型类
        """
        self.model = model
        self.model_name = model.__name__

    # ==================== 事务管理 ====================

    @asynccontextmanager
    async def transaction(self):
        """
        事务上下文管理器

        使用方式:
            async with repository.transaction() as session:
                await repository.create(document, session=session)
                await repository.update(another_document, session=session)
                # 自动提交或回滚

        Yields:
            AsyncIOMotorClientSession: MongoDB 会话对象
        """
        client = self.model.get_motor_client()
        async with await client.start_session() as session:
            async with session.start_transaction():
                try:
                    logger.info("🔄 开始 MongoDB 事务 [%s]", self.model_name)
                    yield session
                    logger.info("✅ MongoDB 事务提交成功 [%s]", self.model_name)
                except Exception as e:
                    logger.error("❌ MongoDB 事务回滚 [%s]: %s", self.model_name, e)
                    raise

    async def start_session(self) -> AsyncIOMotorClientSession:
        """
        开始一个新的会话（不开启事务）

        Returns:
            AsyncIOMotorClientSession: MongoDB 会话对象

        Note:
            使用完毕后需要手动关闭会话：
            session = await repository.start_session()
            try:
                # 使用 session
                pass
            finally:
                await session.end_session()
        """
        client = self.model.get_motor_client()
        session = await client.start_session()
        logger.info("🔄 创建 MongoDB 会话 [%s]", self.model_name)
        return session

    # ==================== 基础 CRUD 模板方法 ====================

    async def create(
        self, document: T, session: Optional[AsyncIOMotorClientSession] = None
    ) -> T:
        """
        创建新文档

        Args:
            document: 文档实例
            session: 可选的 MongoDB 会话，用于事务支持

        Returns:
            创建成功的文档实例
        """
        try:
            await document.insert(session=session)
            logger.info(
                "✅ 创建文档成功 [%s]: %s",
                self.model_name,
                getattr(document, 'id', 'unknown'),
            )
            return document
        except Exception as e:
            logger.error("❌ 创建文档失败 [%s]: %s", self.model_name, e)
            raise

    async def get_by_id(self, object_id: Union[str, PydanticObjectId]) -> Optional[T]:
        """
        根据 ObjectId 获取文档

        Args:
            object_id: MongoDB ObjectId

        Returns:
            文档实例或 None
        """
        try:
            if isinstance(object_id, str):
                object_id = PydanticObjectId(object_id)
            return await self.model.get(object_id)
        except Exception as e:
            logger.error("❌ 根据 ID 获取文档失败 [%s]: %s", self.model_name, e)
            return None

    async def update(
        self, document: T, session: Optional[AsyncIOMotorClientSession] = None
    ) -> T:
        """
        更新文档

        Args:
            document: 要更新的文档实例
            session: 可选的 MongoDB 会话，用于事务支持

        Returns:
            更新后的文档实例
        """
        try:
            await document.save(session=session)
            logger.info(
                "✅ 更新文档成功 [%s]: %s",
                self.model_name,
                getattr(document, 'id', 'unknown'),
            )
            return document
        except Exception as e:
            logger.error("❌ 更新文档失败 [%s]: %s", self.model_name, e)
            raise

    async def delete_by_id(
        self,
        object_id: Union[str, PydanticObjectId],
        session: Optional[AsyncIOMotorClientSession] = None,
    ) -> bool:
        """
        根据 ObjectId 删除文档

        Args:
            object_id: MongoDB ObjectId
            session: 可选的 MongoDB 会话，用于事务支持

        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            document = await self.get_by_id(object_id)
            if document:
                await document.delete(session=session)
                logger.info("✅ 删除文档成功 [%s]: %s", self.model_name, object_id)
                return True
            return False
        except Exception as e:
            logger.error("❌ 删除文档失败 [%s]: %s", self.model_name, e)
            return False

    async def delete(
        self, document: T, session: Optional[AsyncIOMotorClientSession] = None
    ) -> bool:
        """
        删除文档实例

        Args:
            document: 要删除的文档实例
            session: 可选的 MongoDB 会话，用于事务支持

        Returns:
            删除成功返回 True，否则返回 False
        """
        try:
            await document.delete(session=session)
            logger.info(
                "✅ 删除文档成功 [%s]: %s",
                self.model_name,
                getattr(document, 'id', 'unknown'),
            )
            return True
        except Exception as e:
            logger.error("❌ 删除文档失败 [%s]: %s", self.model_name, e)
            return False

    # ==================== 批量操作 ====================

    async def create_batch(
        self, documents: List[T], session: Optional[AsyncIOMotorClientSession] = None
    ) -> List[T]:
        """
        批量创建文档

        Args:
            documents: 文档列表
            session: 可选的 MongoDB 会话，用于事务支持

        Returns:
            成功创建的文档列表
        """
        try:
            # Beanie 的 insert_many 不会自动更新传入对象的 id 属性
            # 我们需要手动从返回的 InsertManyResult 中获取 inserted_ids 并设置
            result = await self.model.insert_many(documents, session=session)
            # 将 MongoDB 生成的 _id 设置回每个文档对象的 id 属性
            for doc, inserted_id in zip(documents, result.inserted_ids):
                doc.id = inserted_id
            logger.info(
                "✅ 批量创建文档成功 [%s]: %d 条记录", self.model_name, len(documents)
            )
            return documents
        except Exception as e:
            logger.error("❌ 批量创建文档失败 [%s]: %s", self.model_name, e)
            raise

    # ==================== 统计方法 ====================

    async def count_all(self) -> int:
        """
        统计所有文档数量

        Returns:
            文档总数
        """
        try:
            count = await self.model.count()
            logger.info("✅ 统计文档总数成功 [%s]: %d 条记录", self.model_name, count)
            return count
        except Exception as e:
            logger.error("❌ 统计文档总数失败 [%s]: %s", self.model_name, e)
            return 0

    async def exists_by_id(self, object_id: Union[str, PydanticObjectId]) -> bool:
        """
        检查文档是否存在

        Args:
            object_id: MongoDB ObjectId

        Returns:
            存在返回 True，否则返回 False
        """
        try:
            if isinstance(object_id, str):
                object_id = PydanticObjectId(object_id)
            document = await self.model.get(object_id)
            return document is not None
        except Exception:
            return False

    # ==================== 辅助方法 ====================

    def get_model_name(self) -> str:
        """
        获取模型名称

        Returns:
            模型类名
        """
        return self.model_name

    def get_collection_name(self) -> str:
        """
        获取集合名称

        Returns:
            MongoDB 集合名称
        """
        return self.model.get_collection_name()


# 导出
__all__ = ["BaseRepository"]
