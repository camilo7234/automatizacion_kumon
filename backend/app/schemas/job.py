"""
app/schemas/job.py
══════════════════════════════════════════════════════════════════
Schemas del estado de un ProcessingJob.
Usado en:
  - POST /api/v1/upload/video   → retorna JobStatusResponse
  - GET  /api/v1/jobs/{job_id}  → retorna JobStatusResponse
══════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, UUID4, field_validator


class JobStatusResponse(BaseModel):
    """
    Respuesta estándar del estado de un job de procesamiento.
    Es el único schema de job que usa la API (ProcessingJobResponse fue descartado).
    """

    job_id: UUID4
    status: str = Field(
        description="queued | processing | done | error | manual_review"
    )
    progress_percent: int = Field(
        ge=0,
        le=100,
        description="Progreso del pipeline 0-100"
    )
    error_message: Optional[str] = None
    result_id: Optional[str] = None   # UUID del TestResult cuando status=done
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("result_id", mode="before")
    @classmethod
    def normalize_result_id(cls, value):
        if value is None:
            return None
        return str(value)

    model_config = {"from_attributes": True}