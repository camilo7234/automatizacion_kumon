"""
app/schemas/cuestionario.py
══════════════════════════════════════════════════════════════════
Schemas del formulario cualitativo del orientador.
Usado en:
  - GET  /api/v1/cuestionario/{result_id}  → CuestionarioResponse
  - POST /api/v1/cuestionario/{result_id}  → CuestionarioSubmitResponse
  - GET  /api/v1/boletin/{result_id}       → BoletinResponse
══════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, UUID4, Field, field_validator


# ── GET /api/v1/cuestionario/{result_id} ─────────────────────────


class CuestionarioResponse(BaseModel):
    """
    Devuelve el formulario cualitativo con la estructura declarativa
    del cuestionario, junto con prefills y banderas automáticas si existen.

    - cuestionario: dict con escala, secciones, prefills y auto_flags.
    - prefill_flags: lista de claves detectadas automáticamente.
    """

    result_id: UUID4
    subject: str
    test_code: str
    cuestionario: Dict[str, Any] = Field(
        description="Estructura completa del formulario cualitativo"
    )
    ya_completado: bool = False
    tiene_prefills: bool = False
    prefill_flags: List[str] = Field(
        default_factory=list,
        description="Claves de métricas ya capturadas automáticamente por el sistema",
    )

    model_config = {"from_attributes": True}


# ── POST /api/v1/cuestionario/{result_id} — Request ──────────────


class RespuestaCuestionarioRequest(BaseModel):
    """
    Body del POST del formulario cualitativo.

    respuestas admite dos formas de entrada:

    1) Anidada por sección y métrica:
      {
        "postura": {
          "motivacion": 4,
          "concentracion": 3
        },
        "habilidad_suma": {
          "velocidad_respuesta": 2
        }
      }

    2) Plana por clave de métrica:
      {
        "motivacion": 4,
        "concentracion": 3,
        "velocidad_respuesta": 2
      }

    El validador normaliza ambas formas a un dict plano por métrica.
    """

    respuestas: Dict[str, Any]
    completado_por: str = Field(min_length=2, description="Nombre del orientador")
    observacion_libre: Optional[str] = None

    @field_validator("respuestas", mode="before")
    @classmethod
    def normalizar_respuestas(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict) or not v:
            raise ValueError("respuestas no puede estar vacío")

        normalizadas: Dict[str, Any] = {}

        for key, value in v.items():
            if isinstance(value, dict) and "valor" in value:
                normalizadas[key] = value
                continue

            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    normalizadas[subkey] = subvalue
            else:
                normalizadas[key] = value

        if not normalizadas:
            raise ValueError("respuestas no puede estar vacío")

        return normalizadas

    @field_validator("completado_por")
    @classmethod
    def normalizar_orientador(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("completado_por debe tener al menos 2 caracteres")
        return v

    @field_validator("observacion_libre")
    @classmethod
    def normalizar_observacion_libre(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


# ── POST /api/v1/cuestionario/{result_id} — Response ─────────────


class SeccionPuntaje(BaseModel):
    """Puntaje de una sección individual del formulario."""

    id: str
    nombre: str
    puntaje: float = Field(ge=0, le=100)
    etiqueta: str
    preguntas: int = Field(ge=0)


class CuestionarioSubmitResponse(BaseModel):
    """
    Respuesta después de completar el formulario cualitativo.

    Escala de etiqueta_total:
      76-100 → fortaleza
      51-75  → en_desarrollo
      26-50  → refuerzo
       0-25  → atencion
    """

    observacion_id: Optional[UUID4] = None
    result_id: UUID4
    total_porcentaje: float = Field(ge=0, le=100)
    etiqueta_total: str
    secciones: List[SeccionPuntaje]
    boletin_habilitado: bool = True
    message: str = "Cuestionario cualitativo guardado correctamente."

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ── GET /api/v1/boletin/{result_id} ──────────────────────────────


class BoletinResponse(BaseModel):
    """
    Datos consolidados del boletín.

    La respuesta expone los bloques principales del informe:
      - cuantitativo
      - cualitativo
      - combinado
      - gaze
    """

    boletin_id: Optional[UUID4] = None
    result_id: UUID4
    subject: str
    test_code: str
    status: str = "ready"
    generated_at: Optional[datetime] = None
    cuantitativo: Dict[str, Any] = Field(default_factory=dict)
    cualitativo: Dict[str, Any] = Field(default_factory=dict)
    combinado: Dict[str, Any] = Field(default_factory=dict)
    gaze: Optional[Dict[str, Any]] = None
    message: str = "Boletín generado correctamente."

    model_config = {"from_attributes": True}
