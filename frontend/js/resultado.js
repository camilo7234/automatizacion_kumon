/* ============================================================
   KUMON · MÓDULO DE RESULTADO
   Archivo: frontend/js/resultado.js
   Depende de: api.js · state.js · ui.js · formatters.js
   Rol: Carga y renderiza el TestResult completo:
        - Hero con nombre del sujeto, nivel y dot OCR
        - Banner de revisión manual si needs_manual_review
        - Bloque semáforo con icono y label
        - Grid de KPIs cuantitativos
        - Tabla de detalles expandida
        - Caja de recomendación
        - Aviso de validación pendiente (si no está completo)
        Al terminar de renderizar notifica a app.js
        via onResultReady() para mostrar el cuestionario.
   ============================================================ */


import { MSG }                            from './config.js';
import { getResult, getResultById}                      from './api.js';
import { setResultData }                  from './state.js';
import {
  el,
  setAlert,
  clearAlert,
  show,
  hide,
  toggle,
}                                         from './ui.js';
import {
  formatPercent,
  formatMinutes,
  formatFraction,
  formatDecimal,
  semaforoEmoji,
  semaforoLabelText,
  toneForSemaforo,
  confidenceDotClass,
  confidenceLabel,
}                                         from './formatters.js';



/* ══════════════════════════════════════════════
   ESTADO INTERNO
   ══════════════════════════════════════════════ */
let _onResultReady = null;   // callback() → void



/* ══════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════ */
export function initResultado(onResultReady) {
  _onResultReady = onResultReady;
}



/* ══════════════════════════════════════════════
   LOAD & RENDER
   Llamado desde polling.js vía app.js → onJobDone
   @param {string} jobId — UUID del job completado
   ══════════════════════════════════════════════ */
async function _loadAndRenderResultado(requestPromise) {
  show(el.resultSection);
  clearAlert(el.resultAlert);
  hide(el.resultBlock);
  setAlert(el.resultAlert, MSG.RESULT_LOADING, 'info');

  const { ok, data, error } = await requestPromise;

  if (!ok || !data) {
    setAlert(el.resultAlert, error ?? MSG.RESULT_ERROR, 'danger');
    return;
  }

  /* Guardar en estado global
     setResultData extrae id_result y lo persiste como currentResultId */
  setResultData(data);
  clearAlert(el.resultAlert);

  /* Renderizar todas las secciones */
  _renderHero(data);
  _renderManualReviewBanner(data);
  _renderSemaforo(data);
  _renderKpis(data);
  _renderDetails(data);
  _renderRecommendation(data);
  _renderValidationNotice(data);

  show(el.resultBlock);

  /* Notificar a app.js que el resultado está listo */
  _onResultReady?.();
}

export async function loadResultado(jobId) {
  return _loadAndRenderResultado(getResult(jobId));
}

/**
 * Carga y renderiza el resultado usando directamente
 * el UUID del TestResult.
 * Llamado desde app.js en el flujo manual_review
 * cuando polling.js ya entregó result_id.
 *
 * @param {string} resultId — UUID de TestResult
 */
export async function loadResultadoById(resultId) {
  return _loadAndRenderResultado(getResultById(resultId));
}


/* ══════════════════════════════════════════════
   HERO — estudiante y nivel de prueba
   Fuente: TestResultResponse
     nombre_sujeto — nombre del prospecto o estudiante
     ws            — código de la hoja de trabajo (ej: "P4")
   ══════════════════════════════════════════════ */
function _renderHero(data) {
  if (el.resultHeroStudent) {
    el.resultHeroStudent.textContent =
      data.nombre_sujeto?.trim() || 'Sin nombre';
  }

  if (el.resultHeroLevel) {
    el.resultHeroLevel.textContent =
      data.ws ? `Nivel ${data.ws}` : '—';
  }
}


/* ══════════════════════════════════════════════
   BANNER DE REVISIÓN MANUAL
   Solo se muestra si needs_manual_review === true
   ══════════════════════════════════════════════ */
