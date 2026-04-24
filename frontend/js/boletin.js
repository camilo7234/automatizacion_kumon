/* ============================================================
   KUMON · MÓDULO DE BOLETÍN
   Archivo: frontend/js/boletin.js
   Depende de: config.js · api.js · state.js · ui.js · formatters.js
   Rol: Renderiza el boletín completo en el visor inline:
        - Barra de estado (generated / corregido)
        - Hero: puntaje combinado + semáforo
        - Dot de confianza OCR
        - Grid de métricas cuantitativas
        - Secciones cualitativas con etiquetas
        - Caja de observación libre del orientador
        - Panel de correcciones (PATCH /boletin/{id})
        - Botón descarga PDF
   ============================================================ */

import { MSG, BOLETIN_STATUS }            from './config.js';
import {
  getBoletin,
  patchBoletin,
  downloadBoletinPdf,
}                                         from './api.js';
import {
  resolveResultId,
  setBoletinData,
  getBoletinData,
}                                         from './state.js';
import {
  el,
  setAlert,
  clearAlert,
  show,
  hide,
  setBoletinActionsEnabled,
}                                         from './ui.js';
import {
  formatPercent,
  formatMinutes,
  formatFraction,
  formatDate,
  semaforoEmoji,
  semaforoLabelText,
  toneForSemaforo,
  confidenceDotClass,
  confidenceLabel,
  boletinStatusClass,
  boletinStatusLabel,
  etiquetaInfo,
}                                         from './formatters.js';


/* ══════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════ */
export function initBoletin() {
  _bindButtons();
}


/* ══════════════════════════════════════════════
   RENDER DESDE DATOS YA CARGADOS
   Llamado desde cuestionario.js vía app.js
   → onBoletinReady(boletinData)
   ══════════════════════════════════════════════ */
export function renderBoletin(data) {
  if (!data) return;

  setBoletinData(data);
  show(el.boletinSection);
  clearAlert(el.boletinAlert);

  _renderStatusBar(data);
  _renderHero(data);
  _renderConfidenceDot(data);
  _renderMetrics(data);
  _renderSections(data);
  _renderObservacion(data);
  _renderCorrectionPanel(data);

  show(el.boletinContent);
  setBoletinActionsEnabled(true);
}


/* ══════════════════════════════════════════════
   LOAD DESDE BACKEND
   Para cuando la página recarga y el boletín
   ya existe — carga directamente sin cuestionario
   ══════════════════════════════════════════════ */
export async function loadBoletin(resultId) {
  show(el.boletinSection);
  clearAlert(el.boletinAlert);
  hide(el.boletinContent);
  setBoletinActionsEnabled(false);
  setAlert(el.boletinAlert, MSG.BOLETIN_LOADING, 'info');

  const { ok, data, error } = await getBoletin(resultId);

  if (!ok || !data) {
    setAlert(
      el.boletinAlert,
      error ?? MSG.BOLETIN_ERROR,
      'danger'
    );
    return;
  }

  clearAlert(el.boletinAlert);
  renderBoletin(data);
}


/* ══════════════════════════════════════════════
   BARRA DE ESTADO
   ══════════════════════════════════════════════ */
function _renderStatusBar(data) {
  if (!el.boletinStatusBar) return;

  const status    = data.status ?? BOLETIN_STATUS.GENERATED;
  const cssClass  = boletinStatusClass(status);
  const label     = boletinStatusLabel(status);
  const dateStr   = formatDate(data.generated_at);

  el.boletinStatusBar.className   = `boletin-status-bar ${cssClass}`;
  el.boletinStatusBar.innerHTML   = `
    <span class="status-label">${label}</span>
    <span class="status-date">${dateStr}</span>
  `;
}


/* ══════════════════════════════════════════════
   HERO — puntaje combinado + semáforo
   ══════════════════════════════════════════════ */
