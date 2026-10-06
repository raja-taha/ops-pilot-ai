"""Initialize schema and seed runbooks / demo data."""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models import (  # noqa: F401
    AuditLog,
    Hypothesis,
    Incident,
    RemediationAction,
    RunbookChunk,
    TimelineEvent,
)
from app.services.runbooks import ensure_runbooks_seeded

logger = get_logger("seed")


async def reset_schema() -> None:
    """Drop and recreate tables (local/dev only)."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("DROP TABLE IF EXISTS audit_logs CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS timeline_events CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS remediation_actions CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS hypotheses CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS incidents CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS runbook_chunks CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS incident_status CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS action_type CASCADE"))
        await conn.execute(text("DROP TYPE IF EXISTS action_status CASCADE"))
        await conn.run_sync(Base.metadata.create_all)


async def init_db(*, reset: bool = False) -> None:
    configure_logging(get_settings().debug)
    if reset:
        await reset_schema()
    else:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        count = await ensure_runbooks_seeded(session)
        await session.commit()
        logger.info("seed_complete", runbooks_inserted=count)


if __name__ == "__main__":
    reset = os.getenv("RESET_DB", "").lower() in {"1", "true", "yes"} or (
        len(os.sys.argv) > 1 and os.sys.argv[1] == "--reset"
    )
    asyncio.run(init_db(reset=reset))
