from __future__ import annotations

"""
app/services/result_calculator.py
══════════════════════════════════════════════════════════════════
Calcula semáforo, starting_point y recommendation a partir de
los datos que Class Navi ya entregó en la pantalla de resumen.

CAMBIOS respecto a versión anterior:
  1. _calculate_no_semaforo ahora usa zonas_ingles del level_rules
     (K Inglés ya tiene starting_point real por score).
  2. _calculate_pages_based detecta tipo=criterios_cualitativos
     (K2 Español → siempre needs_manual_review, sin cálculo).
  3. _calculate_standard maneja starting_point=test_superior/inferior
     como casos semánticos explícitos con semáforo y texto propios.
  4. _calculate_standard detecta starting_point con "/" (doble punto
     de partida en Inglés, ej: "4A 1 / 4A 21") → flag manual review.
══════════════════════════════════════════════════════════════════
"""

import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Constantes
# ══════════════════════════════════════════════════════════════════

NO_SEMAFORO_LEVELS = {
    ("ingles", "K"),
}

PAGES_BASED_LEVELS = {
    ("matematicas", "K2"),
    ("matematicas", "K1"),
    ("espanol",     "K2"),
}

RECOMMENDATIONS = {
    "verde": {
        "default": "Excelente desempeño. El estudiante puede avanzar al siguiente nivel.",
        "pages":   "Excelente desempeño. Completó las páginas requeridas en el tiempo esperado.",
        "test_superior": (
            "Desempeño sobresaliente. Se recomienda aplicar el test del siguiente nivel "
            "para determinar un punto de partida más avanzado."
        ),
    },
    "amarillo": {
        "default": "Buen desempeño. Necesita mejorar la velocidad de respuesta.",
        "score":   "Desempeño aceptable. Se recomienda reforzar antes de avanzar.",
        "pages":   "Completó las páginas pero necesita mejorar velocidad o precisión.",
        "doble_punto": (
            "Punto de partida con dos opciones. Revisar con el orientador cuál "
            "corresponde según el desempeño detallado del estudiante."
        ),
    },
    "rojo": {
        "default": "Necesita reforzar conceptos fundamentales antes de avanzar.",
        "pages":   "No completó las páginas mínimas requeridas. Se recomienda nivel anterior.",
        "test_inferior": (
            "Desempeño insuficiente para este nivel. Se recomienda aplicar el test "
            "del nivel inferior indicado antes de asignar punto de partida."
        ),
    },
    None: {
        "default": "Nivel base. Se inicia desde el principio del programa.",
    },
}


# ══════════════════════════════════════════════════════════════════
# Resultado estructurado
# ══════════════════════════════════════════════════════════════════

class CalculationResult:
    def __init__(self):
        self.semaforo:            Optional[str]     = None
        self.semaforo_detalle:    Optional[str]     = None
        self.current_level:       Optional[str]     = None
        self.starting_point:      Optional[str]     = None
        self.recommendation:      Optional[str]     = None
        self.percentage:          Optional[Decimal] = None
        self.needs_manual_review: bool              = False
        self.review_reasons:      list[str]         = []


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def calculate_result(
    subject:           str,
    test_code:         str,
    correct_answers:   Optional[int],
    total_questions:   Optional[int],
    study_time_min:    Optional[float],
    target_time_min:   Optional[float],
    percentage:        Optional[float],
    level_rules:       dict,
    pagina_3_correcta: Optional[bool] = None,
) -> CalculationResult:

    result = CalculationResult()
    result.current_level = test_code.upper()
    code = test_code.upper()

    # ── Caso 1: Nivel sin semáforo (K Inglés) ────────────────────
    if (subject, code) in NO_SEMAFORO_LEVELS:
        _calculate_no_semaforo(result, correct_answers, total_questions,
                               percentage, level_rules)
        return result

    # ── Caso 2: Niveles basados en páginas ────────────────────────
    if (subject, code) in PAGES_BASED_LEVELS:
        _calculate_pages_based(result, correct_answers, total_questions,
                               study_time_min, target_time_min, level_rules)
        return result

    # ── Caso 3: Niveles estándar ──────────────────────────────────
    _calculate_standard(
        result, subject, code,
        correct_answers, total_questions,
        study_time_min, target_time_min,
        percentage, level_rules,
        pagina_3_correcta,
    )
    return result


