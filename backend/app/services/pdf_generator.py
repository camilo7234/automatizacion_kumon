"""
app/services/pdf_generator.py
══════════════════════════════════════════════════════════════════
BOLETÍN DE DIAGNÓSTICO KUMON — IPIALES
Versión 2.0 — Auditada y reescrita por bloques

BLOQUES:
  [0] Importaciones y constantes
  [1] Helpers — parseo de starting_point y tiempo
  [2] Estilos tipográficos
  [3] Función principal generate_pdf()
  [4] Sección 1 — Encabezado con logo
  [5] Sección 2 — Resultado cuantitativo
  [6] Sección 3 — Valoración cualitativa
  [7] Sección 4 — Puntuación global combinada
  [8] Sección 5 — Recomendación
  [9] Sección 6 — Pie de página
══════════════════════════════════════════════════════════════════
"""

# ══════════════════════════════════════════════════════════════════
# [0] IMPORTACIONES Y CONSTANTES
# ══════════════════════════════════════════════════════════════════

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ── Ruta del logo ─────────────────────────────────────────────────
# Coloca el archivo logo_kumon.png en:  backend/assets/logo_kumon.png
# Si no existe, el boletín se genera igual pero sin imagen de logo.
_LOGO_PATH = os.path.join(
    os.path.dirname(__file__),   # .../backend/app/services/
    "..", "..", "assets", "logo_kumon.png"
)

# ── Nombre fijo del centro ────────────────────────────────────────
_NOMBRE_CENTRO = "Kumon Ipiales"

# ── Paleta de colores ─────────────────────────────────────────────
_COLOR_KUMON_ROJO  = colors.HexColor("#E3001B")   # rojo corporativo Kumon
_COLOR_AZUL        = colors.HexColor("#1A2B4A")   # textos oscuros y encabezados
_COLOR_GRIS        = colors.HexColor("#6B7280")   # texto secundario
_COLOR_GRIS_CLARO  = colors.HexColor("#F3F4F6")   # fondo alterno de filas
_COLOR_BORDE       = colors.HexColor("#D1D5DB")   # bordes de tabla
_COLOR_BLANCO      = colors.white

# ── Colores de semáforo ───────────────────────────────────────────
_SEMAFORO_COLOR: Dict[str, Any] = {
    "verde":    colors.HexColor("#16A34A"),
    "amarillo": colors.HexColor("#D97706"),
    "rojo":     colors.HexColor("#DC2626"),
}
_SEMAFORO_TEXTO: Dict[str, str] = {
    "verde":    "✔ Puede avanzar al siguiente nivel",
    "amarillo": "⚠ Debe consolidar antes de avanzar",
    "rojo":     "✖ Requiere refuerzo en este nivel",
}

# ── Etiquetas cualitativas ────────────────────────────────────────
_ETIQUETA_COLOR: Dict[str, Any] = {
    "fortaleza":     colors.HexColor("#DCFCE7"),
    "en_desarrollo": colors.HexColor("#FEF9C3"),
    "refuerzo":      colors.HexColor("#FFEDD5"),
    "atencion":      colors.HexColor("#FEE2E2"),
}
_ETIQUETA_LABEL: Dict[str, str] = {
    "fortaleza":     "Fortaleza",
    "en_desarrollo": "En desarrollo",
    "refuerzo":      "Necesita refuerzo",
    "atencion":      "Requiere atención especial",
}


# ══════════════════════════════════════════════════════════════════
# [1] HELPERS — PARSEO DE STARTING POINT Y TIEMPO
# ══════════════════════════════════════════════════════════════════

