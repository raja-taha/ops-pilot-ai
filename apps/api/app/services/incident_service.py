from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.workflow import run_incident_agent
from app.core.logging import get_logger
from app.models.incident import (
    ActionStatus,
    ActionType,
    AuditLog,
    Hypothesis,
    Incident,
    IncidentStatus,
    RemediationAction,
    TimelineEvent,
)
from app.schemas.incident import AlertIngestRequest
from app.services.redis_state import append_trace_step, set_incident_state
from app.services.scenarios import resolve_scenario_from_alert

logger = get_logger("incident_service")


def _incident_options():
    return [
        selectinload(Incident.hypotheses),
        selectinload(Incident.actions),
        selectinload(Incident.timeline),
        selectinload(Incident.audit_logs),
    ]


async def list_incidents(session: AsyncSession) -> list[Incident]:
    result = await session.execute(
        select(Incident).order_by(Incident.created_at.desc())
    )
    return list(result.scalars().all())


async def get_incident(session: AsyncSession, incident_id: UUID) -> Incident | None:
    result = await session.execute(
        select(Incident).options(*_incident_options()).where(Incident.id == incident_id)
    )
    return result.scalar_one_or_none()


async def create_and_investigate(
    session: AsyncSession, payload: AlertIngestRequest
) -> Incident:
    scenario = resolve_scenario_from_alert(
        payload.service_name, payload.alert, payload.scenario_id
    )
    title = payload.title or scenario.title
    service_name = payload.service_name or scenario.service_name
    alert = {**scenario.alert, **payload.alert}

    incident = Incident(
        title=title,
        alert_payload=alert,
        service_name=service_name,
        severity=payload.severity or scenario.severity,
        status=IncidentStatus.INVESTIGATING,
        scenario_id=scenario.id if scenario.id != "custom-alert" else payload.scenario_id,
    )
    session.add(incident)
    await session.flush()

    session.add(
        AuditLog(
            incident_id=incident.id,
            actor="system",
            action="incident.created",
            details={"title": title, "service_name": service_name},
        )
    )

    if payload.auto_investigate:
        await _run_investigation(session, incident)
    else:
        await session.flush()

    return await get_incident(session, incident.id)  # type: ignore[return-value]


async def investigate_existing(session: AsyncSession, incident_id: UUID) -> Incident:
    incident = await get_incident(session, incident_id)
    if not incident:
        raise ValueError("Incident not found")
    incident.status = IncidentStatus.INVESTIGATING
    await _run_investigation(session, incident)
    return await get_incident(session, incident.id)  # type: ignore[return-value]


async def _run_investigation(session: AsyncSession, incident: Incident) -> None:
    # Delete via SQL — never touch lazy-loaded relationships in async sessions
    # (accessing incident.hypotheses triggers sync IO → MissingGreenlet).
    await session.execute(
        delete(Hypothesis).where(Hypothesis.incident_id == incident.id)
    )
    await session.execute(
        delete(RemediationAction).where(RemediationAction.incident_id == incident.id)
    )
    await session.execute(
        delete(TimelineEvent).where(TimelineEvent.incident_id == incident.id)
    )
    await session.flush()

    state = await run_incident_agent(
        session,
        incident_id=str(incident.id),
        title=incident.title,
        service_name=incident.service_name,
        severity=incident.severity,
        alert=incident.alert_payload,
        scenario_id=incident.scenario_id,
    )

    for event in state.get("timeline", []):
        session.add(
            TimelineEvent(
                incident_id=incident.id,
                event_time=event["event_time"],
                source=event["source"],
                kind=event["kind"],
                message=event["message"],
                metadata_json=event.get("metadata") or {},
            )
        )

    for hyp in state.get("hypotheses", []):
        session.add(
            Hypothesis(
                incident_id=incident.id,
                rank=hyp.get("rank", 1),
                title=hyp["title"],
                description=hyp["description"],
                evidence_score=hyp["evidence_score"],
                confidence=hyp.get("confidence", hyp["evidence_score"]),
                supporting_evidence=hyp.get("supporting_evidence") or [],
                contradicting_evidence=hyp.get("contradicting_evidence") or [],
                critic_notes=hyp.get("critic_notes"),
                is_primary=bool(hyp.get("is_primary")),
            )
        )

    for action in state.get("remediation_actions", []):
        session.add(
            RemediationAction(
                incident_id=incident.id,
                action_type=ActionType(action["action_type"]),
                title=action["title"],
                description=action["description"],
                target_service=action["target_service"],
                payload=action.get("payload") or {},
                rollback_plan=action["rollback_plan"],
                risk_level=action.get("risk_level", "medium"),
                status=ActionStatus.PROPOSED,
                requires_approval=True,
            )
        )

    incident.summary = state.get("summary")
    incident.root_cause = state.get("primary_root_cause")
    incident.report_markdown = state.get("report_markdown")
    incident.agent_trace = {"steps": state.get("trace", []), "errors": state.get("errors", [])}
    incident.evidence_bundle = state.get("evidence_bundle") or {}
    incident.status = IncidentStatus.AWAITING_APPROVAL

    session.add(
        AuditLog(
            incident_id=incident.id,
            actor="agent",
            action="investigation.completed",
            details={
                "root_cause": incident.root_cause,
                "hypotheses": len(state.get("hypotheses", [])),
                "actions": len(state.get("remediation_actions", [])),
            },
        )
    )
    await session.flush()

    # Redis is best-effort — investigation must still succeed if Redis is down
    try:
        await set_incident_state(
            incident.id,
            {
                "status": incident.status.value,
                "root_cause": incident.root_cause,
                "steps": state.get("trace", []),
            },
        )
        for step in state.get("trace", []):
            await append_trace_step(incident.id, step)
    except Exception as exc:
        logger.warning("redis_state_failed", error=str(exc), incident_id=str(incident.id))

    logger.info(
        "investigation_complete",
        incident_id=str(incident.id),
        root_cause=incident.root_cause,
    )


