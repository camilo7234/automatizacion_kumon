"""
app/services/pdf_generator.py
══════════════════════════════════════════════════════════════════
BOLETÍN DE DIAGNÓSTICO KUMON — IPIALES
Versión 3.0 — Auditoría 100% datos backend · Estilo Kumon Azul

BLOQUES:
  [0]  Importaciones y constantes
  [1]  Paleta de colores y estilos tipográficos
  [2]  Helpers de parseo (starting_point, tiempo, display_name)
  [3]  Componentes visuales reutilizables (barra, badge, tabla estilo)
  [4]  Gráfica de barras horizontales (Chart cualitativo)
  [5]  Gráfica de donut / arco de puntaje combinado
  [6]  Función principal generate_pdf()
  [7]  Sección 1 — Encabezado con logo y datos del estudiante
  [8]  Sección 2 — Resultado cuantitativo (score, tiempo, semáforo)
  [9]  Sección 3 — Prefills automáticos (video/audio/cámara)
  [10] Sección 4 — Valoración cualitativa por áreas
  [11] Sección 5 — Gráfica de actitud por sección
  [12] Sección 6 — Puntuación global combinada 65/35 + arco
  [13] Sección 7 — Recomendación y punto de partida
  [14] Sección 8 — Pie de página
══════════════════════════════════════════════════════════════════
"""

# ══════════════════════════════════════════════════════════════════
# [0] IMPORTACIONES Y CONSTANTES
# ══════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from reportlab.graphics import renderPDF
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, Arc, String, Circle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)

logger = logging.getLogger(__name__)

# ── Rutas de assets ───────────────────────────────────────────────
_ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
_LOGO_PATH  = _ASSETS_DIR / "logo_kumon.png"

# ── Nombre fijo del centro ────────────────────────────────────────
_NOMBRE_CENTRO = "Kumon Ipiales"

# ── Ancho útil del PDF (A4 con márgenes 2cm c/lado) ──────────────
_PAGE_W = A4[0] - 4 * cm   # ≈ 17 cm

# ── Colores matplotlib para gráficas de secciones cualitativas ───
_ETIQ_MPL_BG: Dict[str, str] = {
    "fortaleza":     "#22C55E",
    "en_desarrollo": "#3B82F6",
    "refuerzo":      "#F59E0B",
    "atencion":      "#EF4444",
}

# ══════════════════════════════════════════════════════════════════
# [1] PALETA DE COLORES Y ESTILOS TIPOGRÁFICOS
#     Filosofía: azul corporativo Kumon como color primario,
#     rojo Kumon solo para detalles de marca (logo, líneas).
#     Los colores de semáforo y etiqueta se mantienen semánticos.
# ══════════════════════════════════════════════════════════════════

# ── Marca Kumon ───────────────────────────────────────────────────
_KUMON_ROJO   = colors.HexColor("#E3001B")   # rojo corporativo (solo marca)
_KUMON_AZUL   = colors.HexColor("#003087")   # azul oscuro primario
_KUMON_AZUL_M = colors.HexColor("#0050A0")   # azul medio (cabeceras)
_KUMON_AZUL_L = colors.HexColor("#E8F0FB")   # azul muy claro (fondos)
_KUMON_AZUL_2 = colors.HexColor("#1A6BB5")   # azul botones / badges

# ── Neutros ───────────────────────────────────────────────────────
_GRIS_TXT   = colors.HexColor("#4B5563")   # texto secundario
_GRIS_CLARO = colors.HexColor("#F1F5F9")   # fondo alterno filas
_BORDE      = colors.HexColor("#CBD5E1")   # bordes tabla
_BLANCO     = colors.white
_NEGRO      = colors.black

# ── Semáforo (cuantitativo) ───────────────────────────────────────
_SEM_COLOR: Dict[str, Any] = {
    "verde":    colors.HexColor("#16A34A"),
    "amarillo": colors.HexColor("#D97706"),
    "rojo":     colors.HexColor("#DC2626"),
}
_SEM_TEXTO: Dict[str, str] = {
    "verde":    "[OK]  Puede avanzar al siguiente nivel",
    "amarillo": "[!!]  Debe consolidar antes de avanzar",
    "rojo":     "[XX]  Requiere refuerzo en este nivel",
}

# ── Etiquetas cualitativas ────────────────────────────────────────
_ETIQ_BG: Dict[str, Any] = {
    "fortaleza":     colors.HexColor("#DCFCE7"),
    "en_desarrollo": colors.HexColor("#DBEAFE"),
    "refuerzo":      colors.HexColor("#FEF9C3"),
    "atencion":      colors.HexColor("#FEE2E2"),
}
_ETIQ_FG: Dict[str, Any] = {
    "fortaleza":     colors.HexColor("#166534"),
    "en_desarrollo": colors.HexColor("#1E40AF"),
    "refuerzo":      colors.HexColor("#92400E"),
    "atencion":      colors.HexColor("#991B1B"),
}
_ETIQ_LABEL: Dict[str, str] = {
    "fortaleza":     "Fortaleza",
    "en_desarrollo": "En desarrollo",
    "refuerzo":      "Necesita refuerzo",
    "atencion":      "Requiere atencion especial",
}

# ── Fuente de cada prefill automático ────────────────────────────
# Nota: emojis eliminados — no están garantizados en Helvetica/Linux.
_FUENTE_ICONO: Dict[str, str] = {
    "video":  "[Video]",
    "audio":  "[Audio]",
    "camara": "[Camara]",
}


