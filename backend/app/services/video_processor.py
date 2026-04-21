from __future__ import annotations

"""
app/services/video_processor.py
══════════════════════════════════════════════════════════════════
Análisis del video de grabación de pantalla de la Galaxy Tab S6.

Este módulo consolida en una sola implementación operativa:
- búsqueda del frame final "Diagnostic Test"
- detección de cambios de página
- actividad de escritura
- pausas largas
- activación del borrador
- extracción de audio temporal

IMPORTANTE:
- Se preservan los nombres públicos consumidos por otros módulos:
  analyze_video, get_video_metadata, cleanup_video
- Se preserva VideoAnalysisResult con los campos esperados por:
  processing_service.py, qualitative_analyzer.py y audio_analyzer.py
- Se conservan wrappers de compatibilidad para no romper referencias
  antiguas dentro del proyecto.
══════════════════════════════════════════════════════════════════
"""

# ══════════════════════════════════════════════════════════════════
# BLOQUE 1 — IMPORTS
# ══════════════════════════════════════════════════════════════════

import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# BLOQUE 2 — CONSTANTES DE ANÁLISIS
# ══════════════════════════════════════════════════════════════════

# Muestreo
# 10fps efectivos (30fps ÷ 3): suficiente para capturar el flash
# rápido de transición de páginas en ClassNavi.
SAMPLE_EVERY_N_FRAMES = 3
SUMMARY_SAMPLE_FRAMES = 3
SUMMARY_TAIL_SECONDS = 18
FPS_DEFAULT = 30.0

# Detección de cambio de página
PAGE_CHANGE_BRIGHTNESS_DELTA = 30
PAGE_CHANGE_MIN_GAP_FRAMES = 90
FLASH_BRIGHTNESS_THRESHOLD = 232
PAGE_CHANGE_IGNORE_WINDOW_MS = 1200

# Detección de escritura
WRITING_DIFF_THRESHOLD = 12
WRITING_MIN_ACTIVE_PIXELS = 100
PAUSE_MIN_DURATION_MS = 8000

# ROI barra de herramientas (borrador)
TOOLBAR_ROI_X1_PCT = 0.83
TOOLBAR_ROI_Y1_PCT = 0.00
TOOLBAR_ROI_X2_PCT = 1.00
TOOLBAR_ROI_Y2_PCT = 0.11

# ROI resumen final
SUMMARY_ROI_X1_PCT = 0.08
SUMMARY_ROI_Y1_PCT = 0.28
SUMMARY_ROI_X2_PCT = 0.98
SUMMARY_ROI_Y2_PCT = 0.99

# ROI escritura
WRITING_ROI_X1_PCT = 0.05
WRITING_ROI_Y1_PCT = 0.12
WRITING_ROI_X2_PCT = 0.95
WRITING_ROI_Y2_PCT = 0.90

# Color naranja de la matriz "Diagnostic Test" en HSV
ORANGE_HSV_LOWER = np.array([5, 80, 80])
ORANGE_HSV_UPPER = np.array([32, 255, 255])
ORANGE_MIN_AREA_PCT = 0.025


# ══════════════════════════════════════════════════════════════════
# BLOQUE 3 — ESTRUCTURAS DE DATOS
# ══════════════════════════════════════════════════════════════════

@dataclass
class PageChange:
    frame_number: int
    timestamp_ms: float
    brightness_delta: float
    diff_ratio: float = 0.0
    change_type: str = "page_transition"

    def to_dict(self) -> dict:
        return {
            "frame": self.frame_number,
            "timestamp_ms": round(self.timestamp_ms, 1),
            "brightness_delta": round(self.brightness_delta, 2),
            "diff_ratio": round(self.diff_ratio, 4),
            "change_type": self.change_type,
        }


@dataclass
class PauseEvent:
    inicio_ms: float
    fin_ms: float
    duracion_ms: float
    seccion: str = "desconocida"

    def to_dict(self) -> dict:
        return {
            "inicio_ms": round(self.inicio_ms, 1),
            "fin_ms": round(self.fin_ms, 1),
            "duracion_ms": round(self.duracion_ms, 1),
            "seccion": self.seccion,
        }


@dataclass
class EraserEvent:
    frame_number: int
    timestamp_ms: float

    def to_dict(self) -> dict:
        return {
            "frame": self.frame_number,
            "timestamp_ms": round(self.timestamp_ms, 1),
        }


@dataclass
class VideoAnalysisResult:
    # Identidad
    subject: str = ""
    level: str = ""

    # Señales cualitativas
    time_per_section: dict = field(default_factory=dict)
    num_rewrites: int = 0
    pause_events: list = field(default_factory=list)
    activity_ratio: float = 0.0
    stroke_detail: dict = field(default_factory=dict)

    # Frame final listo para OCR
    summary_frame: Optional[np.ndarray] = None
    summary_frame_idx: int = -1

    # Metadatos
    total_frames: int = 0
    fps: float = FPS_DEFAULT
    duration_ms: float = 0.0
    page_changes: list = field(default_factory=list)
    processing_ms: int = 0

    # Audio temporal
    audio_temp_path: Optional[str] = None

    def to_qualitative_dict(self) -> dict:
        return {
            "time_per_section": self.time_per_section,
            "num_rewrites": self.num_rewrites,
            "pause_events": [
                {
                    "inicio_ms": p.get("inicio_ms"),
                    "duracion_ms": p.get("duracion_ms"),
                    "seccion": p.get("seccion"),
                }
                for p in self.pause_events
                if isinstance(p, dict)
            ],
            "activity_ratio": round(self.activity_ratio, 3),
            "stroke_detail": self.stroke_detail,
        }


# ══════════════════════════════════════════════════════════════════
# BLOQUE 4 — HELPERS BÁSICOS
# ══════════════════════════════════════════════════════════════════

def _safe_fps(raw_fps: float) -> float:
    try:
        fps = float(raw_fps)
    except (TypeError, ValueError):
        return FPS_DEFAULT

    if fps <= 0 or np.isnan(fps) or np.isinf(fps):
        return FPS_DEFAULT

    return fps


def _crop_roi_by_pct(
    frame: np.ndarray,
    x1_pct: float,
    y1_pct: float,
    x2_pct: float,
    y2_pct: float,
) -> np.ndarray:
    h, w = frame.shape[:2]

    x1 = max(0, min(w, int(w * x1_pct)))
    y1 = max(0, min(h, int(h * y1_pct)))
    x2 = max(0, min(w, int(w * x2_pct)))
    y2 = max(0, min(h, int(h * y2_pct)))

    if x2 <= x1 or y2 <= y1:
        return frame

    roi = frame[y1:y2, x1:x2]
    return roi if roi.size > 0 else frame


def _is_near_page_change(
    timestamp_ms: float,
    page_changes: list[dict],
    window_ms: int = PAGE_CHANGE_IGNORE_WINDOW_MS,
) -> bool:
    for change in page_changes:
        try:
            if abs(timestamp_ms - float(change["timestamp_ms"])) <= window_ms:
                return True
        except Exception:
            continue
    return False


def _tail_start_frame(total_frames: int, fps: float) -> int:
    if total_frames <= 0 or fps <= 0:
        return 0
    return max(0, total_frames - int(SUMMARY_TAIL_SECONDS * fps))


def _tail_start_ms(total_frames: int, fps: float) -> float:
    if fps <= 0:
        return 0.0
    return (_tail_start_frame(total_frames, fps) / fps) * 1000.0


def _ensure_section(section_strokes: dict, current_section_num: int) -> str:
    sec_name = f"seccion_{current_section_num}"
    if sec_name not in section_strokes:
        section_strokes[sec_name] = {"strokes": 0, "total_active_ms": 0.0}
    return sec_name


