/* ============================================================
   KUMON · MÓDULO DE BOLETÍN
   Archivo: frontend/js/boletin.js
   Depende de: config.js · api.js · state.js · ui.js · formatters.js
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
  setPdfDownloadEnabled(false);
}


/* ══════════════════════════════════════════════
   LOAD DESDE BACKEND
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
   HERO
   ══════════════════════════════════════════════ */
function _renderHero(data) {
  const combinado    = data.combinado    ?? {};
  const cuantitativo = data.cuantitativo ?? {};

  if (el.boletinHeroScore) {
    const score = _toFloat(combinado.puntaje ?? cuantitativo.percentage);
    el.boletinHeroScore.textContent = formatPercent(score, 1);
  }

  const value = cuantitativo.semaforo ?? '';
  const tone  = toneForSemaforo(value);

  if (el.boletinSemaforoIcon)  el.boletinSemaforoIcon.textContent  = semaforoEmoji(value);
  if (el.boletinSemaforoLabel) {
    el.boletinSemaforoLabel.textContent = semaforoLabelText(value);
    el.boletinSemaforoLabel.className   = `semaforo-label tone-${tone}`;
  }
}


/* ══════════════════════════════════════════════
   DOT DE CONFIANZA OCR
   ══════════════════════════════════════════════ */
