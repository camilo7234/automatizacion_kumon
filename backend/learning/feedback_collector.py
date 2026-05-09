"""
learning/feedback_collector.py
══════════════════════════════════════════════════════════════════════
Módulo PASIVO de recolección de señales — FASE 1.

NO toma decisiones. NO modifica comportamiento existente.
NO para el sistema si falla. NUNCA hace db.commit() propio.

Captura dos tipos de señales por cada video procesado:
  SEÑAL TIPO A — Correcciones del orientador (por métrica)
  SEÑAL TIPO B — Señales cuantitativas del video (fila resumen)
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from database.models import (
        ObservacionCualitativa,
        QualitativeResult,
        TestResult,
    )

logger = logging.getLogger(__name__)


def collect_feedback(
    db: "Session",
    id_job: UUID,
    obs: "ObservacionCualitativa",
    qual: "QualitativeResult | None",
    result: "TestResult",
) -> None:
    """
    Recolecta señales de aprendizaje pasivo y las inserta en
    learning.signal_feedback usando bulk insert (db.add_all).

    Reglas:
      - No lanza excepciones hacia arriba (silencia todo con logger.warning).
      - No hace db.commit() — el caller decide cuándo hacer commit.
      - Si la tabla no existe aún, captura OperationalError sin ruido.
      - Si el módulo learning no existe, el import dentro del caller
        lo absorbe en su propio try/except.

    Produce:
      * Una fila por cada clave en obs.respuestas  (SEÑAL TIPO A)
      * Una fila resumen con metrica=None           (SEÑAL TIPO B)
    """
    try:
        from database.models import SignalFeedback
    except ImportError:
        logger.warning("[learning] SignalFeedback no disponible — ignorando.")
        return

    try:
        subject   = (getattr(obs, "subject",   None) or "")[:20]
        test_code = (getattr(obs, "test_code", None) or "")[:10]

        prefills: dict   = (getattr(qual, "prefills",   None) or {}) if qual else {}
        respuestas: dict = (getattr(obs,  "respuestas", None) or {})

        filas: list[SignalFeedback] = []

        # ── Helpers de conversión segura ─────────────────────────
        def _num(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        def _int(v):
            try:
                return int(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        # ── BUG-4 FIX: construir índice inverso item_id → métricas ──
        # qual.prefills tiene claves de MÉTRICAS (pausas_largas, ritmo_trabajo…)
        # obs.respuestas tiene claves de ITEMS   (fluidez_calculo, mantiene_ritmo…)
        # El loop original hacía prefills.get(item_id) — siempre retornaba {}
        # porque los namespaces son distintos. Nunca se guardaba valor_auto
        # ni confianza_auto reales — los datos de aprendizaje tipo A eran inútiles.
        #
        # Solución: invertir METRICA_A_ITEMS para obtener item_id → [metricas]
        # y desde ahí buscar los prefills crudos del video correctamente.
        try:
            from config.cuestionarios import METRICA_A_ITEMS
            # Construir: { item_id: [metrica1, metrica2, ...] }
            item_a_metricas: dict[str, list[str]] = {}
            for metrica, items in METRICA_A_ITEMS.items():
                for item_id in items:
                    item_a_metricas.setdefault(item_id, []).append(metrica)
        except Exception:
            item_a_metricas = {}

        # ══ SEÑAL TIPO A: una fila por item del formulario ═══════
        for item_id, datos in respuestas.items():
            if not isinstance(datos, dict):
                continue

            # Buscar valor_auto y confianza_auto desde las métricas
            # del video que mapean a este item_id (promedio si hay varias)
            valores_auto:    list[float] = []
            confianzas_auto: list[float] = []

            for metrica in item_a_metricas.get(item_id, []):
                prefill_meta = prefills.get(metrica)
                if not isinstance(prefill_meta, dict):
                    continue
                v = _num(prefill_meta.get("valor"))
                c = _num(prefill_meta.get("confianza"))
                if v is not None:
                    valores_auto.append(v)
                if c is not None:
                    confianzas_auto.append(c)

            valor_auto_final    = round(sum(valores_auto)    / len(valores_auto),    3) if valores_auto    else None
            confianza_auto_final = round(sum(confianzas_auto) / len(confianzas_auto), 3) if confianzas_auto else None

            filas.append(
                SignalFeedback(
                    id_job         = id_job,
                    subject        = subject,
                    test_code      = test_code,
                    metrica        = str(item_id),
                    valor_auto     = valor_auto_final,
                    confianza_auto = confianza_auto_final,
                    valor_final    = _num(datos.get("valor")),
                    fue_corregido  = bool(datos.get("corregido", False)),
                    # Señal B: NULL en fila tipo A
                    activity_ratio    = None,
                    num_rewrites      = None,
                    total_pausas_ms   = None,
                    speech_rate       = None,
                    pct_aciertos      = None,
                    tiempo_ratio      = None,
                    confidence_ocr    = None,
                    etiqueta_final    = None,
                    semaforo          = None,
                    puntaje_combinado = None,
                )
            )

        # ══ SEÑAL TIPO B: fila resumen del job ══════════════════
        # total_pausas_ms: suma de duracion_ms de todos los pause_events
        total_pausas_ms = None
        if qual is not None:
            pause_events = getattr(qual, "pause_events", None) or []
            if isinstance(pause_events, list) and pause_events:
                total_pausas_ms = sum(
                    int(p.get("duracion_ms", 0))
                    for p in pause_events
                    if isinstance(p, dict)
                )

        # tiempo_ratio: study_time / target_time
        tiempo_ratio = None
        study  = _num(getattr(result, "study_time_min",  None))
        target = _num(getattr(result, "target_time_min", None))
        if study is not None and target and target > 0:
            tiempo_ratio = round(study / target, 3)

        filas.append(
            SignalFeedback(
                id_job         = id_job,
                subject        = subject,
                test_code      = test_code,
                metrica        = None,      # ← indica fila resumen
                valor_auto     = None,
                confianza_auto = None,
                valor_final    = None,
                fue_corregido  = False,
                # Señales del video (QualitativeResult)
                activity_ratio  = _num(getattr(qual, "activity_ratio", None)) if qual else None,
                num_rewrites    = _int(getattr(qual, "num_rewrites",   None)) if qual else None,
                total_pausas_ms = total_pausas_ms,
                speech_rate     = _num(getattr(qual, "speech_rate",    None)) if qual else None,
                # Señales de TestResult
                pct_aciertos   = _num(getattr(result, "percentage",      None)),
                tiempo_ratio   = tiempo_ratio,
                confidence_ocr = _num(getattr(result, "confidence_score", None)),
                # Resultado pedagógico final
                etiqueta_final    = getattr(obs,    "etiqueta_cualitativa", None),
                semaforo          = getattr(result, "semaforo",             None),
                puntaje_combinado = _num(getattr(obs, "puntaje_cualitativo", None)),
            )
        )

        if filas:
            db.add_all(filas)
            # ⚠ NO db.commit() — el caller es responsable del commit

    except Exception as exc:   # noqa: BLE001  (captura OperationalError incluido)
        logger.warning(
            "[learning] collect_feedback falló silenciosamente — "
            "las señales de aprendizaje NO se guardaron. Error: %s",
            exc,
        )