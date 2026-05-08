"""
create_learning_signal_feedback

Revision ID: 0001_learning_signal_feedback
Revises: 19945a747ad3
Create Date: 2026-05-07
"""
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from alembic import op

revision      = "0001_learning_signal_feedback"
down_revision = "19945a747ad3"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS learning")
    op.create_table(
        "signal_feedback",
        sa.Column("id",             sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("id_job",         PG_UUID(as_uuid=True),
                  sa.ForeignKey("processing.processing_jobs.id_job", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("subject",        sa.String(20),  nullable=False),
        sa.Column("test_code",      sa.String(10),  nullable=False),
        sa.Column("metrica",        sa.Text()),
        sa.Column("valor_auto",     sa.Numeric(5, 2)),
        sa.Column("confianza_auto", sa.Numeric(4, 3)),
        sa.Column("valor_final",    sa.Numeric(5, 2)),
        sa.Column("fue_corregido",  sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("activity_ratio",    sa.Numeric(4, 3)),
        sa.Column("num_rewrites",      sa.Integer()),
        sa.Column("total_pausas_ms",   sa.Integer()),
        sa.Column("speech_rate",       sa.Numeric(5, 2)),
        sa.Column("pct_aciertos",      sa.Numeric(5, 2)),
        sa.Column("tiempo_ratio",      sa.Numeric(5, 3)),
        sa.Column("confidence_ocr",    sa.Numeric(4, 3)),
        sa.Column("etiqueta_final",    sa.String(30)),
        sa.Column("semaforo",          sa.String(10)),
        sa.Column("puntaje_combinado", sa.Numeric(5, 2)),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        schema="learning",
    )
    op.create_index("ix_sf_id_job",       "signal_feedback", ["id_job"],               schema="learning")
    op.create_index("ix_sf_metrica",      "signal_feedback", ["metrica"],              schema="learning")
    op.create_index("ix_sf_subject_test", "signal_feedback", ["subject", "test_code"], schema="learning")


def downgrade() -> None:
    op.drop_table("signal_feedback", schema="learning")
    op.execute("DROP SCHEMA IF EXISTS learning")
