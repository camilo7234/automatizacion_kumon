# ============================================================
# BLOQUE 1 — Imports
# Schema para consultar el estado de un job de procesamiento
# ============================================================
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ============================================================
# BLOQUE 2 — JobStatusResponse
# Respuesta al consultar GET /api/v1/jobs/{job_id}
# El frontend hace polling a este endpoint cada 5 segundos
# hasta que status sea "done" o "error"
# ============================================================
class JobStatusResponse(BaseModel):
    """
    Estado actual de un job de procesamiento.
    """
    job_id: str = Field(..., description="UUID del job")
    status: str = Field(
        ...,
        description="queued | processing | done | error | manual_review"
    )
    progress_percent: int = Field(
        0,
        ge=0,
        le=100,
        description="Porcentaje de avance 0-100"
    )
    error_message: Optional[str] = Field(
        None,
        description="Mensaje de error si status=error"
    )
    result_id: Optional[str] = Field(
        None,
        description="UUID del resultado cuando status=done"
    )
    started_at: Optional[datetime] = Field(
        None,
        description="Cuándo empezó a procesarse"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="Cuándo terminó el procesamiento"
    )

    class Config:
        from_attributes = True
