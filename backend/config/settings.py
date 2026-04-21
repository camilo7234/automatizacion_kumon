#C:\Users\camil\OneDrive\Escritorio\automatizacion_kumon\backend\config\settings.py

from pydantic_settings import BaseSettings
from pathlib import Path


# backend/
BASE_DIR = Path(__file__).resolve().parent.parent

# automatizacion_kumon/  (raíz del proyecto)
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    # Base de datos
    DATABASE_URL: str

    # Seguridad
    SECRET_KEY: str = "dev_secret_key"

    # Procesamiento de video
    MAX_VIDEO_SIZE_MB: int = 500
    OCR_CONFIDENCE_MIN: float = 0.75
    SPEECH_RATE_UMBRAL_BAJO: float = 1.5
    PAUSA_LARGA_MS: int = 8000

    # Cámara frontal
    ENABLE_FACE_ANALYSIS: bool = False

    # Rutas relativas a backend/
    UPLOAD_DIR: str = "uploads/videos"
    PROCESSED_DIR: str = "uploads/processed"

    # Entorno
    ENVIRONMENT: str = "development"

    # Extensiones de video permitidas
    ALLOWED_VIDEO_EXTENSIONS: set = {".mp4", ".avi", ".mov"}

    # Materias válidas
    VALID_SUBJECTS: set = {"matematicas", "ingles", "espanol"}

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

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


settings = Settings()

# Crear carpetas de uploads al importar
settings.upload_path.mkdir(parents=True, exist_ok=True)
settings.processed_path.mkdir(parents=True, exist_ok=True)
