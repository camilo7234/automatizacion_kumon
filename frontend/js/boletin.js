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
  setPdfDownloadEnabled,
  resetBoletinButtons,
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

  /* Habilitar correcciones y confirmar — PDF bloqueado hasta
     que el orientador confirme o guarde correcciones */
  setBoletinActionsEnabled(true);
  setPdfDownloadEnabled(false);
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
   data.status y data.generated_at existen en la
   raíz de BoletinResponse — no requieren desestructurar.
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
   CORRECCIÓN: todos los campos leídos desde
   data.combinado y data.cuantitativo, no desde
   la raíz de BoletinResponse donde no existen.
   ══════════════════════════════════════════════ */
function _renderHero(data) {
  const combinado    = data.combinado    ?? {};
  const cuantitativo = data.cuantitativo ?? {};

  if (el.boletinHeroScore) {
    /* puntaje combinado: data.combinado.puntaje
       fallback a porcentaje bruto: data.cuantitativo.percentage */
    const score = _toFloat(combinado.puntaje ?? cuantitativo.percentage);
    el.boletinHeroScore.textContent = formatPercent(score, 1);
  }

  /* semaforo: data.cuantitativo.semaforo */
  const value = cuantitativo.semaforo ?? '';
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
   CORRECCIÓN: confidence_score y needs_manual_review
   están en data.cuantitativo, no en la raíz.
   ══════════════════════════════════════════════ */
function _renderConfidenceDot(data) {
  const cuantitativo = data.cuantitativo ?? {};

  const score    = _toFloat(cuantitativo.confidence_score);
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
    if (cuantitativo.needs_manual_review) {
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
   CORRECCIÓN: todos los campos leídos desde
   data.cuantitativo, no desde la raíz.
   ══════════════════════════════════════════════ */
function _renderMetrics(data) {
  if (!el.boletinMetricsGrid) return;

  const cuantitativo = data.cuantitativo ?? {};

  const metrics = [
    {
      label: 'Nivel WS',
      value: cuantitativo.ws ?? '—',
      icon:  '📘',
    },
    {
      label: 'Punto de inicio',
      value: cuantitativo.starting_point ?? '—',
      icon:  '🏁',
    },
    {
      label: 'Porcentaje',
      value: formatPercent(_toFloat(cuantitativo.percentage)),
      icon:  '📊',
    },
    {
      label: 'Aciertos',
      value: formatFraction(cuantitativo.correct_answers, cuantitativo.total_questions),
      icon:  '✅',
    },
    {
      label: 'Tiempo estudio',
      value: formatMinutes(_toFloat(cuantitativo.study_time_min)),
      icon:  '⏱',
    },
    {
      label: 'Tiempo objetivo',
      value: formatMinutes(_toFloat(cuantitativo.target_time_min)),
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
   CORRECCIÓN:
   - data.detalle_secciones → data.cualitativo.secciones
   - data.etiqueta_cualitativa → data.cualitativo.etiqueta_total
   - data.puntaje_cualitativo → data.cualitativo.total_porcentaje
   ══════════════════════════════════════════════ */
function _renderSections(data) {
  if (!el.boletinSections) return;

  const cualitativo = data.cualitativo ?? {};
  const sections    = cualitativo.secciones ?? [];

  if (!sections.length) {
    /* Fallback: mostrar puntaje y etiqueta global */
    const { label, type } = etiquetaInfo(cualitativo.etiqueta_total);
    el.boletinSections.innerHTML = `
      <div class="section-row section-summary">
        <span class="section-nombre">Evaluación global</span>
        <span class="section-puntaje">
          ${formatPercent(_toFloat(cualitativo.total_porcentaje))}
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
   CORRECCIÓN: observacion_cualitativa no existe
   en BoletinResponse — el campo fue guardado en
   ObservacionCualitativa y el backend no lo
   reexpone en este endpoint. Se oculta el bloque.
   ══════════════════════════════════════════════ */
function _renderObservacion(data) {
  if (!el.boletinObservacion) return;
  hide(el.boletinObservacion);
}




/* ══════════════════════════════════════════════
   PANEL DE CORRECCIONES
   CORRECCIÓN:
   - Todos los values leídos desde data.cuantitativo
   - Campo observacion_cualitativa eliminado: no
     existe en BoletinResponse ni en BoletinPatchRequest
     según el schema del backend. El PATCH solo
     acepta campos de data.cuantitativo.
   ══════════════════════════════════════════════ */
function _renderCorrectionPanel(data) {
  if (!el.correctionGrid) return;

  const cuantitativo = data.cuantitativo ?? {};

  const fields = [
    {
      key:         'cuantitativo.ws',
      label:       'Nivel WS',
      type:        'text',
      value:       cuantitativo.ws ?? '',
      placeholder: 'Ej: 5A',
    },
    {
      key:         'cuantitativo.correct_answers',
      label:       'Respuestas correctas',
      type:        'number',
      value:       cuantitativo.correct_answers ?? '',
      placeholder: 'Ej: 18',
      min:         0,
    },
    {
      key:         'cuantitativo.total_questions',
      label:       'Total preguntas',
      type:        'number',
      value:       cuantitativo.total_questions ?? '',
      placeholder: 'Ej: 20',
      min:         1,
    },
    {
      key:         'cuantitativo.study_time_min',
      label:       'Tiempo estudio (min)',
      type:        'number',
      value:       _toFloat(cuantitativo.study_time_min) ?? '',
      placeholder: 'Ej: 45',
      min:         0,
    },
  ];

  el.correctionGrid.innerHTML = fields.map(f => {
    const inputHtml = `<input
         type="${f.type}"
         id="corr_${f.key.replace('.', '_')}"
         data-key="${f.key}"
         class="form-input correction-input"
         value="${_escapeAttr(String(f.value))}"
         placeholder="${_escapeAttr(f.placeholder)}"
         ${f.min !== undefined ? `min="${f.min}"` : ''}>`;

    return `
      <div class="correction-field">
        <label class="correction-label" for="corr_${f.key.replace('.', '_')}">
          ${f.label}
        </label>
        ${inputHtml}
      </div>
    `;
  }).join('');
}




/* ══════════════════════════════════════════════
   GUARDAR CORRECCIONES — submit del panel
   CORRECCIÓN:
   - Los keys ahora son dot-notation: "cuantitativo.ws"
     alineados con BoletinPatchRequest.campo
   - La comparación del valor original se hace
     contra data.cuantitativo[shortKey], no contra
     la raíz de getBoletinData()
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
  const currentCuan = current.cuantitativo ?? {};

  const numericKeys = [
    'cuantitativo.correct_answers',
    'cuantitativo.total_questions',
    'cuantitativo.study_time_min',
    'cuantitativo.target_time_min',
  ];

  /* Construir array de correcciones con estructura auditada por el backend:
     { campo, valor_original, valor_nuevo, motivo }
     campo usa dot-notation: "cuantitativo.ws"
     Solo se incluyen campos que realmente cambiaron. */
  const correcciones = [];

  inputs.forEach(inp => {
    const key      = inp.dataset.key;           // "cuantitativo.ws"
    const rawValue = inp.value.trim();
    const shortKey = key.split('.').pop();      // "ws"

    const valor_nuevo = numericKeys.includes(key) && rawValue !== ''
      ? Number(rawValue)
      : rawValue || null;

    const currentNorm = numericKeys.includes(key)
      ? _toFloat(currentCuan[shortKey])
      : (currentCuan[shortKey] ?? null);

    if (String(valor_nuevo ?? '') !== String(currentNorm ?? '')) {
      correcciones.push({
        campo:          key,
        valor_original: currentNorm,
        valor_nuevo,
        motivo:         null,
      });
    }
  });

  if (!correcciones.length) {
    setAlert(el.boletinAlert, 'No hay cambios para guardar.', 'info');
    return;
  }

  /* corregido_por: reutilizar el nombre que el orientador ya ingresó
     en el cuestionario — fuente única de verdad en el DOM */
  const corregido_por =
    document.getElementById('completadoPorInput')?.value?.trim() || 'Orientador';

  if (el.saveCorrectionBtn) {
    el.saveCorrectionBtn.disabled    = true;
    el.saveCorrectionBtn.textContent = 'Guardando...';
  }

  const payload = { correcciones, corregido_por };
  const { ok, data, error } = await patchBoletin(resultId, payload);

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
  setPdfDownloadEnabled(true);      // ← habilitar PDF tras PATCH exitoso
  hide(el.confirmBoletinBtn);       // ← ocultar "Confirmar sin cambios" — ya no aplica
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

  /* Confirmar sin cambios — habilita el PDF sin hacer PATCH */
  el.confirmBoletinBtn?.addEventListener('click', () => {
    setPdfDownloadEnabled(true);
    hide(el.confirmBoletinBtn);
    setAlert(el.boletinAlert, 'Boletín confirmado. Ya puedes descargar el PDF.', 'success');
  });

  /* Descargar PDF — nombre del archivo desde cuantitativo.nombre_sujeto */
  el.downloadPdfBtn?.addEventListener('click', () => {
    const resultId = resolveResultId();
    if (!resultId) {
      setAlert(el.boletinAlert, MSG.BOLETIN_PDF_ERROR, 'danger');
      return;
    }
    const boletin = getBoletinData();
    /* CORRECCIÓN: nombre_sujeto está en data.cuantitativo, no en la raíz */
    const name    = boletin?.cuantitativo?.nombre_sujeto?.trim() || 'estudiante';
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

  clearAlert(el.boletinAlert);
  hide(el.correctionPanel);
  hide(el.boletinContent);
  hide(el.boletinSection);

  /* resetBoletinButtons es la única fuente de verdad
     para el estado inicial de los tres botones */
  resetBoletinButtons();
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