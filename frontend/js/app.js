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
import {
  initEl, el,
  updateBackendDot,
  show, hide,
  setAlert,
}                                                           from './ui.js';
import { resetState, getResultId }                         from './state.js';
import { checkHealth }                                     from './api.js';
import { initUpload,       resetUpload }                   from './upload.js';
import { initPolling,      startPolling,   resetPolling }  from './polling.js';
import { initResultado,    loadResultado,  resetResultado } from './resultado.js';
import { initCuestionario, loadCuestionario, resetCuestionario } from './cuestionario.js';
import { initBoletin,      loadBoletin,    resetBoletin }  from './boletin.js';

import { MSG }                                             from './config.js';


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
    _onJobDone,       // job terminó con éxito → result_id disponible
    _onJobError,      // job terminó con error del pipeline o timeout
    _onManualReview   // job terminó con status "manual_review" — OCR requiere revisión
  );

  initResultado(_onResultReady);

  initCuestionario(_onCuestionarioDone);

  initBoletin();   // los botones se bindean internamente

  /* 3. Botón "Nueva sesión" */
  el.resetBtn?.addEventListener('click', resetAll);

  /* 4. Health check inicial + periódico */
  _runHealthCheck();
  setInterval(_runHealthCheck, HEALTH_CHECK_INTERVAL_MS);
}




/* ══════════════════════════════════════════════
   FLUJO — callbacks encadenados
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
function _onJobDone(jobId) {
  loadResultado(jobId);
}


/**
 * PASO 2 (error de pipeline o timeout de polling)
 * polling.js llama este callback cuando
 * job.status === "error" o se agotó el timeout.
 * Muestra la sección de resultado con el mensaje
 * de error para que el orientador vea qué pasó.
 */
function _onJobError(errorMsg) {
  show(el.resultSection);
  setAlert(el.resultAlert, errorMsg ?? MSG.POLLING_ERROR, 'danger');
  console.error('[app] Job error:', errorMsg);
}


/**
 * PASO 2 (revisión manual requerida)
 * polling.js llama este callback cuando job.status === "manual_review".
 *
 * CONTRATOS:
 *   - resultId: string → OCR terminó, TestResult existe, cargar resultado normal
 *   - resultId: null   → race condition agotada o TestResult no disponible,
 *                        saltar directo al cuestionario inteligente
 *
 * El cuestionario fue diseñado para operar sin datos cuantitativos —
 * los prefills del video (pausas, ritmo, reescrituras) siempre existen
 * porque vienen de QualitativeResult, no de TestResult.
 */
function _onManualReview(resultId) {
  show(el.resultSection);

  if (resultId) {
    /* Caso normal: result_id llegó, cargar resultado parcial */
    setAlert(el.resultAlert, MSG.POLLING_MANUAL_REVIEW, 'warning');
    loadResultado(resultId);
    return;
  }

  /* Caso sin result_id: el OCR no pudo leer la hoja o el TestResult
     no está disponible aún. Informar al orientador y avanzar directo
     al cuestionario — el sistema no se para. */
  setAlert(
    el.resultAlert,
    'No se pudo leer la hoja de resultados automáticamente. ' +
    'Completa el cuestionario de observación para continuar.',
    'warning'
  );
  loadCuestionario();
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
 * POST /cuestionario terminó con éxito
 * (CuestionarioSubmitResponse.boletin_habilitado === true).
 *
 * NO se pasan los datos del submit — esos son CuestionarioSubmitResponse,
 * no BoletinResponse. Se dispara loadBoletin() para obtener el
 * BoletinResponse completo (cuantitativo + cualitativo + combinado).
 */
function _onCuestionarioDone() {
  const resultId = getResultId();
  if (!resultId) {
    console.error('[app] _onCuestionarioDone: resultId no disponible en estado.');
    return;
  }
  loadBoletin(resultId);
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
   app.js garantiza el estado visual inicial
   independientemente de lo que hagan los módulos.
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

  /* Garantizar visibilidad inicial desde el orquestador */
  show(el.uploadSection);
  hide(el.pipelineSection);
  hide(el.resultSection);
  hide(el.cuestionarioSection);
  hide(el.boletinSection);

  /* Health check inmediato tras reset */
  _runHealthCheck();
}




/* ══════════════════════════════════════════════
   ARRANQUE
   ══════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', init);