def _get_current_section(frame_idx: int, page_changes: list[dict], fps: float) -> str:
    if fps <= 0:
        return "seccion_1"

    timestamp_ms = (frame_idx / fps) * 1000.0
    section = 1

    for change in sorted(page_changes, key=lambda x: x.get("timestamp_ms", 0)):
        try:
            if float(change.get("timestamp_ms", 0.0)) <= timestamp_ms:
                section += 1
            else:
                break
        except Exception:
            continue

    return f"seccion_{section}"


# ══════════════════════════════════════════════════════════════════
# BLOQUE 5 — METADATOS Y UTILIDADES PÚBLICAS
# ══════════════════════════════════════════════════════════════════

def get_video_metadata(video_path: str) -> dict:
    video_file = Path(video_path)
    if not video_file.exists():
        return {
            "exists": False,
            "path": video_path,
            "size_bytes": 0,
            "fps": FPS_DEFAULT,
            "total_frames": 0,
            "duration_ms": 0.0,
        }

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        return {
            "exists": True,
            "path": video_path,
            "size_bytes": video_file.stat().st_size,
            "fps": FPS_DEFAULT,
            "total_frames": 0,
            "duration_ms": 0.0,
        }

    try:
        fps = _safe_fps(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_ms = ((total_frames / fps) * 1000) if fps > 0 and total_frames > 0 else 0.0
        return {
            "exists": True,
            "path": video_path,
            "filename": video_file.name,
            "size_bytes": video_file.stat().st_size,
            "fps": fps,
            "total_frames": total_frames,
            "duration_ms": round(duration_ms, 1),
        }
    finally:
        cap.release()


def cleanup_video(video_path: str) -> None:
    try:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
            logger.info(f"Video eliminado: {video_path}")
    except Exception as e:
        logger.warning(f"No se pudo eliminar el video {video_path}: {e}")


def extract_audio_track(video_path: str) -> Optional[str]:
    if not video_path or not os.path.exists(video_path):
        return None

    fd, wav_path = tempfile.mkstemp(prefix="kumon_audio_", suffix=".wav")
    os.close(fd)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        wav_path,
    ]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=120,
        )
        return wav_path if os.path.exists(wav_path) else None
    except Exception as e:
        logger.warning(f"No se pudo extraer audio con ffmpeg: {e}")
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass
        return None


