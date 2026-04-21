"""
app/schemas/result.py
══════════════════════════════════════════════════════════════════
Schemas del resultado cuantitativo de un test.
Usado en:
  - GET /api/v1/results/{result_id}
  - GET /api/v1/results/job/{job_id}
══════════════════════════════════════════════════════════════════
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, UUID4, Field, field_validator


class TestResultResponse(BaseModel):
    """
    Respuesta completa de un resultado de test.

    Combina:
      - Datos cuantitativos (OCR Class Navi)
      - Metadatos del sujeto
      - Estado del formulario cualitativo

    DISEÑO:
      - Tipos estrictos para contrato API
      - Tolerancia a floats/Decimal desde backend
      - Sin valores mutables compartidos
    """

    # ──────────────────────────────────────────────────────────
    # Identificadores
    # ──────────────────────────────────────────────────────────
    id_result: UUID4
    id_job: UUID4

    # ──────────────────────────────────────────────────────────
    # Sujeto
    # ──────────────────────────────────────────────────────────
    tipo_sujeto: str
    nombre_sujeto: str

    # ──────────────────────────────────────────────────────────
    # Template
    # ──────────────────────────────────────────────────────────
    subject: str
    test_code: str
    display_name: str

    # ──────────────────────────────────────────────────────────
    # Datos Class Navi (OCR)
    # ──────────────────────────────────────────────────────────
    test_date: Optional[date] = None
    ws: Optional[str] = None

    study_time_min: Optional[Decimal] = None
    target_time_min: Optional[Decimal] = None

    correct_answers: Optional[int] = None
    total_questions: Optional[int] = None
    percentage: Optional[Decimal] = None

    # ──────────────────────────────────────────────────────────
    # Cálculos backend
    # ──────────────────────────────────────────────────────────
    current_level: Optional[str] = None
    starting_point: Optional[str] = None
    semaforo: Optional[str] = None
    recommendation: Optional[str] = None

    # ──────────────────────────────────────────────────────────
    # Confianza OCR
    # ──────────────────────────────────────────────────────────
    confidence_score: Optional[Decimal] = None
    needs_manual_review: bool = False

    # ──────────────────────────────────────────────────────────
    # Datos crudos
    # ──────────────────────────────────────────────────────────
    sections_detail: Dict[str, Any] = Field(default_factory=dict)
    raw_ocr_data: Dict[str, Any] = Field(default_factory=dict)

    # ──────────────────────────────────────────────────────────
    # Estado cualitativo
    # ──────────────────────────────────────────────────────────
    tiene_observacion: bool = False
    observacion_completa: bool = False

    # ──────────────────────────────────────────────────────────
    # Metadata
    # ──────────────────────────────────────────────────────────
    created_at: datetime

    # ──────────────────────────────────────────────────────────
    # Normalización de tipos (robustez)
    # ──────────────────────────────────────────────────────────
    @field_validator(
        "study_time_min",
        "target_time_min",
        "percentage",
        "confidence_score",
        mode="before",
    )
    @classmethod
    def normalize_decimal(cls, value):
        if value is None:
            return None
        return Decimal(str(value))

    model_config = {"from_attributes": True}