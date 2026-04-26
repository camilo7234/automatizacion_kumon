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
import { getResult }                      from './api.js';
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
export async function loadResultado(jobId) {
  show(el.resultSection);
  clearAlert(el.resultAlert);
  hide(el.resultBlock);
  setAlert(el.resultAlert, MSG.RESULT_LOADING, 'info');

  const { ok, data, error } = await getResult(jobId);

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



/* ══════════════════════════════════════════════
   HERO — sujeto, nivel, dot de confianza
   Fuente: TestResultResponse
     nombre_sujeto  — nombre del prospecto o estudiante
     ws             — código de la hoja de trabajo (ej: "5A")
     confidence_score — Decimal serializado como string "0.00–1.00"
   ══════════════════════════════════════════════ */
function _renderHero(data) {
  /* nombre_sujeto es el campo real de TestResultResponse */
  if (el.resultHeroStudent) {
    el.resultHeroStudent.textContent =
      data.nombre_sujeto?.trim() || 'Sin nombre';
  }

  /* ws: código de la hoja de trabajo */
  if (el.resultHeroLevel) {
    el.resultHeroLevel.textContent =
      data.ws ? `WS ${data.ws}` : '—';
  }

  /* confidence_score llega como string Decimal — convertir a float */
  const score = data.confidence_score !== null && data.confidence_score !== undefined
    ? parseFloat(data.confidence_score)
    : null;
  const dotClass = confidenceDotClass(score);

  if (el.heroConfidencePct) {
    el.heroConfidencePct.textContent = confidenceLabel(score);
  }

  if (el.heroConfidence) {
    el.heroConfidence.classList.remove('warn', 'alert');
    if (dotClass) el.heroConfidence.classList.add(dotClass);
    el.heroConfidence.setAttribute(
      'title',
      `Confianza OCR: ${confidenceLabel(score)}`
    );
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
        <strong>Revisión manual recomendada.</strong>
        La confianza del OCR fue
        <strong>${confidenceLabel(score)}</strong>.
        Verifica los valores antes de generar el boletín.
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
   KPIs — grid de métricas principales
   Campos Decimal del backend llegan como strings —
   se convierten con parseFloat antes de formatear.
   ══════════════════════════════════════════════ */
function _renderKpis(data) {
  if (!el.kpiGrid) return;

  /* Normalizar Decimals serializados como string */
  const pct         = data.percentage       !== null ? parseFloat(data.percentage)       : null;
  const studyTime   = data.study_time_min   !== null ? parseFloat(data.study_time_min)   : null;
  const targetTime  = data.target_time_min  !== null ? parseFloat(data.target_time_min)  : null;

  const kpis = [
    {
      label: 'Porcentaje',
      value: formatPercent(pct),
      icon:  '📊',
      tone:  _percentTone(pct),
    },
    {
      label: 'Tiempo estudio',
      value: formatMinutes(studyTime),
      icon:  '⏱',
      tone:  'neutral',
    },
    {
      label: 'Tiempo objetivo',
      value: formatMinutes(targetTime),
      icon:  '🎯',
      tone:  'neutral',
    },
    {
      label: 'Aciertos',
      value: formatFraction(data.correct_answers, data.total_questions),
      icon:  '✅',
      tone:  _fractionTone(data.correct_answers, data.total_questions),
    },
  ];

  el.kpiGrid.innerHTML = kpis.map(k => `
    <div class="kpi-card tone-${k.tone}">
      <span class="kpi-icon">${k.icon}</span>
      <span class="kpi-value">${k.value}</span>
      <span class="kpi-label">${k.label}</span>
    </div>
  `).join('');
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
   DETALLES — tabla expandida
   Incluye todos los campos relevantes de
   TestResultResponse para el orientador.
   ══════════════════════════════════════════════ */
function _renderDetails(data) {
  if (!el.detailsGrid) return;

  /* Normalizar Decimals */
  const pct        = data.percentage      !== null ? parseFloat(data.percentage)      : null;
  const studyTime  = data.study_time_min  !== null ? parseFloat(data.study_time_min)  : null;
  const targetTime = data.target_time_min !== null ? parseFloat(data.target_time_min) : null;
  const confScore  = data.confidence_score !== null && data.confidence_score !== undefined
    ? parseFloat(data.confidence_score) : null;

  const rows = [
    { label: 'Prueba',              value: data.display_name      ?? '—' },
    { label: 'Materia',             value: data.subject           ?? '—' },
    { label: 'Código',              value: data.test_code         ?? '—' },
    { label: 'Tipo de sujeto',      value: _formatTipoSujeto(data.tipo_sujeto) },
    { label: 'Nivel WS',            value: data.ws                ?? '—' },
    { label: 'Nivel actual',        value: data.current_level     ?? '—' },
    { label: 'Punto de inicio',     value: data.starting_point    ?? '—' },
    { label: 'Tiempo de estudio',   value: formatMinutes(studyTime) },
    { label: 'Tiempo objetivo',     value: formatMinutes(targetTime) },
    { label: 'Aciertos / Total',    value: formatFraction(data.correct_answers, data.total_questions) },
    { label: 'Porcentaje',          value: formatPercent(pct) },
    { label: 'Confianza OCR',       value: confidenceLabel(confScore) },
    { label: 'Revisión manual',
      value: data.needs_manual_review ? '⚠️ Sí' : '✅ No' },
  ];

  el.detailsGrid.innerHTML = rows.map(r => `
    <div class="detail-row">
      <span class="detail-label">${_escapeHtml(r.label)}</span>
      <span class="detail-value">${_escapeHtml(String(r.value))}</span>
    </div>
  `).join('');
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
  if (el.kpiGrid)           el.kpiGrid.innerHTML               = '';
  if (el.detailsGrid)       el.detailsGrid.innerHTML           = '';
  if (el.recommendationBox) el.recommendationBox.innerHTML     = '';
  if (el.resultHeroStudent) el.resultHeroStudent.textContent   = '';
  if (el.resultHeroLevel)   el.resultHeroLevel.textContent     = '';
  if (el.heroConfidencePct) el.heroConfidencePct.textContent   = '';

  if (el.heroConfidence) {
    el.heroConfidence.classList.remove('warn', 'alert');
  }
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