# ══════════════════════════════════════════════════════════════════
# BLOQUE 6 — FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def analyze_video(video_path: str, subject: str, level: str = "") -> VideoAnalysisResult:
    t_start = time.time()
    result = VideoAnalysisResult()

    result.subject = (subject or "").strip().lower()
    result.level = (level or "").strip().upper()

    video_file = Path(video_path)
    if not video_file.exists():
        raise FileNotFoundError(f"No existe el archivo de video: {video_path}")

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video: {video_path}")

    try:
        raw_fps = cap.get(cv2.CAP_PROP_FPS)
        fps = _safe_fps(raw_fps)

        if fps == FPS_DEFAULT:
            try:
                import json as _json
                probe = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_streams",
                        str(video_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                info = _json.loads(probe.stdout or "{}")
                for stream in info.get("streams", []):
                    if stream.get("codec_type") == "video":
                        r = (stream.get("r_frame_rate") or "0/1").split("/")
                        if len(r) == 2 and int(r[1]) > 0:
                            fps = round(int(r[0]) / int(r[1]), 3)
                            break
            except Exception:
                pass

        result.fps = fps
        result.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if result.total_frames < 0:
            result.total_frames = 0

        result.duration_ms = (
            (result.total_frames / result.fps) * 1000.0
            if result.fps > 0 and result.total_frames > 0
            else 0.0
        )

        logger.info(
            f"Video: {result.total_frames} frames | "
            f"{result.fps:.2f}fps | {result.duration_ms / 1000:.1f}s"
        )

        t_step = time.time()
        result.summary_frame, result.summary_frame_idx = find_diagnostic_frame(
            cap,
            result.total_frames,
            result.fps,
        )
        logger.info(
            "Paso 1 completado | find_diagnostic_frame | %.2fs | frame_idx=%s",
            time.time() - t_step,
            result.summary_frame_idx,
        )

        t_step = time.time()
        _analyze_pages_writing_and_erasing(cap, result, result.subject)
        logger.info(
            "Paso 2-3 completado | _analyze_pages_writing_and_erasing | %.2fs | cambios=%s | pausas=%s | borrados=%s",
            time.time() - t_step,
            len(result.page_changes),
            len(result.pause_events),
            result.num_rewrites,
        )

        t_step = time.time()
        result.time_per_section = _calculate_time_per_section(
            result.page_changes,
            result.total_frames,
            result.fps,
        )
        _postprocess_analysis_results(result)
        logger.info(
            "Paso 4 completado | _calculate_time_per_section + postprocess | %.2fs | pausas_finales=%s | activity_ratio=%s",
            time.time() - t_step,
            len(result.pause_events),
            result.activity_ratio,
        )

        t_step = time.time()
        if result.subject in ("espanol", "ingles"):
            result.audio_temp_path = extract_audio_track(str(video_file))
        else:
            result.audio_temp_path = None
        logger.info(
            "Paso 5 completado | extract_audio_track | %.2fs | audio=%s",
            time.time() - t_step,
            bool(result.audio_temp_path),
        )

    finally:
        cap.release()

    result.processing_ms = int((time.time() - t_start) * 1000)
    logger.info(f"Análisis de video completado en {result.processing_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════
# BLOQUE 7 — FRAME FINAL "DIAGNOSTIC TEST"
# ══════════════════════════════════════════════════════════════════


def _calculate_orange_score(frame: np.ndarray) -> float:
    roi = _crop_roi_by_pct(
        frame,
        SUMMARY_ROI_X1_PCT,
        SUMMARY_ROI_Y1_PCT,
        SUMMARY_ROI_X2_PCT,
        SUMMARY_ROI_Y2_PCT,
    )
    if roi.size == 0:
        return 0.0


    h, w = roi.shape[:2]
    target_w = 320
    if w > target_w:
        scale = target_w / float(w)
        roi = cv2.resize(
            roi,
            (target_w, max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA,
        )


    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, ORANGE_HSV_LOWER, ORANGE_HSV_UPPER)
    orange_pixels = int(np.count_nonzero(mask))
    total_pixels = mask.size if mask.size > 0 else 1

    orange_ratio = orange_pixels / total_pixels

    # Refuerzo por saturación y brillo para no depender solo del rango HSV crudo.
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    vivid_mask = ((sat >= 70) & (val >= 80)).astype(np.uint8)
    vivid_ratio = int(np.count_nonzero(vivid_mask)) / (vivid_mask.size if vivid_mask.size > 0 else 1)

    return float(max(orange_ratio, min(vivid_ratio * 0.18, orange_ratio + 0.004)))



def _select_best_diagnostic_frame(
    candidates: list[tuple[int, np.ndarray, float]]
) -> tuple[Optional[np.ndarray], int]:
    if not candidates:
        return None, -1

    presorted = sorted(candidates, key=lambda x: (x[2], x[0]), reverse=True)
    top_ocr_candidates = presorted[: min(10, len(presorted))]

    try:
        from app.services.ocr_service import get_ocr_reader
        reader = get_ocr_reader()
        use_ocr = reader is not None
    except Exception:
        reader = None
        use_ocr = False
        logger.warning("OCR no disponible para selección de frame diagnóstico.")

    if not use_ocr:
        best_idx, best_frame, _ = presorted[0]
        return best_frame, best_idx

    scored = []

    for frame_idx, frame, orange_score in top_ocr_candidates:
        ocr_score = 0.0
        parsed_date = None
        keyword_hits = 0

        try:
            roi = _crop_roi_by_pct(
                frame,
                SUMMARY_ROI_X1_PCT,
                SUMMARY_ROI_Y1_PCT,
                SUMMARY_ROI_X2_PCT,
                SUMMARY_ROI_Y2_PCT,
            )
            if roi.size == 0:
                scored.append((frame_idx, frame, orange_score, 0.0, None))
                continue

            h, w = roi.shape[:2]
            target_w = 960
            if w > target_w:
                scale = target_w / float(w)
                roi = cv2.resize(
                    roi,
                    (target_w, max(1, int(h * scale))),
                    interpolation=cv2.INTER_AREA,
                )

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)

            ocr_variants = []

            # Variante 1: Otsu estándar
            _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            ocr_variants.append(bin_img)

            # Variante 2: Invertida
            ocr_variants.append(cv2.bitwise_not(bin_img))

            # Variante 3: contraste adaptativo
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_clahe = clahe.apply(gray)
            _, bin_img_clahe = cv2.threshold(
                gray_clahe,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            ocr_variants.append(bin_img_clahe)

            # Variante 4: texto oscuro sobre fondo claro con suavizado
            adaptive = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                11,
            )
            ocr_variants.append(adaptive)

            best_text = ""
            best_local_score = -1.0

            for variant in ocr_variants:
                try:
                    raw = reader.readtext(variant, detail=1, paragraph=False)
                    full_text = " ".join(t.lower() for (_, t, _) in raw)
                    normalized_local = re.sub(r"[^a-z0-9/\- ]", " ", full_text)
                    normalized_local = re.sub(r"\s+", " ", normalized_local).strip()

                    local_hits = 0
                    local_score = 0.0

                    if "diagnostic" in normalized_local:
                        local_score += 3.0
                        local_hits += 1
                    if "diagnostic test" in normalized_local:
                        local_score += 1.8
                        local_hits += 1
                    if "test" in normalized_local:
                        local_score += 0.8
                        local_hits += 1

                    expected_tokens = [
                        "study time",
                        "target time",
                        "test date",
                        "score",
                        "group",
                        "ws",
                    ]
                    for token in expected_tokens:
                        if token in normalized_local:
                            local_score += 0.7
                            local_hits += 1

                    # Tolerancia a OCR imperfecto
                    fuzzy_tokens = [
                        "diagnost",
                        "stud",
                        "target",
                        "date",
                        "group",
                        "time",
                    ]
                    for token in fuzzy_tokens:
                        if token in normalized_local:
                            local_score += 0.25

                    if local_hits >= 3:
                        local_score += 1.0

                    if local_score > best_local_score:
                        best_local_score = local_score
                        best_text = normalized_local

                except Exception:
                    continue

            normalized = best_text

            if "diagnostic" in normalized:
                ocr_score += 3.0
                keyword_hits += 1
            if "diagnostic test" in normalized:
                ocr_score += 1.8
                keyword_hits += 1
            if "test" in normalized:
                ocr_score += 0.8
                keyword_hits += 1

            expected_tokens = [
                "study time",
                "target time",
                "test date",
                "score",
                "group",
                "ws",
            ]
            for token in expected_tokens:
                if token in normalized:
                    ocr_score += 0.7
                    keyword_hits += 1

            # Tolerancia adicional a OCR parcial.
            fuzzy_tokens = [
                "diagnost",
                "stud",
                "target",
                "date",
                "group",
                "time",
            ]
            for token in fuzzy_tokens:
                if token in normalized:
                    ocr_score += 0.25

            if keyword_hits >= 3:
                ocr_score += 1.0

            date_match = re.search(r"(\d{2})[/-](\d{2})[/-](\d{2,4})", normalized)
            if date_match:
                try:
                    g1, g2, g3 = date_match.groups()
                    if len(g3) == 4:
                        parsed_date = datetime(int(g3), int(g2), int(g1))
                    else:
                        parsed_date = datetime(2000 + int(g3), int(g2), int(g1))
                    ocr_score += 0.6
                except ValueError:
                    parsed_date = None

            strong_confirm = (
                ("diagnostic" in normalized and "test" in normalized)
                or ("diagnost" in normalized and keyword_hits >= 2)
                or (keyword_hits >= 3 and ocr_score >= 4.0)
                or (ocr_score >= 5.2)
            )
            if strong_confirm:
                logger.debug(
                    "Frame diagnóstico confirmado temprano | frame=%s | orange=%.4f | ocr=%.2f",
                    frame_idx,
                    orange_score,
                    ocr_score,
                )
                return frame, frame_idx

            scored.append((frame_idx, frame, orange_score, ocr_score, parsed_date))

        except Exception as e:
            logger.debug(f"OCR falló en frame candidato {frame_idx}: {e}")
            scored.append((frame_idx, frame, orange_score, 0.0, None))

    if not scored:
        best_idx, best_frame, _ = presorted[0]
        return best_frame, best_idx

    confirmed = [s for s in scored if s[3] >= 1.6]
    pool = confirmed if confirmed else scored
    pool.sort(
        key=lambda s: (
            s[3],
            s[4] if s[4] else datetime.min,
            s[2],
            s[0],
        ),
        reverse=True,
    )
    best = pool[0]
    return best[1], best[0]

def find_diagnostic_frame(
    cap: cv2.VideoCapture,
    total_frames: int,
    fps: float,
) -> tuple[Optional[np.ndarray], int]:
    if total_frames <= 0 or fps <= 0:
        logger.warning("Metadatos insuficientes para buscar frame diagnóstico.")
        return None, -1


    # Ventana real un poco más amplia para no perder videos donde
    # la pantalla final aparece tarde o queda visible menos tiempo.
    effective_tail_seconds = max(SUMMARY_TAIL_SECONDS, 28)
    tail_frames = int(effective_tail_seconds * fps)
    start_frame = max(0, total_frames - tail_frames)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)


    scored_frames: list[tuple[int, np.ndarray, float]] = []
    raw_candidates: list[tuple[int, np.ndarray, float]] = []


    frame_idx = start_frame
    sampled_count = 0


    while True:
        ret, frame = cap.read()
        if not ret:
            break


        if (frame_idx - start_frame) % SUMMARY_SAMPLE_FRAMES == 0:
            sampled_count += 1
            orange_score = _calculate_orange_score(frame)
            scored_frames.append((frame_idx, frame.copy(), orange_score))


            if orange_score >= ORANGE_MIN_AREA_PCT:
                raw_candidates.append((frame_idx, frame.copy(), orange_score))


        frame_idx += 1


    if not scored_frames:
        logger.warning("No se pudieron muestrear frames en la cola del video.")
        return None, -1


    stable_candidates: list[tuple[int, np.ndarray, float]] = []
    if raw_candidates:
        max_gap_frames = max(1, SUMMARY_SAMPLE_FRAMES * 3)
        cluster = [raw_candidates[0]]


        for candidate in raw_candidates[1:]:
            prev_idx = cluster[-1][0]
            cur_idx = candidate[0]


            if cur_idx - prev_idx <= max_gap_frames:
                cluster.append(candidate)
            else:
                if len(cluster) >= 2:
                    best_in_cluster = max(cluster, key=lambda x: (x[2], x[0]))
                    stable_candidates.append(best_in_cluster)
                elif len(cluster) == 1 and cluster[0][2] >= max(0.018, ORANGE_MIN_AREA_PCT * 0.72):
                    stable_candidates.append(cluster[0])
                cluster = [candidate]


        if cluster and len(cluster) >= 2:
            best_in_cluster = max(cluster, key=lambda x: (x[2], x[0]))
            stable_candidates.append(best_in_cluster)
        elif cluster and len(cluster) == 1 and cluster[0][2] >= max(0.018, ORANGE_MIN_AREA_PCT * 0.72):
            stable_candidates.append(cluster[0])


    candidates = stable_candidates


    if not candidates:
        top_scored = sorted(scored_frames, key=lambda x: (x[2], x[0]), reverse=True)[:12]
        recent_cutoff = start_frame + int(tail_frames * 0.25)
        fallback_min_score = max(0.008, ORANGE_MIN_AREA_PCT * 0.32)
        candidates = [
            c for c in top_scored
            if c[2] >= fallback_min_score and c[0] >= recent_cutoff
        ]


        if candidates:
            logger.warning(
                "No hubo candidatos estables; usando fallback controlado | sampled=%s | best=%.4f | min=%.4f | recent_cutoff=%s",
                sampled_count,
                top_scored[0][2] if top_scored else 0.0,
                fallback_min_score,
                recent_cutoff,
            )
        else:
            # Último rescate: tomar los mejores frames del tramo más final,
            # incluso con naranja débil, para que OCR tenga oportunidad real.
            tail_focus_cutoff = start_frame + int(tail_frames * 0.70)
            tail_focus = [
                c for c in scored_frames
                if c[0] >= tail_focus_cutoff
            ]
            tail_focus = sorted(tail_focus, key=lambda x: (x[2], x[0]), reverse=True)[:6]

            if tail_focus:
                candidates = tail_focus
                logger.warning(
                    "Sin candidatos estables ni fallback principal; usando rescate del tramo final | sampled=%s | candidatos=%s | best=%.4f",
                    sampled_count,
                    len(candidates),
                    candidates[0][2] if candidates else 0.0,
                )
            else:
                best_score = max((x[2] for x in scored_frames), default=0.0)
                logger.warning(
                    "No se encontró la matriz Diagnostic Test en el video | sampled=%s | mejor_orange=%.4f",
                    sampled_count,
                    best_score,
                )
                return None, -1


    logger.info(
        "Frames muestreados=%s | candidatos_brutos=%s | candidatos_finales=%s",
        sampled_count,
        len(raw_candidates),
        len(candidates),
    )


    best_frame, best_idx = _select_best_diagnostic_frame(candidates)
    if best_frame is None or best_idx < 0:
        best_fallback = max(candidates, key=lambda x: (x[2], x[0]))
        logger.warning(
            "Selección OCR no concluyente; usando mejor candidato final por score naranja."
        )
        return best_fallback[1], best_fallback[0]


    logger.info("Frame de resumen seleccionado: %s", best_idx)
    return best_frame, best_idx