def _parsear_starting_point(raw: Optional[str]) -> str:
    """
    Convierte el valor técnico del backend en texto legible para
    el padre de familia y el orientador.

    Ejemplos:
      "O181a"          → "Nivel O — Hoja 181 (variante a)"
      "7A 1"           → "Nivel 7A — Hoja 1"
      "4A 1 / 4A 21"   → "El orientador define entre Nivel 4A Hoja 1 o Hoja 21"
      "test_superior"  → "Avanza al test del siguiente nivel"
      "test_inferior"  → "Se recomienda test del nivel anterior"
      "nivel_actual"   → "Inicia desde el comienzo del nivel actual"
      None / ""        → "No disponible"
    """
    if not raw:
        return "No disponible"

    raw = raw.strip()

    # Casos semánticos especiales
    _especiales = {
        "test_superior": "Avanza al test del siguiente nivel",
        "test_inferior": "Se recomienda aplicar el test del nivel anterior",
        "nivel_actual":  "Inicia desde el comienzo del nivel actual",
    }
    if raw in _especiales:
        return _especiales[raw]

    # Doble punto de partida (Inglés): "4A 1 / 4A 21"
    if "/" in raw:
        partes = [p.strip() for p in raw.split("/")]
        textos = [_parsear_starting_point(p) for p in partes]
        return "El orientador define entre: " + " o ".join(textos)

    # Patrón estándar: letras=nivel, números=hoja, letra_final=variante
    # Ejemplos: "O181a", "P4A", "7A 1", "4A 21"
    match = re.match(
        r"^([A-Za-z0-9]+?)\s*(\d+)\s*([a-z]?)$",
        raw
    )
    if match:
        nivel    = match.group(1).upper()
        hoja     = match.group(2)
        variante = match.group(3).lower()
        base = f"Nivel {nivel} — Hoja {hoja}"
        if variante:
            base += f" (variante {variante})"
        return base

    # Si no matchea ningún patrón, mostrar tal cual (mejor que romper)
    return raw


def _parsear_tiempo(estudio: Optional[float], objetivo: Optional[float]) -> str:
    """
    Convierte los minutos decimales en texto legible.
    Ejemplo: estudio=14.4, objetivo=12.0
      → "14 min 24 seg  (tiempo objetivo: 12 min)"
    """
    if estudio is None:
        return "No disponible"

    def _min_a_texto(minutos: float) -> str:
        mins  = int(minutos)
        segs  = round((minutos - mins) * 60)
        if segs == 0:
            return f"{mins} min"
        return f"{mins} min {segs} seg"

    texto = _min_a_texto(estudio)
    if objetivo is not None:
        texto += f"  (tiempo objetivo: {_min_a_texto(objetivo)})"
        if estudio > objetivo:
            texto += "  — tardó más del objetivo"
        else:
            texto += "  — dentro del tiempo"
    return texto


def _parsear_display_name(cuant: Dict[str, Any]) -> str:
    """
    Construye la cadena de nivel + WS legible para el encabezado.
    Ejemplo: display_name="Nivel P — Hoja 4", ws="P4A"
      → "Nivel P — Hoja 4  (WS: P4A)"
    """
    display = cuant.get("display_name") or ""
    ws      = cuant.get("ws") or ""
    if display and ws:
        return f"{display}  (WS: {ws})"
    return display or ws or "No disponible"


# ══════════════════════════════════════════════════════════════════
# [2] ESTILOS TIPOGRÁFICOS
# ══════════════════════════════════════════════════════════════════

