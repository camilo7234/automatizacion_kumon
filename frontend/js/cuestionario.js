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
          en modo lectura y dispara el boletín si está habilitado
        - POST /cuestionario/{resultId} → envía respuestas
        - Al completar notifica a app.js via onCuestionarioDone()
          (sin argumentos — app.js carga el boletín directamente)
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
let _onCuestionarioDone = null;  // callback() → void  (notifica a app.js)
let _questions          = [];    // Question[] cacheadas para el submit
let _yaCompletado       = false; // true → modo lectura




/* ══════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════ */
export function initCuestionario(onCuestionarioDone) {
  _onCuestionarioDone = onCuestionarioDone;
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
    setAlert(
      el.cuestionarioAlert,
      error ?? MSG.CUESTIONARIO_LOADING,
      'danger'
    );
    return;
  }


  setCuestionario(data);
  clearAlert(el.cuestionarioAlert);


  _questions    = _extraerItemsDeSeciones(data.cuestionario?.secciones ?? []);
  _yaCompletado = Boolean(data.ya_completado);


  /* Header del cuestionario */
  _renderHeader(data);


  /* Preguntas */
  _renderQuestions(
    _questions,
    _yaCompletado,
    data.respuestas_guardadas ?? {}
  );


  /* Footer — campo completado_por + botón submit */
  _renderFooter(data);


  /* Si ya estaba completado y el boletín está habilitado,
     disparar directamente sin esperar submit */
  if (_yaCompletado) {
    setCuestionarioDone(true);
    if (data.boletin_habilitado) {
      _onCuestionarioDone?.();
    }
  }
}




/* ══════════════════════════════════════════════
   HEADER — nombre del sujeto + tag de estado
   Fuente: CuestionarioResponse.nombre_sujeto
   ══════════════════════════════════════════════ */
function _renderHeader(data) {
  /* nombre_sujeto es el campo real de CuestionarioResponse */
  if (el.cuestionarioStudent) {
    el.cuestionarioStudent.textContent =
      data.nombre_sujeto?.trim() || data.result_id || '—';
  }


  /* Tag de estado */
  if (el.cuestionarioStatusTag) {
    if (_yaCompletado) {
      setTag(el.cuestionarioStatusTag, '✅ Completado', 'success');


      /* completado_at puede ser null si el flag es true pero la fecha no llegó */
      const completadoAt  = data.completado_at
        ? formatDate(data.completado_at)
        : 'fecha desconocida';
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
   EXTRACTOR — convierte secciones del backend
   en lista plana de items para el formulario.
   CORRECCIÓN:
   - seccion.items → seccion.preguntas
     (clave real de CuestionarioResponse según el schema
      y la función obtener_cuestionario del backend)
   - seccion.titulo → seccion.nombre
     (clave real del objeto sección retornado por el backend)
   ══════════════════════════════════════════════ */
function _extraerItemsDeSeciones(secciones) {
  const escala = [1, 2, 3, 4, 5];
  const labelMap = {
    1: 'Muy bajo',
    2: 'Bajo',
    3: 'Medio',
    4: 'Alto',
    5: 'Muy alto',
  };


  const questions = [];


  for (const seccion of secciones) {
    for (const item of (seccion.preguntas ?? [])) {
      questions.push({
        id:                item.id,
        label:             item.texto ?? item.id,
        type:              QUESTION_TYPE.RADIO,
        required:          true,
        sectionId:         seccion.nombre,
        sectionTitle:      seccion.nombre,
        options:           escala.map(v => ({ value: String(v), label: labelMap[v] })),
        prefill_valor:     item.prefill_valor     ?? null,
        prefill_fuente:    item.prefill_fuente    ?? null,
        prefill_confianza: item.prefill_confianza ?? null,
      });
    }
  }


  return questions;
}


/* ══════════════════════════════════════════════
   RENDER PREGUNTAS — agrupa por sección
   y muestra sugerencia de prefill si existe.
   CORRECCIÓN: la agrupación usaba push al último
   elemento del array, lo que duplicaba secciones
   cuando preguntas de distintas secciones se
   intercalaban. Ahora usa find() para localizar
   la sección existente antes de crear una nueva.
   ══════════════════════════════════════════════ */
function _renderQuestions(questions, readOnly, savedAnswers) {
  if (!el.cuestionarioBody) return;


  if (!questions.length) {
    el.cuestionarioBody.innerHTML =
      '<p class="empty-state-text">No hay preguntas disponibles.</p>';
    return;
  }


  /* Agrupar por sectionId respetando el orden original */
  const secciones = [];
  for (const q of questions) {
    let sec = secciones.find(s => s.id === q.sectionId);
    if (!sec) {
      sec = { id: q.sectionId, titulo: q.sectionTitle, items: [] };
      secciones.push(sec);
    }
    sec.items.push(q);
  }


  el.cuestionarioBody.innerHTML = secciones.map(sec => `
    <div class="question-section">
      <h3 class="question-section-title">${_escapeHtml(sec.titulo)}</h3>
      ${sec.items.map(q => _buildQuestionBlock(q, readOnly, savedAnswers)).join('')}
    </div>
  `).join('');
}
function _buildQuestionBlock(q, readOnly, savedAnswers) {
  const saved     = savedAnswers[q.id] ?? null;
  const inputHtml = _buildInput(q, readOnly, saved);


  return `
    <div class="question-block" data-question-id="${q.id}">
      <label class="question-label" for="q_${q.id}">
        ${_escapeHtml(q.label ?? q.text ?? `Pregunta ${q.id}`)}
        ${q.required
          ? '<span class="required-star" aria-hidden="true">*</span>'
          : ''}
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
        const checked = saved === opt.value ? 'checked' : '';
        const optId   = `${id}_${opt.value}`;
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
      const rows = q.rows ?? 3;
      const text = saved ? _escapeHtml(String(saved)) : '';
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
   FOOTER — completado_por + observacion_cualitativa + submit
   Textos de botón alineados con setCuestionarioSubmitting en ui.js:
     activo   → 'Guardar validación'
     disabled → '✅ Ya guardado'
   ══════════════════════════════════════════════ */
function _renderFooter(data) {
  /* completado_por: si ya está completo, rellenar con el valor guardado */
  if (el.completadoPorInput) {
    el.completadoPorInput.value    = data.completado_por ?? '';
    el.completadoPorInput.disabled = _yaCompletado;
  }


  /* Botón submit — texto alineado con setCuestionarioSubmitting */
  if (el.saveCuestionarioBtn) {
    el.saveCuestionarioBtn.disabled    = _yaCompletado;
    el.saveCuestionarioBtn.textContent = _yaCompletado
      ? '✅ Ya guardado'
      : 'Guardar validación';
  }


  /* Bind del evento submit solo si no estaba ya completado */
  if (!_yaCompletado) {
    el.cuestionarioForm?.removeEventListener('submit', _handleSubmit);
    el.cuestionarioForm?.addEventListener('submit', _handleSubmit);
  }
}




/* ══════════════════════════════════════════════
   RECOLECCIÓN DE RESPUESTAS
   ══════════════════════════════════════════════ */
function _collectAnswers() {
  const respuestas = {};


  _questions.forEach(q => {
    const name = `q_${q.id}`;


    switch (q.type) {


      case QUESTION_TYPE.RADIO: {
        const checked = el.cuestionarioBody
          ?.querySelector(`input[name="${name}"]:checked`);
        /* Convertir a número entero — el backend espera int en escala 1-5 */
        const raw = checked?.value ?? null
        respuestas[q.id] = raw !== null ? parseInt(raw, 10) : null;
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


  const respuestas     = _collectAnswers();
  const completado_por = el.completadoPorInput?.value?.trim() || null;


  /* Validar que al menos una respuesta no sea vacía */
  const hasAnswer = Object.values(respuestas).some(v =>
    v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)
  );


  if (!hasAnswer) {
    setAlert(el.cuestionarioAlert, MSG.CUESTIONARIO_EMPTY, 'warning');
    return;
  }


  /* Construir payload alineado con RespuestaCuestionarioRequest:
     { respuestas, completado_por, observacion_libre }
     observacion_libre: textarea libre con id="observacion_cualitativa" */
  const payload = {
    respuestas,
    completado_por,
    observacion_libre: _getObservacionCualitativa(),
  };


  setCuestionarioSubmitting(true);


  const { ok, data, error } = await submitCuestionario(resultId, payload);


  setCuestionarioSubmitting(false);


  if (!ok || !data) {
    setAlert(el.cuestionarioAlert, error ?? MSG.CUESTIONARIO_ERROR, 'danger');
    return;
  }


  setCuestionarioDone(true);


  /* Actualizar UI a modo "completado" */
  setTag(el.cuestionarioStatusTag, '✅ Completado', 'success');
  if (el.saveCuestionarioBtn) {
    el.saveCuestionarioBtn.disabled    = true;
    el.saveCuestionarioBtn.textContent = '✅ Ya guardado';
  }


  setAlert(el.cuestionarioAlert, MSG.CUESTIONARIO_SUCCESS, 'success');


  /* Notificar a app.js — sin argumentos.
     app.js llama loadBoletin(resultId) internamente. */
  _onCuestionarioDone?.();
}




/* ══════════════════════════════════════════════
   OBSERVACIÓN CUALITATIVA LIBRE
   Textarea opcional fuera del formulario dinámico.
   id="observacion_cualitativa" en el HTML.
   El campo del backend es observacion_libre en
   RespuestaCuestionarioRequest.
   ══════════════════════════════════════════════ */
function _getObservacionCualitativa() {
  const ta = document.getElementById('observacion_cualitativa');
  return ta?.value?.trim() || null;
}




/* ══════════════════════════════════════════════
   RESET PÚBLICO
   ══════════════════════════════════════════════ */
export function resetCuestionario() {
  _questions    = [];
  _yaCompletado = false;


  if (el.cuestionarioBody)    el.cuestionarioBody.innerHTML      = '';
  if (el.cuestionarioStudent) el.cuestionarioStudent.textContent = '';
  if (el.completadoPorInput)  el.completadoPorInput.value        = '';


  if (el.saveCuestionarioBtn) {
    el.saveCuestionarioBtn.disabled    = false;
    el.saveCuestionarioBtn.textContent = 'Guardar validación';
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