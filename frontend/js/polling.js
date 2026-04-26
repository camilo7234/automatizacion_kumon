/* ============================================================
   KUMON · MÓDULO DE POLLING
   Archivo: frontend/js/polling.js
   Depende de: config.js · api.js · state.js · ui.js · formatters.js
   Rol: Loop de consulta a GET /jobs/{id} cada POLL_INTERVAL_MS.
        - Actualiza el pipeline visual paso a paso
        - Muestra barra de progreso y label de estado
        - Detecta timeout global (POLL_TIMEOUT_MS)
        - Al recibir status "done" entrega result_id al callback onJobDone
        - Al recibir status "error" llama onJobError y detiene el loop
        - Al recibir status "manual_review" llama onManualReview y detiene
   ============================================================ */


import {
  JOB_STATUS,
  JOB_TERMINAL_STATES,
  JOB_ACTIVE_STATES,
  POLL_INTERVAL_MS,
  POLL_TIMEOUT_MS,
  MSG,
  PIPELINE_STEPS,
} from './config.js';

import { getJob }                         from './api.js';
import {
  setJobData,
  setResultId,
  setPollingTimer,
  setPollingStart,
  setPollingActive,
  getPollingTimer,
  pollingElapsedMs,
}                                         from './state.js';
import {
  el,
  setAlert,
  clearAlert,
  setProgress,
  show,
  hide,
}                                         from './ui.js';
import {
  prettyStatus,
  tagTypeForStatus,
  prettyProgressLabel,
}                                         from './formatters.js';



/* ══════════════════════════════════════════════
   ESTADO INTERNO DEL MÓDULO
   ══════════════════════════════════════════════ */
let _onJobDone      = null;   // callback(resultId: string) → void
let _onJobError     = null;   // callback(errorMsg: string) → void
let _onManualReview = null;   // callback(resultId: string | null) → void
let _jobId          = null;   // string — job activo



/* ══════════════════════════════════════════════
   PIPELINE — mapa de pasos visuales
   Fuente: PIPELINE_STEPS en config.js
   Orden: upload(0) · queued(1) · processing(2) ·
          done(3) · validated(4) · boletin(5)
   ══════════════════════════════════════════════ */
const STEP_IDS = PIPELINE_STEPS.map(s => s.id);

function _getPipelineStepEl(stepId) {
  return document.querySelector(
    `.pipeline-step[data-step="${stepId}"]`
  );
}

/**
 * Actualiza el estado visual de los pasos del pipeline.
 * @param {string} status — estado actual del job
 */
function _updatePipelineSteps(status) {
  const activeIndex = _statusToStepIndex(status);

  STEP_IDS.forEach((stepId, index) => {
    const stepEl = _getPipelineStepEl(stepId);
    if (!stepEl) return;

    stepEl.classList.remove('active', 'completed', 'error', 'warning');

    if (status === JOB_STATUS.ERROR) {
      if (index < activeIndex)   stepEl.classList.add('completed');
      if (index === activeIndex) stepEl.classList.add('error');
      return;
    }

    if (status === JOB_STATUS.MANUAL_REVIEW) {
      if (index < activeIndex)   stepEl.classList.add('completed');
      if (index === activeIndex) stepEl.classList.add('warning');
      return;
    }

    if (index < activeIndex)   stepEl.classList.add('completed');
    if (index === activeIndex) stepEl.classList.add('active');
  });
}

/**
 * Mapea job.status al índice de paso en el pipeline visual.
 * Fuente: PIPELINE_STEPS = [upload, queued, processing, done, validated, boletin]
 *                           idx 0    idx 1   idx 2       idx 3  idx 4      idx 5
 */
function _statusToStepIndex(status) {
  const map = {
    [JOB_STATUS.PENDING]:       0,  // upload
    [JOB_STATUS.QUEUED]:        1,  // en cola
    [JOB_STATUS.PROCESSING]:    2,  // procesando
    [JOB_STATUS.DONE]:          3,  // resultado listo
    [JOB_STATUS.ERROR]:         2,  // falló durante procesamiento
    [JOB_STATUS.MANUAL_REVIEW]: 2,  // procesamiento terminó con baja confianza
  };
  return map[status] ?? 0;
}



/* ══════════════════════════════════════════════
   BARRA DE PROGRESO DEL JOB
   Fuente: JobStatusResponse — campo progress_percent
   ══════════════════════════════════════════════ */
function _updateJobProgress(data) {
  /* progress_percent es el campo real de JobStatusResponse */
  const pct    = data?.progress_percent ?? null;
  const status = data?.status           ?? '';

  /* Texto adicional del backend — campo real: error_message
     (usado también para mensajes de progreso como "Extrayendo frames...") */
  const backendMsg = data?.error_message ?? null;
  const label      = prettyProgressLabel(status, pct);

  /* Barra de progreso */
  if (pct !== null) {
    setProgress(el.jobProgressFill, el.jobProgressPct, pct);
    if (el.jobProgressFill) {
      el.jobProgressFill.classList.remove('indeterminate');
    }
    show(el.jobProgressBar);
  } else {
    /* Sin porcentaje: animación indeterminada */
    if (el.jobProgressFill) {
      el.jobProgressFill.style.width = '100%';
      el.jobProgressFill.classList.add('indeterminate');
    }
    show(el.jobProgressBar);
  }

  /* Tag de estado */
  if (el.jobStatusValue) {
    el.jobStatusValue.textContent = prettyStatus(status);
    el.jobStatusValue.className   = `tag tag-${tagTypeForStatus(status)}`;
  }

  /* Texto de progreso: mensaje del backend tiene precedencia */
  if (el.jobProgressText) {
    el.jobProgressText.textContent = backendMsg ?? label;
  }
}



