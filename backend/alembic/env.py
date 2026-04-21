"""
alembic/env.py
══════════════════════════════════════════════════════════════════
Configuración de Alembic para autogenerar migraciones desde los
modelos ORM definidos en database/models.py.

Puntos clave:
  - La URL de BD se toma del .env (via config.settings) para no
    duplicar credenciales en alembic.ini.
  - target_metadata apunta a Base.metadata con todos los modelos
    importados explícitamente para que Alembic los detecte.
  - include_schemas=True es OBLIGATORIO para detectar tablas en
    schemas distintos de 'public' (admin, processing, audit).
  - include_object filtra solo nuestros schemas para no interferir
    con tablas del sistema de PostgreSQL.
══════════════════════════════════════════════════════════════════
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Asegurar que backend/ esté en el path ────────────────────────
# Necesario para que los imports de config.* y database.* funcionen
# cuando Alembic se ejecuta desde backend/
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── Importar settings ANTES que los modelos ──────────────────────
from config.settings import settings

# ── Importar todos los modelos para que Alembic los detecte ──────
# Si no se importan aquí, Alembic no genera las migraciones de esas tablas.
from database.models import (  # noqa: F401
    Role,
    Usuario,
    Student,
    TestTemplate,
    Prospecto,
    ProcessingJob,
    TestResult,
    QualitativeResult,
    ObservacionCualitativa,
    Bulletin,
    ProcessingError,
)
from config.database import Base

# ── Configuración de logging de Alembic ──────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── URL de BD desde .env (no desde alembic.ini) ──────────────────
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# ── Metadata con todos los modelos ───────────────────────────────
target_metadata = Base.metadata

# ── Schemas que Alembic debe gestionar ───────────────────────────
MANAGED_SCHEMAS = {"admin", "processing", "audit"}


def include_object(object, name, type_, reflected, compare_to):
    """
    Filtra qué objetos incluye Alembic en las migraciones.
    Solo procesa tablas de nuestros 3 schemas.
    Ignora tablas del sistema de PostgreSQL (pg_*, information_schema).
    """
    if type_ == "table":
        schema = getattr(object, "schema", None)
        return schema in MANAGED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    """
    Modo offline: genera el SQL sin conectarse a la BD.
    Útil para revisar las migraciones antes de aplicarlas.
    Ejecutar con: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,          # OBLIGATORIO para schemas no-public
        include_object=include_object,
        compare_type=True,             # detecta cambios de tipo de columna
        compare_server_default=True,   # detecta cambios en server_default
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Modo online: aplica las migraciones directamente en la BD.
    Ejecutar con: alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,          # OBLIGATORIO para admin/processing/audit
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