# ══════════════════════════════════════════════════════════════════
# BLOQUE 8 — ANÁLISIS VISUAL UNIFICADO
# ══════════════════════════════════════════════════════════════════


def _analyze_pages_writing_and_erasing(
    cap: cv2.VideoCapture,
    result: VideoAnalysisResult,
    subject: str,
) -> None:
    _ = subject

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    fps = result.fps
    total_frames = result.total_frames

    result.page_changes = []
    result.pause_events = []
    result.stroke_detail = {}
    result.activity_ratio = 0.0
    result.num_rewrites = 0

    if total_frames <= 0 or fps <= 0:
        logger.warning("Metadatos insuficientes para análisis visual.")
        return

    tail_start = _tail_start_frame(total_frames, fps)
    frame_duration_ms = (SAMPLE_EVERY_N_FRAMES / fps) * 1000.0
    effective_min_gap_frames = max(PAGE_CHANGE_MIN_GAP_FRAMES, int(fps * 1.5))

    page_diff_threshold = max(6, WRITING_DIFF_THRESHOLD - 4)
    page_change_confirm_frames = 3
    page_change_min_persist_ratio = 0.014
    page_change_strong_diff_ratio = 0.026
    page_change_medium_diff_ratio = 0.014
    page_change_brightness_ratio = 0.010
    page_change_flash_diff_ratio = 0.010
    page_change_min_mean_motion = 0.0045
    page_change_strong_delta = max(8.0, PAGE_CHANGE_BRIGHTNESS_DELTA * 0.28)
    page_change_candidate_window_frames = max(SAMPLE_EVERY_N_FRAMES * 4, int(fps * 0.9))

    pause_open_streak = max(12, int(round(1500.0 / max(frame_duration_ms, 1.0))))
    pause_close_active_streak = max(3, int(round(300.0 / max(frame_duration_ms, 1.0))))

    # ── Subbloque 8.1 — calibración adaptiva ──────────────────────
    temp_prev_writing = None
    temp_prev_page = None
    temp_prev_page_brightness = 0.0

    writing_motion_history: list[float] = []
    writing_pixels_history: list[int] = []
    page_motion_history: list[float] = []
    page_diff_ratio_history: list[float] = []
    page_delta_history: list[float] = []

    calib_idx = 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    while calib_idx < tail_start:
        ret, frame = cap.read()
        if not ret:
            break

        if calib_idx % SAMPLE_EVERY_N_FRAMES != 0:
            calib_idx += 1
            continue

        writing_roi = _crop_roi_by_pct(
            frame,
            WRITING_ROI_X1_PCT,
            WRITING_ROI_Y1_PCT,
            WRITING_ROI_X2_PCT,
            WRITING_ROI_Y2_PCT,
        )
        page_roi = _crop_roi_by_pct(frame, 0.03, 0.08, 0.97, 0.92)

        writing_gray = cv2.cvtColor(writing_roi, cv2.COLOR_BGR2GRAY)
        writing_gray = cv2.GaussianBlur(writing_gray, (5, 5), 0)

        page_gray = cv2.cvtColor(page_roi, cv2.COLOR_BGR2GRAY)
        page_gray = cv2.GaussianBlur(page_gray, (5, 5), 0)
        page_gray = cv2.resize(
            page_gray,
            None,
            fx=0.35,
            fy=0.35,
            interpolation=cv2.INTER_AREA,
        )

        page_brightness = float(np.mean(page_gray))

        if temp_prev_writing is not None:
            wdiff = cv2.absdiff(writing_gray, temp_prev_writing)
            writing_motion_history.append(float(np.mean(wdiff)) / 255.0)
            writing_pixels_history.append(
                int(np.count_nonzero(wdiff > WRITING_DIFF_THRESHOLD))
            )

        if temp_prev_page is not None:
            pdiff = cv2.absdiff(page_gray, temp_prev_page)
            page_motion_history.append(float(np.mean(pdiff)) / 255.0)
            page_diff_ratio_history.append(
                int(np.count_nonzero(pdiff > page_diff_threshold)) / (pdiff.size or 1)
            )
            page_delta_history.append(abs(page_brightness - temp_prev_page_brightness))

        temp_prev_writing = writing_gray
        temp_prev_page = page_gray
        temp_prev_page_brightness = page_brightness
        calib_idx += 1

    if writing_motion_history:
        q25 = float(np.percentile(writing_motion_history, 25))
        q50 = float(np.percentile(writing_motion_history, 50))
        low_motion = max(0.011, q25 * 1.10)
        high_motion = max(low_motion * 1.45, q50 * 0.90, 0.020)
    else:
        low_motion = 0.014
        high_motion = 0.026

    if writing_pixels_history:
        pixels_q50 = int(np.percentile(writing_pixels_history, 50))
        pixels_q75 = int(np.percentile(writing_pixels_history, 75))
        adaptive_floor = max(24, min(WRITING_MIN_ACTIVE_PIXELS, int(pixels_q50 * 0.85)))
        adaptive_ceiling = max(adaptive_floor + 8, WRITING_MIN_ACTIVE_PIXELS * 2)
        adaptive_pixels = int(pixels_q75 * 1.10)
        active_pixels_threshold = int(
            max(
                adaptive_floor,
                min(adaptive_pixels, adaptive_ceiling),
            )
        )
    else:
        active_pixels_threshold = WRITING_MIN_ACTIVE_PIXELS

    if page_diff_ratio_history:
        page_q90 = float(np.percentile(page_diff_ratio_history, 90))
        page_q95 = float(np.percentile(page_diff_ratio_history, 95))
    else:
        page_q90 = 0.012
        page_q95 = 0.016

    if page_motion_history:
        page_motion_q90 = float(np.percentile(page_motion_history, 90))
    else:
        page_motion_q90 = 0.0050

    if page_delta_history:
        page_delta_q95 = float(np.percentile(page_delta_history, 95))
    else:
        page_delta_q95 = 7.5

    page_change_min_persist_ratio = max(0.012, min(page_q90 * 1.20, 0.022))
    page_change_medium_diff_ratio = max(0.014, min(page_q95 * 1.15, 0.026))
    page_change_strong_diff_ratio = max(page_change_medium_diff_ratio * 1.60, 0.030)
    page_change_brightness_ratio = max(0.009, min(page_q90 * 1.00, 0.018))
    page_change_flash_diff_ratio = max(0.009, min(page_q90 * 0.95, 0.016))
    page_change_min_mean_motion = max(0.0045, min(page_motion_q90 * 1.20, 0.0090))
    page_change_strong_delta = max(6.5, min(page_delta_q95 * 1.10, 12.5))
    page_change_candidate_window_frames = max(
        SAMPLE_EVERY_N_FRAMES * 6,
        int(fps * 1.10),
    )

    writing_like_motion_threshold = max(high_motion * 0.82, low_motion * 1.35, 0.018)
    writing_like_diff_ratio = 0.018

    # ── Subbloque 8.2 — pasada real ───────────────────────────────
    prev_writing_gray: Optional[np.ndarray] = None
    prev_page_gray: Optional[np.ndarray] = None
    prev_page_brightness = 0.0
    prev_eraser_state = False

    active_frames = 0
    total_analyzed = 0

    pause_open = False
    pause_start_ms = 0.0
    pause_section = "seccion_1"

    quiet_streak = 0
    active_streak = 0

    section_strokes = {"seccion_1": {"strokes": 0, "total_active_ms": 0.0}}
    current_section_num = 1
    prev_was_active: dict[str, bool] = {}

    pre_change_page_gray: Optional[np.ndarray] = None
    confirm_countdown = 0

    candidate_change: Optional[dict] = None
    candidate_streak = 0

    post_change_ignore_window_ms = float(min(PAGE_CHANGE_IGNORE_WINDOW_MS, 650))
    post_change_ignore_until_ms = -1.0

    # ── Subbloque 8.2.A — validación de evidencia de sección ──────
    startup_ignore_ms = max(8000.0, frame_duration_ms * 20)
    first_page_min_elapsed_ms = max(25000.0, frame_duration_ms * 90)
    min_section_elapsed_ms = max(18000.0, frame_duration_ms * 60)
    min_section_elapsed_ms_relaxed = max(14000.0, frame_duration_ms * 48)
    min_section_active_ms = max(1000.0, frame_duration_ms * 7)
    min_section_active_ms_strong = max(2200.0, frame_duration_ms * 14)
    min_section_strokes = 3
    min_section_strokes_soft = 2

    def _get_last_change_timestamp_ms() -> float:
        if not result.page_changes:
            return 0.0
        try:
            return float(result.page_changes[-1].get("timestamp_ms", 0.0))
        except Exception:
            return 0.0

    def _get_current_section_metrics(event_ts_ms: float) -> tuple[str, int, float, float]:
        current_section_name = f"seccion_{current_section_num}"
        current_section_data = section_strokes.get(
            current_section_name,
            {"strokes": 0, "total_active_ms": 0.0},
        )
        current_section_strokes = int(current_section_data.get("strokes", 0))
        current_section_active_ms = float(current_section_data.get("total_active_ms", 0.0))
        last_change_ts_ms = _get_last_change_timestamp_ms()
        section_elapsed_ms = max(0.0, event_ts_ms - last_change_ts_ms)
        return (
            current_section_name,
            current_section_strokes,
            current_section_active_ms,
            section_elapsed_ms,
        )

    def _section_has_enough_evidence(
        event_ts_ms: float,
        peak_diff_ratio: float,
        peak_delta: float,
        peak_mean_motion: float,
        peak_is_flash: bool,
    ) -> bool:
        (
            current_section_name,
            current_section_strokes,
            current_section_active_ms,
            section_elapsed_ms,
        ) = _get_current_section_metrics(event_ts_ms)

        _ = current_section_name

        if event_ts_ms < startup_ignore_ms:
            return False

        very_strong_candidate = (
            peak_is_flash
            or (
                peak_diff_ratio >= max(page_change_strong_diff_ratio * 1.45, 0.042)
                and (
                    peak_delta >= max(page_change_strong_delta * 1.05, 8.5)
                    or peak_mean_motion >= (page_change_min_mean_motion * 2.10)
                )
            )
        )

        enough_work_evidence = (
            current_section_strokes >= min_section_strokes
            or current_section_active_ms >= min_section_active_ms_strong
            or (
                current_section_strokes >= min_section_strokes_soft
                and current_section_active_ms >= min_section_active_ms
            )
        )

        soft_accept = (
            section_elapsed_ms >= min_section_elapsed_ms
            and current_section_active_ms >= min_section_active_ms
            and current_section_strokes >= min_section_strokes_soft
        )

        relaxed_accept = (
            section_elapsed_ms >= min_section_elapsed_ms_relaxed
            and current_section_active_ms >= min_section_active_ms_strong
        )

        if not result.page_changes:
            first_page_accept = (
                section_elapsed_ms >= first_page_min_elapsed_ms
                and (
                    enough_work_evidence
                    or relaxed_accept
                    or (
                        very_strong_candidate
                        and current_section_active_ms >= min_section_active_ms
                    )
                )
            )
            return first_page_accept

        if very_strong_candidate and section_elapsed_ms >= min_section_elapsed_ms_relaxed:
            return True

        if enough_work_evidence and section_elapsed_ms >= min_section_elapsed_ms_relaxed:
            return True

        if soft_accept or relaxed_accept:
            return True

        return False

    def close_open_pause(close_ts_ms: float) -> None:
        nonlocal pause_open, pause_start_ms, pause_section
        if not pause_open:
            return

        duration = close_ts_ms - pause_start_ms
        if duration >= PAUSE_MIN_DURATION_MS:
            result.pause_events.append(
                PauseEvent(
                    inicio_ms=pause_start_ms,
                    fin_ms=close_ts_ms,
                    duracion_ms=duration,
                    seccion=pause_section,
                ).to_dict()
            )

        pause_open = False
        pause_start_ms = 0.0

    def rollback_last_page_change() -> None:
        nonlocal current_section_num
        nonlocal pre_change_page_gray
        nonlocal confirm_countdown
        nonlocal quiet_streak
        nonlocal active_streak
        nonlocal post_change_ignore_until_ms

        if result.page_changes:
            result.page_changes.pop()

        if current_section_num > 1:
            sec_name = f"seccion_{current_section_num}"
            sec_data = section_strokes.get(sec_name)
            if (
                sec_data is not None
                and sec_data.get("strokes", 0) == 0
                and sec_data.get("total_active_ms", 0.0) == 0.0
            ):
                section_strokes.pop(sec_name, None)
                prev_was_active.pop(sec_name, None)
            current_section_num = max(1, current_section_num - 1)

        if result.page_changes:
            last_ts = float(result.page_changes[-1].get("timestamp_ms", -1.0))
            post_change_ignore_until_ms = last_ts + post_change_ignore_window_ms
        else:
            post_change_ignore_until_ms = -1.0

        pre_change_page_gray = None
        confirm_countdown = 0
        quiet_streak = 0
        active_streak = 0

    def finalize_candidate() -> None:
        nonlocal candidate_change
        nonlocal candidate_streak
        nonlocal current_section_num
        nonlocal quiet_streak
        nonlocal active_streak
        nonlocal pre_change_page_gray
        nonlocal confirm_countdown
        nonlocal post_change_ignore_until_ms

        if candidate_change is None:
            return

        peak_diff_ratio = float(candidate_change["peak_diff_ratio"])
        peak_delta = float(candidate_change["peak_delta"])
        peak_mean_motion = float(candidate_change["peak_mean_motion"])
        peak_is_flash = bool(candidate_change.get("peak_is_flash", False))
        samples = int(candidate_change.get("samples", 0))
        writing_votes = int(candidate_change.get("writing_votes", 0))

        candidate_is_writing_dominant = (
            not peak_is_flash
            and samples > 0
            and (writing_votes * 10) >= (samples * 6)
            and peak_diff_ratio < max(page_change_strong_diff_ratio * 1.18, 0.032)
            and peak_delta < max(page_change_strong_delta * 1.10, 9.0)
        )

        sustained_change = (
            candidate_streak >= 2
            and (
                (
                    peak_diff_ratio >= page_change_medium_diff_ratio
                    and peak_mean_motion >= page_change_min_mean_motion
                )
                or (
                    peak_delta >= (page_change_strong_delta * 0.80)
                    and peak_diff_ratio >= page_change_brightness_ratio
                )
            )
        )

        strong_single_spike = (
            peak_is_flash
            or (
                peak_diff_ratio >= max(page_change_strong_diff_ratio * 1.08, 0.030)
                and (
                    peak_delta >= max(page_change_strong_delta * 0.70, 6.5)
                    or peak_mean_motion >= (page_change_min_mean_motion * 1.35)
                )
            )
        )

        if (sustained_change or strong_single_spike) and not candidate_is_writing_dominant:
            event_frame = int(candidate_change["peak_frame"])
            event_ts_ms = round((event_frame / fps) * 1000.0, 1)

            last_change_frame = -effective_min_gap_frames
            if result.page_changes:
                last_change_frame = int(
                    result.page_changes[-1].get(
                        "frame",
                        result.page_changes[-1].get("frame_number", -effective_min_gap_frames),
                    )
                )

            section_has_evidence = _section_has_enough_evidence(
                event_ts_ms,
                peak_diff_ratio,
                peak_delta,
                peak_mean_motion,
                peak_is_flash,
            )

            if (
                section_has_evidence
                and (
                    not result.page_changes
                    or (event_frame - last_change_frame) >= effective_min_gap_frames
                )
            ):
                result.page_changes.append(
                    PageChange(
                        frame_number=event_frame,
                        timestamp_ms=event_ts_ms,
                        brightness_delta=peak_delta,
                        diff_ratio=peak_diff_ratio,
                        change_type="page_transition",
                    ).to_dict()
                )

                pre_gray = candidate_change.get("pre_gray")
                pre_change_page_gray = (
                    pre_gray.copy() if isinstance(pre_gray, np.ndarray) else None
                )
                confirm_countdown = page_change_confirm_frames
                current_section_num += 1
                _ensure_section(section_strokes, current_section_num)
                quiet_streak = 0
                active_streak = 0
                post_change_ignore_until_ms = event_ts_ms + post_change_ignore_window_ms
                close_open_pause(event_ts_ms)

        candidate_change = None
        candidate_streak = 0

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    frame_idx = 0

    while frame_idx < tail_start:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % SAMPLE_EVERY_N_FRAMES != 0:
            frame_idx += 1
            continue

        timestamp_ms = (frame_idx / fps) * 1000.0

        writing_roi = _crop_roi_by_pct(
            frame,
            WRITING_ROI_X1_PCT,
            WRITING_ROI_Y1_PCT,
            WRITING_ROI_X2_PCT,
            WRITING_ROI_Y2_PCT,
        )
        page_roi = _crop_roi_by_pct(frame, 0.03, 0.08, 0.97, 0.92)

        writing_gray = cv2.cvtColor(writing_roi, cv2.COLOR_BGR2GRAY)
        writing_gray = cv2.GaussianBlur(writing_gray, (5, 5), 0)

        page_gray = cv2.cvtColor(page_roi, cv2.COLOR_BGR2GRAY)
        page_gray = cv2.GaussianBlur(page_gray, (5, 5), 0)
        page_gray = cv2.resize(
            page_gray,
            None,
            fx=0.35,
            fy=0.35,
            interpolation=cv2.INTER_AREA,
        )

        page_brightness = float(np.mean(page_gray))
        current_section = _ensure_section(section_strokes, current_section_num)

        if prev_writing_gray is not None and prev_page_gray is not None:
            writing_diff = cv2.absdiff(writing_gray, prev_writing_gray)
            changed_pixels = int(np.count_nonzero(writing_diff > WRITING_DIFF_THRESHOLD))
            writing_total_pixels = writing_diff.size if writing_diff.size > 0 else 1
            writing_diff_ratio = changed_pixels / writing_total_pixels
            writing_mean_motion = float(np.mean(writing_diff)) / 255.0

            page_diff = cv2.absdiff(page_gray, prev_page_gray)
            page_changed_pixels = int(np.count_nonzero(page_diff > page_diff_threshold))
            page_total_pixels = page_diff.size if page_diff.size > 0 else 1
            page_diff_ratio = page_changed_pixels / page_total_pixels
            page_mean_motion = float(np.mean(page_diff)) / 255.0
            page_delta = abs(page_brightness - prev_page_brightness)

            if confirm_countdown > 0:
                confirm_countdown -= 1

                if pre_change_page_gray is not None:
                    diff_vs_pre = cv2.absdiff(page_gray, pre_change_page_gray)
                    persist_ratio = (
                        int(np.count_nonzero(diff_vs_pre > page_diff_threshold))
                        / (diff_vs_pre.size or 1)
                    )
                    persist_mean_motion = float(np.mean(diff_vs_pre)) / 255.0

                    if (
                        persist_ratio >= page_change_min_persist_ratio
                        or persist_mean_motion >= page_change_min_mean_motion
                    ):
                        confirm_countdown = 0
                        pre_change_page_gray = None
                    elif confirm_countdown == 0:
                        rollback_last_page_change()

            is_flash = (
                page_brightness >= FLASH_BRIGHTNESS_THRESHOLD
                and page_delta >= max(8.0, page_change_strong_delta * 0.85)
                and page_diff_ratio >= page_change_flash_diff_ratio
            )

            strong_structural_change = page_diff_ratio >= page_change_strong_diff_ratio
            medium_structural_change = (
                page_diff_ratio >= page_change_medium_diff_ratio
                and (
                    page_mean_motion >= page_change_min_mean_motion
                    or page_delta >= (page_change_strong_delta * 0.75)
                )
            )
            brightness_change = (
                page_delta >= page_change_strong_delta
                and (
                    page_diff_ratio >= page_change_brightness_ratio
                    or page_mean_motion >= page_change_min_mean_motion
                )
            )

            looks_like_writing = (
                writing_mean_motion >= writing_like_motion_threshold
                and (
                    writing_diff_ratio >= writing_like_diff_ratio
                    or changed_pixels >= int(active_pixels_threshold * 0.70)
                )
            )

            looks_like_small_noise = (
                page_diff_ratio < max(page_change_medium_diff_ratio * 0.45, 0.006)
                and page_mean_motion < max(page_change_min_mean_motion * 0.65, 0.003)
                and page_delta < max(page_change_strong_delta * 0.45, 4.0)
            )

            suppress_by_writing = (
                looks_like_writing
                and not is_flash
                and page_diff_ratio < max(page_change_strong_diff_ratio * 1.25, 0.036)
                and page_delta < max(page_change_strong_delta * 1.15, 9.5)
            )

            is_candidate = (
                (strong_structural_change or medium_structural_change or brightness_change or is_flash)
                and not looks_like_small_noise
                and not suppress_by_writing
            )

            if is_candidate:
                if (
                    candidate_change is None
                    or (frame_idx - int(candidate_change["last_frame"])) > page_change_candidate_window_frames
                ):
                    finalize_candidate()
                    candidate_change = {
                        "frame": frame_idx,
                        "last_frame": frame_idx,
                        "peak_frame": frame_idx,
                        "peak_diff_ratio": page_diff_ratio,
                        "peak_delta": page_delta,
                        "peak_mean_motion": page_mean_motion,
                        "peak_is_flash": is_flash,
                        "pre_gray": prev_page_gray.copy(),
                        "samples": 1,
                        "writing_votes": 1 if looks_like_writing else 0,
                    }
                    candidate_streak = 1
                else:
                    candidate_streak += 1
                    candidate_change["last_frame"] = frame_idx
                    candidate_change["samples"] = int(candidate_change.get("samples", 0)) + 1
                    if looks_like_writing:
                        candidate_change["writing_votes"] = int(
                            candidate_change.get("writing_votes", 0)
                        ) + 1

                    current_score = (
                        (page_diff_ratio * 1.5)
                        + page_mean_motion
                        + (page_delta / 255.0)
                        + (0.030 if is_flash else 0.0)
                    )
                    saved_score = (
                        (float(candidate_change["peak_diff_ratio"]) * 1.5)
                        + float(candidate_change["peak_mean_motion"])
                        + (float(candidate_change["peak_delta"]) / 255.0)
                        + (0.030 if bool(candidate_change.get("peak_is_flash", False)) else 0.0)
                    )

                    if current_score > saved_score:
                        candidate_change["peak_frame"] = frame_idx
                        candidate_change["peak_diff_ratio"] = page_diff_ratio
                        candidate_change["peak_delta"] = page_delta
                        candidate_change["peak_mean_motion"] = page_mean_motion
                        candidate_change["peak_is_flash"] = is_flash
                    else:
                        candidate_change["peak_diff_ratio"] = max(
                            float(candidate_change["peak_diff_ratio"]),
                            page_diff_ratio,
                        )
                        candidate_change["peak_delta"] = max(
                            float(candidate_change["peak_delta"]),
                            page_delta,
                        )
                        candidate_change["peak_mean_motion"] = max(
                            float(candidate_change["peak_mean_motion"]),
                            page_mean_motion,
                        )
                        candidate_change["peak_is_flash"] = bool(
                            candidate_change.get("peak_is_flash", False)
                        ) or is_flash
            else:
                finalize_candidate()

            current_section = _ensure_section(section_strokes, current_section_num)
            in_post_change_ignore = (
                post_change_ignore_until_ms >= 0.0
                and timestamp_ms <= post_change_ignore_until_ms
            )

            if in_post_change_ignore:
                quiet_streak = 0
                active_streak = 0
                prev_was_active[current_section] = False
            else:
                is_quiet = (
                    writing_mean_motion <= low_motion
                    and changed_pixels < int(active_pixels_threshold * 0.45)
                )
                is_active = (
                    writing_mean_motion >= high_motion
                    or changed_pixels >= active_pixels_threshold
                )

                total_analyzed += 1

                if is_active:
                    active_frames += 1
                    section_strokes[current_section]["total_active_ms"] += frame_duration_ms

                    if not prev_was_active.get(current_section, False):
                        section_strokes[current_section]["strokes"] += 1

                    active_streak += 1
                    quiet_streak = 0
                    prev_was_active[current_section] = True

                elif is_quiet:
                    quiet_streak += 1
                    active_streak = 0
                    prev_was_active[current_section] = False

                else:
                    quiet_streak = 0
                    active_streak = 0
                    prev_was_active[current_section] = False

                if not pause_open and quiet_streak >= pause_open_streak:
                    pause_open = True
                    pause_start_ms = timestamp_ms
                    pause_section = current_section

                if pause_open and active_streak >= pause_close_active_streak:
                    close_open_pause(timestamp_ms)

        eraser_active = _is_eraser_active(frame)
        if eraser_active and not prev_eraser_state:
            result.num_rewrites += 1

        prev_eraser_state = eraser_active
        prev_writing_gray = writing_gray
        prev_page_gray = page_gray
        prev_page_brightness = page_brightness

        frame_idx += 1

    finalize_candidate()

    if pause_open:
        end_ms = (tail_start / fps) * 1000.0
        close_open_pause(end_ms)

    result.activity_ratio = (
        round(active_frames / total_analyzed, 3)
        if total_analyzed > 0
        else 0.0
    )

    tail_start_ms = (tail_start / fps) * 1000.0

    valid_timestamps: list[float] = []
    for change in result.page_changes:
        ts = change.get("timestamp_ms")
        if ts is None:
            continue
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            continue
        if 0.0 < ts < tail_start_ms:
            valid_timestamps.append(ts)

    valid_timestamps.sort()

    normalized_timestamps: list[float] = []
    min_gap_ms = max(
        frame_duration_ms,
        (PAGE_CHANGE_MIN_GAP_FRAMES / fps) * 1000.0,
    )
    min_section_ms = max(16000.0, min_gap_ms)
    min_terminal_section_ms = max(16000.0, min_gap_ms)

    for ts in valid_timestamps:
        remaining_ms = tail_start_ms - ts
        if remaining_ms < min_terminal_section_ms:
            continue

        if not normalized_timestamps:
            if ts >= min_section_ms:
                normalized_timestamps.append(ts)
            continue

        if ts - normalized_timestamps[-1] < min_gap_ms:
            continue

        if ts - normalized_timestamps[-1] < min_section_ms:
            continue

        normalized_timestamps.append(ts)

    merged_section_strokes: dict[str, dict[str, float | int]] = {}
    normalized_section_num = 1
    normalized_boundary_index = 0

    def _section_sort_key(name: str) -> int:
        try:
            return int(str(name).split("_")[-1])
        except Exception:
            return 10**9

    raw_section_names = sorted(section_strokes.keys(), key=_section_sort_key)

    for raw_idx, sec_name in enumerate(raw_section_names, start=1):
        raw_data = section_strokes.get(
            sec_name,
            {"strokes": 0, "total_active_ms": 0.0},
        )

        target_section = _ensure_section(merged_section_strokes, normalized_section_num)
        merged_section_strokes[target_section]["strokes"] += int(raw_data.get("strokes", 0))
        merged_section_strokes[target_section]["total_active_ms"] += float(
            raw_data.get("total_active_ms", 0.0)
        )

        raw_section_end_ts = tail_start_ms
        if raw_idx - 1 < len(valid_timestamps):
            raw_section_end_ts = float(valid_timestamps[raw_idx - 1])

        if normalized_boundary_index < len(normalized_timestamps):
            current_boundary_ts = float(normalized_timestamps[normalized_boundary_index])
            if abs(raw_section_end_ts - current_boundary_ts) <= 1.0:
                normalized_section_num += 1
                normalized_boundary_index += 1

    result.stroke_detail = {}
    for sec_name in sorted(merged_section_strokes.keys(), key=_section_sort_key):
        data = merged_section_strokes[sec_name]
        strokes = int(data.get("strokes", 0))
        total_ms = float(data.get("total_active_ms", 0.0))
        result.stroke_detail[sec_name] = {
            "strokes": strokes,
            "avg_duration_ms": round(total_ms / strokes, 1) if strokes > 0 else 0,
            "total_active_ms": round(total_ms, 1),
        }

    logger.info(
        f"[CORREGIDO] cambios={len(result.page_changes)} | "
        f"pausas={len(result.pause_events)} | "
        f"activity_ratio={result.activity_ratio} | "
        f"rewrites={result.num_rewrites} | "
        f"active_pixels_threshold={active_pixels_threshold} | "
        f"low_motion={round(low_motion, 4)} | "
        f"high_motion={round(high_motion, 4)}"
    )

