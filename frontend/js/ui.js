/* ============================================================
   KUMON · REFERENCIAS DOM Y UTILIDADES DE UI
   Archivo: frontend/js/ui.js
   Depende de: config.js
   Rol: Objeto central el.* con todas las referencias DOM.
        Funciones utilitarias de UI: setAlert, setTag,
        show/hide, setLoadingUpload, updateBackendDot.
        Ningún otro módulo usa document.getElementById
        directamente — solo importa desde aquí.
   ============================================================ */


import { MSG } from './config.js';


/* ══════════════════════════════════════════════
   REFERENCIAS DOM — objeto el.*
   Se inicializa una vez en init() de app.js.
   Cada key mapea exactamente con un id del HTML.
   ══════════════════════════════════════════════ */
export const el = {

  /* ── BACKEND STATUS (header) ── */
  backendDot:           null,  // .backend-status-dot
  backendLabel:         null,  // .backend-status-text


  /* ── SECCIÓN UPLOAD ── */
  uploadSection:        null,  // #uploadSection
  uploadForm:           null,  // #uploadForm
  uploadInput:          null,  // #uploadInput           (input type=file)
  uploadDropZone:       null,  // #uploadDropZone
  uploadDropFilename:   null,  // #uploadDropFilename
  uploadProgressWrap:   null,  // #uploadProgressWrap
  uploadProgressFill:   null,  // #uploadProgressFill
  uploadProgressPct:    null,  // #uploadProgressPct
  uploadAlert:          null,  // #uploadAlert
  uploadBtn:            null,  // #uploadBtn
  resetBtn:             null,  // #resetBtn
  /* Campos del formulario — alineados con VideoUploadForm del backend */
  subjectInput:         null,  // #subjectInput          → form field: subject
  testCodeInput:        null,  // #testCodeInput         → form field: test_code
  nombreCompletoInput:  null,  // #nombreCompletoInput   → form field: nombre_completo


  /* ── PIPELINE ── */
  pipelineSection:      null,  // #pipelineSection
  pipelineSteps:        null,  // NodeList de .pipeline-step (se llena en initEl)
  jobStatusBlock:       null,  // #jobStatusBlock
  jobStatusValue:       null,  // #jobStatusValue
  jobProgressBar:       null,  // #jobProgressBar        (contenedor — toggle visibilidad)
  jobProgressFill:      null,  // #jobProgressFill
  jobProgressPct:       null,  // #jobProgressPct
  jobProgressText:      null,  // #jobProgressText


  /* ── RESULTADO ── */
  resultSection:        null,  // #resultSection
  resultAlert:          null,  // #resultAlert
  resultBlock:          null,  // #resultBlock
  resultHeroStudent:    null,  // #resultHeroStudent
  resultHeroLevel:      null,  // #resultHeroLevel
  heroConfidence:       null,  // #heroConfidence
  heroConfidencePct:    null,  // #heroConfidencePct
  manualReviewBanner:   null,  // #manualReviewBanner
  semaforoBlock:        null,  // #semaforoBlock
  semaforoIcon:         null,  // #semaforoIcon
  semaforoLabel:        null,  // #semaforoLabel
  kpiGrid:              null,  // #kpiGrid
  detailsGrid:          null,  // #detailsGrid
  recommendationBox:    null,  // #recommendationBox
  validationNotice:     null,  // #validationNotice


  /* ── CUESTIONARIO ── */
  cuestionarioSection:  null,  // #cuestionarioSection
  cuestionarioAlert:    null,  // #cuestionarioAlert
  cuestionarioForm:     null,  // #cuestionarioForm
  cuestionarioBody:     null,  // #cuestionarioBody
  cuestionarioStatusTag:null,  // #cuestionarioStatusTag
  cuestionarioStudent:  null,  // #cuestionarioStudent
  saveCuestionarioBtn:  null,  // #saveCuestionarioBtn
  completadoPorInput:   null,  // #completadoPorInput    → payload.completado_por


  /* ── BOLETÍN ── */
  boletinSection:       null,  // #boletinSection
  boletinAlert:         null,  // #boletinAlert
  boletinContent:       null,  // #boletinContent
  boletinStatusBar:     null,  // #boletinStatusBar
  boletinHeroScore:     null,  // #boletinHeroScore
  boletinSemaforoIcon:  null,  // #boletinSemaforoIcon
  boletinSemaforoLabel: null,  // #boletinSemaforoLabel
  boletinMetricsGrid:   null,  // #boletinMetricsGrid
  boletinSections:      null,  // #boletinSections
  boletinObservacion:   null,  // #boletinObservacion
  boletinConfidenceDot: null,  // #boletinConfidenceDot
  boletinConfidencePct: null,  // #boletinConfidencePct
  openBoletinBtn:       null,  // #openBoletinBtn        (abrir visor inline)
  downloadPdfBtn:       null,  // #downloadPdfBtn
  correctionPanel:      null,  // #correctionPanel
  correctionGrid:       null,  // #correctionGrid
  saveCorrectionBtn:    null,  // #saveCorrectionBtn
};