async def decide_action(
    session: AsyncSession,
    incident_id: UUID,
    action_id: UUID,
    *,
    approved: bool,
    decided_by: str,
    notes: str | None,
) -> tuple[RemediationAction, Incident]:
    incident = await get_incident(session, incident_id)
    if not incident:
        raise ValueError("Incident not found")

    action = next((a for a in incident.actions if a.id == action_id), None)
    if not action:
        raise ValueError("Action not found")
    if action.status != ActionStatus.PROPOSED:
        raise ValueError(f"Action already in status {action.status.value}")

    action.decided_by = decided_by
    action.decision_notes = notes

    if not approved:
        action.status = ActionStatus.REJECTED
        session.add(
            AuditLog(
                incident_id=incident.id,
                actor=decided_by,
                action="remediation.rejected",
                details={"action_id": str(action.id), "notes": notes},
            )
        )
        await session.flush()
        return action, incident

    # Approval gate passed — execute simulated operational action
    action.status = ActionStatus.APPROVED
    incident.status = IncidentStatus.REMEDIATING
    session.add(
        AuditLog(
            incident_id=incident.id,
            actor=decided_by,
            action="remediation.approved",
            details={"action_id": str(action.id), "notes": notes},
        )
    )
    await session.flush()

    result = await execute_action_safe(action)
    action.execution_result = result
    action.executed_at = datetime.now(timezone.utc)
    if result.get("ok"):
        action.status = ActionStatus.EXECUTED
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        session.add(
            AuditLog(
                incident_id=incident.id,
                actor="executor",
                action="remediation.executed",
                details={"action_id": str(action.id), "result": result},
            )
        )
    else:
        action.status = ActionStatus.FAILED
        incident.status = IncidentStatus.FAILED
        session.add(
            AuditLog(
                incident_id=incident.id,
                actor="executor",
                action="remediation.failed",
                details={"action_id": str(action.id), "result": result},
            )
        )

    try:
        await set_incident_state(
            incident.id,
            {"status": incident.status.value, "last_action": str(action.id)},
        )
    except Exception as exc:
        logger.warning("redis_state_failed", error=str(exc), incident_id=str(incident.id))
    await session.flush()
    return action, incident


async def execute_action_safe(action: RemediationAction) -> dict:
    """Simulate write operations. Never touches real infrastructure."""
    # Hard safety: only approved actions reach here, and execution is sandboxed.
    return {
        "ok": True,
        "mode": "synthetic",
        "action_type": action.action_type.value,
        "target_service": action.target_service,
        "payload": action.payload,
        "message": (
            f"Synthetic execution of {action.action_type.value} on "
            f"{action.target_service} succeeded. No real cluster mutation performed."
        ),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
