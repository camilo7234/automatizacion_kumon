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
import copy
import io
from xml.sax.saxutils import escape
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
    BoletinPatchRequest,
    BoletinPatchResponse,
)
from config.cuestionarios import (
    METRICA_A_ITEMS,                    # ← NUEVO: necesario para _build_final_respuestas
    obtener_cuestionario,
    obtener_cuestionario_con_prefill,
    calcular_puntaje_cualitativo,
)
from app.services.report_generator import (
    QuantitativeInput,
    QualitativeInput,
    build_report_data,
)
# ── BUG-A FIX: importar el generador visual completo ──────────────
from app.services.pdf_generator import generate_pdf as _generate_pdf_visual

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


def _build_questions(cuestionario: dict) -> list:
    """
    Convierte la estructura interna del cuestionario
    { secciones: [ { id, titulo, items: [ { id, texto, ... } ] } ] }
    en un array plano de preguntas listo para el frontend:
    [ { id, label, type, options, section_id, section_title, ... } ]
    """
    questions = []
    escala = cuestionario.get("escala", {})
    opciones_escala = [
        {"value": v, "label": escala.get("labels", {}).get(v, str(v))}
        for v in range(
            int(escala.get("min", 1)),
            int(escala.get("max", 5)) + 1,
        )
    ]

    for seccion in cuestionario.get("secciones", []):
        for item in seccion.get("items", []):
            questions.append({
                "id":               item["id"],
                "label":            item.get("texto", item["id"]),
                "type":             "radio",
                "options":          opciones_escala,
                "required":         True,
                "section_id":       seccion["id"],
                "section_title":    seccion.get("titulo", ""),
                "prefill_valor":    item.get("prefill_valor"),
                "prefill_fuente":   item.get("prefill_fuente"),
                "prefill_confianza": item.get("prefill_confianza"),
            })

    return questions


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
    subject: str | None = None,
    test_code: str | None = None,
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    # ── Expandir métricas del video → item_ids ──
    if qual and qual.prefills:
        items_del_cuestionario: set[str] = set()
        if subject and test_code:
            try:
                cuestionario = obtener_cuestionario(subject, test_code)
                for seccion in cuestionario.get("secciones", []):
                    for item in seccion.get("items", []):
                        items_del_cuestionario.add(item["id"])
            except Exception:
                pass

        item_acumulado: dict[str, list[float]] = {}
        item_confianza: dict[str, list[float]] = {}
        item_fuente: dict[str, str] = {}

        for metrica, data in qual.prefills.items():
            if not isinstance(data, dict):
                continue
            valor = data.get("valor")
            confianza = float(data.get("confianza", 0.0))
            fuente = data.get("fuente", "sistema")
            if valor is None:
                continue

            for item_id in METRICA_A_ITEMS.get(metrica, []):
                if items_del_cuestionario and item_id not in items_del_cuestionario:
                    continue
                try:
                    valor_f     = float(valor)
                    confianza_f = float(confianza)
                except (TypeError, ValueError):
                    continue
                item_acumulado.setdefault(item_id, []).append(valor_f)
                item_confianza.setdefault(item_id, []).append(confianza_f)
                item_fuente[item_id] = fuente

        for item_id, valores in item_acumulado.items():
            if not valores:
                continue
            merged[item_id] = {
                "valor": round(sum(valores) / len(valores), 2),
                "confianza": round(sum(item_confianza[item_id]) / len(item_confianza[item_id]), 3),
                "fuente": item_fuente.get(item_id, "sistema"),
            }

    # ── Respuestas guardadas del orientador (prioridad) ──
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
    subject: str | None = None,
    test_code: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Construye el dict final de respuestas mezclando:
    1. Prefills del VIDEO (métricas → expandidas a item_ids)
    2. Respuestas del ORIENTADOR (prioridad absoluta)

    FIX: qual.prefills tiene claves de MÉTRICAS (pausas_largas, ritmo_trabajo…)
    pero calcular_puntaje_cualitativo necesita claves de ITEMS (mantiene_ritmo…).
    Este helper hace la traducción usando METRICA_A_ITEMS.
    """
    final_respuestas: dict[str, dict[str, Any]] = {}

    # ── PASO 1: Obtener qué items pertenecen al cuestionario activo ──
    # Si no tenemos subject/test_code, saltamos la expansión de prefills
    items_del_cuestionario: set[str] = set()
    if subject and test_code:
        try:
            cuestionario = obtener_cuestionario(subject, test_code)
            for seccion in cuestionario.get("secciones", []):
                for item in seccion.get("items", []):
                    items_del_cuestionario.add(item["id"])
        except Exception:
            pass  # Si falla, continúa sin filtrar

    # ── PASO 2: Expandir métricas del video → item_ids ──
    if qual and qual.prefills:
        # Acumulamos valores por item (puede haber múltiples métricas → promedio)
        item_acumulado: dict[str, list[float]] = {}
        item_confianza: dict[str, list[float]] = {}

        for metrica, data in qual.prefills.items():
            if not isinstance(data, dict):
                continue
            valor = data.get("valor")
            confianza = data.get("confianza", 0.0)
            if valor is None:
                continue

            # BUG-1 FIX: convertir a float ANTES de setdefault.
            # El patrón anterior llamaba setdefault (creando la lista vacía)
            # y luego float() dentro del try. Si float() fallaba, el except
            # capturaba la excepción pero la lista vacía ya estaba registrada
            # en item_acumulado, causando ZeroDivisionError en el loop inferior.
            try:
                valor_f     = float(valor)
                confianza_f = float(confianza)
            except (TypeError, ValueError):
                continue  # valor no convertible → saltar métrica completa

            # Obtener los items que mapea esta métrica
            items_metrica = METRICA_A_ITEMS.get(metrica, [])

            for item_id in items_metrica:
                # Solo inyectar items que existen en ESTE cuestionario
                if items_del_cuestionario and item_id not in items_del_cuestionario:
                    continue
                item_acumulado.setdefault(item_id, []).append(valor_f)
                item_confianza.setdefault(item_id, []).append(confianza_f)

        # Promediar y guardar
        for item_id, valores in item_acumulado.items():
            if not valores:  # guardia defensiva: nunca debería pasar con el fix anterior
                continue
            confianzas = item_confianza[item_id]
            valor_promedio     = sum(valores)    / len(valores)
            confianza_promedio = sum(confianzas) / len(confianzas)
            final_respuestas[item_id] = {
                "valor":     round(valor_promedio, 2),
                "fuente":    "sistema",
                "corregido": False,
                "confianza": round(confianza_promedio, 3),
            }

    # ── PASO 3: Respuestas del orientador — prioridad absoluta ──
    for key, value in (payload_respuestas or {}).items():
        valor = value.get("valor") if isinstance(value, dict) and "valor" in value else value
        final_respuestas[key] = {
            "valor":     valor,
            "fuente":    "orientador",
            "corregido": bool(
                qual
                and key in (qual.auto_captured_flags or [])
            ),
            "confianza": 1.0,
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

    prefills = _merge_prefills(qual, obs, subject=template.subject, test_code=template.code)
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

    # ── Resolver nombre del sujeto ───────────────────────────────
    # Misma lógica que get_boletin — fuente única para ambos endpoints.
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

    # ── Respuestas guardadas — aplanadas para que el frontend
    # pueda prerellenar los inputs en modo lectura directamente
    # con { [pregunta_id]: valor_int }
    respuestas_guardadas = _flatten_respuestas(obs.respuestas) if obs else {}

    return CuestionarioResponse(
        result_id=result.id_result,
        subject=template.subject,
        test_code=template.code,
        cuestionario=cuestionario,
        ya_completado=bool(obs and obs.esta_completo),
        tiene_prefills=tiene_prefills,
        prefill_flags=prefill_flags,
        # ── Campos de display agregados ──────────────────────────
        nombre_sujeto=nombre_sujeto or None,
        boletin_habilitado=bool(obs and obs.esta_completo),
        completado_por=obs.completado_por if obs else None,
        completado_at=obs.completado_at if obs else None,
        respuestas_guardadas=respuestas_guardadas,
        # ── Array plano para el frontend ───────────────────────
        questions=_build_questions(cuestionario),
        
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
        subject=template.subject,
        test_code=template.code,
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

    obs.subject                  = template.subject
    obs.test_code                = template.code
    obs.respuestas               = final_respuestas
    obs.puntaje_cualitativo      = calc["total_porcentaje"]
    obs.etiqueta_cualitativa     = calc["etiqueta_total"]
    obs.detalle_secciones        = calc["secciones"]
    obs.completado_por           = payload.completado_por
    obs.completado_at            = datetime.now(timezone.utc)
    obs.observacion_libre        = payload.observacion_libre
    obs.correcciones_orientador  = payload.correcciones_orientador or {}
    obs.esta_completo            = obs._esta_completo_calculado

    db.add(obs)
    db.commit()
    db.refresh(obs)

    # ── Aprendizaje pasivo ── FASE 1 ──────────────────────────────
    # Este bloque NUNCA puede detener el flujo principal.
    # Si learning/ no existe, si la tabla no existe, o si falla
    # cualquier cosa: se loguea, se hace rollback de la sesion
    # y el return ocurre igual.
    try:
        from learning.feedback_collector import collect_feedback
        collect_feedback(
            db=db,
            id_job=result.id_job,
            obs=obs,
            qual=qual,
            result=result,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(
            "collect_feedback fallo para result_id=%s — %s: %s",
            result_id,
            type(exc).__name__,
            exc,
        )

    # ✅ RETURN AGREGADO — resuelve ResponseValidationError (input: None)
    return CuestionarioSubmitResponse(
        id_observacion=obs.id_observacion,
        result_id=obs.id_result,
        subject=obs.subject,
        test_code=obs.test_code,
        puntaje_cualitativo=obs.puntaje_cualitativo,
        etiqueta_cualitativa=obs.etiqueta_cualitativa,
        esta_completo=obs.esta_completo,
        completado_por=obs.completado_por,
        completado_at=obs.completado_at,
        detalle_secciones=obs.detalle_secciones,
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

    # Acceso directo a la columna mapeada — getattr defensivo eliminado
    esta_completo = bool(obs and obs.esta_completo)

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
        # BUG-4B FIX: forzar lectura fresca desde BD para que correcciones
        # del orientador (PATCH) sean siempre visibles en esta respuesta,
        # incluso si el objeto bulletin estaba cacheado en la sesión actual.
        db.refresh(bulletin)
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

    # Acceso directo a columnas mapeadas — getattr defensivo eliminado
    puntaje_cualitativo  = obs.puntaje_cualitativo
    etiqueta_cualitativa = obs.etiqueta_cualitativa
    detalle_secciones    = obs.detalle_secciones

    if (
        puntaje_cualitativo is not None
        and etiqueta_cualitativa
        and detalle_secciones is not None
    ):
        total_porcentaje = float(puntaje_cualitativo)
        etiqueta_total   = etiqueta_cualitativa
        secciones        = detalle_secciones
    else:
        # Fallback: cubre registros anteriores a la migración que no
        # tienen estos campos persistidos. Necesario mientras existan
        # las 19 filas históricas sin recalcular.
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
        etiqueta_total   = calc["etiqueta_total"]
        secciones        = calc["secciones"]

    # Obtener el job para usar la fecha oficial de carga del video
    job = result.job

    # ── Resolver nombre del sujeto ───────────────────────────────
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
        confidence_score=result.confidence_score,
        needs_manual_review=result.needs_manual_review,
        tipo_sujeto=result.tipo_sujeto,
        nombre_sujeto=nombre_sujeto,
    )

    cual_input = QualitativeInput(
        total_porcentaje=total_porcentaje,
        etiqueta_total=etiqueta_total,
        secciones=secciones,
        auto_flags=qual.auto_captured_flags if qual and qual.auto_captured_flags else [],
        prefills=qual.prefills if qual and qual.prefills else {},
        gaze_data=qual.gaze_data if qual and qual.gaze_data else None,
        # ── NUEVOS: campos del orientador ────────────────────────
        observacion_libre       = obs.observacion_libre or None,
        correcciones_orientador = obs.correcciones_orientador or {},
        completado_por          = obs.completado_por or None,
    )

    datos = build_report_data(qnt, cual_input)

    if not bulletin:
        bulletin = Bulletin(
            id_result=result.id_result,
            id_template=result.id_template,
        )

    bulletin.datos_boletin        = datos
    bulletin.puntaje_cuantitativo = datos.get("cuantitativo", {}).get("score_index")
    bulletin.puntaje_cualitativo  = total_porcentaje
    bulletin.puntaje_combinado    = datos.get("combinado", {}).get("puntaje")
    bulletin.etiqueta_combinada   = datos.get("combinado", {}).get("etiqueta")
    bulletin.status               = "ready"
    bulletin.generated_at         = datetime.now(timezone.utc)

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
# PATCH /boletin/{result_id}
# ──────────────────────────────────────────────────────────────
@router.patch("/boletin/{result_id}", response_model=BoletinPatchResponse)
def patch_boletin(
    result_id: UUID,
    payload: BoletinPatchRequest,
    db: Session = Depends(get_db),
):
    """
    Aplica correcciones puntuales sobre los datos del boletín ya generado.

    Cada corrección usa notación dot-path para navegar el dict datos_boletin
    y sobreescribir el valor en esa ruta exacta.

    Ejemplos de campo:
      "cuantitativo.recommendation"
      "cualitativo.secciones.0.puntaje"
      "combinado.narrativa"

    El boletín corregido se persiste en bulletin.datos_boletin, que es la
    fuente que usa get_boletin_pdf() al generar el PDF final.
    No se recalcula nada: solo se escribe lo que el orientador indica.

    BUG-3 FIX: correcciones válidas ya no se pierden si una del lote falla.
    BUG-4A FIX: columnas de índice (puntaje_combinado, etiqueta_combinada,
                nombre_sujeto) se sincronizan con datos_boletin tras cada PATCH.
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

    # BUG-4A FIX: expire fuerza que SQLAlchemy NO use objeto cacheado en sesión.
    # Si se llama PATCH varias veces en la misma sesión, siempre lee desde BD.
    bulletin = (
        db.query(Bulletin)
        .filter(Bulletin.id_result == result.id_result)
        .first()
    )
    if not bulletin or not bulletin.datos_boletin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El boletín no existe aún. Genera el boletín antes de corregirlo.",
        )

    db.refresh(bulletin)  # BUG-4A FIX: forzar lectura fresca antes de copiar

    # Trabajar sobre una copia mutable del JSON persistido
    datos = copy.deepcopy(bulletin.datos_boletin)

    correcciones_aplicadas = 0
    errores: list[str] = []

    for correccion in payload.correcciones:
        # BUG-3 FIX: cada corrección opera sobre una copia aislada del nodo raíz.
        # Si falla la navegación o la escritura, solo ESA corrección se descarta
        # y se acumula en errores — las demás correcciones válidas se conservan
        # en `datos` y llegan al commit normalmente.
        partes = correccion.campo.split(".")
        nodo = datos
        try:
            for parte in partes[:-1]:
                if isinstance(nodo, list):
                    nodo = nodo[int(parte)]
                else:
                    nodo = nodo[parte]

            clave_final = partes[-1]
            if isinstance(nodo, list):
                nodo[int(clave_final)] = correccion.valor_nuevo
            else:
                nodo[clave_final] = correccion.valor_nuevo

            correcciones_aplicadas += 1

        except (KeyError, IndexError, ValueError, TypeError) as exc:
            errores.append(f"'{correccion.campo}': {exc}")
            continue

    # BUG-3 FIX: solo bloqueamos el commit si NO se pudo aplicar ninguna corrección.
    if errores and correcciones_aplicadas == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se pudo aplicar ninguna corrección: {'; '.join(errores)}",
        )

    # Auditoría
    campos_aplicados = [
        c.campo for c in payload.correcciones
        if f"'{c.campo}':" not in " ".join(errores)
    ]
    audit = datos.get("_auditoria_correcciones", [])
    audit.append({
        "corregido_por": payload.corregido_por,
        "corregido_at":  datetime.now(timezone.utc).isoformat(),
        "campos": campos_aplicados,
        "campos_fallidos": errores if errores else None,
    })
    datos["_auditoria_correcciones"] = audit

    # ── BUG-4A FIX: sincronizar columnas de índice con datos corregidos ──
    # Cada vez que el orientador guarda cambios, las columnas escalares de
    # Bulletin deben reflejar lo que hay en datos_boletin, no el snapshot
    # original. Esto garantiza que PDF, UI y queries de BD siempre leen
    # exactamente el mismo estado.
    comb_nuevo  = datos.get("combinado",    {}) or {}
    cuant_nuevo = datos.get("cuantitativo", {}) or {}

    bulletin.datos_boletin     = datos
    bulletin.status            = "ready"
    bulletin.puntaje_combinado = comb_nuevo.get("puntaje",  bulletin.puntaje_combinado)
    bulletin.etiqueta_combinada = comb_nuevo.get("etiqueta", bulletin.etiqueta_combinada)
    bulletin.puntaje_cuantitativo = cuant_nuevo.get("score_index", bulletin.puntaje_cuantitativo)
    # nombre_sujeto en cuant es display — no hay columna de índice propia,
    # pero se preserva en datos_boletin para que PDF lo lea correctamente.

    db.add(bulletin)
    db.commit()
    db.refresh(bulletin)

    datos_final = bulletin.datos_boletin

    mensaje_base = f"Boletín corregido por {payload.corregido_por}. {correcciones_aplicadas} campo(s) actualizado(s)."
    if errores:
        mensaje_base += f" Advertencia — {len(errores)} campo(s) no aplicado(s): {'; '.join(errores)}"

    return BoletinPatchResponse(
        boletin_id=bulletin.id_bulletin,
        result_id=result.id_result,
        subject=template.subject,
        test_code=template.code,
        status=bulletin.status,
        generated_at=bulletin.generated_at,
        cuantitativo=datos_final.get("cuantitativo", {}),
        cualitativo=datos_final.get("cualitativo", {}),
        combinado=datos_final.get("combinado", {}),
        gaze=datos_final.get("gaze"),
        correcciones_aplicadas=correcciones_aplicadas,
        message=mensaje_base,
    )



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
    Genera el boletín en PDF y lo retorna como descarga directa.
    Motor único: ReportLab (pdf_generator.generate_pdf).
    No guarda archivo en disco — StreamingResponse en memoria.
    Requiere que el cuestionario cualitativo esté completo.
    """
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

    qual = _get_qualitative_result(db, result)
    job  = result.job

    # ── Obtener nombre del sujeto ────────────────────────────────
    tipo_sujeto   = (getattr(result, "tipo_sujeto", "") or "").strip().lower()
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

    # ── Leer bulletin con refresh ────────────────────────────────
    bulletin = (
        db.query(Bulletin)
        .filter(Bulletin.id_result == result.id_result)
        .first()
    )
    if bulletin:
        db.refresh(bulletin)

    # ── Resolver datos_boletin ───────────────────────────────────
    if bulletin and bulletin.datos_boletin:
        datos = bulletin.datos_boletin
    else:
        if (
            obs.puntaje_cualitativo is not None
            and obs.etiqueta_cualitativa
            and obs.detalle_secciones is not None
        ):
            total_porcentaje = float(obs.puntaje_cualitativo)
            etiqueta_total   = obs.etiqueta_cualitativa
            secciones        = obs.detalle_secciones
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
            etiqueta_total   = calc["etiqueta_total"]
            secciones        = calc["secciones"]

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
            confidence_score=result.confidence_score,
            needs_manual_review=result.needs_manual_review,
            tipo_sujeto=result.tipo_sujeto,
            nombre_sujeto=nombre_sujeto,
        )

        cual_input = QualitativeInput(
            total_porcentaje=total_porcentaje,
            etiqueta_total=etiqueta_total,
            secciones=secciones,
            auto_flags=qual.auto_captured_flags if qual and qual.auto_captured_flags else [],
            prefills=qual.prefills if qual and qual.prefills else {},
            gaze_data=qual.gaze_data if qual and qual.gaze_data else None,
            # ── NUEVOS: campos del orientador ────────────────────────
            observacion_libre       = obs.observacion_libre or None,
            correcciones_orientador = obs.correcciones_orientador or {},
            completado_por          = obs.completado_por or None,
        )

        datos = build_report_data(qnt, cual_input)

        if not bulletin:
            bulletin = Bulletin(
                id_result=result.id_result,
                id_template=result.id_template,
                datos_boletin=datos,
                puntaje_cuantitativo=datos.get("cuantitativo", {}).get("score_index"),
                puntaje_cualitativo=total_porcentaje,
                puntaje_combinado=datos.get("combinado", {}).get("puntaje"),
                etiqueta_combinada=datos.get("combinado", {}).get("etiqueta"),
                status="ready",
                generated_at=datetime.now(timezone.utc),
            )
            db.add(bulletin)
        else:
            bulletin.datos_boletin        = datos
            bulletin.puntaje_cuantitativo = datos.get("cuantitativo", {}).get("score_index")
            bulletin.puntaje_combinado    = datos.get("combinado", {}).get("puntaje")
            bulletin.etiqueta_combinada   = datos.get("combinado", {}).get("etiqueta")
            bulletin.status               = "ready"
            bulletin.generated_at         = datetime.now(timezone.utc)

        db.commit()
        db.refresh(bulletin)

    # ── Nombre del archivo ───────────────────────────────────────
    job_created_at    = job.created_at if job and job.created_at else None
    nombre_safe       = (nombre_sujeto or "sin-nombre").replace("/", "-").replace("\\", "-").replace(" ", "_")
    ws_safe           = (result.ws or "test").replace("/", "-")
    fecha_str         = job_created_at.strftime("%Y%m%d") if job_created_at else "sin-fecha"
    filename          = f"boletin_{nombre_safe}_{ws_safe}_{fecha_str}.pdf"

    orientador_nombre = obs.completado_por or None
    hubo_correcciones = bool(datos.get("_auditoria_correcciones"))

    # ── Renderizado — ReportLab único ───────────────────────────
    try:
        pdf_buffer = _generate_pdf_visual(
            report_data=datos,
            job_created_at=job_created_at,
            prospecto_nombre=nombre_sujeto or "—",
            output_path=None,
            orientador_nombre=orientador_nombre,
            hubo_correcciones=hubo_correcciones,
        )
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-PDF-Engine": "reportlab",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No fue posible generar el PDF: {exc!s}",
        )
# ──────────────────────────────────────────────────────────────
# GET /boletin/{result_id}/imagen-cualitativa
# ──────────────────────────────────────────────────────────────
@router.get("/boletin/{result_id}/imagen-cualitativa")
def get_imagen_cualitativa(result_id: UUID, db: Session = Depends(get_db)):
    """
    Genera y retorna la imagen de valoración cualitativa Kumon
    como PNG en memoria — sin guardar en disco ni en BD.

    La imagen refleja exactamente datos_boletin.cualitativo tal
    como fue guardado por el orientador (incluyendo correcciones).

    Requiere que el bulletin exista y esté en status 'ready'.
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

    bulletin = (
        db.query(Bulletin)
        .filter(Bulletin.id_result == result.id_result)
        .first()
    )
    if not bulletin or not bulletin.datos_boletin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El boletín no existe aún. Genera el PDF primero.",
        )

    # Siempre leer fresco — garantiza correcciones del orientador
    db.refresh(bulletin)

    datos = bulletin.datos_boletin
    cual  = datos.get("cualitativo") or {}
    cuant = datos.get("cuantitativo") or {}

    if not cual.get("secciones"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El boletín no contiene valoración cualitativa.",
        )

    # Importación local para no romper entornos sin matplotlib
    try:
        from app.services.pdf_generator import _generar_imagen_cualitativa
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Motor de imagen no disponible: {exc!s}",
        )

    nombre_sujeto = cuant.get("nombre_sujeto") or "—"
    fecha_str     = cuant.get("test_date") or "—"

    img_buffer = _generar_imagen_cualitativa(
        cual=cual,
        nombre_sujeto=nombre_sujeto,
        fecha_str=fecha_str,
    )

    nombre_safe = nombre_sujeto.replace("/", "-").replace(" ", "_")
    filename_img = f"cualitativa_{nombre_safe}.png"

    return StreamingResponse(
        img_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_img}"',
        },
    )