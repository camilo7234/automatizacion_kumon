# app/main.py
"""
app/main.py
══════════════════════════════════════════════════════════════════
Entrypoint de la aplicación FastAPI.

CAMBIOS FASE 1 — Archivo 2/4:
  1. CORS: eliminado "null" como origin permitido.
     Motivo: "null" permite peticiones desde file:// y data://,
     un vector de ataque real en producción. En desarrollo se
     controla con la variable de entorno CORS_EXTRA_ORIGINS.
  2. Security Headers: nuevo middleware TrustedHostMiddleware y
     cabeceras HTTP de seguridad estándar (X-Frame-Options,
     X-Content-Type-Options, Referrer-Policy, etc.).
  3. Logging: configuración mínima estructurada desde el arranque.
  4. Lifespan: migrado de @app.on_event("startup") deprecated
     a la API moderna lifespan (FastAPI 0.93+).
  5. Metadatos OpenAPI enriquecidos (descripción, contacto).
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.routes import upload, jobs, results, cuestionario
from app.services.ocr_service import initialize_ocr_reader

# ================================================================
# LOGGING
# Configura un formato mínimo pero legible desde el primer import.
# En producción, redirigir a un servicio de logs (Loki, CloudWatch…)
# cambiando el handler aquí o con uvicorn --log-config.
# ================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ================================================================
# CORS — ORIGINS PERMITIDOS
#
# ★ CORRECCIÓN FASE 1:
#   Se eliminó "null" de la lista de origins.
#   "null" es el origin que envían los navegadores cuando la
#   petición viene de file://, data:// o un sandbox iframe —
#   no tiene ningún uso legítimo en producción y expone la API
#   a ataques CSRF desde páginas HTML locales.
#
# En desarrollo local usa Live Server (127.0.0.1:5500) y ya está
# cubierto por las entradas siguientes.
# Para agregar origins adicionales sin tocar código, define la
# variable de entorno:
#   CORS_EXTRA_ORIGINS=http://mi-dominio.com,http://staging.com
# ================================================================
_base_origins: list[str] = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",   # React dev server (futuro)
    "http://localhost:8080",   # Vue dev server (futuro)
]

_extra = os.getenv("CORS_EXTRA_ORIGINS", "")
_extra_origins: list[str] = [o.strip() for o in _extra.split(",") if o.strip()]

ALLOWED_ORIGINS: list[str] = _base_origins + _extra_origins


# ================================================================
# LIFESPAN (reemplaza @app.on_event("startup") deprecado)
# ================================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Inicializa servicios globales al arrancar y los libera al cerrar.
    FastAPI ejecuta el bloque 'before yield' en startup y
    el bloque 'after yield' en shutdown.
    """
    logger.info("── Startup ─────────────────────────────────────────")
    logger.info("Inicializando EasyOCR reader…")
    initialize_ocr_reader()
    logger.info("EasyOCR listo.")
    logger.info("Origins CORS permitidos: %s", ALLOWED_ORIGINS)
    logger.info("────────────────────────────────────────────────────")
    yield
    logger.info("── Shutdown ────────────────────────────────────────")
    logger.info("Aplicación detenida limpiamente.")
    logger.info("────────────────────────────────────────────────────")


# ================================================================
# APLICACIÓN FASTAPI
# ================================================================
app = FastAPI(
    title="Automatización Kumon",
    description=(
        "API de procesamiento de pruebas diagnósticas Kumon. "
        "Sube un video, extrae métricas cuantitativas y cualitativas, "
        "calcula el semáforo de aprendizaje y genera el boletín PDF."
    ),
    version="0.1.0",
    contact={"name": "Camilo Rubio", "email": "soporte@kumon-automatizacion.local"},
    lifespan=lifespan,
)


# ================================================================
# MIDDLEWARE — ORDEN IMPORTANTE (se aplican de abajo hacia arriba)
# ================================================================

# ── ORDEN DE MIDDLEWARE (se aplican de abajo hacia arriba) ──────

# 1. TrustedHostMiddleware
_trusted_hosts_env = os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1")
_trusted_hosts: list[str] = [
    h.strip() for h in _trusted_hosts_env.split(",") if h.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts)

# 2. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# 3. Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"]  = "nosniff"
    response.headers["X-Frame-Options"]         = "DENY"
    response.headers["Referrer-Policy"]          = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]       = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ================================================================
# ROUTERS
# ================================================================
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(results.router)
app.include_router(cuestionario.router)


# ================================================================
# HEALTH CHECK  (útil para Docker, k8s, load balancers)
# ================================================================
@app.get("/health", tags=["infra"], include_in_schema=False)
async def health() -> dict:
    return {"status": "ok", "version": app.version}