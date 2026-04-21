"""
app/services/ocr_service.py
══════════════════════════════════════════════════════════════════
Extracción OCR del frame de resumen de Class Navi.

PRINCIPIO CLAVE:
  Class Navi ya calcula el score automáticamente.
  Este servicio solo LEE el frame de resumen final que muestra:
    WS, Study Time, Target Time, Score, Test Date, Group

INICIALIZACIÓN:
  EasyOCR se instancia UNA SOLA VEZ en el startup de la app.
  Nunca instanciar por frame ni por request (carga ~2-4 segundos).
  La instancia global se accede via get_ocr_reader().

CONFIANZA:
  Cada campo extraído tiene un score de confianza (0.0-1.0).
  confidence_score final = promedio de los campos clave.
  Si confidence_score < OCR_CONFIDENCE_MIN (0.75) →
    needs_manual_review = True en TestResult.

RECUPERACIONES ACTIVAS:
  _extract_score  → "37/5"           → 37/50  (OCR perdió '0' final)
  _extract_times  → "224 mins"       → 22.4   (OCR perdió punto decimal)
  _extract_times  → "p4 22 4 mins"   → 22.4   (token fusionado EasyOCR)
  _extract_ws     → "p4 22 4 mins"   → "P4"   (nivel en token fusionado)
  _extract_date   → "Lun. 23 2026"   → fecha  (formato Class Navi)
══════════════════════════════════════════════════════════════════
"""

import re
import logging
import cv2
from datetime import date
from typing import Optional
import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)

# ── Instancia global de EasyOCR ───────────────────────────────────
_ocr_reader = None

# ── Patrón de niveles Kumon (todas las materias) ──────────────────
# Matemáticas / Español: K2, K1, P1-P6, M1-M3, H
# Inglés:                PII, PI, M, H, K
# ORDEN IMPORTA: PII antes de PI antes de P, K2/K1 antes de K
_LEVEL_RE = re.compile(
    r'\b(PII|PI|K[12]|P[1-6]|M[1-3]|H|K)\b',
    re.IGNORECASE
)


def initialize_ocr_reader() -> None:
    """
    Inicializa EasyOCR con español e inglés.
    Llamar SOLO desde app.on_event("startup").
    """
    global _ocr_reader
    if _ocr_reader is not None:
        logger.info("OCR reader ya estaba inicializado, omitiendo.")
        return
    try:
        import easyocr
        logger.info("Inicializando EasyOCR ['es', 'en']...")
        _ocr_reader = easyocr.Reader(
            ["es", "en"],
            gpu=False,
            verbose=False,
        )
        logger.info("EasyOCR inicializado correctamente.")
    except Exception as e:
        logger.error(f"Error inicializando EasyOCR: {e}")
        raise


def get_ocr_reader():
    """Retorna la instancia global de EasyOCR."""
    if _ocr_reader is None:
        raise RuntimeError(
            "EasyOCR no está inicializado. "
            "Verificar que initialize_ocr_reader() se llamó en startup."
        )
    return _ocr_reader


# ══════════════════════════════════════════════════════════════════
# Resultado estructurado del OCR
# ══════════════════════════════════════════════════════════════════

