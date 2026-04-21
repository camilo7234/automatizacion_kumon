from __future__ import annotations


"""
app/routes/upload.py
══════════════════════════════════════════════════════════════════
Sube el video, crea el ProcessingJob y dispara el pipeline.

FLUJO:
  1. Valida tamaño y extensión del archivo.
  2. Normaliza subject/test_code y verifica que exista TestTemplate activo.
  3. Crea Prospecto y ProcessingJob=queued.
  4. Guarda el video en uploads/videos/.
  5. Lanza ejecutar_pipeline(job_id) como BackgroundTask.
  6. Retorna JobStatusResponse inicial.
══════════════════════════════════════════════════════════════════
"""


import hashlib
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

# Directorio físico donde se guardan temporalmente los videos subidos.
# Evita duplicar "videos" cuando settings.UPLOAD_DIR ya viene como uploads/videos.
# Además, si settings.UPLOAD_DIR es relativo, lo resolvemos contra la raíz de backend.
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

    Este endpoint no procesa el video en línea:
    solo valida, guarda, encola el trabajo y retorna el estado inicial.
    """

    # ============================================================
    # BLOQUE 1: VALIDAR Y NORMALIZAR FORMULARIO
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

    # Reasignamos los valores normalizados que devuelve el schema.
    subject = form.subject
    test_code = form.test_code

    # ============================================================
    # BLOQUE 2: VALIDAR EXTENSIÓN DEL VIDEO
    # ============================================================
    ext = _get_extension(file.filename)

    # ALLOWED_VIDEO_EXTENSIONS suele venir como set/lista de extensiones:
    # por ejemplo {".mp4", ".avi", ".mov"}
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
    # BLOQUE 3: LEER ARCHIVO Y VALIDAR TAMAÑO
    # ============================================================
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)

    if size_mb > settings.MAX_VIDEO_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El archivo supera el tamaño máximo de "
                f"{settings.MAX_VIDEO_SIZE_MB} MB."
            ),
        )

    # ============================================================
    # BLOQUE 4: VALIDAR QUE EXISTA EL TEMPLATE ACTIVO
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
    # BLOQUE 5: CREAR EL PROSPECTO
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
    # BLOQUE 6: GUARDAR EL VIDEO EN DISCO
    # ============================================================
    video_filename = f"{prospecto.id_prospecto}_{test_code}.{ext}"
    video_path = UPLOAD_DIR.joinpath(video_filename)

    # Defensa extra: asegurar que la carpeta exista en tiempo de escritura.
    video_path.parent.mkdir(parents=True, exist_ok=True)

    with video_path.open("wb") as out:
        out.write(content)
        
    # ============================================================
    # BLOQUE 7: CALCULAR HASH MD5 DEL ARCHIVO
    # ============================================================
    file_hash = hashlib.md5(content).hexdigest()

    # ============================================================
    # BLOQUE 8: CREAR PROCESSINGJOB
    #
    # IMPORTANTE:
    # Este bloque ya está alineado con database/models.py.
    # NO usa subject, test_code, source_path ni source_hash.
    # ============================================================
    job = ProcessingJob(
        id_prospecto=prospecto.id_prospecto,
        id_template=template.id_template,
        source_type="video",
        file_path=str(video_path),
        file_name_original=file.filename,
        file_size_bytes=len(content),
        file_hash=file_hash,
        status="queued",
        progress_percent=0,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # ============================================================
    # BLOQUE 9: ENCOLAR EL PIPELINE EN SEGUNDO PLANO
    # ============================================================
    background_tasks.add_task(ejecutar_pipeline, job.id_job)

    # ============================================================
    # BLOQUE 10: RESPUESTA INICIAL AL FRONTEND
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
# FUNCION AUXILIAR: EXTRAER EXTENSIÓN DEL NOMBRE DE ARCHIVO
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
