/* ============================================================
   KUMON · MÓDULO DE POLLING
   Archivo: frontend/js/polling.js
   Depende de: config.js · api.js · state.js · ui.js · formatters.js
   Rol: Loop de consulta a GET /jobs/{id} cada POLL_INTERVAL_MS.
        - Actualiza el pipeline visual paso a paso
        - Muestra barra de progreso y label de estado
        - Detecta timeout global (POLL_TIMEOUT_MS)
        - Al recibir status "done" entrega result_id
          al módulo de resultado via callback onJobDone
        - Al recibir status "error" muestra el mensaje
          y detiene el loop
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
let _onJobDone  = null;   // callback(resultId: string) → void
let _onJobError = null;   // callback(errorMsg: string) → void
let _jobId      = null;   // string — job activo


/* ══════════════════════════════════════════════
   PIPELINE — mapa de pasos visuales
   Cada paso tiene su elemento DOM cacheado
   ══════════════════════════════════════════════ */
const STEP_IDS = PIPELINE_STEPS.map(s => s.id);

function _getPipelineStepEl(stepId) {
  return document.querySelector(
    `.pipeline-step[data-step="${stepId}"]`
  );
}

/**
 * Actualiza el estado visual de los pasos del pipeline.
 * status: estado actual del job
 */
function _updatePipelineSteps(status) {
  const activeIndex = _statusToStepIndex(status);

  STEP_IDS.forEach((stepId, index) => {
    const stepEl = _getPipelineStepEl(stepId);
    if (!stepEl) return;

    stepEl.classList.remove('active', 'completed', 'error');

    if (status === JOB_STATUS.ERROR) {
      if (index < activeIndex)  stepEl.classList.add('completed');
      if (index === activeIndex) stepEl.classList.add('error');
      return;
    }

    if (index < activeIndex)   stepEl.classList.add('completed');
    if (index === activeIndex) stepEl.classList.add('active');
  });
}

/**
 * Mapea job.status al índice de paso en el pipeline visual.
 */
function _statusToStepIndex(status) {
  const map = {
    [JOB_STATUS.PENDING]:    0,   // upload
    [JOB_STATUS.QUEUED]:     1,   // procesando (en espera)
    [JOB_STATUS.PROCESSING]: 1,   // procesando
    [JOB_STATUS.DONE]:       2,   // resultado
    [JOB_STATUS.ERROR]:      1,   // error en procesamiento
  };
  return map[status] ?? 0;
}


/* ══════════════════════════════════════════════
   BARRA DE PROGRESO DEL JOB
   ══════════════════════════════════════════════ */
function _updateJobProgress(data) {
  const pct    = data?.progress ?? null;
  const status = data?.status   ?? '';
  const label  = prettyProgressLabel(status, pct);

  /* Barra de progreso */
  if (pct !== null) {
    setProgress(el.jobProgressFill, el.jobProgressPct, pct);
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
    el.jobStatusValue.className   =
      `tag tag-${tagTypeForStatus(status)}`;
  }

  /* Texto de progreso */
  if (el.jobProgressText) {
    el.jobProgressText.textContent = label;
  }

  /* Mensaje adicional del backend (ej: "Extrayendo frames...") */
  if (data?.message && el.jobProgressText) {
    el.jobProgressText.textContent = data.message;
  }
}


/* ══════════════════════════════════════════════
   INIT
   Llamado desde app.js → init()
   ══════════════════════════════════════════════ */
export function initPolling(onJobDone, onJobError) {
  _onJobDone  = onJobDone;
  _onJobError = onJobError;
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

  /* Error de red */
  if (!ok) {
    /* No detener el polling por un error puntual de red —
       solo mostrar un aviso temporal y reintentar */
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
    _onJobDone?.(resultId);
    return;
  }

  /* ── JOB CON ERROR ── */
  if (status === JOB_STATUS.ERROR) {
    _stopPolling();

    const errorMsg =
      data?.error   ??
      data?.message ??
      'El procesamiento falló. Intenta con otro video.';

    setAlert(el.resultAlert, errorMsg, 'danger');
    _onJobError?.(errorMsg);
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
    stepEl?.classList.remove('active', 'completed', 'error');
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