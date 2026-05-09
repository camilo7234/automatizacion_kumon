BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 828a5c39ed8b

DROP INDEX admin.idx_profesores_activo;

DROP INDEX admin.idx_profesores_usuario;

DROP TABLE admin.profesores;

DROP TABLE audit.logs_auditoria_2027_04;

DROP INDEX admin.idx_profest_estado;

DROP INDEX admin.idx_profest_estudiante;

DROP INDEX admin.idx_profest_profesor;

DROP TABLE admin.profesor_estudiantes;

DROP TABLE audit.logs_auditoria_2026_08;

DROP INDEX audit.idx_log_2026_07_usuario;

DROP TABLE audit.logs_auditoria_2026_07;

DROP INDEX admin.idx_obs_estudiante;

DROP INDEX admin.idx_obs_sesion;

DROP TABLE admin.observaciones_sesion;

DROP INDEX admin.idx_materias_codigo;

DROP TABLE admin.materias;

DROP INDEX admin.idx_sesiones_activa;

DROP INDEX admin.idx_sesiones_token;

DROP INDEX admin.idx_sesiones_usuario;

DROP TABLE admin.sesiones_auth;

DROP TABLE audit.logs_auditoria_2026_11;

DROP INDEX admin.idx_tareas_completada;

DROP INDEX admin.idx_tareas_profesor;

DROP TABLE admin.tareas_asignadas;

DROP TABLE audit.logs_auditoria;

DROP INDEX admin.idx_config_clave;

DROP TABLE admin.configuracion_sistema;

DROP INDEX admin.idx_sesiones_clase_estudiante;

DROP INDEX admin.idx_sesiones_clase_fecha;

DROP INDEX admin.idx_sesiones_clase_profesor;

DROP TABLE admin.sesiones_clase;

DROP TABLE audit.logs_auditoria_2026_09;

DROP INDEX audit.idx_log_2026_06_usuario;

DROP TABLE audit.logs_auditoria_2026_06;

DROP INDEX audit.idx_log_2026_03_accion;

DROP INDEX audit.idx_log_2026_03_usuario;

DROP TABLE audit.logs_auditoria_2026_03;

DROP TABLE audit.logs_auditoria_2027_05;

DROP TABLE audit.logs_auditoria_2026_12;

DROP TABLE audit.logs_auditoria_2027_02;

DROP INDEX audit.idx_log_2026_05_usuario;

DROP TABLE audit.logs_auditoria_2026_05;

DROP INDEX audit.idx_log_2026_04_usuario;

DROP TABLE audit.logs_auditoria_2026_04;

DROP TABLE audit.logs_auditoria_2027_01;

DROP TABLE audit.logs_auditoria_2027_06;

DROP TABLE audit.logs_auditoria_2026_10;

DROP TABLE audit.logs_auditoria_2027_03;

ALTER TABLE admin.estudiantes ALTER COLUMN id_estudiante DROP DEFAULT;

DROP INDEX admin.idx_estudiantes_apellido;

DROP INDEX admin.idx_estudiantes_codigo;

DROP INDEX admin.idx_estudiantes_deleted;

DROP INDEX admin.idx_estudiantes_documento;

DROP INDEX admin.idx_estudiantes_estado;

ALTER TABLE admin.estudiantes DROP CONSTRAINT uq_estudiantes_documento;

ALTER TABLE admin.estudiantes DROP CONSTRAINT estudiantes_created_by_fkey;

COMMENT ON TABLE admin.estudiantes IS NULL;

ALTER TABLE admin.estudiantes DROP COLUMN alergias;

ALTER TABLE admin.estudiantes DROP COLUMN foto_perfil_url;

ALTER TABLE admin.estudiantes DROP COLUMN motivo_retiro;

ALTER TABLE admin.estudiantes DROP COLUMN created_by;

ALTER TABLE admin.estudiantes DROP COLUMN notas_medicas;

ALTER TABLE admin.estudiantes DROP COLUMN observaciones_gen;

ALTER TABLE admin.usuarios ALTER COLUMN id_usuario DROP DEFAULT;

DROP INDEX admin.idx_usuarios_activo;

DROP INDEX admin.idx_usuarios_deleted;