function _renderManualReviewBanner(data) {
  const needs = Boolean(data.needs_manual_review);
  toggle(el.manualReviewBanner, needs);

  if (needs && el.manualReviewBanner) {
    const score = data.confidence_score !== null && data.confidence_score !== undefined
      ? parseFloat(data.confidence_score)
      : null;

    el.manualReviewBanner.innerHTML = `
      <span class="banner-icon">⚠️</span>
      <span>
        <strong>Revisión necesaria.</strong>
        El video no se pudo leer con claridad suficiente
        (<strong>${confidenceLabel(score)}</strong>).
        Completa el formulario y ajusta los valores antes de generar el boletín.
      </span>
    `;
  }
}


/* ══════════════════════════════════════════════
   SEMÁFORO
   ══════════════════════════════════════════════ */
function _renderSemaforo(data) {
  const value = data.semaforo ?? '';
  const tone  = toneForSemaforo(value);

  if (el.semaforoBlock) {
    el.semaforoBlock.classList.remove('verde', 'amarillo', 'rojo', 'default');
    el.semaforoBlock.classList.add(tone);
  }

  if (el.semaforoIcon)  el.semaforoIcon.textContent  = semaforoEmoji(value);
  if (el.semaforoLabel) el.semaforoLabel.textContent = semaforoLabelText(value);
}



/* ══════════════════════════════════════════════
   KPIs — tarjetas esenciales para el orientador
   Solo muestra lo que el orientador necesita
   saber inmediatamente tras procesar el video.
   _renderDetails queda vacío: toda la info
   relevante vive aquí. El detalle completo
   va en el boletín.
   ══════════════════════════════════════════════ */
function _renderKpis(data) {
  if (!el.kpiGrid) return;

  const studyTime  = data.study_time_min  != null ? parseFloat(data.study_time_min)  : null;
  const targetTime = data.target_time_min != null ? parseFloat(data.target_time_min) : null;

  // Tiempo: muestra lo que haya — si OCR no leyó el real, muestra "? / 15 min"
  const tiempoValue = (() => {
    const real = studyTime  != null ? `${formatDecimal(studyTime,  1)} min` : '?';
    const obj  = targetTime != null ? `${formatDecimal(targetTime, 1)} min` : '?';
    if (studyTime == null && targetTime == null) return '—';
    return `${real} / ${obj}`;
  })();

  // Aciertos: muestra "— / 30" cuando OCR no leyó los aciertos pero el template sí tiene el total
  const aciertosValue = (() => {
    const correctos = data.correct_answers != null ? data.correct_answers : '—';
    const total     = data.total_questions != null ? data.total_questions : '—';
    if (correctos === '—' && total === '—') return '—';
    return `${correctos} / ${total}`;
  })();

  // Punto de inicio: traducir valores técnicos a lenguaje del orientador
  const spValue = _formatStartingPoint(data.starting_point ?? null);

  // Semáforo en texto legible
  const semaforoValue = _formatSemaforoLabel(data.semaforo);

  const kpis = [
    {
      icon:  '🎓',
      label: 'Nivel evaluado',
      value: data.display_name ?? data.current_level ?? '—',
    },
    {
      icon:  '🚦',
      label: 'Resultado',
      value: semaforoValue,
    },
    {
      icon:  '⭐',
      label: 'Punto de inicio',
      value: spValue,
    },
    {
      icon:  '⏱',
      label: 'Tiempo (real / objetivo)',
      value: tiempoValue,
    },
    {
      icon:  '✅',
      label: 'Aciertos',
      value: aciertosValue,
    },
  ];

  el.kpiGrid.innerHTML = kpis.map(k => `
    <div class="kpi-card">
      <span class="kpi-icon">${k.icon}</span>
      <span class="kpi-value">${k.value}</span>
      <span class="kpi-label">${k.label}</span>
    </div>
  `).join('');
}

// Convierte el semáforo interno en texto legible para el orientador
function _formatSemaforoLabel(semaforo) {
  if (!semaforo) return '—';
  const map = {
    verde:    '✅ Puede avanzar',
    amarillo: '⚠️ Necesita refuerzo',
    rojo:     '🔴 Requiere atención',
  };
  return map[semaforo.toLowerCase()] ?? semaforo;
}

