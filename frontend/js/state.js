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


import { JOB_TERMINAL_STATES } from './config.js';


/* ══════════════════════════════════════════════
   ESTADO INTERNO
   Prefijo _ indica que es privado a este módulo
   ══════════════════════════════════════════════ */
const _state = {

  /* ── JOB ACTIVO ── */
  currentJobId:    null,   // string | null — UUID del job en BD
  pollingTimer:    null,   // setInterval ref
  pollingStart:    null,   // Date — para calcular timeout

  /* ── RESULTADO DEL VIDEO ── */
  currentResultId: null,   // string | null — UUID de TestResult en BD
  lastJobData:     null,   // objeto completo de GET /jobs/{job_id}   → JobStatusResponse
  lastResultData:  null,   // objeto completo de GET /results/job/{jobId} → TestResultResponse

  /* ── CUESTIONARIO ── */
  lastCuestionarioData: null,  // objeto de GET /cuestionario/{resultId} → CuestionarioResponse
  cuestionarioLoaded:   false, // true cuando el orientador completó el cuestionario (POST exitoso)

  /* ── BOLETÍN ── */
  lastBoletinData: null,   // objeto de GET /boletin/{resultId} → BoletinResponse

  /* ── UI FLAGS ── */
  isUploading:     false,  // true mientras el video viaja al backend
  uploadProgress:  0,      // número 0–100 — progreso del upload (XHR onProgress)
  isPolling:       false,  // true mientras el polling está activo
};



/* ══════════════════════════════════════════════
   GETTERS
   ══════════════════════════════════════════════ */

export const getJobId             = () => _state.currentJobId;
export const getResultId          = () => _state.currentResultId;
export const getPollingTimer      = () => _state.pollingTimer;
export const getPollingStart      = () => _state.pollingStart;
export const getJobData           = () => _state.lastJobData;
export const getResultData        = () => _state.lastResultData;
export const getCuestionario      = () => _state.lastCuestionarioData;
export const isCuestionarioDone   = () => _state.cuestionarioLoaded;
export const getBoletinData       = () => _state.lastBoletinData;
export const isUploading          = () => _state.isUploading;
export const getUploadProgress    = () => _state.uploadProgress;
export const isPolling            = () => _state.isPolling;



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

/**
 * Guarda el TestResultResponse completo.
 * Fuente: backend/app/schemas/result.py — TestResultResponse
 * El campo identificador real es id_result (UUID).
 */
export function setResultData(data) {
  _state.lastResultData  = data;
  /* id_result es el campo real de TestResultResponse */
  _state.currentResultId = data?.id_result ?? _state.currentResultId;
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

export function setUploadProgress(pct) {
  _state.uploadProgress = Number(pct) || 0;
}

export function setPollingActive(val) {
  _state.isPolling = Boolean(val);
}



/* ══════════════════════════════════════════════
   HELPERS DERIVADOS
   Calculados a partir del estado — no almacenados
   ══════════════════════════════════════════════ */

/**
 * true si hay un job activo y aún no terminó.
 * Usa JOB_TERMINAL_STATES para incluir todos los estados
 * terminales: done, error, manual_review.
 */
export function jobIsRunning() {
  const status = _state.lastJobData?.status;
  return Boolean(
    _state.currentJobId &&
    status &&
    !JOB_TERMINAL_STATES.has(status)
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

/**
 * Retorna el resultId disponible.
 * Fuente: campo id_result de TestResultResponse.
 */
export function resolveResultId() {
  return (
    _state.currentResultId ??
    _state.lastResultData?.id_result ??
    null
  );
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
  _state.uploadProgress        = 0;
  _state.isPolling             = false;
}



/* ══════════════════════════════════════════════
   DEBUG (solo desarrollo)
   Expone el estado en consola si hace falta
   ══════════════════════════════════════════════ */
export function debugState() {
  if (import.meta?.env?.MODE === 'production') return;
  console.table({
    jobId:             _state.currentJobId,
    resultId:          _state.currentResultId,
    jobStatus:         _state.lastJobData?.status ?? '—',
    uploadProgress:    _state.uploadProgress,
    hasResult:         hasResult(),
    cuestionarioDone:  _state.cuestionarioLoaded,
    hasBoletin:        hasBoletin(),
    isPolling:         _state.isPolling,
    pollingElapsedSec: Math.round(pollingElapsedMs() / 1000),
  });
}