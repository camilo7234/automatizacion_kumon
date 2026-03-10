# config/settings.py
# Configuracion central de la aplicacion
# Lee variables de entorno desde .env automaticamente
# ============================================================

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # Aplicacion
    APP_NAME: str = "automatizacion_kumon"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Base de datos
    # El .env sobreescribe este valor automaticamente
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/automatizacion_kumon"
    DATABASE_ECHO: bool = False

    # Servidor
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = 8000

    # Almacenamiento de archivos
    UPLOAD_FOLDER: str = "uploads"
    MAX_VIDEO_SIZE_MB: int = 500
    ALLOWED_VIDEO_FORMATS: str = "mp4,avi,mov"

    # Procesamiento OCR
    # Nota: 0.75 es la fuente de verdad definida en la BD
    # Este valor se usa solo como referencia en el codigo Python
    OCR_CONFIDENCE_THRESHOLD: float = 0.75
    BATCH_SIZE: int = 10

    # Seguridad JWT
    SECRET_KEY: str = "automatizacion-kumon-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Instancia global. Importar en todo el proyecto con:
# from config.settings import settings
settings = Settings()
