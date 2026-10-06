"""Background worker — polls Redis for incident state heartbeats / future job queue."""

from __future__ import annotations

import asyncio
import os
import signal

import redis.asyncio as redis
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger("worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_running = True


def _stop(*_args):
    global _running
    _running = False


async def main() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    client = redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("worker_started", redis=REDIS_URL)
    while _running:
        try:
            keys = await client.keys("incident:*:state")
            await client.set("opspilot:worker:heartbeat", str(len(keys)), ex=30)
            logger.info("heartbeat", active_incidents=len(keys))
        except Exception as exc:
            logger.warning("worker_loop_error", error=str(exc))
        await asyncio.sleep(10)
    await client.aclose()
    logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
