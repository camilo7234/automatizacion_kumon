from __future__ import annotations

"""
app/routes/upload.py
══════════════════════════════════════════════════════════════════
Sube el video, crea el ProcessingJob y dispara el pipeline.

FLUJO:
  1. Valida extensión del archivo (ANTES de leer contenido).
  2. Normaliza subject/test_code y verifica que exista TestTemplate activo.
  3. Crea Prospecto y ProcessingJob=queued.
  4. Guarda el video en uploads/videos/ mediante streaming por chunks.
     ★ FIX FASE 1: el video ya NO se carga completo en RAM.
       Se escribe chunk a chunk y se va contando el tamaño en vuelo.
       Si se supera MAX_VIDEO_SIZE_MB se aborta antes de terminar.
  5. Lanza ejecutar_pipeline(job_id) como BackgroundTask.
  6. Retorna JobStatusResponse inicial.

CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
  - BLOQUE 2 (extensión) se ejecuta ANTES de tocar el body.
  - BLOQUE 3 desaparece: content = await file.read() → eliminado.
  - El guardado en disco (BLOQUE 6) es ahora streaming con chunks de 1 MiB.
  - El hash MD5 (BLOQUE 7) se calcula incrementalmente durante el streaming.
  - El rollback de archivo parcial ante error se hace en finally.
══════════════════════════════════════════════════════════════════
"""

import hashlib
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import settings
from database.models import (
    ProcessingJob,
    Prospecto,
    TestTemplate,
)
from app.schemas.job import JobStatusResponse
from app.schemas.upload import VideoUploadForm
from app.services.processing_service import ejecutar_pipeline


# ================================================================
# CONFIGURACIÓN DEL ROUTER
# ================================================================
router = APIRouter(prefix="/api/v1/upload", tags=["upload"])

# Tamaño de cada chunk que se lee del stream de red (1 MiB).
# Lo suficientemente grande para ser eficiente, lo suficientemente
# pequeño para no saturar RAM en subidas concurrentes.
_CHUNK_SIZE = 1 * 1024 * 1024  # 1 MiB

# Directorio físico donde se guardan los videos subidos.
BASE_DIR = Path(__file__).resolve().parents[2]

_base_upload_dir = Path(settings.UPLOAD_DIR)
if not _base_upload_dir.is_absolute():
    _base_upload_dir = BASE_DIR / _base_upload_dir