# ══════════════════════════════════════════════════════════════════
# BLOQUE 9 — BORRADOR / TOOLBAR
# ══════════════════════════════════════════════════════════════════

def _is_eraser_active(frame: np.ndarray) -> bool:
    roi = _crop_roi_by_pct(
        frame,
        TOOLBAR_ROI_X1_PCT,
        TOOLBAR_ROI_Y1_PCT,
        TOOLBAR_ROI_X2_PCT,
        TOOLBAR_ROI_Y2_PCT,
    )
    if roi.size == 0:
        return False

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    orange_mask = cv2.inRange(hsv, np.array([5, 90, 80]), np.array([25, 255, 255]))
    red_mask_1 = cv2.inRange(hsv, np.array([0, 90, 80]), np.array([10, 255, 255]))
    red_mask_2 = cv2.inRange(hsv, np.array([170, 90, 80]), np.array([180, 255, 255]))

    mask = cv2.bitwise_or(orange_mask, cv2.bitwise_or(red_mask_1, red_mask_2))
    colored_ratio = int(np.count_nonzero(mask)) / (mask.size or 1)

    return colored_ratio >= 0.020


# ══════════════════════════════════════════════════════════════════
# BLOQUE 10 — TIEMPO POR SECCIÓN
# ══════════════════════════════════════════════════════════════════

