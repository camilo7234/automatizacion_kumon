"""initial_schema_clean

Revision ID: fe919fe46e29
Revises: 
Create Date: 2026-05-10 19:14:15.900931
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'fe919fe46e29'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 0. Schemas ────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS admin")
    op.execute("CREATE SCHEMA IF NOT EXISTS processing")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.execute("CREATE SCHEMA IF NOT EXISTS learning")

    # ── 1. admin.roles ────────────────────────────────────────────
    op.create_table('roles',
        sa.Column('id_rol',      sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('nombre_rol',  sa.String(50),   nullable=False, unique=True),
        sa.Column('descripcion', sa.Text()),
        sa.Column('permisos',    postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('activo',      sa.Boolean(),    nullable=False, server_default=sa.text('true')),
        sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',  sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='admin'
    )

    # ── 2. admin.usuarios ─────────────────────────────────────────
    op.create_table('usuarios',
        sa.Column('id_usuario',        sa.UUID(),       primary_key=True),
        sa.Column('id_rol',            sa.Integer(),    sa.ForeignKey('admin.roles.id_rol'), nullable=False),
        sa.Column('primer_nombre',     sa.String(100),  nullable=False),
        sa.Column('segundo_nombre',    sa.String(100)),
        sa.Column('primer_apellido',   sa.String(100),  nullable=False),
        sa.Column('segundo_apellido',  sa.String(100)),
        sa.Column('email',             sa.String(255),  nullable=False, unique=True),
        sa.Column('password_hash',     sa.String(255),  nullable=False),
        sa.Column('activo',            sa.Boolean(),    nullable=False, server_default=sa.text('true')),
        sa.Column('email_verificado',  sa.Boolean(),    nullable=False, server_default=sa.text('false')),
        sa.Column('ultimo_acceso',     sa.DateTime(timezone=True)),
        sa.Column('intentos_fallidos', sa.Integer(),    nullable=False, server_default=sa.text('0')),
        sa.Column('bloqueado_hasta',   sa.DateTime(timezone=True)),
        sa.Column('created_at',        sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',        sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at',        sa.DateTime(timezone=True)),
        schema='admin'
    )

    # ── 3. admin.estudiantes ──────────────────────────────────────
    op.create_table('estudiantes',
        sa.Column('id_estudiante',      sa.UUID(),      primary_key=True),
        sa.Column('codigo_estudiante',  sa.String(20),  unique=True),
        sa.Column('primer_nombre',      sa.String(100), nullable=False),
        sa.Column('segundo_nombre',     sa.String(100)),
        sa.Column('primer_apellido',    sa.String(100), nullable=False),
        sa.Column('segundo_apellido',   sa.String(100)),
        sa.Column('tipo_documento',     sa.String(10),  nullable=False, server_default=sa.text("'TI'")),
        sa.Column('numero_documento',   sa.String(30),  nullable=False),
        sa.Column('fecha_nacimiento',   sa.Date(),      nullable=False),
        sa.Column('genero',             sa.String(20)),
        sa.Column('direccion',          sa.Text()),
        sa.Column('telefono_contacto',  sa.String(20)),
        sa.Column('email',              sa.String(255)),
        sa.Column('nombre_acudiente',   sa.String(200)),
        sa.Column('telefono_acudiente', sa.String(20)),
        sa.Column('email_acudiente',    sa.String(255)),
        sa.Column('relacion_acudiente', sa.String(50)),
        sa.Column('grado_escolar',      sa.String(50)),
        sa.Column('institucion_origen', sa.String(200)),
        sa.Column('fecha_ingreso',      sa.Date(),      nullable=False, server_default=sa.text('CURRENT_DATE')),
        sa.Column('fecha_retiro',       sa.Date()),
        sa.Column('estado',             sa.String(20),  nullable=False, server_default=sa.text("'activo'")),
        sa.Column('created_at',         sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at',         sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at',         sa.DateTime(timezone=True)),
        schema='admin'
    )

    # ── 4. processing.prospectos ──────────────────────────────────
    op.create_table('prospectos',
    sa.Column('id_prospecto', sa.UUID(), nullable=False),
    sa.Column('nombre_completo', sa.Text(), nullable=False),
    sa.Column('grado_escolar', sa.Text(), nullable=True),
    sa.Column('nombre_escuela', sa.Text(), nullable=True),
    sa.Column('fecha_prueba', sa.Date(), nullable=True),
    sa.Column('nombre_acudiente', sa.Text(), nullable=True),
    sa.Column('telefono', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.PrimaryKeyConstraint('id_prospecto'),
    schema='processing'
    )
    op.create_table('test_templates',
    sa.Column('id_template', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('subject', sa.String(length=20), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('grade_level', sa.String(length=50), nullable=True),
    sa.Column('total_items', sa.Integer(), nullable=False),
    sa.Column('time_pattern_min', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('answer_key', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('level_rules', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('extraction_rules', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.PrimaryKeyConstraint('id_template'),
    sa.UniqueConstraint('code', 'subject', name='uq_test_code_subject'),
    schema='processing'
    )
    op.create_table('processing_jobs',
    sa.Column('id_job', sa.UUID(), nullable=False),
    sa.Column('id_estudiante', sa.UUID(), nullable=True),
    sa.Column('id_prospecto', sa.UUID(), nullable=True),
    sa.Column('id_template', sa.Integer(), nullable=False),
    sa.Column('source_type', sa.String(length=10), server_default=sa.text("'video'"), nullable=False),
    sa.Column('file_path', sa.Text(), nullable=True),
    sa.Column('file_name_original', sa.Text(), nullable=True),
    sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
    sa.Column('file_hash', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'queued'"), nullable=False),
    sa.Column('progress_percent', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('retry_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('queued','processing','done','error','manual_review')", name='chk_job_status'),
    sa.CheckConstraint('(id_estudiante IS NOT NULL AND id_prospecto IS NULL) OR (id_estudiante IS NULL AND id_prospecto IS NOT NULL)', name='chk_xor_sujeto'),
    sa.CheckConstraint('completed_at IS NULL OR completed_at >= started_at', name='chk_job_completado'),
    sa.CheckConstraint('progress_percent BETWEEN 0 AND 100', name='chk_job_progress'),
    sa.ForeignKeyConstraint(['id_estudiante'], ['admin.estudiantes.id_estudiante'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['id_prospecto'], ['processing.prospectos.id_prospecto'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['id_template'], ['processing.test_templates.id_template'], ),
    sa.PrimaryKeyConstraint('id_job'),
    schema='processing'
    )
    op.create_table('processing_errors',
    sa.Column('id_error', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('id_job', sa.UUID(), nullable=True),
    sa.Column('stage', sa.String(length=50), nullable=False),
    sa.Column('error_type', sa.String(length=100), nullable=True),
    sa.Column('error_detail', sa.Text(), nullable=True),
    sa.Column('stack_trace', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['id_job'], ['processing.processing_jobs.id_job'], ),
    sa.PrimaryKeyConstraint('id_error'),
    schema='audit'
    )
    op.create_table('signal_feedback',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('id_job', sa.UUID(), nullable=False),
    sa.Column('subject', sa.String(length=20), nullable=False),
    sa.Column('test_code', sa.String(length=10), nullable=False),
    sa.Column('metrica', sa.Text(), nullable=True),
    sa.Column('valor_auto', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('confianza_auto', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('valor_final', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('fue_corregido', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('activity_ratio', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('num_rewrites', sa.Integer(), nullable=True),
    sa.Column('total_pausas_ms', sa.Integer(), nullable=True),
    sa.Column('speech_rate', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('pct_aciertos', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('tiempo_ratio', sa.Numeric(precision=5, scale=3), nullable=True),
    sa.Column('confidence_ocr', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('etiqueta_final', sa.String(length=30), nullable=True),
    sa.Column('semaforo', sa.String(length=10), nullable=True),
    sa.Column('puntaje_combinado', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['id_job'], ['processing.processing_jobs.id_job'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='learning'
    )
    op.create_table('qualitative_results',
    sa.Column('id_qualitative', sa.UUID(), nullable=False),
    sa.Column('id_job', sa.UUID(), nullable=False),
    sa.Column('time_per_section', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('num_rewrites', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('pause_events', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('activity_ratio', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('stroke_detail', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('vad_segments', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('speech_rate', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('silence_events', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('gaze_data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text('NULL'), nullable=True),
    sa.Column('prefills', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('auto_captured_flags', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('processing_ms', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['id_job'], ['processing.processing_jobs.id_job'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id_qualitative'),
    sa.UniqueConstraint('id_job'),
    schema='processing'
    )
    op.create_table('test_results',
    sa.Column('id_result', sa.UUID(), nullable=False),
    sa.Column('id_job', sa.UUID(), nullable=False),
    sa.Column('id_prospecto', sa.UUID(), nullable=True),
    sa.Column('id_estudiante', sa.UUID(), nullable=True),
    sa.Column('id_template', sa.Integer(), nullable=False),
    sa.Column('tipo_sujeto', sa.String(length=20), nullable=False),
    sa.Column('test_date', sa.Date(), nullable=True),
    sa.Column('ws', sa.String(length=20), nullable=True),
    sa.Column('study_time_min', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('target_time_min', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('correct_answers', sa.Integer(), nullable=True),
    sa.Column('total_questions', sa.Integer(), nullable=True),
    sa.Column('percentage', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('current_level', sa.String(length=30), nullable=True),
    sa.Column('starting_point', sa.String(length=50), nullable=True),
    sa.Column('semaforo', sa.String(length=10), nullable=True),
    sa.Column('recommendation', sa.Text(), nullable=True),
    sa.Column('confidence_score', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('needs_manual_review', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('raw_ocr_data', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('sections_detail', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.CheckConstraint("semaforo IS NULL OR semaforo IN ('verde','amarillo','rojo')", name='chk_result_semaforo'),
    sa.CheckConstraint("tipo_sujeto IN ('prospecto','estudiante')", name='chk_result_tipo_sujeto'),
    sa.CheckConstraint('percentage IS NULL OR percentage BETWEEN 0 AND 100', name='chk_result_percentage'),
    sa.ForeignKeyConstraint(['id_estudiante'], ['admin.estudiantes.id_estudiante'], ),
    sa.ForeignKeyConstraint(['id_job'], ['processing.processing_jobs.id_job'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['id_prospecto'], ['processing.prospectos.id_prospecto'], ),
    sa.ForeignKeyConstraint(['id_template'], ['processing.test_templates.id_template'], ),
    sa.PrimaryKeyConstraint('id_result'),
    sa.UniqueConstraint('id_job'),
    schema='processing'
    )
    op.create_table('bulletins',
    sa.Column('id_bulletin', sa.UUID(), nullable=False),
    sa.Column('id_result', sa.UUID(), nullable=False),
    sa.Column('id_template', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('datos_boletin', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('puntaje_cuantitativo', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('puntaje_cualitativo', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('puntaje_combinado', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('etiqueta_combinada', sa.String(length=20), nullable=True),
    sa.Column('pdf_path', sa.Text(), nullable=True),
    sa.Column('pdf_size_bytes', sa.BigInteger(), nullable=True),
    sa.Column('approved_by', sa.UUID(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.CheckConstraint("etiqueta_combinada IS NULL OR etiqueta_combinada IN ('fortaleza','en_desarrollo','refuerzo','atencion')", name='chk_bulletin_etiqueta'),
    sa.CheckConstraint("status IN ('pending','generating','ready','delivered','error')", name='chk_bulletin_status'),
    sa.ForeignKeyConstraint(['approved_by'], ['admin.usuarios.id_usuario'], ),
    sa.ForeignKeyConstraint(['id_result'], ['processing.test_results.id_result'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['id_template'], ['processing.test_templates.id_template'], ),
    sa.PrimaryKeyConstraint('id_bulletin'),
    sa.UniqueConstraint('id_result'),
    schema='processing'
    )
    op.create_table('observaciones_cualitativas',
    sa.Column('id_observacion', sa.UUID(), nullable=False),
    sa.Column('id_result', sa.UUID(), nullable=False),
    sa.Column('subject', sa.String(length=20), nullable=False),
    sa.Column('test_code', sa.String(length=10), nullable=False),
    sa.Column('respuestas', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('completado_por', sa.Text(), nullable=True),
    sa.Column('completado_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('puntaje_cualitativo', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('etiqueta_cualitativa', sa.String(length=30), nullable=True),
    sa.Column('detalle_secciones', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('observacion_libre', sa.Text(), nullable=True),
    sa.Column('correcciones_orientador', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
    sa.Column('esta_completo', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.CheckConstraint("etiqueta_cualitativa IS NULL OR etiqueta_cualitativa IN ('fortaleza','en_desarrollo','refuerzo','atencion')", name='chk_obs_etiqueta_cualitativa'),
    sa.ForeignKeyConstraint(['id_result'], ['processing.test_results.id_result'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id_observacion'),
    sa.UniqueConstraint('id_result'),
    schema='processing'
    )


def downgrade() -> None:
    op.drop_table('observaciones_cualitativas', schema='processing')
    op.drop_table('bulletins', schema='processing')
    op.drop_table('test_results', schema='processing')
    op.drop_table('qualitative_results', schema='processing')
    op.drop_table('signal_feedback', schema='learning')
    op.drop_table('processing_errors', schema='audit')
    op.drop_table('processing_jobs', schema='processing')
    op.drop_table('test_templates', schema='processing')
    op.drop_table('prospectos', schema='processing')
    op.drop_table('estudiantes', schema='admin')
    op.drop_table('usuarios', schema='admin')
    op.drop_table('roles', schema='admin')
    op.execute("DROP SCHEMA IF EXISTS learning")
    op.execute("DROP SCHEMA IF EXISTS audit")
    op.execute("DROP SCHEMA IF EXISTS processing")
    op.execute("DROP SCHEMA IF EXISTS admin")