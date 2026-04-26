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
        - Caja de observación cualitativa del orientador
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
   UTILIDAD — normalizar Decimal serializado
   BoletinResponse serializa campos Decimal como
   strings desde el backend (ej: "85.50").
   Llamar antes de cualquier formateo numérico.
   ══════════════════════════════════════════════ */
function _toFloat(value) {
  if (value === null || value === undefined) return null;
  const n = parseFloat(value);
  return isNaN(n) ? null : n;
}



/* ══════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════ */
export function initBoletin() {
  _bindButtons();
}



/* ══════════════════════════════════════════════
   RENDER DESDE DATOS YA CARGADOS
   Llamado desde loadBoletin() — recibe
   BoletinResponse completo del GET /boletin/{id}
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
   Llamado desde app.js → _onCuestionarioDone
   vía loadBoletin(resultId).
   También usado para recargar tras correcciones.
   ══════════════════════════════════════════════ */
export async function loadBoletin(resultId) {
  show(el.boletinSection);
  clearAlert(el.boletinAlert);
  hide(el.boletinContent);
  setBoletinActionsEnabled(false);
  setAlert(el.boletinAlert, MSG.BOLETIN_LOADING, 'info');

  const { ok, data, error } = await getBoletin(resultId);

  if (!ok || !data) {
    setAlert(el.boletinAlert, error ?? MSG.BOLETIN_ERROR, 'danger');
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

  const status   = data.status ?? BOLETIN_STATUS.GENERATED;
  const cssClass = boletinStatusClass(status);
  const label    = boletinStatusLabel(status);
  const dateStr  = formatDate(data.generated_at);

  el.boletinStatusBar.className = `boletin-status-bar ${cssClass}`;
  el.boletinStatusBar.innerHTML = `
    <span class="status-label">${label}</span>
    <span class="status-date">${dateStr}</span>
  `;
}



/* ══════════════════════════════════════════════
   HERO — puntaje combinado + semáforo
   Campos Decimal (puntaje_combinado, percentage)
   llegan como strings — normalizar con _toFloat.
   ══════════════════════════════════════════════ */
function _renderHero(data) {
  if (el.boletinHeroScore) {
    /* puntaje_combinado es el score final; fallback a percentage */
    const score = _toFloat(data.puntaje_combinado ?? data.percentage);
    el.boletinHeroScore.textContent = formatPercent(score, 1);
  }

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
   confidence_score llega como string Decimal.
   ══════════════════════════════════════════════ */
function _renderConfidenceDot(data) {
  const score    = _toFloat(data.confidence_score);
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
   Campos Decimal normalizados con _toFloat.
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
      value: formatPercent(_toFloat(data.percentage)),
      icon:  '📊',
    },
    {
      label: 'Aciertos',
      value: formatFraction(data.correct_answers, data.total_questions),
      icon:  '✅',
    },
    {
      label: 'Tiempo estudio',
      value: formatMinutes(_toFloat(data.study_time_min)),
      icon:  '⏱',
    },
    {
      label: 'Tiempo objetivo',
      value: formatMinutes(_toFloat(data.target_time_min)),
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
   puntaje por sección y puntaje_cualitativo global
   son Decimal — normalizar con _toFloat.
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
          ${formatPercent(_toFloat(data.puntaje_cualitativo))}
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
          ${formatPercent(_toFloat(sec.puntaje))}
        </span>
        <span class="tag tag-${type}">${label}</span>
      </div>
    `;
  }).join('');
}



/* ══════════════════════════════════════════════
   OBSERVACIÓN CUALITATIVA DEL ORIENTADOR
   Campo real de BoletinResponse: observacion_cualitativa
   ══════════════════════════════════════════════ */
function _renderObservacion(data) {
  if (!el.boletinObservacion) return;

  /* observacion_cualitativa es el campo real de BoletinResponse */
  const text = data.observacion_cualitativa ?? null;

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
   Permite corregir valores cuantitativos y la
   observación antes o después de generar el PDF.
   Usa PATCH /api/v1/boletin/{resultId}
   Campo observación: observacion_cualitativa
   (alineado con BoletinPatchRequest)
   ══════════════════════════════════════════════ */
function _renderCorrectionPanel(data) {
  if (!el.correctionGrid) return;

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
      value:       _toFloat(data.study_time_min) ?? '',
      placeholder: 'Ej: 45',
      min:         0,
    },
    {
      /* observacion_cualitativa — alineado con BoletinPatchRequest */
      key:         'observacion_cualitativa',
      label:       'Observación del orientador',
      type:        'textarea',
      value:       data.observacion_cualitativa ?? '',
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

  const inputs  = el.correctionGrid
    ?.querySelectorAll('.correction-input') ?? [];
  const current = getBoletinData() ?? {};

  const corrections = {};
  const numericKeys = [
    'correct_answers', 'total_questions',
    'study_time_min',  'target_time_min',
  ];

  inputs.forEach(inp => {
    const key      = inp.dataset.key;
    const rawValue = inp.value.trim();

    const value = numericKeys.includes(key) && rawValue !== ''
      ? Number(rawValue)
      : rawValue || null;

    /* Para comparación normalizar el valor actual también
       (puede ser string Decimal del backend) */
    const currentNorm = numericKeys.includes(key)
      ? _toFloat(current[key])
      : (current[key] ?? null);

    /* Solo incluir en el payload si el valor cambió */
    if (String(value ?? '') !== String(currentNorm ?? '')) {
      corrections[key] = value;
    }
  });

  if (!Object.keys(corrections).length) {
    setAlert(el.boletinAlert, 'No hay cambios para guardar.', 'info');
    return;
  }

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

  /* Descargar PDF — nombre del archivo desde nombre_sujeto */
  el.downloadPdfBtn?.addEventListener('click', () => {
    const resultId = resolveResultId();
    if (!resultId) {
      setAlert(el.boletinAlert, MSG.BOLETIN_PDF_ERROR, 'danger');
      return;
    }
    const boletin = getBoletinData();
    /* nombre_sujeto es el campo real de BoletinResponse */
    const name    = boletin?.nombre_sujeto?.trim() || 'estudiante';
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