function _renderConfidenceDot(data) {
  const cuantitativo = data.cuantitativo ?? {};
  const score        = _toFloat(cuantitativo.confidence_score);
  const dotClass     = confidenceDotClass(score);
  const label        = confidenceLabel(score);

  if (el.boletinConfidencePct) el.boletinConfidencePct.textContent = label;

  if (el.boletinConfidenceDot) {
    el.boletinConfidenceDot.classList.remove('warn', 'alert');
    if (dotClass) el.boletinConfidenceDot.classList.add(dotClass);
    el.boletinConfidenceDot.setAttribute('title', label);
  }

  const manualBanner = document.getElementById('boletinManualReviewBanner');
  if (manualBanner) {
    if (cuantitativo.needs_manual_review) {
      manualBanner.innerHTML = `
        <span>⚠️</span>
        <span>Confianza OCR baja (${label}). Verifica los valores en el editor.</span>
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

  const c = data.cuantitativo ?? {};

  const metrics = [
    { label: 'Nivel WS',       value: c.ws ?? '—',                                       icon: '📘' },
    { label: 'Punto de inicio', value: c.starting_point ?? '—',                          icon: '🏁' },
    { label: 'Porcentaje',     value: formatPercent(_toFloat(c.percentage)),              icon: '📊' },
    { label: 'Aciertos',       value: formatFraction(c.correct_answers, c.total_questions), icon: '✅' },
    { label: 'Tiempo estudio', value: formatMinutes(_toFloat(c.study_time_min)),          icon: '⏱' },
    { label: 'Tiempo objetivo', value: formatMinutes(_toFloat(c.target_time_min)),        icon: '🎯' },
  ];

  el.boletinMetricsGrid.innerHTML = metrics
    .map(m => `
      <div class="metric-card">
        <span class="metric-icon">${m.icon}</span>
        <span class="metric-value">${_escapeHtml(String(m.value))}</span>
        <span class="metric-label">${m.label}</span>
      </div>
    `)
    .join('');
}


/* ══════════════════════════════════════════════
   SECCIONES CUALITATIVAS
   ══════════════════════════════════════════════ */
function _renderSections(data) {
  if (!el.boletinSections) return;

  const cualitativo = data.cualitativo ?? {};
  const sections    = cualitativo.secciones ?? [];

  if (!sections.length) {
    const { label, type } = etiquetaInfo(cualitativo.etiqueta_total);
    el.boletinSections.innerHTML = `
      <div class="section-row section-summary">
        <span class="section-nombre">Evaluación global</span>
        <span class="section-puntaje">${formatPercent(_toFloat(cualitativo.total_porcentaje))}</span>
        <span class="tag tag-${type}">${label}</span>
      </div>
    `;
    return;
  }

  el.boletinSections.innerHTML = sections
    .map(sec => {
      const { label, type } = etiquetaInfo(sec.etiqueta);
      return `
        <div class="section-row">
          <span class="section-nombre">${_escapeHtml(sec.nombre ?? '—')}</span>
          <span class="section-puntaje">${formatPercent(_toFloat(sec.puntaje))}</span>
          <span class="tag tag-${type}">${label}</span>
        </div>
      `;
    })
    .join('');
}


/* ══════════════════════════════════════════════
   OBSERVACIÓN — oculta (no expuesta en BoletinResponse)
   ══════════════════════════════════════════════ */
function _renderObservacion(data) {
  if (!el.boletinObservacion) return;
  hide(el.boletinObservacion);
}


/* ══════════════════════════════════════════════
   PANEL DE CORRECCIONES (conservado, hidden permanente)
   Sigue siendo renderizado en DOM para compatibilidad
   con correcciones que vengan del editor.
   ══════════════════════════════════════════════ */
function _renderCorrectionPanel(data) {
  if (!el.correctionGrid) return;

  const c = data.cuantitativo ?? {};

  const fields = [
    { key: 'cuantitativo.ws',              label: 'Nivel WS',            type: 'text',   value: c.ws ?? '',                               placeholder: 'Ej: 5A'  },
    { key: 'cuantitativo.correct_answers', label: 'Respuestas correctas', type: 'number', value: c.correct_answers ?? '',                   placeholder: 'Ej: 18', min: 0 },
    { key: 'cuantitativo.total_questions', label: 'Total preguntas',      type: 'number', value: c.total_questions ?? '',                   placeholder: 'Ej: 20', min: 1 },
    { key: 'cuantitativo.study_time_min',  label: 'Tiempo estudio (min)', type: 'number', value: _toFloat(c.study_time_min) ?? '',          placeholder: 'Ej: 45', min: 0 },
  ];

  el.correctionGrid.innerHTML = fields
    .map(f => {
      const safeId = `corr_${f.key.replace('.', '_')}`;
      return `
        <div class="correction-field">
          <label class="correction-label" for="${safeId}">${f.label}</label>
          <input type="${f.type}" id="${safeId}" data-key="${f.key}"
                 class="form-input correction-input"
                 value="${_escapeAttr(String(f.value))}"
                 placeholder="${_escapeAttr(f.placeholder)}"
                 ${f.min !== undefined ? `min="${f.min}"` : ''}>
        </div>
      `;
    })
    .join('');
}


/* ══════════════════════════════════════════════
   BIND DE BOTONES — boletinSection
   openBoletinBtn → navega al editor
   ══════════════════════════════════════════════ */
function _bindButtons() {

  /* Navegar al editor */
  el.openBoletinBtn?.addEventListener('click', () => {
    const data = getBoletinData();
    if (!data) return;
    hide(el.boletinSection);
    renderBoletinEditor(data);
    show(el.boletinEditorSection);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  /* Confirmar sin cambios */
  el.confirmBoletinBtn?.addEventListener('click', () => {
    setPdfDownloadEnabled(true);
    hide(el.confirmBoletinBtn);
    setAlert(el.boletinAlert, 'Boletín confirmado. Ya puedes descargar el PDF.', 'success');
  });

  /* Descargar PDF */
  el.downloadPdfBtn?.addEventListener('click', () => {
    const resultId = resolveResultId();
    if (!resultId) {
      setAlert(el.boletinAlert, MSG.BOLETIN_PDF_ERROR, 'danger');
      return;
    }
    const boletin = getBoletinData();
    const name    = boletin?.cuantitativo?.nombre_sujeto?.trim() || 'estudiante';
    downloadBoletinPdf(resultId, name);
  });
}


/* ══════════════════════════════════════════════
   RENDER EDITOR DE BOLETÍN
   Llamado desde openBoletinBtn → navega a #boletinEditorSection
   Renderiza vista padre + precarga inputs del orientador.
   ══════════════════════════════════════════════ */
export function renderBoletinEditor(data) {
  if (!data) return;

  const c    = data.cuantitativo ?? {};
  const cual = data.cualitativo  ?? {};
  const comb = data.combinado    ?? {};

  /* — Tab activo por defecto: vista padre — */
  _editorSetTab('padre');

  /* — Limpiar alerts — */
  clearAlert(el.editorAlert);

  /* ── Vista padre: header estudiante ── */
  if (el.editorStudentName) {
    el.editorStudentName.textContent =
      c.nombre_sujeto || c.display_name || '—';
  }
  if (el.editorStudentMeta) {
    const parts = [c.subject, c.test_code].filter(Boolean);
    el.editorStudentMeta.textContent = parts.join(' — ') || '—';
  }
  if (el.editorStudentDates) {
    const testDate = formatDate(c.test_date);
    const emitDate = formatDate(data.generated_at);
    el.editorStudentDates.textContent =
      `Test aplicado: ${testDate} · Emitido: ${emitDate}`;
  }

  /* ── KPIs hero ── */
  if (el.editorKpiRow) {
    const semaforo = c.semaforo ?? '';
    const tone     = toneForSemaforo(semaforo);
    const kpis = [
      { value: formatPercent(_toFloat(c.percentage)),          label: 'Ejercicios correctos' },
      { value: formatMinutes(_toFloat(c.study_time_min)),      label: 'Tiempo empleado'      },
      { value: formatMinutes(_toFloat(c.target_time_min)),     label: 'Tiempo esperado'      },
      { value: semaforoLabelText(semaforo), label: 'Resultado general', tone },
    ];
    el.editorKpiRow.innerHTML = kpis
      .map(k => `
        <div class="editor-kpi-card ${k.tone ? `editor-kpi-semaforo tone-${k.tone}` : ''}">
          <span class="editor-kpi-value">${_escapeHtml(String(k.value))}</span>
          <span class="editor-kpi-label">${k.label}</span>
        </div>
      `)
      .join('');
  }

  /* ── Punto de inicio ── */
  if (el.editorStartingPoint && el.editorSpDetail) {
    const sp = c.starting_point;
    if (sp) {
      el.editorSpDetail.textContent =
        `${sp}${c.ws ? ' · Nivel WS: ' + c.ws : ''}${c.current_level ? ' · ' + c.current_level : ''}`;
      show(el.editorStartingPoint);
    } else {
      hide(el.editorStartingPoint);
    }
  }

  /* ── Gráfica de barras por sección cualitativa ── */
  if (el.editorSectionsChart) {
    const secciones = cual.secciones ?? [];
    if (secciones.length) {
      el.editorSectionsChart.innerHTML = _buildSectionsChart(secciones);
    } else {
      el.editorSectionsChart.innerHTML =
        '<p class="editor-empty">Sin datos de secciones.</p>';
    }
  }

  /* ── Barras de hábitos de trabajo ── */
  if (el.editorHabitsBars) {
    const secciones = cual.secciones ?? [];
    if (secciones.length) {
      el.editorHabitsBars.innerHTML = secciones
        .map(sec => {
          const pct   = _toFloat(sec.puntaje) ?? 0;
          const color = _habitBarColor(pct);
          return `
            <div class="editor-habit-row">
              <span class="editor-habit-name">${_escapeHtml(sec.nombre ?? '—')}</span>
              <div class="editor-habit-bar-wrap">
                <div class="editor-habit-bar-fill ${color}"
                     style="width:${Math.min(100, pct)}%"></div>
              </div>
              <span class="editor-habit-score">${Math.round(pct)}/100</span>
            </div>
          `;
        })
        .join('');
    } else {
      el.editorHabitsBars.innerHTML =
        '<p class="editor-empty">Sin hábitos registrados.</p>';
    }
  }

  /* ── Chips de comportamientos observados (auto_flags) ── */
  if (el.editorFlagsBlock && el.editorFlagsChips) {
    const flags = cual.auto_flags ?? [];
    if (flags.length) {
      el.editorFlagsChips.innerHTML = flags
        .map(f => `<span class="editor-flag-chip">${_escapeHtml(String(f))}</span>`)
        .join('');
      show(el.editorFlagsBlock);
    } else {
      hide(el.editorFlagsBlock);
    }
  }

  /* ── Narrativa ── */
  if (el.editorNarrativaText) {
    el.editorNarrativaText.textContent =
      c.recommendation || comb.narrativa || '—';
  }

  /* ── Semáforo ── */
  const semVal  = c.semaforo ?? '';
  const semTone = toneForSemaforo(semVal);
  if (el.editorSemaforoCircle) {
    el.editorSemaforoCircle.className = `editor-semaforo-circle tone-${semTone}`;
    el.editorSemaforoCircle.textContent = semaforoEmoji(semVal);
  }
  if (el.editorSemaforoLabel) {
    el.editorSemaforoLabel.textContent = semaforoLabelText(semVal);
  }
  if (el.editorSemaforoDesc) {
    el.editorSemaforoDesc.textContent = comb.narrativa ?? '—';
  }

  /* ── Editor orientador: campos cuantitativos ── */
  if (el.editorCuantGrid) {
    const cuantFields = [
      { key: 'cuantitativo.ws',              label: 'Nivel WS',             type: 'text',   value: c.ws ?? '',                          placeholder: 'Ej: 5A'  },
      { key: 'cuantitativo.starting_point',  label: 'Punto de inicio',      type: 'text',   value: c.starting_point ?? '',              placeholder: 'Ej: B41' },
      { key: 'cuantitativo.correct_answers', label: 'Respuestas correctas', type: 'number', value: c.correct_answers ?? '',             placeholder: 'Ej: 18', min: 0 },
      { key: 'cuantitativo.total_questions', label: 'Total preguntas',       type: 'number', value: c.total_questions ?? '',             placeholder: 'Ej: 20', min: 1 },
      { key: 'cuantitativo.study_time_min',  label: 'Tiempo estudio (min)', type: 'number', value: _toFloat(c.study_time_min) ?? '',    placeholder: 'Ej: 45', min: 0 },
      { key: 'cuantitativo.target_time_min', label: 'Tiempo esperado (min)', type: 'number', value: _toFloat(c.target_time_min) ?? '', placeholder: 'Ej: 30', min: 0 },
    ];
    el.editorCuantGrid.innerHTML = cuantFields
      .map(f => {
        const safeId = `edit_${f.key.replace('.', '_')}`;
        return `
          <div class="editor-edit-field">
            <label class="editor-edit-label" for="${safeId}">${f.label}</label>
            <input type="${f.type}" id="${safeId}" data-key="${f.key}"
                   class="form-input editor-edit-input"
                   value="${_escapeAttr(String(f.value))}"
                   placeholder="${_escapeAttr(f.placeholder)}"
                   ${f.min !== undefined ? `min="${f.min}"` : ''}>
          </div>
        `;
      })
      .join('');
  }

  /* ── Editor orientador: sliders de secciones cualitativas ── */
  if (el.editorCualSliders) {
    const secciones = cual.secciones ?? [];
    if (secciones.length) {
      el.editorCualSliders.innerHTML = secciones
        .map((sec, i) => {
          const pct    = Math.round(_toFloat(sec.puntaje) ?? 0);
          const safeId = `slider_sec_${i}`;
          return `
            <div class="editor-slider-row">
              <span class="editor-slider-name">${_escapeHtml(sec.nombre ?? '—')}</span>
              <input type="range" id="${safeId}"
                     class="editor-slider"
                     data-idx="${i}"
                     data-seccion="${_escapeAttr(sec.nombre ?? '')}"
                     min="0" max="100" step="1"
                     value="${pct}">
              <span class="editor-slider-val" id="${safeId}_val">${pct}</span>
            </div>
          `;
        })
        .join('');

      /* Actualizar label en tiempo real */
      el.editorCualSliders.querySelectorAll('.editor-slider').forEach(slider => {
        const valEl = document.getElementById(`${slider.id}_val`);
        slider.addEventListener('input', () => {
          if (valEl) valEl.textContent = slider.value;
        });
      });
    } else {
      el.editorCualSliders.innerHTML =
        '<p class="editor-empty">Sin secciones para editar.</p>';
    }
  }


  /* ── Precargar textareas de narrativa ── */
  if (el.editorRecommendation) el.editorRecommendation.value = c.recommendation ?? '';
  if (el.editorNarrativa)      el.editorNarrativa.value      = comb.narrativa ?? '';

  /* ── Bind botones del editor (solo una vez) ── */
  _bindEditorButtons();
}


/* ══════════════════════════════════════════════
   TABS DEL EDITOR
   ══════════════════════════════════════════════ */
function _editorSetTab(tab) {
  const isPadre = tab === 'padre';

  if (el.editorTabPadre) {
    el.editorTabPadre.classList.toggle('active', isPadre);
    el.editorTabPadre.setAttribute('aria-selected', String(isPadre));
  }
  if (el.editorTabOrientador) {
    el.editorTabOrientador.classList.toggle('active', !isPadre);
    el.editorTabOrientador.setAttribute('aria-selected', String(!isPadre));
  }
  if (el.editorViewPadre)       isPadre  ? show(el.editorViewPadre)       : hide(el.editorViewPadre);
  if (el.editorViewOrientador)  !isPadre ? show(el.editorViewOrientador)  : hide(el.editorViewOrientador);
}


/* ══════════════════════════════════════════════
   BIND BOTONES DEL EDITOR
   Se usa flag para evitar listeners duplicados
   en recargas del editor.
   ══════════════════════════════════════════════ */
let _editorBound = false;

function _bindEditorButtons() {
  if (_editorBound) return;
  _editorBound = true;

  /* Tabs */
  el.editorTabPadre?.addEventListener('click',      () => _editorSetTab('padre'));
  el.editorTabOrientador?.addEventListener('click', () => _editorSetTab('orientador'));

  /* Volver al resumen */
  el.editorBackBtn?.addEventListener('click', () => {
    hide(el.boletinEditorSection);
    show(el.boletinSection);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  /* Guardar y generar PDF */
  el.editorSaveBtn?.addEventListener('click', _handleEditorSave);
}


/* ══════════════════════════════════════════════
   GUARDAR DESDE EDITOR — PATCH + habilitar PDF
   ══════════════════════════════════════════════ */
async function _handleEditorSave() {
  const resultId = resolveResultId();
  if (!resultId) {
    setAlert(el.editorAlert, 'Sin result_id para guardar.', 'danger');
    return;
  }

  const corregido_por = el.editorCorregidoPor?.value?.trim() || '';
  if (!corregido_por || corregido_por.length < 2) {
    setAlert(el.editorAlert, 'Ingresa el nombre del orientador (mínimo 2 caracteres).', 'warning');
    el.editorCorregidoPor?.focus();
    return;
  }

  const current     = getBoletinData() ?? {};
  const currentC    = current.cuantitativo ?? {};
  const currentComb = current.combinado    ?? {};

  const numericKeys = [
    'cuantitativo.correct_answers',
    'cuantitativo.total_questions',
    'cuantitativo.study_time_min',
    'cuantitativo.target_time_min',
  ];

  const correcciones = [];

  /* — Campos cuantitativos del grid — */
  el.editorCuantGrid?.querySelectorAll('.editor-edit-input[data-key]').forEach(inp => {
    const key      = inp.dataset.key;
    const rawValue = inp.value.trim();
    const shortKey = key.split('.').pop();

    const valor_nuevo = numericKeys.includes(key) && rawValue !== ''
      ? Number(rawValue)
      : rawValue || null;

    const currentNorm = numericKeys.includes(key)
      ? _toFloat(currentC[shortKey])
      : (currentC[shortKey] ?? null);

    if (String(valor_nuevo ?? '') !== String(currentNorm ?? '')) {
      correcciones.push({
        campo:          key,
        valor_original: currentNorm,
        valor_nuevo,
        motivo:         null,
      });
    }
  });

  /* — Recommendation textarea — */
  if (el.editorRecommendation) {
    const newRec = el.editorRecommendation.value.trim();
    const oldRec = currentC.recommendation ?? '';
    if (newRec !== oldRec) {
      correcciones.push({
        campo:          'cuantitativo.recommendation',
        valor_original: oldRec,
        valor_nuevo:    newRec,
        motivo:         null,
      });
    }
  }

  /* — Narrativa combinada textarea — */
  if (el.editorNarrativa) {
    const newNar = el.editorNarrativa.value.trim();
    const oldNar = currentComb.narrativa ?? '';
    if (newNar !== oldNar) {
      correcciones.push({
        campo:          'combinado.narrativa',
        valor_original: oldNar,
        valor_nuevo:    newNar,
        motivo:         null,
      });
    }
  }

  /* — Sliders de secciones cualitativas — */
  /* El campo usa índice NUMÉRICO: cualitativo.secciones.0.puntaje
     El backend parsea dot-notation con int() sobre el tercer segmento.
     Usar el nombre como índice genera int("Postura y actitud") → 422. */
  const seccionesActuales = current.cualitativo?.secciones ?? [];

  el.editorCualSliders?.querySelectorAll('.editor-slider').forEach(slider => {
    const idx         = parseInt(slider.dataset.idx ?? '-1', 10);
    if (idx === -1 || idx >= seccionesActuales.length) return;

    const valor_nuevo    = Number(slider.value);
    const valor_original = _toFloat(seccionesActuales[idx]?.puntaje) ?? null;

    if (valor_nuevo !== valor_original) {
      correcciones.push({
        campo:          `cualitativo.secciones.${idx}.puntaje`,
        valor_original,
        valor_nuevo,
        motivo:         null,
      });
    }
  });

  if (!correcciones.length) {
    setAlert(el.editorAlert, 'No hay cambios para guardar.', 'info');
    return;
  }

  /* — Estado del botón durante el POST — */
  if (el.editorSaveBtn) {
    el.editorSaveBtn.disabled    = true;
    el.editorSaveBtn.textContent = '⏳ Guardando...';
  }

  const { ok, data, error } = await patchBoletin(resultId, { correcciones, corregido_por });

  if (el.editorSaveBtn) {
    el.editorSaveBtn.disabled    = false;
    el.editorSaveBtn.textContent = '💾 Guardar y generar PDF';
  }

  if (!ok || !data) {
    setAlert(el.editorAlert, error ?? MSG.BOLETIN_PATCH_ERROR, 'danger');
    return;
  }

  /* — Éxito: volver al resumen con PDF habilitado — */
  setBoletinData(data);
  hide(el.boletinEditorSection);
  show(el.boletinSection);
  renderBoletin(data);
  setPdfDownloadEnabled(true);
  hide(el.confirmBoletinBtn);
  setAlert(
    el.boletinAlert,
    MSG.BOLETIN_PATCH_SUCCESS ?? 'Correcciones guardadas. PDF listo.',
    'success'
  );
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ══════════════════════════════════════════════
   HELPERS DE RENDER — gráfica de barras secciones
   ══════════════════════════════════════════════ */
function _buildSectionsChart(secciones) {
  const maxPct = 100;
  const bars = secciones
    .map(sec => {
      const pct = Math.min(100, _toFloat(sec.puntaje) ?? 0);
      return `
        <div class="editor-chart-col">
          <div class="editor-chart-bar-wrap">
            <div class="editor-chart-bar-fill" style="height:${pct}%"></div>
          </div>
          <span class="editor-chart-label">${_escapeHtml(sec.nombre ?? '—')}</span>
        </div>
      `;
    })
    .join('');

  return `<div class="editor-chart-grid">${bars}</div>`;
}

function _habitBarColor(pct) {
  if (pct >= 76) return 'bar-verde';
  if (pct >= 51) return 'bar-amarillo';
  if (pct >= 26) return 'bar-naranja';
  return 'bar-rojo';
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

  if (el.boletinConfidenceDot) el.boletinConfidenceDot.classList.remove('warn', 'alert');
  if (el.boletinSemaforoLabel) el.boletinSemaforoLabel.className = 'semaforo-label';

  /* Reset editor */
  if (el.editorKpiRow)          el.editorKpiRow.innerHTML        = '';
  if (el.editorSectionsChart)   el.editorSectionsChart.innerHTML = '';
  if (el.editorHabitsBars)      el.editorHabitsBars.innerHTML    = '';
  if (el.editorFlagsChips)      el.editorFlagsChips.innerHTML    = '';
  if (el.editorCuantGrid)       el.editorCuantGrid.innerHTML     = '';
  if (el.editorCualSliders)     el.editorCualSliders.innerHTML   = '';
  if (el.editorRecommendation)  el.editorRecommendation.value    = '';
  if (el.editorNarrativa)       el.editorNarrativa.value         = '';
  if (el.editorCorregidoPor)    el.editorCorregidoPor.value      = '';
  _editorBound = false;

  clearAlert(el.boletinAlert);
  clearAlert(el.editorAlert);
  hide(el.correctionPanel);
  hide(el.boletinContent);
  hide(el.boletinSection);
  hide(el.boletinEditorSection);

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