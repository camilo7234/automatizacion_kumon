# ============================================================
# BLOQUE 1 — Imports y validadores base
# Schema para la solicitud de subida de video/PDF
# ============================================================
from pydantic import BaseModel, UUID4, Field, field_validator
from typing import Optional
from datetime import datetime


# ============================================================
# BLOQUE 2 — UploadVideoRequest
# Valida los datos que llegan junto al archivo en el POST
# El archivo en sí viene como UploadFile, no aquí
# ============================================================
class UploadVideoRequest(BaseModel):
    """
    Datos requeridos al subir un video o PDF de test.
    El archivo binario se recibe por separado como Form/File.
    """
    estudiante_id: UUID4 = Field(
        ...,
        description="UUID del estudiante en admin.estudiantes"
    )
    subject: str = Field(
        ...,
        description="Materia: matematicas, ingles, espanol"
    )
    test_code: str = Field(
        ...,
        description="Código del nivel: K1, K2, P1, P2, M1, H, etc."
    )

    @field_validator("subject")
    @classmethod
    def validar_subject(cls, v: str) -> str:
        # Normalizar a minúsculas y validar
        v = v.lower().strip()
        permitidas = {"matematicas", "ingles", "espanol"}
        if v not in permitidas:
            raise ValueError(f"Materia inválida. Opciones: {permitidas}")
        return v

    @field_validator("test_code")
    @classmethod
    def validar_test_code(cls, v: str) -> str:
        # Normalizar a mayúsculas
        return v.upper().strip()


# ============================================================
# BLOQUE 3 — ProcessingJobResponse
# Lo que la API retorna después de recibir el archivo
# El frontend usa job_id para hacer polling del estado
# ============================================================
class ProcessingJobResponse(BaseModel):
    """
    Respuesta inmediata al subir un archivo.
    Retorna el job_id para que el frontend consulte el estado.
    """
    job_id: str = Field(..., description="UUID del job creado")
    status: str = Field(..., description="Estado inicial: queued")
    message: str = Field(..., description="Mensaje descriptivo")
    created_at: datetime = Field(..., description="Timestamp de creación")

    class Config:
        # Permite crear este schema desde un objeto ORM directamente
        from_attributes = True
