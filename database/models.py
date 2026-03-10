# database/models.py
# Modelos SQLAlchemy del modulo de procesamiento
# Mapean las tablas del schema 'processing' de PostgreSQL
# Las tablas de admin (estudiantes, profesores) son de solo
# lectura para este modulo. El compañero las gestiona.
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
# FUNCION HELPER
# ============================================================

def generate_uuid():
    return str(uuid.uuid4())


# ============================================================
# TABLAS DE REFERENCIA DEL SCHEMA ADMIN
# Solo lectura. El compañero es el dueno de estas tablas.
# Las incluimos para poder hacer JOINs desde Python.
# ============================================================

class Student(Base):
    """
    Referencia a admin.estudiantes.
    Este modulo NUNCA hace INSERT ni UPDATE en esta tabla.
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

    # Relaciones hacia las tablas que SI son de este modulo
    processing_jobs = relationship("ProcessingJob", back_populates="student")
    test_results    = relationship("TestResult",    back_populates="student")
    bulletins       = relationship("Bulletin",      back_populates="student")

    @property
    def full_name(self) -> str:
        parts = [self.primer_nombre, self.segundo_nombre,
                 self.primer_apellido, self.segundo_apellido]
        return " ".join(p for p in parts if p)

    def __repr__(self):
        return f"<Student(id={self.id_estudiante}, name={self.full_name})>"


# ============================================================
# SCHEMA PROCESSING — TABLAS PROPIAS DE ESTE MODULO
# ============================================================

class TestTemplate(Base):
    """
    processing.test_templates
    Plantilla de cada test Kumon por nivel y materia.
    29 registros: 12 Matematicas + 12 Espanol + 5 Ingles.
    Define estructura, tiempo objetivo y criterios del semaforo.
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


class ProcessingJob(Base):
    """
    processing.processing_jobs
    Cola de procesamiento. Cada video o PDF subido genera un job.
    Estados: queued -> processing -> done | error | manual_review
    """
    __tablename__  = "processing_jobs"
    __table_args__ = {"schema": "processing"}

    id_job             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_estudiante      = Column(UUID(as_uuid=True),
                                ForeignKey("admin.estudiantes.id_estudiante"),
                                nullable=False, index=True)
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

    # Relaciones
    student  = relationship("Student",      back_populates="processing_jobs")
    template = relationship("TestTemplate", back_populates="processing_jobs")
    result   = relationship("TestResult",   back_populates="job", uselist=False)
    errors   = relationship("ProcessingError", back_populates="job")

    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @property
    def is_failed(self) -> bool:
        return self.status == "error"

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def __repr__(self):
        return f"<ProcessingJob(id={self.id_job}, status={self.status})>"


class TestResult(Base):
    """
    processing.test_results
    Resultado final del OCR por cada job exitoso.
    Un job produce exactamente un resultado (UNIQUE id_job).
    semaforo: verde=sube nivel, amarillo=repite, rojo=refuerza.
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
    job      = relationship("ProcessingJob", back_populates="result")
    student  = relationship("Student",       back_populates="test_results")
    template = relationship("TestTemplate",  back_populates="test_results")
    bulletin = relationship("Bulletin",      back_populates="result", uselist=False)

    @property
    def passed(self) -> bool:
        return self.semaforo == "verde"

    @property
    def needs_review(self) -> bool:
        return self.semaforo == "rojo"

    def __repr__(self):
        return (f"<TestResult(student={self.id_estudiante}, "
                f"level={self.current_level}, semaforo={self.semaforo})>")


class Bulletin(Base):
    """
    processing.bulletins
    Boletin PDF generado por cada resultado de test.
    Un boletin cubre un solo test de una sola materia.
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
        return self.status == "pending"

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"

    def __repr__(self):
        return f"<Bulletin(id={self.id_bulletin}, status={self.status})>"


class ProcessingError(Base):
    """
    audit.processing_errors
    Errores tecnicos del motor OCR y procesamiento de videos.
    Para diagnostico, reintento y monitoreo del sistema.
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
