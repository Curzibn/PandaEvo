from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.database import engine
from app.logger import get_logger

logger = get_logger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"
_LOCK_ID = 7481265


@dataclass
class MigrationFile:
    version: str
    description: str
    path: Path
    up_sql: str
    checksum: str


async def ensure_schema_migrations_table(conn: AsyncConnection) -> None:
    await conn.execute(
        text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(64) NOT NULL PRIMARY KEY,
                description VARCHAR(255) NOT NULL DEFAULT '',
                checksum VARCHAR(64) NOT NULL DEFAULT '',
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    )


async def acquire_lock(conn: AsyncConnection) -> bool:
    result = await conn.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": _LOCK_ID})
    row = result.scalar_one()
    return bool(row)


async def release_lock(conn: AsyncConnection) -> None:
    await conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": _LOCK_ID})


def load_migration_files() -> list[MigrationFile]:
    if not _MIGRATIONS_DIR.exists():
        logger.warning(f"Migration directory not found: {_MIGRATIONS_DIR}")
        return []

    migrations = []
    pattern = re.compile(r"^(\d{14})_(.+)\.sql$")

    for file_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        match = pattern.match(file_path.name)
        if not match:
            logger.warning(f"Skipping invalid migration file: {file_path.name}")
            continue

        version = match.group(1)
        description = match.group(2).replace("_", " ")

        try:
            content = file_path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

            up_match = re.search(r"-- migrate:up\s+(.*?)(?=\s*-- migrate:down|$)", content, re.DOTALL)
            if not up_match:
                logger.warning(f"No '-- migrate:up' section found in {file_path.name}")
                continue

            up_sql = up_match.group(1).strip()
            if not up_sql:
                logger.warning(f"Empty '-- migrate:up' section in {file_path.name}")
                continue

            migrations.append(
                MigrationFile(
                    version=version,
                    description=description,
                    path=file_path,
                    up_sql=up_sql,
                    checksum=checksum,
                )
            )
        except Exception as e:
            logger.error(f"Failed to parse migration file {file_path.name}: {e}", exc_info=True)
            continue

    logger.info(f"Loaded {len(migrations)} migration file(s)")
    return migrations


async def get_applied_versions(conn: AsyncConnection) -> dict[str, dict[str, Any]]:
    result = await conn.execute(
        text("SELECT version, description, checksum, applied_at FROM schema_migrations ORDER BY version")
    )
    rows = result.fetchall()
    return {row.version: {"description": row.description, "checksum": row.checksum, "applied_at": row.applied_at} for row in rows}


async def execute_migration(conn: AsyncConnection, migration: MigrationFile) -> None:
    logger.info(f"Applying migration {migration.version}: {migration.description}")

    statements = [s.strip() for s in migration.up_sql.split(";") if s.strip()]
    if not statements:
        logger.warning(f"No SQL statements found in migration {migration.version}")
        return

    for i, statement in enumerate(statements, 1):
        try:
            await conn.execute(text(statement))
            logger.debug(f"Executed statement {i}/{len(statements)} of migration {migration.version}")
        except Exception as e:
            logger.error(f"Failed to execute statement {i}/{len(statements)} of migration {migration.version}: {e}")
            logger.error(f"Statement: {statement[:200]}...")
            raise

    await conn.execute(
        text("""
            INSERT INTO schema_migrations (version, description, checksum)
            VALUES (:version, :description, :checksum)
        """),
        {
            "version": migration.version,
            "description": migration.description,
            "checksum": migration.checksum,
        },
    )
    logger.info(f"Successfully applied migration {migration.version}")


async def run_migrations() -> None:
    logger.info("Starting database migrations")

    async with engine.begin() as conn:
        if not await acquire_lock(conn):
            logger.error("Failed to acquire migration lock, another migration may be running")
            raise RuntimeError("Migration lock acquisition failed")

        await ensure_schema_migrations_table(conn)

        migration_files = load_migration_files()
        if not migration_files:
            logger.info("No migration files found")
            return

        applied = await get_applied_versions(conn)
        logger.info(f"Found {len(applied)} already applied migration(s)")

        for migration in migration_files:
            if migration.version in applied:
                applied_info = applied[migration.version]
                if applied_info["checksum"] != migration.checksum:
                    logger.warning(
                        f"Migration {migration.version} ({migration.description}) checksum mismatch: "
                        f"database has {applied_info['checksum'][:8]}..., file has {migration.checksum[:8]}..."
                    )

        pending = [m for m in migration_files if m.version not in applied]
        if not pending:
            logger.info("All migrations are already applied")
            return

        logger.info(f"Found {len(pending)} pending migration(s)")

        for migration in pending:
            await execute_migration(conn, migration)

        logger.info(f"Successfully applied {len(pending)} migration(s)")
