"""fix_prospecto_cascade_delete

Revision ID: 19945a747ad3
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05 15:57:20.905460
"""
from typing import Sequence, Union
from alembic import op

revision: str = '19945a747ad3'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        'processing_jobs_id_prospecto_fkey',
        'processing_jobs',
        schema='processing',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'processing_jobs_id_prospecto_fkey',
        'processing_jobs',
        'prospectos',
        ['id_prospecto'],
        ['id_prospecto'],
        source_schema='processing',
        referent_schema='processing',
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint(
        'processing_jobs_id_prospecto_fkey',
        'processing_jobs',
        schema='processing',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'processing_jobs_id_prospecto_fkey',
        'processing_jobs',
        'prospectos',
        ['id_prospecto'],
        ['id_prospecto'],
        source_schema='processing',
        referent_schema='processing',
        ondelete='SET NULL'
    )