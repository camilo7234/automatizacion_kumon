"""
app/services/pdf_generator.py
══════════════════════════════════════════════════════════════════
Convierte el dict de build_report_data() en un PDF físico
usando ReportLab.

Recibe:
  - report_data: Dict producido por report_generator.build_report_data()
  - job_created_at: datetime de ProcessingJob.created_at (fecha del boletín)
  - prospecto_nombre: str del sujeto evaluado
  - orientador_nombre: str|None del orientador que completó el formulario
  - output_path: ruta absoluta donde guardar el PDF

Secciones del PDF:
  1 — Encabezado (nombre, fecha evaluación, materia, nivel, orientador)
  2 — Resultado cuantitativo (score, tiempo, semáforo, starting point)
  3 — Valoración cualitativa (tabla de métricas, postura, narrativa)
  4 — Recomendación del orientador
  5 — Pie de página (fecha emisión, indicador validación)

REGLA: No modifica report_generator.py ni models.py.
       Solo lee el dict ya construido y escribe el archivo.
══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ── Paleta de colores Kumon ───────────────────────────────────────
_COLOR_VERDE    = colors.HexColor("#2ECC71")
_COLOR_AMARILLO = colors.HexColor("#F1C40F")
_COLOR_ROJO     = colors.HexColor("#E74C3C")
_COLOR_AZUL     = colors.HexColor("#2C3E50")
_COLOR_GRIS     = colors.HexColor("#95A5A6")
_COLOR_FONDO    = colors.HexColor("#F8F9FA")
_COLOR_BORDE    = colors.HexColor("#DEE2E6")

# ── Mapa etiquetas → color de fondo de la celda ──────────────────
_ETIQUETA_COLOR: Dict[str, Any] = {
    "fortaleza":     colors.HexColor("#D5F5E3"),
    "en_desarrollo": colors.HexColor("#FEF9E7"),
    "refuerzo":      colors.HexColor("#FDEBD0"),
    "atencion":      colors.HexColor("#FADBD8"),
}

# ── Mapa etiquetas → texto legible en español ─────────────────────
_ETIQUETA_LABEL: Dict[str, str] = {
    "fortaleza":     "Fortaleza",
    "en_desarrollo": "En desarrollo",
    "refuerzo":      "Refuerzo",
    "atencion":      "Atención especial",
}

# ── Mapa semáforo → color visual ─────────────────────────────────
_SEMAFORO_COLOR: Dict[str, Any] = {
    "verde":    _COLOR_VERDE,
    "amarillo": _COLOR_AMARILLO,
    "rojo":     _COLOR_ROJO,
}

# ── Mapa semáforo → texto pedagógico ─────────────────────────────
_SEMAFORO_TEXTO: Dict[str, str] = {
    "verde":    "Puede avanzar al siguiente nivel",
    "amarillo": "Consolidar antes de avanzar",
    "rojo":     "Requiere refuerzo en este nivel",
}


def generate_pdf(
    report_data: Dict[str, Any],
    job_created_at: datetime,
    prospecto_nombre: str,
    output_path: str,
    orientador_nombre: Optional[str] = None,
    hubo_correcciones: bool = False,
) -> Path:
    """
    Genera el PDF del boletín y lo guarda en output_path.

    Parámetros:
      report_data       → dict de build_report_data() (4 bloques)
      job_created_at    → ProcessingJob.created_at (fecha de evaluación)
      prospecto_nombre  → nombre del sujeto evaluado
      output_path       → ruta absoluta del archivo PDF de salida
      orientador_nombre → nombre del orientador (None si no disponible)
      hubo_correcciones → True si el orientador editó campos del boletín

    Retorna la ruta del PDF generado como Path.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = _build_styles()
    story  = []

    cuant = report_data.get("cuantitativo", {})
    cual  = report_data.get("cualitativo",  {})
    comb  = report_data.get("combinado",    {})

    # ── Sección 1: Encabezado ─────────────────────────────────────
    story += _seccion_encabezado(
        styles,
        prospecto_nombre=prospecto_nombre,
        job_created_at=job_created_at,
        cuant=cuant,
        orientador_nombre=orientador_nombre,
    )

    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=_COLOR_BORDE))
    story.append(Spacer(1, 0.4 * cm))

    # ── Sección 2: Resultado cuantitativo ─────────────────────────
    story += _seccion_cuantitativo(styles, cuant)

    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=_COLOR_BORDE))
    story.append(Spacer(1, 0.4 * cm))

    # ── Sección 3: Valoración cualitativa ─────────────────────────
    story += _seccion_cualitativa(styles, cual)

    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=_COLOR_BORDE))
    story.append(Spacer(1, 0.4 * cm))

    # ── Sección 4: Recomendación ──────────────────────────────────
    story += _seccion_recomendacion(styles, cuant, comb)

    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=_COLOR_BORDE))
    story.append(Spacer(1, 0.3 * cm))

    # ── Sección 5: Pie de página ──────────────────────────────────
    story += _seccion_pie(styles, hubo_correcciones=hubo_correcciones)

    doc.build(story)
    logger.info("PDF generado: %s (%.1f KB)", path, path.stat().st_size / 1024)
    return path


# ══════════════════════════════════════════════════════════════════
# Estilos
# ══════════════════════════════════════════════════════════════════

def _build_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo":        ParagraphStyle(
            "titulo",
            fontSize=18, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL, alignment=TA_CENTER, spaceAfter=4,
        ),
        "subtitulo":     ParagraphStyle(
            "subtitulo",
            fontSize=11, fontName="Helvetica",
            textColor=_COLOR_GRIS, alignment=TA_CENTER, spaceAfter=2,
        ),
        "seccion":       ParagraphStyle(
            "seccion",
            fontSize=13, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL, spaceBefore=6, spaceAfter=4,
        ),
        "campo_label":   ParagraphStyle(
            "campo_label",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL,
        ),
        "campo_valor":   ParagraphStyle(
            "campo_valor",
            fontSize=10, fontName="Helvetica",
            textColor=colors.black,
        ),
        "narrativa":     ParagraphStyle(
            "narrativa",
            fontSize=10, fontName="Helvetica",
            textColor=colors.black, leading=14, spaceAfter=4,
        ),
        "pie":           ParagraphStyle(
            "pie",
            fontSize=8, fontName="Helvetica",
            textColor=_COLOR_GRIS, alignment=TA_CENTER,
        ),
        "pie_negrita":   ParagraphStyle(
            "pie_negrita",
            fontSize=8, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL, alignment=TA_CENTER,
        ),
    }


# ══════════════════════════════════════════════════════════════════
# Sección 1 — Encabezado
# ══════════════════════════════════════════════════════════════════

def _seccion_encabezado(
    styles: Dict,
    prospecto_nombre: str,
    job_created_at: datetime,
    cuant: Dict[str, Any],
    orientador_nombre: Optional[str],
) -> list:
    """
    Encabezado del boletín.

    Fecha mostrada: job_created_at (ProcessingJob.created_at).
    NO usa test_date del OCR — esa es la fecha interna del test Class Navi.
    """
    elementos = []

    elementos.append(Paragraph("BOLETÍN DE DIAGNÓSTICO KUMON", styles["titulo"]))
    elementos.append(Paragraph("Prueba Diagnóstica — Resultado de Evaluación", styles["subtitulo"]))
    elementos.append(Spacer(1, 0.3 * cm))

    fecha_str = job_created_at.strftime("%d de %B de %Y") if job_created_at else "No disponible"

    materia_raw  = cuant.get("subject", "")
    materia_str  = materia_raw.capitalize() if materia_raw else "No disponible"
    ws_str       = cuant.get("ws") or "No disponible"
    display_name = cuant.get("display_name") or "No disponible"
    nivel_str    = f"{display_name} — WS {ws_str}"

    filas = [
        ["Estudiante evaluado:", prospecto_nombre or "No disponible"],
        ["Fecha de evaluación:", fecha_str],
        ["Materia:",             materia_str],
        ["Nivel / WS:",          nivel_str],
    ]
    if orientador_nombre:
        filas.append(["Orientador:", orientador_nombre])

    tabla = Table(filas, colWidths=[5 * cm, 12 * cm])
    tabla.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",  (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",  (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), _COLOR_AZUL),
        ("VALIGN",    (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla)
    return elementos


# ══════════════════════════════════════════════════════════════════
# Sección 2 — Resultado cuantitativo
# ══════════════════════════════════════════════════════════════════

def _seccion_cuantitativo(styles: Dict, cuant: Dict[str, Any]) -> list:
    elementos = []
    elementos.append(Paragraph("Resultado Cuantitativo", styles["seccion"]))

    correctas = cuant.get("correct_answers")
    total     = cuant.get("total_questions")
    pct       = cuant.get("percentage")
    score_str = (
        f"{correctas}/{total}  ({pct:.1f}%)"
        if correctas is not None and total is not None and pct is not None
        else "No disponible"
    )

    estudio  = cuant.get("study_time_min")
    objetivo = cuant.get("target_time_min")
    tiempo_str = (
        f"{estudio:.1f} min (objetivo: {objetivo:.1f} min)"
        if estudio is not None and objetivo is not None
        else "No disponible"
    )

    semaforo     = (cuant.get("semaforo") or "").strip().lower()
    semaforo_col = _SEMAFORO_COLOR.get(semaforo, _COLOR_GRIS)
    semaforo_txt = _SEMAFORO_TEXTO.get(semaforo, "Sin clasificación")
    semaforo_label = semaforo.capitalize() if semaforo else "No disponible"

    starting = cuant.get("starting_point") or "No disponible"

    # Tabla de 4 filas con campo / valor
    filas = [
        [Paragraph("<b>Indicador</b>",    styles["campo_label"]),
         Paragraph("<b>Resultado</b>",    styles["campo_label"])],
        ["Aciertos",   score_str],
        ["Tiempo",     tiempo_str],
        ["Punto de partida recomendado", starting],
    ]
    tabla = Table(filas, colWidths=[8 * cm, 9 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), _COLOR_AZUL),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 10),
        ("GRID",         (0, 0), (-1, -1), 0.5, _COLOR_BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_COLOR_FONDO, colors.white]),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.3 * cm))

    # Semáforo — bloque visual destacado
    semaforo_tabla = Table(
        [[f"● {semaforo_label.upper()}  —  {semaforo_txt}"]],
        colWidths=[17 * cm],
    )
    semaforo_tabla.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), semaforo_col),
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 11),
        ("TEXTCOLOR",   (0, 0), (-1, -1), colors.white),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    elementos.append(semaforo_tabla)
    return elementos


# ══════════════════════════════════════════════════════════════════
# Sección 3 — Valoración cualitativa
# ══════════════════════════════════════════════════════════════════

def _seccion_cualitativa(styles: Dict, cual: Dict[str, Any]) -> list:
    elementos = []
    elementos.append(Paragraph("Valoración Cualitativa", styles["seccion"]))

    secciones  = cual.get("secciones") or []
    auto_flags = cual.get("auto_flags") or []
    etiqueta   = cual.get("etiqueta_total") or ""
    pct_total  = cual.get("total_porcentaje")

    # Encabezado resumen cualitativo
    if pct_total is not None and etiqueta:
        etiq_label = _ETIQUETA_LABEL.get(etiqueta, etiqueta)
        etiq_color = _ETIQUETA_COLOR.get(etiqueta, _COLOR_FONDO)
        resumen = Table(
            [[f"Valoración global: {etiq_label}  ({pct_total:.1f}%)"]],
            colWidths=[17 * cm],
        )
        resumen.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), etiq_color),
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(resumen)
        elementos.append(Spacer(1, 0.3 * cm))

    # Tabla de métricas por sección
    if secciones:
        filas_tabla = [
            [Paragraph("<b>Área evaluada</b>",    styles["campo_label"]),
             Paragraph("<b>Nivel</b>",             styles["campo_label"]),
             Paragraph("<b>Puntaje</b>",           styles["campo_label"]),
             Paragraph("<b>Fuente</b>",            styles["campo_label"])],
        ]
        estilos_filas = []
        for i, sec in enumerate(secciones, start=1):
            nombre  = sec.get("nombre") or sec.get("name") or f"Sección {i}"
            etiq_s  = sec.get("etiqueta") or ""
            pct_s   = sec.get("porcentaje") or sec.get("puntaje")
            fuente  = "Auto" if nombre.lower() in [f.lower() for f in auto_flags] else "Orientador"
            label_s = _ETIQUETA_LABEL.get(etiq_s, etiq_s)
            col_s   = _ETIQUETA_COLOR.get(etiq_s, colors.white)
            pct_txt = f"{pct_s:.1f}%" if pct_s is not None else "—"

            filas_tabla.append([nombre, label_s, pct_txt, fuente])
            estilos_filas.append(("BACKGROUND", (1, i), (1, i), col_s))

        tabla_cual = Table(filas_tabla, colWidths=[7 * cm, 5 * cm, 3 * cm, 2.5 * cm])
        estilo_base = [
            ("BACKGROUND",   (0, 0), (-1, 0), _COLOR_AZUL),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("GRID",         (0, 0), (-1, -1), 0.5, _COLOR_BORDE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]
        tabla_cual.setStyle(TableStyle(estilo_base + estilos_filas))
        elementos.append(tabla_cual)
    else:
        elementos.append(Paragraph("No se registraron métricas cualitativas.", styles["narrativa"]))

    return elementos


# ══════════════════════════════════════════════════════════════════
# Sección 4 — Recomendación
# ══════════════════════════════════════════════════════════════════

def _seccion_recomendacion(
    styles: Dict,
    cuant: Dict[str, Any],
    comb: Dict[str, Any],
) -> list:
    elementos = []
    elementos.append(Paragraph("Recomendación del Orientador", styles["seccion"]))

    recomendacion_cuant = cuant.get("recommendation") or ""
    narrativa_comb      = comb.get("narrativa") or ""

    if recomendacion_cuant:
        elementos.append(Paragraph(recomendacion_cuant, styles["narrativa"]))

    if narrativa_comb and narrativa_comb != recomendacion_cuant:
        elementos.append(Paragraph(narrativa_comb, styles["narrativa"]))

    if not recomendacion_cuant and not narrativa_comb:
        elementos.append(Paragraph(
            "El orientador debe completar la recomendación manualmente.",
            styles["narrativa"],
        ))

    return elementos


# ══════════════════════════════════════════════════════════════════
# Sección 5 — Pie de página
# ══════════════════════════════════════════════════════════════════

def _seccion_pie(styles: Dict, hubo_correcciones: bool) -> list:
    elementos = []
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    elementos.append(Paragraph(f"Fecha de emisión del boletín: {ahora}", styles["pie"]))

    if hubo_correcciones:
        elementos.append(Paragraph(
            "✔ Validado y corregido por el orientador",
            styles["pie_negrita"],
        ))
    else:
        elementos.append(Paragraph(
            "Generado automáticamente — pendiente de validación por el orientador",
            styles["pie"],
        ))

    elementos.append(Paragraph("Sistema de Diagnóstico Kumon — Uso interno del centro", styles["pie"]))
    return elementos