def _calculate_time_per_section(
    page_changes: list[dict],
    total_frames: int,
    fps: float,
) -> dict:
    if fps <= 0:
        return {"seccion_1": 0.0}

    tail_start_ms = _tail_start_ms(total_frames, fps)
    if tail_start_ms <= 0:
        return {"seccion_1": 0.0}

    valid_timestamps = []
    for change in page_changes:
        ts = change.get("timestamp_ms")
        if ts is None:
            continue
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            continue
        if 0.0 < ts < tail_start_ms:
            valid_timestamps.append(ts)

    valid_timestamps.sort()

    normalized_timestamps = []
    min_gap_ms = max(
        (SAMPLE_EVERY_N_FRAMES / fps) * 1000.0,
        (PAGE_CHANGE_MIN_GAP_FRAMES / fps) * 1000.0,
    )
    min_section_ms = max(16000.0, min_gap_ms)
    min_terminal_section_ms = max(16000.0, min_gap_ms)

    for ts in valid_timestamps:
        remaining_ms = tail_start_ms - ts
        if remaining_ms < min_terminal_section_ms:
            continue

        if not normalized_timestamps:
            if ts >= min_section_ms:
                normalized_timestamps.append(ts)
            continue

        if ts - normalized_timestamps[-1] < min_gap_ms:
            continue

        if ts - normalized_timestamps[-1] < min_section_ms:
            continue

        normalized_timestamps.append(ts)

    boundaries_ms = [0.0]
    boundaries_ms.extend(normalized_timestamps)
    boundaries_ms.append(tail_start_ms)

    time_per_section = {}
    for i in range(len(boundaries_ms) - 1):
        sec_name = f"seccion_{i + 1}"
        duration_ms = max(0.0, boundaries_ms[i + 1] - boundaries_ms[i])
        time_per_section[sec_name] = round(duration_ms / 1000.0, 2)

    if not time_per_section:
        time_per_section["seccion_1"] = round(tail_start_ms / 1000.0, 2)

    return time_per_section

