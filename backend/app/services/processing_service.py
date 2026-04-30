from __future__ import annotations


"""
app/services/processing_service.py
══════════════════════════════════════════════════════════════════
Orquestador principal del pipeline de procesamiento.


FLUJO COMPLETO:
  0%  → Job recibido, iniciando
  10% → Video abierto, metadatos leídos
  25% → Frame de resumen encontrado + OCR ejecutado
  40% → Cambios de página detectados + actividad de escritura
  55% → Audio analizado (ESP/ING) o saltado (MAT)
  65% → Análisis cualitativo cruzado
  75% → Semáforo y starting_point calculados
  85% → Resultados guardados en BD
  95% → Video eliminado del disco
  100% → Job completado, status=done


MANEJO DE ERRORES:
  Cualquier excepción no capturada → status=error en el job.
  Si el OCR falla con confianza baja → status=manual_review.
  Cada paso actualiza progress_percent en BD para que el
  frontend pueda hacer polling preciso.


ENTIDAD SUJETO:
  El sistema maneja dos tipos de sujeto:
    - Prospecto: persona no matriculada, datos temporales
    - Estudiante: alumno activo en el sistema del admin
  El job tiene XOR: id_prospecto O id_estudiante.
  Este servicio maneja ambos casos transparentemente.


NOTA TÉCNICA — async vs sync:
  ejecutar_pipeline es def (síncronа), NO async def.
  FastAPI BackgroundTasks ejecuta funciones síncronas en un
  ThreadPoolExecutor, liberando el event loop para que el servidor
  pueda responder peticiones de polling mientras el video se procesa.
  Si fuera async def, todas las operaciones bloqueantes (OpenCV,
  EasyOCR, SQLAlchemy) congelarían el event loop completo.
══════════════════════════════════════════════════════════════════
"""


import logging
import traceback
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID


from sqlalchemy.orm import Session


from config.database import SessionLocal
from database.models import (
    ProcessingJob,
    TestTemplate,
    TestResult,
    QualitativeResult,
    ProcessingError,
)


# ── Imports de servicios al nivel de módulo ───────────────────────
# Así los ImportError se detectan al arrancar uvicorn, no durante
# el procesamiento de un video.
from app.services.video_processor import analyze_video, get_video_metadata, cleanup_video
from app.services.ocr_service import extract_summary_frame
from app.services.audio_analyzer import analyze_audio
from app.services.face_analyzer import analyze_face
from app.services.qualitative_analyzer import analyze_qualitative
from app.services.result_calculator import calculate_result


logger = logging.getLogger(__name__)


# Activar solo en desarrollo local para guardar frames de debug.
# Nunca debe estar en True en producción.
_DEBUG_SAVE_FRAMES = False



# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL — Entry point (llamada desde background task)
# ══════════════════════════════════════════════════════════════════
def ejecutar_pipeline(job_id: UUID) -> None:
    """
    Orquesta el pipeline completo para un ProcessingJob.
    Se ejecuta como BackgroundTask de FastAPI.

    IMPORTANTE: Esta función es síncrona (def, no async def).
    FastAPI la ejecuta en un ThreadPoolExecutor, manteniendo el
    event loop libre para responder peticiones de polling mientras
    el video se procesa en segundo plano.

    Args:
        job_id: UUID del ProcessingJob en estado 'queued'
    """
    db: Session = SessionLocal()
    video_path: Optional[str] = None

    def _make_json_safe(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if type(value).__name__ == "date" and hasattr(value, "isoformat"):
            return value.isoformat()

        if isinstance(value, dict):
            return {k: _make_json_safe(v) for k, v in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [_make_json_safe(v) for v in value]

        return str(value)

    try:
        # ──────────────────────────────────────────────────────────
        # PASO 0: Cargar job
        # ──────────────────────────────────────────────────────────
        job = _get_job(db, job_id)
        if not job:
            logger.error(f"Job {job_id} no encontrado en BD.")
            return

        _update_job(db, job, status="processing", progress=5)

        video_path = job.file_path
        if not video_path:
            raise ValueError(f"El job {job.id_job} no tiene file_path definido")

        template = job.template
        if not template:
            template = _get_template_by_id(db, job.id_template)

        if not template:
            raise ValueError(
                f"TestTemplate no encontrado para id_template={job.id_template}"
            )

        subject = template.subject
        test_code = template.code

        logger.info(
            f"Pipeline iniciado | job={job_id} | "
            f"subject={subject} | test_code={test_code}"
        )

        _update_job(db, job, progress=10)

        # ──────────────────────────────────────────────────────────
        # PASO 1: Analizar video
        # ──────────────────────────────────────────────────────────
        meta = get_video_metadata(video_path)
        logger.info(f"Video: {meta}")
        _update_job(db, job, progress=15)

        # CORRECCIÓN: se pasa level=test_code para que video_processor
        # calcule el gap mínimo entre páginas según las páginas esperadas
        # del nivel, evitando falsos cambios de página por sombras o reflejos.
        video_result = analyze_video(video_path, subject, level=test_code)
        _update_job(db, job, progress=40)

        # ──────────────────────────────────────────────────────────
        # VALIDACIÓN CRÍTICA: summary_frame
        # ──────────────────────────────────────────────────────────
        if video_result.summary_frame is None:
            logger.warning(
                f"No se encontró frame de resumen para job_id={job.id_job} "
                f"(video: {video_path}). Se continuará en modo manual_review."
            )

        # ──────────────────────────────────────────────────────────
        # PASO 2: OCR sobre frame de resumen
        # ──────────────────────────────────────────────────────────
        ocr_result = None

        if video_result.summary_frame is not None:
            logger.info(
                f"Frame de resumen disponible: idx={video_result.summary_frame_idx}"
            )

            try:
                # Solo en desarrollo: guardar frame para depuración
                if _DEBUG_SAVE_FRAMES:
                    import cv2
                    cv2.imwrite("debug_summary_frame.jpg", video_result.summary_frame)
                    logger.debug("Frame de resumen guardado como debug_summary_frame.jpg")

                ocr_result = extract_summary_frame(video_result.summary_frame, template=template)

                if ocr_result is not None:
                    logger.info(
                        f"OCR completado: conf={ocr_result.confidence_score} "
                        f"ws={ocr_result.ws} score={ocr_result.percentage}"
                    )
                else:
                    logger.warning(
                        "Se encontró frame de resumen, pero OCR no retornó resultado. "
                        "Se continuará en manual_review."
                    )

            except Exception as ocr_exc:
                logger.warning(
                    f"OCR falló sobre el frame de resumen: {ocr_exc}. "
                    "Se continuará en manual_review."
                )
                ocr_result = None
        else:
            logger.warning(
                "No hay frame de resumen disponible; se omite OCR cuantitativo y "
                "el cuestionario deberá resolver los faltantes."
            )

        _update_job(db, job, progress=55)

        # ──────────────────────────────────────────────────────────
        # PASO 3: Análisis de audio (ESP/ING)
        # ──────────────────────────────────────────────────────────
        audio_result = analyze_audio(
            wav_path=video_result.audio_temp_path,
            subject=subject,
            page_changes=video_result.page_changes,
            video_path=video_path,
            total_frames=video_result.total_frames,
            fps=video_result.fps,
        )
        _update_job(db, job, progress=60)

        # ──────────────────────────────────────────────────────────
        # PASO 4: Análisis de cámara (stub)
        # ──────────────────────────────────────────────────────────
        face_result = analyze_face(
            video_path=video_path,
            total_frames=video_result.total_frames,
            fps=video_result.fps,
            page_changes=video_result.page_changes,
        )
        _update_job(db, job, progress=65)

        # ──────────────────────────────────────────────────────────
        # PASO 5: Análisis cualitativo cruzado
        # ──────────────────────────────────────────────────────────
        qual_result = analyze_qualitative(
            video_result=video_result,
            audio_result=audio_result,
            face_result=face_result,
            subject=subject,
            test_code=test_code,
        )
        _update_job(db, job, progress=72)

        # ──────────────────────────────────────────────────────────
        # PASO 6: Calcular semáforo y starting_point (cuantitativo)
        # ──────────────────────────────────────────────────────────
        ocr_data = (
            _make_json_safe(ocr_result.to_dict())
            if ocr_result
            else {
                "summary_frame_found": video_result.summary_frame is not None,
                "summary_frame_idx": video_result.summary_frame_idx,
                "ocr_executed": video_result.summary_frame is not None,
                "ocr_status": (
                    "skipped_no_summary_frame"
                    if video_result.summary_frame is None
                    else "no_result"
                ),
            }
        )

        if isinstance(ocr_data, dict):
            ocr_data["test_date_ocr"] = (
                ocr_result.test_date.isoformat()
                if ocr_result and ocr_result.test_date
                else None
            )
            ocr_data["test_date_oficial"] = (
                job.created_at.date().isoformat()
                if job.created_at
                else datetime.now(timezone.utc).date().isoformat()
            )
            ocr_data["test_date_source"] = "system_upload_date"

        ocr_data = _make_json_safe(ocr_data)

        calc = calculate_result(
            subject=subject,
            test_code=test_code,
            correct_answers=ocr_result.correct_answers if ocr_result else None,
            total_questions=template.total_items,
            study_time_min=(
                float(ocr_result.study_time_min)
                if ocr_result and ocr_result.study_time_min
                else None
            ),
            target_time_min=(
                float(template.time_pattern_min)
                if template.time_pattern_min
                else None
            ),
            percentage=(
                float(ocr_result.percentage)
                if ocr_result and ocr_result.percentage
                else None
            ),
            level_rules=template.level_rules or {},
            pagina_3_correcta=None,
        )
        _update_job(db, job, progress=78)

        # ──────────────────────────────────────────────────────────
        # PASO 7: Calcular resultado cualitativo e integrado
        # ──────────────────────────────────────────────────────────
        needs_review = (
            (ocr_result is None)
            or ocr_result.needs_manual_review
            or calc.needs_manual_review
        )

        tipo_sujeto = "prospecto" if job.id_prospecto is not None else "estudiante"

        resultado_cualitativo = _calcular_resultado_cualitativo(
            prefills=qual_result.prefills,
            subject=subject,
            test_code=test_code,
        )

        resultado_integrado = _calcular_resultado_integrado(
            semaforo_cuantitativo=calc.semaforo,
            semaforo_cualitativo=resultado_cualitativo["color"],
            study_time_min=(
                float(ocr_result.study_time_min)
                if ocr_result and ocr_result.study_time_min
                else None
            ),
            target_time_min=(
                float(template.time_pattern_min)
                if template.time_pattern_min
                else None
            ),
            percentage=(
                float(calc.percentage) if calc.percentage is not None else None
            ),
            flag_critico=resultado_cualitativo["flag_critico"],
        )

        logger.info(
            f"Cualitativo: color={resultado_cualitativo['color']} "
            f"flags={resultado_cualitativo['flags_total']} "
            f"critico={resultado_cualitativo['flag_critico']}"
        )
        logger.info(
            f"Integrado 65/35: score_final={resultado_integrado['score_final']} "
            f"color_final={resultado_integrado['color_final']} "
            f"override={resultado_integrado['override']}"
        )

        sections_detail = _make_json_safe(
            {
                "cuantitativo": {
                    "color": calc.semaforo,
                    "percentage": (
                        float(calc.percentage)
                        if calc.percentage is not None
                        else None
                    ),
                    "correct_answers": (
                        ocr_result.correct_answers if ocr_result else None
                    ),
                    "total_questions": template.total_items,
                    "study_time_min": (
                        float(ocr_result.study_time_min)
                        if ocr_result and ocr_result.study_time_min
                        else None
                    ),
                    "target_time_min": (
                        float(template.time_pattern_min)
                        if template.time_pattern_min
                        else None
                    ),
                    "starting_point": calc.starting_point,
                    "recommendation": calc.recommendation,
                },
                "cualitativo": {
                    "color": resultado_cualitativo["color"],
                    "flags_total": resultado_cualitativo["flags_total"],
                    "flag_critico": resultado_cualitativo["flag_critico"],
                    "detalles": resultado_cualitativo["detalles"],
                    "subject": subject,
                    "nivel": test_code.upper(),
                },
                "integrado": {
                    "color_final": resultado_integrado["color_final"],
                    "score_cuantitativo": resultado_integrado["score_cuantitativo"],
                    "score_cualitativo": resultado_integrado["score_cualitativo"],
                    "score_final": resultado_integrado["score_final"],
                    "formula": "0.65 × cuantitativo + 0.35 × cualitativo",
                    "override": resultado_integrado["override"],
                    "time_ratio": resultado_integrado["time_ratio"],
                },
            }
        )

        # ──────────────────────────────────────────────────────────
        # PASO 8: Guardar TestResult en BD
        # ──────────────────────────────────────────────────────────
        test_result = TestResult(
            id_job=job.id_job,
            id_template=template.id_template,
            id_prospecto=job.id_prospecto,
            id_estudiante=job.id_estudiante,
            tipo_sujeto=tipo_sujeto,

            # Datos OCR de Class Navi
            ws=ocr_result.ws if ocr_result else None,
            test_date=(
                job.created_at.date()
                if job.created_at
                else datetime.now(timezone.utc).date()
            ),
            study_time_min=ocr_result.study_time_min if ocr_result else None,
            target_time_min=template.time_pattern_min,
            correct_answers=ocr_result.correct_answers if ocr_result else None,
            total_questions=template.total_items,
            percentage=(
                float(calc.percentage)
                if calc.percentage is not None
                else (
                    float(ocr_result.percentage)
                    if ocr_result and ocr_result.percentage
                    else None
                )
            ),

            # Cálculos del backend (cuantitativo)
            current_level=calc.current_level,
            starting_point=calc.starting_point,
            semaforo=calc.semaforo,
            recommendation=calc.recommendation,

            # Confianza OCR
            confidence_score=ocr_result.confidence_score if ocr_result else 0.0,
            needs_manual_review=needs_review,

            # Datos crudos para auditoría
            raw_ocr_data=ocr_data,

            # Resultados cualitativos e integrado para el boletín
            sections_detail=sections_detail,
        )
        db.add(test_result)
        db.flush()

        # ──────────────────────────────────────────────────────────
        # PASO 9: Guardar QualitativeResult en BD
        # ──────────────────────────────────────────────────────────
        qual_db = QualitativeResult(
            id_job=job.id_job,

            # Señales crudas
            time_per_section=qual_result.time_per_section,
            num_rewrites=qual_result.num_rewrites,
            pause_events=qual_result.pause_events,
            activity_ratio=qual_result.activity_ratio,
            stroke_detail=qual_result.stroke_detail,

            # Audio
            vad_segments=qual_result.vad_segments,
            speech_rate=qual_result.speech_rate,
            silence_events=qual_result.silence_events,

            # Cámara (None si desactivada)
            gaze_data=qual_result.gaze_data,

            # Prefills para el formulario
            auto_captured_flags=qual_result.auto_captured_flags,
            prefills=qual_result.prefills,

            # Tiempo de procesamiento del video
            processing_ms=video_result.processing_ms,
        )
        db.add(qual_db)

        # ──────────────────────────────────────────────────────────
        # PASO 10: Actualizar job con el resultado final
        # ──────────────────────────────────────────────────────────
        job.error_message = None
        final_status = "manual_review" if needs_review else "done"
        _update_job(db, job, status=final_status, progress=100, commit=False)

        db.commit()  # ← commit único: test_result + qual_db + estado final del job

        logger.info(
            f"Resultados guardados: id={test_result.id_result} | "
            f"semaforo_cuant={calc.semaforo} | "
            f"semaforo_cual={resultado_cualitativo['color']} | "
            f"color_final={resultado_integrado['color_final']} | "
            f"score_final={resultado_integrado['score_final']} | "
            f"starting={calc.starting_point} | "
            f"review={needs_review}"
        )

        # ──────────────────────────────────────────────────────────
        # PASO 11: Eliminar video del disco
        # ──────────────────────────────────────────────────────────
        cleanup_video(video_path)
        video_path = None

        logger.info(f"Pipeline completado | job={job_id} | status={final_status}")


    except Exception as e:
        logger.error(f"Pipeline ERROR | job={job_id} | {e}", exc_info=True)


        try:
            _register_error(db, job_id, e)
            current_job = db.query(ProcessingJob).filter_by(id_job=job_id).first()
            _update_job(
                db,
                current_job,
                status="error",
                progress=0,
                error=str(e)[:500],
            )
        except Exception as db_err:
            logger.error(f"Error adicional al registrar fallo: {db_err}")


        if video_path:
            try:
                cleanup_video(video_path)
            except Exception:
                pass


    finally:
        db.close()
        
# ══════════════════════════════════════════════════════════════════
# Cálculo cualitativo e integrado (Kumon 65/35)
# ══════════════════════════════════════════════════════════════════


def _calcular_resultado_cualitativo(
    prefills:  dict,
    subject:   str,
    test_code: str,
) -> dict:
    """
    Convierte los prefills capturados por qualitative_analyzer en un
    resultado cualitativo Kumon con semáforo verde/amarillo/rojo.


    Fuentes de flags (métricas ya medidas por el backend):
      num_reescrituras  → esfuerzo / dudas / exactitud
      pausas_largas     → bloqueos / baja fluidez
      ritmo_trabajo     → velocidad y consistencia
      actividad_general → concentración / involucramiento


    Regla de clasificación:
      🟢 Verde:    0–1 flags leves
      🟡 Amarillo: 2–3 flags o ≥1 moderado
      🔴 Rojo:     ≥4 flags o ≥1 crítico
    """
    flags: list[dict] = []
    flag_critico = False


    # ── num_reescrituras ──────────────────────────────────────────
    reescrituras = (prefills.get("num_reescrituras") or {}).get("valor", 0) or 0
    if reescrituras >= 8:
        flags.append({
            "tipo":    "critico",
            "detalle": f"Reescrituras muy altas ({reescrituras})",
        })
        flag_critico = True
    elif reescrituras >= 4:
        flags.append({
            "tipo":    "moderado",
            "detalle": f"Reescrituras frecuentes ({reescrituras})",
        })
    elif reescrituras >= 1:
        flags.append({
            "tipo":    "leve",
            "detalle": f"Algunas reescrituras ({reescrituras})",
        })


    # ── pausas_largas (≥8 s) ─────────────────────────────────────
    pausas = (prefills.get("pausas_largas") or {}).get("valor", 0) or 0
    if pausas > 10:
        flags.append({
            "tipo":    "critico",
            "detalle": f"Bloqueos críticos ({pausas} pausas ≥8s)",
        })
        flag_critico = True
    elif pausas >= 6:
        flags.append({
            "tipo":    "moderado",
            "detalle": f"Bloqueos frecuentes ({pausas} pausas ≥8s)",
        })
    elif pausas >= 1:
        flags.append({
            "tipo":    "leve",
            "detalle": f"Algunas pausas largas ({pausas})",
        })


    # ── ritmo_trabajo ─────────────────────────────────────────────
    ritmo = (prefills.get("ritmo_trabajo") or {}).get("valor", "normal") or "normal"
    if ritmo == "irregular":
        flags.append({"tipo": "moderado", "detalle": "Ritmo de trabajo irregular"})
    elif ritmo == "lento":
        flags.append({"tipo": "moderado", "detalle": "Ritmo de trabajo lento"})


    # ── actividad_general ─────────────────────────────────────────
    actividad = (prefills.get("actividad_general") or {}).get("valor", 1.0)
    if actividad is None:
        actividad = 1.0
    if actividad < 0.05:
        flags.append({
            "tipo":    "critico",
            "detalle": f"Actividad casi nula ({actividad:.3f})",
        })
        flag_critico = True
    elif actividad < 0.20:
        flags.append({
            "tipo":    "moderado",
            "detalle": f"Actividad muy baja ({actividad:.3f})",
        })
    elif actividad < 0.40:
        flags.append({
            "tipo":    "leve",
            "detalle": f"Actividad baja ({actividad:.3f})",
        })


    # ── Clasificación final ───────────────────────────────────────
    total         = len(flags)
    num_moderados = sum(1 for f in flags if f["tipo"] == "moderado")
    num_criticos  = sum(1 for f in flags if f["tipo"] == "critico")


    if flag_critico or num_criticos >= 1 or total >= 4:
        color = "rojo"
    elif total >= 2 or num_moderados >= 1:
        color = "amarillo"
    else:
        color = "verde"


    logger.info(
        f"Cualitativo [{subject} {test_code.upper()}]: "
        f"flags={total} (mod={num_moderados} crit={num_criticos}) → {color}"
    )


    return {
        "color":        color,
        "flags_total":  total,
        "flag_critico": flag_critico,
        "detalles":     [f["detalle"] for f in flags],
    }



def _calcular_resultado_integrado(
    semaforo_cuantitativo: Optional[str],
    semaforo_cualitativo:  str,
    study_time_min:        Optional[float],
    target_time_min:       Optional[float],
    percentage:            Optional[float],
    flag_critico:          bool,
) -> dict:
    """
    Combina cuantitativo (65 %) + cualitativo (35 %) → resultado final Kumon.


    Escala interna:
      verde    → 100 pts
      amarillo →  85 pts
      rojo     →  70 pts


    Reglas de override (sobrescriben la fórmula):
      1. Flag crítico presente              → rojo automático (score = 70)
      2. Tiempo > target_time_min + 1 min  → score techo = 74 → rojo
         Tolerancia de 1 minuto absoluto:
         si el estándar es 10 min, se acepta hasta 11 min sin penalizar.
      3. Porcentaje < 75 %                 → score techo = 74 → rojo
    """
    _SCORE: dict[str, float] = {"verde": 100.0, "amarillo": 85.0, "rojo": 70.0}


    score_cuant = _SCORE.get(semaforo_cuantitativo or "rojo", 70.0)
    score_cual  = _SCORE.get(semaforo_cualitativo, 70.0)
    score_final = round(0.65 * score_cuant + 0.35 * score_cual, 1)


    # time_ratio se conserva solo para auditoría en BD, no controla la decisión.
    time_ratio: Optional[float] = None
    if study_time_min and target_time_min and target_time_min > 0:
        time_ratio = round(study_time_min / target_time_min, 2)


    override: Optional[str] = None
    if flag_critico:
        score_final = 70.0
        override    = "rojo_por_flag_critico"
    elif (
        study_time_min is not None
        and target_time_min is not None
        and study_time_min > target_time_min + 1.0
    ):
        # Tolerancia de 1 minuto absoluto.
        # Ejemplo: target=10 min → penaliza si study_time > 11 min.
        #          target=25 min → penaliza si study_time > 26 min.
        score_final = min(score_final, 74.0)
        override    = "penalizado_por_tiempo"
    elif percentage is not None and percentage < 75.0:
        score_final = min(score_final, 74.0)
        override    = "penalizado_por_puntaje_bajo"


    if score_final >= 90.0:
        color_final = "verde"
    elif score_final >= 75.0:
        color_final = "amarillo"
    else:
        color_final = "rojo"


    return {
        "color_final":        color_final,
        "score_cuantitativo": score_cuant,
        "score_cualitativo":  score_cual,
        "score_final":        score_final,
        "override":           override,
        "time_ratio":         time_ratio,
    }



# ══════════════════════════════════════════════════════════════════
# Helpers de BD
# ══════════════════════════════════════════════════════════════════


def _get_job(db: Session, job_id: UUID) -> Optional[ProcessingJob]:
    """Busca un ProcessingJob por ID."""
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.id_job == job_id)
        .first()
    )



