"""
seed_data.py
Inserta datos de prueba en la BD para desarrollo independiente.
SOLO usar en ambiente de desarrollo, nunca en producción.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uuid import uuid4
from datetime import date
from sqlalchemy import text
from config.database import SessionLocal, verificar_conexion

# --- Datos de prueba ---
ESTUDIANTES_PRUEBA = [
    {
        "id_estudiante": str(uuid4()),
        "codigo_estudiante": "EST-001",
        "primer_nombre": "Ana",
        "segundo_nombre": "Maria",
        "primer_apellido": "Garcia",
        "segundo_apellido": "Lopez",
        "tipo_documento": "TI",
        "numero_documento": "1000000001",
        "fecha_nacimiento": "2015-03-10",
        "genero": "femenino",
        "nombre_acudiente": "Carmen Lopez",
        "telefono_acudiente": "3001234567",
        "email_acudiente": "carmen.lopez@email.com",
        "grado_escolar": "4 primaria",
        "estado": "activo",
    },
    {
        "id_estudiante": str(uuid4()),
        "codigo_estudiante": "EST-002",
        "primer_nombre": "Carlos",
        "segundo_nombre": None,
        "primer_apellido": "Martinez",
        "segundo_apellido": "Ruiz",
        "tipo_documento": "TI",
        "numero_documento": "1000000002",
        "fecha_nacimiento": "2014-07-22",
        "genero": "masculino",
        "nombre_acudiente": "Pedro Martinez",
        "telefono_acudiente": "3007654321",
        "email_acudiente": "pedro.martinez@email.com",
        "grado_escolar": "5 primaria",
        "estado": "activo",
    },
    {
        "id_estudiante": str(uuid4()),
        "codigo_estudiante": "EST-003",
        "primer_nombre": "Sofia",
        "segundo_nombre": None,
        "primer_apellido": "Torres",
        "segundo_apellido": "Perez",
        "tipo_documento": "TI",
        "numero_documento": "1000000003",
        "fecha_nacimiento": "2016-11-05",
        "genero": "femenino",
        "nombre_acudiente": "Luis Torres",
        "telefono_acudiente": "3109876543",
        "email_acudiente": "luis.torres@email.com",
        "grado_escolar": "3 primaria",
        "estado": "activo",
    },
]


def seed_estudiantes(db):
    """Inserta estudiantes de prueba si no existen."""
    for est in ESTUDIANTES_PRUEBA:
        # Verificar si ya existe por codigo
        resultado = db.execute(
            text("SELECT id_estudiante FROM admin.estudiantes WHERE codigo_estudiante = :codigo"),
            {"codigo": est["codigo_estudiante"]}
        ).fetchone()

        if resultado:
            print(f"  [SKIP] {est['primer_nombre']} {est['primer_apellido']} ya existe")
            continue

        # Convertir tipos antes del INSERT para evitar conflicto con sintaxis ::uuid de PostgreSQL
        from uuid import UUID as UUIDType
        params = dict(est)
        params["id_estudiante"] = UUIDType(est["id_estudiante"])
        params["fecha_nacimiento"] = date.fromisoformat(est["fecha_nacimiento"])

        db.execute(text("""
            INSERT INTO admin.estudiantes (
                id_estudiante, codigo_estudiante,
                primer_nombre, segundo_nombre,
                primer_apellido, segundo_apellido,
                tipo_documento, numero_documento,
                fecha_nacimiento, genero,
                nombre_acudiente, telefono_acudiente,
                email_acudiente, grado_escolar, estado
            ) VALUES (
                :id_estudiante, :codigo_estudiante,
                :primer_nombre, :segundo_nombre,
                :primer_apellido, :segundo_apellido,
                :tipo_documento, :numero_documento,
                :fecha_nacimiento, :genero,
                :nombre_acudiente, :telefono_acudiente,
                :email_acudiente, :grado_escolar, :estado
            )
        """), params)

        print(f"  [OK] Insertado: {est['primer_nombre']} {est['primer_apellido']} ({est['codigo_estudiante']})")

    db.commit()



def main():
    print("=" * 50)
    print("SEED DATA - Automatización Kumon")
    print("=" * 50)

    # Verificar conexión primero
    estado = verificar_conexion()
    print(f"\nConexión BD: {estado}")

    if not estado:
        print("ERROR: No se puede conectar a la BD. Verifica tu .env")
        sys.exit(1)

    db = SessionLocal()
    try:
        print("\n>> Insertando estudiantes de prueba...")
        seed_estudiantes(db)
        print("\n>> Verificando resultado:")
        total = db.execute(text("SELECT COUNT(*) FROM admin.estudiantes")).scalar()
        print(f"   Total estudiantes en BD: {total}")

        # Mostrar los UUIDs para usarlos en pruebas
        estudiantes = db.execute(
            text("SELECT id_estudiante, codigo_estudiante, primer_nombre, primer_apellido FROM admin.estudiantes ORDER BY codigo_estudiante")
        ).fetchall()

        print("\n>> UUIDs de estudiantes (cópialos para probar la API):")
        print("-" * 60)
        for e in estudiantes:
            print(f"  {e[1]} | {e[2]} {e[3]}")
            print(f"  UUID: {e[0]}")
            print()

    finally:
        db.close()

    print("=" * 50)
    print("Seed completado exitosamente")
    print("=" * 50)


if __name__ == "__main__":
    main()