# ══════════════════════════════════════════════════════════════════
# Caso 1 — K Inglés (sin semáforo)
# ══════════════════════════════════════════════════════════════════

def _calculate_no_semaforo(
    result:          CalculationResult,
    correct_answers: Optional[int],
    total_questions: Optional[int],
    percentage:      Optional[float],
    level_rules:     dict,                          # ← NUEVO parámetro
) -> None:
    """
    K Inglés: nivel base, sin semáforo.
    CAMBIO: ahora usa zonas_ingles del level_rules para
    calcular el starting_point real en lugar de "Inicio del programa".
    El manejo del lápiz (manejo_lapiz) siempre requiere revisión manual.
    """
    result.semaforo = None

    if correct_answers is None:
        result.needs_manual_review = True
        result.review_reasons.append("No se extrajo número de aciertos del OCR.")
        result.starting_point = "nivel_actual"
        result.recommendation = RECOMMENDATIONS[None]["default"]
        return

    if total_questions:
        pct = round(correct_answers / total_questions * 100, 2)
        result.percentage = Decimal(str(pct))

    # ── Buscar starting_point en zonas_ingles del level_rules ─────
    zonas_ingles = level_rules.get("zonas_ingles", [])
    if zonas_ingles:
        zona = _find_zone_by_score(correct_answers, zonas_ingles)
        if zona:
            result.starting_point = zona.get("starting_point", "7A 1")
        else:
            result.starting_point = "7A 1"
            result.review_reasons.append(
                f"Score {correct_answers} fuera de zonas_ingles. "
                "Se asignó 7A 1 como fallback."
            )
    else:
        # Sin level_rules → fallback clásico
        result.starting_point = "7A 1"
        result.review_reasons.append(
            "zonas_ingles no disponible en level_rules. "
            "Se asignó 7A 1 como fallback."
        )

    # ── Manejo del lápiz siempre requiere revisión manual ─────────
    if level_rules.get("manejo_lapiz"):
        result.needs_manual_review = True
        result.review_reasons.append(
            "K Inglés: criterios de manejo del lápiz (ZI/ZII) "
            "requieren evaluación manual del orientador."
        )

    # ── Texto de recomendación por score ──────────────────────────
    pct_val = float(result.percentage) if result.percentage else 0
    if pct_val >= 87:
        result.recommendation = (
            "Nivel K Inglés superado. Se recomienda aplicar el test "
            "del siguiente nivel (PII)."
        )
    elif pct_val >= 62:
        result.recommendation = (
            "Buen desempeño inicial. Comenzar en el punto de partida "
            "indicado con refuerzo oral."
        )
    else:
        result.recommendation = (
            "Nivel base de Inglés. Iniciar desde el punto de partida "
            "asignado con énfasis en vocabulario oral."
        )

    # Doble punto de partida en K Inglés ("4A 1 / 4A 21")
    if result.starting_point and "/" in result.starting_point:
        result.needs_manual_review = True
        result.review_reasons.append(
            f"Punto de partida doble ({result.starting_point}): "
            "el orientador debe elegir según el desempeño oral del estudiante."
        )

    logger.info(
        f"K Inglés (no semáforo): "
        f"score={correct_answers}/{total_questions} "
        f"starting_point={result.starting_point}"
    )


# ══════════════════════════════════════════════════════════════════
# Caso 2 — Niveles por páginas (K2/K1 MAT, K2 ESP)
# ══════════════════════════════════════════════════════════════════