function _renderHero(data) {
  /* Puntaje combinado */
  if (el.boletinHeroScore) {
    const score = data.puntaje_combinado ?? data.percentage ?? null;
    el.boletinHeroScore.textContent = formatPercent(score, 1);
  }

  /* Semáforo */
  const value = data.semaforo ?? '';
  const tone  = toneForSemaforo(value);

  if (el.boletinSemaforoIcon) {
    el.boletinSemaforoIcon.textContent  = semaforoEmoji(value);
  }
  if (el.boletinSemaforoLabel) {
    el.boletinSemaforoLabel.textContent = semaforoLabelText(value);
    el.boletinSemaforoLabel.className   = `semaforo-label tone-${tone}`;
  }
}


/* ══════════════════════════════════════════════
   DOT DE CONFIANZA OCR
   ══════════════════════════════════════════════ */
function _renderConfidenceDot(data) {
  const score    = data.confidence_score ?? null;
  const dotClass = confidenceDotClass(score);
  const label    = confidenceLabel(score);

  if (el.boletinConfidencePct) {
    el.boletinConfidencePct.textContent = label;
  }

  if (el.boletinConfidenceDot) {
    el.boletinConfidenceDot.classList.remove('warn', 'alert');
    if (dotClass) el.boletinConfidenceDot.classList.add(dotClass);
    el.boletinConfidenceDot.setAttribute('title', label);
  }

  /* Banner de revisión manual inline en el boletín */
  const manualBanner = document.getElementById('boletinManualReviewBanner');
  if (manualBanner) {
    if (data.needs_manual_review) {
      manualBanner.innerHTML = `
        <span>⚠️</span>
        <span>Confianza OCR baja (${label}).
              Verifica los valores en el panel de correcciones.</span>
      `;
      show(manualBanner);
    } else {
      hide(manualBanner);
    }
  }
}


/* ══════════════════════════════════════════════
   MÉTRICAS CUANTITATIVAS
   ══════════════════════════════════════════════ */
function _renderMetrics(data) {
  if (!el.boletinMetricsGrid) return;

  const metrics = [
    {
      label: 'Nivel WS',
      value: data.ws ?? '—',
      icon:  '📘',
    },
    {
      label: 'Punto de inicio',
      value: data.starting_point ?? '—',
      icon:  '🏁',
    },
    {
      label: 'Porcentaje',
      value: formatPercent(data.percentage),
      icon:  '📊',
    },
    {
      label: 'Aciertos',
      value: formatFraction(data.correct_answers, data.total_questions),
      icon:  '✅',
    },
    {
      label: 'Tiempo estudio',
      value: formatMinutes(data.study_time_min),
      icon:  '⏱',
    },
    {
      label: 'Tiempo objetivo',
      value: formatMinutes(data.target_time_min),
      icon:  '🎯',
    },
  ];

  el.boletinMetricsGrid.innerHTML = metrics.map(m => `
    <div class="metric-card">
      <span class="metric-icon">${m.icon}</span>
      <span class="metric-value">${_escapeHtml(String(m.value))}</span>
      <span class="metric-label">${m.label}</span>
    </div>
  `).join('');
}


/* ══════════════════════════════════════════════
   SECCIONES CUALITATIVAS
   detalle_secciones: [{ nombre, puntaje, etiqueta }]
   ══════════════════════════════════════════════ */
function _renderSections(data) {
  if (!el.boletinSections) return;

  const sections = data.detalle_secciones ?? [];

  if (!sections.length) {
    /* Fallback: mostrar puntaje y etiqueta global */
    const { label, type } = etiquetaInfo(data.etiqueta_cualitativa);
    el.boletinSections.innerHTML = `
      <div class="section-row section-summary">
        <span class="section-nombre">Evaluación global</span>
        <span class="section-puntaje">
          ${formatPercent(data.puntaje_cualitativo)}
        </span>
        <span class="tag tag-${type}">${label}</span>
      </div>
    `;
    return;
  }

  el.boletinSections.innerHTML = sections.map(sec => {
    const { label, type } = etiquetaInfo(sec.etiqueta);
    return `
      <div class="section-row">
        <span class="section-nombre">
          ${_escapeHtml(sec.nombre ?? '—')}
        </span>
        <span class="section-puntaje">
          ${formatPercent(sec.puntaje)}
        </span>
        <span class="tag tag-${type}">${label}</span>
      </div>
    `;
  }).join('');
}


