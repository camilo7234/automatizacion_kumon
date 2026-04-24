/* ============================================================
   KUMON · FORMATEADORES
   Archivo: frontend/js/formatters.js
   Depende de: config.js
   Rol: Funciones PURAS de transformación de datos.
        No tocan el DOM, no tienen efectos secundarios.
        Reciben un valor primitivo y retornan un string
        o clase CSS lista para usar en los renderers.
   ============================================================ */

import {
  JOB_STATUS,
  BOLETIN_STATUS,
  SEMAFORO,
  SEMAFORO_EMOJI,
  SEMAFORO_LABEL,
  CONFIDENCE,
} from './config.js';


/* ══════════════════════════════════════════════
   NÚMEROS
   ══════════════════════════════════════════════ */

/**
 * Formatea un número como porcentaje.
 * formatPercent(87.4)   → "87.4%"
 * formatPercent(87.456) → "87.5%"
 * formatPercent(null)   → "—"
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return `${Number(value).toFixed(decimals)}%`;
}

/**
 * Formatea un número decimal con precisión configurable.
 * formatDecimal(3.14159, 2) → "3.14"
 * formatDecimal(null)       → "—"
 */
export function formatDecimal(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return Number(value).toFixed(decimals);
}

/**
 * Formatea un entero con separadores de miles.
 * formatInt(12345) → "12,345"
 */
export function formatInt(value) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return Number(value).toLocaleString('es-CO');
}

/**
 * Formatea minutos como "Xm" o "Xh Ym".
 * formatMinutes(90) → "1h 30m"
 * formatMinutes(45) → "45m"
 * formatMinutes(0)  → "0m"
 */
export function formatMinutes(minutes) {
  if (minutes === null || minutes === undefined || isNaN(minutes)) return '—';
  const m = Math.round(Number(minutes));
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem === 0 ? `${h}h` : `${h}h ${rem}m`;
}

/**
 * Fracción de aciertos: "correct / total"
 * formatFraction(18, 20) → "18 / 20"
 */
export function formatFraction(correct, total) {
  const c = correct ?? '—';
  const t = total   ?? '—';
  return `${c} / ${t}`;
}


/* ══════════════════════════════════════════════
   FECHAS
   ══════════════════════════════════════════════ */

/**
 * Formatea un ISO string como fecha legible.
 * formatDate("2026-04-24T17:30:00Z") → "24 abr 2026, 12:30"
 * formatDate(null) → "—"
 */
export function formatDate(isoString) {
  if (!isoString) return '—';
  try {
    return new Intl.DateTimeFormat('es-CO', {
      day:    '2-digit',
      month:  'short',
      year:   'numeric',
      hour:   '2-digit',
      minute: '2-digit',
    }).format(new Date(isoString));
  } catch {
    return isoString;
  }
}

/**
 * Solo la hora.
 * formatTime("2026-04-24T17:30:00Z") → "12:30"
 */
export function formatTime(isoString) {
  if (!isoString) return '—';
  try {
    return new Intl.DateTimeFormat('es-CO', {
      hour:   '2-digit',
      minute: '2-digit',
    }).format(new Date(isoString));
  } catch {
    return '—';
  }
}


/* ══════════════════════════════════════════════
   TEXTO
   ══════════════════════════════════════════════ */

/**
 * Primera letra en mayúscula.
 * titleCase("procesando") → "Procesando"
 */