def _get_template_by_id(db: Session, id_template: int) -> Optional[TestTemplate]:
    """
    Busca un TestTemplate por su llave primaria.
    Se usa como respaldo cuando no se quiere depender de relaciones lazy.
    """
    return (
        db.query(TestTemplate)
        .filter(TestTemplate.id_template == id_template)
        .first()
    )



def _update_job(
    db:       Session,
    job:      Optional[ProcessingJob],
    status:   Optional[str] = None,
    progress: Optional[int] = None,
    error:    Optional[str] = None,
    commit:   bool = True,
) -> None:
    """
    Actualiza el estado del job en BD y hace commit por defecto.


    Nota:
      ProcessingJob no tiene result_id.
      El resultado se consulta desde la relación test_result.
    """
    if not job:
        return


    if status:
        job.status = status
        if status in ("done", "error", "manual_review"):
            job.completed_at = datetime.now(timezone.utc)
        if status == "processing" and not job.started_at:
            job.started_at = datetime.now(timezone.utc)


    if progress is not None:
        job.progress_percent = progress


    if error is not None:
        job.error_message = error


    if not commit:
        return


    try:
        db.commit()
    except Exception as e:
        logger.warning(f"No se pudo hacer commit en _update_job: {e}")
        db.rollback()

def _register_error(db: Session, job_id: UUID, exc: Exception) -> None:
    """
    Registra el error en audit.processing_errors.


    Campos reales del modelo:
      - id_job
      - stage
      - error_type
      - error_detail
      - stack_trace
    """
    try:
        err = ProcessingError(
            id_job=job_id,
            stage="general",
            error_type=type(exc).__name__,
            error_detail=str(exc)[:500],
            stack_trace=traceback.format_exc()[:2000],
        )
        db.add(err)
        db.commit()
    except Exception:
        db.rollback()



# ══════════════════════════════════════════════════════════════════
# Utilidades públicas
# ══════════════════════════════════════════════════════════════════


def get_job_status(job_id: UUID, db: Session) -> Optional[dict]:
    """
    Retorna el estado actual de un job.
    Usado por GET /api/v1/jobs/{job_id}.


    REGLAS:
      - NO convertir tipos aquí (eso lo hace el schema).
      - Solo consultar TestResult cuando el job terminó.
    """
    job = _get_job(db, job_id)
    if not job:
        return None


    result_id = None


    if job.status in ("done", "manual_review"):
        result_row = (
            db.query(TestResult.id_result)
            .filter(TestResult.id_job == job.id_job)
            .first()
        )


        if result_row and result_row[0] is not None:
            result_id = result_row[0]  # ← UUID puro, NO str


    return {
        "job_id": job.id_job,  # ← UUID puro
        "status": job.status,
        "progress_percent": job.progress_percent,
        "error_message": job.error_message,
        "result_id": result_id,  # ← UUID o None
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }