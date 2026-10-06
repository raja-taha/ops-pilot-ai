"""Initialize schema and seed runbooks / demo data."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models import AuditLog, Hypothesis, Incident, RemediationAction, RunbookChunk, TimelineEvent  # noqa: F401
from app.services.runbooks import ensure_runbooks_seeded

logger = get_logger("seed")


async def init_db() -> None:
    configure_logging(get_settings().debug)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        count = await ensure_runbooks_seeded(session)
        await session.commit()
        logger.info("seed_complete", runbooks_inserted=count)


if __name__ == "__main__":
    asyncio.run(init_db())