/* ══════════════════════════════════════════════
   OBSERVACIÓN LIBRE DEL ORIENTADOR
   ══════════════════════════════════════════════ */
function _renderObservacion(data) {
  if (!el.boletinObservacion) return;

  const text = data.observacion_libre ?? null;

  if (!text) {
    hide(el.boletinObservacion);
    return;
  }

  el.boletinObservacion.innerHTML = `
    <p class="observacion-label">💬 Observación del orientador</p>
    <p class="observacion-text">${_escapeHtml(text)}</p>
  `;
  show(el.boletinObservacion);
}


/* ══════════════════════════════════════════════
   PANEL DE CORRECCIONES
   Permite al orientador corregir valores
   cuantitativos antes o después de generar el PDF.
   Usa PATCH /api/v1/boletin/{resultId}
   ══════════════════════════════════════════════ */
function _renderCorrectionPanel(data) {
  if (!el.correctionGrid) return;

  /* Campos corregibles: los cuantitativos clave */
  const fields = [
    {
      key:         'ws',
      label:       'Nivel WS',
      type:        'text',
      value:       data.ws ?? '',
      placeholder: 'Ej: 5A',
    },
    {
      key:         'correct_answers',
      label:       'Respuestas correctas',
      type:        'number',
      value:       data.correct_answers ?? '',
      placeholder: 'Ej: 18',
      min:         0,
    },
    {
      key:         'total_questions',
      label:       'Total preguntas',
      type:        'number',
      value:       data.total_questions ?? '',
      placeholder: 'Ej: 20',
      min:         1,
    },
    {
      key:         'study_time_min',
      label:       'Tiempo estudio (min)',
      type:        'number',
      value:       data.study_time_min ?? '',
      placeholder: 'Ej: 45',
      min:         0,
    },
    {
      key:         'observacion_libre',
      label:       'Observación del orientador',
      type:        'textarea',
      value:       data.observacion_libre ?? '',
      placeholder: 'Escribe una observación adicional...',
    },
  ];

  el.correctionGrid.innerHTML = fields.map(f => {
    const inputHtml = f.type === 'textarea'
      ? `<textarea
           id="corr_${f.key}"
           data-key="${f.key}"
           class="form-textarea correction-input"
           rows="2"
           placeholder="${_escapeAttr(f.placeholder)}"
         >${_escapeHtml(String(f.value))}</textarea>`
      : `<input
           type="${f.type}"
           id="corr_${f.key}"
           data-key="${f.key}"
           class="form-input correction-input"
           value="${_escapeAttr(String(f.value))}"
           placeholder="${_escapeAttr(f.placeholder)}"
           ${f.min !== undefined ? `min="${f.min}"` : ''}>`;

    return `
      <div class="correction-field">
        <label class="correction-label" for="corr_${f.key}">
          ${f.label}
        </label>
        ${inputHtml}
      </div>
    `;
  }).join('');
}


/* ══════════════════════════════════════════════
   GUARDAR CORRECCIONES — submit del panel
   ══════════════════════════════════════════════ */
async function _handleSaveCorrections() {
  const resultId = resolveResultId();
  if (!resultId) {
    setAlert(el.boletinAlert, 'Sin result_id para guardar.', 'danger');
    return;
  }

  /* Recolectar solo los campos que cambiaron */
  const inputs = el.correctionGrid
    ?.querySelectorAll('.correction-input') ?? [];

  const corrections = {};
  const current     = getBoletinData() ?? {};

  inputs.forEach(inp => {
    const key      = inp.dataset.key;
    const rawValue = inp.tagName === 'TEXTAREA'
      ? inp.value.trim()
      : inp.value.trim();

    /* Convertir a número si el campo original era numérico */
    const numericKeys = [
      'correct_answers', 'total_questions',
      'study_time_min',  'target_time_min',
    ];
    const value = numericKeys.includes(key) && rawValue !== ''
      ? Number(rawValue)
      : rawValue || null;

    /* Solo incluir en el payload si el valor cambió */
    if (String(value) !== String(current[key] ?? '')) {
      corrections[key] = value;
    }
  });

  if (!Object.keys(corrections).length) {
    setAlert(el.boletinAlert, 'No hay cambios para guardar.', 'info');
    return;
  }

  /* Deshabilitar botón durante el request */
  if (el.saveCorrectionBtn) {
    el.saveCorrectionBtn.disabled    = true;
    el.saveCorrectionBtn.textContent = 'Guardando...';
  }

  const { ok, data, error } = await patchBoletin(resultId, corrections);

  if (el.saveCorrectionBtn) {
    el.saveCorrectionBtn.disabled    = false;
    el.saveCorrectionBtn.textContent = 'Guardar correcciones';
  }

  if (!ok || !data) {
    setAlert(
      el.boletinAlert,
      error ?? MSG.BOLETIN_PATCH_ERROR,
      'danger'
    );
    return;
  }

  /* Re-renderizar el boletín con los datos corregidos */
  setAlert(el.boletinAlert, MSG.BOLETIN_PATCH_SUCCESS, 'success');
  renderBoletin(data);
}


/* ══════════════════════════════════════════════
   BIND DE BOTONES
   ══════════════════════════════════════════════ */
function _bindButtons() {

  /* Abrir/ocultar panel de correcciones */
  el.openBoletinBtn?.addEventListener('click', () => {
    if (!el.correctionPanel) return;
    const isHidden = el.correctionPanel.classList.contains('hidden');
    isHidden ? show(el.correctionPanel) : hide(el.correctionPanel);
    el.openBoletinBtn.textContent = isHidden
      ? '✏️ Ocultar correcciones'
      : '✏️ Corregir valores';
  });

  /* Guardar correcciones */
  el.saveCorrectionBtn?.addEventListener('click', _handleSaveCorrections);

  /* Descargar PDF */
  el.downloadPdfBtn?.addEventListener('click', () => {
    const resultId = resolveResultId();
    if (!resultId) {
      setAlert(el.boletinAlert, MSG.BOLETIN_PDF_ERROR, 'danger');
      return;
    }
    const boletin  = getBoletinData();
    const name     = boletin?.student_name ?? 'estudiante';
    downloadBoletinPdf(resultId, name);
  });
}


/* ══════════════════════════════════════════════
   RESET PÚBLICO
   ══════════════════════════════════════════════ */
export function resetBoletin() {
  if (el.boletinMetricsGrid) el.boletinMetricsGrid.innerHTML = '';
  if (el.boletinSections)    el.boletinSections.innerHTML    = '';
  if (el.correctionGrid)     el.correctionGrid.innerHTML     = '';
  if (el.boletinObservacion) el.boletinObservacion.innerHTML = '';
  if (el.boletinStatusBar)   el.boletinStatusBar.className   = 'boletin-status-bar';
  if (el.boletinHeroScore)   el.boletinHeroScore.textContent = '—';

  if (el.boletinConfidenceDot) {
    el.boletinConfidenceDot.classList.remove('warn', 'alert');
  }
  if (el.boletinSemaforoLabel) {
    el.boletinSemaforoLabel.className = 'semaforo-label';
  }
  if (el.openBoletinBtn) {
    el.openBoletinBtn.textContent = '✏️ Corregir valores';
  }

  clearAlert(el.boletinAlert);
  hide(el.correctionPanel);
  hide(el.boletinContent);
  hide(el.boletinSection);
  setBoletinActionsEnabled(false);
}


/* ══════════════════════════════════════════════
   UTILIDADES INTERNAS
   ══════════════════════════════════════════════ */
function _escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#39;');
}

function _escapeAttr(str) {
  return String(str ?? '').replace(/"/g, '&quot;');
}