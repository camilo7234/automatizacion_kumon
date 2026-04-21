
#C:\Users\camil\OneDrive\Escritorio\automatizacion_kumon\backend\config\database.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config.settings import settings


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.is_development,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency de FastAPI para inyectar la sesión de BD en cada request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verificar_conexion() -> dict:
    """Verifica que PostgreSQL responde. Usado en GET /health."""
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
        return {"status": "ok", "db": "kumon_db", "version": version}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
