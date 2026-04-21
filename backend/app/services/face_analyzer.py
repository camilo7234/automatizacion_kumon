from __future__ import annotations

"""
app/services/face_analyzer.py
══════════════════════════════════════════════════════════════════
Análisis de cámara frontal — STUB DESACTIVADO.

ESTADO ACTUAL:
  Desactivado hasta confirmar que la Galaxy Tab S6 soporta
  grabación simultánea de:
    - Pantalla (grabación de Class Navi)
    - Cámara frontal (PIP en el mismo archivo de video)
    - Audio (micrófono)

ACTIVACIÓN:
  1. Confirmar hardware: grabar un video de prueba con PIP
     y verificar que las 3 pistas están en el mismo archivo.
  2. Cambiar en backend/.env:
       ENABLE_FACE_ANALYSIS=true
  3. Implementar _extract_pip_region() con las coordenadas
     reales del PIP en el video de la tablet.
  4. Implementar _analyze_gaze() con el modelo elegido.

MÉTRICAS PREVISTAS (cuando esté activo):
  - pct_mirando_pantalla: porcentaje del tiempo que el niño
    mira la pantalla (proxy de concentración).
  - head_pose_events: eventos donde la cabeza se desvía
    significativamente de la pantalla.
  - distancia_estimada: distancia aproximada del niño a la
    tablet (útil para evaluar postura).

ESTRUCTURA gaze_data (cuando esté activo):
  {
    "pct_mirando_pantalla": 0.82,
    "head_pose_events": [
      {"inicio_ms": 12000, "duracion_ms": 3500, "desviacion": "izquierda"},
      ...
    ],
    "distancia_cm_estimada": 35.0,
    "confianza": 0.78
  }

REGLA auto_captured_flags:
  Igual que audio_analyzer: solo si confianza >= umbral se
  agrega a auto_captured_flags y no aparece en el formulario.
  Si confianza < umbral → sale en formulario para el orientador.
══════════════════════════════════════════════════════════════════
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Estructuras de datos
# ══════════════════════════════════════════════════════════════════

@dataclass
class FaceAnalysisResult:
    """
    Resultado del análisis de cámara frontal.
    Todos los campos son None cuando el módulo está desactivado
    o cuando el hardware no soporta grabación PIP.

    Se persiste en qualitative_results.gaze_data (JSONB).
    None mientras ENABLE_FACE_ANALYSIS=false.
    """

    # Porcentaje del tiempo mirando la pantalla (0.0-1.0)
    pct_mirando_pantalla:    Optional[float] = None

    # Eventos de desvío de mirada
    # [{"inicio_ms": X, "duracion_ms": Y, "desviacion": "izquierda|derecha|arriba|abajo"}]
    head_pose_events:        list = field(default_factory=list)

    # Distancia estimada del niño a la tablet en cm
    distancia_cm_estimada:   Optional[float] = None

    # Confianza global del análisis (0.0-1.0)
    confianza:               float = 0.0

    # Métricas capturadas con confianza suficiente
    # (no aparecen en el formulario del orientador)
    auto_captured_flags:     list = field(default_factory=list)

    # Prefills generados
    prefills:                dict = field(default_factory=dict)

    # Meta
    enabled:                 bool  = False
    skip_reason:             Optional[str] = None
    processing_ok:           bool  = False

    def to_gaze_dict(self) -> Optional[dict]:
        """
        Serializa para guardar en qualitative_results.gaze_data.
        Retorna None si el módulo está desactivado.
        """
        if not self.enabled or not self.processing_ok:
            return None
        return {
            "pct_mirando_pantalla":  self.pct_mirando_pantalla,
            "head_pose_events":      self.head_pose_events,
            "distancia_cm_estimada": self.distancia_cm_estimada,
            "confianza":             self.confianza,
        }


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL — Entry point
# ══════════════════════════════════════════════════════════════════

def analyze_face(
    video_path: str,
    total_frames: int,
    fps: float,
    page_changes: list[dict],
) -> FaceAnalysisResult:
    """
    Analiza la cámara frontal del video PIP.

    ACTUALMENTE: retorna un resultado vacío inmediatamente
    porque ENABLE_FACE_ANALYSIS=false en .env.

    Cuando se active:
      1. Extrae la región PIP del video frame a frame.
      2. Detecta la cara del niño con un detector ligero.
      3. Estima la pose de la cabeza (gaze direction).
      4. Calcula pct_mirando_pantalla y head_pose_events.

    Args:
        video_path:   ruta al video (con PIP cuando esté activo)
        total_frames: total de frames del video
        fps:          fps del video
        page_changes: cambios de página para contextualizar eventos

    Returns:
        FaceAnalysisResult. Si enabled=False → todos los campos None.
    """
    result = FaceAnalysisResult()

    # ── Guardia principal ─────────────────────────────────────────
    if not settings.ENABLE_FACE_ANALYSIS:
        result.enabled     = False
        result.skip_reason = (
            "ENABLE_FACE_ANALYSIS=false en .env. "
            "Activar cuando se confirme hardware Galaxy Tab S6 con PIP."
        )
        logger.info("face_analyzer: desactivado por configuración.")
        return result

    # ── Flujo activo (implementar cuando se confirme hardware) ────
    result.enabled = True
    logger.info("face_analyzer: iniciando análisis de cámara frontal...")

    try:
        result = _run_face_analysis(
            video_path, total_frames, fps, page_changes
        )
        result.enabled       = True
        result.processing_ok = True

    except NotImplementedError:
        result.skip_reason   = "Análisis facial pendiente de implementación."
        result.processing_ok = False
        logger.warning("face_analyzer: análisis no implementado aún.")

    except Exception as e:
        result.skip_reason   = f"Error en análisis facial: {str(e)[:100]}"
        result.processing_ok = False
        logger.error(f"face_analyzer error: {e}", exc_info=True)

    return result


# ══════════════════════════════════════════════════════════════════
# Implementación (PENDIENTE — esqueleto listo)
# ══════════════════════════════════════════════════════════════════

def _run_face_analysis(
    video_path: str,
    total_frames: int,
    fps: float,
    page_changes: list[dict],
) -> FaceAnalysisResult:
    """
    IMPLEMENTAR cuando se confirme el hardware.

    Pasos previstos:
      1. _extract_pip_region(frame) → recortar región PIP del video
      2. _detect_face(pip_frame)    → detectar cara con MediaPipe o
                                      OpenCV Haar Cascade (liviano)
      3. _estimate_gaze(face_roi)   → estimar dirección de mirada
      4. Agregar a head_pose_events si desvío > umbral
      5. Calcular pct_mirando_pantalla al final

    Librerías candidatas (NO instalar hasta confirmar hardware):
      - mediapipe: detección de cara y pose, muy preciso
      - opencv face detection: Haar cascade, más liviano
      - dlib: más pesado, mejor precisión para pose

    NOTA: Antes de implementar, verificar que el video PIP
    tenga suficiente resolución en la región de la cara para
    que la detección sea confiable.
    """
    raise NotImplementedError(
        "Análisis facial pendiente. "
        "Implementar cuando se confirme hardware Samsung Galaxy S6 con PIP."
    )


def _extract_pip_region(frame, pip_coords: dict):
    """
    STUB — Extrae la región PIP (cámara frontal) del frame.

    Args:
        frame:      frame completo del video (numpy array)
        pip_coords: coordenadas del PIP en el video.
                    Determinar con un video de prueba real.
                    Ejemplo: {"x1": 0, "y1": 0, "x2": 200, "y2": 200}

    Returns:
        numpy array con la región del PIP recortada.
    """
    raise NotImplementedError("Coordenadas PIP pendientes de calibración.")


def _detect_face(pip_frame):
    """
    STUB — Detecta la cara del niño en la región PIP.

    Returns:
        bounding box (x, y, w, h) o None si no se detectó.
    """
    raise NotImplementedError


def _estimate_gaze(face_roi) -> Optional[str]:
    """
    STUB — Estima la dirección de la mirada.

    Returns:
        "pantalla" | "izquierda" | "derecha" | "arriba" | "abajo" | None
    """
    raise NotImplementedError


# ══════════════════════════════════════════════════════════════════
# Utilidades públicas
# ══════════════════════════════════════════════════════════════════

def is_face_analysis_enabled() -> bool:
    """
    Retorna True si el análisis facial está habilitado en .env.
    Usado por processing_service para decidir si llamar analyze_face().
    """
    return settings.ENABLE_FACE_ANALYSIS


def get_face_analysis_status() -> dict:
    """
    Retorna el estado del módulo de análisis facial.
    Usado en GET /health para informar al frontend.
    """
    return {
        "enabled":    settings.ENABLE_FACE_ANALYSIS,
        "status":     "active" if settings.ENABLE_FACE_ANALYSIS else "disabled",
        "reason":     (
            "Hardware pendiente de validación (Galaxy Tab S6 PIP)"
            if not settings.ENABLE_FACE_ANALYSIS
            else "Activo"
        ),
        "activate":   "Cambiar ENABLE_FACE_ANALYSIS=true en backend/.env",
    }
