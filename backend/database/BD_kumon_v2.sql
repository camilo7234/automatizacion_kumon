-- Consulta 1: Verificar columnas reales de ObservacionCualitativa
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'observaciones_cualitativas'
ORDER BY ordinal_position;

-- Consulta 2: Estado de los boletines generados
SELECT id_bulletin, status,
       (datos_boletin IS NOT NULL) as tiene_datos,
       pdf_path,
       generated_at
FROM bulletins
ORDER BY generated_at DESC
LIMIT 10;

-- Consulta 3: Cuestionarios completados existentes
SELECT COUNT(*) as total,
       COUNT(completado_at) as completados,
       COUNT(puntaje_cualitativo) as con_puntaje_persistido
FROM observaciones_cualitativas;