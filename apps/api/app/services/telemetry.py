"""Telemetry tool layer — synthetic by default, Prometheus-ready interface."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.services.scenarios import Scenario, get_scenario, list_scenarios


class TelemetryClient:
    async def query_logs(
        self, service_name: str, scenario_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def query_metrics(
        self, service_name: str, scenario_id: str | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def query_deployments(
        self, service_name: str, scenario_id: str | None = None
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class SyntheticTelemetryClient(TelemetryClient):
    def _scenario(self, service_name: str, scenario_id: str | None) -> Scenario | None:
        if scenario_id:
            return get_scenario(scenario_id)
        for s in list_scenarios():
            if s.service_name == service_name:
                return s
        return None

    async def query_logs(
        self, service_name: str, scenario_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        scenario = self._scenario(service_name, scenario_id)
        if not scenario:
            return []
        return scenario.logs[:limit]

    async def query_metrics(
        self, service_name: str, scenario_id: str | None = None
    ) -> list[dict[str, Any]]:
        scenario = self._scenario(service_name, scenario_id)
        if not scenario:
            return []
        return scenario.metrics

    async def query_deployments(
        self, service_name: str, scenario_id: str | None = None
    ) -> list[dict[str, Any]]:
        scenario = self._scenario(service_name, scenario_id)
        if not scenario:
            return []
        return scenario.deployments


class PrometheusTelemetryClient(TelemetryClient):
    """Thin adapter — falls back to synthetic if Prometheus unreachable."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.fallback = SyntheticTelemetryClient()

    async def query_metrics(
        self, service_name: str, scenario_id: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.settings.prometheus_url}/api/v1/query",
                    params={"query": f'up{{job="{service_name}"}}'},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("data", {}).get("result", [])
                return [
                    {
                        "name": "up",
                        "value": float(r["value"][1]),
                        "unit": "bool",
                        "labels": r.get("metric", {}),
                    }
                    for r in results
                ]
        except Exception:
            return await self.fallback.query_metrics(service_name, scenario_id)

    async def query_logs(
        self, service_name: str, scenario_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        # Loki optional; synthetic fallback keeps demos reliable
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.settings.loki_url}/loki/api/v1/query_range",
                    params={
                        "query": f'{{service="{service_name}"}}',
                        "limit": str(limit),
                    },
                )
                resp.raise_for_status()
                return [{"raw": resp.json()}]
        except Exception:
            return await self.fallback.query_logs(service_name, scenario_id, limit)

    async def query_deployments(
        self, service_name: str, scenario_id: str | None = None
    ) -> list[dict[str, Any]]:
        return await self.fallback.query_deployments(service_name, scenario_id)


def get_telemetry_client() -> TelemetryClient:
    settings = get_settings()
    if settings.telemetry_mode == "prometheus":
        return PrometheusTelemetryClient()
    return SyntheticTelemetryClient()
