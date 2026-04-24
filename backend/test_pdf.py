# backend/test_pdf.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from decimal import Decimal
from app.services.report_generator import build_report_data, QuantitativeInput, QualitativeInput
from app.services.pdf_generator import generate_pdf

cuant = QuantitativeInput(
    subject="matematicas", test_code="P4", display_name="Nivel P — Hoja 4",
    ws="P4A", test_date=None,
    study_time_min=Decimal("14.4"), target_time_min=Decimal("12.0"),
    correct_answers=37, total_questions=60,
    percentage=Decimal("61.67"),
    current_level="P", starting_point="O181a",
    semaforo="verde", recommendation="El estudiante puede avanzar al siguiente nivel.",
)
cual = QualitativeInput(
    total_porcentaje=72.5, etiqueta_total="en_desarrollo",
    secciones=[
        {"nombre": "Ritmo de trabajo", "etiqueta": "en_desarrollo", "porcentaje": 70.0},
        {"nombre": "Postura",          "etiqueta": "refuerzo",      "porcentaje": 45.0},
        {"nombre": "Concentración",    "etiqueta": "fortaleza",     "porcentaje": 85.0},
    ],
    auto_flags=["ritmo_trabajo", "concentracion"],
    prefills={},
)

report_data = build_report_data(cuant, cual)
path = generate_pdf(
    report_data=report_data,
    job_created_at=datetime(2026, 4, 22, 10, 30),
    prospecto_nombre="Juan Pérez",
    output_path="boletin_prueba.pdf",
    orientador_nombre="Orientadora María",
    hubo_correcciones=False,
)
print(f"PDF generado en: {path}")