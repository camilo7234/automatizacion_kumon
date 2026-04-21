from __future__ import annotations

"""
app/services/audio_analyzer.py
══════════════════════════════════════════════════════════════════
Análisis de audio para tests de ESPAÑOL e INGLÉS únicamente.
MATEMÁTICAS no aplica — el caller debe verificar antes de invocar.

FLUJO:
  1. detect_reading_sections()
       Usa los frames del video (via page_changes y OCR ligero)
       para identificar qué segmentos de tiempo corresponden a
       secciones de "lectura en voz alta".
       Detecta textos como "Lee el siguiente texto", "Read aloud",
       "Lee en voz alta", "Read the following" en el frame.

  2. analyze_audio()
       Entry point principal. Recibe el WAV temporal extraído
       por video_processor.extract_audio_track().
       Coordina VAD, speech_rate y silence_events.
       Solo analiza los segmentos de lectura en voz alta.
       Elimina el WAV temporal al finalizar.

  3. run_vad()
       Voice Activity Detection con webrtcvad.
       Retorna segmentos donde hay voz detectada.

  4. calculate_speech_rate()
       Estima palabras por segundo en los segmentos de voz.
       Método: energía RMS + zero crossing rate via librosa.
       (Sin modelo de reconocimiento de voz — solo señal acústica)

  5. detect_silences()
       Detecta silencios prolongados dentro de una sección de
       lectura. Un silencio largo = posible bloqueo o dificultad.

REGLA CRÍTICA — auto_captured_flags:
  Si un aspecto NO se pudo extraer con confianza suficiente,
  NO se agrega a auto_captured_flags y queda pendiente para
  que el orientador lo complete en el formulario cualitativo.
  Si SÍ se extrajo → se agrega a auto_captured_flags y NO
  aparece como pregunta en el formulario.

MÉTRICAS KUMON PARA LECTURA EN VOZ ALTA:
  Según el método Kumon, los aspectos evaluados en lectura son:
    - Fluidez:      lee sin interrupciones largas (VAD continuo)
    - Velocidad:    palabras por segundo dentro del rango esperado
    - Bloqueos:     silencios >8s dentro de una sección de lectura
  Pronunciación e intonación NO se evalúan automáticamente
  (requieren criterio pedagógico del orientador).
══════════════════════════════════════════════════════════════════
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# Constantes
# ══════════════════════════════════════════════════════════════════

# VAD
VAD_AGGRESSIVENESS     = 2       # 0-3. 2 = balance ruido ambiental / voz
VAD_FRAME_MS           = 30      # ms por frame VAD (10, 20 o 30 — obligatorio webrtcvad)
VAD_SAMPLE_RATE        = 16000   # Hz — debe coincidir con extract_audio_track
VAD_MIN_VOICE_MS       = 300     # ms mínimos de voz continua para contar segmento
VAD_PADDING_MS         = 300     # ms de padding al inicio/fin de cada segmento

# Silencios dentro de lectura
SILENCE_MIN_DURATION_MS = 8000   # silencio ≥ 8s dentro de lectura = posible bloqueo

# Speech rate
SPEECH_RATE_CONFIDENCE_MIN = 0.6  # confianza mínima para agregar a auto_captured_flags

# Patrones de texto en pantalla que indican sección de lectura en voz alta
READING_ALOUD_PATTERNS = [
    "lee el siguiente",
    "lee en voz alta",
    "lee el texto",
    "read aloud",
    "read the following",
    "read this",
    "lee este",
    "lee la siguiente",
]

# Confianza mínima OCR para confiar en que detectó texto de lectura
READING_OCR_CONFIDENCE  = 0.55

# ══════════════════════════════════════════════════════════════════
# Estructuras de datos
# ══════════════════════════════════════════════════════════════════

@dataclass
class ReadingSection:
    """
    Segmento del video donde el prospecto debe leer en voz alta.
    Detectado por OCR sobre el frame de esa sección.
    """
    seccion_id:   str              # "seccion_3", "seccion_5", etc.
    inicio_ms:    float
    fin_ms:       float
    texto_found:  str = ""         # texto que triggereó la detección
    confidence:   float = 0.0


@dataclass
class AudioAnalysisResult:
    """
    Resultado del análisis de audio.
    Se persiste en qualitative_results (campos de audio).

    auto_captured_flags: claves de métricas capturadas con confianza
    suficiente. Solo estas NO aparecen en el formulario del orientador.
    """
    # Segmentos de voz detectados por VAD
    vad_segments:   list = field(default_factory=list)
    # [{"inicio_ms": 5000, "fin_ms": 8200}, ...]

    # Velocidad de lectura estimada (palabras/segundo)
    speech_rate:    Optional[float] = None

    # Silencios prolongados dentro de secciones de lectura
    silence_events: list = field(default_factory=list)
    # [{"inicio_ms": 22000, "duracion_ms": 11000, "seccion": "seccion_3"}, ...]

    # Secciones de lectura detectadas
    reading_sections: list = field(default_factory=list)

    # Métricas capturadas automáticamente con confianza suficiente
    # Solo estas NO aparecen en el formulario del orientador
    auto_captured_flags: list = field(default_factory=list)

    # Prefills generados para el formulario
    # {"fluidez_lectura": {"valor": "fluida", "confianza": 0.87}, ...}
    prefills: dict = field(default_factory=dict)

    # Meta
    audio_duration_ms: float = 0.0
    processing_ok:     bool  = False
    skip_reason:       Optional[str] = None   # razón si se omitió el análisis


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL — Entry point
# ══════════════════════════════════════════════════════════════════

def analyze_audio(
    wav_path: str,
    subject: str,
    page_changes: list[dict],
    video_path: str,
    total_frames: int,
    fps: float,
) -> AudioAnalysisResult:
    """
    Analiza el audio del test. Solo para ESP e ING.

    Args:
        wav_path:     ruta al WAV temporal (16kHz mono)
        subject:      espanol | ingles
        page_changes: cambios de página detectados por video_processor
        video_path:   ruta al video original (para OCR de frames de lectura)
        total_frames: total de frames del video
        fps:          fps del video

    Returns:
        AudioAnalysisResult con vad_segments, speech_rate,
        silence_events, auto_captured_flags y prefills.
    """
    result = AudioAnalysisResult()

    # Guardia: solo ESP e ING
    if subject == "matematicas":
        result.skip_reason = "matematicas no requiere análisis de audio"
        logger.info("Audio: omitido (matematicas)")
        return result

    if not wav_path or not os.path.exists(wav_path):
        result.skip_reason = "archivo WAV no disponible"
        logger.warning("Audio: WAV no encontrado, análisis omitido")
        return result

    try:
        import librosa

        # Cargar audio
        audio_np, sr = librosa.load(wav_path, sr=VAD_SAMPLE_RATE, mono=True)
        result.audio_duration_ms = len(audio_np) / sr * 1000
        logger.info(
            f"Audio cargado: {result.audio_duration_ms/1000:.1f}s | sr={sr}Hz"
        )

        # Paso 1: Detectar secciones de lectura en voz alta
        result.reading_sections = detect_reading_sections(
            video_path, page_changes, total_frames, fps
        )
        logger.info(
            f"Secciones de lectura detectadas: {len(result.reading_sections)}"
        )

        # Paso 2: VAD sobre segmentos de lectura
        # Si no se detectaron secciones de lectura → VAD sobre todo el audio
        if result.reading_sections:
            vad_segments, silence_events = _analyze_reading_windows(
                audio_np, sr, result.reading_sections
            )
        else:
            logger.warning(
                "No se detectaron secciones de lectura por OCR. "
                "Aplicando VAD sobre audio completo."
            )
            vad_segments = run_vad(audio_np, sr)
            silence_events = detect_silences(
                audio_np, sr, vad_segments, "audio_completo"
            )

        result.vad_segments   = vad_segments
        result.silence_events = silence_events

        # Paso 3: Speech rate (solo si hay segmentos de voz)
        if vad_segments:
            speech_rate, sr_confidence = calculate_speech_rate(
                audio_np, sr, vad_segments
            )
            result.speech_rate = speech_rate

            # Solo marcar como capturado si la confianza es suficiente
            if sr_confidence >= SPEECH_RATE_CONFIDENCE_MIN and speech_rate is not None:
                result.auto_captured_flags.append("velocidad_lectura")
                result.prefills["velocidad_lectura"] = {
                    "valor":     _classify_speech_rate(speech_rate),
                    "confianza": round(sr_confidence, 3),
                }

        # Paso 4: Evaluar fluidez basada en VAD y silencios
        if vad_segments:
            fluidez_valor, fluidez_conf = _evaluate_fluency(
                vad_segments, silence_events, result.audio_duration_ms
            )
            if fluidez_conf >= 0.65:
                result.auto_captured_flags.append("fluidez_lectura")
                result.prefills["fluidez_lectura"] = {
                    "valor":     fluidez_valor,
                    "confianza": round(fluidez_conf, 3),
                }

        # Paso 5: Bloqueos (silencios largos dentro de lectura)
        if silence_events:
            result.auto_captured_flags.append("bloqueos_lectura")
            result.prefills["bloqueos_lectura"] = {
                "valor":     len(silence_events),
                "confianza": 0.90,   # alta confianza: silencio es objetivo
            }

        result.processing_ok = True
        logger.info(
            f"Audio procesado OK. "
            f"VAD segments={len(vad_segments)} | "
            f"silencios={len(silence_events)} | "
            f"speech_rate={result.speech_rate} | "
            f"flags={result.auto_captured_flags}"
        )

    except Exception as e:
        logger.error(f"Error en análisis de audio: {e}", exc_info=True)
        result.skip_reason = f"error en análisis: {str(e)[:100]}"
        result.processing_ok = False

    finally:
        # Eliminar WAV temporal siempre, haya o no error
        _cleanup_wav(wav_path)

    return result


# ══════════════════════════════════════════════════════════════════
# PASO 1 — Detectar secciones de lectura en voz alta
# ══════════════════════════════════════════════════════════════════

def detect_reading_sections(
    video_path: str,
    page_changes: list[dict],
    total_frames: int,
    fps: float,
) -> list[dict]:
    """
    Usa OCR sobre el primer frame de cada sección para detectar
    si esa sección contiene instrucción de lectura en voz alta.

    Busca patrones como:
      "Lee el siguiente texto", "Read aloud", "Lee en voz alta", etc.

    Returns:
        Lista de dicts:
        [{"seccion_id": "seccion_3", "inicio_ms": 45000, "fin_ms": 90000}, ...]
    """
    import cv2

    reading_sections = []

    try:
        from app.services.ocr_service import get_ocr_reader
        reader = get_ocr_reader()
    except Exception:
        logger.warning("OCR no disponible para detectar secciones de lectura.")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    try:
        # Construir lista de secciones con sus rangos de tiempo
        tail_start_ms = max(
            0, total_frames - int(15 * fps)
        ) / fps * 1000

        boundaries_ms = [0.0]
        for change in page_changes:
            boundaries_ms.append(change["timestamp_ms"])
        boundaries_ms.append(tail_start_ms)

        for i in range(len(boundaries_ms) - 1):
            sec_id    = f"seccion_{i + 1}"
            inicio_ms = boundaries_ms[i]
            fin_ms    = boundaries_ms[i + 1]

            # Leer el frame del inicio de la sección (+ 500ms para estabilizar)
            target_ms = inicio_ms + 500
            target_frame = int(target_ms / 1000 * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()

            if not ret:
                continue

            # OCR solo en la mitad superior del frame (instrucciones suelen estar arriba)
            h = frame.shape[0]
            roi = frame[:int(h * 0.55), :]

            try:
                raw = reader.readtext(roi, detail=1, paragraph=False)
                full_text = " ".join(t.lower() for (_, t, _) in raw)

                is_reading = any(
                    pattern in full_text
                    for pattern in READING_ALOUD_PATTERNS
                )

                if is_reading:
                    # Obtener el texto que triggereó la detección
                    matched_pattern = next(
                        p for p in READING_ALOUD_PATTERNS if p in full_text
                    )
                    avg_conf = (
                        sum(c for (_, _, c) in raw) / len(raw)
                        if raw else 0.0
                    )

                    if avg_conf >= READING_OCR_CONFIDENCE:
                        reading_sections.append({
                            "seccion_id":  sec_id,
                            "inicio_ms":   inicio_ms,
                            "fin_ms":      fin_ms,
                            "texto_found": matched_pattern,
                            "confidence":  round(avg_conf, 3),
                        })
                        logger.info(
                            f"Sección de lectura detectada: {sec_id} "
                            f"({inicio_ms:.0f}ms-{fin_ms:.0f}ms) "
                            f"| texto='{matched_pattern}' "
                            f"| conf={avg_conf:.2f}"
                        )

            except Exception as e:
                logger.debug(f"OCR falló en sección {sec_id}: {e}")
                continue

    finally:
        cap.release()

    return reading_sections


# ══════════════════════════════════════════════════════════════════
# PASO 2 — VAD y silencios sobre ventanas de lectura
# ══════════════════════════════════════════════════════════════════

def _analyze_reading_windows(
    audio_np: np.ndarray,
    sr: int,
    reading_sections: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Aplica VAD y detección de silencios únicamente dentro de
    los segmentos de lectura en voz alta detectados.
    """
    all_vad_segments:   list[dict] = []
    all_silence_events: list[dict] = []

    for section in reading_sections:
        inicio_ms = section["inicio_ms"]
        fin_ms    = section["fin_ms"]
        sec_id    = section["seccion_id"]

        # Extraer ventana de audio
        start_sample = int(inicio_ms / 1000 * sr)
        end_sample   = int(fin_ms   / 1000 * sr)
        window_audio = audio_np[start_sample:end_sample]

        if len(window_audio) < sr * 0.5:   # menos de 0.5s → saltar
            continue

        # VAD sobre esta ventana
        vad_segs = run_vad(window_audio, sr, offset_ms=inicio_ms)
        all_vad_segments.extend(vad_segs)

        # Silencios dentro de esta ventana
        silences = detect_silences(window_audio, sr, vad_segs, sec_id, offset_ms=inicio_ms)
        all_silence_events.extend(silences)

    return all_vad_segments, all_silence_events