/* ══════════════════════════════════════════════
   INICIALIZACIÓN
   Llamado UNA vez desde app.js → init()
   Resuelve todos los ids del DOM y los guarda
   en el objeto el.*
   ══════════════════════════════════════════════ */
export function initEl() {
  const get = (id) => document.getElementById(id);

  /* Header */
  el.backendDot           = document.querySelector('.backend-status-dot');
  el.backendLabel         = document.querySelector('.backend-status-text');

  /* Upload */
  el.uploadSection        = get('uploadSection');
  el.uploadForm           = get('uploadForm');
  el.uploadInput          = get('uploadInput');
  el.uploadDropZone       = get('uploadDropZone');
  el.uploadDropFilename   = get('uploadDropFilename');
  el.uploadProgressWrap   = get('uploadProgressWrap');
  el.uploadProgressFill   = get('uploadProgressFill');
  el.uploadProgressPct    = get('uploadProgressPct');
  el.uploadAlert          = get('uploadAlert');
  el.uploadBtn            = get('uploadBtn');
  el.resetBtn             = get('resetBtn');
  /* Campos del formulario — IDs alineados con VideoUploadForm del backend */
  el.subjectInput         = get('subjectInput');
  el.testCodeInput        = get('testCodeInput');
  el.nombreCompletoInput  = get('nombreCompletoInput');

  /* Pipeline */
  el.pipelineSection      = get('pipelineSection');
  el.pipelineSteps        = document.querySelectorAll('.pipeline-step');
  el.jobStatusBlock       = get('jobStatusBlock');
  el.jobStatusValue       = get('jobStatusValue');
  el.jobProgressBar       = get('jobProgressBar');
  el.jobProgressFill      = get('jobProgressFill');
  el.jobProgressPct       = get('jobProgressPct');
  el.jobProgressText      = get('jobProgressText');

  /* Resultado */
  el.resultSection        = get('resultSection');
  el.resultAlert          = get('resultAlert');
  el.resultBlock          = get('resultBlock');
  el.resultHeroStudent    = get('resultHeroStudent');
  el.resultHeroLevel      = get('resultHeroLevel');
  el.heroConfidence       = get('heroConfidence');
  el.heroConfidencePct    = get('heroConfidencePct');
  el.manualReviewBanner   = get('manualReviewBanner');
  el.semaforoBlock        = get('semaforoBlock');
  el.semaforoIcon         = get('semaforoIcon');
  el.semaforoLabel        = get('semaforoLabel');
  el.kpiGrid              = get('kpiGrid');
  el.detailsGrid          = get('detailsGrid');
  el.recommendationBox    = get('recommendationBox');
  el.validationNotice     = get('validationNotice');

  /* Cuestionario */
  el.cuestionarioSection  = get('cuestionarioSection');
  el.cuestionarioAlert    = get('cuestionarioAlert');
  el.cuestionarioForm     = get('cuestionarioForm');
  el.cuestionarioBody     = get('cuestionarioBody');
  el.cuestionarioStatusTag= get('cuestionarioStatusTag');
  el.cuestionarioStudent  = get('cuestionarioStudent');
  el.saveCuestionarioBtn  = get('saveCuestionarioBtn');
  el.completadoPorInput   = get('completadoPorInput');

  /* Boletín */
  el.boletinSection       = get('boletinSection');
  el.boletinAlert         = get('boletinAlert');
  el.boletinContent       = get('boletinContent');
  el.boletinStatusBar     = get('boletinStatusBar');
  el.boletinHeroScore     = get('boletinHeroScore');
  el.boletinSemaforoIcon  = get('boletinSemaforoIcon');
  el.boletinSemaforoLabel = get('boletinSemaforoLabel');
  el.boletinMetricsGrid   = get('boletinMetricsGrid');
  el.boletinSections      = get('boletinSections');
  el.boletinObservacion   = get('boletinObservacion');
  el.boletinConfidenceDot = get('boletinConfidenceDot');
  el.boletinConfidencePct = get('boletinConfidencePct');
  el.openBoletinBtn       = get('openBoletinBtn');
  el.downloadPdfBtn       = get('downloadPdfBtn');
  el.correctionPanel      = get('correctionPanel');
  el.correctionGrid       = get('correctionGrid');
  el.saveCorrectionBtn    = get('saveCorrectionBtn');
}



