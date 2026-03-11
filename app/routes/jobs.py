# ============================================================
# BLOQUE 1 — Imports
# Router para consultar estado de jobs de procesamiento
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.job import JobStatusResponse
from config.database import get_db
from database.models import ProcessingJob, Prospecto, Student

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


# ============================================================
# BLOQUE 2 — Helper: obtener nombre del sujeto del job
# Centraliza la lógica de buscar nombre sea prospecto o estudiante
# Evita duplicar esta lógica en cada endpoint
# ============================================================
def obtener_nombre_sujeto(job: ProcessingJob) -> str:
    """
    Retorna el nombre del sujeto del job.
    Puede ser un prospecto (nombre_completo) o
    un estudiante matriculado (full_name via property).
    """
    if job.prospecto:
        return job.prospecto.nombre_completo
    elif job.student:
        return job.student.full_name
    return "Desconocido"


# ============================================================
# BLOQUE 3 — GET /api/v1/jobs/{job_id}
# Consulta el estado actual de un job de procesamiento
# El frontend llama este endpoint cada 5 segundos (polling)
# hasta que status sea "done", "error" o "manual_review"
# ============================================================
@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Retorna el estado actual de un job de procesamiento.
    Incluye progreso, errores si los hay, y result_id cuando termina.
    """
    # Buscar el job cargando las relaciones necesarias
    job = db.query(ProcessingJob).filter(
        ProcessingJob.id_job == job_id
    ).first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job no encontrado: {job_id}"
        )

    # Obtener result_id solo si el job terminó exitosamente
    result_id = None
    if job.is_done and job.result:
        result_id = str(job.result.id_result)

    return JobStatusResponse(
        job_id=str(job.id_job),
        status=job.status,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        result_id=result_id,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# ============================================================
# BLOQUE 4 — GET /api/v1/jobs/{job_id}/detail
# Detalle completo del job incluyendo nombre del sujeto
# Útil para el panel del orientador — muestra a quién pertenece
# ============================================================
@router.get("/{job_id}/detail", tags=["jobs"])
async def get_job_detail(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Retorna información completa del job incluyendo datos
    del estudiante o prospecto asociado.
    """
    job = db.query(ProcessingJob).filter(
        ProcessingJob.id_job == job_id
    ).first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job no encontrado: {job_id}"
        )

    # Obtener nombre del template
    template_info = None
    if job.template:
        template_info = {
            "code": job.template.code,
            "subject": job.template.subject,
            "display_name": job.template.display_name,
        }

    return {
        "job_id": str(job.id_job),
        "status": job.status,
        "progress_percent": job.progress_percent,
        "error_message": job.error_message,
        "source_type": job.source_type,
        "file_name_original": job.file_name_original,
        "tipo_origen": "prospecto" if job.is_prospecto else "estudiante",
        "nombre_sujeto": obtener_nombre_sujeto(job),
        "template": template_info,
        "result_id": str(job.result.id_result) if job.is_done and job.result else None,
        "duration_seconds": job.duration_seconds,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }
