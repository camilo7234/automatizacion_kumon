/* ============================================================
   KUMON · MÓDULO DE CUESTIONARIO
   Archivo: frontend/js/cuestionario.js
   Depende de: config.js · api.js · state.js · ui.js · formatters.js
   Rol: Carga y renderiza el formulario de validación
        cualitativa del orientador.
        - GET /cuestionario/{resultId} → construye el form
        - Renderiza cada pregunta según su type
          (radio, select, textarea, number, checkbox)
        - Si ya_completado === true muestra el form
          en modo lectura con las respuestas guardadas
        - POST /cuestionario/{resultId} → envía respuestas
        - Al recibir BoletinResponse notifica a app.js
          via onBoletinReady(boletinData)
   ============================================================ */

import {
  QUESTION_TYPE,
  MSG,
}                                         from './config.js';

import { getCuestionario, submitCuestionario } from './api.js';
import {
  resolveResultId,
  setCuestionario,
  setCuestionarioDone,
  setBoletinData,
}                                         from './state.js';
import {
  el,
  setAlert,
  clearAlert,
  show,
  hide,
  setTag,
  setCuestionarioSubmitting,
}                                         from './ui.js';
import { formatDate, titleCase }          from './formatters.js';


/* ══════════════════════════════════════════════
   ESTADO INTERNO
   ══════════════════════════════════════════════ */
let _onBoletinReady = null;  // callback(boletinData) → void
let _questions      = [];    // Question[] cacheadas para el submit
let _yaCompletado   = false; // true → modo lectura


/* ══════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════ */
export function initCuestionario(onBoletinReady) {
  _onBoletinReady = onBoletinReady;
}


/* ══════════════════════════════════════════════
   LOAD & RENDER
   Llamado desde resultado.js vía app.js → onResultReady
   ══════════════════════════════════════════════ */
export async function loadCuestionario() {
  const resultId = resolveResultId();
  if (!resultId) {
    setAlert(el.cuestionarioAlert, 'No hay result_id disponible.', 'danger');
    return;
  }

  show(el.cuestionarioSection);
  clearAlert(el.cuestionarioAlert);
  setAlert(el.cuestionarioAlert, MSG.CUESTIONARIO_LOADING, 'info');

  const { ok, data, error } = await getCuestionario(resultId);

  if (!ok || !data) {
    setAlert(el.cuestionarioAlert, error ?? MSG.CUESTIONARIO_LOADING, 'danger');
    return;
  }

  setCuestionario(data);
  clearAlert(el.cuestionarioAlert);

  _questions     = data.questions  ?? [];
  _yaCompletado  = Boolean(data.ya_completado);

  /* Header del cuestionario */
  _renderHeader(data);

  /* Preguntas */
  _renderQuestions(_questions, _yaCompletado, data.respuestas_guardadas ?? {});

  /* Footer — campo completado_por + botón submit */
  _renderFooter(data);

  /* Si ya estaba completado, cargar directamente el boletín */
  if (_yaCompletado) {
    setCuestionarioDone(true);
    show(el.cuestionarioSection);
  }
}


/* ══════════════════════════════════════════════
   HEADER — nombre del estudiante + tag de estado
   ══════════════════════════════════════════════ */
function _renderHeader(data) {
  /* Nombre */
  if (el.cuestionarioStudent) {
    el.cuestionarioStudent.textContent =
      data.student_name ?? data.result_id ?? '—';
  }

  /* Tag de estado */
  if (el.cuestionarioStatusTag) {
    if (_yaCompletado) {
      setTag(el.cuestionarioStatusTag, '✅ Completado', 'success');
      const completadoAt  = formatDate(data.completado_at);
      const completadoPor = data.completado_por ?? 'Orientador';
      el.cuestionarioStatusTag.setAttribute(
        'title',
        `Completado por ${completadoPor} el ${completadoAt}`
      );
    } else {
      setTag(el.cuestionarioStatusTag, '⏳ Pendiente', 'warning');
    }
  }
}


/* ══════════════════════════════════════════════
   RENDER PREGUNTAS
   Construye el HTML del formulario dinámicamente
   ══════════════════════════════════════════════ */
function _renderQuestions(questions, readOnly, savedAnswers) {
  if (!el.cuestionarioBody) return;

  if (!questions.length) {
    el.cuestionarioBody.innerHTML =
      '<p class="empty-state-text">No hay preguntas disponibles.</p>';
    return;
  }

  el.cuestionarioBody.innerHTML = questions
    .map(q => _buildQuestionBlock(q, readOnly, savedAnswers))
    .join('');
}

