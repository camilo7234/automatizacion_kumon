/* ============================================================
   KUMON · ORQUESTADOR PRINCIPAL
   Archivo: frontend/js/app.js
   Tipo: ES Module — importado en index.html como
         <script type="module" src="./js/app.js"></script>
   Rol: Punto de entrada único de la aplicación.
        - Inicializa todos los módulos con sus callbacks
        - Define el flujo completo de 5 pasos:
          upload → polling → resultado → cuestionario → boletín
        - Gestiona el health check periódico del backend
        - Expone resetAll() para el botón "Nueva sesión"
        NO contiene lógica de negocio — solo orquesta.
   ============================================================ */

/* ── Módulos propios ── */
import { initEl, el, updateBackendDot, show, hide } from './ui.js';
import { resetState }                               from './state.js';
import { checkHealth }                              from './api.js';
import { initUpload,      resetUpload }             from './upload.js';
import { initPolling,     startPolling,  resetPolling }   from './polling.js';
import { initResultado,   loadResultado, resetResultado } from './resultado.js';
import { initCuestionario,loadCuestionario,resetCuestionario } from './cuestionario.js';
import { initBoletin,     renderBoletin, loadBoletin, resetBoletin } from './boletin.js';

/* ── Constantes ── */
const HEALTH_CHECK_INTERVAL_MS = 30_000;   // cada 30 s


/* ══════════════════════════════════════════════
   INIT — punto de arranque de la app
   Llamado una sola vez en DOMContentLoaded
   ══════════════════════════════════════════════ */
function init() {

  /* 1. Resolver todas las referencias DOM */
  initEl();

  /* 2. Inicializar módulos con sus callbacks de flujo */
  initUpload(_onUploadDone);

  initPolling(
    _onJobDone,    // job terminó con éxito → result_id
    _onJobError    // job terminó con error
  );

  initResultado(_onResultReady);

  initCuestionario(_onBoletinReady);

  initBoletin();   // los botones se bindean internamente

  /* 3. Botón "Nueva sesión" */
  el.resetBtn?.addEventListener('click', resetAll);

  /* 4. Health check inicial + periódico */
  _runHealthCheck();
  setInterval(_runHealthCheck, HEALTH_CHECK_INTERVAL_MS);
}


/* ══════════════════════════════════════════════
   FLUJO — 5 callbacks encadenados
   Cada uno es llamado por el módulo anterior
   cuando su tarea termina con éxito.
   ══════════════════════════════════════════════ */

/**
 * PASO 1 → 2
 * upload.js llama este callback cuando el video
 * se subió correctamente y recibió un job_id.
 * Arranca el polling.
 */
function _onUploadDone(jobId) {
  startPolling(jobId);
}

/**
 * PASO 2 → 3
 * polling.js llama este callback cuando
 * job.status === "done" y hay un result_id.
 * Carga y renderiza el resultado del video.
 */
function _onJobDone(resultId) {
  loadResultado(resultId);
}

/**
 * PASO 2 (error)
 * polling.js llama este callback cuando
 * job.status === "error" o se agotó el timeout.
 * Muestra la sección de resultado con el error
 * para que el orientador vea el mensaje.
 */
function _onJobError(errorMsg) {
  show(el.resultSection);
  console.error('[app] Job error:', errorMsg);
}

/**
 * PASO 3 → 4
 * resultado.js llama este callback cuando
 * el TestResult fue renderizado correctamente.
 * Carga el cuestionario de validación cualitativa.
 */
function _onResultReady() {
  loadCuestionario();
}

/**
 * PASO 4 → 5
 * cuestionario.js llama este callback cuando
 * el POST /cuestionario retornó el BoletinResponse.
 * Renderiza el boletín directamente con esos datos
 * sin hacer otro GET — el dato ya está en memoria.
 */
function _onBoletinReady(boletinData) {
  renderBoletin(boletinData);
}


/* ══════════════════════════════════════════════
   HEALTH CHECK
   Verifica si el backend responde.
   Actualiza el dot verde/rojo/amarillo del header.
   ══════════════════════════════════════════════ */
async function _runHealthCheck() {
  updateBackendDot('pending');

  const { ok } = await checkHealth();

  updateBackendDot(ok ? 'ok' : 'error');
}


/* ══════════════════════════════════════════════
   RESET ALL — "Nueva sesión"
   Limpia TODO el estado y la UI para procesar
   un nuevo video sin recargar la página.
   ══════════════════════════════════════════════ */
function resetAll() {
  /* Estado global */
  resetState();

  /* Cada módulo limpia su propio estado y UI */
  resetUpload();
  resetPolling();
  resetResultado();
  resetCuestionario();
  resetBoletin();

  /* Volver a mostrar solo la sección de upload */
  show(el.uploadSection);

  /* Health check inmediato tras reset */
  _runHealthCheck();
}


/* ══════════════════════════════════════════════
   ARRANQUE
   ══════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', init);