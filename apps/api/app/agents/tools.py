from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.runbooks import retrieve_runbooks
from app.services.telemetry import get_telemetry_client


async def tool_query_logs(
    service_name: str, scenario_id: str | None = None
) -> list[dict[str, Any]]:
    client = get_telemetry_client()
    return await client.query_logs(service_name, scenario_id)


async def tool_query_metrics(
    service_name: str, scenario_id: str | None = None
) -> list[dict[str, Any]]:
    client = get_telemetry_client()
    return await client.query_metrics(service_name, scenario_id)


async def tool_query_deployments(
    service_name: str, scenario_id: str | None = None
) -> list[dict[str, Any]]:
    client = get_telemetry_client()
    return await client.query_deployments(service_name, scenario_id)


async def tool_retrieve_runbooks(
    session: AsyncSession, query: str, service_name: str
) -> list[dict[str, Any]]:
    return await retrieve_runbooks(session, query=query, service_name=service_name, top_k=4)


# Write tools are intentionally NOT exposed to the autonomous agent.
WRITE_ACTIONS_REQUIRE_APPROVAL = {
    "restart",
    "rollback",
    "scale",
    "config_change",
    "drain",
    "feature_flag",
}
