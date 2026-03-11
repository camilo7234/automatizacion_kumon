# ============================================================
# BLOQUE 1 — Exportaciones del módulo schemas
# Importar aquí facilita usar: from app.schemas import X
# en lugar de from app.schemas.upload import X
# ============================================================
from app.schemas.upload import UploadVideoRequest, ProcessingJobResponse
from app.schemas.job import JobStatusResponse

__all__ = [
    "UploadVideoRequest",
    "ProcessingJobResponse",
    "JobStatusResponse",
]
