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
   Fuente: backend/app/routes/upload.py
           backend/app/schemas/upload.py — VideoUploadForm
   ══════════════════════════════════════════════ */

/**
 * Sube el video al backend como multipart/form-data.
 *
 * Campos obligatorios del backend (VideoUploadForm):
 *   file            — UploadFile
 *   subject         — "matematicas" | "ingles" | "espanol"
 *   test_code       — "K1", "K2", "P1"…"P6", "M1"…"M3", "H", etc.
 *
 * Campos opcionales del backend:
 *   nombre_completo — nombre del prospecto (default: "Sin nombre")
 *   grado_escolar   — string | null
 *   nombre_escuela  — string | null
 *   nombre_acudiente— string | null
 *   telefono        — string | null
 *
 * @param {File}     file
 * @param {Object}   meta — {
 *   subject:          string (requerido),
 *   test_code:        string (requerido),
 *   nombre_completo:  string,
 *   grado_escolar:    string|null,
 *   nombre_escuela:   string|null,
 *   nombre_acudiente: string|null,
 *   telefono:         string|null,
 * }
 * @param {Function} onProgress — callback(pct: 0–100) para la barra
 * @returns {{ ok: bool, data: JobStatusResponse, error }}
 *
 * JobStatusResponse al crear:
 * {
 *   job_id:           string (UUID),
 *   status:           "queued",
 *   progress_percent: 0,
 *   error_message:    null,
 *   result_id:        null,
 *   started_at:       null,
 *   completed_at:     null,
 * }
 */