def _build_styles() -> Dict[str, ParagraphStyle]:
    """
    Define todos los estilos de texto del PDF en un solo lugar.
    Para cambiar fuentes, tamaños o colores: editar solo este bloque.
    """
    return {
        # Título principal del boletín
        "titulo": ParagraphStyle(
            "titulo",
            fontSize=17, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL, alignment=TA_CENTER,
            spaceAfter=2,
        ),
        # Subtítulo debajo del título
        "subtitulo": ParagraphStyle(
            "subtitulo",
            fontSize=10, fontName="Helvetica",
            textColor=_COLOR_GRIS, alignment=TA_CENTER,
            spaceAfter=2,
        ),
        # Nombre del centro
        "centro": ParagraphStyle(
            "centro",
            fontSize=11, fontName="Helvetica-Bold",
            textColor=_COLOR_KUMON_ROJO, alignment=TA_CENTER,
            spaceAfter=4,
        ),
        # Título de cada sección
        "seccion": ParagraphStyle(
            "seccion",
            fontSize=12, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL, spaceBefore=4, spaceAfter=4,
        ),
        # Etiqueta de campo (columna izquierda de tablas)
        "campo_label": ParagraphStyle(
            "campo_label",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL,
        ),
        # Valor de campo (columna derecha de tablas)
        "campo_valor": ParagraphStyle(
            "campo_valor",
            fontSize=10, fontName="Helvetica",
            textColor=colors.black,
        ),
        # Texto de párrafos narrativos
        "narrativa": ParagraphStyle(
            "narrativa",
            fontSize=10, fontName="Helvetica",
            textColor=colors.black, leading=15, spaceAfter=4,
        ),
        # Pie de página — texto pequeño gris
        "pie": ParagraphStyle(
            "pie",
            fontSize=7.5, fontName="Helvetica",
            textColor=_COLOR_GRIS, alignment=TA_CENTER,
        ),
        # Pie de página — texto pequeño negrita
        "pie_negrita": ParagraphStyle(
            "pie_negrita",
            fontSize=7.5, fontName="Helvetica-Bold",
            textColor=_COLOR_AZUL, alignment=TA_CENTER,
        ),
    }


# ══════════════════════════════════════════════════════════════════
# [3] FUNCIÓN PRINCIPAL generate_pdf()
# ══════════════════════════════════════════════════════════════════

