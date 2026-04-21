"""
app/schemas/upload.py
══════════════════════════════════════════════════════════════════
Schema de entrada para POST /api/v1/upload/video.
Los campos llegan como Form fields (no JSON body) porque
el request incluye un archivo (UploadFile).
══════════════════════════════════════════════════════════════════
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class VideoUploadForm(BaseModel):
    """
    Datos del formulario de subida de video.
    Todos los campos son strings porque vienen de multipart/form-data.
    Las validaciones de subject y extensión se hacen en la ruta.
    """

    subject:          str = Field(description="matematicas | ingles | espanol")
    test_code:        str = Field(description="K1, K2, P1-P6, M1-M3, H, PII, PI, M")
    nombre_completo:  str = Field(default="Sin nombre", description="Nombre del prospecto")
    grado_escolar:    Optional[str] = None
    nombre_escuela:   Optional[str] = None
    nombre_acudiente: Optional[str] = None
    telefono:         Optional[str] = None

    @field_validator("subject")
    @classmethod
    def normalizar_subject(cls, v: str) -> str:
        """Normaliza a minúsculas y valida que sea una materia válida."""
        v = v.strip().lower()
        if v not in {"matematicas", "ingles", "espanol"}:
            raise ValueError("subject debe ser: matematicas | ingles | espanol")
        return v

    @field_validator("test_code")
    @classmethod
    def normalizar_test_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("nombre_completo")
    @classmethod
    def normalizar_nombre(cls, v: str) -> str:
        v = v.strip()
        return v if v else "Sin nombre"

    model_config = {"from_attributes": True}
