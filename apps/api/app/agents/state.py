from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    incident_id: str
    title: str
    service_name: str
    severity: str
    scenario_id: str | None
    alert: dict[str, Any]
    plan: list[str]
    logs: list[dict[str, Any]]
    metrics: list[dict[str, Any]]
    deployments: list[dict[str, Any]]
    runbooks: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    primary_root_cause: str | None
    remediation_actions: list[dict[str, Any]]
    summary: str
    report_markdown: str
    evidence_bundle: dict[str, Any]
    trace: list[dict[str, Any]]
    errors: list[str]