/* ══════════════════════════════════════════════
   setAlert — muestra un mensaje de alerta
   target : elemento DOM del alert
   message: texto a mostrar
   type   : 'info' | 'success' | 'warning' | 'danger'
   ══════════════════════════════════════════════ */
export function setAlert(target, message, type = 'info') {
  if (!target) return;
  target.className     = `alert alert-${type}`;
  target.textContent   = message;
  target.style.display = message ? 'flex' : 'none';
}

export function clearAlert(target) {
  if (!target) return;
  target.style.display = 'none';
  target.textContent   = '';
}



/* ══════════════════════════════════════════════
   setTag — actualiza un badge de estado
   target : elemento DOM del tag
   text   : texto del badge
   type   : 'default'|'success'|'warning'|'danger'|'info'|'primary'
   ══════════════════════════════════════════════ */
export function setTag(target, text, type = 'default') {
  if (!target) return;
  target.className   = `tag tag-${type}`;
  target.textContent = text;
}



/* ══════════════════════════════════════════════
   SHOW / HIDE — manejo de visibilidad
   Parámetro renombrado a `node` para no shadowear
   el objeto exportado `el` del mismo módulo.
   ══════════════════════════════════════════════ */
export function show(node)  { if (node) node.classList.remove('hidden'); }
export function hide(node)  { if (node) node.classList.add('hidden'); }
export function toggle(node, visible) {
  if (!node) return;
  visible ? show(node) : hide(node);
}



/* ══════════════════════════════════════════════
   BACKEND STATUS DOT
   Actualiza el indicador de conexión en el header.
   state: 'ok' | 'error' | 'pending'
   ══════════════════════════════════════════════ */
export function updateBackendDot(state) {
  if (!el.backendDot) return;

  el.backendDot.className = `backend-status-dot ${state}`;

  const labels = {
    ok:      MSG.BACKEND_OK,
    error:   MSG.BACKEND_ERROR,
    pending: MSG.BACKEND_CHECKING,
  };

  if (el.backendLabel) {
    el.backendLabel.textContent = labels[state] ?? '';
  }
}



/* ══════════════════════════════════════════════
   UPLOAD LOADING STATE
   Muestra/oculta el estado de carga del upload
   y bloquea el botón durante la subida.
   Resetea la barra a 0% al iniciar para que no
   muestre el valor residual de un upload anterior.
   ══════════════════════════════════════════════ */
export function setLoadingUpload(loading) {
  if (el.uploadBtn) {
    el.uploadBtn.disabled    = loading;
    el.uploadBtn.textContent = loading ? 'Subiendo...' : 'Procesar video';
  }
  if (loading) {
    /* Resetear barra antes de mostrarla */
    setProgress(el.uploadProgressFill, el.uploadProgressPct, 0);
  }
  toggle(el.uploadProgressWrap, loading);
}



/* ══════════════════════════════════════════════
   PROGRESS BAR — actualiza el ancho de la barra
   fill  : elemento .progress-bar-fill
   pctEl : elemento de texto con el %
   value : número 0–100
   ══════════════════════════════════════════════ */
export function setProgress(fill, pctEl, value) {
  const pct = Math.min(100, Math.max(0, value));
  if (fill)  fill.style.width  = `${pct}%`;
  if (pctEl) pctEl.textContent = `${Math.round(pct)}%`;
}



/* ══════════════════════════════════════════════
   BOTONES DEL BOLETÍN
   Habilita/deshabilita los botones de acción
   según si el boletín ya existe.
   ══════════════════════════════════════════════ */
export function setBoletinActionsEnabled(enabled) {
  if (el.openBoletinBtn)  el.openBoletinBtn.disabled  = !enabled;
  if (el.downloadPdfBtn)  el.downloadPdfBtn.disabled  = !enabled;
}



/* ══════════════════════════════════════════════
   CUESTIONARIO SUBMIT BUTTON
   El POST /cuestionario guarda la observación;
   el boletín se genera en GET /boletin posterior.
   ══════════════════════════════════════════════ */
export function setCuestionarioSubmitting(submitting) {
  if (!el.saveCuestionarioBtn) return;
  el.saveCuestionarioBtn.disabled    = submitting;
  el.saveCuestionarioBtn.textContent = submitting
    ? 'Guardando validación...'
    : 'Guardar validación';
}