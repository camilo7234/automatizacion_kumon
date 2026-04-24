/* ============================================================
   KUMON · CAPA DE COMUNICACIÓN CON EL BACKEND
   Archivo: frontend/js/api.js
   Depende de: config.js
   Rol: ÚNICA capa que hace fetch() al backend.
        Ningún otro módulo llama fetch() directamente.
        Cada función retorna { ok, data, error }
        para que el llamador decida cómo manejar
        el resultado sin atrapar excepciones.
   ============================================================ */

import { ENDPOINTS } from './config.js';


/* ══════════════════════════════════════════════
   HELPER INTERNO — wrapper de fetch
   Centraliza el manejo de errores HTTP y de red.
   Retorna siempre { ok: bool, data, error }
   ══════════════════════════════════════════════ */
async function _request(url, options = {}) {
  try {
    const res  = await fetch(url, options);
    const text = await res.text();

    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }

    if (!res.ok) {
      const message =
        data?.detail ??
        data?.message ??
        data?.error  ??
        `HTTP ${res.status}: ${res.statusText}`;
      return { ok: false, data: null, error: message };
    }

    return { ok: true, data, error: null };

  } catch (err) {
    /* Error de red (sin conexión, CORS, timeout) */
    return {
      ok:    false,
      data:  null,
      error: err?.message ?? 'Error de red — sin respuesta del servidor',
    };
  }
}


/* ══════════════════════════════════════════════
   HEALTH CHECK
   GET /api/v1/health
   ══════════════════════════════════════════════ */

/**
 * Verifica si el backend está disponible.
 * @returns {{ ok: bool, data, error }}
 */
export async function checkHealth() {
  return _request(ENDPOINTS.health());
}


/* ══════════════════════════════════════════════
   UPLOAD
   POST /api/v1/upload/video
   ══════════════════════════════════════════════ */

/**
 * Sube el video al backend.
 * @param {File}   file          — archivo seleccionado
 * @param {Object} meta          — { student_name, level, orientador }
 * @param {Function} onProgress  — callback(pct: 0–100) para la barra
 * @returns {{ ok: bool, data: { job_id, result_id? }, error }}
 */
export function uploadVideo(file, meta = {}, onProgress = null) {
  return new Promise((resolve) => {
    const formData = new FormData();
    formData.append('file', file);

    if (meta.student_name) formData.append('student_name', meta.student_name);
    if (meta.level)        formData.append('level',        meta.level);
    if (meta.orientador)   formData.append('orientador',   meta.orientador);

    const xhr = new XMLHttpRequest();

    /* Progreso real del upload */
    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });
    }

    xhr.addEventListener('load', () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = { raw: xhr.responseText };
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({ ok: true, data, error: null });
      } else {
        const message =
          data?.detail ??
          data?.message ??
          `HTTP ${xhr.status}`;
        resolve({ ok: false, data: null, error: message });
      }
    });

    xhr.addEventListener('error', () => {
      resolve({
        ok:    false,
        data:  null,
        error: 'Error de red al subir el video.',
      });
    });

    xhr.addEventListener('abort', () => {
      resolve({
        ok:    false,
        data:  null,
        error: 'La subida fue cancelada.',
      });
    });

    xhr.open('POST', ENDPOINTS.uploadVideo());
    xhr.send(formData);
  });
}


/* ══════════════════════════════════════════════
   JOBS
   GET /api/v1/jobs/{jobId}
   ══════════════════════════════════════════════ */

/**
 * Consulta el estado de un job de procesamiento.
 * @param {string} jobId
 * @returns {{ ok: bool, data: JobResponse, error }}
 *
 * JobResponse esperado:
 * {
 *   job_id:    string,
 *   status:    'pending'|'queued'|'processing'|'done'|'error',
 *   progress:  number | null,   // 0–100
 *   message:   string | null,
 *   result_id: string | null,   // disponible cuando status === 'done'
 *   error:     string | null,
 * }
 */
export async function getJob(jobId) {
  return _request(ENDPOINTS.getJob(jobId));
}


/* ══════════════════════════════════════════════
   RESULTS
   GET /api/v1/results/job/{jobId}
   ══════════════════════════════════════════════ */

