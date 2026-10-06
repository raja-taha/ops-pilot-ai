from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ApiKey, DbSession
from app.schemas.incident import (
    AlertIngestRequest,
    ApprovalRequest,
    ApprovalResponse,
    IncidentDetail,
    IncidentSummary,
    ReportOut,
    ScenarioOut,
)
from app.services import incident_service
from app.services.scenarios import list_scenarios

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "ops-pilot-api",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/scenarios", response_model=list[ScenarioOut])
async def scenarios(_: ApiKey):
    return [
        ScenarioOut(
            id=s.id,
            title=s.title,
            service_name=s.service_name,
            severity=s.severity,
            description=s.description,
            expected_root_cause=s.expected_root_cause,
        )
        for s in list_scenarios()
    ]


@router.get("/incidents", response_model=list[IncidentSummary])
async def list_incidents(session: DbSession, _: ApiKey):
    return await incident_service.list_incidents(session)


@router.post(
    "/incidents",
    response_model=IncidentDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(payload: AlertIngestRequest, session: DbSession, _: ApiKey):
    incident = await incident_service.create_and_investigate(session, payload)
    return incident


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
async def get_incident(incident_id: UUID, session: DbSession, _: ApiKey):
    incident = await incident_service.get_incident(session, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/investigate", response_model=IncidentDetail)
async def reinvestigate(incident_id: UUID, session: DbSession, _: ApiKey):
    try:
        return await incident_service.investigate_existing(session, incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/incidents/{incident_id}/actions/{action_id}/decision",
    response_model=ApprovalResponse,
)
async def decide(
    incident_id: UUID,
    action_id: UUID,
    payload: ApprovalRequest,
    session: DbSession,
    _: ApiKey,
):
    try:
        action, incident = await incident_service.decide_action(
            session,
            incident_id,
            action_id,
            approved=payload.approved,
            decided_by=payload.decided_by,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    message = (
        "Action approved and synthetically executed"
        if payload.approved
        else "Action rejected — no operational change applied"
    )
    return ApprovalResponse(
        action=action,
        incident_status=incident.status,
        message=message,
    )


@router.get("/incidents/{incident_id}/report", response_model=ReportOut)
async def report(incident_id: UUID, session: DbSession, _: ApiKey):
    incident = await incident_service.get_incident(session, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not incident.report_markdown:
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return ReportOut(
        incident_id=incident.id,
        markdown=incident.report_markdown,
        generated_at=incident.updated_at,
    )