function _buildQuestionBlock(q, readOnly, savedAnswers) {
  const saved = savedAnswers[q.id] ?? null;

  const inputHtml = _buildInput(q, readOnly, saved);

  return `
    <div class="question-block" data-question-id="${q.id}">
      <label class="question-label" for="q_${q.id}">
        ${_escapeHtml(q.label ?? q.text ?? `Pregunta ${q.id}`)}
        ${q.required ? '<span class="required-star" aria-hidden="true">*</span>' : ''}
      </label>
      ${q.description
        ? `<p class="question-description">${_escapeHtml(q.description)}</p>`
        : ''}
      <div class="question-input-wrap">
        ${inputHtml}
      </div>
    </div>
  `;
}


/* ══════════════════════════════════════════════
   BUILD INPUT — según el type de la pregunta
   ══════════════════════════════════════════════ */
function _buildInput(q, readOnly, saved) {
  const disabled = readOnly ? 'disabled' : '';
  const id       = `q_${q.id}`;
  const name     = `q_${q.id}`;

  switch (q.type) {

    /* ── RADIO ── */
    case QUESTION_TYPE.RADIO: {
      const options = q.options ?? [];
      return options.map(opt => {
        const checked  = saved === opt.value ? 'checked' : '';
        const optId    = `${id}_${opt.value}`;
        return `
          <label class="radio-option ${readOnly && checked ? 'selected' : ''}">
            <input type="radio"
                   id="${optId}"
                   name="${name}"
                   value="${_escapeAttr(opt.value)}"
                   ${checked} ${disabled}>
            <span class="radio-label">${_escapeHtml(opt.label ?? opt.value)}</span>
          </label>
        `;
      }).join('');
    }

    /* ── SELECT ── */
    case QUESTION_TYPE.SELECT: {
      const options = q.options ?? [];
      return `
        <select id="${id}" name="${name}" class="form-select" ${disabled}>
          <option value="">— Selecciona —</option>
          ${options.map(opt => {
            const sel = saved === opt.value ? 'selected' : '';
            return `<option value="${_escapeAttr(opt.value)}" ${sel}>
              ${_escapeHtml(opt.label ?? opt.value)}
            </option>`;
          }).join('')}
        </select>
      `;
    }

    /* ── TEXTAREA ── */
    case QUESTION_TYPE.TEXTAREA: {
      const rows  = q.rows ?? 3;
      const text  = saved ? _escapeHtml(String(saved)) : '';
      return `
        <textarea id="${id}"
                  name="${name}"
                  class="form-textarea"
                  rows="${rows}"
                  placeholder="${_escapeAttr(q.placeholder ?? '')}"
                  ${disabled}>${text}</textarea>
      `;
    }

    /* ── NUMBER ── */
    case QUESTION_TYPE.NUMBER: {
      const min  = q.min  !== undefined ? `min="${q.min}"`   : '';
      const max  = q.max  !== undefined ? `max="${q.max}"`   : '';
      const step = q.step !== undefined ? `step="${q.step}"` : 'step="1"';
      const val  = saved !== null ? `value="${_escapeAttr(saved)}"` : '';
      return `
        <input type="number"
               id="${id}"
               name="${name}"
               class="form-input"
               ${min} ${max} ${step} ${val}
               placeholder="${_escapeAttr(q.placeholder ?? '')}"
               ${disabled}>
      `;
    }

    /* ── CHECKBOX ── */
    case QUESTION_TYPE.CHECKBOX: {
      const options  = q.options ?? [];
      const savedArr = Array.isArray(saved) ? saved : [];
      return options.map(opt => {
        const checked = savedArr.includes(opt.value) ? 'checked' : '';
        const optId   = `${id}_${opt.value}`;
        return `
          <label class="checkbox-option ${readOnly && checked ? 'selected' : ''}">
            <input type="checkbox"
                   id="${optId}"
                   name="${name}"
                   value="${_escapeAttr(opt.value)}"
                   ${checked} ${disabled}>
            <span class="checkbox-label">
              ${_escapeHtml(opt.label ?? opt.value)}
            </span>
          </label>
        `;
      }).join('');
    }

    /* ── FALLBACK ── */
    default:
      return `<p class="question-unknown">Tipo desconocido: ${_escapeHtml(q.type)}</p>`;
  }
}


/* ══════════════════════════════════════════════
   FOOTER — completado_por + observacion_libre + submit
   ══════════════════════════════════════════════ */
function _renderFooter(data) {
  /* completado_por: si ya está completo, rellenar con el valor guardado */
  if (el.completadoPorInput) {
    el.completadoPorInput.value    = data.completado_por ?? '';
    el.completadoPorInput.disabled = _yaCompletado;
  }

  /* Botón submit */
  if (el.saveCuestionarioBtn) {
    el.saveCuestionarioBtn.disabled = _yaCompletado;
    el.saveCuestionarioBtn.textContent = _yaCompletado
      ? '✅ Ya generado'
      : 'Generar boletín';
  }

  /* Bind del evento submit (solo si no estaba ya completado) */
  if (!_yaCompletado) {
    el.cuestionarioForm?.removeEventListener('submit', _handleSubmit);
    el.cuestionarioForm?.addEventListener('submit', _handleSubmit);
  }
}


