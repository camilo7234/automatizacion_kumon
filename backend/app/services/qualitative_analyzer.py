from __future__ import annotations

"""
app/services/qualitative_analyzer.py
══════════════════════════════════════════════════════════════════
Cruza todas las señales del video, audio y cámara frontal para
generar los prefills del formulario cualitativo del orientador.

PRINCIPIO CENTRAL:
  Solo se agrega una métrica a auto_captured_flags si fue
  capturada con confianza >= su umbral individual.
  Si NO se capturó → queda fuera de auto_captured_flags
  y el orientador DEBE completarla en el formulario.

MÉTRICAS POR FUENTE:
  Video  → ritmo, borrones, pausas, actividad, cambios de hoja
  Audio  → fluidez_lectura, velocidad_lectura, bloqueos_lectura
           (solo ESP e ING, solo secciones de lectura en voz alta)
  Cámara → concentracion_visual, postura_distancia
           (FUTURO — cuando se confirme hardware PIP)

MÉTRICAS SIEMPRE MANUALES (orientador):
  postura, autonomia, disciplina, eficiencia, confianza,
  orden_visual, ansiedad_frustracion, concentracion (sin cámara)
  → Estas NUNCA se agregan a auto_captured_flags.
  → Siempre aparecen en el formulario del orientador.

ESTRUCTURA prefills:
  {
    "clave_metrica": {
      "valor":     <valor extraído>,
      "confianza": 0.87,
      "fuente":    "video" | "audio" | "camara"
    }
  }
══════════════════════════════════════════════════════════════════
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# Umbrales de confianza por métrica
# Si la confianza < umbral → no se captura automáticamente
# ══════════════════════════════════════════════════════════════════

CONFIDENCE_THRESHOLDS = {
    # Video
    "ritmo_trabajo":        0.70,
    "num_reescrituras":     0.90,   # objetivo — alta confianza
    "pausas_largas":        0.90,   # objetivo — alta confianza
    "actividad_general":    0.75,
    # Audio (ESP/ING)
    "fluidez_lectura":      0.65,
    "velocidad_lectura":    0.60,
    "bloqueos_lectura":     0.90,
    # Cámara (FUTURO)
    "concentracion_visual": 0.72,
    "postura_distancia":    0.68,
}

# Métricas que SIEMPRE requieren al orientador — nunca automáticas
ALWAYS_MANUAL = {
    "postura",
    "autonomia",
    "disciplina",
    "eficiencia",
    "confianza_actitud",
    "orden_visual",
    "ansiedad_frustracion",
    "concentracion",        # sin cámara frontal activa
    "motivacion",
    "comprension_instrucciones",
}

# ══════════════════════════════════════════════════════════════════
# Estructuras de datos
# ══════════════════════════════════════════════════════════════════

@dataclass
class QualitativeAnalysisResult:
    """
    Resultado consolidado del análisis cualitativo automático.

    prefills:
      Métricas capturadas automáticamente con su valor y confianza.
      Se pre-rellenan en el formulario del orientador.

    auto_captured_flags:
      Lista de claves capturadas con confianza suficiente.
      Estas NO aparecen como preguntas en el formulario.
      El orientador puede verlas pero no se le piden activamente.

    metricas_pendientes:
      Lista de claves que el sistema NO pudo capturar.
      Estas SÍ aparecen como preguntas en el formulario.
    """

    prefills:             dict  = field(default_factory=dict)
    auto_captured_flags:  list  = field(default_factory=list)
    metricas_pendientes:  list  = field(default_factory=list)

    # Señales crudas consolidadas para guardar en qualitative_results
    time_per_section:    dict  = field(default_factory=dict)
    num_rewrites:        int   = 0
    pause_events:        list  = field(default_factory=list)
    activity_ratio:      float = 0.0
    stroke_detail:       dict  = field(default_factory=dict)
    vad_segments:        list  = field(default_factory=list)
    speech_rate:         Optional[float] = None
    silence_events:      list  = field(default_factory=list)
    gaze_data:           Optional[dict] = None

    processing_ms:       int   = 0


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL — Entry point
# ══════════════════════════════════════════════════════════════════

def analyze_qualitative(
    video_result,       # VideoAnalysisResult de video_processor
    audio_result,       # AudioAnalysisResult de audio_analyzer
    face_result,        # FaceAnalysisResult  de face_analyzer
    subject:    str,
    test_code:  str,
) -> QualitativeAnalysisResult:
    """
    Cruza las señales del video, audio y cámara frontal para
    generar prefills y determinar qué métricas van al formulario.

    Args:
        video_result: VideoAnalysisResult
        audio_result: AudioAnalysisResult
        face_result:  FaceAnalysisResult
        subject:      matematicas | ingles | espanol
        test_code:    K1, K2, P1-P6, M1-M3, H, PII, PI, M

    Returns:
        QualitativeAnalysisResult con prefills, auto_captured_flags
        y metricas_pendientes.
    """
    import time
    t_start = time.time()

    result = QualitativeAnalysisResult()

    # ── 1. Copiar señales crudas ──────────────────────────────────
    _copy_raw_signals(result, video_result, audio_result, face_result)

    # ── 2. Analizar señales de video ──────────────────────────────
    _analyze_video_signals(result, video_result)

    # ── 3. Analizar señales de audio (solo ESP e ING) ─────────────
    if subject in ("espanol", "ingles"):
        _analyze_audio_signals(result, audio_result)

    # ── 4. Analizar señales de cámara (solo si activo) ────────────
    if face_result and face_result.enabled and face_result.processing_ok:
        _analyze_face_signals(result, face_result)

    # ── 5. Determinar métricas pendientes para el formulario ──────
    result.metricas_pendientes = _get_pending_metrics(
        result.auto_captured_flags, subject, test_code
    )

    result.processing_ms = int((time.time() - t_start) * 1000)

    logger.info(
        f"Qualitative analysis: "
        f"auto_captured={result.auto_captured_flags} | "
        f"pendientes={result.metricas_pendientes} | "
        f"{result.processing_ms}ms"
    )

    return result


# ══════════════════════════════════════════════════════════════════
# Paso 1 — Copiar señales crudas al resultado
# ══════════════════════════════════════════════════════════════════

def _copy_raw_signals(
    result:       QualitativeAnalysisResult,
    video_result,
    audio_result,
    face_result,
) -> None:
    """Copia las señales crudas de cada módulo al resultado consolidado."""

    # Video
    if video_result:
        result.time_per_section = video_result.time_per_section or {}
        result.num_rewrites     = video_result.num_rewrites or 0
        result.pause_events     = video_result.pause_events  or []
        result.activity_ratio   = video_result.activity_ratio or 0.0
        result.stroke_detail    = video_result.stroke_detail  or {}

    # Audio
    if audio_result and audio_result.processing_ok:
        result.vad_segments   = audio_result.vad_segments   or []
        result.speech_rate    = audio_result.speech_rate
        result.silence_events = audio_result.silence_events or []

    # Cámara frontal
    if face_result and face_result.enabled and face_result.processing_ok:
        result.gaze_data = face_result.to_gaze_dict()


# ══════════════════════════════════════════════════════════════════
# Paso 2 — Analizar señales de video
# ══════════════════════════════════════════════════════════════════

def _analyze_video_signals(
    result:       QualitativeAnalysisResult,
    video_result,
) -> None:
    """
    Extrae métricas cualitativas de las señales de video.

    Métricas que intenta capturar:
      num_reescrituras → conteo objetivo de borrador activado
      pausas_largas    → conteo objetivo de pausas >= 8s
      ritmo_trabajo    → clasificación basada en activity_ratio y strokes
      actividad_general → ratio de actividad (proxy de concentración)
    """
    if not video_result:
        return

    # ── num_reescrituras (borrones) ───────────────────────────────
    # Alta confianza: es un conteo objetivo de activaciones del borrador
    _register_metric(
        result      = result,
        key         = "num_reescrituras",
        valor       = video_result.num_rewrites,
        confianza   = 0.92,
        fuente      = "video",
    )

    # ── pausas_largas ─────────────────────────────────────────────
    # Alta confianza: es un conteo objetivo de inactividad >= 8s
    num_pausas = len(video_result.pause_events)
    _register_metric(
        result    = result,
        key       = "pausas_largas",
        valor     = num_pausas,
        confianza = 0.91,
        fuente    = "video",
    )

    # ── ritmo_trabajo ─────────────────────────────────────────────
    # Basado en activity_ratio y densidad de strokes
    if video_result.activity_ratio > 0:
        ritmo, confianza = _classify_work_rhythm(
            video_result.activity_ratio,
            video_result.stroke_detail,
            video_result.time_per_section,
        )
        _register_metric(
            result    = result,
            key       = "ritmo_trabajo",
            valor     = ritmo,
            confianza = confianza,
            fuente    = "video",
        )

    # ── actividad_general ─────────────────────────────────────────
    # Proxy de concentración general (sin cámara frontal)
    if video_result.activity_ratio > 0:
        _register_metric(
            result    = result,
            key       = "actividad_general",
            valor     = round(video_result.activity_ratio, 3),
            confianza = 0.78,
            fuente    = "video",
        )


def _classify_work_rhythm(
    activity_ratio: float,
    stroke_detail:  dict,
    time_per_section: dict,
) -> tuple[str, float]:
    """
    Clasifica el ritmo de trabajo del prospecto.

    Escala:
      rapido:   activity_ratio > 0.65 y avg_duration_ms bajo
      normal:   activity_ratio 0.35-0.65
      lento:    activity_ratio < 0.35
      irregular: varianza alta entre secciones

    Returns:
        (etiqueta, confianza)
    """
    confidence = 0.72

    # Calcular varianza de actividad entre secciones
    if len(stroke_detail) > 1:
        strokes_per_section = [
            v.get("strokes", 0) for v in stroke_detail.values()
        ]
        if strokes_per_section:
            mean_s  = sum(strokes_per_section) / len(strokes_per_section)
            variance = sum((s - mean_s) ** 2 for s in strokes_per_section) / len(strokes_per_section)
            cv = (variance ** 0.5 / mean_s) if mean_s > 0 else 0

            if cv > 0.5:   # coeficiente de variación alto → irregular
                return "irregular", 0.70

    if activity_ratio > 0.65:
        return "rapido",  confidence
    elif activity_ratio > 0.35:
        return "normal",  confidence
    else:
        return "lento",   confidence


# ══════════════════════════════════════════════════════════════════
# Paso 3 — Analizar señales de audio
# ══════════════════════════════════════════════════════════════════

def _analyze_audio_signals(
    result:       QualitativeAnalysisResult,
    audio_result,
) -> None:
    """
    Integra los prefills de audio generados por audio_analyzer.
    Solo para ESP e ING.

    audio_analyzer ya calculó la confianza de cada métrica.
    Aquí solo registramos las que pasaron el umbral.
    """
    if not audio_result or not audio_result.processing_ok:
        logger.info("Audio no disponible — métricas de lectura quedan pendientes.")
        return

    # Tomar los prefills que ya generó audio_analyzer
    for key, data in audio_result.prefills.items():
        if key in ALWAYS_MANUAL:
            continue
        _register_metric(
            result    = result,
            key       = key,
            valor     = data.get("valor"),
            confianza = data.get("confianza", 0.0),
            fuente    = "audio",
        )


# ══════════════════════════════════════════════════════════════════
# Paso 4 — Analizar señales de cámara frontal (FUTURO)
# ══════════════════════════════════════════════════════════════════

def _analyze_face_signals(
    result:      QualitativeAnalysisResult,
    face_result,
) -> None:
    """
    Integra señales de la cámara frontal cuando esté activa.
    Actualmente no se ejecuta porque face_result.enabled=False.
    """
    if not face_result or not face_result.processing_ok:
        return

    # Concentración visual (proxy de gaze)
    if face_result.pct_mirando_pantalla is not None:
        valor, conf = _classify_visual_attention(
            face_result.pct_mirando_pantalla,
            face_result.confianza,
        )
        _register_metric(
            result    = result,
            key       = "concentracion_visual",
            valor     = valor,
            confianza = conf,
            fuente    = "camara",
        )

    # Distancia / postura
    if face_result.distancia_cm_estimada is not None:
        _register_metric(
            result    = result,
            key       = "postura_distancia",
            valor     = _classify_posture_distance(face_result.distancia_cm_estimada),
            confianza = face_result.confianza * 0.9,
            fuente    = "camara",
        )


def _classify_visual_attention(
    pct_mirando: float,
    face_confidence: float,
) -> tuple[str, float]:
    """Clasifica la atención visual basada en porcentaje mirando pantalla."""
    if pct_mirando >= 0.80:
        return "alta",  round(face_confidence * 0.95, 3)
    elif pct_mirando >= 0.55:
        return "media", round(face_confidence * 0.90, 3)
    else:
        return "baja",  round(face_confidence * 0.85, 3)


def _classify_posture_distance(distancia_cm: float) -> str:
    """
    Clasifica la distancia estimada del niño a la tablet.
    Rango saludable recomendado por Kumon: 30-45 cm.
    """
    if distancia_cm < 25:
        return "muy_cerca"
    elif distancia_cm <= 45:
        return "adecuada"
    else:
        return "lejos"


# ══════════════════════════════════════════════════════════════════
# Paso 5 — Determinar métricas pendientes para el formulario
# ══════════════════════════════════════════════════════════════════


def _get_pending_metrics(
    auto_captured: list[str],
    subject:       str,
    test_code:     str,
) -> list[str]:
    """
    Retorna la lista de métricas que NO fueron capturadas
    automáticamente y que el orientador DEBE completar.

    Las métricas requeridas dependen del nivel y materia.
    Las que están en auto_captured se excluyen del formulario.
    Las que están en ALWAYS_MANUAL siempre van al formulario.
    """
    required = _get_required_metrics(subject, test_code)
    pending  = [m for m in required if m not in auto_captured]
    return pending


def _get_required_metrics(subject: str, test_code: str) -> list[str]:
    """
    Retorna la lista completa de métricas cualitativas requeridas
    para el formulario según materia y nivel.


    Basado en el método Kumon (documentos oficiales Dpto. Pedagógico, mar-2026):
      Todos los niveles:    postura
      Desde K2:             motivacion
      Desde K1:             comprension_instrucciones
      MAT K2:               secuencia_numerica, manejo_lapiz
      MAT K1:               habilidad_suma, manejo_lapiz
      MAT P1-P2:            habilidad_suma, manejo_lapiz,
                            eficiencia, confianza_actitud
      MAT P3-P4:            habilidad_suma_resta, mult_division,
                            eficiencia, confianza_actitud
      MAT P5-P6:            habilidad_suma_resta, fracciones,
                            eficiencia, confianza_actitud
      MAT M1-H:             ritmo_trabajo, autonomia, concentracion,
                            disciplina, eficiencia, confianza_actitud,
                            num_reescrituras, orden_visual,
                            ansiedad_frustracion, pausas_largas
      ESP K2:               vocabulario_diccion, manejo_lapiz
      ESP K1:               lectura_comprension, lectura_voz_alta,
                            manejo_lapiz
      ESP P1-P6:            lectura_voz_alta, comprension_lectora,
                            estructura_escritura, eficiencia,
                            confianza_actitud
      ESP M1-H:             comprension_lectora, estructura_escritura,
                            fluidez_lectura, velocidad_lectura,
                            bloqueos_lectura, ritmo_trabajo, autonomia,
                            concentracion, disciplina, orden_visual,
                            ansiedad_frustracion, eficiencia,
                            confianza_actitud
      ING K:                conexion_sonido_significado, manejo_lapiz,
                            lectura_voz_alta
      ING PII-H:            conexion_sonido_significado, gramatica,
                            escritura_ingles, lectura_voz_alta,
                            fluidez_lectura, velocidad_lectura,
                            bloqueos_lectura, ritmo_trabajo, autonomia,
                            concentracion, disciplina, orden_visual,
                            ansiedad_frustracion, eficiencia,
                            confianza_actitud


    Si el test_code no corresponde a ningún nivel conocido para
    la materia, se registra una advertencia y se retorna el
    conjunto completo de ALWAYS_MANUAL más postura, para que
    el orientador complete manualmente sin que el sistema se detenga.
    """
    # Base: postura siempre requerida en todos los niveles
    metrics: list[str] = ["postura"]


    code = test_code.upper()

    if subject == "matematicas" and code == "M4":
        code = "H"


    # motivacion: universal desde K2 (doc. oficial: todos los niveles)
    metrics.append("motivacion")


    # comprension_instrucciones: desde K1 (K2 usa apoyo del orientador)
    if code != "K2":
        metrics.append("comprension_instrucciones")


    # ── MATEMÁTICAS ───────────────────────────────────────────────
    if subject == "matematicas":
        if code == "K2":
            metrics += ["secuencia_numerica", "manejo_lapiz"]


        elif code == "K1":
            metrics += ["habilidad_suma", "manejo_lapiz"]


        elif code in ("P1", "P2"):
            metrics += [
                "habilidad_suma",
                "manejo_lapiz",
                "eficiencia",
                "confianza_actitud",
            ]


        elif code in ("P3", "P4"):
            metrics += [
                "habilidad_suma_resta",
                "mult_division",
                "eficiencia",
                "confianza_actitud",
            ]


        elif code in ("P5", "P6"):
            metrics += [
                "habilidad_suma_resta",
                "fracciones",
                "eficiencia",
                "confianza_actitud",
            ]


        elif code in ("M1", "M2", "M3", "H"):
            metrics += [
                "ritmo_trabajo",
                "autonomia",
                "concentracion",
                "disciplina",
                "eficiencia",
                "confianza_actitud",
                "num_reescrituras",
                "orden_visual",
                "ansiedad_frustracion",
                "pausas_largas",
            ]


        else:
            # Nivel desconocido para matemáticas: el orientador completa todo manualmente
            logger.warning(
                f"test_code desconocido para matemáticas: '{test_code}'. "
                f"Se usará conjunto ALWAYS_MANUAL completo."
            )
            metrics += sorted(ALWAYS_MANUAL)


    # ── ESPAÑOL ───────────────────────────────────────────────────
    elif subject == "espanol":
        if code == "K2":
            metrics += ["vocabulario_diccion", "manejo_lapiz"]


        elif code == "K1":
            metrics += [
                "lectura_comprension",
                "lectura_voz_alta",
                "manejo_lapiz",
            ]


        elif code in ("P1", "P2", "P3", "P4", "P5", "P6"):
            metrics += [
                "lectura_voz_alta",
                "comprension_lectora",
                "estructura_escritura",
                "eficiencia",
                "confianza_actitud",
            ]


        elif code in ("M1", "M2", "M3", "H"):
            metrics += [
                "comprension_lectora",
                "estructura_escritura",
                "fluidez_lectura",
                "velocidad_lectura",
                "bloqueos_lectura",
                "ritmo_trabajo",
                "autonomia",
                "concentracion",
                "disciplina",
                "orden_visual",
                "ansiedad_frustracion",
                "eficiencia",
                "confianza_actitud",
            ]


        else:
            # Nivel desconocido para español: el orientador completa todo manualmente
            logger.warning(
                f"test_code desconocido para español: '{test_code}'. "
                f"Se usará conjunto ALWAYS_MANUAL completo."
            )
            metrics += sorted(ALWAYS_MANUAL)


    # ── INGLÉS ────────────────────────────────────────────────────
    elif subject == "ingles":
        if code == "K":
            metrics += [
                "conexion_sonido_significado",
                "manejo_lapiz",
                "lectura_voz_alta",
            ]


        elif code in ("PII", "PI", "M", "H"):
            metrics += [
                "conexion_sonido_significado",
                "gramatica",
                "escritura_ingles",
                "lectura_voz_alta",
                "fluidez_lectura",
                "velocidad_lectura",
                "bloqueos_lectura",
                "ritmo_trabajo",
                "autonomia",
                "concentracion",
                "disciplina",
                "orden_visual",
                "ansiedad_frustracion",
                "eficiencia",
                "confianza_actitud",
            ]


        else:
            # Nivel desconocido para inglés: el orientador completa todo manualmente
            logger.warning(
                f"test_code desconocido para inglés: '{test_code}'. "
                f"Se usará conjunto ALWAYS_MANUAL completo."
            )
            metrics += sorted(ALWAYS_MANUAL)


    else:
        # Materia desconocida: advertencia y fallback completo
        logger.warning(
            f"Materia desconocida: '{subject}' con test_code '{test_code}'. "
            f"Se usará conjunto ALWAYS_MANUAL completo."
        )
        metrics += sorted(ALWAYS_MANUAL)


    metrics = list(dict.fromkeys(metrics))
    return metrics

# ══════════════════════════════════════════════════════════════════
# Utilidad interna — registrar métrica
# ══════════════════════════════════════════════════════════════════

def _register_metric(
    result:    QualitativeAnalysisResult,
    key:       str,
    valor:     Any,
    confianza: float,
    fuente:    str,
) -> None:
    """
    Registra una métrica en prefills y, si la confianza es
    suficiente y no es ALWAYS_MANUAL, la agrega a auto_captured_flags.

    Args:
        key:       clave de la métrica
        valor:     valor capturado
        confianza: confianza del sistema (0.0-1.0)
        fuente:    video | audio | camara
    """
    # Las métricas ALWAYS_MANUAL nunca se capturan automáticamente
    if key in ALWAYS_MANUAL:
        return

    threshold = CONFIDENCE_THRESHOLDS.get(key, 0.70)

    # Guardar en prefills siempre (para mostrar como sugerencia si aplica)
    result.prefills[key] = {
        "valor":     valor,
        "confianza": round(confianza, 3),
        "fuente":    fuente,
    }

    # Solo agregar a auto_captured_flags si supera el umbral
    if confianza >= threshold:
        if key not in result.auto_captured_flags:
            result.auto_captured_flags.append(key)
            logger.debug(
                f"Métrica capturada automáticamente: "
                f"{key}={valor} (conf={confianza:.3f} >= {threshold})"
            )
    else:
        logger.debug(
            f"Métrica NO capturada (confianza baja): "
            f"{key}={valor} (conf={confianza:.3f} < {threshold})"
        )
