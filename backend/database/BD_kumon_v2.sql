SELECT version_num FROM alembic_version;SELECT conname, confdeltype
FROM pg_constraint
WHERE conname = 'processing_jobs_id_prospecto_fkey';