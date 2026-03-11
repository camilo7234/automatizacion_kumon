# ============================================================
# BLOQUE 1 — Exportaciones del módulo routes
# Registrar aquí cada nuevo router que se cree
# ============================================================
from app.routes.upload import router as upload_router
from app.routes.jobs import router as jobs_router

__all__ = ["upload_router", "jobs_router"]
