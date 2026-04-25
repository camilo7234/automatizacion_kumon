# backend/config/settings.py
"""
config/settings.py
══════════════════════════════════════════════════════════════════
Configuración centralizada con Pydantic Settings.
Todos los valores sensibles DEBEN venir del archivo .env —
ninguno tiene un default inseguro hardcodeado.

CAMBIOS FASE 1 — Archivo 3/4:
  1. SECRET_KEY sin default: si no está en .env el servidor no
     arranca (ValueError explícito). Antes tenía "dev_secret_key"
     lo que significaba que en producción sin .env la app corría
     con una clave pública conocida.
  2. Nuevo campo DEBUG: controla logging verboso y Swagger UI.
     En producción (DEBUG=False) se deshabilita /docs y /redoc.
  3. Nuevo campo ALLOWED_HOSTS para TrustedHostMiddleware.
  4. model_config reemplaza la clase Config interna (Pydantic v2).
  5. validator startup_check: valida invariantes críticas al
     importar — falla rápido si el entorno está mal configurado.
  6. Propiedad docs_url / redoc_url: retorna None en producción
     para que FastAPI no exponga OpenAPI al público.
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/
BASE_DIR = Path(__file__).resolve().parent.parent

# automatizacion_kumon/  (raíz del proyecto)
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    """
    Todas las variables de entorno de la aplicación.

    Las variables SIN valor default son OBLIGATORIAS: si no existen
    en .env o en el entorno del proceso, Pydantic lanza un error
    claro antes de que arranque cualquier servidor.
    """

    # ── Base de datos ─────────────────────────────────────────────
    DATABASE_URL: str  # obligatoria — sin default

    # ── Seguridad ─────────────────────────────────────────────────
    # ★ CORRECCIÓN FASE 1:
    #   Ya NO tiene default "dev_secret_key".
    #   Si DATABASE_URL existe pero SECRET_KEY no, la app no arranca.
    #   Para generar una clave segura ejecuta:
    #     python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str  # obligatoria — sin default

    # ── Entorno ───────────────────────────────────────────────────
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = False  # True solo en desarrollo — deshabilita /docs en producción

    # ── CORS / Hosts ──────────────────────────────────────────────
    # Hosts adicionales permitidos, separados por coma.
    # En producción: ALLOWED_HOSTS=mi-dominio.com,www.mi-dominio.com
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"

    # Origins CORS adicionales (además de localhost:5500/127.0.0.1:5500).
    # En producción: CORS_EXTRA_ORIGINS=https://app.mi-dominio.com
    CORS_EXTRA_ORIGINS: str = ""

    # ── Procesamiento de video ────────────────────────────────────
    MAX_VIDEO_SIZE_MB: int = Field(default=500, gt=0, le=2000)
    OCR_CONFIDENCE_MIN: float = Field(default=0.75, ge=0.0, le=1.0)
    SPEECH_RATE_UMBRAL_BAJO: float = Field(default=1.5, gt=0.0)
    PAUSA_LARGA_MS: int = Field(default=8000, gt=0)

    # ── Cámara frontal (stub futuro) ──────────────────────────────
    ENABLE_FACE_ANALYSIS: bool = False

    # ── Rutas relativas a backend/ ────────────────────────────────
    UPLOAD_DIR: str = "uploads/videos"
    PROCESSED_DIR: str = "uploads/processed"

    # ── Extensiones y materias ────────────────────────────────────
    ALLOWED_VIDEO_EXTENSIONS: set = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    VALID_SUBJECTS: set = {"matematicas", "ingles", "espanol"}

    # ── Pydantic v2 config (reemplaza clase Config interna) ───────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # DATABASE_URL y database_url son equivalentes
        extra="ignore",         # Variables extra en .env no causan error
    )

    # ── Validadores ───────────────────────────────────────────────

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        """
        Rechaza claves débiles o vacías.
        Mínimo 32 caracteres para garantizar entropía suficiente
        con cualquier algoritmo de firma (HMAC-SHA256, etc.).
        """
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY debe tener al menos 32 caracteres. "
                "Genera una con: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Blacklist de valores conocidos inseguros
        _WEAK = {"dev_secret_key", "secret", "changeme", "password", "supersecret"}
        if v.lower() in _WEAK:
            raise ValueError(
                f"SECRET_KEY usa un valor inseguro conocido ('{v}'). "
                "Genera una clave aleatoria y ponla en tu .env."
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("DATABASE_URL no puede estar vacía.")
        return v

    @model_validator(mode="after")
    def warn_if_debug_in_production(self) -> "Settings":
        """
        Avisa (y en el futuro puede bloquear) si DEBUG está activo
        en un entorno de producción.
        """
        if self.ENVIRONMENT == "production" and self.DEBUG:
            import warnings
            warnings.warn(
                "⚠️  DEBUG=True en ENVIRONMENT=production. "
                "Deshabilita DEBUG en producción para ocultar /docs y /redoc.",
                stacklevel=2,
            )
        return self

    # ── Rutas calculadas ──────────────────────────────────────────

    @property
    def upload_path(self) -> Path:
        """uploads/videos/ dentro de backend/"""
        return BASE_DIR / self.UPLOAD_DIR

    @property
    def processed_path(self) -> Path:
        """uploads/processed/ dentro de backend/"""
        return BASE_DIR / self.PROCESSED_DIR

    @property
    def frontend_path(self) -> Path:
        """frontend/ en la raíz del proyecto (fuera de backend/)"""
        return PROJECT_ROOT / "frontend"

    @property
    def max_video_size_bytes(self) -> int:
        return self.MAX_VIDEO_SIZE_MB * 1024 * 1024

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Lista de hosts permitidos para TrustedHostMiddleware."""
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """
        Lista completa de origins CORS permitidos.
        Combina los base (localhost:5500) con los de CORS_EXTRA_ORIGINS.
        """
        base = [
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:3000",
            "http://localhost:8080",
        ]
        extra = [o.strip() for o in self.CORS_EXTRA_ORIGINS.split(",") if o.strip()]
        return base + extra

    @property
    def openapi_url(self) -> Optional[str]:
        """Expone /openapi.json solo en desarrollo."""
        return "/openapi.json" if self.DEBUG else None

    @property
    def docs_url(self) -> Optional[str]:
        """Expone /docs (Swagger UI) solo en desarrollo."""
        return "/docs" if self.DEBUG else None

    @property
    def redoc_url(self) -> Optional[str]:
        """Expone /redoc solo en desarrollo."""
        return "/redoc" if self.DEBUG else None


# ── Instancia singleton ───────────────────────────────────────────
# Si .env no tiene SECRET_KEY o DATABASE_URL, esto lanza un error
# claro ANTES de que arranque uvicorn. Falla rápido y con mensaje útil.
settings = Settings()

# Crear carpetas de uploads al importar (idempotente).
settings.upload_path.mkdir(parents=True, exist_ok=True)
settings.processed_path.mkdir(parents=True, exist_ok=True)