DROP INDEX admin.idx_usuarios_email;

DROP INDEX admin.idx_usuarios_rol;

ALTER TABLE admin.usuarios DROP CONSTRAINT usuarios_created_by_fkey;

ALTER TABLE admin.usuarios DROP COLUMN foto_perfil_url;

ALTER TABLE admin.usuarios DROP COLUMN token_recuperacion;

ALTER TABLE admin.usuarios DROP COLUMN token_exp;

ALTER TABLE admin.usuarios DROP COLUMN created_by;

ALTER TABLE admin.usuarios DROP COLUMN telefono;

DROP INDEX audit.idx_errors_job;

DROP INDEX audit.idx_errors_stage;

ALTER TABLE processing.bulletins ALTER COLUMN id_bulletin DROP DEFAULT;

COMMENT ON COLUMN processing.bulletins.puntaje_combinado IS NULL;

DROP INDEX processing.idx_bulletins_pending;

DROP INDEX processing.idx_bulletins_result;

DROP INDEX processing.idx_bulletins_status;

COMMENT ON TABLE processing.bulletins IS NULL;

ALTER TABLE processing.observaciones_cualitativas ALTER COLUMN id_observacion DROP DEFAULT;

DROP INDEX processing.idx_obs_cual_result;

COMMENT ON TABLE processing.observaciones_cualitativas IS NULL;

ALTER TABLE processing.processing_jobs ALTER COLUMN id_job DROP DEFAULT;

COMMENT ON COLUMN processing.processing_jobs.file_path IS NULL;

COMMENT ON COLUMN processing.processing_jobs.file_hash IS NULL;

DROP INDEX processing.idx_jobs_estudiante;

DROP INDEX processing.idx_jobs_hash;

DROP INDEX processing.idx_jobs_prospecto;

DROP INDEX processing.idx_jobs_status;

DROP INDEX processing.idx_jobs_template;

COMMENT ON TABLE processing.processing_jobs IS NULL;

ALTER TABLE processing.prospectos ALTER COLUMN id_prospecto DROP DEFAULT;

DROP INDEX processing.idx_prospectos_fecha;

DROP INDEX processing.idx_prospectos_nombre;

COMMENT ON TABLE processing.prospectos IS NULL;

ALTER TABLE processing.qualitative_results ALTER COLUMN id_qualitative DROP DEFAULT;

ALTER TABLE processing.qualitative_results ALTER COLUMN gaze_data SET DEFAULT NULL;

COMMENT ON COLUMN processing.qualitative_results.gaze_data IS NULL;

DROP INDEX processing.idx_qual_job;

COMMENT ON TABLE processing.qualitative_results IS NULL;

ALTER TABLE processing.test_results ALTER COLUMN id_result DROP DEFAULT;

COMMENT ON COLUMN processing.test_results.ws IS NULL;

COMMENT ON COLUMN processing.test_results.study_time_min IS NULL;

COMMENT ON COLUMN processing.test_results.target_time_min IS NULL;

COMMENT ON COLUMN processing.test_results.semaforo IS NULL;

COMMENT ON COLUMN processing.test_results.raw_ocr_data IS NULL;

DROP INDEX processing.idx_results_estudiante;

DROP INDEX processing.idx_results_job;

DROP INDEX processing.idx_results_prospecto;

DROP INDEX processing.idx_results_review;

DROP INDEX processing.idx_results_semaforo;

COMMENT ON TABLE processing.test_results IS NULL;

COMMENT ON COLUMN processing.test_templates.answer_key IS NULL;

COMMENT ON COLUMN processing.test_templates.level_rules IS NULL;

COMMENT ON COLUMN processing.test_templates.extraction_rules IS NULL;

COMMENT ON COLUMN processing.test_templates.metadata IS NULL;

DROP INDEX processing.idx_templates_active;

DROP INDEX processing.idx_templates_code;

DROP INDEX processing.idx_templates_subject;

COMMENT ON TABLE processing.test_templates IS NULL;

INSERT INTO alembic_version (version_num) VALUES ('828a5c39ed8b') RETURNING alembic_version.version_num;

-- Running upgrade 828a5c39ed8b -> a1b2c3d4e5f6