/**
 * Obtiene el resultado completo del análisis de video.
 * @param {string} jobId
 * @returns {{ ok: bool, data: ResultResponse, error }}
 *
 * ResultResponse esperado:
 * {
 *   id:                  string,
 *   ws:                  string,
 *   study_time_min:      number,
 *   target_time_min:     number,
 *   correct_answers:     number,
 *   total_questions:     number,
 *   percentage:          number,
 *   semaforo:            'verde'|'amarillo'|'rojo',
 *   starting_point:      string,
 *   recommendation:      string,
 *   confidence_score:    number,   // 0.0 – 1.0
 *   needs_manual_review: boolean,
 * }
 */
export async function getResult(jobId) {
  return _request(ENDPOINTS.getResult(jobId));
}


/* ══════════════════════════════════════════════
   CUESTIONARIO
   GET  /api/v1/cuestionario/{resultId}
   POST /api/v1/cuestionario/{resultId}
   ══════════════════════════════════════════════ */

/**
 * Carga el formulario de validación cualitativa.
 * @param {string} resultId
 * @returns {{ ok: bool, data: CuestionarioResponse, error }}
 *
 * CuestionarioResponse esperado:
 * {
 *   result_id:    string,
 *   questions:    Question[],
 *   ya_completado: boolean,
 *   completado_at: string | null,
 *   completado_por: string | null,
 * }
 */
export async function getCuestionario(resultId) {
  return _request(ENDPOINTS.getCuestionario(resultId));
}

/**
 * Envía las respuestas del cuestionario al backend.
 * El backend genera el boletín y retorna BoletinResponse.
 * @param {string} resultId
 * @param {Object} payload — { respuestas: {}, completado_por, observacion_libre }
 * @returns {{ ok: bool, data: BoletinResponse, error }}
 *
 * BoletinResponse esperado:
 * {
 *   result_id:           string,
 *   student_name:        string,
 *   level:               string,
 *   ws:                  string,
 *   semaforo:            string,
 *   percentage:          number,
 *   puntaje_cualitativo: number,
 *   etiqueta_cualitativa:string,
 *   detalle_secciones:   Section[],
 *   study_time_min:      number,
 *   target_time_min:     number,
 *   correct_answers:     number,
 *   total_questions:     number,
 *   starting_point:      string,
 *   recommendation:      string,
 *   confidence_score:    number,
 *   needs_manual_review: boolean,
 *   observacion_libre:   string | null,
 *   status:              string,
 *   generated_at:        string,
 * }
 */
export async function submitCuestionario(resultId, payload) {
  return _request(ENDPOINTS.submitCuestionario(resultId), {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });
}


/* ══════════════════════════════════════════════
   BOLETÍN
   GET   /api/v1/boletin/{resultId}
   PATCH /api/v1/boletin/{resultId}
   ══════════════════════════════════════════════ */

/**
 * Carga el boletín generado.
 * @param {string} resultId
 * @returns {{ ok: bool, data: BoletinResponse, error }}
 */
export async function getBoletin(resultId) {
  return _request(ENDPOINTS.getBoletin(resultId));
}

/**
 * Aplica correcciones del orientador al boletín.
 * Corresponde al BLOQUE 3 del plan de migración.
 * @param {string} resultId
 * @param {Object} corrections — campos corregidos, p.ej.:
 *   {
 *     ws:               "5A",
 *     correct_answers:  19,
 *     observacion_libre:"Estudiante muy concentrado.",
 *   }
 * @returns {{ ok: bool, data: BoletinResponse, error }}
 */
export async function patchBoletin(resultId, corrections) {
  return _request(ENDPOINTS.patchBoletin(resultId), {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(corrections),
  });
}

/**
 * Descarga el PDF del boletín usando un anchor programático.
 * Abre el endpoint en una nueva pestaña para aprovechar
 * el StreamingResponse del backend.
 * @param {string} resultId
 * @param {string} studentName — para el nombre del archivo
 */
export function downloadBoletinPdf(resultId, studentName = 'boletin') {
  const url      = ENDPOINTS.getBoletinPdf(resultId);
  const filename = `boletin_${studentName.replace(/\s+/g, '_')}.pdf`;
  const a        = document.createElement('a');
  a.href         = url;
  a.download     = filename;
  a.target       = '_blank';
  a.rel          = 'noopener noreferrer';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}