/* ══════════════════════════════════════════════
   RECOLECCIÓN DE RESPUESTAS
   Recorre el DOM del formulario y extrae
   los valores según el tipo de cada pregunta
   ══════════════════════════════════════════════ */
function _collectAnswers() {
  const respuestas = {};

  _questions.forEach(q => {
    const name = `q_${q.id}`;

    switch (q.type) {

      case QUESTION_TYPE.RADIO: {
        const checked = el.cuestionarioBody
          ?.querySelector(`input[name="${name}"]:checked`);
        respuestas[q.id] = checked?.value ?? null;
        break;
      }

      case QUESTION_TYPE.SELECT: {
        const sel = el.cuestionarioBody
          ?.querySelector(`select[name="${name}"]`);
        respuestas[q.id] = sel?.value || null;
        break;
      }

      case QUESTION_TYPE.TEXTAREA: {
        const ta = el.cuestionarioBody
          ?.querySelector(`textarea[name="${name}"]`);
        respuestas[q.id] = ta?.value?.trim() || null;
        break;
      }

      case QUESTION_TYPE.NUMBER: {
        const inp = el.cuestionarioBody
          ?.querySelector(`input[name="${name}"]`);
        const raw = inp?.value;
        respuestas[q.id] = raw !== '' && raw !== undefined
          ? Number(raw)
          : null;
        break;
      }

      case QUESTION_TYPE.CHECKBOX: {
        const checked = el.cuestionarioBody
          ?.querySelectorAll(`input[name="${name}"]:checked`) ?? [];
        respuestas[q.id] = Array.from(checked).map(c => c.value);
        break;
      }

      default:
        respuestas[q.id] = null;
    }
  });

  return respuestas;
}


/* ══════════════════════════════════════════════
   SUBMIT
   ══════════════════════════════════════════════ */
async function _handleSubmit(e) {
  e.preventDefault();
  clearAlert(el.cuestionarioAlert);

  const resultId = resolveResultId();
  if (!resultId) {
    setAlert(el.cuestionarioAlert, 'Sin result_id.', 'danger');
    return;
  }

  const respuestas      = _collectAnswers();
  const completado_por  = el.completadoPorInput?.value?.trim() || null;

  /* Validar que al menos una respuesta no sea null */
  const hasAnswer = Object.values(respuestas).some(v =>
    v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)
  );

  if (!hasAnswer) {
    setAlert(el.cuestionarioAlert, MSG.CUESTIONARIO_EMPTY, 'warning');
    return;
  }

  /* Construir payload */
  const payload = {
    respuestas,
    completado_por,
    /* observacion_libre — si el orientador escribió en un textarea libre */
    observacion_libre: _getObservacionLibre(),
  };

  setCuestionarioSubmitting(true);

  const { ok, data, error } = await submitCuestionario(resultId, payload);

  setCuestionarioSubmitting(false);

  if (!ok || !data) {
    setAlert(el.cuestionarioAlert, error ?? MSG.CUESTIONARIO_ERROR, 'danger');
    return;
  }

  /* Guardar boletín en estado global */
  setBoletinData(data);
  setCuestionarioDone(true);

  /* Actualizar UI del cuestionario a modo "completado" */
  setTag(el.cuestionarioStatusTag, '✅ Completado', 'success');
  if (el.saveCuestionarioBtn) {
    el.saveCuestionarioBtn.disabled    = true;
    el.saveCuestionarioBtn.textContent = '✅ Ya generado';
  }

  setAlert(el.cuestionarioAlert, MSG.CUESTIONARIO_SUCCESS, 'success');

  /* Notificar a app.js para mostrar el boletín */
  _onBoletinReady?.(data);
}


/* ══════════════════════════════════════════════
   OBSERVACIÓN LIBRE
   Busca un textarea con id="observacion_libre"
   que puede existir fuera del formulario dinámico
   ══════════════════════════════════════════════ */
function _getObservacionLibre() {
  const ta = document.getElementById('observacion_libre');
  return ta?.value?.trim() || null;
}


/* ══════════════════════════════════════════════
   RESET PÚBLICO
   ══════════════════════════════════════════════ */
export function resetCuestionario() {
  _questions    = [];
  _yaCompletado = false;

  if (el.cuestionarioBody)     el.cuestionarioBody.innerHTML    = '';
  if (el.cuestionarioStudent)  el.cuestionarioStudent.textContent = '';
  if (el.completadoPorInput)   el.completadoPorInput.value       = '';
  if (el.saveCuestionarioBtn) {
    el.saveCuestionarioBtn.disabled    = false;
    el.saveCuestionarioBtn.textContent = 'Generar boletín';
  }

  clearAlert(el.cuestionarioAlert);
  hide(el.cuestionarioSection);

  el.cuestionarioForm?.removeEventListener('submit', _handleSubmit);
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