def _build_styles() -> Dict[str, ParagraphStyle]:
    """
    Define todos los estilos tipográficos del PDF en un único lugar.
    Modificar tipografía / tamaños: solo editar este bloque.
    """
    return {
        # ── Encabezado ────────────────────────────────────────────
        "titulo": ParagraphStyle(
            "titulo", fontSize=16, fontName="Helvetica-Bold",
            textColor=_KUMON_AZUL, alignment=TA_CENTER, spaceAfter=2,
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", fontSize=9, fontName="Helvetica",
            textColor=_GRIS_TXT, alignment=TA_CENTER, spaceAfter=2,
        ),
        "centro": ParagraphStyle(
            "centro", fontSize=11, fontName="Helvetica-Bold",
            textColor=_KUMON_ROJO, alignment=TA_CENTER, spaceAfter=3,
        ),
        # ── Secciones ─────────────────────────────────────────────
        "seccion": ParagraphStyle(
            "seccion", fontSize=11, fontName="Helvetica-Bold",
            textColor=_KUMON_AZUL, spaceBefore=6, spaceAfter=4,
        ),
        "subseccion": ParagraphStyle(
            "subseccion", fontSize=9.5, fontName="Helvetica-Bold",
            textColor=_KUMON_AZUL_M, spaceBefore=3, spaceAfter=2,
        ),
        # ── Tablas ────────────────────────────────────────────────
        "campo_label": ParagraphStyle(
            "campo_label", fontSize=8.5, fontName="Helvetica-Bold",
            textColor=_KUMON_AZUL,
        ),
        "campo_valor": ParagraphStyle(
            "campo_valor", fontSize=9.5, fontName="Helvetica",
            textColor=_NEGRO,
        ),
        # ── Narrativa / párrafo ───────────────────────────────────
        "narrativa": ParagraphStyle(
            "narrativa", fontSize=9.5, fontName="Helvetica",
            textColor=_NEGRO, leading=14, spaceAfter=4,
        ),
        "narrativa_azul": ParagraphStyle(
            "narrativa_azul", fontSize=9.5, fontName="Helvetica",
            textColor=_KUMON_AZUL, leading=14, spaceAfter=4,
        ),
        # ── Badge / chips ─────────────────────────────────────────
        "badge": ParagraphStyle(
            "badge", fontSize=8, fontName="Helvetica-Bold",
            textColor=_BLANCO, alignment=TA_CENTER,
        ),
        # ── Notas y avisos ────────────────────────────────────────
        "aviso": ParagraphStyle(
            "aviso", fontSize=8, fontName="Helvetica",
            textColor=colors.HexColor("#92400E"),
            backColor=colors.HexColor("#FFFBEB"),
        ),
        "aviso_info": ParagraphStyle(
            "aviso_info", fontSize=8, fontName="Helvetica",
            textColor=_KUMON_AZUL,
            backColor=_KUMON_AZUL_L,
        ),
        # ── Pie ───────────────────────────────────────────────────
        "pie": ParagraphStyle(
            "pie", fontSize=7, fontName="Helvetica",
            textColor=_GRIS_TXT, alignment=TA_CENTER,
        ),
        "pie_negrita": ParagraphStyle(
            "pie_negrita", fontSize=7, fontName="Helvetica-Bold",
            textColor=_KUMON_AZUL, alignment=TA_CENTER,
        ),
    }

# ══════════════════════════════════════════════════════════════════
# [2] HELPERS DE PARSEO
# ══════════════════════════════════════════════════════════════════

def _parsear_starting_point(raw: Optional[str]) -> str:
    """
    Convierte el valor técnico del backend en texto legible.
    Cubre: códigos semánticos, doble punto de partida y patrón estándar
    nivel+hoja+variante (ej. 'O181a' → 'Nivel O — Hoja 181 (variante a)').
    """
    if not raw:
        return "No disponible"
    raw = raw.strip()
    _especiales = {
        "test_superior": "Avanza al test del siguiente nivel",
        "test_inferior": "Se recomienda aplicar el test del nivel anterior",
        "nivel_actual":  "Inicia desde el comienzo del nivel actual",
    }
    if raw in _especiales:
        return _especiales[raw]
    if "/" in raw:
        partes = [p.strip() for p in raw.split("/")]
        textos = [_parsear_starting_point(p) for p in partes]
        return "El orientador define entre: " + " o ".join(textos)
    match = re.match(r"^([A-Za-z0-9]+?)\s*(\d+)\s*([a-z]?)$", raw)
    if match:
        nivel    = match.group(1).upper()
        hoja     = match.group(2)
        variante = match.group(3)
        base = f"Nivel {nivel} — Hoja {hoja}"
        if variante:
            base += f" (variante {variante})"
        return base
    return raw


def _parsear_tiempo(estudio: Optional[float], objetivo: Optional[float]) -> str:
    """
    Convierte minutos decimales en texto legible.
    Ej: estudio=14.4, objetivo=12.0 → '14 min 24 seg  (objetivo: 12 min) — tardó más'
    """
    if estudio is None:
        return "No disponible"

    # Guard: tiempo 0 es dato no capturado, no tiempo real de trabajo
    if estudio == 0.0:
        return "No registrado (tiempo en 0)"

    def _fmt(minutos: float) -> str:
        mins = int(minutos)
        segs = round((minutos - mins) * 60)
        return f"{mins} min {segs} seg" if segs else f"{mins} min"

    txt = _fmt(estudio)
    if objetivo is not None:
        txt += f"  (objetivo: {_fmt(objetivo)})"
        txt += "  — dentro del tiempo" if estudio <= objetivo else "  — tardó mas del objetivo"
    return txt


def _parsear_display_name(cuant: Dict[str, Any]) -> str:
    """Combina display_name y ws en un string legible para el encabezado."""
    display = cuant.get("display_name") or ""
    ws      = cuant.get("ws") or ""
    if display and ws:
        return f"{display}  (WS: {ws})"
    return display or ws or "No disponible"


def _label_fuente(prefill_item: Dict[str, Any]) -> str:
    """Retorna texto con fuente e icono para la tabla de prefills."""
    fuente = prefill_item.get("fuente", "")
    conf   = prefill_item.get("confianza")
    icono  = _FUENTE_ICONO.get(fuente, "[Auto]")   # fallback ASCII, no emoji/Unicode
    try:
        conf_txt = f" ({float(conf)*100:.0f}%)" if conf is not None else ""
    except (TypeError, ValueError):
        conf_txt = ""
    return f"{icono} {fuente.capitalize()}{conf_txt}"

# ══════════════════════════════════════════════════════════════════
# [3] COMPONENTES VISUALES REUTILIZABLES
# ══════════════════════════════════════════════════════════════════

def _tabla_base_style(
    n_rows: int,
    header_color=None,
    alternate: bool = True,
) -> TableStyle:
    """
    Retorna un TableStyle azul estandar Kumon reutilizable.
    header_color: color de la fila 0; por defecto _KUMON_AZUL_M.
    """
    hc = header_color or _KUMON_AZUL_M
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, 0),  hc),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  _BLANCO),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.4, _BORDE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]
    if alternate:
        for i in range(1, n_rows):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), _GRIS_CLARO))
    return TableStyle(cmds)


