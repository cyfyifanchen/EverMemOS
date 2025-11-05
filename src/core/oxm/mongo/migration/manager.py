"""
MongoDB migration manager module.

This module provides a high-level interface for managing MongoDB database migrations
using Beanie as the underlying migration engine.
"""

import os
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from common_utils.project_path import CURRENT_DIR
from pymongo import MongoClient

# Module-level logger for this file
logger = logging.getLogger(__name__)


class MigrationManager:
    """Migration manager for MongoDB using Beanie"""

    MIGRATIONS_DIR = CURRENT_DIR / "migrations" / "mongodb"

    # Default migration template
    MIGRATION_TEMPLATE = '''"""
{description}

Created at: {created_at}
"""

from beanie import Document
from beanie import iterative_migration, free_fall_migration
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT


class Forward:
    """Forward migration"""
    
    # Example: Iterative migration (recommended)
    # @iterative_migration()
    # async def update_field(self, input_document: OldModel, output_document: NewModel):
    #     output_document.new_field = input_document.old_field
    
    # Example: Free fall migration (flexible)
    # @free_fall_migration(document_models=[YourModel])
    # async def create_indexes(self, session):
    #     # Get collection
    #     collection = YourModel.get_motor_collection()
    #     
    #     # Create indexes
    #     indexes = [
    #         IndexModel([("field_name", ASCENDING)], name="idx_field_name")
    #     ]
    #     await collection.create_indexes(indexes)
    
    pass


class Backward:
    """Backward migration"""
    
    # @iterative_migration()
    # async def revert_field(self, input_document: NewModel, output_document: OldModel):
    #     output_document.old_field = input_document.new_field
    
    # @free_fall_migration(document_models=[YourModel])
    # async def drop_indexes(self, session):
    #     collection = YourModel.get_motor_collection()
    #     await collection.drop_index("idx_field_name")
    
    pass
'''

    def __init__(
        self,
        uri: Optional[str] = None,
        database: Optional[str] = None,
        migrations_path: Optional[Path] = None,
        use_transaction: bool = True,
        distance: Optional[int] = None,
        backward: bool = False,
        stream_output: bool = True,
    ):
        """
        Initialize migration manager

        Args:
            uri: MongoDB connection URI. If not provided, load from env.
            database: MongoDB database name. If not provided, load from env.
            migrations_path: Directory of migration files. Defaults to MIGRATIONS_DIR.
            use_transaction: Whether to use transactions (requires replica set).
            distance: Number of migrations to apply (positive integer).
            backward: Whether to perform rollback.
        """
        self.uri = uri or self._get_mongodb_uri()
        self.database = database or self._get_mongodb_database()
        self.migrations_path = migrations_path or self.MIGRATIONS_DIR
        self.use_transaction = use_transaction
        self.distance = distance
        self.backward = backward
        self.stream_output = stream_output

        if not self.uri:
            raise ValueError("MongoDB URI cannot be empty")
        if not self.database:
            raise ValueError("MongoDB database name cannot be empty")
        if not self.migrations_path:
            raise ValueError("Migrations path cannot be empty")

        self._ensure_migrations_dir()

    @staticmethod
    def _get_mongodb_uri() -> str:
        """Get MongoDB URI from environment variables"""
        base_uri = None
        if uri := os.getenv("MONGODB_URI"):
            base_uri = uri
        else:
            # Build URI from separate environment variables
            host = os.getenv("MONGODB_HOST", "localhost")
            port = os.getenv("MONGODB_PORT", "27017")
            username = os.getenv("MONGODB_USERNAME", "")
            password = os.getenv("MONGODB_PASSWORD", "")
            database = os.getenv("MONGODB_DATABASE", "memsys")

            if username and password:
                base_uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
            else:
                base_uri = f"mongodb://{host}:{port}/{database}"

        # 追加 URI 参数（如果有）
        uri_params = os.getenv("MONGODB_URI_PARAMS", "").strip()
        if uri_params:
            separator = '&' if ('?' in base_uri) else '?'
            return f"{base_uri}{separator}{uri_params}"
        return base_uri

    @staticmethod
    def _get_mongodb_database() -> str:
        """Get MongoDB database name from environment"""
        return os.getenv("MONGODB_DATABASE", "memsys")

    def _ensure_migrations_dir(self):
        """Ensure migrations directory exists"""
        self.migrations_path.mkdir(parents=True, exist_ok=True)

    def create_migration(self, migration_name: str) -> Path:
        """
        Create a new migration file

        Args:
            migration_name: Name of the migration

        Returns:
            Path to the created migration file

        Raises:
            FileExistsError: If migration file already exists
        """
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{migration_name}.py"
        filepath = self.migrations_path / filename

        # Check if file already exists
        if filepath.exists():
            raise FileExistsError(f"迁移文件已存在: {filepath}")

        # Generate migration content
        content = self.MIGRATION_TEMPLATE.format(
            description=migration_name.replace("_", " ").title(),
            created_at=datetime.now().isoformat(),
        )

        # Write file
        filepath.write_text(content, encoding='utf-8')
        logger.info(f"✅ 创建迁移文件: {filepath}")

        return filepath

    def run_migration(self) -> int:
        """
        Run migration using Beanie

        Returns:
            Exit code from Beanie command
        """
        # Build beanie args
        beanie_args = ["migrate"]
        if self.distance is not None:
            if self.distance <= 0:
                raise ValueError("Migration distance must be positive")
            beanie_args.extend(["--distance", str(self.distance)])
        if self.backward:
            beanie_args.append("--backward")
        if not self.use_transaction:
            beanie_args.append("--no-use-transaction")

        # Build complete command
        cmd = [
            "beanie",
            *beanie_args,
            "-uri",
            self.uri,
            "-db",
            self.database,
            "-p",
            str(self.migrations_path),
        ]

        logger.info(f"🚀 执行命令: {' '.join(cmd[3:])}")  # Hide python path
        logger.info(f"📍 数据库: {self.database}")
        logger.info(f"📁 迁移目录: {self.migrations_path}")

        # Snapshot migration logs before running
        before_names, before_current = self._snapshot_migration_log()
        if not before_names:
            logger.info("🧭 没有迁移记录，跳过迁移")
            return 0
        logger.info(f"🧭 迁移前记录数量: {len(before_names)}")
        logger.info(f"⭐ 迁移前当前指针: {before_current}")
        try:
            # Execute command
            if self.stream_output:
                # 将子进程输出重定向到当前进程的标准输出/错误，实时打印
                result = subprocess.run(
                    cmd,
                    check=True,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    text=True,
                    env=os.environ.copy(),
                )
                # 实时模式下输出已直接打印，此处无需再次记录 result.stdout/stderr
            else:
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=os.environ.copy(),
                )

                # Log buffered output at the end
                if result.stdout:
                    logger.info(result.stdout)
                if result.stderr:
                    logger.warning(result.stderr)

            # Snapshot and log diff after success
            self._log_migration_diff(before_names, before_current)
            return result.returncode

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 命令执行失败: {e}")
            if e.stdout:
                logger.info(f"标准输出: {e.stdout}")
            if e.stderr:
                logger.error(f"错误输出: {e.stderr}")
            # Snapshot and log diff even on failure (迁移可能部分执行)
            self._log_migration_diff(before_names, before_current)
            return e.returncode

        except FileNotFoundError:
            logger.error("❌ 找不到 beanie 命令，请确保已安装 beanie")
            logger.error("安装命令: pip install beanie")
            # Snapshot and log diff even if command not found (应无变化)
            self._log_migration_diff(before_names, before_current)
            return 1

    # ---------- Helper methods for migration log inspection ----------
    def _get_sync_mongo_client(self) -> MongoClient:
        """Create a short-lived sync MongoDB client for inspections."""
        return MongoClient(self.uri)

    def _read_migration_logs(self):
        """Read migrations_log documents sorted by ts ascending.

        Returns:
            Tuple[List[str], Optional[str]] | (None, None) if any error occurs.
        """
        try:
            with self._get_sync_mongo_client() as client:
                db = client[self.database]
                coll = db["migrations_log"]
                docs = list(
                    coll.find({}, {"_id": 0, "name": 1, "is_current": 1, "ts": 1}).sort(
                        "ts", 1
                    )
                )
                names = [d.get("name") for d in docs if d.get("name")]
                current = None
                for d in reversed(docs):
                    if d.get("is_current"):
                        current = d.get("name")
                        break
                return names, current
        except Exception as e:
            logger.warning("读取迁移日志失败: %s", str(e))
            return None, None

    def _snapshot_migration_log(self):
        """Wrapper to snapshot current migration log state."""
        names, current = self._read_migration_logs()
        if names is None:
            return None, None
        return set(names), current

    def _log_migration_diff(self, before_names, before_current) -> None:
        """Compare before/after migration log snapshots and print diffs."""
        after_names, after_current = self._snapshot_migration_log()
        if after_names is None:
            logger.info("🧭 无法读取迁移后日志快照")
            return

        logger.info("🧭 迁移后记录数量: %d", len(after_names))
        if after_current:
            logger.info("⭐ 迁移后当前指针: %s", after_current)
        else:
            logger.info("⭐ 迁移后当前指针: <无>")

        if before_names is None:
            return

        added = sorted(list(after_names - before_names))
        removed = sorted(list(before_names - after_names))

        if added:
            logger.info("✅ 新增执行脚本: %s", ", ".join(added))
        else:
            logger.info("✅ 新增执行脚本: <无>")

        if removed:
            logger.info("↩️ 回滚移除脚本: %s", ", ".join(removed))
        else:
            logger.info("↩️ 回滚移除脚本: <无>")

        if before_current != after_current:
            logger.info(
                "📍 当前指针变更: %s -> %s",
                before_current or "<无>",
                after_current or "<无>",
            )

    # ---------- Public utility for manual query ----------
    def get_migration_history(self):
        """Return full migration history from migrations_log (sorted by ts asc)."""
        try:
            with self._get_sync_mongo_client() as client:
                db = client[self.database]
                coll = db["migrations_log"]
                docs = list(
                    coll.find({}, {"_id": 0, "name": 1, "is_current": 1, "ts": 1}).sort(
                        "ts", 1
                    )
                )
                return docs
        except Exception as e:
            logger.warning("获取迁移历史失败: %s", str(e))
            return []

    def log_migration_history(self) -> None:
        """Log migration history and current pointer."""
        names, current = self._snapshot_migration_log()
        if names is None:
            logger.info("无法读取迁移历史")
            return
        logger.info("📜 已记录迁移脚本(%d): %s", len(names), ", ".join(sorted(names)))
        logger.info("⭐ 当前指针: %s", current or "<无>")