ALTER TABLE processing.observaciones_cualitativas ADD COLUMN puntaje_cualitativo NUMERIC(5, 2);

COMMENT ON COLUMN processing.observaciones_cualitativas.puntaje_cualitativo IS 'Score 0-100 del formulario cualitativo del orientador.';

ALTER TABLE processing.observaciones_cualitativas ADD COLUMN etiqueta_cualitativa VARCHAR(50);

COMMENT ON COLUMN processing.observaciones_cualitativas.etiqueta_cualitativa IS 'Etiqueta resultante: fortaleza, en_desarrollo, refuerzo, atencion.';

ALTER TABLE processing.observaciones_cualitativas ADD COLUMN detalle_secciones JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN processing.observaciones_cualitativas.detalle_secciones IS 'Desglose por sección del cuestionario cualitativo.';

ALTER TABLE processing.observaciones_cualitativas ADD COLUMN observacion_libre TEXT;

COMMENT ON COLUMN processing.observaciones_cualitativas.observacion_libre IS 'Nota libre opcional escrita por el orientador.';

ALTER TABLE processing.observaciones_cualitativas ADD COLUMN correcciones_orientador JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN processing.observaciones_cualitativas.correcciones_orientador IS 'Campos donde el orientador modificó un valor capturado automáticamente por el sistema. Estructura: {campo: {valor_sistema, valor_orientador, confianza_original}}';

ALTER TABLE processing.observaciones_cualitativas ADD COLUMN esta_completo BOOLEAN DEFAULT false NOT NULL;

COMMENT ON COLUMN processing.observaciones_cualitativas.esta_completo IS 'True cuando el orientador finalizó el formulario (completado_at IS NOT NULL).';

CREATE INDEX idx_obs_cual_completo ON processing.observaciones_cualitativas (esta_completo) WHERE esta_completo = true;

UPDATE alembic_version SET version_num='a1b2c3d4e5f6' WHERE alembic_version.version_num = '828a5c39ed8b';

-- Running upgrade a1b2c3d4e5f6 -> 19945a747ad3

ALTER TABLE processing.processing_jobs DROP CONSTRAINT processing_jobs_id_prospecto_fkey;

ALTER TABLE processing.processing_jobs ADD CONSTRAINT processing_jobs_id_prospecto_fkey FOREIGN KEY(id_prospecto) REFERENCES processing.prospectos (id_prospecto) ON DELETE CASCADE;

UPDATE alembic_version SET version_num='19945a747ad3' WHERE alembic_version.version_num = 'a1b2c3d4e5f6';

-- Running upgrade 19945a747ad3 -> 0001_learning_signal_feedback

CREATE SCHEMA IF NOT EXISTS learning;

CREATE TABLE learning.signal_feedback (
    id BIGSERIAL NOT NULL, 
    id_job UUID NOT NULL, 
    subject VARCHAR(20) NOT NULL, 
    test_code VARCHAR(10) NOT NULL, 
    metrica TEXT, 
    valor_auto NUMERIC(5, 2), 
    confianza_auto NUMERIC(4, 3), 
    valor_final NUMERIC(5, 2), 
    fue_corregido BOOLEAN DEFAULT false NOT NULL, 
    activity_ratio NUMERIC(4, 3), 
    num_rewrites INTEGER, 
    total_pausas_ms INTEGER, 
    speech_rate NUMERIC(5, 2), 
    pct_aciertos NUMERIC(5, 2), 
    tiempo_ratio NUMERIC(5, 3), 
    confidence_ocr NUMERIC(4, 3), 
    etiqueta_final VARCHAR(30), 
    semaforo VARCHAR(10), 
    puntaje_combinado NUMERIC(5, 2), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(id_job) REFERENCES processing.processing_jobs (id_job) ON DELETE CASCADE
);

CREATE INDEX ix_sf_id_job ON learning.signal_feedback (id_job);

CREATE INDEX ix_sf_metrica ON learning.signal_feedback (metrica);

CREATE INDEX ix_sf_subject_test ON learning.signal_feedback (subject, test_code);

UPDATE alembic_version SET version_num='0001_learning_signal_feedback' WHERE alembic_version.version_num = '19945a747ad3';

COMMIT;