def _bloque_color(
    texto: str,
    bg: Any,
    fg: Any = None,
    ancho: Optional[float] = None,   # corregido: Optional[float] en vez de float = None
    font_size: int = 10,
    bold: bool = True,
) -> Table:
    """
    Crea un bloque de una celda con fondo de color (semaforo, etiqueta...).
    Sirve tanto para semaforo cuantitativo como para badge cualitativo.
    """
    fg    = fg or _BLANCO
    ancho = ancho or _PAGE_W
    fn    = "Helvetica-Bold" if bold else "Helvetica"
    bloque = Table([[texto]], colWidths=[ancho])
    bloque.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("FONTNAME",      (0, 0), (-1, -1), fn),
        ("FONTSIZE",      (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR",     (0, 0), (-1, -1), fg),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        # "ROUNDEDCORNERS" eliminado — no existe en ReportLab TableStyle
    ]))
    return bloque


def _barra_progreso_rl(
    pct: float,
    width: float = 10 * cm,
    height: float = 0.45 * cm,
    color_barra: Any = None,
    color_fondo: Any = None,
) -> Table:
    """
    Barra de progreso horizontal usando celdas de ReportLab.
    pct: 0.0-100.0
    Devuelve una Table de una fila con dos celdas (rellena + vacia).
    """
    color_barra = color_barra or _KUMON_AZUL_2
    color_fondo = color_fondo or _KUMON_AZUL_L
    pct_clamp   = max(0.0, min(100.0, float(pct)))
    filled_w    = width * pct_clamp / 100.0

    # Garantizar ancho mínimo para no romper Table con colWidth=0
    filled_w = max(filled_w, 1.0)
    empty_w  = max(width - filled_w, 0.0)

    if empty_w > 0:
        cols = [filled_w, empty_w]
        data = [["", ""]]
        cmds = [
            ("BACKGROUND", (0, 0), (0, 0), color_barra),
            ("BACKGROUND", (1, 0), (1, 0), color_fondo),
        ]
    else:
        # pct == 100%: una sola celda rellena
        cols = [width]
        data = [[""]]
        cmds = [
            ("BACKGROUND", (0, 0), (0, 0), color_barra),
        ]

    cmds += [
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOX",           (0, 0), (-1, -1), 0.3, _BORDE),
    ]

    tbl = Table(data, colWidths=cols, rowHeights=[height])
    tbl.setStyle(TableStyle(cmds))
    return tbl

# ══════════════════════════════════════════════════════════════════
# [4] GRÁFICA DE BARRAS HORIZONTALES — ACTITUD POR SECCIÓN
#     Usa matplotlib → genera PNG en memoria → Image de ReportLab.
#     Paleta: colores por etiqueta cualitativa (_ETIQ_MPL_BG).
# ══════════════════════════════════════════════════════════════════

def _grafica_barras_secciones(
    secciones: List[Dict[str, Any]],
    ancho_cm: float = 15,
    alto_cm: float  = None,
) -> Optional[Image]:
    """
    Gráfica de barras horizontales con el puntaje de cada sección
    cualitativa evaluada por el orientador.

    Retorna un objeto Image de ReportLab o None si no hay datos.
    """
    if not secciones:
        return None

    nombres  = []
    puntajes = []
    colores  = []

    for sec in secciones:
        nombre = sec.get("nombre") or sec.get("name") or "Área"
        pct    = sec.get("porcentaje") or sec.get("puntaje") or 0.0
        etiq   = sec.get("etiqueta") or "en_desarrollo"
        nombres.append(nombre)
        puntajes.append(float(pct))
        colores.append(_ETIQ_MPL_BG.get(etiq, "#3B82F6"))

    n      = len(nombres)
    alto_i = alto_cm or max(3.5, n * 0.75 + 1.5)

    fig, ax = plt.subplots(figsize=(ancho_cm / 2.54, alto_i / 2.54))

    # Barras horizontales
    y_pos = np.arange(n)
    bars  = ax.barh(y_pos, puntajes, color=colores, height=0.55,
                    edgecolor="white", linewidth=0.5)

    # Etiquetas de valor dentro / fuera de la barra
    for bar, val in zip(bars, puntajes):
        x_txt = val - 4 if val > 15 else val + 1.5
        color_txt = "white" if val > 15 else "#1E293B"
        ha        = "right"  if val > 15 else "left"
        ax.text(x_txt, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%", va="center", ha=ha,
                fontsize=7.5, color=color_txt, fontweight="bold")

    # Línea de referencia 100%
    ax.axvline(x=100, color="#E2E8F0", linewidth=0.8, linestyle="--")

    # Configuración de ejes
    ax.set_yticks(y_pos)
    ax.set_yticklabels(nombres, fontsize=8, color="#1E3A5F")
    ax.set_xlim(0, 110)
    ax.set_xlabel("Puntaje (%)", fontsize=7.5, color="#475569")
    ax.set_title("Desempeño por área evaluada", fontsize=9,
                 color="#003087", fontweight="bold", pad=8)

    # Fondo y bordes
    ax.set_facecolor("#F8FAFC")
    fig.patch.set_facecolor("#FFFFFF")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E2E8F0")
    ax.spines["bottom"].set_color("#E2E8F0")
    ax.tick_params(axis="x", colors="#64748B", labelsize=7)
    ax.tick_params(axis="y", colors="#1E3A5F")
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.5, linestyle="-")

    # Leyenda de etiquetas
    leyenda = [
        mpatches.Patch(color=_ETIQ_MPL_BG["fortaleza"],     label="Fortaleza"),
        mpatches.Patch(color=_ETIQ_MPL_BG["en_desarrollo"], label="En desarrollo"),
        mpatches.Patch(color=_ETIQ_MPL_BG["refuerzo"],      label="Necesita refuerzo"),
        mpatches.Patch(color=_ETIQ_MPL_BG["atencion"],      label="Requiere atención"),
    ]
    ax.legend(handles=leyenda, loc="lower right", fontsize=6.5,
              framealpha=0.8, edgecolor="#CBD5E1")

    plt.tight_layout(pad=0.6)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight",
                facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_cm * cm, height=alto_i * cm)


# ══════════════════════════════════════════════════════════════════
# [5] GRÁFICA DE ARCO — PUNTAJE GLOBAL COMBINADO
#     Semicírculo tipo velocímetro con aguja que apunta al puntaje.
#     Zonas coloreadas: 0-25 rojo, 26-50 naranja, 51-75 azul, 76-100 verde.
# ══════════════════════════════════════════════════════════════════

def _grafica_arco_combinado(
    puntaje: float,
    etiqueta: Optional[str],
    ancho_cm: float = 8,
    alto_cm: float  = 5,
) -> Optional[Image]:
    """
    Genera un medidor semicircular (gauge) para el puntaje combinado 0-100.
    Retorna Image de ReportLab o None si puntaje es None.
    """
    if puntaje is None:
        return None

    fig, ax = plt.subplots(figsize=(ancho_cm / 2.54, alto_cm / 2.54),
                           subplot_kw={"aspect": "equal"})

    # ── Zonas de color (semicírculo inferior = 180° a 0°) ────────
    zonas = [
        (0,  25,  "#EF4444"),   # atención — rojo
        (25, 50,  "#F97316"),   # refuerzo — naranja
        (50, 76,  "#3B82F6"),   # en desarrollo — azul
        (76, 100, "#22C55E"),   # fortaleza — verde
    ]
    for inicio, fin, color in zonas:
        theta1 = 180 - (inicio / 100) * 180
        theta2 = 180 - (fin  / 100) * 180
        wedge  = mpatches.Wedge(
            center=(0, 0), r=1.0,
            theta1=theta2, theta2=theta1,
            width=0.35, facecolor=color, alpha=0.85, edgecolor="white",
            linewidth=0.8
        )
        ax.add_patch(wedge)

    # ── Aguja ────────────────────────────────────────────────────
    angle_rad = math.radians(180 - (puntaje / 100) * 180)
    needle_x  = 0.72 * math.cos(angle_rad)
    needle_y  = 0.72 * math.sin(angle_rad)
    ax.annotate("", xy=(needle_x, needle_y), xytext=(0, 0),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color="#1E293B",
                    lw=1.5,
                    mutation_scale=10,
                ))

    # Punto central de la aguja
    circle = plt.Circle((0, 0), 0.06, color="#1E293B", zorder=5)
    ax.add_patch(circle)

    # ── Texto central ─────────────────────────────────────────────
    ax.text(0, -0.22, f"{puntaje:.0f}", ha="center", va="center",
            fontsize=15, fontweight="bold", color="#003087")
    etiq_lbl = _ETIQ_LABEL.get(etiqueta or "", "")
    ax.text(0, -0.42, etiq_lbl, ha="center", va="center",
            fontsize=6.5, color="#475569")

    # ── Etiquetas de rango ────────────────────────────────────────
    ax.text(-1.1,  0.05, "0",   ha="center", fontsize=6, color="#64748B")
    ax.text( 0,    1.12, "50",  ha="center", fontsize=6, color="#64748B")
    ax.text( 1.1,  0.05, "100", ha="center", fontsize=6, color="#64748B")

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.55, 1.35)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")
    plt.tight_layout(pad=0.2)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight",
                facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_cm * cm, height=alto_cm * cm)


# ══════════════════════════════════════════════════════════════════
# [6] FUNCIÓN PRINCIPAL generate_pdf()
# ══════════════════════════════════════════════════════════════════

def generate_pdf(
    report_data:       Dict[str, Any],
    job_created_at:    datetime,
    prospecto_nombre:  str,
    output_path:       Optional[str] = None,
    orientador_nombre: Optional[str] = None,
    hubo_correcciones: bool = False,
) -> "Path | io.BytesIO":
    """
    Genera el PDF del boletín completo.

    Parámetros
    ----------
    report_data       : dict de build_report_data() con claves:
                        cuantitativo, cualitativo, combinado, gaze
    job_created_at    : datetime del ProcessingJob (fecha del boletín)
    prospecto_nombre  : nombre del estudiante evaluado
    output_path       : ruta donde guardar el PDF.
                        Si es None (por defecto), retorna io.BytesIO
                        listo para StreamingResponse sin tocar disco.
    orientador_nombre : nombre del orientador (None si no disponible)
    hubo_correcciones : True si el orientador editó campos

    Retorna
    -------
    - io.BytesIO  si output_path es None  → usar para StreamingResponse
    - Path        si output_path se indica → compatible con uso en disco
    """
    # ── Destino: buffer en memoria o archivo en disco ─────────────
    if output_path is None:
        target: "str | io.BytesIO" = io.BytesIO()
    else:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        target = str(path)

    doc = SimpleDocTemplate(
        target,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = _build_styles()
    story: List[Any] = []

    # Extraer bloques del report_data
    cuant = report_data.get("cuantitativo", {})
    cual  = report_data.get("cualitativo",  {})
    comb  = report_data.get("combinado",    {})
    gaze  = report_data.get("gaze")

    # ── [7] Encabezado ────────────────────────────────────────────
    story += _seccion_encabezado(
        styles, prospecto_nombre, job_created_at,
        cuant, orientador_nombre,
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=_KUMON_ROJO))
    story.append(Spacer(1, 0.3 * cm))

    # ── [8] Resultado cuantitativo ────────────────────────────────
    story += _seccion_cuantitativo(styles, cuant)
    story.append(Spacer(1, 0.35 * cm))
    story.append(HRFlowable(width="100%", thickness=0.4, color=_BORDE))
    story.append(Spacer(1, 0.3 * cm))

    # ── [9] Prefills automáticos (video / audio / cámara) ─────────
    prefills   = cual.get("prefills")   or {}
    auto_flags = cual.get("auto_flags") or []
    if prefills:
        story += _seccion_prefills(styles, prefills, auto_flags)
        story.append(Spacer(1, 0.35 * cm))
        story.append(HRFlowable(width="100%", thickness=0.4, color=_BORDE))
        story.append(Spacer(1, 0.3 * cm))

    # ── [10] Valoración cualitativa ───────────────────────────────
    story += _seccion_cualitativa(styles, cual)
    story.append(Spacer(1, 0.35 * cm))

    # ── [11] Gráfica de actitud ───────────────────────────────────
    secciones = cual.get("secciones") or []
    if secciones:
        story += _seccion_grafica_cualitativa(styles, secciones)
        story.append(Spacer(1, 0.35 * cm))
        story.append(HRFlowable(width="100%", thickness=0.4, color=_BORDE))
        story.append(Spacer(1, 0.3 * cm))

    # ── [12] Puntuación global combinada 65/35 ────────────────────
    if comb:
        story += _seccion_combinada(styles, comb)
        story.append(Spacer(1, 0.35 * cm))
        story.append(HRFlowable(width="100%", thickness=0.4, color=_BORDE))
        story.append(Spacer(1, 0.3 * cm))

    # ── Gaze (reservado cámara frontal) ───────────────────────────
    if gaze:
        story += _seccion_gaze(styles, gaze)
        story.append(Spacer(1, 0.35 * cm))
        story.append(HRFlowable(width="100%", thickness=0.4, color=_BORDE))
        story.append(Spacer(1, 0.3 * cm))

    # ── [13] Recomendación y punto de partida ─────────────────────
    story += _seccion_recomendacion(styles, cuant, comb)
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=_KUMON_ROJO))
    story.append(Spacer(1, 0.3 * cm))

    # ── [14] Pie de página ────────────────────────────────────────
    story += _seccion_pie(styles, hubo_correcciones=hubo_correcciones)

    doc.build(story)

    # ── Retornar según modo ───────────────────────────────────────
    if output_path is None:
        target.seek(0)
        logger.info("PDF generado en memoria (%.1f KB)", target.getbuffer().nbytes / 1024)
        return target
    else:
        logger.info("PDF guardado en disco: %s (%.1f KB)", path, path.stat().st_size / 1024)
        return path

# ══════════════════════════════════════════════════════════════════
# [7] SECCIÓN 1 — ENCABEZADO CON LOGO Y DATOS DEL ESTUDIANTE
#     Datos usados: subject, display_name, ws, test_code,
#                   test_date, current_level
# ══════════════════════════════════════════════════════════════════

def _seccion_encabezado(
    styles:            Dict,
    prospecto_nombre:  str,
    job_created_at:    datetime,
    cuant:             Dict[str, Any],
    orientador_nombre: Optional[str],
) -> list:
    """
    Encabezado del boletín: logo + título Kumon a la derecha,
    luego tabla de datos del estudiante con fondo azul claro.

    Campos usados de cuant:
      subject, display_name, ws, test_code, current_level
    """
    _LOGO_ANCHO = 3.5 * cm
    _LOGO_ALTO  = 2.0 * cm
    elementos   = []

    # ── Logo + bloque título ──────────────────────────────────────
    logo_path_abs = os.path.abspath(_LOGO_PATH)
    if os.path.exists(logo_path_abs):
        logo_cell = Image(logo_path_abs, width=_LOGO_ANCHO, height=_LOGO_ALTO)
    else:
        logo_cell = Paragraph(
            "<i>[logo_kumon.png<br/>no encontrado]</i>",
            ParagraphStyle("av", fontSize=6.5, textColor=_GRIS_TXT),
        )

    titulo_cell = [
        Paragraph("BOLETÍN DE DIAGNÓSTICO", styles["titulo"]),
        Paragraph(_NOMBRE_CENTRO,            styles["centro"]),
        Paragraph("Prueba Diagnóstica — Resultado de Evaluación",
                  styles["subtitulo"]),
    ]

    enc_tbl = Table([[logo_cell, titulo_cell]], colWidths=[4 * cm, 13 * cm])
    enc_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",       (1, 0), (1, 0),   "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    elementos.append(enc_tbl)
    elementos.append(Spacer(1, 0.3 * cm))

    # ── Tabla de datos del estudiante ────────────────────────────
    fecha_str  = job_created_at.strftime("%d de %B de %Y") if job_created_at else "—"
    materia    = (cuant.get("subject") or "").capitalize() or "—"
    nivel_str  = _parsear_display_name(cuant)
    cod_test   = cuant.get("test_code") or "—"
    nivel_act  = cuant.get("current_level") or "—"
    fecha_test = cuant.get("test_date") or "—"

    filas = [
        ["Estudiante evaluado:",  prospecto_nombre or "—"],
        ["Fecha de evaluación:",  fecha_str],
        ["Materia:",              materia],
        ["Nivel evaluado:",       nivel_str],
        ["Código de test:",       cod_test],
        ["Nivel actual:",         nivel_act],
    ]
    if fecha_test and fecha_test != "—":
        filas.append(["Fecha del test (BD):", str(fecha_test)])
    if orientador_nombre:
        filas.append(["Orientador a cargo:", orientador_nombre])

    tbl = Table(filas, colWidths=[5 * cm, 12 * cm])
    cmds = [
        ("BACKGROUND",    (0, 0), (-1, -1), _KUMON_AZUL_L),
        ("FONTNAME",      (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1),  "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR",     (0, 0), (0, -1),  _KUMON_AZUL),
        ("TEXTCOLOR",     (1, 0), (1, -1),  _NEGRO),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.3, _BORDE),
    ]
    cmds.append(("BACKGROUND", (0, 0), (-1, 0), _KUMON_AZUL_L))
    tbl.setStyle(TableStyle(cmds))
    elementos.append(tbl)
    return elementos

# ══════════════════════════════════════════════════════════════════
# [8] SECCIÓN 2 — RESULTADO CUANTITATIVO
#     Datos usados: correct_answers, total_questions, percentage,
#                   study_time_min, target_time_min, time_ratio,
#                   starting_point, semaforo, score_index,
#                   needs_manual_review, review_reasons
# ══════════════════════════════════════════════════════════════════

def _seccion_cuantitativo(styles: Dict, cuant: Dict[str, Any]) -> list:
    """
    Muestra los resultados numéricos del test diagnóstico.
    Incluye barra de progreso de aciertos, barra de tiempo y semáforo.
    """
    elementos = []
    elementos.append(Paragraph("📊  Resultado Cuantitativo", styles["seccion"]))

    # ── Textos calculados ─────────────────────────────────────────
    correctas = cuant.get("correct_answers")
    total     = cuant.get("total_questions")
    pct       = cuant.get("percentage")
    pct_val   = float(pct) if pct is not None else (
        round(correctas / total * 100, 1) if (correctas is not None and total) else None
    )
    score_str = (f"{correctas} correctas de {total}  ({pct_val:.1f}%)"
                 if correctas is not None else "No disponible")

    tiempo_str  = _parsear_tiempo(cuant.get("study_time_min"), cuant.get("target_time_min"))
    time_ratio  = cuant.get("time_ratio")
    score_index = cuant.get("score_index")

    # ── Tabla de indicadores ──────────────────────────────────────
    filas = [
        [Paragraph("<b>Indicador</b>", styles["campo_label"]),
         Paragraph("<b>Resultado</b>", styles["campo_label"])],
        ["Respuestas correctas",         score_str],
        ["Tiempo de estudio",            tiempo_str],
        ["Ratio tiempo (real/objetivo)", f"{time_ratio:.2f}x" if time_ratio else "—"],
        ["Puntaje cuant. (índice 0-100)", f"{score_index:.0f}" if score_index is not None else "—"],
        ["Punto de partida", _parsear_starting_point(cuant.get("starting_point"))],
    ]

    tbl = Table(filas, colWidths=[6.5 * cm, 10.5 * cm])
    tbl.setStyle(_tabla_base_style(len(filas)))
    elementos.append(tbl)
    elementos.append(Spacer(1, 0.25 * cm))

    # ── Barra de progreso de aciertos ────────────────────────────
    if pct_val is not None:
        sem  = (cuant.get("semaforo") or "").strip().lower()
        col_b = _SEM_COLOR.get(sem, _KUMON_AZUL_2)
        fila_barra = Table(
            [[Paragraph(f"<b>Aciertos:</b>  {pct_val:.0f}%", styles["campo_label"]),
              _barra_progreso_rl(pct_val, width=9 * cm, color_barra=col_b)]],
            colWidths=[4 * cm, 9.5 * cm],
        )
        fila_barra.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        elementos.append(fila_barra)
        elementos.append(Spacer(1, 0.18 * cm))

    # ── Barra de tiempo (solo si hay ratio) ───────────────────────
    if time_ratio is not None:
        # ratio > 1 → tardó más del objetivo (malo), mostrar en rojo
        pct_tiempo = min(100, time_ratio * 100)
        col_t = (colors.HexColor("#DC2626") if time_ratio > 1
                 else colors.HexColor("#16A34A"))
        fila_tiempo = Table(
            [[Paragraph(f"<b>Tiempo:</b>  {time_ratio:.2f}x", styles["campo_label"]),
              _barra_progreso_rl(pct_tiempo, width=9 * cm, color_barra=col_t)]],
            colWidths=[4 * cm, 9.5 * cm],
        )
        fila_tiempo.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",(0, 0), (-1, -1), 0),
        ]))
        elementos.append(fila_tiempo)
        elementos.append(Spacer(1, 0.18 * cm))

    # ── Bloque semáforo ───────────────────────────────────────────
    semaforo     = (cuant.get("semaforo") or "").strip().lower()
    semaforo_col = _SEM_COLOR.get(semaforo, _GRIS_TXT)
    semaforo_txt = _SEM_TEXTO.get(semaforo, "Sin clasificación automática")
    elementos.append(_bloque_color(semaforo_txt, bg=semaforo_col, font_size=11))

    # ── Aviso revisión manual ─────────────────────────────────────
    if cuant.get("needs_manual_review"):
        razones = cuant.get("review_reasons") or []
        nota    = "⚠ Este resultado requiere revisión del orientador."
        if razones:
            nota += "  Motivo: " + razones[0]
        elementos.append(Spacer(1, 0.15 * cm))
        elementos.append(Paragraph(nota, styles["aviso"]))

    return elementos


# ══════════════════════════════════════════════════════════════════
# [9] SECCIÓN 3 — PREFILLS AUTOMÁTICOS (VIDEO / AUDIO / CÁMARA)
#     Datos usados: cualitativo.prefills, cualitativo.auto_flags
#     Muestra qué captó el sistema automáticamente con su confianza.
# ══════════════════════════════════════════════════════════════════

def _seccion_prefills(
    styles:     Dict,
    prefills:   Dict[str, Any],
    auto_flags: List[str],
) -> list:
    """
    Muestra la tabla de señales capturadas automáticamente por
    el sistema (video, audio, cámara) con su confianza y valor.
    Diferencia entre 'auto_captured' (confianza >= umbral)
    y 'pre-marcado para orientador' (ALWAYS_CONFIRM).
    """
    elementos = []
    elementos.append(Paragraph(
        "🤖  Señales Capturadas Automáticamente", styles["seccion"]
    ))
    elementos.append(Paragraph(
        "Datos extraídos por el sistema de análisis de video/audio. "
        "Los marcados con ✔ fueron validados automáticamente. "
        "Los marcados con 👁 requieren confirmación del orientador.",
        styles["aviso_info"]
    ))
    elementos.append(Spacer(1, 0.2 * cm))

    filas = [
        [Paragraph("<b>Métrica</b>",   styles["campo_label"]),
         Paragraph("<b>Valor</b>",     styles["campo_label"]),
         Paragraph("<b>Fuente</b>",    styles["campo_label"]),
         Paragraph("<b>Estado</b>",    styles["campo_label"])],
    ]
    estilos_din: List[tuple] = []

    for i, (key, data) in enumerate(prefills.items(), start=1):
        valor    = data.get("valor", "—")
        fuente   = _label_fuente(data)
        es_auto  = key in auto_flags
        estado   = "✔ Validado" if es_auto else "👁 Confirmar"
        col_est  = colors.HexColor("#16A34A") if es_auto else colors.HexColor("#D97706")

        # Valor legible
        if isinstance(valor, float):
            valor_str = f"{valor:.3f}"
        elif isinstance(valor, bool):
            valor_str = "Sí" if valor else "No"
        else:
            valor_str = str(valor) if valor is not None else "—"

        filas.append([key.replace("_", " ").capitalize(), valor_str, fuente, estado])
        estilos_din.append(("TEXTCOLOR", (3, i), (3, i), col_est))
        estilos_din.append(("FONTNAME",  (3, i), (3, i), "Helvetica-Bold"))
        if i % 2 == 0:
            estilos_din.append(("BACKGROUND", (0, i), (2, i), _GRIS_CLARO))

    tbl = Table(filas, colWidths=[5.5 * cm, 4 * cm, 4.5 * cm, 3 * cm])
    base_style = _tabla_base_style(len(filas), header_color=_KUMON_AZUL, alternate=False)
    tbl.setStyle(TableStyle(base_style._cmds + estilos_din))
    elementos.append(tbl)
    return elementos


# ══════════════════════════════════════════════════════════════════
# [10] SECCIÓN 4 — VALORACIÓN CUALITATIVA POR ÁREAS
#      Datos usados: cualitativo.total_porcentaje, etiqueta_total,
#                    secciones (nombre, etiqueta, porcentaje, puntaje)
#                    auto_flags (para marcar fuente)
# ══════════════════════════════════════════════════════════════════

def _seccion_cualitativa(styles: Dict, cual: Dict[str, Any]) -> list:
    """
    Tabla de áreas de actitud y comportamiento con nivel, puntaje
    y fuente (automático u orientador). Incluye resumen global
    con badge de etiqueta colorido al inicio.
    """
    elementos  = []
    elementos.append(Paragraph("📋  Valoración Cualitativa", styles["seccion"]))

    secciones  = cual.get("secciones") or []
    auto_flags = [f.lower() for f in (cual.get("auto_flags") or [])]
    etiqueta   = cual.get("etiqueta_total") or ""
    pct_total  = cual.get("total_porcentaje")

    # ── Badge resumen global ──────────────────────────────────────
    if pct_total is not None and etiqueta:
        etiq_lbl = _ETIQ_LABEL.get(etiqueta, etiqueta)
        etiq_bg  = _ETIQ_BG.get(etiqueta, _KUMON_AZUL_L)
        etiq_fg  = _ETIQ_FG.get(etiqueta, _KUMON_AZUL)
        elementos.append(_bloque_color(
            f"Nivel general de actitud: {etiq_lbl}  —  {pct_total:.1f}%",
            bg=etiq_bg, fg=etiq_fg, font_size=10,
        ))
        elementos.append(Spacer(1, 0.25 * cm))

        # Barra de progreso cualitativo
        fila_b = Table(
            [[Paragraph(f"<b>Actitud global:</b>  {pct_total:.0f}%", styles["campo_label"]),
              _barra_progreso_rl(
                  pct_total, width=9 * cm,
                  color_barra=_ETIQ_FG.get(etiqueta, _KUMON_AZUL_2),
              )]],
            colWidths=[4.5 * cm, 9.5 * cm],
        )
        fila_b.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elementos.append(fila_b)
        elementos.append(Spacer(1, 0.2 * cm))

    # ── Tabla detallada por área ──────────────────────────────────
    if secciones:
        filas_tbl = [
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
            lbl_s    = _ETIQ_LABEL.get(etiq_s, etiq_s)
            bg_s     = _ETIQ_BG.get(etiq_s, _BLANCO)
            pct_txt  = f"{float(pct_s):.1f}%" if pct_s is not None else "—"

            filas_tbl.append([nombre, lbl_s, pct_txt, fuente])
            estilos_din.append(("BACKGROUND", (1, i), (1, i), bg_s))
            estilos_din.append(("TEXTCOLOR",  (1, i), (1, i),
                                 _ETIQ_FG.get(etiq_s, _NEGRO)))
            estilos_din.append(("FONTNAME",   (1, i), (1, i), "Helvetica-Bold"))
            if i % 2 == 0:
                estilos_din.append(("BACKGROUND", (0, i), (0, i), _GRIS_CLARO))
                estilos_din.append(("BACKGROUND", (2, i), (3, i), _GRIS_CLARO))

        tbl_c = Table(filas_tbl, colWidths=[6 * cm, 4.5 * cm, 2.5 * cm, 4 * cm])
        base  = _tabla_base_style(len(filas_tbl), alternate=False)
        tbl_c.setStyle(TableStyle(base._cmds + estilos_din))
        elementos.append(tbl_c)
    else:
        elementos.append(Paragraph(
            "No se registraron métricas de actitud en esta evaluación.",
            styles["narrativa"],
        ))

    return elementos


# ══════════════════════════════════════════════════════════════════
# [11] SECCIÓN 5 — GRÁFICA DE ACTITUD POR SECCIÓN
#      Llama a _grafica_barras_secciones() y la inserta en el PDF.
# ══════════════════════════════════════════════════════════════════

def _seccion_grafica_cualitativa(
    styles:    Dict,
    secciones: List[Dict[str, Any]],
) -> list:
    """
    Inserta la gráfica de barras horizontales de la valoración
    cualitativa directamente después de la tabla de áreas.
    """
    elementos = []
    img = _grafica_barras_secciones(secciones, ancho_cm=15)
    if img:
        elementos.append(KeepTogether([
            Paragraph("📈  Gráfica de desempeño por área", styles["subseccion"]),
            Spacer(1, 0.15 * cm),
            img,
        ]))
    return elementos


# ══════════════════════════════════════════════════════════════════
# [12] SECCIÓN 6 — PUNTUACIÓN GLOBAL COMBINADA 65/35
#      Datos usados: combinado.puntaje, etiqueta, narrativa,
#                    kpi.cuantitativo.{puntaje, peso},
#                    kpi.cualitativo.{puntaje, peso},
#                    datos_incompletos
# ══════════════════════════════════════════════════════════════════

def _seccion_combinada(styles: Dict, comb: Dict[str, Any]) -> list:
    """
    Sección de puntuación global combinada con:
    - Badge de etiqueta coloreado
    - Tabla KPI cuantitativo vs cualitativo con pesos
    - Arco (velocímetro) de puntaje final
    - Narrativa explicativa generada por el backend
    """
    elementos = []
    elementos.append(Paragraph("🏆  Puntuación Global del Diagnóstico", styles["seccion"]))

    puntaje  = comb.get("puntaje")
    etiqueta = comb.get("etiqueta") or ""
    narrativa = comb.get("narrativa") or ""
    kpi       = comb.get("kpi") or {}
    incompleto = comb.get("datos_incompletos", False)

    # ── Aviso datos incompletos ───────────────────────────────────
    if incompleto:
        elementos.append(Paragraph(
            "⚠ El puntaje combinado es parcial porque falta uno de los dos componentes.",
            styles["aviso"],
        ))
        elementos.append(Spacer(1, 0.15 * cm))

    # ── Badge de etiqueta global ──────────────────────────────────
    if puntaje is not None and etiqueta:
        etiq_lbl = _ETIQ_LABEL.get(etiqueta, etiqueta)
        etiq_bg  = _ETIQ_BG.get(etiqueta, _KUMON_AZUL_L)
        etiq_fg  = _ETIQ_FG.get(etiqueta, _KUMON_AZUL)
        elementos.append(_bloque_color(
            f"Puntaje combinado: {puntaje:.1f} / 100  —  {etiq_lbl}",
            bg=etiq_bg, fg=etiq_fg, font_size=11,
        ))
        elementos.append(Spacer(1, 0.3 * cm))

    # ── Arco velocímetro + tabla KPI lado a lado ──────────────────
    cuant_kpi = kpi.get("cuantitativo") or {}
    cual_kpi  = kpi.get("cualitativo")  or {}

    arco_img = _grafica_arco_combinado(
        puntaje, etiqueta, ancho_cm=7, alto_cm=4.5
    )

    kpi_rows = [
        [Paragraph("<b>Componente</b>",   styles["campo_label"]),
         Paragraph("<b>Puntaje</b>",      styles["campo_label"]),
         Paragraph("<b>Peso</b>",         styles["campo_label"]),
         Paragraph("<b>Contribución</b>", styles["campo_label"])],
    ]
    for nombre_kpi, bloque_kpi in [("Cuantitativo", cuant_kpi),
                                    ("Cualitativo",  cual_kpi)]:
        p = bloque_kpi.get("puntaje")
        w = bloque_kpi.get("peso")
        contrib = f"{p * w:.1f}" if (p is not None and w is not None) else "—"
        kpi_rows.append([
            nombre_kpi,
            f"{p:.1f}" if p is not None else "—",
            f"{w*100:.0f}%" if w is not None else "—",
            contrib,
        ])

    tbl_kpi = Table(kpi_rows, colWidths=[3.5 * cm, 2.2 * cm, 2 * cm, 2.5 * cm])
    tbl_kpi.setStyle(_tabla_base_style(len(kpi_rows)))

    if arco_img:
        contenido_kpi = Table(
            [[arco_img, tbl_kpi]],
            colWidths=[7.5 * cm, 9.5 * cm],
        )
        contenido_kpi.setStyle(TableStyle([
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elementos.append(contenido_kpi)
    else:
        elementos.append(tbl_kpi)

    # ── Narrativa del backend ─────────────────────────────────────
    if narrativa:
        elementos.append(Spacer(1, 0.25 * cm))
        elementos.append(Paragraph(narrativa, styles["narrativa_azul"]))

    return elementos


# ══════════════════════════════════════════════════════════════════
# SECCIÓN GAZE — DATOS DE CÁMARA FRONTAL (reservado)
#   Solo aparece cuando el backend entrega gaze_data != None.
#   Preparado para cuando se active el hardware PIP / cámara.
# ══════════════════════════════════════════════════════════════════

def _seccion_gaze(styles: Dict, gaze: Dict[str, Any]) -> list:
    """
    Muestra los datos de atención visual (cámara frontal).
    Actualmente reservado — aparece solo si gaze llega con datos.
    """
    elementos = []
    elementos.append(Paragraph("📷  Análisis de Atención Visual (Cámara)", styles["seccion"]))
    elementos.append(Paragraph(
        "Datos capturados por la cámara frontal durante la sesión.",
        styles["aviso_info"]
    ))
    elementos.append(Spacer(1, 0.2 * cm))

    filas = [[Paragraph("<b>Métrica</b>", styles["campo_label"]),
              Paragraph("<b>Valor</b>",   styles["campo_label"])]]
    for key, val in gaze.items():
        if isinstance(val, float):
            val_str = f"{val:.3f}"
        elif isinstance(val, dict):
            val_str = str(val)
        else:
            val_str = str(val) if val is not None else "—"
        filas.append([key.replace("_", " ").capitalize(), val_str])

    tbl = Table(filas, colWidths=[6 * cm, 11 * cm])
    tbl.setStyle(_tabla_base_style(len(filas)))
    elementos.append(tbl)
    return elementos


# ══════════════════════════════════════════════════════════════════
# [13] SECCIÓN 7 — RECOMENDACIÓN Y PUNTO DE PARTIDA
#      Datos usados: cuantitativo.recommendation, starting_point,
#                    semaforo (para color de fondo),
#                    combinado.etiqueta (para contexto)
# ══════════════════════════════════════════════════════════════════

def _seccion_recomendacion(
    styles: Dict,
    cuant:  Dict[str, Any],
    comb:   Dict[str, Any],
) -> list:
    """
    Muestra la recomendación del backend y el punto de partida
    calculado por result_calculator, en un bloque de acción clara.
    """
    elementos = []
    elementos.append(Paragraph("🎯  Recomendación y Punto de Partida", styles["seccion"]))

    recomendacion = cuant.get("recommendation") or ""
    starting      = _parsear_starting_point(cuant.get("starting_point"))
    semaforo      = (cuant.get("semaforo") or "").strip().lower()
    comb_etiq     = comb.get("etiqueta") if comb else None

    # ── Punto de partida con color del semáforo ───────────────────
    sem_bg  = _SEM_COLOR.get(semaforo, _KUMON_AZUL_M)
    elementos.append(_bloque_color(
        f"📌  Punto de partida recomendado:  {starting}",
        bg=sem_bg, font_size=10,
    ))
    elementos.append(Spacer(1, 0.2 * cm))

    # ── Recomendación narrativa del backend ───────────────────────
    if recomendacion:
        elementos.append(Paragraph(
            f"<b>Recomendación del sistema:</b>  {recomendacion}",
            styles["narrativa_azul"],
        ))
        elementos.append(Spacer(1, 0.15 * cm))

    # ── Contexto del combinado ────────────────────────────────────
    if comb_etiq:
        comb_bg  = _ETIQ_BG.get(comb_etiq, _KUMON_AZUL_L)
        comb_fg  = _ETIQ_FG.get(comb_etiq, _KUMON_AZUL)
        comb_lbl = _ETIQ_LABEL.get(comb_etiq, "")
        elementos.append(_bloque_color(
            f"Desempeño global: {comb_lbl}",
            bg=comb_bg, fg=comb_fg, font_size=9, bold=False,
        ))

    return elementos


# ══════════════════════════════════════════════════════════════════
# [14] SECCIÓN 8 — PIE DE PÁGINA
#      Muestra confidencialidad, fecha de generación,
#      aviso de correcciones del orientador.
# ══════════════════════════════════════════════════════════════════

def _seccion_pie(
    styles:           Dict,
    hubo_correcciones: bool = False,
) -> list:
    """
    Pie de página con información institucional, confidencialidad
    y aviso si el orientador realizó correcciones manuales.
    """
    elementos = []
    ahora = datetime.now().strftime("%d/%m/%Y  %H:%M")

    elementos.append(Paragraph(
        f"Generado automáticamente por el sistema de diagnóstico Kumon Ipiales  ·  {ahora}",
        styles["pie_negrita"],
    ))
    elementos.append(Spacer(1, 0.1 * cm))
    elementos.append(Paragraph(
        "Este boletín es de uso interno y confidencial. "
        "No debe ser distribuido a terceros sin autorización del centro.",
        styles["pie"],
    ))

    if hubo_correcciones:
        elementos.append(Spacer(1, 0.1 * cm))
        elementos.append(Paragraph(
            "⚠  Este boletín contiene campos revisados o ajustados manualmente por el orientador.",
            ParagraphStyle(
                "pie_aviso", fontSize=7, fontName="Helvetica-Bold",
                textColor=colors.HexColor("#92400E"), alignment=TA_CENTER,
            ),
        ))

    elementos.append(Spacer(1, 0.15 * cm))
    elementos.append(Paragraph(
        f"Kumon Ipiales  ·  Sistema de Diagnóstico Automático v3.0  ·  {_NOMBRE_CENTRO}",
        styles["pie"],
    ))
    return elementos