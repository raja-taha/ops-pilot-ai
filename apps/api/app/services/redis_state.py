from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


def _key(incident_id: UUID | str) -> str:
    return f"incident:{incident_id}:state"


async def set_incident_state(incident_id: UUID | str, state: dict[str, Any], ttl: int = 86400) -> None:
    client = get_redis()
    await client.set(_key(incident_id), json.dumps(state), ex=ttl)


async def get_incident_state(incident_id: UUID | str) -> dict[str, Any] | None:
    client = get_redis()
    raw = await client.get(_key(incident_id))
    if not raw:
        return None
    return json.loads(raw)


async def append_trace_step(incident_id: UUID | str, step: dict[str, Any]) -> dict[str, Any]:
    state = await get_incident_state(incident_id) or {"steps": []}
    steps = state.setdefault("steps", [])
    steps.append(step)
    await set_incident_state(incident_id, state)
    return state


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
