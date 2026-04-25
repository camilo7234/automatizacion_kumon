from __future__ import annotations

"""
app/routes/results.py
══════════════════════════════════════════════════════════════════
Expone resultados cuantitativos (y combinados) de un test:

  - GET /api/v1/results/{result_id}
  - GET /api/v1/results/job/{job_id}

Usa:
  - TestResult             — datos Class Navi + semáforo
  - QualitativeResult      — señales automáticas + prefills del video
  - ObservacionCualitativa — puntaje cualitativo calculado (post-formulario)
  - TestResultResponse     — schema unificado para el frontend

CORRECCIÓN APLICADA:
  - Se elimina la dependencia funcional de report_generator dentro
    de esta ruta de resultados preliminares.
  - Se conserva el cálculo cualitativo auxiliar cuando existe
    ObservacionCualitativa completa, pero NO se arma ni se expone
    reporte/boletín desde aquí.
  - Se mantiene intacto el contrato del schema TestResultResponse.
  - No se cambian rutas.
  - No se cambian nombres de variables existentes.
  - No se quitan funciones existentes.
══════════════════════════════════════════════════════════════════
"""

# ════════════════════════════════════════════════════════════════
# 1) IMPORTS
# ════════════════════════════════════════════════════════════════

from uuid import UUID
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from database.models import TestResult, QualitativeResult
from app.schemas.result import TestResultResponse
from config.cuestionarios import calcular_puntaje_cualitativo


# ════════════════════════════════════════════════════════════════
# 2) ROUTER
# ════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api/v1/results", tags=["results"])


# ════════════════════════════════════════════════════════════════
# 3) HELPERS INTERNOS
# ════════════════════════════════════════════════════════════════

def _flatten_respuestas(respuestas: dict[str, Any] | None) -> dict[str, Any]:
    """
    Aplana el formato enriquecido de respuestas al formato plano
    que espera calcular_puntaje_cualitativo.

    Entrada:  {"clave": {"valor": X, "fuente": "orientador", ...}}
    Salida:   {"clave": X}
    """
    flattened: dict[str, Any] = {}
    if not respuestas:
        return flattened

    for key, value in respuestas.items():
        if isinstance(value, dict) and "valor" in value:
            flattened[key] = value.get("valor")
        else:
            flattened[key] = value

    return flattened


def _get_nombre_sujeto(result: TestResult) -> str:
    """
    Obtiene el nombre visible del sujeto sin asumir un único nombre de atributo.

    Se prioriza la relación correcta según tipo_sujeto, pero se incluyen
    varios fallbacks para evitar errores si el modelo del admin cambia
    ligeramente el nombre del campo.
    """
    tipo_sujeto = (getattr(result, "tipo_sujeto", "") or "").strip().lower()

    prospecto = getattr(result, "prospecto", None)
    estudiante = getattr(result, "estudiante", None)

    if tipo_sujeto == "prospecto":
        candidatos = [prospecto, estudiante, result]
    elif tipo_sujeto == "estudiante":
        candidatos = [estudiante, prospecto, result]
    else:
        candidatos = [prospecto, estudiante, result]

    for obj in candidatos:
        if obj is None:
            continue

        for attr in ("nombre_completo", "full_name", "display_name", "name"):
            value = getattr(obj, attr, None)
            if value:
                return str(value)

        primer_nombre = getattr(obj, "primer_nombre", None)
        primer_apellido = getattr(obj, "primer_apellido", None)
        if primer_nombre or primer_apellido:
            return " ".join(
                part for part in [primer_nombre, primer_apellido] if part
            ).strip()

    return ""


