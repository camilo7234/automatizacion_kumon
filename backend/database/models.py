"""
database/models.py
══════════════════════════════════════════════════════════════════════
FUENTE DE VERDAD de todos los modelos ORM del proyecto.

app/models/__init__.py está VACÍO intencionalmente.
Todos los modelos viven aquí.

Bloques:
  0. Imports y configuración base
  1. Schema ADMIN  — tablas del módulo del compañero (solo lectura)
  2. Schema PROCESSING — tablas de nuestro módulo
     2.1  TestTemplate         — plantillas de los 29 tests Kumon
     2.2  Prospecto            — persona no matriculada que hace el test
     2.3  ProcessingJob        — cola de procesamiento de videos
     2.4  TestResult           — resultados cuantitativos (OCR Class Navi)
     2.5  QualitativeResult    — señales automáticas video/audio
     2.6  ObservacionCualitativa — formulario del orientador
     2.7  Bulletin             — boletín PDF final
  3. Schema AUDIT
     3.1  ProcessingError      — errores del pipeline por stage
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════
# BLOQUE 0 — Imports y configuración base
# ══════════════════════════════════════════════════════════════════
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,          # ← reemplaza TIMESTAMPTZ
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    JSONB,
    UUID,
    # INET no se usa en los modelos actuales
)
from sqlalchemy.orm import relationship

from config.database import Base

# Alias para claridad: en PostgreSQL DateTime(timezone=True) = TIMESTAMPTZ
TIMESTAMPTZ = DateTime(timezone=True)

class Role(Base):
    """
    [ADMIN 1/4] Roles del sistema.
    Referenciado por Usuario para control de acceso.
    """

    __tablename__ = "roles"
    __table_args__ = {"schema": "admin"}

    id_rol      = Column(Integer, primary_key=True, autoincrement=True)
    nombre_rol  = Column(String(50), nullable=False, unique=True)
    descripcion = Column(Text)
    permisos    = Column(JSONB,    nullable=False, server_default=text("'{}'::jsonb"))
    activo      = Column(Boolean,  nullable=False, server_default=text("true"))
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at  = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # ── Relaciones ────────────────────────────────────────────────
    usuarios = relationship(
        "Usuario",
        back_populates="rol",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id_rol} nombre='{self.nombre_rol}'>"


class Usuario(Base):
    """
    [ADMIN 2/4] Usuarios del sistema (orientadores, admins).
    Se usa en Bulletin.approved_by para saber quién aprobó el boletín.
    """

    __tablename__ = "usuarios"
    __table_args__ = {"schema": "admin"}

    id_usuario        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_rol            = Column(Integer, ForeignKey("admin.roles.id_rol"), nullable=False)
    primer_nombre     = Column(String(100), nullable=False)
    segundo_nombre    = Column(String(100))
    primer_apellido   = Column(String(100), nullable=False)
    segundo_apellido  = Column(String(100))
    email             = Column(String(255), nullable=False, unique=True)
    password_hash     = Column(String(255), nullable=False)
    activo            = Column(Boolean,  nullable=False, server_default=text("true"))
    email_verificado  = Column(Boolean,  nullable=False, server_default=text("false"))
    ultimo_acceso     = Column(DateTime(timezone=True))
    intentos_fallidos = Column(Integer,  nullable=False, server_default=text("0"))
    bloqueado_hasta   = Column(DateTime(timezone=True))
    created_at        = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at        = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    deleted_at        = Column(DateTime(timezone=True))  # soft delete
    # ── Relaciones ────────────────────────────────────────────────
    rol = relationship("Role", back_populates="usuarios")

    # ── Properties ───────────────────────────────────────────────
    @property
    def nombre_completo(self) -> str:
        partes = [
            self.primer_nombre,
            self.segundo_nombre,
            self.primer_apellido,
            self.segundo_apellido,
        ]
        return " ".join(p for p in partes if p)

    @property
    def is_active(self) -> bool:
        return self.activo and self.deleted_at is None

    def __repr__(self) -> str:
        return f"<Usuario id={self.id_usuario} email='{self.email}'>"


class Student(Base):
    """
    [ADMIN 3/4] Estudiantes matriculados.
    Gestionado 100% por el módulo del compañero.
    Nuestro módulo solo lo referencia en ProcessingJob y TestResult
    para cuando un estudiante ya matriculado realiza un test.
    En la práctica actual, el flujo principal usa Prospecto.
    """

    __tablename__ = "estudiantes"
    __table_args__ = {"schema": "admin"}

    id_estudiante      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_estudiante  = Column(String(20), unique=True)
    primer_nombre      = Column(String(100), nullable=False)
    segundo_nombre     = Column(String(100))
    primer_apellido    = Column(String(100), nullable=False)
    segundo_apellido   = Column(String(100))
    tipo_documento     = Column(String(10),  nullable=False, server_default=text("'TI'"))
    numero_documento   = Column(String(30),  nullable=False)
    fecha_nacimiento   = Column(Date,        nullable=False)
    genero             = Column(String(20))
    direccion          = Column(Text)
    telefono_contacto  = Column(String(20))
    email              = Column(String(255))
    nombre_acudiente   = Column(String(200))
    telefono_acudiente = Column(String(20))
    email_acudiente    = Column(String(255))
    relacion_acudiente = Column(String(50))
    grado_escolar      = Column(String(50))
    institucion_origen = Column(String(200))
    fecha_ingreso      = Column(Date,    nullable=False, server_default=text("CURRENT_DATE"))
    fecha_retiro       = Column(Date)
    estado             = Column(String(20), nullable=False, server_default=text("'activo'"))
    created_at         = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))
    updated_at         = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))
    deleted_at         = Column(TIMESTAMPTZ)  # soft delete

    # ── Relaciones hacia nuestro módulo (back_populates) ──────────
    processing_jobs = relationship(
        "ProcessingJob",
        back_populates="estudiante",
        foreign_keys="[ProcessingJob.id_estudiante]",
        lazy="select",
    )
    test_results = relationship(
        "TestResult",
        back_populates="estudiante",
        foreign_keys="[TestResult.id_estudiante]",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def nombre_completo(self) -> str:
        partes = [
            self.primer_nombre,
            self.segundo_nombre,
            self.primer_apellido,
            self.segundo_apellido,
        ]
        return " ".join(p for p in partes if p)

    @property
    def is_active(self) -> bool:
        return self.estado == "activo" and self.deleted_at is None

    def __repr__(self) -> str:
        return (
            f"<Student id={self.id_estudiante} "
            f"nombre='{self.primer_nombre} {self.primer_apellido}'>"
        )


# ══════════════════════════════════════════════════════════════════
# BLOQUE 2 — Schema PROCESSING
# Estas tablas son responsabilidad exclusiva de nuestro módulo.
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# BLOQUE 2.1 — TestTemplate
# 29 plantillas de tests Kumon (12 MAT, 12 ESP, 5 ING).
# Se cargan con seed_runner.py. No se modifican en runtime.
# ──────────────────────────────────────────────────────────────────


class TestTemplate(Base):
    """
    [PROCESSING 1/7] Plantillas de los 29 tests de diagnóstico Kumon.

    Columnas JSONB clave:
      answer_key      → clave de respuestas (referencia, no para calcular score)
      level_rules     → rangos del semáforo verde/amarillo/rojo y puntos de partida
      extraction_rules → guía para el OCR: key_frames, secciones, buscar_en_video
      metadata_       → versión del seed para upsert idempotente

    NOTA IMPORTANTE:
      La columna en BD se llama "metadata" pero el atributo Python
      se llama "metadata_" porque SQLAlchemy reserva Base.metadata
      como atributo del sistema. Column("metadata", JSONB) mapea
      la columna BD correctamente.
    """

    __tablename__ = "test_templates"
    __table_args__ = (
        UniqueConstraint("code", "subject", name="uq_test_code_subject"),
        {"schema": "processing"},
    )

    id_template      = Column(Integer,    primary_key=True, autoincrement=True)
    code             = Column(String(10), nullable=False)
    subject          = Column(String(20), nullable=False)   # matematicas|ingles|espanol
    display_name     = Column(String(100), nullable=False)
    grade_level      = Column(String(50))
    total_items      = Column(Integer,    nullable=False)
    time_pattern_min = Column(Numeric(5, 2), nullable=False)
    description      = Column(Text)
    answer_key       = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    level_rules      = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    extraction_rules = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # "metadata" → reservado en SQLAlchemy. Columna BD: "metadata", atributo Python: "metadata_"
    metadata_        = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    active           = Column(Boolean, nullable=False, server_default=text("true"))
    created_at       = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))
    updated_at       = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))

    # ── Relaciones ────────────────────────────────────────────────
    processing_jobs = relationship(
        "ProcessingJob",
        back_populates="template",
        lazy="select",
    )
    test_results = relationship(
        "TestResult",
        back_populates="template",
        lazy="select",
    )
    bulletins = relationship(
        "Bulletin",
        back_populates="template",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def seed_version(self) -> Optional[str]:
        """Versión del seed desde metadata_. Controla el upsert idempotente."""
        if self.metadata_:
            return self.metadata_.get("version")
        return None

    @property
    def tiene_audio(self) -> bool:
        """True si el test requiere análisis de audio (ESP e ING)."""
        return self.subject in ("espanol", "ingles")

    def __repr__(self) -> str:
        return f"<TestTemplate code='{self.code}' subject='{self.subject}'>"


# ──────────────────────────────────────────────────────────────────
# BLOQUE 2.2 — Prospecto
# Registro liviano de persona NO matriculada que realiza un test.
# Si se matricula después, el compañero crea su registro en
# admin.estudiantes. Los dos registros NO se vinculan automáticamente.
# ──────────────────────────────────────────────────────────────────


class Prospecto(Base):
    """
    [PROCESSING 2/7] Persona no matriculada que realiza una prueba diagnóstica.

    Diseño deliberadamente liviano: solo los datos necesarios para
    identificar al prospecto en el boletín. No tiene soft delete porque
    si se borra un prospecto, el job asociado queda con id_prospecto=NULL
    (ON DELETE SET NULL en la FK de processing_jobs).
    """

    __tablename__ = "prospectos"
    __table_args__ = {"schema": "processing"}

    id_prospecto     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo  = Column(Text, nullable=False)
    grado_escolar    = Column(Text)
    nombre_escuela   = Column(Text)
    fecha_prueba     = Column(Date)
    nombre_acudiente = Column(Text)
    telefono         = Column(Text)
    created_at       = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))

    # ── Relaciones bidireccionales ────────────────────────────────
    # foreign_keys explícitos porque ProcessingJob tiene DOS FKs
    processing_jobs = relationship(
        "ProcessingJob",
        back_populates="prospecto",
        foreign_keys="[ProcessingJob.id_prospecto]",
        lazy="select",
    )
    test_results = relationship(
        "TestResult",
        back_populates="prospecto",
        foreign_keys="[TestResult.id_prospecto]",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def first_name(self) -> str:
        """Primera palabra del nombre_completo. Útil para saludos en el boletín."""
        return self.nombre_completo.split()[0] if self.nombre_completo else ""

    @property
    def tiene_acudiente(self) -> bool:
        return bool(self.nombre_acudiente)

    def __repr__(self) -> str:
        return f"<Prospecto id={self.id_prospecto} nombre='{self.nombre_completo}'>"


# ──────────────────────────────────────────────────────────────────
# BLOQUE 2.3 — ProcessingJob
# Cola de procesamiento. Una fila por video subido.
#
# CONSTRAINT XOR (chk_xor_sujeto):
#   Siempre exactamente UNO de id_estudiante o id_prospecto está lleno.
#   Nunca ambos. Nunca ninguno.
#
# RELACIONES CON foreign_keys EXPLÍCITOS:
#   ProcessingJob tiene DOS ForeignKey hacia tablas distintas
#   (admin.estudiantes y processing.prospectos). SQLAlchemy no puede
#   inferir automáticamente cuál FK usar para cada relationship.
#   Por eso se declara foreign_keys=[...] en cada relación.
# ──────────────────────────────────────────────────────────────────


class ProcessingJob(Base):
    """
    [PROCESSING 3/7] Cola de procesamiento de videos.

    Ciclo de vida del status:
      queued → processing → done | error | manual_review

    Ciclo de vida del video:
      file_path apunta al archivo temporal en uploads/videos/
      Después del análisis el video se elimina del disco
      y file_path se pone NULL. Solo persisten los datos extraídos.
    """

    __tablename__ = "processing_jobs"
    __table_args__ = (
        # XOR: exactamente uno de los dos sujetos debe estar presente
        CheckConstraint(
            "(id_estudiante IS NOT NULL AND id_prospecto IS NULL) OR "
            "(id_estudiante IS NULL AND id_prospecto IS NOT NULL)",
            name="chk_xor_sujeto",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="chk_job_completado",
        ),
        {"schema": "processing"},
    )

    id_job             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── XOR sujeto ────────────────────────────────────────────────
    id_estudiante = Column(
        UUID(as_uuid=True),
        ForeignKey("admin.estudiantes.id_estudiante", ondelete="CASCADE"),
        nullable=True,   # NULL cuando el sujeto es un prospecto
    )
    id_prospecto = Column(
        UUID(as_uuid=True),
        ForeignKey("processing.prospectos.id_prospecto", ondelete="SET NULL"),
        nullable=True,   # NULL cuando el sujeto es un estudiante
    )

    # ── Template y archivo ────────────────────────────────────────
    id_template        = Column(
        Integer,
        ForeignKey("processing.test_templates.id_template"),
        nullable=False,
    )
    source_type        = Column(String(10),  nullable=False, server_default=text("'video'"))
    file_path          = Column(Text)          # NULL después de procesar (video eliminado)
    file_name_original = Column(Text)
    file_size_bytes    = Column(BigInteger)
    file_hash          = Column(String(32), nullable=False)   # MD5, detecta duplicados

    # ── Estado del pipeline ───────────────────────────────────────
    status           = Column(String(20), nullable=False, server_default=text("'queued'"))
    progress_percent = Column(Integer,   nullable=False, server_default=text("0"))
    error_message    = Column(Text)
    retry_count      = Column(Integer,   nullable=False, server_default=text("0"))

    # ── Timestamps ────────────────────────────────────────────────
    created_at   = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))
    started_at   = Column(TIMESTAMPTZ)
    completed_at = Column(TIMESTAMPTZ)

    # ── Relaciones ────────────────────────────────────────────────
    # foreign_keys OBLIGATORIO: ProcessingJob tiene dos FKs y SQLAlchemy
    # no puede inferir cuál usar para cada relación sin indicarlo.
    estudiante = relationship(
        "Student",
        back_populates="processing_jobs",
        foreign_keys=[id_estudiante],
        lazy="select",
    )
    prospecto = relationship(
        "Prospecto",
        back_populates="processing_jobs",
        foreign_keys=[id_prospecto],
        lazy="select",
    )
    template = relationship(
        "TestTemplate",
        back_populates="processing_jobs",
        lazy="select",
    )

    # Resultados del pipeline (uselist=False → acceso directo, no lista)
    test_result = relationship(
        "TestResult",
        back_populates="job",
        uselist=False,
        lazy="select",
    )
    qualitative_result = relationship(
        "QualitativeResult",
        back_populates="job",
        uselist=False,
        lazy="select",
    )
    processing_errors = relationship(
        "ProcessingError",
        back_populates="job",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def is_prospecto(self) -> bool:
        """True si el sujeto del job es un prospecto."""
        return self.id_prospecto is not None

    @property
    def is_estudiante(self) -> bool:
        """True si el sujeto del job es un estudiante matriculado."""
        return self.id_estudiante is not None

    @property
    def duration_seconds(self) -> Optional[float]:
        """
        Segundos totales que tardó el pipeline.
        None si el job aún no ha terminado.
        """
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def sujeto_nombre(self) -> str:
        """
        Nombre del sujeto sin importar si es prospecto o estudiante.
        Útil para logs y respuestas de la API.
        """
        if self.prospecto:
            return self.prospecto.nombre_completo
        if self.estudiante:
            return self.estudiante.nombre_completo
        return "Desconocido"

    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @property
    def is_error(self) -> bool:
        return self.status == "error"

    @property
    def needs_review(self) -> bool:
        return self.status == "manual_review"

    def __repr__(self) -> str:
        return (
            f"<ProcessingJob id={self.id_job} "
            f"status='{self.status}' "
            f"sujeto='{'prospecto' if self.is_prospecto else 'estudiante'}'>"
        )


# ──────────────────────────────────────────────────────────────────
# BLOQUE 2.4 — TestResult
# Resultados cuantitativos extraídos por OCR del frame de resumen
# de Class Navi. Class Navi YA calcula el score; el OCR solo lee.
#
# Campos del frame de resumen que OCR extrae:
#   ws              → Work Sheet (número de hoja)
#   study_time_min  → tiempo real que tardó el prospecto
#   target_time_min → TPT (tiempo patrón del nivel)
#   correct_answers → aciertos
#   total_questions → total de preguntas
#   percentage      → porcentaje calculado por Class Navi
#
# Campos que calcula nuestro backend:
#   semaforo        → verde/amarillo/rojo según level_rules del template
#   starting_point  → punto de partida recomendado
#   recommendation  → texto pedagógico generado
# ──────────────────────────────────────────────────────────────────


class TestResult(Base):
    """
    [PROCESSING 4/7] Resultados del test. Un resultado por job.

    Relación con ObservacionCualitativa:
      uselist=False → result.observacion_cualitativa devuelve
      el objeto directamente, no una lista.

    Relación con Bulletin:
      uselist=False → result.bulletin devuelve el objeto directamente.
    """

    __tablename__ = "test_results"
    __table_args__ = {"schema": "processing"}

    id_result     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_job        = Column(
        UUID(as_uuid=True),
        ForeignKey("processing.processing_jobs.id_job", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # Un job → un resultado máximo
    )
    id_prospecto  = Column(
        UUID(as_uuid=True),
        ForeignKey("processing.prospectos.id_prospecto"),
        nullable=True,
    )
    id_estudiante = Column(
        UUID(as_uuid=True),
        ForeignKey("admin.estudiantes.id_estudiante"),
        nullable=True,
    )
    id_template   = Column(
        Integer,
        ForeignKey("processing.test_templates.id_template"),
        nullable=False,
    )
    tipo_sujeto   = Column(String(20), nullable=False)   # prospecto | estudiante

    # ── Datos extraídos por OCR del frame de resumen Class Navi ───
    test_date        = Column(Date)
    ws               = Column(String(20))        # Work Sheet
    study_time_min   = Column(Numeric(6, 2))     # tiempo real empleado
    target_time_min  = Column(Numeric(6, 2))     # TPT del nivel
    correct_answers  = Column(Integer)
    total_questions  = Column(Integer)
    percentage       = Column(Numeric(5, 2))     # porcentaje (0-100)

    # ── Cálculos del backend (result_calculator.py) ───────────────
    current_level  = Column(String(30))          # nivel actual detectado
    starting_point = Column(String(50))          # punto de partida recomendado
    semaforo       = Column(String(10))          # verde | amarillo | rojo
    recommendation = Column(Text)                # texto pedagógico

    # ── Confianza y revisión manual ───────────────────────────────
    confidence_score    = Column(Numeric(4, 3))  # 0.000 - 1.000
    needs_manual_review = Column(
        Boolean, nullable=False, server_default=text("false")
    )   # True si confidence_score < OCR_CONFIDENCE_MIN (0.75)

    # ── Datos crudos para auditoría y debugging ───────────────────
    raw_ocr_data    = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    sections_detail = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))

    # ── Relaciones ────────────────────────────────────────────────
    job = relationship(
        "ProcessingJob",
        back_populates="test_result",
        lazy="select",
    )
    prospecto = relationship(
        "Prospecto",
        back_populates="test_results",
        foreign_keys=[id_prospecto],
        lazy="select",
    )
    estudiante = relationship(
        "Student",
        back_populates="test_results",
        foreign_keys=[id_estudiante],
        lazy="select",
    )
    template = relationship(
        "TestTemplate",
        back_populates="test_results",
        lazy="select",
    )
    # uselist=False: acceso directo result.observacion_cualitativa
    observacion_cualitativa = relationship(
        "ObservacionCualitativa",
        back_populates="result",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )
    # uselist=False: acceso directo result.bulletin
    bulletin = relationship(
        "Bulletin",
        back_populates="result",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def tiene_observacion(self) -> bool:
        """True si ya existe el formulario cualitativo para este resultado."""
        return self.observacion_cualitativa is not None

    @property
    def observacion_completa(self) -> bool:
        """True si el formulario cualitativo fue completado por el orientador."""
        return (
            self.observacion_cualitativa is not None
            and self.observacion_cualitativa.esta_completo
        )

    @property
    def boletin_habilitado(self) -> bool:
        """
        El boletín se puede generar cuando:
          - Hay un resultado cuantitativo (OCR exitoso), Y
          - El formulario cualitativo fue completado.
        """
        return not self.needs_manual_review and self.observacion_completa

    @property
    def tiempo_sobre_patron(self) -> Optional[float]:
        """
        Diferencia entre el tiempo real y el TPT del nivel.
        Negativo = fue más rápido que el patrón (buena señal).
        None si faltan datos.
        """
        if self.study_time_min is not None and self.target_time_min is not None:
            return float(self.study_time_min - self.target_time_min)
        return None

    def __repr__(self) -> str:
        return (
            f"<TestResult id={self.id_result} "
            f"semaforo='{self.semaforo}' "
            f"tipo='{self.tipo_sujeto}'>"
        )


# ──────────────────────────────────────────────────────────────────
# BLOQUE 2.5 — QualitativeResult
# Señales automáticas extraídas del video y audio por el pipeline.
# No es visible para el orientador directamente; sus datos alimentan
# los "prefills" del formulario (ObservacionCualitativa).
#
# auto_captured_flags lista las métricas que el sistema captó con
# suficiente confianza. Esas métricas NO aparecen como preguntas
# en el formulario del orientador. Si el orientador quiere
# corregirlas, puede hacerlo en ObservacionCualitativa.
# ──────────────────────────────────────────────────────────────────


class QualitativeResult(Base):
    """
    [PROCESSING 5/7] Señales automáticas del video y audio.

    Señales de video (todas las materias):
      time_per_section  → segundos por sección del test
      num_rewrites      → veces que se detectó borrado/reescritura
      pause_events      → pausas largas sin actividad en pantalla
      activity_ratio    → ratio tiempo activo / tiempo total (0.0-1.0)
      stroke_detail     → strokes por sección (ritmo de trabajo)

    Señales de audio (solo ESP e ING):
      vad_segments      → segmentos donde se detectó voz
      speech_rate       → palabras por segundo estimadas
      silence_events    → silencios prolongados en el audio

    Señales de cámara frontal (FUTURO):
      gaze_data         → NULL hasta validar hardware Samsung Galaxy S6
                          Se activa con ENABLE_FACE_ANALYSIS=true en .env

    Prefills:
      prefills           → dict con valor y confianza por métrica
      auto_captured_flags → lista de claves capturadas automáticamente
    """

    __tablename__ = "qualitative_results"
    __table_args__ = {"schema": "processing"}

    id_qualitative = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_job         = Column(
        UUID(as_uuid=True),
        ForeignKey("processing.processing_jobs.id_job", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # Un job → un qualitative_result máximo
    )

    # ── Señales de video ──────────────────────────────────────────
    # {"seccion_1": 45.2, "seccion_2": 120.0, ...}
    time_per_section = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Total de eventos de borrado/reescritura detectados
    num_rewrites     = Column(Integer, nullable=False, server_default=text("0"))

    # [{"inicio_ms": 12000, "duracion_ms": 9500, "seccion": "seccion_2"}, ...]
    pause_events     = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # Ratio tiempo activo / total (0.0-1.0). Proxy de concentración/motivación.
    activity_ratio   = Column(Numeric(4, 3))

    # {"seccion_1": {"strokes": 42, "avg_duration_ms": 320}, ...}
    stroke_detail    = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # ── Señales de audio (solo ESP e ING) ─────────────────────────
    # [{"inicio_ms": 5000, "fin_ms": 8200}, ...]
    vad_segments   = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # Palabras por segundo estimadas durante la lectura en voz alta
    speech_rate    = Column(Numeric(5, 2))

    # [{"inicio_ms": 22000, "duracion_ms": 11000}, ...]
    silence_events = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # ── Señales de cámara frontal — FUTURO ────────────────────────
    # NULL hasta confirmar compatibilidad hardware Samsung Galaxy S6.
    # Activar con ENABLE_FACE_ANALYSIS=true en .env.
    # Estructura esperada cuando esté activo:
    # {"pct_mirando_pantalla": 0.82, "head_pose_events": [...]}
    gaze_data = Column(JSONB, nullable=True, server_default=text("NULL"))

    # ── Prefills para el formulario del orientador ────────────────
    # {
    #   "velocidad_respuesta": {"valor": "rapida",  "confianza": 0.91},
    #   "fluidez_lectura":     {"valor": "fluida",  "confianza": 0.85},
    #   "num_reescrituras":    {"valor": 3,          "confianza": 0.99}
    # }
    prefills = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Lista de claves que el sistema captó con confianza suficiente.
    # Estas métricas NO aparecen en el formulario del orientador.
    # Ejemplo: ["velocidad_respuesta", "fluidez_lectura", "num_reescrituras"]
    auto_captured_flags = Column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    # ── Meta ──────────────────────────────────────────────────────
    processing_ms = Column(Integer)   # duración del análisis en milisegundos
    created_at    = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))

    # ── Relaciones ────────────────────────────────────────────────
    job = relationship(
        "ProcessingJob",
        back_populates="qualitative_result",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def tiene_audio(self) -> bool:
        """True si se procesó audio (hay segmentos VAD)."""
        return bool(self.vad_segments)

    @property
    def tiene_gaze(self) -> bool:
        """True si se capturaron datos de cámara frontal (hardware disponible)."""
        return self.gaze_data is not None

    @property
    def total_pausa_ms(self) -> int:
        """Suma total de milisegundos en pausas largas."""
        if not self.pause_events:
            return 0
        return sum(p.get("duracion_ms", 0) for p in self.pause_events)

    def __repr__(self) -> str:
        return (
            f"<QualitativeResult id={self.id_qualitative} "
            f"rewrites={self.num_rewrites} "
            f"flags={self.auto_captured_flags}>"
        )


# ──────────────────────────────────────────────────────────────────
# BLOQUE 2.6 — ObservacionCualitativa
# Formulario cualitativo completado por el orientador.
#
# Contiene DOS tipos de datos en el campo JSONB "respuestas":
#   1. Métricas que el sistema NO pudo capturar automáticamente
#      (las que NO están en auto_captured_flags del QualitativeResult)
#   2. Correcciones del orientador sobre métricas que el OCR sí
#      capturó pero que el orientador considera incorrectas
#
# Estructura de cada entrada en "respuestas":
#   {
#     "clave_metrica": {
#       "valor":     <respuesta>,          ← valor capturado o corregido
#       "fuente":    "ocr"|"orientador",   ← quién proveyó el valor
#       "corregido": true|false            ← true si orientador corrigió OCR
#     }
#   }
# ──────────────────────────────────────────────────────────────────


class ObservacionCualitativa(Base):
    """
    [PROCESSING 6/7] Formulario cualitativo del orientador.

    Relación con TestResult:
      unique=True → un resultado tiene máximo una observación cualitativa.
      uselist=False en TestResult.observacion_cualitativa.
    """

    __tablename__ = "observaciones_cualitativas"
    __table_args__ = {"schema": "processing"}

    id_observacion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_result      = Column(
        UUID(as_uuid=True),
        ForeignKey("processing.test_results.id_result", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # Un resultado → una observación cualitativa máximo
    )
    subject   = Column(String(20), nullable=False)   # matematicas|ingles|espanol
    test_code = Column(String(10), nullable=False)   # K1, P3, M, etc.

    # Ver estructura detallada en el docstring del bloque
    respuestas     = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    completado_por = Column(Text)      # nombre del orientador
    completado_at  = Column(TIMESTAMPTZ)
    created_at     = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))

    # ── Relaciones ────────────────────────────────────────────────
    result = relationship(
        "TestResult",
        back_populates="observacion_cualitativa",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def esta_completo(self) -> bool:
        """
        True si el orientador terminó el formulario.
        Requiere respuestas no vacías Y timestamp de completado.
        """
        return bool(self.respuestas) and self.completado_at is not None

    @property
    def total_respuestas(self) -> int:
        """Cantidad de métricas respondidas en el formulario."""
        return len(self.respuestas) if self.respuestas else 0

    @property
    def correcciones_ocr(self) -> list[str]:
        """
        Lista de claves donde el orientador corrigió un valor del OCR.
        Útil para auditoría y para mejorar el modelo de OCR.
        """
        if not self.respuestas:
            return []
        return [
            clave
            for clave, datos in self.respuestas.items()
            if isinstance(datos, dict) and datos.get("corregido") is True
        ]

    @property
    def pct_corregido(self) -> float:
        """Porcentaje de respuestas que fueron correcciones del OCR."""
        if not self.total_respuestas:
            return 0.0
        return round(len(self.correcciones_ocr) / self.total_respuestas * 100, 1)

    def __repr__(self) -> str:
        return (
            f"<ObservacionCualitativa id={self.id_observacion} "
            f"completo={self.esta_completo} "
            f"subject='{self.subject}' code='{self.test_code}'>"
        )


# ──────────────────────────────────────────────────────────────────
# BLOQUE 2.7 — Bulletin
# Boletín PDF final. Consolida los 3 bloques del informe:
#   - Cuantitativo : datos Class Navi + semáforo + starting_point
#   - Cualitativo  : formulario del orientador + señales automáticas
#   - Combinado    : fórmula 65% cuantitativo + 35% cualitativo
#
# El bloque de cámara frontal (gaze) estará disponible cuando
# se valide el hardware de las tablets.
# ──────────────────────────────────────────────────────────────────


class Bulletin(Base):
    """
    [PROCESSING 7/7] Boletín PDF del diagnóstico.

    Ciclo de vida del status:
      pending → generating → ready → delivered | error

    datos_boletin estructura:
    {
      "cuantitativo": { score, ws, study_time, target_time, semaforo, starting_point },
      "cualitativo":  { secciones: [...], puntaje_total, etiqueta },
      "combinado":    { puntaje, etiqueta, breakdown },
      "gaze":         null   ← futuro (cámara frontal)
    }

    Fórmula puntaje_combinado:
      0.65 × puntaje_cuantitativo + 0.35 × puntaje_cualitativo

    Escala etiqueta_combinada:
      76-100 → fortaleza
      51-75  → en_desarrollo
      26-50  → refuerzo
       0-25  → atencion
    """

    __tablename__ = "bulletins"
    __table_args__ = {"schema": "processing"}

    id_bulletin  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_result    = Column(
        UUID(as_uuid=True),
        ForeignKey("processing.test_results.id_result", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # Un resultado → un boletín máximo
    )
    id_template  = Column(
        Integer,
        ForeignKey("processing.test_templates.id_template"),
        nullable=False,
    )

    # ── Estado ────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, server_default=text("'pending'"))

    # ── Datos consolidados para renderizar el PDF ─────────────────
    datos_boletin = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # ── Puntajes calculados ───────────────────────────────────────
    puntaje_cuantitativo = Column(Numeric(5, 2))   # score Class Navi normalizado 0-100
    puntaje_cualitativo  = Column(Numeric(5, 2))   # score formulario 0-100
    puntaje_combinado    = Column(Numeric(5, 2))   # 0.65 × cuant + 0.35 × cual
    etiqueta_combinada   = Column(String(20))      # fortaleza|en_desarrollo|refuerzo|atencion

    # ── PDF generado ──────────────────────────────────────────────
    pdf_path       = Column(Text)
    pdf_size_bytes = Column(BigInteger)

    # ── Aprobación y entrega ──────────────────────────────────────
    approved_by  = Column(UUID(as_uuid=True), ForeignKey("admin.usuarios.id_usuario"))
    approved_at  = Column(TIMESTAMPTZ)
    delivered_at = Column(TIMESTAMPTZ)
    generated_at = Column(TIMESTAMPTZ)
    created_at   = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))

    # ── Relaciones ────────────────────────────────────────────────
    result = relationship(
        "TestResult",
        back_populates="bulletin",
        lazy="select",
    )
    template = relationship(
        "TestTemplate",
        back_populates="bulletins",
        lazy="select",
    )

    # ── Properties ───────────────────────────────────────────────
    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    @property
    def is_delivered(self) -> bool:
        return self.status == "delivered"

    @property
    def tiene_pdf(self) -> bool:
        return self.pdf_path is not None

    @property
    def puntaje_combinado_calculado(self) -> Optional[float]:
        """
        Calcula 0.65 × cuantitativo + 0.35 × cualitativo.
        None si faltan datos. Útil para verificar coherencia.
        """
        if self.puntaje_cuantitativo is not None and self.puntaje_cualitativo is not None:
            return round(
                float(self.puntaje_cuantitativo) * 0.65
                + float(self.puntaje_cualitativo) * 0.35,
                2,
            )
        return None

    def __repr__(self) -> str:
        return (
            f"<Bulletin id={self.id_bulletin} "
            f"status='{self.status}' "
            f"etiqueta='{self.etiqueta_combinada}'>"
        )


# ══════════════════════════════════════════════════════════════════
# BLOQUE 3 — Schema AUDIT
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# BLOQUE 3.1 — ProcessingError
# Errores del pipeline clasificados por stage.
# Se registra automáticamente en processing_service.py
# cuando falla cualquier etapa del pipeline.
# ──────────────────────────────────────────────────────────────────


class ProcessingError(Base):
    """
    [AUDIT 1/1] Errores del pipeline de procesamiento.

    stages posibles:
      ocr         → falló la extracción OCR del frame de resumen
      audio       → falló el análisis de audio (VAD, speech rate)
      qualitative → falló el qualitative_analyzer
      calculator  → falló el result_calculator (semáforo, starting_point)
      bulletin    → falló la generación del boletín PDF
      general     → error no clasificado
    """

    __tablename__ = "processing_errors"
    __table_args__ = {"schema": "audit"}

    id_error     = Column(BigInteger, primary_key=True, autoincrement=True)
    id_job       = Column(
        UUID(as_uuid=True),
        ForeignKey("processing.processing_jobs.id_job"),
        nullable=True,   # Puede ser NULL si el error ocurre antes de crear el job
    )
    stage        = Column(String(50),  nullable=False)
    error_type   = Column(String(100))
    error_detail = Column(Text)
    stack_trace  = Column(Text)
    created_at   = Column(TIMESTAMPTZ, nullable=False, server_default=text("NOW()"))

    # ── Relaciones ────────────────────────────────────────────────
    job = relationship(
        "ProcessingJob",
        back_populates="processing_errors",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<ProcessingError id={self.id_error} "
            f"stage='{self.stage}' "
            f"type='{self.error_type}'>"
        )