export function titleCase(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

/**
 * Snake_case a palabras.
 * snakeToWords("needs_manual_review") → "Needs Manual Review"
 */
export function snakeToWords(str) {
  if (!str) return '';
  return str
    .split('_')
    .map(w => titleCase(w))
    .join(' ');
}


/* ══════════════════════════════════════════════
   STATUS DEL JOB
   Mapea job.status del backend → label legible
   ══════════════════════════════════════════════ */
const JOB_STATUS_LABEL = {
  [JOB_STATUS.PENDING]:    'En espera',
  [JOB_STATUS.QUEUED]:     'En cola',
  [JOB_STATUS.PROCESSING]: 'Procesando',
  [JOB_STATUS.DONE]:       'Completado',
  [JOB_STATUS.ERROR]:      'Error',
};

/**
 * prettyStatus("processing") → "Procesando"
 */
export function prettyStatus(status) {
  return JOB_STATUS_LABEL[status] ?? titleCase(status ?? '—');
}

/**
 * Clase CSS del tag según el status del job.
 * tagTypeForStatus("done") → "success"
 */
export function tagTypeForStatus(status) {
  const map = {
    [JOB_STATUS.PENDING]:    'default',
    [JOB_STATUS.QUEUED]:     'warning',
    [JOB_STATUS.PROCESSING]: 'info',
    [JOB_STATUS.DONE]:       'success',
    [JOB_STATUS.ERROR]:      'danger',
  };
  return map[status] ?? 'default';
}

/**
 * Label del progreso según el status.
 * prettyProgressLabel("processing", 65) → "Procesando — 65%"
 */
export function prettyProgressLabel(status, pct) {
  const label = prettyStatus(status);
  if (pct !== null && pct !== undefined && !isNaN(pct)) {
    return `${label} — ${Math.round(pct)}%`;
  }
  return label;
}


/* ══════════════════════════════════════════════
   SEMÁFORO
   ══════════════════════════════════════════════ */

/**
 * Emoji del semáforo.
 * semaforoEmoji("verde") → "🟢"
 */
export function semaforoEmoji(value) {
  return SEMAFORO_EMOJI[value] ?? '⚪';
}

/**
 * Label legible del semáforo.
 * semaforoLabelText("rojo") → "Necesita refuerzo"
 */
export function semaforoLabelText(value) {
  return SEMAFORO_LABEL[value] ?? '—';
}

/**
 * Clase CSS del bloque semáforo.
 * toneForSemaforo("amarillo") → "amarillo"
 * (coincide con las clases CSS .semaforo-block.verde/amarillo/rojo)
 */
export function toneForSemaforo(value) {
  const valid = [SEMAFORO.VERDE, SEMAFORO.AMARILLO, SEMAFORO.ROJO];
  return valid.includes(value) ? value : 'default';
}


/* ══════════════════════════════════════════════
   CONFIANZA OCR (confidence_score)
   ══════════════════════════════════════════════ */

/**
 * Clase CSS del dot de confianza.
 * confidenceDotClass(0.90) → ""        (verde — default)
 * confidenceDotClass(0.70) → "warn"    (amarillo)
 * confidenceDotClass(0.50) → "alert"   (rojo)
 */
export function confidenceDotClass(score) {
  if (score === null || score === undefined) return 'warn';
  if (score >= CONFIDENCE.HIGH)   return '';       // verde (sin modificador)
  if (score >= CONFIDENCE.MEDIUM) return 'warn';
  return 'alert';
}

/**
 * Label de confianza legible.
 * confidenceLabel(0.92) → "92% confianza"
 * confidenceLabel(null) → "Sin datos"
 */
export function confidenceLabel(score) {
  if (score === null || score === undefined) return 'Sin datos';
  return `${Math.round(score * 100)}% confianza`;
}


/* ══════════════════════════════════════════════
   BOLETÍN STATUS
   ══════════════════════════════════════════════ */

/**
 * Clase CSS de la barra de estado del boletín.
 * boletinStatusClass("generated") → "generated"
 */
export function boletinStatusClass(status) {
  const map = {
    [BOLETIN_STATUS.GENERATED]: 'generated',
    [BOLETIN_STATUS.PENDING]:   'pending',
    [BOLETIN_STATUS.CORREGIDO]: 'corregido',
  };
  return map[status] ?? 'pending';
}

/**
 * Label del estado del boletín.
 * boletinStatusLabel("generated") → "Boletín generado"
 */
export function boletinStatusLabel(status) {
  const map = {
    [BOLETIN_STATUS.GENERATED]: 'Boletín generado',
    [BOLETIN_STATUS.PENDING]:   'Pendiente de generación',
    [BOLETIN_STATUS.CORREGIDO]: 'Revisado por orientador',
  };
  return map[status] ?? titleCase(status ?? '—');
}


/* ══════════════════════════════════════════════
   ETIQUETA CUALITATIVA
   Mapea etiqueta_cualitativa del backend
   a un label legible para el visor del boletín
   ══════════════════════════════════════════════ */
const ETIQUETA_MAP = {
  fortaleza:   { label: 'Fortaleza',         type: 'success' },
  proceso:     { label: 'En proceso',         type: 'warning' },
  atencion:    { label: 'Requiere atención',  type: 'danger'  },
  desarrollo:  { label: 'En desarrollo',      type: 'info'    },
  logrado:     { label: 'Logrado',            type: 'success' },
};

/**
 * Retorna { label, type } para una etiqueta cualitativa.
 * etiquetaInfo("fortaleza") → { label: "Fortaleza", type: "success" }
 */
export function etiquetaInfo(etiqueta) {
  return ETIQUETA_MAP[etiqueta?.toLowerCase()] ?? {
    label: titleCase(etiqueta ?? '—'),
    type:  'default',
  };
}