def _json_safe(value):
    """Convierte tipos NumPy y estructuras anidadas a tipos JSON-nativos."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


class OCRExtractionResult:
    """
    Resultado de leer el frame de resumen de Class Navi.
    Todos los campos son Optional porque el OCR puede fallar
    en leer uno o varios de ellos.
    """

    def __init__(self):
        self.ws: Optional[str] = None
        self.study_time_min: Optional[float] = None
        self.target_time_min: Optional[float] = None
        self.correct_answers: Optional[int] = None
        self.total_questions: Optional[int] = None
        self.percentage: Optional[float] = None
        self.test_date: Optional[date] = None
        self.group: Optional[str] = None

        self.confidence_score: float = 0.0
        self.needs_manual_review: bool = True
        self.raw_text: list = []
        self.field_confidences: dict = {}

    def to_dict(self) -> dict:
        payload = {
            "ws": self.ws,
            "study_time_min": float(self.study_time_min) if self.study_time_min is not None else None,
            "target_time_min": float(self.target_time_min) if self.target_time_min is not None else None,
            "correct_answers": int(self.correct_answers) if self.correct_answers is not None else None,
            "total_questions": int(self.total_questions) if self.total_questions is not None else None,
            "percentage": float(self.percentage) if self.percentage is not None else None,
            "test_date": self.test_date,
            "group": self.group,
            "confidence_score": float(self.confidence_score) if self.confidence_score is not None else 0.0,
            "needs_manual_review": bool(self.needs_manual_review),
            "field_confidences": self.field_confidences,
            "raw_text_count": int(len(self.raw_text)),
        }
        return _json_safe(payload)


# ══════════════════════════════════════════════════════════════════
# Extractores por campo
# ══════════════════════════════════════════════════════════════════

# ── MODIFICADO ────────────────────────────────────────────────────
def _extract_ws(raw: list, result: OCRExtractionResult) -> None:
    """
    Extrae el código de nivel (WS) del frame de resumen.
    Soporta todos los niveles de las 3 materias Kumon:
      Matemáticas / Español: K2, K1, P1-P6, M1-M3, H
      Inglés:                PII, PI, M, H, K

    ESTRATEGIA (3 pasos en orden de confianza):

    PASO 1 — Token con "WS" explícito (confianza máxima)
      La celda de Class Navi muestra "WS" como encabezado
      y el nivel en la misma línea o en el token siguiente.
      Ej: "WS P4" → P4

    PASO 2 — Celda limpia: solo el código de nivel (confianza alta)
      EasyOCR a veces lee la celda del nivel como texto aislado.
      Ej: texto = "P4" exacto, conf > 0.60 → P4

    PASO 3 — Nivel dentro de token fusionado (confianza reducida)
      EasyOCR puede fusionar varias celdas en un solo token.
      Ej: "p4 22 4 mins" → extrae "P4", conf * 0.85
      Este paso usa _LEVEL_RE que prioriza PII > PI > K2/K1 > K
      para evitar falsos positivos entre niveles similares.

    Si ningún paso encuentra el nivel → ws queda None
    y _calculate_confidence penaliza la confianza global.
    """
    # PASO 1: token con "WS" explícito
    for (_, text, conf) in raw:
        if re.search(r'\bWS\b|work\s*sheet', text, re.IGNORECASE):
            m = _LEVEL_RE.search(text)
            if m:
                result.ws = m.group(0).upper()
                result.field_confidences["ws"] = conf
                logger.info(f"WS extraído (paso 1 - WS explícito): '{text}' → {result.ws}")
                return

    # PASO 2: celda limpia — solo el código de nivel
    for (_, text, conf) in raw:
        m = _LEVEL_RE.fullmatch(text.strip())
        if m and conf > 0.60:
            result.ws = m.group(0).upper()
            result.field_confidences["ws"] = conf
            logger.info(f"WS extraído (paso 2 - celda limpia): '{text}' → {result.ws}")
            return

    # PASO 3: nivel dentro de token fusionado ("p4 22 4 mins")
    for (_, text, conf) in raw:
        m = _LEVEL_RE.search(text)
        if m:
            result.ws = m.group(0).upper()
            result.field_confidences["ws"] = round(conf * 0.85, 4)
            logger.warning(
                f"WS extraído (paso 3 - token fusionado): '{text}' → {result.ws} "
                f"(confianza reducida: {result.field_confidences['ws']:.2f})"
            )
            return


# ── MODIFICADO ────────────────────────────────────────────────────
def _extract_times(raw: list, result: OCRExtractionResult, full_text: str) -> None:
    """
    Extrae Study Time (decimal, ej: 22.4) y Target Time (entero, ej: 15).

    PASS 1 – decimal limpio + "min"         → Study Time  ("15.6 mins")
             Formato ideal, confianza bruta de EasyOCR.

    PASS 2 – entero + "min"                 → Target Time ("15 mins")
             Primer entero entre 5 y 60 seguido de "min".

    PASS 3 – token fusionado "NN N mins"    → Study Time  ("p4 22 4 mins" → 22.4)
             EasyOCR fusiona celdas: nivel + minutos + segundos en un token.
             Patrón: 1-3 dígitos + espacio + 1-2 dígitos + "mins"
             Interpretación: primer grupo = minutos, segundo = décimas.
             Confianza fija 0.55 (lógicamente verificada, frame distorsionado).

    PASS 4 – 3 dígitos consecutivos + "min" → Study Time recuperado ("224 mins" → 22.4)
             OCR omite el punto decimal. Primeros 2 dígitos = entero, último = décima.
             Confianza fija 0.55 (mismo criterio que PASS 3).

    PASS 5 – entero aislado 5-60            → Target Time fallback
             Solo si target_time_min sigue vacío después de los pasos anteriores.

    NOTA SOBRE ASIGNACIÓN study vs target:
      PASS 1 asigna estrictamente a study_time (valor decimal = tiempo medido).
      PASS 2 asigna estrictamente a target_time (valor entero + "min" = TPT).
      PASS 3 y 4 solo actúan si study_time sigue vacío.
      PASS 5 solo actúa si target_time sigue vacío.
    """
    # ── PASS 1: decimal limpio → Study Time ──────────────────────
    for (_, text, conf) in raw:
        m = re.search(r'(\d+)[.,](\d+)', text.strip())
        if m and result.study_time_min is None:
            val = float(f"{m.group(1)}.{m.group(2)}")
            if 0.5 <= val <= 120:
                result.study_time_min = round(val, 2)
                result.field_confidences["study_time"] = conf

    # ── PASS 2: entero + "min" → Target Time ─────────────────────
    # Se excluyen tokens con punto/coma decimal porque esos corresponden
    # a study_time (ya capturado en PASS 1). Target Time siempre es
    # un entero limpio como "15 mins", nunca "14.4 mins".
    # Sin esta exclusión, "14.4 mins" es procesado primero y el "14"
    # queda asignado como target_time antes de llegar a "15 mins".
    for (_, text, conf) in raw:
        if re.search(r'min', text, re.IGNORECASE):
            if re.search(r'\d+[.,]\d+', text):
                continue  # es decimal → es study_time, no target_time
            m = re.search(r'(\d{1,3})', text)
            if m and result.target_time_min is None:
                val = int(m.group(1))
                if 5 <= val <= 60:
                    result.target_time_min = float(val)
                    result.field_confidences["target_time"] = conf


    # ── PASS 3: token fusionado "NN N mins" → Study Time ─────────
    # EasyOCR une celdas: "p4 22 4 mins" → estudio=22.4 min
    # Requiere: dígitos + espacio + dígitos + "mins" en el mismo token
    if result.study_time_min is None:
        for (_, text, conf) in raw:
            if re.search(r'min', text, re.IGNORECASE):
                m = re.search(r'(\d{1,3})\s+(\d{1,2})\s*mins?', text, re.IGNORECASE)
                if m:
                    val = float(f"{m.group(1)}.{m.group(2)}")
                    if 0.5 <= val <= 120:
                        result.study_time_min = round(val, 2)
                        result.field_confidences["study_time"] = 0.55
                        logger.warning(
                            f"Study time (pass 3 - token fusionado): '{text}' → {val} min"
                        )
                        break

    # ── PASS 4: 3 dígitos consecutivos + "min" → Study Time recovery
    # "22.4 mins" → OCR lee "224 mins" (pierde el punto decimal)
    if result.study_time_min is None:
        for (_, text, conf) in raw:
            if re.search(r'min', text, re.IGNORECASE):
                m = re.search(r'(\d{3})', text)
                if m:
                    val_str = m.group(1)
                    recovered = int(val_str[:2]) + int(val_str[2]) / 10
                    if 0.5 <= recovered <= 120:
                        result.study_time_min = round(recovered, 1)
                        result.field_confidences["study_time"] = 0.55
                        logger.warning(
                            f"Study time (pass 4 - punto omitido): '{text}' → {recovered} min"
                        )
                        break

    # ── PASS 5: entero aislado 5-60 → Target Time fallback ───────
    if result.target_time_min is None:
        for (_, text, conf) in raw:
            m = re.match(r'^\s*(\d{1,3})\s*$', text)
            if m:
                val = int(m.group(1))
                if 5 <= val <= 60:
                    result.target_time_min = float(val)
                    result.field_confidences["target_time"] = conf * 0.8
                    break


def _extract_score(raw: list, result: OCRExtractionResult, full_text: str) -> None:
    """
    Extrae correct_answers, total_questions y percentage.

    CASO NORMAL:   "37/50" → correct=37, total=50, pct=74.0
                   Confianza: valor bruto de EasyOCR.

    RECUPERACIÓN:  "37/5"  → OCR perdió el '0' final del denominador.
                   Si correct > total, intenta total * 10.
                   Confianza fija 0.65.
    """
    fraction_pattern = re.compile(r'(\d+)\s*/\s*(\d+)')

    for (_, text, conf) in raw:
        match = fraction_pattern.search(text)
        if match:
            correct = int(match.group(1))
            total   = int(match.group(2))

            if total > 0 and correct <= total:
                result.correct_answers = correct
                result.total_questions = total
                result.percentage      = round(correct / total * 100, 2)
                result.field_confidences["score"] = conf
                return

            if correct > total and total > 0:
                total_recovered = total * 10
                if correct <= total_recovered:
                    result.correct_answers = correct
                    result.total_questions = total_recovered
                    result.percentage      = round(correct / total_recovered * 100, 2)
                    result.field_confidences["score"] = 0.65
                    logger.warning(
                        f"Score recuperado: {correct}/{total} → {correct}/{total_recovered} "
                        f"(OCR omitió '0' final del denominador)"
                    )
                    return

    # ── Fallback: porcentaje directo ──────────────────────────────
    pct_pattern = re.compile(r'(\d{1,3})\s*%')
    for (_, text, conf) in raw:
        match = pct_pattern.search(text)
        if match:
            pct = float(match.group(1))
            if 0 <= pct <= 100:
                result.percentage = pct
                result.field_confidences["percentage"] = conf

#_______________________________________________________________________
#BLOQUE 4: extracción de fecha y grupo (con recuperación activa)
#_______________________________________________________________________
def _extract_date(raw: list, result: OCRExtractionResult, full_text: str) -> None:
    """
    Extrae test_date del frame de resumen.

    Formatos soportados:
      1. DD/MM/YYYY          → "23/03/2026"
      2. YYYY-MM-DD          → "2026-03-23"
      3. DD-MM-YYYY          → "23-03-2026"
      4. Abrev. + día + año  → "Lun. 23 2026" / "Mar 23 2026" / "Mon 23 2026"
    """
    date_patterns = [
        re.compile(r'(\d{2})/(\d{2})/(\d{4})'),
        re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
        re.compile(r'(\d{2})-(\d{2})-(\d{4})'),
    ]

    for (_, text, conf) in raw:
        for i, pattern in enumerate(date_patterns):
            match = pattern.search(text)
            if match:
                try:
                    if i == 0:
                        result.test_date = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                    elif i == 1:
                        result.test_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                    elif i == 2:
                        result.test_date = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                    result.field_confidences["test_date"] = conf
                    return
                except ValueError:
                    continue

    classnavi_pattern = re.compile(
        r'(?:lun|mar|mie|mié|jue|vie|sáb|sab|dom|mon|tue|wed|thu|fri|sat|sun)'
        r'\.?\s+(\d{1,2})\s+(\d{4})',
        re.IGNORECASE
    )

    today = date.today()

    for (_, text, conf) in raw:
        match = classnavi_pattern.search(text)
        if match:
            try:
                day  = int(match.group(1))
                year = int(match.group(2))
                result.test_date = date(year, today.month, day)
                result.field_confidences["test_date"] = conf * 0.8
                logger.warning(
                    f"Fecha recuperada con mes inferido: día={day}, mes={today.month}, año={year} "
                    f"(Class Navi no muestra mes en el frame)"
                )
                return
            except ValueError:
                continue


def _extract_group(raw: list, result: OCRExtractionResult, full_text: str) -> None:
    """
    Extrae el valor de Group desde el frame de resumen.

    CASOS SOPORTADOS:

    1. "Group 4" en el mismo token → extracción directa
    2. "Group" y "4" en tokens separados (caso más común en EasyOCR)
    3. Fallback: número aislado en columna final (baja confianza)

    NOTA:
      Group NO usa _LEVEL_RE porque no representa nivel Kumon.
      Los grupos válidos de Kumon son del 1 al 9 (un solo dígito).
      Números mayores como 60 (total_questions) quedan explícitamente
      excluidos para evitar confusión con datos de la gráfica de curvas.

      El paso 2B fue eliminado: inferir el grupo desde el dígito final
      del token WS no tiene respaldo en el frame. Si el valor real del
      grupo no aparece como token independiente, el campo queda None y
      se transfiere al cuestionario inteligente.
    """

    group_pattern = re.compile(
        r'(group|level|nivel|grupo)\s*([A-Za-z0-9]+)',
        re.IGNORECASE
    )

    # ── PASO 1: "Group 4" en mismo token ─────────────────────
    for (_, text, conf) in raw:
        match = group_pattern.search(text)
        if match:
            candidate = match.group(2).strip()
            if re.match(r'^[1-9]$', candidate):
                result.group = candidate
                result.field_confidences["group"] = conf
                logger.info(f"Group extraído (paso 1): '{text}' → {result.group}")
                return

    # ── PASO 2: "Group" y valor en tokens separados ──────────
    for i, (_, text, conf) in enumerate(raw):
        if re.search(r'(group|level|nivel|grupo)', text, re.IGNORECASE):
            if i + 1 < len(raw):
                next_text = raw[i + 1][1]
                next_conf = raw[i + 1][2]

                if re.match(r'^[1-9]$', next_text.strip()):
                    result.group = next_text.strip()
                    result.field_confidences["group"] = next_conf * 0.9
                    logger.info(
                        f"Group extraído (paso 2A - token separado): "
                        f"'{text}' + '{next_text}' → {result.group}"
                    )
                    return

    # ── PASO 3: fallback → número aislado (baja confianza) ────
    # Solo acepta dígitos del 1 al 9 — los grupos Kumon nunca superan
    # este rango. Esto evita que total_questions (ej: 60) o valores
    # de la gráfica sean tomados erróneamente como grupo del estudiante.
    for (_, text, conf) in raw:
        if re.match(r'^[1-9]$', text.strip()):
            result.group = text.strip()
            result.field_confidences["group"] = conf * 0.6
            logger.warning(
                f"Group extraído (fallback): '{text}' → {result.group} "
                f"(confianza reducida)"
            )
            return

# ══════════════════════════════════════════════════════════════════
# HELPERS DE DETECCIÓN DINÁMICA DE ROI
# ══════════════════════════════════════════════════════════════════

def _find_orange_region(frame: np.ndarray):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array([5, 80, 80])
    upper = np.array([32, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    h_frame, w_frame = frame.shape[:2]
    # El header rojo/naranja de la tabla Kumon es una franja horizontal
    # delgada (~4-6% del frame). El umbral anterior (10%) era demasiado
    # alto y descartaba el header, forzando el fallback al ROI incorrecto.
    if cv2.contourArea(largest) < (h_frame * w_frame) * 0.03:
        return None

    x, y, w, h = cv2.boundingRect(largest)
    return (y, y + h, x, x + w)

def _detect_table_contour(frame: np.ndarray, orange_bbox) -> np.ndarray:
    if orange_bbox is None:
        return None

    y1, y2, x1, x2 = orange_bbox
    h_frame, w_frame = frame.shape[:2]

    # La tabla completa de resumen comienza en el borde superior
    # del header naranja y se extiende hasta el 97% del frame.
    # Buscar contornos solo dentro del header (y1:y2) es incorrecto
    # porque la tabla está debajo del header, no dentro de él.
    table_region = frame[y1:int(h_frame * 0.97), x1:x2]
    h_or, w_or = table_region.shape[:2]

    if table_region.size == 0:
        return None

    gray = cv2.cvtColor(table_region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    min_area = (h_or * w_or) * 0.05
    valid = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        tx, ty, tw, th = cv2.boundingRect(cnt)
        aspect = tw / th if th > 0 else 0
        if 0.8 < aspect < 12.0:
            valid.append((area, tx, ty, tw, th))

    if not valid:
        return None

    valid.sort(reverse=True)
    _, tx, ty, tw, th = valid[0]
    return table_region[ty:ty + th, tx:tx + tw]


def _fallback_roi(frame: np.ndarray, orange_bbox) -> np.ndarray:
    h, w = frame.shape[:2]

    if orange_bbox is not None:
        y1, y2, x1, x2 = orange_bbox
        mid_y = y1 + (y2 - y1) // 2
        roi = frame[mid_y:y2, x1:x2]
        if roi.size > 0:
            return roi

    # La tabla de resumen (WS | Study Time | Score | Group) siempre
    # aparece en el 45% INFERIOR del frame de Class Navi.
    # El 55% superior contiene la gráfica de curvas (C1, B1, A1, 2A1)
    # que NO debe procesarse con OCR de tabla.
    return frame[int(h * 0.55):h, 0:w]


def _exclude_bottom_strip(roi: np.ndarray, pct: float = 0.08) -> np.ndarray:
    if roi is None or roi.size == 0:
        return roi
    h = roi.shape[0]
    cut = max(1, int(h * (1.0 - pct)))
    return roi[0:cut, :]


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL OCR (CRÍTICA)
# ══════════════════════════════════════════════════════════════════

def extract_summary_frame(frame: np.ndarray) -> OCRExtractionResult:

    result = OCRExtractionResult()

    try:
        reader = get_ocr_reader()

        h, w = frame.shape[:2]

        orange_bbox = _find_orange_region(frame)
        roi = _detect_table_contour(frame, orange_bbox)
        logger.info(f"ROI dinámica: orange_bbox={orange_bbox} | tabla_detectada={roi is not None}")

        if roi is None or roi.size == 0:
            logger.warning("Contorno de tabla no detectado — usando fallback ROI relativo.")
            roi = _fallback_roi(frame, orange_bbox)

        roi = _exclude_bottom_strip(roi, pct=0.08)

        if roi is None or roi.size == 0:
            logger.warning("Fallback ROI vacío — usando frame completo como último recurso.")
            roi = frame

        raw = reader.readtext(roi, detail=1, paragraph=False)

        result.raw_text = [(text, conf) for (_, text, conf) in raw]

        # 🔥 DEBUG CRÍTICO (NO QUITAR)
        logger.warning(f"OCR RAW DETECTADO: {result.raw_text}")

        full_text = " ".join(text for (_, text, _) in raw)

        _extract_ws(raw, result)
        _extract_times(raw, result, full_text)
        _extract_score(raw, result, full_text)
        _extract_date(raw, result, full_text)
        _extract_group(raw, result, full_text)

        result.confidence_score = _calculate_confidence(result)
        result.needs_manual_review = (
            result.confidence_score < settings.OCR_CONFIDENCE_MIN
        )

    except Exception as e:
        logger.error(f"Error en OCR del frame de resumen: {e}")
        result.confidence_score = 0.0
        result.needs_manual_review = True

    return result


# ══════════════════════════════════════════════════════════════════
# Cálculo de confianza global
# ══════════════════════════════════════════════════════════════════

def _calculate_confidence(result: OCRExtractionResult) -> float:
    """
    Calcula el confidence_score global como promedio ponderado
    de los campos clave extraídos.

    Pesos por importancia pedagógica:
      score/percentage → 35%
      study_time       → 25%
      target_time      → 20%
      ws               → 10%
      test_date        → 5%
      group            → 5%
    """
    weights = {
        "score":       0.35,
        "percentage":  0.35,
        "study_time":  0.25,
        "target_time": 0.20,
        "ws":          0.10,
        "test_date":   0.05,
        "group":       0.05,
    }

    total_weight = 0.0
    weighted_sum = 0.0

    for field, weight in weights.items():
        if field in result.field_confidences:
            confidence = result.field_confidences[field]
            weighted_sum += confidence * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0

    raw_score = weighted_sum / total_weight

    if result.correct_answers is None and result.percentage is None:
        raw_score *= 0.5
    if result.study_time_min is None:
        raw_score *= 0.8

    # NOTA: sin coma al final — la coma convertiría el float en una
    # tupla (0.313,) rompiendo la comparación con OCR_CONFIDENCE_MIN.
    return round(min(raw_score, 1.0), 3)