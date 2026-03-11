# ============================================================
# BLOQUE 1 — Imports y configuración base
# ============================================================
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float,
    ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, CheckConstraint, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from config.database import Base


# ============================================================
# BLOQUE 2 — Función helper para generar UUIDs
# ============================================================
def generate_uuid():
    """Genera un UUID string para valores por defecto."""
    return str(uuid.uuid4())


# ============================================================
# BLOQUE 3 — Clase Student (tabla admin.estudiantes)
# Solo lectura desde este módulo
# ============================================================
class Student(Base):
    """
    Referencia a admin.estudiantes.
    Este módulo NUNCA hace INSERT ni UPDATE en esta tabla.
    Solo consulta para asociar resultados al estudiante correcto.
    """
    __tablename__  = "estudiantes"
    __table_args__ = {"schema": "admin"}

    id_estudiante     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_estudiante = Column(String(20),  unique=True)
    primer_nombre     = Column(String(100), nullable=False)
    segundo_nombre    = Column(String(100))
    primer_apellido   = Column(String(100), nullable=False)
    segundo_apellido  = Column(String(100))
    estado            = Column(String(20),  nullable=False, default="activo")
    deleted_at        = Column(DateTime(timezone=True))
    created_at        = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at        = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones hacia las tablas que SÍ son de este módulo
    processing_jobs = relationship("ProcessingJob", back_populates="student",
                                   foreign_keys="ProcessingJob.id_estudiante")
    test_results    = relationship("TestResult",    back_populates="student")
    bulletins       = relationship("Bulletin",      back_populates="student")

    @property
    def full_name(self) -> str:
        """Retorna nombre completo formateado."""
        parts = [self.primer_nombre, self.segundo_nombre,
                 self.primer_apellido, self.segundo_apellido]
        return " ".join(p for p in parts if p)

    def __repr__(self):
        return f"<Student(id={self.id_estudiante}, name={self.full_name})>"


# ============================================================
# BLOQUE 4 — Clase TestTemplate (tabla processing.test_templates)
# Define estructura y criterios de cada test por materia/nivel
# ============================================================
class TestTemplate(Base):
    """
    processing.test_templates
    Plantilla de cada test Kumon por nivel y materia.
    29 registros: 12 Matemáticas + 12 Español + 5 Inglés.
    Define estructura, tiempo objetivo y criterios del semáforo.
    """
    __tablename__  = "test_templates"
    __table_args__ = (
        UniqueConstraint("code", "subject", name="uq_test_code_subject"),
        {"schema": "processing"}
    )

    id_template      = Column(Integer,      primary_key=True, autoincrement=True)
    code             = Column(String(10),   nullable=False, index=True)
    subject          = Column(String(20),   nullable=False)
    display_name     = Column(String(100),  nullable=False)
    grade_level      = Column(String(50))
    total_items      = Column(Integer,      nullable=False)
    time_pattern_min = Column(Numeric(5,2), nullable=False)
    description      = Column(Text)
    answer_key       = Column(JSONB,        nullable=False, default=dict)
    level_rules      = Column(JSONB,        nullable=False, default=dict)
    extraction_rules = Column(JSONB,        nullable=False, default=dict)
    metadata_        = Column("metadata", JSONB, nullable=False, default=dict)
    active           = Column(Boolean,      nullable=False, default=True)
    created_at       = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at       = Column(DateTime(timezone=True), default=datetime.utcnow,
                              onupdate=datetime.utcnow)

    # Relaciones
    processing_jobs = relationship("ProcessingJob", back_populates="template")
    test_results    = relationship("TestResult",    back_populates="template")
    bulletins       = relationship("Bulletin",      back_populates="template")

    def __repr__(self):
        return f"<TestTemplate(code={self.code}, subject={self.subject})>"