def _calculate_pages_based(
    result:           CalculationResult,
    correct_answers:  Optional[int],
    total_questions:  Optional[int],
    study_time_min:   Optional[float],
    target_time_min:  Optional[float],
    level_rules:      dict,
) -> None:
    """
    K2/K1 Matemáticas y K2 Español.

    CAMBIO: detecta tipo=criterios_cualitativos (K2 Español).
    K2 Español es evaluación visual por color del orientador →
    siempre needs_manual_review=True, sin cálculo automático.

    K2/K1 Matemáticas usan punto_partida_map numérico → cálculo normal.
    """
    tipo = level_rules.get("tipo", "paginas")

    # ── K2 Español: evaluación cualitativa, sin cálculo automático ─
    if tipo == "criterios_cualitativos":
        result.semaforo           = None
        result.needs_manual_review = True
        result.starting_point     = "nivel_actual"
        result.review_reasons.append(
            "K2 Español: evaluación cualitativa por color (azul/amarillo/verde/rosa/rojo). "
            "El orientador debe asignar el punto de partida manualmente según "
            "los criterios de la gráfica oficial."
        )
        result.recommendation = (
            "Este nivel requiere evaluación presencial del orientador. "
            "El punto de partida se determina por criterios cualitativos de lectura, "
            "no por puntuación numérica."
        )
        logger.info("K2 ESP: criterios_cualitativos → manual review obligatorio")
        return

    # ── K2/K1 MAT: sistema de páginas con mapa numérico ───────────
    if not level_rules:
        result.needs_manual_review = True
        result.review_reasons.append("level_rules vacío. Semáforo no calculable.")
        result.semaforo       = "amarillo"
        result.recommendation = RECOMMENDATIONS["amarillo"]["pages"]
        return

    umbral_paginas = level_rules.get("umbral_paginas", 7)
    umbral_tiempo  = level_rules.get("umbral_tiempo_min", target_time_min or 10)
    punto_map      = level_rules.get("punto_partida_map", {})

    paginas_ok = correct_answers

    if paginas_ok is None:
        result.needs_manual_review = True
        result.review_reasons.append("No se extrajo número de páginas del OCR.")
        result.semaforo       = None
        result.recommendation = "Revisar manualmente: no se pudo extraer resultado."
        return

    if total_questions:
        pct = round(paginas_ok / total_questions * 100, 2)
        result.percentage = Decimal(str(pct))

    tiempo_ok = (study_time_min is None) or (study_time_min <= umbral_tiempo)

    if paginas_ok >= umbral_paginas and tiempo_ok:
        result.semaforo         = "verde"
        result.semaforo_detalle = f"Completó {paginas_ok} páginas en tiempo"
        result.recommendation   = RECOMMENDATIONS["verde"]["pages"]
    elif paginas_ok >= umbral_paginas and not tiempo_ok:
        result.semaforo         = "amarillo"
        result.semaforo_detalle = (
            f"Completó {paginas_ok} páginas pero tardó "
            f"{study_time_min:.1f} min (TPT={umbral_tiempo})"
        )
        result.recommendation = RECOMMENDATIONS["amarillo"]["pages"]
    else:
        result.semaforo         = "rojo"
        result.semaforo_detalle = (
            f"Solo completó {paginas_ok} páginas (mínimo: {umbral_paginas})"
        )
        result.recommendation = RECOMMENDATIONS["rojo"]["pages"]

    result.starting_point = _lookup_starting_point_pages(
        paginas_ok, umbral_paginas, punto_map
    )

    logger.info(
        f"Pages-based: paginas={paginas_ok}/{total_questions} "
        f"semaforo={result.semaforo} "
        f"starting_point={result.starting_point}"
    )


def _lookup_starting_point_pages(
    paginas_ok:    int,
    umbral_minimo: int,
    punto_map:     dict,
) -> str:
    if paginas_ok < umbral_minimo:
        return punto_map.get("menos_7", punto_map.get("menos_umbral", "nivel_actual"))

    key = str(paginas_ok)
    if key in punto_map:
        return punto_map[key]

    for k in sorted(
        punto_map.keys(),
        key=lambda x: int(x) if x.isdigit() else -1,
        reverse=True
    ):
        if k.isdigit() and int(k) <= paginas_ok:
            return punto_map[k]

    return "nivel_actual"


# ══════════════════════════════════════════════════════════════════
# Caso 3 — Niveles estándar (P1–H todos, PII–H Inglés)
# ══════════════════════════════════════════════════════════════════