# ══════════════════════════════════════════════════════════════════
# PASO 2.A — VAD (Voice Activity Detection)
# ══════════════════════════════════════════════════════════════════

def run_vad(
    audio_np: np.ndarray,
    sr: int,
    offset_ms: float = 0.0,
) -> list[dict]:
    """
    Detecta segmentos de voz usando webrtcvad.

    Args:
        audio_np:  audio como numpy float32 (ya a 16kHz mono)
        sr:        sample rate (debe ser 16000)
        offset_ms: offset en ms para ajustar timestamps al video original

    Returns:
        [{"inicio_ms": X, "fin_ms": Y}, ...]
    """
    try:
        import webrtcvad
    except ImportError:
        logger.error("webrtcvad no instalado.")
        return []

    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

    # Convertir float32 → int16 (requerido por webrtcvad)
    audio_int16 = (audio_np * 32767).astype(np.int16)
    audio_bytes = audio_int16.tobytes()

    frame_length = int(sr * VAD_FRAME_MS / 1000)   # samples por frame
    frame_bytes  = frame_length * 2                 # bytes por frame (int16)

    segments     = []
    voice_frames = []
    in_voice     = False
    voice_start_ms = 0.0

    for i in range(0, len(audio_bytes) - frame_bytes, frame_bytes):
        chunk      = audio_bytes[i:i + frame_bytes]
        frame_ms   = (i // frame_bytes) * VAD_FRAME_MS
        timestamp_ms = frame_ms + offset_ms

        try:
            is_speech = vad.is_speech(chunk, sr)
        except Exception:
            is_speech = False

        if is_speech:
            if not in_voice:
                in_voice = True
                voice_start_ms = timestamp_ms
            voice_frames.append(timestamp_ms)
        else:
            if in_voice:
                duracion = timestamp_ms - voice_start_ms
                if duracion >= VAD_MIN_VOICE_MS:
                    segments.append({
                        "inicio_ms": round(voice_start_ms, 1),
                        "fin_ms":    round(timestamp_ms, 1),
                    })
                in_voice = False
                voice_frames = []

    # Cerrar último segmento si el audio termina con voz
    if in_voice and voice_frames:
        duracion = voice_frames[-1] - voice_start_ms
        if duracion >= VAD_MIN_VOICE_MS:
            segments.append({
                "inicio_ms": round(voice_start_ms, 1),
                "fin_ms":    round(voice_frames[-1], 1),
            })

    logger.debug(f"VAD: {len(segments)} segmentos de voz detectados")
    return segments


# ══════════════════════════════════════════════════════════════════
# PASO 2.B — Silencios prolongados dentro de lectura
# ══════════════════════════════════════════════════════════════════

def detect_silences(
    audio_np: np.ndarray,
    sr: int,
    vad_segments: list[dict],
    seccion_id: str,
    offset_ms: float = 0.0,
) -> list[dict]:
    """
    Detecta silencios prolongados entre segmentos de voz.
    Un silencio >= SILENCE_MIN_DURATION_MS dentro de una sección
    de lectura indica posible bloqueo o dificultad de comprensión.

    Args:
        vad_segments: segmentos de voz ya calculados
        seccion_id:   identificador de la sección para el reporte
        offset_ms:    offset para ajustar al tiempo absoluto del video

    Returns:
        [{"inicio_ms": X, "duracion_ms": Y, "seccion": Z}, ...]
    """
    if not vad_segments:
        return []

    silences = []
    window_duration_ms = len(audio_np) / sr * 1000

    # Calcular los huecos entre segmentos de voz
    prev_end_ms = offset_ms
    for seg in sorted(vad_segments, key=lambda s: s["inicio_ms"]):
        gap_ms = seg["inicio_ms"] - prev_end_ms
        if gap_ms >= SILENCE_MIN_DURATION_MS:
            silences.append({
                "inicio_ms":   round(prev_end_ms, 1),
                "fin_ms":      round(seg["inicio_ms"], 1),
                "duracion_ms": round(gap_ms, 1),
                "seccion":     seccion_id,
            })
            logger.debug(
                f"Silencio detectado en {seccion_id}: "
                f"{prev_end_ms:.0f}ms → {seg['inicio_ms']:.0f}ms "
                f"({gap_ms:.0f}ms)"
            )
        prev_end_ms = seg["fin_ms"]

    # Silencio después del último segmento de voz
    window_end_ms = offset_ms + window_duration_ms
    final_gap = window_end_ms - prev_end_ms
    if final_gap >= SILENCE_MIN_DURATION_MS:
        silences.append({
            "inicio_ms":   round(prev_end_ms, 1),
            "fin_ms":      round(window_end_ms, 1),
            "duracion_ms": round(final_gap, 1),
            "seccion":     seccion_id,
        })

    return silences


# ══════════════════════════════════════════════════════════════════
# PASO 3 — Velocidad de lectura (speech rate)
# ══════════════════════════════════════════════════════════════════

def calculate_speech_rate(
    audio_np: np.ndarray,
    sr: int,
    vad_segments: list[dict],
) -> tuple[Optional[float], float]:
    """
    Estima la velocidad de lectura en palabras por segundo.

    Método (sin ASR — solo análisis de señal acústica):
      1. Extraer solo los segmentos de voz (del VAD).
      2. Calcular Zero Crossing Rate (ZCR) — proxy de articulación.
      3. Detectar picos de energía RMS → aproxima sílabas.
      4. Convertir sílabas → palabras (ratio español/inglés ≈ 2.5 síl/palabra).
      5. Dividir por duración total de voz en segundos.

    Este método es una APROXIMACIÓN. La confianza depende de
    la calidad del audio. Si la confianza es baja (<0.6),
    el speech_rate NO se agrega a auto_captured_flags y el
    orientador debe calificarlo manualmente.

    Returns:
        (palabras_por_segundo, confianza) o (None, 0.0) si falla
    """
    try:
        import librosa

        if not vad_segments:
            return None, 0.0

        # Duración total de voz activa
        total_voice_ms = sum(
            s["fin_ms"] - s["inicio_ms"] for s in vad_segments
        )
        if total_voice_ms < 1000:   # menos de 1 segundo de voz → no confiable
            return None, 0.0

        total_voice_s = total_voice_ms / 1000

        # Concatenar solo los segmentos de voz para el análisis
        voice_chunks = []
        for seg in vad_segments:
            start = int(seg["inicio_ms"] / 1000 * sr)
            end   = int(seg["fin_ms"]   / 1000 * sr)
            chunk = audio_np[start:end]
            if len(chunk) > 0:
                voice_chunks.append(chunk)

        if not voice_chunks:
            return None, 0.0

        voice_audio = np.concatenate(voice_chunks)

        # Detectar picos de energía RMS como proxy de sílabas
        frame_length = int(sr * 0.025)   # 25ms frames
        hop_length   = int(sr * 0.010)   # 10ms hop

        rms = librosa.feature.rms(
            y=voice_audio,
            frame_length=frame_length,
            hop_length=hop_length,
        )[0]

        # Normalizar RMS
        if rms.max() == 0:
            return None, 0.0

        rms_norm = rms / rms.max()
        threshold = 0.15   # umbral para considerar onset de sílaba

        # Contar transiciones bajo→sobre el umbral (onsets de sílaba)
        syllable_onsets = 0
        was_above = False
        for val in rms_norm:
            is_above = val > threshold
            if is_above and not was_above:
                syllable_onsets += 1
            was_above = is_above

        if syllable_onsets == 0:
            return None, 0.0

        # Convertir sílabas → palabras (≈2.5 sílabas por palabra en ESP/ING)
        estimated_words = syllable_onsets / 2.5
        words_per_second = round(estimated_words / total_voice_s, 2)

        # Calcular confianza basada en calidad de señal
        # SNR aproximado: ratio RMS_voz / RMS_ruido_de_fondo
        snr_estimate = float(np.mean(rms_norm[rms_norm > threshold]))
        confidence = min(snr_estimate * 1.5, 1.0)

        # Sanity check: velocidad esperada 1.5-4.5 palabras/seg para niños
        if not (0.5 <= words_per_second <= 6.0):
            confidence *= 0.4   # penalizar resultado fuera de rango

        logger.debug(
            f"Speech rate: {words_per_second} wps | "
            f"sílabas≈{syllable_onsets} | "
            f"duración_voz={total_voice_s:.1f}s | "
            f"confianza={confidence:.2f}"
        )

        return words_per_second, round(confidence, 3)

    except Exception as e:
        logger.error(f"Error calculando speech rate: {e}")
        return None, 0.0


# ══════════════════════════════════════════════════════════════════
# PASO 4 — Clasificar velocidad de lectura
# ══════════════════════════════════════════════════════════════════

def _classify_speech_rate(words_per_second: float) -> str:
    """
    Clasifica la velocidad de lectura según el método Kumon.

    Rangos calibrados para niños de 5-16 años:
      Rápida:  > 2.5 wps  (lectura fluida, nivel esperado o superior)
      Normal:  1.5-2.5 wps (ritmo adecuado)
      Lenta:   < 1.5 wps  (puede indicar dificultad de comprensión)

    El umbral inferior viene de config.settings.SPEECH_RATE_UMBRAL_BAJO (1.5).
    """
    from config.settings import settings

    umbral_lento = settings.SPEECH_RATE_UMBRAL_BAJO   # 1.5 por defecto

    if words_per_second >= 2.5:
        return "rapida"
    elif words_per_second >= umbral_lento:
        return "normal"
    else:
        return "lenta"


# ══════════════════════════════════════════════════════════════════
# PASO 5 — Evaluar fluidez global
# ══════════════════════════════════════════════════════════════════

def _evaluate_fluency(
    vad_segments: list[dict],
    silence_events: list[dict],
    audio_duration_ms: float,
) -> tuple[str, float]:
    """
    Evalúa la fluidez general de la lectura en voz alta.

    Criterios:
      fluida:      ratio de voz > 70% del tiempo de lectura
                   Y menos de 2 silencios prolongados
      con_pausas:  ratio de voz 40-70%
                   O 2-4 silencios prolongados
      no_fluida:   ratio de voz < 40%
                   O más de 4 silencios prolongados

    Returns:
        (etiqueta, confianza)
        confianza baja (<0.65) → no se agrega a auto_captured_flags
    """
    if not vad_segments or audio_duration_ms == 0:
        return "no_evaluada", 0.0

    total_voice_ms = sum(
        s["fin_ms"] - s["inicio_ms"] for s in vad_segments
    )
    voice_ratio    = total_voice_ms / audio_duration_ms
    num_silencios  = len(silence_events)

    if voice_ratio >= 0.70 and num_silencios < 2:
        etiqueta   = "fluida"
        confidence = 0.85
    elif voice_ratio >= 0.40 or num_silencios <= 4:
        etiqueta   = "con_pausas"
        confidence = 0.72
    else:
        etiqueta   = "no_fluida"
        confidence = 0.80

    # Penalizar confianza si el audio es muy corto
    if audio_duration_ms < 5000:
        confidence *= 0.6

    logger.debug(
        f"Fluidez: {etiqueta} | voice_ratio={voice_ratio:.2f} | "
        f"silencios={num_silencios} | conf={confidence:.2f}"
    )

    return etiqueta, round(confidence, 3)


# ══════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════

def _cleanup_wav(wav_path: str) -> None:
    """Elimina el archivo WAV temporal."""
    try:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
            logger.info(f"WAV temporal eliminado: {wav_path}")
    except Exception as e:
        logger.warning(f"No se pudo eliminar WAV temporal: {e}")
