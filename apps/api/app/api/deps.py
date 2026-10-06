from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_api_key
from app.db.session import get_db
from app.services import incident_service

DbSession = Annotated[AsyncSession, Depends(get_db)]
ApiKey = Annotated[str, Depends(require_api_key)]


async def get_incident_or_404(session: DbSession, incident_id: UUID):
    incident = await incident_service.get_incident(session, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident
