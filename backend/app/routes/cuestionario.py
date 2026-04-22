from __future__ import annotations

"""
app/routes/cuestionario.py
══════════════════════════════════════════════════════════════════
Maneja toda la capa cualitativa del orientador y el boletín:

  - GET  /api/v1/cuestionario/{result_id}
  - POST /api/v1/cuestionario/{result_id}
  - GET  /api/v1/boletin/{result_id}

Flujo:
  1) QualitativeResult guarda señales automáticas (video/audio/gaze).
  2) GET cuestionario usa config.cuestionarios + prefills.
  3) POST cuestionario guarda ObservacionCualitativa con el valor final
     consolidado (automático + orientador).
  4) GET boletin combina TestResult + ObservacionCualitativa
     usando report_generator (65% cuant + 35% cual).
  5) Opcionalmente persiste/lee de la tabla Bulletin.
══════════════════════════════════════════════════════════════════
"""
import io
from xml.sax.saxutils import escape
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from database.models import (
    TestResult,
    QualitativeResult,
    ObservacionCualitativa,
    Bulletin,
)
from app.schemas.cuestionario import (
    CuestionarioResponse,
    RespuestaCuestionarioRequest,
    CuestionarioSubmitResponse,
    BoletinResponse,
)
from config.cuestionarios import (
    obtener_cuestionario,
    obtener_cuestionario_con_prefill,
    calcular_puntaje_cualitativo,
)
from app.services.report_generator import (
    QuantitativeInput,
    QualitativeInput,
    build_report_data,
)

router = APIRouter(prefix="/api/v1", tags=["cuestionario"])


# ──────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────

def _get_template_or_409(result: TestResult):
    template = result.template
    if not template:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El resultado no tiene una plantilla asociada.",
        )
    return template


def _get_qualitative_result(db: Session, result: TestResult):
    return (
        db.query(QualitativeResult)
        .filter(QualitativeResult.id_job == result.id_job)
        .first()
    )


def _obs_to_prefills(respuestas: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    prefills: dict[str, dict[str, Any]] = {}
    if not respuestas:
        return prefills

    for key, value in respuestas.items():
        if isinstance(value, dict) and "valor" in value:
            prefills[key] = {
                "valor": value.get("valor"),
                "confianza": 1.0,
                "fuente": value.get("fuente", "orientador"),
            }
        else:
            prefills[key] = {
                "valor": value,
                "confianza": 1.0,
                "fuente": "orientador",
            }

    return prefills


def _merge_prefills(
    qual: QualitativeResult | None,
    obs: ObservacionCualitativa | None,
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    if qual and qual.prefills:
        merged.update(qual.prefills)

    if obs and obs.respuestas:
        merged.update(_obs_to_prefills(obs.respuestas))

    return merged


def _flatten_respuestas(respuestas: dict[str, Any] | None) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    if not respuestas:
        return flattened

    for key, value in respuestas.items():
        if isinstance(value, dict) and "valor" in value:
            flattened[key] = value.get("valor")
        else:
            flattened[key] = value

    return flattened


def _build_final_respuestas(
    payload_respuestas: dict[str, Any] | None,
    qual: QualitativeResult | None,
) -> dict[str, dict[str, Any]]:
    final_respuestas: dict[str, dict[str, Any]] = {}

    if qual and qual.prefills:
        for key, data in qual.prefills.items():
            final_respuestas[key] = {
                "valor": data.get("valor"),
                "fuente": "sistema",
                "corregido": False,
            }

    for key, value in (payload_respuestas or {}).items():
        valor = value.get("valor") if isinstance(value, dict) and "valor" in value else value
        final_respuestas[key] = {
            "valor": valor,
            "fuente": "orientador",
            "corregido": bool(qual and key in (qual.auto_captured_flags or [])),
        }

    return final_respuestas


# ──────────────────────────────────────────────────────────────
# GET /cuestionario/{result_id}
# ──────────────────────────────────────────────────────────────

@router.get("/cuestionario/{result_id}", response_model=CuestionarioResponse)
def get_cuestionario(result_id: UUID, db: Session = Depends(get_db)):
    result = (
        db.query(TestResult)
        .filter(TestResult.id_result == result_id)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado no encontrado.",
        )

    template = _get_template_or_409(result)
    qual = _get_qualitative_result(db, result)

    obs = (
        db.query(ObservacionCualitativa)
        .filter(ObservacionCualitativa.id_result == result.id_result)
        .first()
    )

    prefills = _merge_prefills(qual, obs)
    prefill_flags = qual.auto_captured_flags if qual and qual.auto_captured_flags else []
    tiene_prefills = bool(prefills)

    if prefills:
        cuestionario = obtener_cuestionario_con_prefill(
            subject=template.subject,
            test_code=template.code,
            prefills=prefills,
            auto_flags=prefill_flags,
        )
    else:
        cuestionario = obtener_cuestionario(
            subject=template.subject,
            test_code=template.code,
        )

    return CuestionarioResponse(
        result_id=result.id_result,
        subject=template.subject,
        test_code=template.code,
        cuestionario=cuestionario,
        ya_completado=bool(obs and obs.esta_completo),
        tiene_prefills=tiene_prefills,
        prefill_flags=prefill_flags,
    )


# ──────────────────────────────────────────────────────────────
# POST /cuestionario/{result_id}
# ──────────────────────────────────────────────────────────────


@router.post(
    "/cuestionario/{result_id}",
    response_model=CuestionarioSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_cuestionario(
    result_id: UUID,
    payload: RespuestaCuestionarioRequest,
    db: Session = Depends(get_db),
):
    result = (
        db.query(TestResult)
        .filter(TestResult.id_result == result_id)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado no encontrado.",
        )


    template = _get_template_or_409(result)
    qual = _get_qualitative_result(db, result)


    final_respuestas = _build_final_respuestas(
        payload_respuestas=payload.respuestas,
        qual=qual,
    )
    respuestas_para_calculo = _flatten_respuestas(final_respuestas)


    if not respuestas_para_calculo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se recibieron respuestas para calcular el cuestionario.",
        )


    calc = calcular_puntaje_cualitativo(
        subject=template.subject,
        test_code=template.code,
        respuestas=respuestas_para_calculo,
    )


    obs = (
        db.query(ObservacionCualitativa)
        .filter(ObservacionCualitativa.id_result == result.id_result)
        .first()
    )
    if not obs:
        obs = ObservacionCualitativa(id_result=result.id_result)


    mapper_attrs = set(type(obs).__mapper__.attrs.keys())


    obs.subject = template.subject
    obs.test_code = template.code
    obs.respuestas = final_respuestas

    if "puntaje_cualitativo" in mapper_attrs:
        obs.puntaje_cualitativo = calc["total_porcentaje"]
    if "etiqueta_cualitativa" in mapper_attrs:
        obs.etiqueta_cualitativa = calc["etiqueta_total"]
    if "detalle_secciones" in mapper_attrs:
        obs.detalle_secciones = calc["secciones"]
    if "completado" in mapper_attrs:
        obs.completado = True
    if "esta_completo" in mapper_attrs:
        obs.esta_completo = True

    obs.completado_por = payload.completado_por
    obs.completado_at = datetime.now(timezone.utc)

    if "observacion_libre" in mapper_attrs:
        obs.observacion_libre = payload.observacion_libre
    if "correcciones_orientador" in mapper_attrs:
        obs.correcciones_orientador = payload.correcciones_orientador or {}

    db.add(obs)


    db.commit()
    db.refresh(obs)


    return CuestionarioSubmitResponse(
        observacion_id=obs.id_observacion,
        result_id=result.id_result,
        total_porcentaje=calc["total_porcentaje"],
        etiqueta_total=calc["etiqueta_total"],
        secciones=calc["secciones"],
        boletin_habilitado=True,
        message="Cuestionario cualitativo guardado correctamente.",
    )

# ──────────────────────────────────────────────────────────────
# GET /boletin/{result_id}
# ──────────────────────────────────────────────────────────────


@router.get("/boletin/{result_id}", response_model=BoletinResponse)
def get_boletin(result_id: UUID, db: Session = Depends(get_db)):
    """
    Retorna el boletín consolidado:
      - Si existe en tabla Bulletin con datos_boletin completo, lo sirve
        directamente sin recalcular ni modificar nada en BD.
      - Si no existe o está incompleto, lo construye con report_generator,
        lo persiste y lo retorna.


    En ambos casos retorna:
      - cuantitativo
      - cualitativo
      - combinado (65% cuant + 35% cual)
      - gaze (si hubiese datos de cámara frontal)
    """
    result = (
        db.query(TestResult)
        .filter(TestResult.id_result == result_id)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado no encontrado.",
        )


    template = _get_template_or_409(result)


    obs = (
        db.query(ObservacionCualitativa)
        .filter(ObservacionCualitativa.id_result == result.id_result)
        .first()
    )

    esta_completo = bool(
        obs
        and (
            getattr(obs, "esta_completo", False)
            or (
                getattr(obs, "respuestas", None)
                and getattr(obs, "completado_at", None) is not None
            )
        )
    )

    if not esta_completo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El boletín solo está disponible cuando el cuestionario cualitativo está completo.",
        )


    bulletin = (
        db.query(Bulletin)
        .filter(Bulletin.id_result == result.id_result)
        .first()
    )


    # ── Early return: si el boletín ya fue generado, servirlo directamente ──
    # No se recalcula, no se escribe en BD, no se pisa generated_at.
    # La verdad persistida en Bulletin es la fuente final.
    if bulletin and bulletin.datos_boletin:
        datos = bulletin.datos_boletin
        return BoletinResponse(
            boletin_id=bulletin.id_bulletin,
            result_id=result.id_result,
            subject=template.subject,
            test_code=template.code,
            status=bulletin.status,
            generated_at=bulletin.generated_at,
            cuantitativo=datos.get("cuantitativo", {}),
            cualitativo=datos.get("cualitativo", {}),
            combinado=datos.get("combinado", {}),
            gaze=datos.get("gaze"),
            message="Boletín generado correctamente.",
        )


    # ── Generación: solo llega aquí si bulletin no existe o no tiene datos ──
    qual = _get_qualitative_result(db, result)

    puntaje_cualitativo = getattr(obs, "puntaje_cualitativo", None)
    etiqueta_cualitativa = getattr(obs, "etiqueta_cualitativa", None)
    detalle_secciones = getattr(obs, "detalle_secciones", None)

    if (
        puntaje_cualitativo is not None
        and etiqueta_cualitativa
        and detalle_secciones is not None
    ):
        total_porcentaje = float(puntaje_cualitativo)
        etiqueta_total = etiqueta_cualitativa
        secciones = detalle_secciones
    else:
        try:
            calc = calcular_puntaje_cualitativo(
                subject=template.subject,
                test_code=template.code,
                respuestas=_flatten_respuestas(obs.respuestas),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No fue posible calcular el boletín cualitativo: {exc}",
            ) from exc


        total_porcentaje = float(calc["total_porcentaje"])
        etiqueta_total = calc["etiqueta_total"]
        secciones = calc["secciones"]


    # Obtener el job para usar la fecha oficial de carga del video
    job = result.job


    qnt = QuantitativeInput(
        subject=template.subject,
        test_code=template.code,
        display_name=template.display_name,
        ws=result.ws,
        test_date=job.created_at if job and job.created_at else result.test_date,
        study_time_min=result.study_time_min,
        target_time_min=result.target_time_min,
        correct_answers=result.correct_answers,
        total_questions=result.total_questions,
        percentage=result.percentage,
        current_level=result.current_level,
        starting_point=result.starting_point,
        semaforo=result.semaforo,
        recommendation=result.recommendation,
    )


    cual_input = QualitativeInput(
        total_porcentaje=total_porcentaje,
        etiqueta_total=etiqueta_total,
        secciones=secciones,
        auto_flags=qual.auto_captured_flags if qual and qual.auto_captured_flags else [],
        prefills=qual.prefills if qual and qual.prefills else {},
        gaze_data=qual.gaze_data if qual and qual.gaze_data else None,
    )


    datos = build_report_data(qnt, cual_input)


    if not bulletin:
        bulletin = Bulletin(
            id_result=result.id_result,
            id_template=result.id_template,
        )


    bulletin.datos_boletin = datos
    bulletin.puntaje_cuantitativo = datos.get("cuantitativo", {}).get("score_index")
    bulletin.puntaje_cualitativo = total_porcentaje
    bulletin.puntaje_combinado = datos.get("combinado", {}).get("puntaje")
    bulletin.etiqueta_combinada = datos.get("combinado", {}).get("etiqueta")
    bulletin.status = "ready"
    bulletin.generated_at = datetime.now(timezone.utc)


    db.add(bulletin)
    db.commit()
    db.refresh(bulletin)


    return BoletinResponse(
        boletin_id=bulletin.id_bulletin,
        result_id=result.id_result,
        subject=template.subject,
        test_code=template.code,
        status=bulletin.status,
        generated_at=bulletin.generated_at,
        cuantitativo=datos.get("cuantitativo", {}),
        cualitativo=datos.get("cualitativo", {}),
        combinado=datos.get("combinado", {}),
        gaze=datos.get("gaze"),
        message="Boletín generado correctamente.",
    )

# ──────────────────────────────────────────────────────────────
# Helpers para generación de PDF
# ──────────────────────────────────────────────────────────────

import io
from fastapi.responses import StreamingResponse


def _color_semaforo(semaforo: str) -> str:
    """Mapea el semáforo cuantitativo a un color hex."""
    return {
        "verde":    "#437a22",
        "amarillo": "#b07a00",
        "rojo":     "#a13544",
    }.get((semaforo or "").lower(), "#7a7974")


def _color_etiqueta(etiqueta: str) -> str:
    """Mapea la etiqueta combinada a un color hex."""
    return {
        "sobresaliente":         "#437a22",
        "en_nivel":              "#437a22",
        "en_desarrollo":         "#b07a00",
        "requiere_apoyo":        "#a13544",
        "rojo_por_flag_critico": "#a12c7b",
    }.get((etiqueta or "").lower(), "#7a7974")


def _svg_gauge(pct: float, color: str, label: str) -> str:
    """
    Genera un gauge semicircular en SVG puro.
    pct: valor de 0 a 100.
    """
    pct = max(0.0, min(100.0, float(pct or 0)))
    radius  = 54
    cx, cy  = 70, 70
    # Ángulo de barrido: 180° = pct 100
    import math
    angle_deg = 180.0 * (pct / 100.0)
    angle_rad = math.radians(180 - angle_deg)
    end_x = cx + radius * math.cos(angle_rad)
    end_y = cy - radius * math.sin(angle_rad)
    large = 1 if angle_deg > 180 else 0

    # Track gris de fondo (semicírculo completo)
    track_end_x = cx + radius
    track_start_x = cx - radius

    return f"""
    <svg width="140" height="80" viewBox="0 0 140 80" xmlns="http://www.w3.org/2000/svg">
      <!-- Track fondo -->
      <path d="M {cx - radius} {cy} A {radius} {radius} 0 0 1 {cx + radius} {cy}"
            fill="none" stroke="#e6e4df" stroke-width="12" stroke-linecap="round"/>
      <!-- Arco de valor -->
      <path d="M {cx - radius} {cy} A {radius} {radius} 0 {large} 1 {end_x:.2f} {end_y:.2f}"
            fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round"/>
      <!-- Valor numérico -->
      <text x="{cx}" y="{cy - 4}" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="20" font-weight="bold" fill="{color}">
        {pct:.1f}
      </text>
      <text x="{cx}" y="{cy + 12}" text-anchor="middle"
            font-family="Arial, sans-serif" font-size="9" fill="#7a7974">
        {label}
      </text>
    </svg>"""


def _svg_barra(secciones: list) -> str:
    """
    Genera barras horizontales SVG para las secciones cualitativas.
    Cada sección: {"nombre": str, "porcentaje": float, "etiqueta": str}
    """
    if not secciones:
        return ""

    bar_height = 18
    gap        = 10
    label_w    = 160
    bar_max_w  = 200
    total_h    = len(secciones) * (bar_height + gap) + 10
    total_w    = label_w + bar_max_w + 50

    items = []
    for i, sec in enumerate(secciones):
        pct   = float(sec.get("porcentaje") or sec.get("puntaje") or 0)
        nombre = str(sec.get("nombre") or sec.get("nombre_display") or f"Sección {i+1}")[:30]
        color = _color_etiqueta(sec.get("etiqueta") or "")
        y     = i * (bar_height + gap) + 5
        bar_w = int((pct / 100.0) * bar_max_w)
        items.append(f"""
          <text x="{label_w - 6}" y="{y + bar_height - 4}"
                text-anchor="end" font-family="Arial,sans-serif"
                font-size="10" fill="#28251d">{nombre}</text>
          <rect x="{label_w}" y="{y}" width="{bar_max_w}" height="{bar_height}"
                rx="4" fill="#e6e4df"/>
          <rect x="{label_w}" y="{y}" width="{bar_w}" height="{bar_height}"
                rx="4" fill="{color}"/>
          <text x="{label_w + bar_w + 5}" y="{y + bar_height - 4}"
                font-family="Arial,sans-serif" font-size="10"
                fill="{color}" font-weight="bold">{pct:.0f}%</text>
        """)

    return f"""
    <svg width="{total_w}" height="{total_h}"
         viewBox="0 0 {total_w} {total_h}"
         xmlns="http://www.w3.org/2000/svg">
      {''.join(items)}
    </svg>"""


def _build_pdf_html(
    datos:    dict,
    result:   "TestResult",
    template: Any,
    nombre_sujeto: str,
) -> str:
    """
    Construye el HTML completo del boletín para WeasyPrint.
    Incluye: encabezado, sección cuantitativa, cualitativa y combinada.
    """
    cuan    = datos.get("cuantitativo") or {}
    cual    = datos.get("cualitativo")  or {}
    comb    = datos.get("combinado")    or {}

    # ── Datos cuantitativos ──────────────────────────────────────
    pct_cuan      = float(cuan.get("score_index")   or cuan.get("percentage") or 0)
    score_cuan    = float(cuan.get("score_index")   or 0)
    semaforo      = str(cuan.get("semaforo")        or "").lower()
    color_sem     = _color_semaforo(semaforo)
    correctas     = cuan.get("correct_answers", 0)
    total_preg    = cuan.get("total_questions", 0)
    pct_bruta     = float(cuan.get("percentage")    or 0)
    study_time    = float(cuan.get("study_time_min") or 0)
    target_time   = float(cuan.get("target_time_min") or 0)
    ws            = cuan.get("ws") or template.code if template else ""
    test_date_raw = cuan.get("test_date") or (str(result.test_date) if result.test_date else "—")
    nivel_actual  = cuan.get("current_level") or "—"
    punto_inicio  = cuan.get("starting_point") or "—"
    recom         = cuan.get("recommendation") or "—"
    display_name  = cuan.get("display_name") or (template.display_name if template else "")

    gauge_cuan = _svg_gauge(score_cuan, color_sem, "Índice cuantitativo")

    # ── Datos cualitativos ───────────────────────────────────────
    pct_cual      = float(cual.get("total_porcentaje") or cual.get("puntaje") or 0)
    etq_cual      = cual.get("etiqueta_total") or "—"
    color_cual    = _color_etiqueta(etq_cual)
    secciones_q   = cual.get("secciones") or []

    gauge_cual = _svg_gauge(pct_cual, color_cual, "Índice cualitativo")
    barras_html = _svg_barra(secciones_q)

    # Flags observados
    auto_flags: list = cual.get("auto_flags") or []
    flags_html = ""
    if auto_flags:
        items_flag = "".join(
            f'<span class="flag">{f.replace("_", " ").capitalize()}</span>'
            for f in auto_flags
        )
        flags_html = f'<div class="flags-row">{items_flag}</div>'

    # ── Datos combinados ─────────────────────────────────────────
    pct_comb      = float(comb.get("puntaje") or 0)
    etq_comb      = comb.get("etiqueta") or "—"
    color_comb    = _color_etiqueta(etq_comb)
    formula_txt   = comb.get("formula") or "0.65 × cuantitativo + 0.35 × cualitativo"
    override_note = ""
    if comb.get("override"):
        override_note = f'<p class="override-note">⚠ Ajuste aplicado: {comb["override"].replace("_", " ")}</p>'

    gauge_comb = _svg_gauge(pct_comb, color_comb, "Puntaje combinado")

    # ── Etiqueta display ─────────────────────────────────────────
    etiquetas_display = {
        "sobresaliente":         "Sobresaliente",
        "en_nivel":              "En nivel",
        "en_desarrollo":         "En desarrollo",
        "requiere_apoyo":        "Requiere apoyo",
        "rojo_por_flag_critico": "Requiere seguimiento cercano",
    }
    etq_cuan_label = etiquetas_display.get(cuan.get("etiqueta") or semaforo, semaforo.capitalize())
    etq_cual_label = etiquetas_display.get(etq_cual, etq_cual.replace("_", " ").capitalize())
    etq_comb_label = etiquetas_display.get(etq_comb, etq_comb.replace("_", " ").capitalize())

    # ── HTML ─────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: Arial, sans-serif;
    font-size: 11px;
    color: #28251d;
    background: #fff;
    padding: 28px 32px;
  }}
  /* ── Encabezado ── */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 3px solid #01696f;
    padding-bottom: 12px;
    margin-bottom: 18px;
  }}
  .header-title {{ font-size: 20px; font-weight: bold; color: #01696f; }}
  .header-sub   {{ font-size: 12px; color: #7a7974; margin-top: 2px; }}
  .header-meta  {{ text-align: right; font-size: 10px; color: #7a7974; line-height: 1.7; }}
  .header-meta strong {{ color: #28251d; }}

  /* ── Secciones ── */
  .section {{
    margin-bottom: 20px;
    border: 1px solid #dcd9d5;
    border-radius: 6px;
    overflow: hidden;
  }}
  .section-title {{
    background: #f3f0ec;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: bold;
    color: #28251d;
    border-bottom: 1px solid #dcd9d5;
  }}
  .section-body {{ padding: 14px; }}

  /* ── Gauge row ── */
  .gauge-row {{
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 10px;
  }}
  .gauge-info {{ flex: 1; }}
  .etiqueta-badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
    color: #fff;
    margin-bottom: 6px;
  }}

  /* ── Tabla de datos ── */
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  td, th {{
    padding: 5px 8px;
    border: 1px solid #dcd9d5;
    font-size: 10px;
  }}
  th {{
    background: #f9f8f5;
    font-weight: bold;
    color: #7a7974;
    text-transform: uppercase;
    font-size: 9px;
    letter-spacing: 0.04em;
  }}
  tr:nth-child(even) td {{ background: #fafaf8; }}

  /* ── Barra de tiempo ── */
  .time-bar-wrap {{ margin-top: 8px; }}
  .time-bar-track {{
    height: 10px;
    background: #e6e4df;
    border-radius: 5px;
    overflow: hidden;
    margin-top: 4px;
  }}
  .time-bar-fill {{ height: 100%; border-radius: 5px; }}

  /* ── Flags ── */
  .flags-row {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 5px; }}
  .flag {{
    background: #f3f0ec;
    border: 1px solid #dcd9d5;
    border-radius: 3px;
    padding: 2px 8px;
    font-size: 9px;
    color: #7a7974;
  }}

  /* ── Combinado ── */
  .formula-txt {{
    font-size: 10px;
    color: #7a7974;
    margin-top: 6px;
    font-style: italic;
  }}
  .override-note {{
    font-size: 10px;
    color: #a13544;
    margin-top: 4px;
    font-weight: bold;
  }}

  /* ── Recomendación ── */
  .recom-box {{
    background: #f3f0ec;
    border-left: 3px solid #01696f;
    padding: 8px 12px;
    border-radius: 0 4px 4px 0;
    font-size: 10px;
    color: #28251d;
    margin-top: 10px;
  }}

  /* ── Footer ── */
  .footer {{
    margin-top: 24px;
    border-top: 1px solid #dcd9d5;
    padding-top: 8px;
    font-size: 9px;
    color: #bab9b4;
    text-align: center;
  }}
</style>
</head>
<body>

<!-- ═══ ENCABEZADO ═══ -->
<div class="header">
  <div>
    <div class="header-title">Boletín de Desempeño</div>
    <div class="header-sub">{display_name}</div>
  </div>
  <div class="header-meta">
    <div><strong>Alumno:</strong> {nombre_sujeto or "—"}</div>
    <div><strong>Nivel WS:</strong> {ws}</div>
    <div><strong>Fecha test:</strong> {test_date_raw}</div>
    <div><strong>Nivel actual:</strong> {nivel_actual}</div>
    <div><strong>Punto de inicio:</strong> {punto_inicio}</div>
  </div>
</div>

<!-- ═══ CUANTITATIVO ═══ -->
<div class="section">
  <div class="section-title">① Resultado Cuantitativo</div>
  <div class="section-body">
    <div class="gauge-row">
      <div>{gauge_cuan}</div>
      <div class="gauge-info">
        <div class="etiqueta-badge" style="background:{color_sem};">{etq_cuan_label}</div>
        <table>
          <tr>
            <th>Respuestas correctas</th>
            <th>Porcentaje bruto</th>
            <th>Índice cuantitativo</th>
          </tr>
          <tr>
            <td style="text-align:center;">{correctas} / {total_preg}</td>
            <td style="text-align:center;">{pct_bruta:.1f}%</td>
            <td style="text-align:center; font-weight:bold; color:{color_sem};">{score_cuan:.1f}</td>
          </tr>
        </table>
        <div class="time-bar-wrap">
          <span style="font-size:10px; color:#7a7974;">
            Tiempo: <strong style="color:#28251d;">{study_time:.1f} min</strong>
            / objetivo {target_time:.1f} min
          </span>
          <div class="time-bar-track">
            <div class="time-bar-fill"
                 style="width:{min(100, (study_time/target_time*100) if target_time else 0):.1f}%;
                        background:{color_sem};"></div>
          </div>
        </div>
      </div>
    </div>
    <div class="recom-box">{recom}</div>
  </div>
</div>

<!-- ═══ CUALITATIVO ═══ -->
<div class="section">
  <div class="section-title">② Resultado Cualitativo</div>
  <div class="section-body">
    <div class="gauge-row">
      <div>{gauge_cual}</div>
      <div class="gauge-info">
        <div class="etiqueta-badge" style="background:{color_cual};">{etq_cual_label}</div>
        <p style="font-size:10px; color:#7a7974; margin-top:4px;">
          Evaluación observacional según el método Kumon
        </p>
        {flags_html}
      </div>
    </div>
    {"<p style='font-size:11px;font-weight:bold;color:#28251d;margin-bottom:8px;'>Desglose por área</p>" + barras_html if secciones_q else ""}
  </div>
</div>

<!-- ═══ COMBINADO ═══ -->
<div class="section">
  <div class="section-title">③ Puntaje Combinado (65% cuantitativo + 35% cualitativo)</div>
  <div class="section-body">
    <div class="gauge-row">
      <div>{gauge_comb}</div>
      <div class="gauge-info">
        <div class="etiqueta-badge" style="background:{color_comb};">{etq_comb_label}</div>
        <p class="formula-txt">Fórmula: {formula_txt}</p>
        {override_note}
        <table style="margin-top:10px;">
          <tr>
            <th>Cuantitativo (65%)</th>
            <th>Cualitativo (35%)</th>
            <th>Puntaje final</th>
          </tr>
          <tr>
            <td style="text-align:center;">{score_cuan:.1f}</td>
            <td style="text-align:center;">{pct_cual:.1f}</td>
            <td style="text-align:center; font-weight:bold; font-size:13px; color:{color_comb};">
              {pct_comb:.1f}
            </td>
          </tr>
        </table>
      </div>
    </div>
  </div>
</div>

<!-- ═══ FOOTER ═══ -->
<div class="footer">
  Generado por el sistema de evaluación Kumon &nbsp;·&nbsp; {test_date_raw}
  &nbsp;·&nbsp; Este documento es de uso interno del orientador.
</div>

</body>
</html>"""

# ──────────────────────────────────────────────────────────────
# Helpers internos para PDF fallback (ReportLab)
# ──────────────────────────────────────────────────────────────

def _pdf_safe_text(value: Any) -> str:
    """
    Convierte valores arbitrarios a texto seguro para PDF.
    No asume estructura fija y evita romper el fallback si algún campo cambia.
    """
    if value is None:
        return "N/A"

    if isinstance(value, bool):
        return "Sí" if value else "No"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        return value.strip() or "N/A"

    if isinstance(value, list):
        if not value:
            return "[]"
        return ", ".join(_pdf_safe_text(item) for item in value)

    if isinstance(value, dict):
        if not value:
            return "{}"
        partes: list[str] = []
        for key, val in value.items():
            partes.append(f"{key}: {_pdf_safe_text(val)}")
        return "; ".join(partes)

    return str(value)


def _build_pdf_story_reportlab(
    datos: dict[str, Any],
    result: TestResult,
    template: Any,
    nombre_sujeto: str,
):
    """
    Construye el contenido del PDF usando ReportLab como fallback
    cuando WeasyPrint no puede cargarse o falla al renderizar.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="BoletinTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=10,
    )

    subtitle_style = ParagraphStyle(
        name="BoletinSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10,
    )

    section_title_style = ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.white,
        backColor=colors.HexColor("#1d4ed8"),
        spaceBefore=8,
        spaceAfter=6,
        leftIndent=6,
    )

    cell_label_style = ParagraphStyle(
        name="CellLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )

    cell_value_style = ParagraphStyle(
        name="CellValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#111827"),
    )

    body_style = ParagraphStyle(
        name="BodyTextPdf",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#111827"),
    )

    def make_table_from_mapping(mapping: dict[str, Any]) -> Table:
        rows = []
        for key, value in mapping.items():
            label = escape(str(key).replace("_", " ").capitalize())
            text = escape(_pdf_safe_text(value)).replace("\n", "<br/>")
            rows.append([
                Paragraph(label, cell_label_style),
                Paragraph(text, cell_value_style),
            ])

        if not rows:
            rows = [[
                Paragraph("Sin datos", cell_label_style),
                Paragraph("N/A", cell_value_style),
            ]]

        table = Table(rows, colWidths=[5.2 * cm, 11.8 * cm], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.HexColor("#f8fafc")]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    cuantitativo = datos.get("cuantitativo") or {}
    cualitativo = datos.get("cualitativo") or {}
    combinado = datos.get("combinado") or {}
    gaze = datos.get("gaze")

    encabezado = {
        "Nombre": nombre_sujeto or "N/A",
        "Materia": getattr(template, "subject", "") or "N/A",
        "Nivel": result.ws or getattr(template, "code", "") or "N/A",
        "Plantilla": getattr(template, "display_name", "") or "N/A",
        "Fecha prueba": str(result.test_date or "N/A"),
        "Tipo sujeto": result.tipo_sujeto or "N/A",
    }

    story = [
        Paragraph("Boletín de diagnóstico", title_style),
        Paragraph(
            "Documento generado automáticamente a partir del resultado consolidado del caso.",
            subtitle_style,
        ),
        Paragraph("Datos generales", section_title_style),
        make_table_from_mapping(encabezado),
        Spacer(1, 0.35 * cm),
    ]

    if cuantitativo:
        story.extend([
            Paragraph("Bloque cuantitativo", section_title_style),
            make_table_from_mapping(cuantitativo),
            Spacer(1, 0.35 * cm),
        ])

    if cualitativo:
        story.extend([
            Paragraph("Bloque cualitativo", section_title_style),
            make_table_from_mapping(cualitativo),
            Spacer(1, 0.35 * cm),
        ])

    if combinado:
        story.extend([
            Paragraph("Bloque combinado", section_title_style),
            make_table_from_mapping(combinado),
            Spacer(1, 0.35 * cm),
        ])

    if gaze is not None:
        story.extend([
            Paragraph("Gaze", section_title_style),
            Paragraph(escape(_pdf_safe_text(gaze)), body_style),
            Spacer(1, 0.35 * cm),
        ])

    return story


def _build_pdf_buffer_with_reportlab(
    datos: dict[str, Any],
    result: TestResult,
    template: Any,
    nombre_sujeto: str,
) -> io.BytesIO:
    """
    Genera un PDF válido en memoria usando ReportLab.
    Se usa solo como fallback cuando WeasyPrint no puede ejecutarse.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate

    pdf_buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Boletín de diagnóstico",
        author="automatizacion_kumon",
    )

    story = _build_pdf_story_reportlab(
        datos=datos,
        result=result,
        template=template,
        nombre_sujeto=nombre_sujeto,
    )

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

# ──────────────────────────────────────────────────────────────
# GET /boletin/{result_id}/pdf
# ──────────────────────────────────────────────────────────────

@router.get("/boletin/{result_id}/pdf")
def get_boletin_pdf(result_id: UUID, db: Session = Depends(get_db)):
    """
    Genera el boletín en PDF y lo retorna como descarga directa al dispositivo.
    No guarda el archivo en el servidor — StreamingResponse en memoria.

    Requiere que el cuestionario cualitativo esté completo.

    Estrategia robusta:
      1) Asegura que exista una versión vigente del boletín.
      2) Intenta renderizar con WeasyPrint.
      3) Si WeasyPrint no puede importarse o falla por dependencias nativas,
         usa ReportLab como fallback automático.
      4) Mantiene la misma ruta y el mismo contrato de descarga.
    """
    weasyprint_error: Exception | None = None
    WeasyprintHTML = None

    try:
        from weasyprint import HTML as WeasyprintHTML
    except (ImportError, OSError) as exc:
        weasyprint_error = exc
        WeasyprintHTML = None

    # ── Validar que existe el resultado ──────────────────────────
    result = (
        db.query(TestResult)
        .filter(TestResult.id_result == result_id)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado no encontrado.",
        )

    template = _get_template_or_409(result)

    # ── Validar cuestionario completo ────────────────────────────
    obs = (
        db.query(ObservacionCualitativa)
        .filter(ObservacionCualitativa.id_result == result.id_result)
        .first()
    )
    if not obs or not obs.esta_completo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El PDF solo está disponible cuando el cuestionario cualitativo está completo.",
        )

    bulletin = (
        db.query(Bulletin)
        .filter(Bulletin.id_result == result.id_result)
        .first()
    )

    qual = _get_qualitative_result(db, result)

    if (
        obs.puntaje_cualitativo is not None
        and obs.etiqueta_cualitativa
        and obs.detalle_secciones is not None
    ):
        total_porcentaje = float(obs.puntaje_cualitativo)
        etiqueta_total = obs.etiqueta_cualitativa
        secciones = obs.detalle_secciones
    else:
        try:
            calc = calcular_puntaje_cualitativo(
                subject=template.subject,
                test_code=template.code,
                respuestas=_flatten_respuestas(obs.respuestas),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No fue posible calcular el boletín cualitativo: {exc}",
            ) from exc

        total_porcentaje = float(calc["total_porcentaje"])
        etiqueta_total = calc["etiqueta_total"]
        secciones = calc["secciones"]

    job = result.job

    qnt = QuantitativeInput(
        subject=template.subject,
        test_code=template.code,
        display_name=template.display_name,
        ws=result.ws,
        test_date=job.created_at if job and job.created_at else result.test_date,
        study_time_min=result.study_time_min,
        target_time_min=result.target_time_min,
        correct_answers=result.correct_answers,
        total_questions=result.total_questions,
        percentage=result.percentage,
        current_level=result.current_level,
        starting_point=result.starting_point,
        semaforo=result.semaforo,
        recommendation=result.recommendation,
    )

    cual_input = QualitativeInput(
        total_porcentaje=total_porcentaje,
        etiqueta_total=etiqueta_total,
        secciones=secciones,
        auto_flags=qual.auto_captured_flags if qual and qual.auto_captured_flags else [],
        prefills=qual.prefills if qual and qual.prefills else {},
        gaze_data=qual.gaze_data if qual and qual.gaze_data else None,
    )

    datos = build_report_data(qnt, cual_input)

    if not bulletin:
        bulletin = Bulletin(
            id_result=result.id_result,
            id_template=result.id_template,
        )

    if bulletin.datos_boletin != datos:
        bulletin.datos_boletin = datos
        bulletin.puntaje_cuantitativo = datos.get("cuantitativo", {}).get("score_index")
        bulletin.puntaje_cualitativo = total_porcentaje
        bulletin.puntaje_combinado = datos.get("combinado", {}).get("puntaje")
        bulletin.etiqueta_combinada = datos.get("combinado", {}).get("etiqueta")
        bulletin.status = "ready"
        bulletin.generated_at = datetime.now(timezone.utc)
        db.add(bulletin)
        db.commit()
        db.refresh(bulletin)

    datos = bulletin.datos_boletin or datos

    # ── Obtener nombre del sujeto ────────────────────────────────
    tipo_sujeto = (getattr(result, "tipo_sujeto", "") or "").strip().lower()
    nombre_sujeto = ""
    for obj in [
        getattr(result, "prospecto", None) if tipo_sujeto == "prospecto"
        else getattr(result, "estudiante", None),
        getattr(result, "prospecto", None),
        getattr(result, "estudiante", None),
    ]:
        if obj is None:
            continue
        for attr in ("nombre_completo", "full_name", "display_name", "name"):
            val = getattr(obj, attr, None)
            if val:
                nombre_sujeto = str(val)
                break
        if not nombre_sujeto:
            p = getattr(obj, "primer_nombre", None)
            a = getattr(obj, "primer_apellido", None)
            if p or a:
                nombre_sujeto = " ".join(x for x in [p, a] if x).strip()
        if nombre_sujeto:
            break

    # ── Nombre del archivo sugerido ──────────────────────────────
    nombre_safe = (nombre_sujeto or "sin-nombre").replace("/", "-").replace("\\", "-").replace(" ", "_")
    ws_safe = (result.ws or "test").replace("/", "-")
    fecha_str = str(result.test_date or "").replace("-", "") or "sin-fecha"
    filename = f"boletin_{nombre_safe}_{ws_safe}_{fecha_str}.pdf"

    # ── Generar HTML para WeasyPrint si está disponible ──────────
    html_str = _build_pdf_html(datos, result, template, nombre_sujeto)

    # ── Intentar con WeasyPrint primero ──────────────────────────
    if WeasyprintHTML is not None:
        try:
            pdf_buffer = io.BytesIO()
            WeasyprintHTML(string=html_str).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)

            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
            )
        except Exception as exc:
            weasyprint_error = exc

    # ── Fallback automático a ReportLab ──────────────────────────
    try:
        pdf_buffer = _build_pdf_buffer_with_reportlab(
            datos=datos,
            result=result,
            template=template,
            nombre_sujeto=nombre_sujeto,
        )

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-PDF-Engine": "reportlab-fallback",
            },
        )
    except Exception as fallback_exc:
        detalle_base = "No fue posible generar el PDF."
        if weasyprint_error is not None:
            detalle_base += f" WeasyPrint falló: {weasyprint_error!s}."
        detalle_base += f" Fallback ReportLab falló: {fallback_exc!s}."

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detalle_base,
        )