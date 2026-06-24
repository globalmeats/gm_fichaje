"""Endpoints de administración: alta de empleados y reset de PIN (REQ-05).

El PIN inicial (y el regenerado en un reset) se devuelve EN CLARO una única vez para
que el administrador lo entregue; nunca se vuelve a poder recuperar.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.security import generate_pin, hash_pin
from app.core.time import utc_now
from app.db.models import TimePolicy, Worker
from app.schemas.policy import TimePolicyResponse, TimePolicyUpdate
from app.schemas.worker import WorkerCreate, WorkerCreatedResponse
from app.services.onboarding import create_employee

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/workers",
    response_model=WorkerCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_worker(
    body: WorkerCreate,
    claims: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> WorkerCreatedResponse:
    created = await create_employee(
        db,
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        created_by=uuid.UUID(claims["worker_id"]),
    )
    return WorkerCreatedResponse(
        id=created.id,
        employee_code=created.employee_code,
        role=created.role,
        pin=created.pin,
        pin_temporary=created.pin_temporary,
    )


@router.post("/workers/{worker_id}/reset-pin", response_model=WorkerCreatedResponse)
async def admin_reset_pin(
    worker_id: uuid.UUID,
    claims: dict = Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
) -> WorkerCreatedResponse:
    worker = await db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no existe.")

    new_pin = generate_pin(worker.code_norm)
    worker.pin_hash = hash_pin(new_pin)
    worker.pin_temporary = True  # fuerza cambio en el siguiente login
    worker.failed_attempts = 0
    worker.locked_until = None
    await db.commit()

    return WorkerCreatedResponse(
        id=str(worker.id),
        employee_code=worker.code,
        role=worker.role,
        pin=new_pin,
        pin_temporary=True,
    )


@router.get("/time-policy", response_model=TimePolicyResponse)
async def get_time_policy(
    claims: dict = Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
) -> TimePolicy:
    """Devuelve la política de tiempo vigente (singleton, REQ-13)."""
    policy = await db.get(TimePolicy, 1)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Política no inicializada."
        )
    return policy


@router.put("/time-policy", response_model=TimePolicyResponse)
async def update_time_policy(
    body: TimePolicyUpdate,
    claims: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> TimePolicy:
    """Actualiza la política (solo admin). Ajustable en runtime sin tocar código (REQ-13)."""
    policy = await db.get(TimePolicy, 1)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Política no inicializada."
        )

    fields = body.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(policy, key, value)
    policy.updated_at = utc_now()
    await db.commit()
    await db.refresh(policy)
    return policy
