/* ============================================================
   KUMON · MÓDULO DE UPLOAD
   Archivo: frontend/js/upload.js
   Depende de: config.js · api.js · state.js · ui.js
   Rol: Maneja toda la interacción del área de upload:
        - Drag & drop + click para seleccionar archivo
        - Validación de tipo y tamaño antes de enviar
        - Barra de progreso real via XHR onProgress
        - Entrega job_id al módulo de polling al terminar
        - Callback onUploadDone(jobId) inyectado desde app.js
   ============================================================ */

import {
  MAX_FILE_SIZE_BYTES,
  ACCEPTED_VIDEO_TYPES,
  ACCEPTED_VIDEO_LABEL,
  MSG,
} from './config.js';

import { uploadVideo }                    from './api.js';
import { setUploading, setJobId }         from './state.js';
import {
  el,
  setAlert,
  clearAlert,
  setLoadingUpload,
  setProgress,
  show,
  hide,
}                                         from './ui.js';


/* ══════════════════════════════════════════════
   ESTADO INTERNO DEL MÓDULO
   ══════════════════════════════════════════════ */
let _selectedFile  = null;   // File | null
let _onUploadDone  = null;   // callback(jobId: string) → void


/* ══════════════════════════════════════════════
   INIT
   Llamado desde app.js → init()
   Recibe el callback que dispara el polling
   ══════════════════════════════════════════════ */
export function initUpload(onUploadDone) {
  _onUploadDone = onUploadDone;

  _bindDropZone();
  _bindFileInput();
  _bindForm();
}


/* ══════════════════════════════════════════════
   DROP ZONE — drag & drop
   ══════════════════════════════════════════════ */
function _bindDropZone() {
  const zone = el.uploadDropZone;
  if (!zone) return;

  /* Click abre el file picker */
  zone.addEventListener('click', () => {
    el.uploadInput?.click();
  });

  /* Teclado: Enter / Space también abren el picker */
  zone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      el.uploadInput?.click();
    }
  });

  /* Drag events */
  zone.addEventListener('dragenter',  _onDragEnter);
  zone.addEventListener('dragover',   _onDragOver);
  zone.addEventListener('dragleave',  _onDragLeave);
  zone.addEventListener('drop',       _onDrop);
}

function _onDragEnter(e) {
  e.preventDefault();
  el.uploadDropZone?.classList.add('drag-over');
}

function _onDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
}

function _onDragLeave(e) {
  /* Solo quitar la clase si el cursor salió del zone completo */
  if (!el.uploadDropZone?.contains(e.relatedTarget)) {
    el.uploadDropZone?.classList.remove('drag-over');
  }
}

function _onDrop(e) {
  e.preventDefault();
  el.uploadDropZone?.classList.remove('drag-over');

  const files = e.dataTransfer?.files;
  if (files?.length > 0) {
    _handleFileSelection(files[0]);
  }
}


/* ══════════════════════════════════════════════
   FILE INPUT — input[type=file]
   ══════════════════════════════════════════════ */
function _bindFileInput() {
  el.uploadInput?.addEventListener('change', (e) => {
    const files = e.target?.files;
    if (files?.length > 0) {
      _handleFileSelection(files[0]);
    }
  });
}


/* ══════════════════════════════════════════════
   VALIDACIÓN Y SELECCIÓN DE ARCHIVO
   ══════════════════════════════════════════════ */
function _handleFileSelection(file) {
  clearAlert(el.uploadAlert);

  /* Validar tipo MIME */
  if (!ACCEPTED_VIDEO_TYPES.includes(file.type)) {
    setAlert(
      el.uploadAlert,
      `${MSG.UPLOAD_TYPE_INVALID} Tipos aceptados: ${ACCEPTED_VIDEO_LABEL}.`,
      'danger'
    );
    _clearSelection();
    return;
  }

  /* Validar tamaño */
  if (file.size > MAX_FILE_SIZE_BYTES) {
    setAlert(
      el.uploadAlert,
      MSG.UPLOAD_SIZE_EXCEEDED,
      'danger'
    );
    _clearSelection();
    return;
  }

  /* Archivo válido */
  _selectedFile = file;
  _showFilename(file.name, _formatFileSize(file.size));
}

function _clearSelection() {
  _selectedFile = null;
  if (el.uploadInput) el.uploadInput.value = '';
  if (el.uploadDropFilename) el.uploadDropFilename.textContent = '';
}

function _showFilename(name, size) {
  if (el.uploadDropFilename) {
    el.uploadDropFilename.textContent = `${name}  (${size})`;
  }
}

function _formatFileSize(bytes) {
  if (bytes < 1024)        return `${bytes} B`;
  if (bytes < 1024 ** 2)   return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3)   return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}


/* ══════════════════════════════════════════════
   FORMULARIO — submit
   ══════════════════════════════════════════════ */
function _bindForm() {
  el.uploadForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    await _handleSubmit();
  });
}

async function _handleSubmit() {
  clearAlert(el.uploadAlert);

  /* Validar que haya archivo */
  if (!_selectedFile) {
    setAlert(el.uploadAlert, MSG.UPLOAD_REQUIRED, 'warning');
    return;
  }

  /* Leer metadata del formulario */
  const meta = {
    student_name: el.studentNameInput?.value?.trim() || null,
    level:        el.levelInput?.value?.trim()        || null,
    orientador:   el.orientadorInput?.value?.trim()   || null,
  };

  /* UI: modo loading */
  setUploading(true);
  setLoadingUpload(true);
  setProgress(el.uploadProgressFill, el.uploadProgressPct, 0);
  setAlert(el.uploadAlert, MSG.UPLOAD_LOADING, 'info');

  /* Subir con progreso */
  const { ok, data, error } = await uploadVideo(
    _selectedFile,
    meta,
    (pct) => {
      setProgress(el.uploadProgressFill, el.uploadProgressPct, pct);
    }
  );

  /* UI: salir de loading */
  setUploading(false);
  setLoadingUpload(false);

  if (!ok || !data?.job_id) {
    setAlert(
      el.uploadAlert,
      error ?? MSG.UPLOAD_ERROR,
      'danger'
    );
    return;
  }

  /* Guardar job_id en estado global */
  setJobId(data.job_id);

  /* Confirmar éxito y pasar el control al polling */
  setAlert(el.uploadAlert, MSG.UPLOAD_SUCCESS, 'success');
  _onUploadDone?.(data.job_id);
}


/* ══════════════════════════════════════════════
   RESET PÚBLICO
   Llamado desde app.js → resetAll()
   Limpia el formulario y el estado interno
   ══════════════════════════════════════════════ */
export function resetUpload() {
  _selectedFile = null;

  if (el.uploadInput)        el.uploadInput.value       = '';
  if (el.uploadDropFilename) el.uploadDropFilename.textContent = '';
  if (el.studentNameInput)   el.studentNameInput.value  = '';
  if (el.levelInput)         el.levelInput.value        = '';
  if (el.orientadorInput)    el.orientadorInput.value   = '';

  clearAlert(el.uploadAlert);
  setLoadingUpload(false);
  setProgress(el.uploadProgressFill, el.uploadProgressPct, 0);
  hide(el.uploadProgressWrap);
}