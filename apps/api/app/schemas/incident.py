from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.incident import ActionStatus, ActionType, IncidentStatus


class AlertIngestRequest(BaseModel):
    title: str | None = None
    service_name: str | None = None
    severity: str = "high"
    alert: dict[str, Any] = Field(default_factory=dict)
    scenario_id: str | None = Field(
        default=None,
        description="Optional synthetic scenario id, e.g. payment-latency-spike",
    )
    auto_investigate: bool = True


class HypothesisOut(BaseModel):
    id: UUID
    rank: int
    title: str
    description: str
    evidence_score: float
    confidence: float
    supporting_evidence: list[Any]
    contradicting_evidence: list[Any]
    critic_notes: str | None
    is_primary: bool

    model_config = {"from_attributes": True}


class RemediationActionOut(BaseModel):
    id: UUID
    action_type: ActionType
    title: str
    description: str
    target_service: str
    payload: dict[str, Any]
    rollback_plan: str
    risk_level: str
    status: ActionStatus
    requires_approval: bool
    decided_by: str | None
    decision_notes: str | None
    executed_at: datetime | None
    execution_result: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class TimelineEventOut(BaseModel):
    id: UUID
    event_time: datetime
    source: str
    kind: str
    message: str
    metadata_json: dict[str, Any] = Field(validation_alias="metadata_json")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditLogOut(BaseModel):
    id: UUID
    actor: str
    action: str
    details: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentSummary(BaseModel):
    id: UUID
    title: str
    service_name: str
    severity: str
    status: IncidentStatus
    summary: str | None
    root_cause: str | None
    scenario_id: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class IncidentDetail(IncidentSummary):
    alert_payload: dict[str, Any]
    report_markdown: str | None
    agent_trace: dict[str, Any]
    evidence_bundle: dict[str, Any]
    hypotheses: list[HypothesisOut]
    actions: list[RemediationActionOut]
    timeline: list[TimelineEventOut]
    audit_logs: list[AuditLogOut]


class ApprovalRequest(BaseModel):
    approved: bool
    decided_by: str = "oncall-engineer"
    notes: str | None = None


class ApprovalResponse(BaseModel):
    action: RemediationActionOut
    incident_status: IncidentStatus
    message: str


class ScenarioOut(BaseModel):
    id: str
    title: str
    service_name: str
    severity: str
    description: str
    expected_root_cause: str


class ReportOut(BaseModel):
    incident_id: UUID
    markdown: str
    generated_at: datetime
