/* ============================================================
   KUMON · ESTADO GLOBAL
   Archivo: frontend/js/state.js
   Depende de: config.js
   Rol: Objeto central de estado de la app. Todos los módulos
        leen y escriben el estado SOLO a través de los
        getters y setters exportados — nunca acceden al
        objeto _state directamente desde afuera.
        Esto garantiza que cualquier cambio de estado
        sea rastreable y predecible.
   ============================================================ */

import { JOB_STATUS } from './config.js';

/* ══════════════════════════════════════════════
   ESTADO INTERNO
   Prefijo _ indica que es privado a este módulo
   ══════════════════════════════════════════════ */
const _state = {

  /* ── JOB ACTIVO ── */
  currentJobId:    null,   // string | null — ID del job en BD
  pollingTimer:    null,   // setInterval ref
  pollingStart:    null,   // Date — para calcular timeout

  /* ── RESULTADO DEL VIDEO ── */
  currentResultId: null,   // string | null — ID de TestResult en BD
  lastJobData:     null,   // objeto completo de GET /jobs/{id}
  lastResultData:  null,   // objeto completo de GET /results/job/{jobId}

  /* ── CUESTIONARIO ── */
  lastCuestionarioData: null,  // objeto de GET /cuestionario/{resultId}
  cuestionarioLoaded:   false, // true cuando el orientador completó y se generó boletín

  /* ── BOLETÍN ── */
  lastBoletinData: null,   // objeto de GET /boletin/{resultId}

  /* ── UI FLAGS ── */
  isUploading:     false,  // true mientras el video viaja al backend
  isPolling:       false,  // true mientras el polling está activo
};


/* ══════════════════════════════════════════════
   GETTERS
   ══════════════════════════════════════════════ */

export const getJobId        = ()  => _state.currentJobId;
export const getResultId     = ()  => _state.currentResultId;
export const getPollingTimer  = ()  => _state.pollingTimer;
export const getPollingStart  = ()  => _state.pollingStart;
export const getJobData       = ()  => _state.lastJobData;
export const getResultData    = ()  => _state.lastResultData;
export const getCuestionario  = ()  => _state.lastCuestionarioData;
export const isCuestionarioDone = () => _state.cuestionarioLoaded;
export const getBoletinData   = ()  => _state.lastBoletinData;
export const isUploading      = ()  => _state.isUploading;
export const isPolling        = ()  => _state.isPolling;


/* ══════════════════════════════════════════════
   SETTERS
   ══════════════════════════════════════════════ */

export function setJobId(id) {
  _state.currentJobId = id;
}

export function setResultId(id) {
  _state.currentResultId = id;
}

export function setPollingTimer(timer) {
  _state.pollingTimer = timer;
}

export function setPollingStart(date) {
  _state.pollingStart = date;
}

export function setJobData(data) {
  _state.lastJobData = data;
}

export function setResultData(data) {
  _state.lastResultData    = data;
  _state.currentResultId   = data?.id ?? _state.currentResultId;
}

export function setCuestionario(data) {
  _state.lastCuestionarioData = data;
}

export function setCuestionarioDone(val) {
  _state.cuestionarioLoaded = Boolean(val);
}

export function setBoletinData(data) {
  _state.lastBoletinData = data;
}

export function setUploading(val) {
  _state.isUploading = Boolean(val);
}

export function setPollingActive(val) {
  _state.isPolling = Boolean(val);
}


/* ══════════════════════════════════════════════
   HELPERS DERIVADOS
   Calculados a partir del estado — no almacenados
   ══════════════════════════════════════════════ */

/** true si hay un job activo y aún no terminó */
export function jobIsRunning() {
  const status = _state.lastJobData?.status;
  return Boolean(
    _state.currentJobId &&
    status &&
    status !== JOB_STATUS.DONE &&
    status !== JOB_STATUS.ERROR
  );
}

/** true si el resultado ya llegó del backend */
export function hasResult() {
  return Boolean(_state.lastResultData);
}

/** true si el boletín ya fue generado */
export function hasBoletin() {
  return Boolean(_state.lastBoletinData);
}

/** Retorna el resultId del estado o del último resultado cargado */
export function resolveResultId() {
  return _state.currentResultId
    ?? _state.lastResultData?.id
    ?? null;
}

/** Cuántos ms lleva el polling activo */
export function pollingElapsedMs() {
  if (!_state.pollingStart) return 0;
  return Date.now() - _state.pollingStart.getTime();
}


/* ══════════════════════════════════════════════
   RESET
   Limpia el estado para una nueva sesión de
   procesamiento sin recargar la página.
   Se llama desde app.js → resetAll()
   ══════════════════════════════════════════════ */
export function resetState() {
  /* Detener polling si estaba activo */
  if (_state.pollingTimer) {
    clearInterval(_state.pollingTimer);
  }

  _state.currentJobId          = null;
  _state.pollingTimer          = null;
  _state.pollingStart          = null;
  _state.currentResultId       = null;
  _state.lastJobData           = null;
  _state.lastResultData        = null;
  _state.lastCuestionarioData  = null;
  _state.cuestionarioLoaded    = false;
  _state.lastBoletinData       = null;
  _state.isUploading           = false;
  _state.isPolling             = false;
}


/* ══════════════════════════════════════════════
   DEBUG (solo desarrollo)
   Expone el estado en consola si hace falta
   ══════════════════════════════════════════════ */
export function debugState() {
  if (import.meta?.env?.MODE === 'production') return;
  console.table({
    jobId:              _state.currentJobId,
    resultId:           _state.currentResultId,
    jobStatus:          _state.lastJobData?.status ?? '—',
    hasResult:          hasResult(),
    cuestionarioDone:   _state.cuestionarioLoaded,
    hasBoletin:         hasBoletin(),
    isPolling:          _state.isPolling,
    pollingElapsedSec:  Math.round(pollingElapsedMs() / 1000),
  });
}