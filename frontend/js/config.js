/* ============================================================
   KUMON · CONFIGURACIÓN GLOBAL
   Archivo: frontend/js/config.js
   Rol: Única fuente de verdad para URLs del backend,
        intervalos de polling, constantes de dominio y
        mensajes de estado. Ningún otro archivo hardcodea
        una URL o constante — solo importa desde aquí.
   ============================================================ */

/* ══════════════════════════════════════════════
   BASE URL DEL BACKEND
   Cambia solo aquí para apuntar a producción,
   staging o local sin tocar ningún otro archivo.
   ══════════════════════════════════════════════ */
export const API_BASE = 'http://localhost:8000';


/* ══════════════════════════════════════════════
   ENDPOINTS — mapeados 1:1 con el backend
   Cada función recibe los parámetros necesarios
   y retorna la URL completa lista para fetch().
   ══════════════════════════════════════════════ */
export const ENDPOINTS = {

  /* ── UPLOAD ── */
  uploadVideo: ()                  => `${API_BASE}/api/v1/upload/video`,

  /* ── JOBS ── */
  getJob:      (jobId)             => `${API_BASE}/api/v1/jobs/${jobId}`,

  /* ── RESULTS ── */
  getResult:   (jobId)             => `${API_BASE}/api/v1/results/job/${jobId}`,

  /* ── CUESTIONARIO ── */
  getCuestionario:    (resultId)   => `${API_BASE}/api/v1/cuestionario/${resultId}`,
  submitCuestionario: (resultId)   => `${API_BASE}/api/v1/cuestionario/${resultId}`,

  /* ── BOLETÍN ── */
  getBoletin:   (resultId)         => `${API_BASE}/api/v1/boletin/${resultId}`,
  getBoletinPdf:(resultId)         => `${API_BASE}/api/v1/boletin/${resultId}/pdf`,
  patchBoletin: (resultId)         => `${API_BASE}/api/v1/boletin/${resultId}`,

  /* ── HEALTH ── */
  health: ()                       => `${API_BASE}/api/v1/health`,
};


/* ══════════════════════════════════════════════
   POLLING
   ══════════════════════════════════════════════ */

/** Intervalo entre llamadas a GET /jobs/{id} (ms) */
export const POLL_INTERVAL_MS = 4000;

/** Tiempo máximo de polling antes de asumir timeout (ms) */
export const POLL_TIMEOUT_MS  = 600_000; // 10 minutos


/* ══════════════════════════════════════════════
   ESTADOS DEL JOB
   Deben coincidir exactamente con los valores
   que retorna el backend en job.status
   ══════════════════════════════════════════════ */
export const JOB_STATUS = {
  PENDING:    'pending',
  QUEUED:     'queued',
  PROCESSING: 'processing',
  DONE:       'done',
  ERROR:      'error',
};

/** Estados que indican que el job terminó (éxito o error) */
export const JOB_TERMINAL_STATES = new Set([
  JOB_STATUS.DONE,
  JOB_STATUS.ERROR,
]);

/** Estados que indican que el job sigue activo */
export const JOB_ACTIVE_STATES = new Set([
  JOB_STATUS.PENDING,
  JOB_STATUS.QUEUED,
  JOB_STATUS.PROCESSING,
]);


/* ══════════════════════════════════════════════
   ESTADOS DEL BOLETÍN
   Deben coincidir con Bulletin.status del backend
   ══════════════════════════════════════════════ */
export const BOLETIN_STATUS = {
  PENDING:    'pending',
  GENERATED:  'generated',
  CORREGIDO:  'corregido_por_orientador',
};


/* ══════════════════════════════════════════════
   SEMÁFORO
   Valores que retorna TestResult.semaforo
   ══════════════════════════════════════════════ */
export const SEMAFORO = {
  VERDE:    'verde',
  AMARILLO: 'amarillo',
  ROJO:     'rojo',
};

export const SEMAFORO_EMOJI = {
  [SEMAFORO.VERDE]:    '🟢',
  [SEMAFORO.AMARILLO]: '🟡',
  [SEMAFORO.ROJO]:     '🔴',
};

export const SEMAFORO_LABEL = {
  [SEMAFORO.VERDE]:    'Aprobado',
  [SEMAFORO.AMARILLO]: 'En proceso',
  [SEMAFORO.ROJO]:     'Necesita refuerzo',
};


