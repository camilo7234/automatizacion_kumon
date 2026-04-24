"""add_missing_obs_columns

Revision ID: a1b2c3d4e5f6
Revises: 828a5c39ed8b
Create Date: 2026-04-24 10:00:00.000000

Añade las columnas faltantes en processing.observaciones_cualitativas
que el ORM (models.py) declara pero que no existen en la BD real:

  - puntaje_cualitativo   NUMERIC(5,2)   — score 0-100 del formulario
  - etiqueta_cualitativa  VARCHAR(50)    — fortaleza/en_desarrollo/etc.
  - detalle_secciones     JSONB          — desglose por sección del cuestionario
  - observacion_libre     TEXT           — nota libre del orientador
  - correcciones_orientador JSONB        — campos que el orientador modificó vs OCR
  - esta_completo         BOOLEAN        — True cuando completado_at IS NOT NULL
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '828a5c39ed8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Columnas faltantes en observaciones_cualitativas ──────────
    op.add_column(
        'observaciones_cualitativas',
        sa.Column(
            'puntaje_cualitativo',
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment='Score 0-100 del formulario cualitativo del orientador.',
        ),
        schema='processing',
    )
    op.add_column(
        'observaciones_cualitativas',
        sa.Column(
            'etiqueta_cualitativa',
            sa.String(length=50),
            nullable=True,
            comment='Etiqueta resultante: fortaleza, en_desarrollo, refuerzo, atencion.',
        ),
        schema='processing',
    )
    op.add_column(
        'observaciones_cualitativas',
        sa.Column(
            'detalle_secciones',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment='Desglose por sección del cuestionario cualitativo.',
        ),
        schema='processing',
    )
    op.add_column(
        'observaciones_cualitativas',
        sa.Column(
            'observacion_libre',
            sa.Text(),
            nullable=True,
            comment='Nota libre opcional escrita por el orientador.',
        ),
        schema='processing',
    )
    op.add_column(
        'observaciones_cualitativas',
        sa.Column(
            'correcciones_orientador',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
            comment=(
                'Campos donde el orientador modificó un valor capturado '
                'automáticamente por el sistema. '
                'Estructura: {campo: {valor_sistema, valor_orientador, confianza_original}}'
            ),
        ),
        schema='processing',
    )
    op.add_column(
        'observaciones_cualitativas',
        sa.Column(
            'esta_completo',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='True cuando el orientador finalizó el formulario (completado_at IS NOT NULL).',
        ),
        schema='processing',
    )

    # ── Índice útil para consultar observaciones completas ────────
    op.create_index(
        'idx_obs_cual_completo',
        'observaciones_cualitativas',
        ['esta_completo'],
        schema='processing',
        postgresql_where=sa.text('esta_completo = true'),
    )


def downgrade() -> None:
    # ── Eliminar índice primero ───────────────────────────────────
    op.drop_index(
        'idx_obs_cual_completo',
        table_name='observaciones_cualitativas',
        schema='processing',
    )

    # ── Eliminar columnas en orden inverso ────────────────────────
    op.drop_column('observaciones_cualitativas', 'esta_completo',     schema='processing')
    op.drop_column('observaciones_cualitativas', 'correcciones_orientador', schema='processing')
    op.drop_column('observaciones_cualitativas', 'observacion_libre', schema='processing')
    op.drop_column('observaciones_cualitativas', 'detalle_secciones', schema='processing')
    op.drop_column('observaciones_cualitativas', 'etiqueta_cualitativa', schema='processing')
    op.drop_column('observaciones_cualitativas', 'puntaje_cualitativo', schema='processing')