# ══════════════════════════════════════════════════════════════════
# BLOQUE 11 — POSTPROCESO FINAL
# ══════════════════════════════════════════════════════════════════

def _postprocess_analysis_results(result: VideoAnalysisResult) -> None:
    """
    Refinamiento final del análisis:
    - limpia pausas inválidas
    - une pausas fragmentadas
    - reetiqueta pausas según time_per_section final
    - NO recalcula activity_ratio
    """
    section_ranges = []
    if isinstance(result.time_per_section, dict):
        ordered_sections = []
        for sec_name, duration_s in result.time_per_section.items():
            if not isinstance(sec_name, str) or not sec_name.startswith("seccion_"):
                continue
            try:
                sec_idx = int(sec_name.split("_")[-1])
                duration_s = float(duration_s)
            except Exception:
                continue
            if duration_s <= 0:
                continue
            ordered_sections.append((sec_idx, sec_name, duration_s))

        ordered_sections.sort(key=lambda x: x[0])

        cursor_ms = 0.0
        for _, sec_name, duration_s in ordered_sections:
            start_ms = cursor_ms
            end_ms = cursor_ms + (duration_s * 1000.0)
            section_ranges.append((start_ms, end_ms, sec_name))
            cursor_ms = end_ms

    if not result.pause_events:
        result.pause_events = []
        logger.info(
            f"POST | pausas_finales=0 | activity_ratio={result.activity_ratio}"
        )
        return

    pauses = []
    for p in result.pause_events:
        if not isinstance(p, dict):
            continue
        try:
            inicio = float(p.get("inicio_ms", 0))
            fin = float(p.get("fin_ms", inicio))
            dur = float(p.get("duracion_ms", fin - inicio))
        except Exception:
            continue

        if dur <= 0 or fin < inicio:
            continue

        pauses.append(
            {
                "inicio_ms": inicio,
                "fin_ms": fin,
                "duracion_ms": dur,
                "seccion": p.get("seccion", "desconocida"),
            }
        )

    if not pauses:
        result.pause_events = []
        logger.info(
            f"POST | pausas_finales=0 | activity_ratio={result.activity_ratio}"
        )
        return

    pauses.sort(key=lambda x: x["inicio_ms"])

    merged = [pauses[0]]
    for p in pauses[1:]:
        last = merged[-1]
        gap = p["inicio_ms"] - last["fin_ms"]

        if gap <= 1500:
            last["fin_ms"] = max(last["fin_ms"], p["fin_ms"])
            last["duracion_ms"] = last["fin_ms"] - last["inicio_ms"]
        else:
            merged.append(p)

    cleaned = []
    for p in merged:
        dur = p["duracion_ms"]
        if dur < 4000:
            continue

        section_name = p["seccion"]
        if section_ranges:
            midpoint_ms = (p["inicio_ms"] + p["fin_ms"]) / 2.0
            for idx, (start_ms, end_ms, sec_name) in enumerate(section_ranges):
                is_last = idx == len(section_ranges) - 1
                if start_ms <= midpoint_ms < end_ms or (
                    is_last and start_ms <= midpoint_ms <= end_ms
                ):
                    section_name = sec_name
                    break

        cleaned.append(
            {
                "inicio_ms": round(p["inicio_ms"], 1),
                "fin_ms": round(p["fin_ms"], 1),
                "duracion_ms": round(dur, 1),
                "seccion": section_name,
            }
        )

    result.pause_events = cleaned
    logger.info(
        f"POST | pausas_finales={len(cleaned)} | activity_ratio={result.activity_ratio}"
    )