export function uploadVideo(file, meta = {}, onProgress = null) {
  return new Promise((resolve) => {
    const formData = new FormData();
    formData.append('file', file);

    /* Campos obligatorios — el backend valida su presencia */
    formData.append('subject',   meta.subject   ?? '');
    formData.append('test_code', meta.test_code ?? '');

    /* Campos opcionales — solo se envían si tienen valor */
    if (meta.nombre_completo)   formData.append('nombre_completo',  meta.nombre_completo);
    if (meta.grado_escolar)     formData.append('grado_escolar',    meta.grado_escolar);
    if (meta.nombre_escuela)    formData.append('nombre_escuela',   meta.nombre_escuela);
    if (meta.nombre_acudiente)  formData.append('nombre_acudiente', meta.nombre_acudiente);
    if (meta.telefono)          formData.append('telefono',         meta.telefono);

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
   Fuente: backend/app/schemas/job.py — JobStatusResponse
   ══════════════════════════════════════════════ */

/**
 * Consulta el estado de un job de procesamiento.
 * @param {string} jobId
 * @returns {{ ok: bool, data: JobStatusResponse, error }}
 *
 * JobStatusResponse:
 * {
 *   job_id:           string (UUID),
 *   status:           "queued"|"processing"|"done"|"error"|"manual_review",
 *   progress_percent: number,        // 0–100
 *   error_message:    string | null,
 *   result_id:        string | null, // UUID del TestResult cuando status="done"
 *   started_at:       string | null,
 *   completed_at:     string | null,
 * }
 */
export async function getJob(jobId) {
  return _request(ENDPOINTS.getJob(jobId));
}



/* ══════════════════════════════════════════════
   RESULTS
   GET /api/v1/results/job/{jobId}
   Fuente: backend/app/schemas/result.py — TestResultResponse
   ══════════════════════════════════════════════ */

/**
 * Obtiene el resultado completo del análisis de video.
 * @param {string} jobId
 * @returns {{ ok: bool, data: TestResultResponse, error }}
 *
 * TestResultResponse:
 * {
 *   id_result:           string (UUID),
 *   id_job:              string (UUID),
 *   tipo_sujeto:         string,
 *   nombre_sujeto:       string,
 *   subject:             string,
 *   test_code:           string,
 *   display_name:        string,
 *   test_date:           string | null,
 *   ws:                  string | null,
 *   study_time_min:      string | null, // Decimal serializado
 *   target_time_min:     string | null,
 *   correct_answers:     number | null,
 *   total_questions:     number | null,
 *   percentage:          string | null, // Decimal serializado
 *   current_level:       string | null,
 *   starting_point:      string | null,
 *   semaforo:            "verde"|"amarillo"|"rojo"|null,
 *   recommendation:      string | null,
 *   confidence_score:    string | null, // Decimal 0.0–1.0
 *   needs_manual_review: boolean,
 *   sections_detail:     object,
 *   raw_ocr_data:        object,
 *   tiene_observacion:   boolean,
 *   observacion_completa:boolean,
 *   created_at:          string,
 * }
 */
export async function getResult(jobId) {
  return _request(ENDPOINTS.getResult(jobId));
}



/* ══════════════════════════════════════════════
   CUESTIONARIO
   GET  /api/v1/cuestionario/{resultId}
   POST /api/v1/cuestionario/{resultId}
   Fuente: backend/app/schemas/cuestionario.py
   ══════════════════════════════════════════════ */

/**
 * Carga el formulario de validación cualitativa.
 * @param {string} resultId
 * @returns {{ ok: bool, data: CuestionarioResponse, error }}
 *
 * CuestionarioResponse:
 * {
 *   result_id:     string (UUID),
 *   subject:       string,
 *   test_code:     string,
 *   cuestionario:  object,   // estructura declarativa con secciones y preguntas
 *   ya_completado: boolean,
 *   tiene_prefills:boolean,
 *   prefill_flags: string[], // claves capturadas automáticamente por el sistema
 * }
 */
export async function getCuestionario(resultId) {
  return _request(ENDPOINTS.getCuestionario(resultId));
}


/**
 * Envía las respuestas del cuestionario al backend.
 * Guarda la ObservacionCualitativa y habilita el boletín.
 * El boletín en sí se obtiene con getBoletin(resultId).
 *
 * @param {string} resultId
 * @param {Object} payload — {
 *   respuestas:              object,  // { clave: valor } o { seccion: { clave: valor } }
 *   completado_por:          string,  // nombre del orientador (mínimo 2 caracteres, requerido)
 *   observacion_libre:       string|null,
 *   correcciones_orientador: object,  // {} por defecto
 * }
 * @returns {{ ok: bool, data: CuestionarioSubmitResponse, error }}
 *
 * CuestionarioSubmitResponse:
 * {
 *   observacion_id:    string | null (UUID),
 *   result_id:         string (UUID),
 *   total_porcentaje:  number,   // 0–100
 *   etiqueta_total:    string,   // "fortaleza"|"en_desarrollo"|"refuerzo"|"atencion"
 *   secciones:         SeccionPuntaje[],
 *   boletin_habilitado:boolean,
 *   message:           string,
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
   Fuente: backend/app/schemas/cuestionario.py — BoletinResponse / BoletinPatchRequest
   ══════════════════════════════════════════════ */

/**
 * Obtiene el boletín consolidado.
 * Solo disponible cuando el cuestionario cualitativo está completo.
 * Si el boletín no existe lo genera; si ya existe lo sirve desde BD.
 *
 * @param {string} resultId
 * @returns {{ ok: bool, data: BoletinResponse, error }}
 *
 * BoletinResponse:
 * {
 *   boletin_id:   string | null (UUID),
 *   result_id:    string (UUID),
 *   subject:      string,
 *   test_code:    string,
 *   status:       "ready" | "pending" | "corregido_por_orientador",
 *   generated_at: string | null,
 *   cuantitativo: object,
 *   cualitativo:  object,
 *   combinado:    object,
 *   gaze:         object | null,
 *   message:      string,
 * }
 */
export async function getBoletin(resultId) {
  return _request(ENDPOINTS.getBoletin(resultId));
}


/**
 * Aplica correcciones del orientador al boletín.
 * Fuente: BoletinPatchRequest
 *
 * @param {string} resultId
 * @param {Object} payload — {
 *   correcciones: [
 *     {
 *       campo:          string,  // ruta dot-notation, ej: "cuantitativo.recommendation"
 *       valor_original: any,     // valor previo (para auditoría)
 *       valor_nuevo:    any,     // valor corregido
 *       motivo:         string|null,
 *     }
 *   ],
 *   corregido_por: string,       // nombre del orientador (mínimo 2 caracteres)
 * }
 * @returns {{ ok: bool, data: BoletinPatchResponse, error }}
 *
 * BoletinPatchResponse:
 * {
 *   boletin_id:             string (UUID),
 *   result_id:              string (UUID),
 *   subject:                string,
 *   test_code:              string,
 *   status:                 string,
 *   generated_at:           string | null,
 *   cuantitativo:           object,
 *   cualitativo:            object,
 *   combinado:              object,
 *   gaze:                   object | null,
 *   correcciones_aplicadas: number,
 *   message:                string,
 * }
 */
export async function patchBoletin(resultId, payload) {
  return _request(ENDPOINTS.patchBoletin(resultId), {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });
}


/**
 * Descarga el PDF del boletín usando un anchor programático.
 * Aprovecha el StreamingResponse del backend directamente.
 * Requiere que el cuestionario cualitativo esté completo.
 *
 * @param {string} resultId
 * @param {string} nombreSujeto — para el nombre sugerido del archivo
 */
export function downloadBoletinPdf(resultId, nombreSujeto = 'boletin') {
  const url      = ENDPOINTS.getBoletinPdf(resultId);
  const filename = `boletin_${nombreSujeto.replace(/\s+/g, '_')}.pdf`;
  const a        = document.createElement('a');
  a.href         = url;
  a.download     = filename;
  a.target       = '_blank';
  a.rel          = 'noopener noreferrer';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}