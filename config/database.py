# config/database.py
# Conexion SQLAlchemy con PostgreSQL
# ============================================================

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config.settings import settings


# Motor de conexion a PostgreSQL
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,   # Verifica la conexion antes de usarla
    pool_size=5,          # Conexiones simultaneas normales
    max_overflow=10       # Conexiones extra en momentos de pico
)

# Fabrica de sesiones de base de datos
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# Clase base para todos los modelos SQLAlchemy del proyecto
class Base(DeclarativeBase):
    pass


# Dependencia para FastAPI
# Se usa en los endpoints con: db: Session = Depends(get_db)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Funcion para probar la conexion
def verificar_conexion() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Conexion a PostgreSQL exitosa")
        return True
    except Exception as e:
        print(f"Error de conexion: {e}")
        return False