UPLOAD_DIR = (
    _base_upload_dir
    if _base_upload_dir.name.lower() == "videos"
    else _base_upload_dir.joinpath("videos")
)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ================================================================
# ENDPOINT PRINCIPAL: SUBIDA DE VIDEO
# ================================================================
@router.post(
    "/video",
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject: str = Form(...),
    test_code: str = Form(...),
    nombre_completo: str = Form("Sin nombre"),
    grado_escolar: Optional[str] = Form(None),
    nombre_escuela: Optional[str] = Form(None),
    nombre_acudiente: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Sube un video de prueba diagnóstica y crea un ProcessingJob.

    El video se escribe en disco por chunks de 1 MiB: en ningún momento
    el contenido completo reside en RAM, lo que permite subidas concurrentes
    de archivos grandes sin agotar la memoria del servidor.
    """

    # ============================================================
    # BLOQUE 1: VALIDAR EXTENSIÓN (antes de leer cualquier byte)
    # ============================================================
    ext = _get_extension(file.filename)
    allowed_exts = {e.lower() for e in settings.ALLOWED_VIDEO_EXTENSIONS}

    if f".{ext}" not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato de video no permitido: .{ext}. "
                f"Permitidos: {', '.join(sorted(allowed_exts))}"
            ),
        )

    # ============================================================
    # BLOQUE 2: VALIDAR Y NORMALIZAR FORMULARIO
    # ============================================================
    form = VideoUploadForm(
        subject=subject,
        test_code=test_code,
        nombre_completo=nombre_completo,
        grado_escolar=grado_escolar,
        nombre_escuela=nombre_escuela,
        nombre_acudiente=nombre_acudiente,
        telefono=telefono,
    )
    subject = form.subject
    test_code = form.test_code

    # ============================================================
    # BLOQUE 3: VALIDAR QUE EXISTA EL TEMPLATE ACTIVO
    # ============================================================
    template = (
        db.query(TestTemplate)
        .filter(
            TestTemplate.subject == subject,
            TestTemplate.code == test_code,
            TestTemplate.active.is_(True),
        )
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No existe template activo para {subject}/{test_code}.",
        )

    # ============================================================
    # BLOQUE 4: CREAR EL PROSPECTO
    # ============================================================
    prospecto = Prospecto(
        id_prospecto=uuid4(),
        nombre_completo=form.nombre_completo,
        grado_escolar=form.grado_escolar,
        nombre_escuela=form.nombre_escuela,
        nombre_acudiente=form.nombre_acudiente,
        telefono=form.telefono,
    )
    db.add(prospecto)
    db.flush()

    # ============================================================
    # BLOQUE 5: GUARDAR VIDEO EN DISCO (STREAMING — sin RAM completa)
    #
    # ★ CORRECCIÓN FASE 1 — crítico de performance:
    #   Antes: content = await file.read()  → todo en RAM de golpe.
    #   Ahora: leemos chunks de 1 MiB y los escribimos directamente a disco.
    #
    # GARANTÍAS:
    #   • Si el archivo supera MAX_VIDEO_SIZE_MB se lanza 413 y se borra
    #     el archivo parcial (bloque except).
    #   • El hash MD5 se calcula de forma incremental: mismo resultado
    #     que antes, cero costo extra de memoria.
    #   • Si ocurre cualquier otro error de I/O el except también limpia.
    # ============================================================
    video_filename = f"{prospecto.id_prospecto}_{test_code}.{ext}"
    video_path = UPLOAD_DIR / video_filename
    video_path.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024
    bytes_written = 0
    md5 = hashlib.md5()

    try:
        with video_path.open("wb") as out:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    # Abortar: supera el límite configurado.
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"El archivo supera el tamaño máximo de "
                            f"{settings.MAX_VIDEO_SIZE_MB} MB."
                        ),
                    )
                md5.update(chunk)
                out.write(chunk)
    except HTTPException:
        # Limpiar archivo parcial antes de propagar el 413.
        if video_path.exists():
            os.remove(video_path)
        raise
    except Exception as exc:
        # Error inesperado de I/O: limpiar y propagar.
        if video_path.exists():
            os.remove(video_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el video en disco.",
        ) from exc

    file_hash = md5.hexdigest()

    # ============================================================
    # BLOQUE 6: CREAR PROCESSINGJOB
    # ============================================================
    job = ProcessingJob(
        id_prospecto=prospecto.id_prospecto,
        id_template=template.id_template,
        source_type="video",
        file_path=str(video_path),
        file_name_original=file.filename,
        file_size_bytes=bytes_written,
        file_hash=file_hash,
        status="queued",
        progress_percent=0,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # ============================================================
    # BLOQUE 7: ENCOLAR EL PIPELINE EN SEGUNDO PLANO
    # ============================================================
    background_tasks.add_task(ejecutar_pipeline, job.id_job)

    # ============================================================
    # BLOQUE 8: RESPUESTA INICIAL AL FRONTEND
    # ============================================================
    return JobStatusResponse(
        job_id=job.id_job,
        status=job.status,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        result_id=None,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# ================================================================
# FUNCIÓN AUXILIAR: EXTRAER EXTENSIÓN DEL NOMBRE DE ARCHIVO
# ================================================================
def _get_extension(filename: Optional[str]) -> str:
    """
    Devuelve la extensión del archivo en minúsculas sin el punto.

    Ejemplos:
      "video.MP4" -> "mp4"
      "clase.mov" -> "mov"
      None        -> ""
      "archivo"   -> ""
    """
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()