/* ══════════════════════════════════════════════
   TIPOS DE PREGUNTA DEL CUESTIONARIO
   Deben coincidir con question.type del backend
   ══════════════════════════════════════════════ */
export const QUESTION_TYPE = {
  RADIO:    'radio',
  SELECT:   'select',
  TEXTAREA: 'textarea',
  NUMBER:   'number',
  CHECKBOX: 'checkbox',
};


/* ══════════════════════════════════════════════
   UMBRALES DE CONFIANZA OCR
   Usados para colorear el dot de confidence_score
   ══════════════════════════════════════════════ */
export const CONFIDENCE = {
  HIGH:   0.85,   // >= 0.85 → verde
  MEDIUM: 0.65,   // >= 0.65 → amarillo
                  //  < 0.65 → rojo, needs_manual_review esperado
};


/* ══════════════════════════════════════════════
   UPLOAD
   ══════════════════════════════════════════════ */

/** Tamaño máximo de archivo permitido (bytes) — 500 MB */
export const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024;

/** Extensiones de video aceptadas */
export const ACCEPTED_VIDEO_TYPES = [
  'video/mp4',
  'video/quicktime',
  'video/x-msvideo',
  'video/webm',
];

/** Extensiones legibles para el hint del drop-zone */
export const ACCEPTED_VIDEO_LABEL = 'MP4, MOV, AVI, WEBM';


/* ══════════════════════════════════════════════
   PIPELINE — pasos visuales
   Orden y labels de los pasos del proceso.
   id debe coincidir con los estados del job.
   ══════════════════════════════════════════════ */
export const PIPELINE_STEPS = [
  { id: 'upload',     label: 'Subida',       icon: '📤' },
  { id: 'processing', label: 'Procesando',   icon: '⚙️'  },
  { id: 'done',       label: 'Resultado',    icon: '📊' },
  { id: 'validated',  label: 'Validación',   icon: '✅' },
  { id: 'boletin',    label: 'Boletín',      icon: '📋' },
];


/* ══════════════════════════════════════════════
   MENSAJES DE UI
   Textos centralizados para no repetirlos
   en múltiples archivos JS.
   ══════════════════════════════════════════════ */
export const MSG = {
  // Upload
  UPLOAD_REQUIRED:       'Selecciona un archivo de video antes de continuar.',
  UPLOAD_SIZE_EXCEEDED:  `El archivo supera el límite de 500 MB.`,
  UPLOAD_TYPE_INVALID:   `Formato no soportado. Usa ${ACCEPTED_VIDEO_LABEL}.`,
  UPLOAD_LOADING:        'Subiendo video al servidor...',
  UPLOAD_SUCCESS:        'Video subido correctamente. Procesando...',
  UPLOAD_ERROR:          'Error al subir el video. Intenta de nuevo.',

  // Polling
  POLLING_TIMEOUT:       'El procesamiento tardó demasiado. Verifica el servidor.',
  POLLING_ERROR:         'Error consultando el estado del job.',

  // Resultado
  RESULT_LOADING:        'Cargando resultado del análisis...',
  RESULT_ERROR:          'No fue posible cargar el resultado.',

  // Cuestionario
  CUESTIONARIO_LOADING:  'Cargando formulario de validación...',
  CUESTIONARIO_EMPTY:    'Completa al menos una respuesta antes de continuar.',
  CUESTIONARIO_SUCCESS:  'Boletín generado correctamente.',
  CUESTIONARIO_ERROR:    'No fue posible guardar la validación.',

  // Boletín
  BOLETIN_LOADING:       'Generando boletín...',
  BOLETIN_NOT_READY:     'El boletín aún no está disponible.',
  BOLETIN_ERROR:         'Error al cargar el boletín.',
  BOLETIN_PDF_ERROR:     'Error al descargar el PDF.',
  BOLETIN_PATCH_SUCCESS: 'Correcciones guardadas correctamente.',
  BOLETIN_PATCH_ERROR:   'Error al guardar las correcciones.',

  // Backend
  BACKEND_OK:            'Servidor conectado',
  BACKEND_ERROR:         'Servidor no disponible',
  BACKEND_CHECKING:      'Verificando conexión...',
};