def _build_response(result: TestResult, qual: QualitativeResult | None) -> TestResultResponse:
    """
    Construye el payload final del resultado con el contrato exacto
    que espera TestResultResponse.

    Importante:
      - id_result / id_job se envían como UUID reales.
      - No se incluye 'report' porque el schema no lo define.
      - No se ejecuta build_report_data aquí porque esta ruta representa
        el resultado preliminar, no el boletín final.
      - Se conserva el cálculo auxiliar cualitativo únicamente para no
        romper compatibilidad lógica con observaciones completas, aunque
        no se exponga un reporte en la respuesta.
    """
    # ── Acceso seguro al template ────────────────────────────────
    template = result.template

    # ── Observación cualitativa ──────────────────────────────────
    obs = result.observacion_cualitativa

    # ── Cálculo cualitativo auxiliar (sin generar boletín) ──────
    # Se deja este bloque para conservar robustez operativa cuando
    # exista observación completa, pero sin acoplar /results al flujo
    # de report_generator ni al boletín consolidado.
    if obs and obs.esta_completo and template:
        try:
            calc = calcular_puntaje_cualitativo(
                subject=template.subject,
                test_code=template.code,
                respuestas=_flatten_respuestas(obs.respuestas),
            )
            total_porcentaje = float(calc.get("total_porcentaje", 0.0))
            etiqueta_total = calc.get("etiqueta_total", "en_desarrollo")
            secciones = calc.get("secciones", [])
        except (ValueError, KeyError, TypeError):
            total_porcentaje = 0.0
            etiqueta_total = "en_desarrollo"
            secciones = []
    else:
        total_porcentaje = 0.0
        etiqueta_total = "en_desarrollo"
        secciones = []

    # ── Normalización defensiva de estructuras JSON ──────────────
    sections_detail = result.sections_detail or {}
    raw_ocr_data = result.raw_ocr_data or {}

    # Estas variables se conservan para compatibilidad futura y para
    # dejar explícito que el endpoint ya evaluó la presencia de datos
    # cualitativos calculados, sin convertir esto en armado de boletín.
    _ = total_porcentaje
    _ = etiqueta_total
    _ = secciones
    _ = qual

    # ── Response final con contrato exacto del schema ────────────
    return TestResultResponse(
        id_result=result.id_result,
        id_job=result.id_job,

        tipo_sujeto=result.tipo_sujeto or "",
        nombre_sujeto=_get_nombre_sujeto(result),

        subject=template.subject if template else "",
        test_code=template.code if template else "",
        display_name=template.display_name if template else "",

        test_date=result.test_date,
        ws=result.ws,
        study_time_min=result.study_time_min,
        target_time_min=result.target_time_min,
        correct_answers=result.correct_answers,
        total_questions=result.total_questions,
        percentage=result.percentage,

        current_level=result.current_level,
        starting_point=result.starting_point,
        semaforo=result.semaforo,
        recommendation=result.recommendation,

        confidence_score=result.confidence_score,
        needs_manual_review=result.needs_manual_review,

        sections_detail=sections_detail,
        raw_ocr_data=raw_ocr_data,

        tiene_observacion=bool(obs),
        observacion_completa=bool(obs.esta_completo) if obs else False,

        created_at=result.created_at,
    )


# ════════════════════════════════════════════════════════════════
# 4) ENDPOINT: GET /api/v1/results/{result_id}
# ════════════════════════════════════════════════════════════════

@router.get("/{result_id}", response_model=TestResultResponse)
def get_result(result_id: UUID, db: Session = Depends(get_db)):
    """
    Obtiene un resultado por su UUID.
    """
    result = (
        db.query(TestResult)
        .filter(TestResult.id_result == result_id)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado no encontrado.",
        )

    # QualitativeResult no tiene id_result.
    # La FK correcta es id_job → processing_jobs.id_job.
    qual = (
        db.query(QualitativeResult)
        .filter(QualitativeResult.id_job == result.id_job)
        .first()
    )

    return _build_response(result, qual)


# ════════════════════════════════════════════════════════════════
# 5) ENDPOINT: GET /api/v1/results/job/{job_id}
# ════════════════════════════════════════════════════════════════

@router.get("/job/{job_id}", response_model=TestResultResponse)
def get_result_by_job(job_id: UUID, db: Session = Depends(get_db)):
    """
    Obtiene el resultado asociado a un job.
    """
    result = (
        db.query(TestResult)
        .filter(TestResult.id_job == job_id)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado no disponible para este job.",
        )

    qual = (
        db.query(QualitativeResult)
        .filter(QualitativeResult.id_job == result.id_job)
        .first()
    )

    return _build_response(result, qual)