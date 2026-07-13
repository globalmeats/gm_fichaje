"""Ausencias: vacaciones, bajas y permisos retribuidos + justificante de asistencia (REQ-28).

Alta y gestión SOLO admin/gestora (`ABSENCE_WRITE_ROLES`); el trabajador solo consulta lo suyo
(self) y descarga su propio justificante. Reutiliza el patrón de acceso self-vs-oversight de
`export.load_report`. El justificante se guarda CIFRADO (Fernet) y nunca se sirve en los
listados JSON, solo por descarga explícita.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_claims, get_db
from app.api.export import OVERSIGHT_ROLES
from app.core.crypto import decrypt_blob, encrypt_blob
from app.core.time import utc_now
from app.db.models import (
    JUSTIFICANTE_CONTENT_TYPES,
    MAX_JUSTIFICANTE_BYTES,
    Absence,
    AbsenceDocument,
    TimePolicy,
    Worker,
)
from app.domain.absences import absence_hours, overlaps, vacation_balance, vacation_days_taken
from app.domain.schedule import effective_vacation_days
from app.schemas.absence import (
    AbsenceCreate,
    AbsenceDocumentResponse,
    AbsenceResponse,
    VacationBalanceResponse,
)

router = APIRouter(prefix="/absences", tags=["absences"])

# Solo admin/gestora (y supervisor) dan de alta/gestionan ausencias (REQ-24).
ABSENCE_WRITE_ROLES = {"admin", "supervisor"}


def _require_write(claims: dict) -> None:
    if claims.get("role") not in ABSENCE_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo admin/gestora pueden gestionar ausencias.",
        )


def _resolve_target(claims: dict, worker_id: uuid.UUID | None) -> uuid.UUID:
    """Self vs oversight: el empleado solo accede a lo suyo; oversight a cualquiera."""
    own = uuid.UUID(claims["worker_id"])
    target = worker_id or own
    if target != own and claims.get("role") not in OVERSIGHT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para ver las ausencias de otro trabajador.",
        )
    return target


async def _doc_absence_ids(db: AsyncSession, absence_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not absence_ids:
        return set()
    rows = (
        await db.execute(
            select(AbsenceDocument.absence_id).where(
                AbsenceDocument.absence_id.in_(absence_ids)
            )
        )
    ).scalars().all()
    return set(rows)


def _to_response(absence: Absence, *, has_document: bool) -> AbsenceResponse:
    return AbsenceResponse(
        id=absence.id,
        worker_id=absence.worker_id,
        absence_type=absence.absence_type,
        subtype=absence.subtype,
        start_date=absence.start_date,
        end_date=absence.end_date,
        start_time=absence.start_time,
        end_time=absence.end_time,
        status=absence.status,
        justified=absence.justified,
        note=absence.note,
        hours=absence_hours(absence),
        has_document=has_document,
    )


@router.post("", response_model=AbsenceResponse, status_code=status.HTTP_201_CREATED)
async def create_absence(
    body: AbsenceCreate,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> AbsenceResponse:
    _require_write(claims)

    worker = await db.get(Worker, body.worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no existe.")

    existing = (
        await db.execute(select(Absence).where(Absence.worker_id == body.worker_id))
    ).scalars().all()
    if overlaps(body.start_date, body.end_date, body.start_time, body.end_time, list(existing)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La ausencia solapa con otra ya registrada del trabajador.",
        )

    absence = Absence(
        worker_id=body.worker_id,
        absence_type=body.absence_type,
        subtype=body.subtype,
        start_date=body.start_date,
        end_date=body.end_date,
        start_time=body.start_time,
        end_time=body.end_time,
        status=body.status,
        note=body.note,
        created_by=uuid.UUID(claims["worker_id"]),
    )
    db.add(absence)
    await db.commit()
    await db.refresh(absence)
    return _to_response(absence, has_document=False)


@router.get("", response_model=list[AbsenceResponse])
async def list_absences(
    worker_id: uuid.UUID | None = None,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> list[AbsenceResponse]:
    target = _resolve_target(claims, worker_id)
    rows = (
        await db.execute(
            select(Absence)
            .where(Absence.worker_id == target)
            .order_by(Absence.start_date.desc())
        )
    ).scalars().all()
    with_doc = await _doc_absence_ids(db, [a.id for a in rows])
    return [_to_response(a, has_document=a.id in with_doc) for a in rows]


@router.post("/{absence_id}/cancel", response_model=AbsenceResponse)
async def cancel_absence(
    absence_id: uuid.UUID,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> AbsenceResponse:
    _require_write(claims)
    absence = await db.get(Absence, absence_id)
    if absence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ausencia no existe.")
    absence.status = "cancelada"
    absence.updated_at = utc_now()
    await db.commit()
    await db.refresh(absence)
    with_doc = await _doc_absence_ids(db, [absence.id])
    return _to_response(absence, has_document=absence.id in with_doc)


@router.post(
    "/{absence_id}/justificante",
    response_model=AbsenceDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_justificante(
    absence_id: uuid.UUID,
    file: UploadFile = File(...),
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> AbsenceDocumentResponse:
    """Adjunta el justificante de ASISTENCIA (cifrado) y marca la ausencia como justificada.

    Solo se admiten justificantes de asistencia (PDF/JPG/PNG); nunca informes con diagnóstico.
    """
    _require_write(claims)
    absence = await db.get(Absence, absence_id)
    if absence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ausencia no existe.")

    if file.content_type not in JUSTIFICANTE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo no admitido: {file.content_type}. Solo PDF/JPG/PNG.",
        )
    data = await file.read()
    if not data or len(data) > MAX_JUSTIFICANTE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El justificante está vacío o supera el tamaño máximo (5 MB).",
        )

    doc = AbsenceDocument(
        absence_id=absence_id,
        filename=file.filename or "justificante",
        content_type=file.content_type,
        byte_size=len(data),
        content_encrypted=encrypt_blob(data),
        uploaded_by=uuid.UUID(claims["worker_id"]),
    )
    db.add(doc)
    absence.justified = True
    absence.verified_by = uuid.UUID(claims["worker_id"])
    absence.updated_at = utc_now()
    await db.commit()
    await db.refresh(doc)
    return AbsenceDocumentResponse.model_validate(doc)


@router.get("/{absence_id}/justificante/{doc_id}")
async def download_justificante(
    absence_id: uuid.UUID,
    doc_id: uuid.UUID,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> Response:
    absence = await db.get(Absence, absence_id)
    if absence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ausencia no existe.")
    # Acceso: el dueño (self) o un rol de supervisión.
    own = uuid.UUID(claims["worker_id"])
    if absence.worker_id != own and claims.get("role") not in OVERSIGHT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para descargar este justificante.",
        )
    doc = await db.get(AbsenceDocument, doc_id)
    if doc is None or doc.absence_id != absence_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Justificante no existe.")

    content = decrypt_blob(doc.content_encrypted)
    return Response(
        content=content,
        media_type=doc.content_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )


@router.get("/me/balance", response_model=VacationBalanceResponse)
async def my_vacation_balance(
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> VacationBalanceResponse:
    worker_id = uuid.UUID(claims["worker_id"])
    return await vacation_balance_for(db, worker_id)


async def vacation_balance_for(
    db: AsyncSession, worker_id: uuid.UUID
) -> VacationBalanceResponse:
    """Saldo de vacaciones del año en curso (autodisponibilidad, REQ-18)."""
    worker = await db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no existe.")
    policy = await db.get(TimePolicy, 1)
    absences = (
        await db.execute(select(Absence).where(Absence.worker_id == worker_id))
    ).scalars().all()
    year = utc_now().year
    taken = vacation_days_taken(list(absences), year)
    entitled = effective_vacation_days(worker, policy)
    bal = vacation_balance(entitled, taken)
    return VacationBalanceResponse(
        year=year, entitled=bal["entitled"], taken=bal["taken"], remaining=bal["remaining"]
    )