# ============================================================
# BLOQUE 5 — Clase ProcessingJob (tabla processing.processing_jobs)
# Cola de procesamiento — MODIFICADA para soportar prospectos
# id_estudiante e id_prospecto son mutuamente excluyentes
# ============================================================
class ProcessingJob(Base):
    """
    processing.processing_jobs
    Cola de procesamiento. Cada video o PDF subido genera un job.
    Estados: queued -> processing -> done | error | manual_review
    CAMBIO: Ahora soporta dos orígenes:
    - id_estudiante (NULL) para estudiante matriculado
    - id_prospecto (NULL) para diagnóstico sin matrícula
    Nunca los dos llenos simultáneamente — garantizado por constraint en BD.
    """
    __tablename__  = "processing_jobs"
    __table_args__ = {"schema": "processing"}

    id_job             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # CAMBIO: nullable=True — puede ser estudiante O prospecto
    id_estudiante      = Column(UUID(as_uuid=True),
                                ForeignKey("admin.estudiantes.id_estudiante"),
                                nullable=True, index=True)
    # NUEVO: id_prospecto para diagnósticos sin matrícula
    id_prospecto       = Column(UUID(as_uuid=True),
                                ForeignKey("processing.prospectos.id_prospecto"),
                                nullable=True, index=True)
    id_template        = Column(Integer,
                                ForeignKey("processing.test_templates.id_template"),
                                nullable=False, index=True)
    source_type        = Column(String(10),  nullable=False)
    file_path          = Column(Text,        nullable=False)
    file_name_original = Column(Text)
    file_size_bytes    = Column(BigInteger)
    file_hash          = Column(String(32),  nullable=False, index=True)
    status             = Column(String(20),  nullable=False, default="queued")
    error_message      = Column(Text)
    progress_percent   = Column(Integer,     nullable=False, default=0)
    retry_count        = Column(Integer,     nullable=False, default=0)
    max_retries        = Column(Integer,     nullable=False, default=3)
    created_at         = Column(DateTime(timezone=True), default=datetime.utcnow)
    started_at         = Column(DateTime(timezone=True))
    completed_at       = Column(DateTime(timezone=True))
    created_by         = Column(UUID(as_uuid=True))

    # Relaciones — especificar foreign_keys explícitamente por ambigüedad
    student   = relationship("Student",      back_populates="processing_jobs",
                             foreign_keys=[id_estudiante])
    prospecto = relationship("Prospecto",    back_populates="processing_jobs",
                             foreign_keys=[id_prospecto])
    template  = relationship("TestTemplate", back_populates="processing_jobs")
    result    = relationship("TestResult",   back_populates="job", uselist=False)
    errors    = relationship("ProcessingError", back_populates="job")

    @property
    def is_done(self) -> bool:
        """True si el procesamiento terminó exitosamente."""
        return self.status == "done"

    @property
    def is_failed(self) -> bool:
        """True si el procesamiento falló."""
        return self.status == "error"

    @property
    def is_prospecto(self) -> bool:
        """True si el job es de un prospecto (sin matrícula)."""
        return self.id_prospecto is not None

    @property
    def is_estudiante(self) -> bool:
        """True si el job es de un estudiante matriculado."""
        return self.id_estudiante is not None

    @property
    def duration_seconds(self):
        """Retorna la duración del procesamiento en segundos."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def __repr__(self):
        if self.is_prospecto:
            origen = f"prospecto={self.id_prospecto}"
        else:
            origen = f"estudiante={self.id_estudiante}"
        return f"<ProcessingJob(id={self.id_job}, status={self.status}, {origen})>"


# ============================================================
# BLOQUE 6 — Clase TestResult (tabla processing.test_results)
# MODIFICADA: agrega relación con observación_cualitativa
# ============================================================
class TestResult(Base):
    """
    processing.test_results
    Resultado final del OCR por cada job exitoso.
    Un job produce exactamente un resultado (UNIQUE id_job).
    Semáforo: verde=sube nivel, amarillo=repite, rojo=refuerza.
    CAMBIO: Agrega relación con observaciones_cualitativas.
    """
    __tablename__  = "test_results"
    __table_args__ = {"schema": "processing"}

    id_result           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_job              = Column(UUID(as_uuid=True),
                                 ForeignKey("processing.processing_jobs.id_job"),
                                 nullable=False, unique=True)
    id_estudiante       = Column(UUID(as_uuid=True),
                                 ForeignKey("admin.estudiantes.id_estudiante"),
                                 nullable=False, index=True)
    id_template         = Column(Integer,
                                 ForeignKey("processing.test_templates.id_template"),
                                 nullable=False)
    test_date           = Column(Date,         nullable=False)
    time_used_min       = Column(Numeric(6,2), nullable=False)
    correct_answers     = Column(Integer,      nullable=False)
    total_questions     = Column(Integer,      nullable=False)
    percentage          = Column(Numeric(5,2), nullable=False)
    current_level       = Column(String(30),   nullable=False)
    starting_point      = Column(String(50),   nullable=False)
    semaforo            = Column(String(10),   nullable=False)
    recommendation      = Column(Text,         nullable=False)
    sections_detail     = Column(JSONB,        nullable=False, default=dict)
    confidence_score    = Column(Numeric(4,3))
    raw_ocr_data        = Column(JSONB)
    needs_manual_review = Column(Boolean,      nullable=False, default=False)
    reviewed_by         = Column(UUID(as_uuid=True))
    reviewed_at         = Column(DateTime(timezone=True))
    created_at          = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    job                     = relationship("ProcessingJob", back_populates="result")
    student                 = relationship("Student",       back_populates="test_results")
    template                = relationship("TestTemplate",  back_populates="test_results")
    bulletin                = relationship("Bulletin",      back_populates="result", uselist=False)
    # NUEVA: conexión con observación cualitativa
    observacion_cualitativa = relationship("ObservacionCualitativa",
                                           back_populates="result", uselist=False)

    @property
    def passed(self) -> bool:
        """True si el semáforo es verde (aprobó)."""
        return self.semaforo == "verde"

    @property
    def needs_review(self) -> bool:
        """True si el semáforo es rojo (necesita refuerzo)."""
        return self.semaforo == "rojo"

    def __repr__(self):
        return (f"<TestResult(student={self.id_estudiante}, "
                f"level={self.current_level}, semaforo={self.semaforo})>")


# ============================================================
# BLOQUE 7 — Clase Bulletin (tabla processing.bulletins)
# Sin cambios, pero incluida para referencia completa
# ============================================================
class Bulletin(Base):
    """
    processing.bulletins
    Boletín PDF generado por cada resultado de test.
    Un boletín cubre un solo test de una sola materia.
    Flujo: pending -> approved (por admin) -> delivered (al padre).
    """
    __tablename__  = "bulletins"
    __table_args__ = {"schema": "processing"}

    id_bulletin       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_result         = Column(UUID(as_uuid=True),
                                ForeignKey("processing.test_results.id_result"),
                                nullable=False, unique=True)
    id_estudiante     = Column(UUID(as_uuid=True),
                                ForeignKey("admin.estudiantes.id_estudiante"),
                                nullable=False, index=True)
    id_template       = Column(Integer,
                                ForeignKey("processing.test_templates.id_template"),
                                nullable=False)
    template_used     = Column(String(50))
    generated_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    approved_by_admin = Column(Boolean,      nullable=False, default=False)
    approved_by_user  = Column(UUID(as_uuid=True))
    approved_at       = Column(DateTime(timezone=True))
    pdf_path          = Column(Text)
    pdf_size_bytes    = Column(BigInteger)
    status            = Column(String(20),   nullable=False, default="pending")
    delivery_date     = Column(DateTime(timezone=True))
    metadata_         = Column("metadata", JSONB, nullable=False, default=dict)
    created_at        = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    result    = relationship("TestResult",  back_populates="bulletin")
    student   = relationship("Student",     back_populates="bulletins")
    template  = relationship("TestTemplate",back_populates="bulletins")

    @property
    def is_pending(self) -> bool:
        """True si está pendiente de aprobación."""
        return self.status == "pending"

    @property
    def is_approved(self) -> bool:
        """True si fue aprobado por admin."""
        return self.status == "approved"

    def __repr__(self):
        return f"<Bulletin(id={self.id_bulletin}, status={self.status})>"


# ============================================================
# BLOQUE 8 — Clase Prospecto (tabla processing.prospectos)
# NUEVA CLASE — estudiantes sin matrícula para diagnósticos
# ============================================================
class Prospecto(Base):
    """
    processing.prospectos
    Estudiantes que vienen a prueba diagnóstica sin estar matriculados.
    Los datos se extraen automáticamente del encabezado del video via OCR.
    Si el padre decide matricular al niño, el compañero crea el registro
    formal en admin.estudiantes y vincula manualmente al historial.
    """
    __tablename__  = "prospectos"
    __table_args__ = {"schema": "processing"}

    id_prospecto     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo  = Column(Text,        nullable=False)
    grado_escolar    = Column(Text)
    nombre_escuela   = Column(Text)
    fecha_prueba     = Column(Date)
    nombre_acudiente = Column(Text)
    telefono         = Column(Text)
    created_at       = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    processing_jobs = relationship("ProcessingJob", back_populates="prospecto",
                                   foreign_keys="ProcessingJob.id_prospecto")

    @property
    def first_name(self) -> str:
        """Retorna solo el primer nombre para mensajes cortos."""
        return self.nombre_completo.split()[0] if self.nombre_completo else ""

    def __repr__(self):
        return f"<Prospecto(nombre={self.nombre_completo}, grado={self.grado_escolar})>"


# ============================================================
# BLOQUE 9 — Clase ObservacionCualitativa (tabla processing.observaciones_cualitativas)
# NUEVA CLASE — respuestas al cuestionario cualitativo por materia/nivel
# ============================================================
class ObservacionCualitativa(Base):
    """
    processing.observaciones_cualitativas
    Respuestas del orientador al cuestionario cualitativo por materia/nivel.
    Basado en los PDFs oficiales de Kumon: Matemáticas, Español, Inglés.
    Se completa DESPUÉS del OCR — es opcional pero recomendado para el boletín.
    El JSONB respuestas sigue la estructura definida en
    app/config/cuestionarios.py según subject y test_code.
    Un resultado puede tener 0 o 1 observación cualitativa (UNIQUE id_result).
    """
    __tablename__  = "observaciones_cualitativas"
    __table_args__ = {"schema": "processing"}

    id_observacion  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_result       = Column(UUID(as_uuid=True),
                             ForeignKey("processing.test_results.id_result",
                                        ondelete="CASCADE"),
                             nullable=False, unique=True)
    subject         = Column(Text, nullable=False)
    test_code       = Column(Text, nullable=False)
    respuestas      = Column(JSONB, nullable=False, default=dict)
    completado_por  = Column(Text)
    completado_at   = Column(DateTime(timezone=True))
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    result = relationship("TestResult", back_populates="observacion_cualitativa")

    @property
    def esta_completo(self) -> bool:
        """True si el orientador ya respondió el cuestionario completamente."""
        return bool(self.respuestas) and self.completado_at is not None

    def __repr__(self):
        estado = "completo" if self.esta_completo else "incompleto"
        return f"<ObservacionCualitativa(result={self.id_result}, subject={self.subject}, {estado})>"


# ============================================================
# BLOQUE 10 — Clase ProcessingError (tabla audit.processing_errors)
# Sin cambios, pero incluida para referencia completa
# ============================================================
class ProcessingError(Base):
    """
    audit.processing_errors
    Errores técnicos del motor OCR y procesamiento de videos.
    Para diagnóstico, reintento y monitoreo del sistema.
    """
    __tablename__  = "processing_errors"
    __table_args__ = {"schema": "audit"}

    id_error      = Column(Integer,  primary_key=True, autoincrement=True)
    id_job        = Column(UUID(as_uuid=True),
                           ForeignKey("processing.processing_jobs.id_job"),
                           nullable=False, index=True)
    error_type    = Column(String(50), nullable=False)
    error_message = Column(Text,       nullable=False)
    stack_trace   = Column(Text)
    context_data  = Column(JSONB)
    created_at    = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relaciones
    job = relationship("ProcessingJob", back_populates="errors")

    def __repr__(self):
        return f"<ProcessingError(job={self.id_job}, type={self.error_type})>"
