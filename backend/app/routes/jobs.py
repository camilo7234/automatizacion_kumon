from __future__ import annotations

"""
app/routes/jobs.py
══════════════════════════════════════════════════════════════════
Consulta el estado de un ProcessingJob para polling en frontend.
══════════════════════════════════════════════════════════════════
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from app.schemas.job import JobStatusResponse
from app.services.processing_service import get_job_status

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    estado = get_job_status(job_id, db)
    if not estado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job no encontrado.",
        )

    # Normalizar result_id a string para evitar error de validación
    # cuando el servicio devuelve UUID y el schema espera Optional[str].
    if estado.get("result_id") is not None:
        estado["result_id"] = str(estado["result_id"])

    return JobStatusResponse(**estado)