// Convierte el starting_point técnico en texto legible para el orientador
function _formatStartingPoint(sp) {
  if (!sp) return '—';
  if (sp === 'nivel_actual')  return 'Inicio del nivel actual';
  if (sp === 'test_superior') return 'Aplicar test nivel superior';
  if (sp === 'test_inferior') return 'Aplicar test nivel inferior';
  return sp; // ej: "4A 1", "K1 21" — ya son legibles
}

function _percentTone(pct) {
  if (pct === null || pct === undefined) return 'neutral';
  if (pct >= 80) return 'success';
  if (pct >= 60) return 'warning';
  return 'danger';
}

function _fractionTone(correct, total) {
  if (!total) return 'neutral';
  const ratio = correct / total;
  if (ratio >= 0.8) return 'success';
  if (ratio >= 0.6) return 'warning';
  return 'danger';
}


/* ══════════════════════════════════════════════
   DETALLES — desactivado intencionalmente.
   Toda la información relevante para el
   orientador vive en _renderKpis.
   El detalle completo (confianza OCR, tipo de
   sujeto, códigos internos) va en el boletín.
   ══════════════════════════════════════════════ */
function _renderDetails(data) {
  if (!el.detailsGrid) return;
  el.detailsGrid.innerHTML = '';
}

function _formatTipoSujeto(tipo) {
  if (!tipo) return '—';
  const map = { prospecto: 'Prospecto', estudiante: 'Estudiante' };
  return map[tipo.toLowerCase()] ?? tipo;
}

/* ══════════════════════════════════════════════
   RECOMENDACIÓN
   ══════════════════════════════════════════════ */
function _renderRecommendation(data) {
  if (!el.recommendationBox) return;

  const text = data.recommendation ?? null;

  if (!text) {
    hide(el.recommendationBox);
    return;
  }

  el.recommendationBox.innerHTML = `
    <p class="recommendation-label">💡 Recomendación</p>
    <p class="recommendation-text">${_escapeHtml(text)}</p>
  `;
  show(el.recommendationBox);
}



/* ══════════════════════════════════════════════
   AVISO DE VALIDACIÓN PENDIENTE
   Solo se muestra si el cuestionario NO está
   completo todavía.
   Fuente: TestResultResponse.tiene_observacion
           TestResultResponse.observacion_completa
   ══════════════════════════════════════════════ */
function _renderValidationNotice(data) {
  if (!el.validationNotice) return;

  /* Si ya existe una observación completa, no mostrar el aviso */
  const yaCompleto = Boolean(data.tiene_observacion && data.observacion_completa);
  if (yaCompleto) {
    hide(el.validationNotice);
    return;
  }

  el.validationNotice.innerHTML = `
    <span class="notice-icon">📋</span>
    <span>Completa el formulario de validación
          para generar el boletín del estudiante.</span>
  `;
  show(el.validationNotice);
}



/* ══════════════════════════════════════════════
   RESET PÚBLICO
   ══════════════════════════════════════════════ */
export function resetResultado() {
  if (el.kpiGrid)           el.kpiGrid.innerHTML             = '';
  if (el.detailsGrid)       el.detailsGrid.innerHTML         = '';
  if (el.recommendationBox) el.recommendationBox.innerHTML   = '';
  if (el.resultHeroStudent) el.resultHeroStudent.textContent = '';
  if (el.resultHeroLevel)   el.resultHeroLevel.textContent   = '';

  if (el.semaforoBlock) {
    el.semaforoBlock.classList.remove('verde', 'amarillo', 'rojo', 'default');
  }

  clearAlert(el.resultAlert);
  hide(el.resultBlock);
  hide(el.resultSection);
  hide(el.manualReviewBanner);
  hide(el.validationNotice);
  hide(el.recommendationBox);
}


/* ══════════════════════════════════════════════
   UTILIDADES INTERNAS
   ══════════════════════════════════════════════ */
function _escapeHtml(str) {
  return String(str)
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#39;');
}