def _calculate_standard(
    result:            CalculationResult,
    subject:           str,
    code:              str,
    correct_answers:   Optional[int],
    total_questions:   Optional[int],
    study_time_min:    Optional[float],
    target_time_min:   Optional[float],
    percentage:        Optional[float],
    level_rules:       dict,
    pagina_3_correcta: Optional[bool],
) -> None:
    # ── Validar datos de entrada ─────────────────────────────────
    if correct_answers is None and percentage is None:
        result.needs_manual_review = True
        result.review_reasons.append("Sin score del OCR: ni aciertos ni porcentaje.")
        result.semaforo       = None
        result.recommendation = "Revisar manualmente: OCR no extrajo resultado."
        return

    if not level_rules or "zonas" not in level_rules:
        result.needs_manual_review = True
        result.review_reasons.append("level_rules sin zonas en template.")
        _calculate_emergency_semaforo(
            result, correct_answers, total_questions, percentage,
            study_time_min, target_time_min
        )
        return

    # ── Calcular porcentaje ──────────────────────────────────────
    if correct_answers is not None and total_questions:
        pct = round(correct_answers / total_questions * 100, 2)
        result.percentage = Decimal(str(pct))
    elif percentage is not None:
        result.percentage = Decimal(str(percentage))
        pct = percentage
    else:
        pct = None

    # ── Buscar zona por aciertos absolutos ────────────────────────
    zona = None
    zonas = level_rules.get("zonas", [])

    if correct_answers is not None:
        zona = _find_zone_by_score(correct_answers, zonas)

    if zona is None and pct is not None and total_questions:
        approx_score = round(pct / 100 * total_questions)
        zona = _find_zone_by_score(approx_score, zonas)

    if zona is None:
        result.needs_manual_review = True
        result.review_reasons.append(
            f"Score {correct_answers} fuera de todas las zonas del template."
        )
        _calculate_emergency_semaforo(
            result, correct_answers, total_questions, pct,
            study_time_min, target_time_min
        )
        return

    # ── Obtener starting_point y zona ────────────────────────────
    zona_nombre    = zona.get("nombre", "rojo")
    starting_point = zona.get("starting_point", "nivel_actual")

    # ── CAMBIO: manejar test_superior / test_inferior ────────────
    if starting_point == "test_superior":
        result.semaforo         = "verde"
        result.starting_point   = "test_superior"
        result.semaforo_detalle = (
            f"Score {correct_answers}/{total_questions} supera el umbral máximo del nivel"
        )
        result.recommendation = RECOMMENDATIONS["verde"]["test_superior"]
        logger.info(
            f"Standard: {subject} {code} | "
            f"score={correct_answers} → test_superior"
        )
        return

    if starting_point == "test_inferior":
        result.semaforo         = "rojo"
        result.starting_point   = "test_inferior"
        test_inf_ref            = level_rules.get("test_inferior_referencia", "nivel inferior")
        result.semaforo_detalle = (
            f"Score {correct_answers}/{total_questions} por debajo del umbral mínimo del nivel"
        )
        result.recommendation = (
            RECOMMENDATIONS["rojo"]["test_inferior"] +
            (f" Test sugerido: {test_inf_ref}." if test_inf_ref else "")
        )
        logger.info(
            f"Standard: {subject} {code} | "
            f"score={correct_answers} → test_inferior ({test_inf_ref})"
        )
        return

    # ── CAMBIO: doble starting_point (Inglés "4A 1 / 4A 21") ─────
    if "/" in str(starting_point):
        result.needs_manual_review = True
        result.review_reasons.append(
            f"Punto de partida doble ({starting_point}): "
            "el orientador debe elegir según el desempeño detallado del estudiante."
        )
        result.recommendation = RECOMMENDATIONS["amarillo"]["doble_punto"]

    result.starting_point = starting_point

    # ── Semáforo base por nombre de zona ─────────────────────────
    if zona_nombre.startswith("verde"):
        semaforo_base = "verde"
    elif zona_nombre.startswith("amarillo") or zona_nombre.startswith("am"):
        semaforo_base = "amarillo"
    else:
        semaforo_base = "rojo"

    # ── Factor tiempo: verde → amarillo si se excedió el TPT ─────
    umbral_tiempo = level_rules.get("umbral_tiempo_min", target_time_min)

    if (
        semaforo_base == "verde"
        and study_time_min is not None
        and umbral_tiempo is not None
        and study_time_min > umbral_tiempo
    ):
        semaforo_base = "amarillo"
        result.semaforo_detalle = (
            f"Score en zona verde ({correct_answers}/{total_questions}) "
            f"pero tardó {study_time_min:.1f} min (TPT={umbral_tiempo} min)"
        )
        if not result.recommendation or "/" not in str(starting_point):
            result.recommendation = RECOMMENDATIONS["amarillo"]["default"]
    else:
        result.semaforo_detalle = (
            f"Score={correct_answers}/{total_questions} | Zona={zona_nombre}"
        )
        if not result.recommendation or "/" not in str(starting_point):
            result.recommendation = RECOMMENDATIONS[semaforo_base]["default"]

    result.semaforo = semaforo_base

    # ── pagina_3_correcta ────────────────────────────────────────
    if pagina_3_correcta is not None:
        _apply_pagina_3_rule(result, pagina_3_correcta, semaforo_base,
                             correct_answers, zonas)

    logger.info(
        f"Standard: {subject} {code} | "
        f"score={correct_answers}/{total_questions} "
        f"time={study_time_min}/{umbral_tiempo} "
        f"semaforo={result.semaforo} "
        f"starting_point={result.starting_point}"
    )


