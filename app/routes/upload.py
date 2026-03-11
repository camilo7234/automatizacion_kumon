# ============================================================
# BLOQUE 1 — Imports
# Router para recibir archivos de video y PDF de tests Kumon
# ============================================================
import hashlib
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.schemas.upload import ProcessingJobResponse
from config.database import get_db
from config.settings import settings
from database.models import ProcessingJob, Student, TestTemplate

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])


# ============================================================
# BLOQUE 2 — Helper: calcular hash MD5 del archivo
# Evita reprocesar el mismo video dos veces
# Se calcula en chunks para no cargar todo en memoria RAM
# ============================================================
def calcular_hash_md5(file_bytes: bytes) -> str:
    """Calcula hash MD5 de los bytes del archivo."""
    return hashlib.md5(file_bytes).hexdigest()


# ============================================================
# BLOQUE 3 — Helper: guardar archivo en disco temporalmente
# Los videos se guardan en uploads/videos/ con nombre UUID
# Se eliminan después de procesar para no acumular espacio
# ============================================================
def guardar_archivo_temporal(file_bytes: bytes, extension: str, job_id: str) -> str:
    """
    Guarda el archivo en uploads/videos/ y retorna la ruta.
    El nombre del archivo es el job_id para trazabilidad.
    """
    carpeta = os.path.join(settings.UPLOAD_FOLDER, "videos")
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, f"{job_id}.{extension}")
    with open(ruta, "wb") as f:
        f.write(file_bytes)
    return ruta


# ============================================================
# BLOQUE 4 — Helper: validar formato del archivo
# Solo acepta los formatos definidos en settings
# ============================================================
def obtener_extension(filename: str) -> str:
    """
    Extrae y valida la extensión del archivo.
    Lanza HTTPException si el formato no está permitido.
    """
    if "." not in filename:
        raise HTTPException(
            status_code=400,
            detail="El archivo no tiene extensión válida"
        )
    ext = filename.rsplit(".", 1)[-1].lower()
    formatos_permitidos = settings.ALLOWED_VIDEO_FORMATS.split(",")
    if ext not in formatos_permitidos:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no permitido: .{ext}. Permitidos: {formatos_permitidos}"
        )
    return ext


# ============================================================
# BLOQUE 5 — Endpoint POST /api/v1/upload/video
# Recibe video, valida, crea ProcessingJob con status=queued
# NO procesa el video aquí — solo lo encola
# El procesamiento OCR vendrá después de forma asíncrona
# ============================================================
@router.post("/video", response_model=ProcessingJobResponse)
async def upload_video(
    estudiante_id: str = Form(..., description="UUID del estudiante"),
    subject: str = Form(..., description="Materia: matematicas, ingles, espanol"),
    test_code: str = Form(..., description="Código del test: K1, P1, M1, H, etc."),
    file: UploadFile = File(..., description="Archivo de video .mp4 .avi .mov"),
    db: Session = Depends(get_db),
):
    """
    Recibe un video de grabación de pantalla de Kumon Connect.
    Valida el archivo, lo guarda temporalmente y crea un job en cola.
    Retorna el job_id para que el frontend consulte el estado.
    """
    # --- Validar formato del archivo ---
    extension = obtener_extension(file.filename)

    # --- Leer bytes del archivo ---
    file_bytes = await file.read()

    # --- Validar tamaño máximo ---
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.MAX_VIDEO_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande: {size_mb:.1f}MB. Máximo: {settings.MAX_VIDEO_SIZE_MB}MB"
        )

    # --- Validar que el estudiante existe en la BD ---
    try:
        estudiante_uuid = uuid.UUID(estudiante_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"estudiante_id no es un UUID válido: {estudiante_id}"
        )

    estudiante = db.query(Student).filter(
        Student.id_estudiante == estudiante_uuid,
        Student.estado == "activo"
    ).first()

    if not estudiante:
        raise HTTPException(
            status_code=404,
            detail=f"Estudiante no encontrado o inactivo: {estudiante_id}"
        )

    # --- Validar que el template existe para ese test_code y subject ---
    subject_normalizado = subject.lower().strip()
    test_code_normalizado = test_code.upper().strip()

    template = db.query(TestTemplate).filter(
        TestTemplate.code == test_code_normalizado,
        TestTemplate.subject == subject_normalizado,
        TestTemplate.active == True
    ).first()

    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"No existe template para: code={test_code_normalizado}, subject={subject_normalizado}"
        )

    # --- Calcular hash y verificar duplicados ---
    file_hash = calcular_hash_md5(file_bytes)

    job_duplicado = db.query(ProcessingJob).filter(
        ProcessingJob.file_hash == file_hash,
        ProcessingJob.status == "done"
    ).first()

    if job_duplicado:
        raise HTTPException(
            status_code=409,
            detail=f"Este video ya fue procesado. Job existente: {job_duplicado.id_job}"
        )

    # --- Crear el job y guardar archivo ---
    nuevo_job_id = str(uuid.uuid4())
    ruta_archivo = guardar_archivo_temporal(file_bytes, extension, nuevo_job_id)

    nuevo_job = ProcessingJob(
        id_job=uuid.UUID(nuevo_job_id),
        id_estudiante=estudiante_uuid,
        id_template=template.id_template,
        source_type="video",
        file_path=ruta_archivo,
        file_name_original=file.filename,
        file_size_bytes=len(file_bytes),
        file_hash=file_hash,
        status="queued",
        progress_percent=0,
    )

    db.add(nuevo_job)
    db.commit()
    db.refresh(nuevo_job)

    return ProcessingJobResponse(
        job_id=str(nuevo_job.id_job),
        status=nuevo_job.status,
        message=f"Video recibido. En cola para procesar. Estudiante: {estudiante.full_name}",
        created_at=nuevo_job.created_at,
    )