# ══════════════════════════════════════════════════════════════════
# BLOQUE 12 — WRAPPERS DE COMPATIBILIDAD
# ══════════════════════════════════════════════════════════════════

def detect_page_changes(video_path: str, subject: str = "", level: str = "") -> list[dict]:
    """
    Wrapper de compatibilidad.
    Retorna únicamente page_changes usando la misma ruta consolidada.
    """
    result = analyze_video(video_path, subject=subject, level=level)
    return result.page_changes


def analyze_writing_activity(video_path: str, subject: str = "", level: str = "") -> dict:
    """
    Wrapper de compatibilidad.
    Retorna señales de escritura/pausas/borrados sin romper referencias antiguas.
    """
    result = analyze_video(video_path, subject=subject, level=level)
    return {
        "pause_events": result.pause_events,
        "activity_ratio": result.activity_ratio,
        "stroke_detail": result.stroke_detail,
        "num_rewrites": result.num_rewrites,
        "time_per_section": result.time_per_section,
    }


def detect_eraser_events(video_path: str, subject: str = "", level: str = "") -> dict:
    """
    Wrapper de compatibilidad.
    Conserva una función separada para código legado.
    """
    result = analyze_video(video_path, subject=subject, level=level)
    return {
        "num_rewrites": result.num_rewrites,
    }


def get_current_section(frame_idx: int, page_changes: list[dict], fps: float) -> str:
    """
    Wrapper público de compatibilidad.
    """
    return _get_current_section(frame_idx, page_changes, fps)