def _find_zone_by_score(score: int, zonas: list[dict]) -> Optional[dict]:
    for zona in zonas:
        z_min = zona.get("min", 0)
        z_max = zona.get("max", 0)
        if z_min <= score <= z_max:
            return zona
    return None


def _apply_pagina_3_rule(
    result:          CalculationResult,
    pagina_3_ok:     bool,
    semaforo_base:   str,
    correct_answers: Optional[int],
    zonas:           list[dict],
) -> None:
    if not pagina_3_ok and semaforo_base in ("amarillo", "verde"):
        result.needs_manual_review = True
        result.review_reasons.append(
            "Página 3 incorrecta con score borderline. "
            "Verificar con instructivo oficial si afecta el punto de partida."
        )
        logger.warning(
            "pagina_3_correcta=False con semaforo borderline. "
            "Flagged para revisión manual."
        )


def _calculate_emergency_semaforo(
    result:          CalculationResult,
    correct_answers: Optional[int],
    total_questions: Optional[int],
    percentage:      Optional[float],
    study_time_min:  Optional[float] = None,
    target_time_min: Optional[float] = None,
) -> None:
    """
    Fallback cuando level_rules no está disponible.
    Siempre marca needs_manual_review=True.
    """
    result.needs_manual_review = True

    if correct_answers is not None and total_questions:
        pct = round(correct_answers / total_questions * 100, 2)
        result.percentage = Decimal(str(pct))
    elif percentage is not None:
        pct = percentage
        result.percentage = Decimal(str(pct))
    else:
        pct = None

    if pct is None:
        result.semaforo       = None
        result.recommendation = "Sin datos suficientes para calcular semáforo."
        return

    time_ratio = None
    if study_time_min is not None and target_time_min and target_time_min > 0:
        time_ratio = study_time_min / target_time_min

    tiempo_excedido    = time_ratio is not None and time_ratio > 1.50
    tiempo_ligeramente = time_ratio is not None and time_ratio > 1.10

    if pct >= 90:
        semaforo_base = "verde"
    elif pct >= 75:
        semaforo_base = "amarillo"
    else:
        semaforo_base = "rojo"

    if tiempo_excedido and semaforo_base in ("verde", "amarillo"):
        semaforo_base = "rojo"
        result.semaforo_detalle = (
            f"Tiempo excedido: {study_time_min:.1f}/{target_time_min:.1f} min "
            f"({time_ratio:.0%} del TPT) | pct={pct:.1f}%"
        )
    elif tiempo_ligeramente and semaforo_base == "verde":
        semaforo_base = "amarillo"
        result.semaforo_detalle = (
            f"Score verde ({pct:.1f}%) pero lento: "
            f"{study_time_min:.1f}/{target_time_min:.1f} min ({time_ratio:.0%} TPT)"
        )
    else:
        result.semaforo_detalle = (
            f"Cálculo normalizado: pct={pct:.1f}% "
            f"| tiempo={f'{time_ratio:.0%} TPT' if time_ratio else 'desconocido'}"
        )

    result.semaforo       = semaforo_base
    result.starting_point = "nivel_actual"
    result.recommendation = RECOMMENDATIONS[semaforo_base]["default"]

    logger.warning(
        f"Emergency semáforo: pct={pct:.1f}% "
        f"time_ratio={f'{time_ratio:.2f}' if time_ratio else 'N/A'} "
        f"→ {result.semaforo} (level_rules no disponible)"
    )


# ══════════════════════════════════════════════════════════════════
# Utilidades públicas
# ══════════════════════════════════════════════════════════════════

def has_semaforo(subject: str, test_code: str) -> bool:
    return (subject, test_code.upper()) not in NO_SEMAFORO_LEVELS


def is_pages_based(subject: str, test_code: str) -> bool:
    return (subject, test_code.upper()) in PAGES_BASED_LEVELS


def get_time_ratio(
    study_time_min:  Optional[float],
    target_time_min: Optional[float],
) -> Optional[float]:
    if study_time_min is None or target_time_min is None or target_time_min == 0:
        return None
    return round(study_time_min / target_time_min, 3)