/* ══════════════════════════════════════════════
   INIT
   Llamado desde app.js → init()
   Recibe los tres callbacks del flujo.
   ══════════════════════════════════════════════ */
export function initPolling(onJobDone, onJobError, onManualReview) {
  _onJobDone      = onJobDone;
  _onJobError     = onJobError;
  _onManualReview = onManualReview;
}



/* ══════════════════════════════════════════════
   START POLLING
   Llamado desde upload.js vía app.js → onUploadDone
   ══════════════════════════════════════════════ */
export function startPolling(jobId) {
  _jobId = jobId;

  /* Mostrar sección pipeline */
  show(el.pipelineSection);
  clearAlert(el.uploadAlert);
  show(el.jobStatusBlock);

  /* Registrar tiempo de inicio para timeout */
  setPollingStart(new Date());
  setPollingActive(true);

  /* Primera consulta inmediata antes del primer intervalo */
  _tick();

  /* Loop periódico */
  const timer = setInterval(_tick, POLL_INTERVAL_MS);
  setPollingTimer(timer);
}



/* ══════════════════════════════════════════════
   TICK — una consulta al backend
   ══════════════════════════════════════════════ */
async function _tick() {

  /* Verificar timeout global */
  if (pollingElapsedMs() > POLL_TIMEOUT_MS) {
    _stopPolling();
    setAlert(el.resultAlert, MSG.POLLING_TIMEOUT, 'warning');
    _onJobError?.(MSG.POLLING_TIMEOUT);
    return;
  }

  const { ok, data, error } = await getJob(_jobId);

  /* Error de red — no detener el polling, reintentar en el próximo tick */
  if (!ok) {
    if (el.jobProgressText) {
      el.jobProgressText.textContent = `⚠ ${MSG.POLLING_ERROR} — reintentando...`;
    }
    return;
  }

  /* Guardar los datos del job en el estado global */
  setJobData(data);

  const status = data?.status;

  /* Actualizar pipeline y barra */
  _updatePipelineSteps(status);
  _updateJobProgress(data);

  /* ── JOB TERMINADO CON ÉXITO ── */
  if (status === JOB_STATUS.DONE) {
    _stopPolling();

    const resultId = data?.result_id ?? null;

    if (!resultId) {
      /* El job terminó pero no hay result_id — caso anómalo */
      setAlert(
        el.resultAlert,
        'El procesamiento terminó pero no se generó un resultado.',
        'warning'
      );
      _onJobError?.('Sin result_id tras job completado.');
      return;
    }

    setResultId(resultId);
    _onJobDone?.(_jobId);
    return;
  }

  /* ── JOB CON ERROR DE PIPELINE ── */
  if (status === JOB_STATUS.ERROR) {
    _stopPolling();

    /* error_message es el campo real de JobStatusResponse */
    const errorMsg =
      data?.error_message ??
      'El procesamiento falló. Intenta con otro video.';

    setAlert(el.resultAlert, errorMsg, 'danger');
    _onJobError?.(errorMsg);
    return;
  }

  /* ── JOB CON REVISIÓN MANUAL REQUERIDA ── */
  if (status === JOB_STATUS.MANUAL_REVIEW) {
    _stopPolling();

    /* Puede existir un result_id parcial incluso en manual_review */
    const resultId = data?.result_id ?? null;
    if (resultId) {
      setResultId(resultId);
    }

    _onManualReview?.(resultId);
    return;
  }

  /* ── JOB ACTIVO — continuar polling ── */
  // El loop de setInterval seguirá llamando _tick()
}



/* ══════════════════════════════════════════════
   STOP POLLING — detiene el loop
   ══════════════════════════════════════════════ */
function _stopPolling() {
  const timer = getPollingTimer();
  if (timer) {
    clearInterval(timer);
    setPollingTimer(null);
  }
  setPollingActive(false);
}



/* ══════════════════════════════════════════════
   RESET PÚBLICO
   Llamado desde app.js → resetAll()
   ══════════════════════════════════════════════ */
export function resetPolling() {
  _stopPolling();
  _jobId = null;

  /* Limpiar pipeline visual */
  STEP_IDS.forEach((stepId) => {
    const stepEl = _getPipelineStepEl(stepId);
    stepEl?.classList.remove('active', 'completed', 'error', 'warning');
  });

  /* Limpiar barra y tag */
  if (el.jobStatusValue) {
    el.jobStatusValue.textContent = '';
    el.jobStatusValue.className   = 'tag';
  }
  if (el.jobProgressFill) {
    el.jobProgressFill.style.width = '0%';
    el.jobProgressFill.classList.remove('indeterminate');
  }
  if (el.jobProgressPct)  el.jobProgressPct.textContent  = '';
  if (el.jobProgressText) el.jobProgressText.textContent = '';

  hide(el.pipelineSection);
  hide(el.jobStatusBlock);
}