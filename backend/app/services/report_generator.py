from __future__ import annotations


"""
app/services/report_generator.py
══════════════════════════════════════════════════════════════════
Genera la estructura de datos para el boletín por resultado.


NO genera PDF directamente (eso será otro servicio). Aquí solo
arma un dict listo para BoletinResponse.datos con 3 bloques:


  - cuantitativo:   65% del puntaje final, solo datos Class Navi
  - cualitativo:    35% del puntaje final, formulario orientador
                    + señales automáticas (video/audio/gaze)
  - combinado:      mezcla 65/35, etiqueta general y narrativa
  - gaze:           reservado para futuro (cámara frontal)


Este servicio NO pregunta a la BD por el formulario; asume que
TestResult y ObservacionCualitativa ya existen y los recibe
como argumentos (para no acoplar capas).
══════════════════════════════════════════════════════════════════
"""


import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional


from config.settings import settings


logger = logging.getLogger(__name__)


# Escala interna de puntaje por semáforo.
# Debe mantenerse sincronizada con processing_service.calcularresultadointegrado.
_SEMAFORO_SCORE: Dict[str, float] = {
    "verde":    100.0,
    "amarillo":  85.0,
    "rojo":      70.0,
}


# ══════════════════════════════════════════════════════════════════
# Dataclass de entrada (para desacoplar de SQLAlchemy)
# ══════════════════════════════════════════════════════════════════


@dataclass
class QuantitativeInput:
    """Datos cuantitativos que vienen de TestResult."""
    subject:          str
    test_code:        str
    display_name:     str
    ws:               Optional[str]
    test_date:        Optional[Any]
    study_time_min:   Optional[Decimal]
    target_time_min:  Optional[Decimal]
    correct_answers:  Optional[int]
    total_questions:  Optional[int]
    percentage:       Optional[Decimal]
    current_level:    Optional[str]
    starting_point:   Optional[str]
    semaforo:         Optional[str]
    recommendation:   Optional[str]
    confidence_score:     Optional[float]   = None
    needs_manual_review:  Optional[bool]    = None
    tipo_sujeto:          Optional[str]     = None
    nombre_sujeto:        Optional[str]     = None


@dataclass
class QualitativeInput:
    """
    Resumen cualitativo consolidado (ya calculado en config/cuestionarios.py).


    total_porcentaje:   0-100 (promedio ponderado de secciones)
    etiqueta_total:     fortaleza | en_desarrollo | refuerzo | atencion
    secciones:          lista de secciones con puntaje y etiqueta
    auto_flags:         métricas capturadas automáticamente (video/audio)
    prefills:           prefills originales (para depuración)
    gaze_data:          dict o None (cuando se active cámara frontal)
    """
    total_porcentaje: float
    etiqueta_total:   str
    secciones:        list
    auto_flags:       list
    prefills:         dict
    gaze_data:        Optional[dict] = None



# ══════════════════════════════════════════════════════════════════
# Sanitizador JSON — elimina Decimal antes de persistir en JSONB
# ══════════════════════════════════════════════════════════════════

def _sanitize_decimals(obj: Any) -> Any:
    """
    Recorre recursivamente obj y convierte Decimal → float.
    Necesario porque PostgreSQL/psycopg2 puede deserializar
    columnas JSONB con valores numéricos como decimal.Decimal,
    que no es serializable por json.dumps nativo de Python.
    Solo modifica instancias de Decimal; no altera ningún otro tipo.
    """
    if isinstance(obj, dict):
        return {k: _sanitize_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_decimals(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════


def build_report_data(
    cuantitativo: QuantitativeInput,
    cualitativo:  QualitativeInput,
    integrado:    Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Construye el dict para BoletinResponse.datos.

    Fórmula de puntaje combinado (acordada en informe 6):
      puntaje_combinado = 0.65 * score_cuantitativo +
                          0.35 * score_cualitativo

    Si se recibe el bloque integrado del pipeline, se respeta
    su score_final cuando existe un override activo.
    """
    cuant_block = _build_cuantitativo_block(cuantitativo)
    cual_block  = _build_cualitativo_block(cualitativo)
    comb_block  = _build_combinado_block(cuant_block, cual_block, integrado)
    gaze_block  = cualitativo.gaze_data or None

    return _sanitize_decimals({
        "cuantitativo": cuant_block,
        "cualitativo":  cual_block,
        "combinado":    comb_block,
        "gaze":         gaze_block,
    })
# ══════════════════════════════════════════════════════════════════
# Helpers internos
# ══════════════════════════════════════════════════════════════════


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



def _normalize_weight(value: Any, default: float) -> float:
    parsed = _to_float(value)
    if parsed is None or parsed <= 0:
        return default
    return parsed



def _semaforo_to_score(semaforo: Optional[str]) -> Optional[float]:
    """
    Convierte el semáforo cuantitativo al puntaje interno 0-100.
    Usa la misma escala que processing_service.calcularresultadointegrado
    para garantizar que el boletín muestre el mismo combinado que el pipeline.
    """
    if semaforo is None:
        return None
    return _SEMAFORO_SCORE.get(semaforo.strip().lower())



# ══════════════════════════════════════════════════════════════════
# Bloque cuantitativo
# ══════════════════════════════════════════════════════════════════


def _build_cuantitativo_block(c: QuantitativeInput) -> Dict[str, Any]:
    """
    Construye el resumen cuantitativo puro.
    Todo lo que aquí aparece viene de Class Navi + result_calculator.

    score_index: puntaje en escala interna 0-100 mapeado desde el semáforo.
    Se usa en _build_combinado_block para la fórmula 65/35.
    No reemplaza 'percentage', que se conserva como dato de display crudo.
    """
    pct         = _to_float(c.percentage)
    study_time  = _to_float(c.study_time_min)
    target_time = _to_float(c.target_time_min)


    time_ratio = None
    if study_time is not None and target_time is not None and target_time > 0:
        time_ratio = study_time / target_time


    # score_index usa la escala semáforo (verde=100, amarillo=85, rojo=70)
    # para que el combinado 65/35 sea consistente con el pipeline.
    score_index = _semaforo_to_score(c.semaforo)


    return {
        "subject":        c.subject,
        "test_code":      c.test_code,
        "display_name":   c.display_name,
        "ws":             c.ws,
        "test_date":      c.test_date.isoformat() if c.test_date else None,
        "study_time_min": study_time,
        "target_time_min": target_time,
        "time_ratio":     round(time_ratio, 3) if time_ratio is not None else None,
        "correct_answers": c.correct_answers,
        "total_questions": c.total_questions,
        "percentage":     pct,
        "current_level":  c.current_level,
        "starting_point": c.starting_point,
        "semaforo":       c.semaforo,
        "recommendation": c.recommendation,
        "score_index":    score_index,
        "confidence_score":      c.confidence_score,
        "needs_manual_review":   c.needs_manual_review,
        "tipo_sujeto":           c.tipo_sujeto,
        "nombre_sujeto":         c.nombre_sujeto,
    }



# ══════════════════════════════════════════════════════════════════
# Bloque cualitativo
# ══════════════════════════════════════════════════════════════════


def _build_cualitativo_block(q: QualitativeInput) -> Dict[str, Any]:
    """
    Construye el resumen cualitativo puro.


    total_porcentaje: 0-100 → se mantiene tal cual
    etiqueta_total:   fortaleza | en_desarrollo | refuerzo | atencion
    """
    return {
        "total_porcentaje": round(float(q.total_porcentaje), 1),
        "etiqueta_total":   q.etiqueta_total,
        "secciones":        q.secciones,
        "auto_flags":       q.auto_flags,
        "prefills":         q.prefills,
    }



# ══════════════════════════════════════════════════════════════════
# Bloque combinado 65/35
# ══════════════════════════════════════════════════════════════════


def _build_combinado_block(
    cuant: Dict[str, Any],
    cual:  Dict[str, Any],
    integrado: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Combina cuantitativo y cualitativo según la fórmula:
      65% cuantitativo + 35% cualitativo.

    Ambos puntajes están en escala 0-100.
    score_cuant viene de score_index (semáforo mapeado).
    score_cual  viene de total_porcentaje (promedio ponderado secciones).

    Si se recibe el bloque integrado del pipeline (sections_detail.integrado),
    se usa su score_final y color_final directamente para respetar overrides
    activos (rojo_por_flag_critico, penalizado_por_tiempo, etc.).
    El recálculo propio solo aplica cuando el integrado no está disponible.
    """
    weight_cuant = _normalize_weight(
        getattr(settings, "BOLETIN_WEIGHT_CUANT", 0.65),
        0.65,
    )
    weight_cual = _normalize_weight(
        getattr(settings, "BOLETIN_WEIGHT_CUAL", 0.35),
        0.35,
    )

    total_weight = weight_cuant + weight_cual
    if total_weight <= 0:
        weight_cuant = 0.65
        weight_cual  = 0.35
        total_weight = 1.0

    weight_cuant = weight_cuant / total_weight
    weight_cual  = weight_cual  / total_weight

    score_cuant = _to_float(cuant.get("score_index"))
    score_cual  = _to_float(cual.get("total_porcentaje"))

    # Si el pipeline ya calculó el resultado integrado con overrides,
    # se usa directamente. Nunca recalcular por encima de un override activo.
    if (
        integrado is not None
        and integrado.get("score_final") is not None
        and integrado.get("override") is not None
    ):
        combined_score = _to_float(integrado.get("score_final"))
        etiqueta = _classify_combined_label(combined_score)
        narrative = _build_combined_narrative(
            combined_score,
            etiqueta,
            cuant.get("semaforo"),
            cual.get("etiqueta_total"),
        )
        return {
            "puntaje":   combined_score,
            "etiqueta":  etiqueta,
            "kpi": {
                "cuantitativo": {
                    "puntaje": score_cuant,
                    "peso":    round(weight_cuant, 4),
                },
                "cualitativo": {
                    "puntaje": score_cual,
                    "peso":    round(weight_cual, 4),
                },
            },
            "narrativa": narrative,
        }

    datos_incompletos = False
    if score_cuant is None or score_cual is None:
        datos_incompletos = True
        # Calcular con lo que hay, solo si al menos uno está disponible
        if score_cuant is not None:
            combined_score = round(weight_cuant * score_cuant, 1)
        elif score_cual is not None:
            combined_score = round(weight_cual * score_cual, 1)
        else:
            combined_score = None
    else:
        combined_score = round(
            weight_cuant * score_cuant + weight_cual * score_cual,
            1,
        )

    etiqueta  = _classify_combined_label(combined_score)
    narrative = _build_combined_narrative(
        combined_score,
        etiqueta,
        cuant.get("semaforo"),
        cual.get("etiqueta_total"),
    )

    return {
        "puntaje":   combined_score,
        "etiqueta":  etiqueta,
        "datos_incompletos": datos_incompletos,
        "kpi": {
            "cuantitativo": {
                "puntaje": score_cuant,
                "peso":    round(weight_cuant, 4),
            },
            "cualitativo": {
                "puntaje": score_cual,
                "peso":    round(weight_cual, 4),
            },
        },
        "narrativa": narrative,
    }


def _classify_combined_label(puntaje: Optional[float]) -> Optional[str]:
    """
    Clasifica el puntaje combinado 0-100 en etiquetas.
    Usa los mismos rangos del bloque cualitativo:


      76-100 → fortaleza
      51-75  → en_desarrollo
      26-50  → refuerzo
       0-25  → atencion
    """
    if puntaje is None:
        return None


    if puntaje >= 76:
        return "fortaleza"
    elif puntaje >= 51:
        return "en_desarrollo"
    elif puntaje >= 26:
        return "refuerzo"
    else:
        return "atencion"



def _build_combined_narrative(
    puntaje:       Optional[float],
    etiqueta:      Optional[str],
    semaforo:      Optional[str],
    etiqueta_cual: Optional[str],
) -> str:
    """
    Genera un texto corto para el bloque combinado.
    No reemplaza la recomendación detallada del cuantitativo,
    solo la complementa con la visión 65/35.
    """
    if puntaje is None or etiqueta is None:
        return "Los datos no son suficientes para generar un resumen combinado automático."


    semaforo_norm      = (semaforo      or "").strip().lower()
    etiqueta_cual_norm = (etiqueta_cual or "").strip().lower()


    partes = []


    if etiqueta == "fortaleza":
        partes.append("El desempeño global del estudiante es una fortaleza.")
    elif etiqueta == "en_desarrollo":
        partes.append("El desempeño global está en desarrollo y muestra buen potencial.")
    elif etiqueta == "refuerzo":
        partes.append("El desempeño global requiere refuerzo focalizado.")
    else:
        partes.append("El desempeño global necesita atención especial en esta materia.")


    if semaforo_norm == "verde":
        partes.append("Los resultados cuantitativos indican que puede avanzar de nivel.")
    elif semaforo_norm == "amarillo":
        partes.append("Cuantitativamente está en zona de precaución; conviene consolidar antes de avanzar.")
    elif semaforo_norm == "rojo":
        partes.append("Cuantitativamente está por debajo de lo esperado para este nivel.")


    if etiqueta_cual_norm == "fortaleza":
        partes.append("Las observaciones cualitativas muestran hábitos de estudio sólidos.")
    elif etiqueta_cual_norm == "en_desarrollo":
        partes.append("En lo cualitativo, está construyendo buenos hábitos, aunque aún hay aspectos por madurar.")
    elif etiqueta_cual_norm == "refuerzo":
        partes.append("En lo cualitativo, se recomienda reforzar hábitos y acompañamiento durante el trabajo.")
    elif etiqueta_cual_norm == "atencion":
        partes.append("En lo cualitativo, se observan señales que requieren seguimiento cercano del orientador.")


    return " ".join(partes)