def generate_pdf(
    report_data:       Dict[str, Any],
    job_created_at:    datetime,
    prospecto_nombre:  str,
    output_path:       str,
    orientador_nombre: Optional[str] = None,
    hubo_correcciones: bool = False,
) -> Path:
    """
    Genera el PDF del boletín y lo guarda en output_path.

    Parámetros:
      report_data       → dict de build_report_data() (bloques: cuantitativo,
                          cualitativo, combinado, meta)
      job_created_at    → datetime del ProcessingJob (fecha del boletín)
      prospecto_nombre  → nombre del estudiante evaluado
      output_path       → ruta donde guardar el PDF (se crea si no existe)
      orientador_nombre → nombre del orientador (None si no disponible)
      hubo_correcciones → True si el orientador editó campos del boletín

    Retorna:
      Path del archivo PDF generado.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = _build_styles()
    story: List[Any] = []

    # Extraer los 3 bloques del report_data
    cuant = report_data.get("cuantitativo", {})
    cual  = report_data.get("cualitativo",  {})
    comb  = report_data.get("combinado",    {})

    # ── Sección 1: Encabezado con logo ───────────────────────────
    story += _seccion_encabezado(
        styles,
        prospecto_nombre=prospecto_nombre,
        job_created_at=job_created_at,
        cuant=cuant,
        orientador_nombre=orientador_nombre,
    )

    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=_COLOR_KUMON_ROJO))
    story.append(Spacer(1, 0.35 * cm))

    # ── Sección 2: Resultado cuantitativo ────────────────────────
    story += _seccion_cuantitativo(styles, cuant)

    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=_COLOR_BORDE))
    story.append(Spacer(1, 0.35 * cm))

    # ── Sección 3: Valoración cualitativa ────────────────────────
    story += _seccion_cualitativa(styles, cual)

    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=_COLOR_BORDE))
    story.append(Spacer(1, 0.35 * cm))

    # ── Sección 4: Puntuación global combinada ───────────────────
    if comb:
        story += _seccion_combinada(styles, comb)
        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                 color=_COLOR_BORDE))
        story.append(Spacer(1, 0.35 * cm))

    # ── Sección 5: Recomendación ─────────────────────────────────
    story += _seccion_recomendacion(styles, cuant, comb)

    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5,
                             color=_COLOR_KUMON_ROJO))
    story.append(Spacer(1, 0.3 * cm))

    # ── Sección 6: Pie de página ─────────────────────────────────
    story += _seccion_pie(styles, hubo_correcciones=hubo_correcciones)

    doc.build(story)
    logger.info("PDF generado: %s (%.1f KB)", path, path.stat().st_size / 1024)
    return path


# ══════════════════════════════════════════════════════════════════
# [4] SECCIÓN 1 — ENCABEZADO CON LOGO
# ══════════════════════════════════════════════════════════════════

def _seccion_encabezado(
    styles:            Dict,
    prospecto_nombre:  str,
    job_created_at:    datetime,
    cuant:             Dict[str, Any],
    orientador_nombre: Optional[str],
) -> list:
    """
    Encabezado del boletín.

    Muestra el logo de Kumon a la izquierda (si existe el archivo)
    y el título + nombre del centro a la derecha.
    Luego una tabla con los datos del estudiante.

    LOGO: coloca el archivo PNG en  backend/assets/logo_kumon.png
    Para cambiar el tamaño del logo edita _LOGO_ANCHO y _LOGO_ALTO.
    """
    _LOGO_ANCHO = 3.5 * cm   # ← cambia aquí el ancho del logo
    _LOGO_ALTO  = 2.0 * cm   # ← cambia aquí el alto del logo

    elementos = []

    # ── Logo + título lado a lado ─────────────────────────────────
    logo_path_abs = os.path.abspath(_LOGO_PATH)
    if os.path.exists(logo_path_abs):
        logo_img = Image(logo_path_abs, width=_LOGO_ANCHO, height=_LOGO_ALTO)
        logo_cell = logo_img
    else:
        # Sin logo: celda vacía con texto de aviso (solo para desarrollo)
        logo_cell = Paragraph(
            "<i>[logo_kumon.png no encontrado<br/>en backend/assets/]</i>",
            ParagraphStyle("aviso", fontSize=7, textColor=_COLOR_GRIS),
        )

    titulo_cell = [
        Paragraph("BOLETÍN DE DIAGNÓSTICO", styles["titulo"]),
        Paragraph(_NOMBRE_CENTRO, styles["centro"]),
        Paragraph("Prueba Diagnóstica — Resultado de Evaluación",
                  styles["subtitulo"]),
    ]

    encabezado_tabla = Table(
        [[logo_cell, titulo_cell]],
        colWidths=[4 * cm, 13 * cm],
    )
    encabezado_tabla.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (1, 0), (1, 0),   "CENTER"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elementos.append(encabezado_tabla)
    elementos.append(Spacer(1, 0.35 * cm))

    # ── Tabla de datos del estudiante ────────────────────────────
    fecha_str    = (job_created_at.strftime("%d de %B de %Y")
                    if job_created_at else "No disponible")
    materia_raw  = cuant.get("subject", "")
    materia_str  = materia_raw.capitalize() if materia_raw else "No disponible"
    nivel_str    = _parsear_display_name(cuant)

    filas = [
        ["Estudiante evaluado:", prospecto_nombre or "No disponible"],
        ["Fecha de evaluación:", fecha_str],
        ["Materia:",             materia_str],
        ["Nivel evaluado:",      nivel_str],
    ]
    if orientador_nombre:
        filas.append(["Orientador a cargo:", orientador_nombre])

    tabla = Table(filas, colWidths=[5 * cm, 12 * cm])
    tabla.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",     (0, 0), (0, -1), _COLOR_AZUL),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
    ]))
    elementos.append(tabla)
    return elementos


# ══════════════════════════════════════════════════════════════════
# [5] SECCIÓN 2 — RESULTADO CUANTITATIVO
# ══════════════════════════════════════════════════════════════════

def _seccion_cuantitativo(styles: Dict, cuant: Dict[str, Any]) -> list:
    """
    Muestra los resultados numéricos del test:
      - Aciertos y porcentaje
      - Tiempo de estudio vs. objetivo
      - Punto de partida (en texto legible para el padre)
      - Semáforo (bloque de color destacado)

    Para cambiar el texto del semáforo: editar _SEMAFORO_TEXTO en [0].
    Para cambiar los colores del semáforo: editar _SEMAFORO_COLOR en [0].
    """
    elementos = []
    elementos.append(Paragraph("Resultado Cuantitativo", styles["seccion"]))

    # ── Construir textos legibles ─────────────────────────────────
    correctas = cuant.get("correct_answers")
    total     = cuant.get("total_questions")
    pct       = cuant.get("percentage")

    if correctas is not None and total is not None:
        pct_val   = float(pct) if pct is not None else round(correctas / total * 100, 1)
        score_str = f"{correctas} correctas de {total}  ({pct_val:.1f}%)"
    else:
        score_str = "No disponible"

    tiempo_str = _parsear_tiempo(
        cuant.get("study_time_min"),
        cuant.get("target_time_min"),
    )

    starting_str = _parsear_starting_point(cuant.get("starting_point"))

    # ── Tabla de indicadores ──────────────────────────────────────
    filas = [
        [Paragraph("<b>Indicador</b>",           styles["campo_label"]),
         Paragraph("<b>Resultado</b>",            styles["campo_label"])],
        ["Respuestas correctas",  score_str],
        ["Tiempo de estudio",     tiempo_str],
        ["Punto de partida",      starting_str],
    ]

    tabla = Table(filas, colWidths=[6.5 * cm, 10.5 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  _COLOR_AZUL),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  _COLOR_BLANCO),
        ("FONTNAME",       (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",       (1, 1), (1, -1),  "Helvetica"),
        ("FONTSIZE",       (0, 0), (-1, -1), 10),
        ("GRID",           (0, 0), (-1, -1), 0.5, _COLOR_BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_COLOR_GRIS_CLARO, _COLOR_BLANCO]),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",     (0, 0), (-1, -1), 6),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 0.3 * cm))

    # ── Bloque semáforo ───────────────────────────────────────────
    semaforo     = (cuant.get("semaforo") or "").strip().lower()
    semaforo_col = _SEMAFORO_COLOR.get(semaforo, _COLOR_GRIS)
    semaforo_txt = _SEMAFORO_TEXTO.get(semaforo, "Sin clasificación automática")

    bloque_semaforo = Table(
        [[semaforo_txt]],
        colWidths=[17 * cm],
    )
    bloque_semaforo.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), semaforo_col),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 11),
        ("TEXTCOLOR",     (0, 0), (-1, -1), _COLOR_BLANCO),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    elementos.append(bloque_semaforo)

    # ── Nota si requiere revisión manual ─────────────────────────
    if cuant.get("needs_manual_review"):
        elementos.append(Spacer(1, 0.2 * cm))
        razones = cuant.get("review_reasons") or []
        nota = "⚠ Este resultado requiere revisión del orientador."
        if razones:
            nota += "  Motivo: " + razones[0]
        elementos.append(Paragraph(nota, ParagraphStyle(
            "aviso_rev", fontSize=8.5, fontName="Helvetica",
            textColor=colors.HexColor("#92400E"),
            backColor=colors.HexColor("#FFFBEB"),
        )))

    return elementos


# ══════════════════════════════════════════════════════════════════
# [6] SECCIÓN 3 — VALORACIÓN CUALITATIVA
# ══════════════════════════════════════════════════════════════════

def _seccion_cualitativa(styles: Dict, cual: Dict[str, Any]) -> list:
    """
    Muestra las áreas de actitud y comportamiento evaluadas por
    el orientador durante la sesión de diagnóstico.

    Soporta hasta 6 secciones (ejes del cuestionario).
    Columnas: Área evaluada | Nivel | Puntaje | Fuente

    Para cambiar las etiquetas: editar _ETIQUETA_LABEL en [0].
    Para cambiar los colores: editar _ETIQUETA_COLOR en [0].
    """
    elementos = []
    elementos.append(Paragraph("Valoración Cualitativa", styles["seccion"]))

    secciones  = cual.get("secciones") or []
    auto_flags = [f.lower() for f in (cual.get("auto_flags") or [])]
    etiqueta   = cual.get("etiqueta_total") or ""
    pct_total  = cual.get("total_porcentaje")

    # ── Resumen global cualitativo ────────────────────────────────
    if pct_total is not None and etiqueta:
        etiq_label = _ETIQUETA_LABEL.get(etiqueta, etiqueta)
        etiq_color = _ETIQUETA_COLOR.get(etiqueta, _COLOR_GRIS_CLARO)
        resumen = Table(
            [[f"Nivel general de actitud: {etiq_label}  ({pct_total:.1f}%)"]],
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

    # ── Tabla de métricas por área ────────────────────────────────
    if secciones:
        filas_tabla = [
            [Paragraph("<b>Área evaluada</b>",  styles["campo_label"]),
             Paragraph("<b>Nivel</b>",           styles["campo_label"]),
             Paragraph("<b>Puntaje</b>",         styles["campo_label"]),
             Paragraph("<b>Evaluado por</b>",    styles["campo_label"])],
        ]
        estilos_din: List[tuple] = []

        for i, sec in enumerate(secciones, start=1):
            nombre   = sec.get("nombre") or sec.get("name") or f"Área {i}"
            etiq_s   = sec.get("etiqueta") or ""
            pct_s    = sec.get("porcentaje") or sec.get("puntaje")
            es_auto  = nombre.lower() in auto_flags
            fuente   = "Automático" if es_auto else "Orientador"
            label_s  = _ETIQUETA_LABEL.get(etiq_s, etiq_s)
            col_s    = _ETIQUETA_COLOR.get(etiq_s, _COLOR_BLANCO)
            pct_txt  = f"{pct_s:.1f}%" if pct_s is not None else "—"

            filas_tabla.append([nombre, label_s, pct_txt, fuente])
            estilos_din.append(("BACKGROUND", (1, i), (1, i), col_s))
            if i % 2 == 0:
                estilos_din.append(
                    ("BACKGROUND", (0, i), (0, i), _COLOR_GRIS_CLARO)
                )

        tabla_cual = Table(
            filas_tabla,
            colWidths=[6.5 * cm, 5 * cm, 2.5 * cm, 3 * cm],
        )
        estilo_base = [
            ("BACKGROUND",    (0, 0), (-1, 0), _COLOR_AZUL),
            ("TEXTCOLOR",     (0, 0), (-1, 0), _COLOR_BLANCO),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.5, _COLOR_BORDE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]
        tabla_cual.setStyle(TableStyle(estilo_base + estilos_din))
        elementos.append(tabla_cual)
    else:
        elementos.append(Paragraph(
            "No se registraron métricas de actitud en esta evaluación.",
            styles["narrativa"],
        ))

    return elementos


# ══════════════════════════════════════════════════════════════════
# [7] SECCIÓN 4 — PUNTUACIÓN GLOBAL COMBINADA
# ══════════════════════════════════════════════════════════════════

def _seccion_combinada(styles: Dict, comb: Dict[str, Any]) -> list:
    """
    Muestra la puntuación global que combina lo cuantitativo (65%)
    y lo cualitativo (35%) en un único indicador.

    Este bloque viene del campo 'combinado' de report_data.
    Si el backend no entrega este bloque, la sección no aparece.
    """
    elementos = []
    elementos.append(Paragraph("Puntuación Global del Diagnóstico", styles["seccion"]))

    puntaje  = comb.get("puntaje")
    etiqueta = comb.get("etiqueta") or ""
    narrativa = comb.get("narrativa") or ""
    kpi       = comb.get("kpi") or {}

    # ── Barra de puntuación global ────────────────────────────────
    if puntaje is not None:
        etiq_label = _ETIQUETA_LABEL.get(etiqueta, etiqueta)
        etiq_color = _ETIQUETA_COLOR.get(etiqueta, _COLOR_GRIS_CLARO)

        puntaje_cuant = kpi.get("cuantitativo", {}).get("puntaje")
        puntaje_cual  = kpi.get("cualitativo",  {}).get("puntaje")

        desglose = ""
        if puntaje_cuant is not None and puntaje_cual is not None:
            desglose = (
                f"  (Cuantitativo: {puntaje_cuant:.1f}/100 × 65%"
                f"  +  Actitud: {puntaje_cual:.1f}/100 × 35%)"
            )

        bloque_comb = Table(
            [[f"Puntuación global: {float(puntaje):.1f} / 100  —  {etiq_label}{desglose}"]],
            colWidths=[17 * cm],
        )
        bloque_comb.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), etiq_color),
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        elementos.append(bloque_comb)

    # ── Narrativa explicativa ─────────────────────────────────────
    if narrativa:
        elementos.append(Spacer(1, 0.25 * cm))
        elementos.append(Paragraph(narrativa, styles["narrativa"]))

    return elementos


# ══════════════════════════════════════════════════════════════════
# [8] SECCIÓN 5 — RECOMENDACIÓN
# ══════════════════════════════════════════════════════════════════

def _seccion_recomendacion(
    styles: Dict,
    cuant:  Dict[str, Any],
    comb:   Dict[str, Any],
) -> list:
    """
    Muestra la recomendación pedagógica para el padre de familia.

    Fuentes (en orden de prioridad):
      1. cuant['recommendation']  → recomendación del calculador de semáforo
      2. comb['narrativa']        → conclusión global combinada
    Si ninguna está disponible, muestra mensaje de completar manualmente.
    """
    elementos = []
    elementos.append(Paragraph("Recomendación para la Familia", styles["seccion"]))

    rec_cuant    = (cuant.get("recommendation") or "").strip()
    narrativa    = (comb.get("narrativa")        or "").strip()

    if rec_cuant:
        elementos.append(Paragraph(rec_cuant, styles["narrativa"]))

    if narrativa and narrativa != rec_cuant:
        elementos.append(Paragraph(narrativa, styles["narrativa"]))

    if not rec_cuant and not narrativa:
        elementos.append(Paragraph(
            "El orientador debe completar la recomendación de forma manual "
            "según el desempeño observado durante la evaluación.",
            styles["narrativa"],
        ))

    return elementos


# ══════════════════════════════════════════════════════════════════
# [9] SECCIÓN 6 — PIE DE PÁGINA
# ══════════════════════════════════════════════════════════════════

def _seccion_pie(styles: Dict, hubo_correcciones: bool) -> list:
    """
    Pie de página con fecha de emisión y estado de validación.

    hubo_correcciones=True  → "Validado por el orientador"
    hubo_correcciones=False → "Pendiente de validación"

    También muestra el nombre del centro (_NOMBRE_CENTRO).
    """
    elementos = []
    ahora = datetime.now().strftime("%d/%m/%Y  %H:%M")

    elementos.append(Paragraph(
        f"Fecha de emisión: {ahora}",
        styles["pie"],
    ))

    if hubo_correcciones:
        elementos.append(Paragraph(
            "✔ Revisado y validado por el orientador",
            styles["pie_negrita"],
        ))
    else:
        elementos.append(Paragraph(
            "Generado automáticamente — pendiente de validación por el orientador",
            styles["pie"],
        ))

    elementos.append(Paragraph(
        f"Sistema de Diagnóstico Interno — {_NOMBRE_CENTRO}",
        styles["pie"],
    ))
    return elementos