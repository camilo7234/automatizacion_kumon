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

# Fragmentos técnicos que nunca deben llegar al frontend.
_TECHNICAL_PATTERNS = (
    "traceback",
    "sqlalchemy",
    "psycopg",
    "operationalerror",
    "file \"",
    "/home/",
    "/usr/",
    "/app/",
    "stack trace",
    "exception",
)

_GENERIC_ERROR = "El procesamiento falló. Intenta de nuevo o contacta al administrador."


def _sanitize_error(message: str | None) -> str | None:
    """
    Devuelve un mensaje genérico si el texto contiene información técnica
    que no debe exponerse al usuario final.
    El mensaje original se conserva en logs del servidor (no aquí).
    """
    if message is None:
        return None
    lower = message.lower()
    if any(pattern in lower for pattern in _TECHNICAL_PATTERNS):
        return _GENERIC_ERROR
    return message


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

    # Sanitizar error_message antes de exponer al frontend.
    estado["error_message"] = _sanitize_error(estado.get("error_message"))

    return JobStatusResponse(**estado)