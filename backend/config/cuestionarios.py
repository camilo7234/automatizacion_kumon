from __future__ import annotations

"""
config/cuestionarios.py
══════════════════════════════════════════════════════════════════
Motor declarativo de cuestionarios cualitativos.

Objetivos:
  - Formularios MUY cortos (máx. 8 preguntas por test).
  - Escala numérica 1–5 uniforme.
  - Plantillas por materia/nivel, optimizadas para nuestro proyecto.
  - Cálculo por sección y total en escala 0–100 + etiqueta.
  - Integración directa con:
      * GET /api/v1/cuestionario/{result_id}
      * POST /api/v1/cuestionario/{result_id}
      * Boletín 65% cuantitativo + 35% cualitativo.

Etiquetas cualitativas:
  - fortaleza     (76–100)
  - en_desarrollo (51–75)
  - refuerzo      (26–50)
  - atencion      (0–25)
══════════════════════════════════════════════════════════════════
"""

from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────
# Escala fija 1–5
# ──────────────────────────────────────────────────────────────

ESCALA_1_5 = {
    "min": 1,
    "max": 5,
    "labels": {
        1: "Muy bajo",
        2: "Bajo",
        3: "Medio",
        4: "Alto",
        5: "Muy alto",
    },
}


# ──────────────────────────────────────────────────────────────
# Plantillas por materia/nivel
# ──────────────────────────────────────────────────────────────

CUESTIONARIOS: Dict[Tuple[str, str], Dict[str, Any]] = {
    # ── INGLÉS ────────────────────────────────────────────────
    ("ingles", "K"): {
        "secciones": [
            {
                "id": "exposicion_basica",
                "titulo": "Respuesta al inglés oral y visual",
                "peso": 0.4,
                "items": [
                    {
                        "id": "escucha_frases_simples",
                        "texto": "Comprende instrucciones o expresiones simples en inglés y responde apoyándose en la imagen o el significado.",
                        "peso": 0.5,
                    },
                    {
                        "id": "repite_palabras",
                        "texto": "Intenta repetir o decir palabras y expresiones en inglés cuando escucha el modelo o mira la imagen.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "actitud",
                "titulo": "Postura y actitud ante la prueba",
                "peso": 0.3,
                "items": [
                    {
                        "id": "participacion",
                        "texto": "Sigue las instrucciones del orientador y participa con interés durante la prueba.",
                        "peso": 0.5,
                    },
                    {
                        "id": "persistencia",
                        "texto": "Se mantiene concentrado e intenta continuar incluso cuando encuentra dificultad.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "autonomia_inicial",
                "titulo": "Escritura y autonomía inicial",
                "peso": 0.3,
                "items": [
                    {
                        "id": "sigue_rutina",
                        "texto": "Copia o traza con calma y corrección, siguiendo la rutina de trabajo con poca guía.",
                        "peso": 0.5,
                    },
                    {
                        "id": "usa_material",
                        "texto": "Escribe o responde de forma independiente cuando el ejercicio se lo permite, sin distraerse constantemente.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("ingles", "PII"): {
        "secciones": [
            {
                "id": "lectura_palabras",
                "titulo": "Lectura y respuesta a palabras",
                "peso": 0.35,
                "items": [
                    {
                        "id": "lee_palabras_conocidas",
                        "texto": "Reconoce y lee con seguridad palabras frecuentes del nivel.",
                        "peso": 0.5,
                    },
                    {
                        "id": "decodifica_nuevas",
                        "texto": "Intenta resolver palabras o ejercicios nuevos sin abandonar rápidamente.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_basica",
                "titulo": "Relación sonido, significado y texto",
                "peso": 0.35,
                "items": [
                    {
                        "id": "relaciona_imagen_texto",
                        "texto": "Relaciona correctamente palabras con imágenes, significado o ejemplos del ejercicio.",
                        "peso": 0.5,
                    },
                    {
                        "id": "sigue_instrucciones",
                        "texto": "Lee y sigue instrucciones cortas en inglés con apoyo mínimo del orientador.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "ritmo_trabajo",
                "titulo": "Escritura y lectura en voz alta",
                "peso": 0.30,
                "items": [
                    {
                        "id": "mantiene_ritmo",
                        "texto": "Copia palabras, expresiones o frases de forma tranquila y correcta.",
                        "peso": 0.5,
                    },
                    {
                        "id": "termina_tiempo",
                        "texto": "Lee en voz alta en inglés de forma natural y se aproxima a una pronunciación correcta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("ingles", "PI"): {
        "secciones": [
            {
                "id": "fluidez_lectora",
                "titulo": "Lectura en voz alta",
                "peso": 0.4,
                "items": [
                    {
                        "id": "lectura_corrida",
                        "texto": "Lee en voz alta de forma corrida, con pocas detenciones y buen ritmo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "pronunciacion",
                        "texto": "Pronuncia la mayoría de palabras de forma comprensible y natural.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_oraciones",
                "titulo": "Significado y estructura de oraciones",
                "peso": 0.3,
                "items": [
                    {
                        "id": "responde_preguntas",
                        "texto": "Responde los ejercicios basándose en su comprensión y no al azar.",
                        "peso": 0.5,
                    },
                    {
                        "id": "identifica_idea",
                        "texto": "Relaciona la imagen, el diálogo o la oración con el significado y el orden correcto de las palabras.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "autonomia_trabajo",
                "titulo": "Escritura y autonomía en el trabajo",
                "peso": 0.3,
                "items": [
                    {
                        "id": "resuelve_solo",
                        "texto": "Copia palabras, expresiones y frases de forma tranquila y correcta, con poca ayuda.",
                        "peso": 0.5,
                    },
                    {
                        "id": "auto_corrige",
                        "texto": "Escribe de forma independiente y se auto-corrige cuando detecta un error.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("ingles", "M"): {
        "secciones": [
            {
                "id": "fluidez",
                "titulo": "Lectura en voz alta",
                "peso": 0.4,
                "items": [
                    {
                        "id": "ritmo_estable",
                        "texto": "Lee en voz alta con un ritmo estable y sin silabeo excesivo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "entonacion",
                        "texto": "Lee de forma natural y se aproxima a una pronunciación adecuada.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_texto",
                "titulo": "Respuesta a ejercicios y estructura gramatical",
                "peso": 0.35,
                "items": [
                    {
                        "id": "inferencias",
                        "texto": "Responde los ejercicios basándose en sus conocimientos y en la comprensión del enunciado.",
                        "peso": 0.5,
                    },
                    {
                        "id": "vocabulario_contexto",
                        "texto": "Al ordenar, completar o transformar frases, demuestra comprensión de la estructura gramatical aunque cometa algunos errores.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "gestion_tiempo",
                "titulo": "Actitud, concentración y escritura",
                "peso": 0.25,
                "items": [
                    {
                        "id": "sin_pausas_largas",
                        "texto": "Intenta resolver los ejercicios que le resultan difíciles y mantiene la concentración durante la prueba.",
                        "peso": 0.5,
                    },
                    {
                        "id": "termina_con_calma",
                        "texto": "Copia palabras, expresiones y frases de forma tranquila y correcta, y escribe de forma independiente cuando puede.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("ingles", "H"): {
        "secciones": [
            {
                "id": "comprension_profunda",
                "titulo": "Respuesta a ejercicios y comprensión",
                "peso": 0.45,
                "items": [
                    {
                        "id": "argumentos",
                        "texto": "Responde los ejercicios mostrando comprensión del texto y de la consigna.",
                        "peso": 0.5,
                    },
                    {
                        "id": "opinion_justificada",
                        "texto": "Al transformar o completar frases, conserva la estructura básica aunque presente errores puntuales.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "vocabulario_estrategias",
                "titulo": "Escritura y lectura en voz alta",
                "peso": 0.3,
                "items": [
                    {
                        "id": "usa_parafrasis",
                        "texto": "Copia y escribe respuestas completas con constancia y de forma correcta.",
                        "peso": 0.5,
                    },
                    {
                        "id": "maneja_palabras_desconocidas",
                        "texto": "Lee en voz alta de forma natural y se aproxima a una pronunciación correcta incluso con vocabulario más complejo.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "autonomia_estudio",
                "titulo": "Autonomía y actitud de trabajo",
                "peso": 0.25,
                "items": [
                    {
                        "id": "organiza_tiempo",
                        "texto": "Lee y sigue las instrucciones de la prueba con poca ayuda del orientador.",
                        "peso": 0.5,
                    },
                    {
                        "id": "mantiene_enfoque",
                        "texto": "Se mantiene enfocado e intenta resolver los ejercicios retadores sin abandonar con facilidad.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    # ── MATEMÁTICAS ──────────────────────────────────────────
    ("matematicas", "K2"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y concentración",
                "peso": 0.35,
                "items": [
                    {
                        "id": "sigue_instrucciones",
                        "texto": "Puede seguir instrucciones básicas (sentarse, sujetar el lápiz).",
                        "peso": 0.5,
                    },
                    {
                        "id": "motivacion",
                        "texto": "Está motivado y trata de resolver la prueba de forma independiente.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "secuencia_numerica",
                "titulo": "Comprensión de la secuencia numérica",
                "peso": 0.35,
                "items": [
                    {
                        "id": "cuenta_imagenes",
                        "texto": "Cuenta imágenes o lee tablas numéricas mientras señala los números.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lee_tabla",
                        "texto": "Lee espontáneamente el primer número de la tabla y continúa.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lapiz_escritura",
                "titulo": "Manejo del lápiz y escritura de números",
                "peso": 0.30,
                "items": [
                    {
                        "id": "sujeta_lapiz",
                        "texto": "Sujeta el lápiz de forma adecuada para su edad.",
                        "peso": 0.5,
                    },
                    {
                        "id": "trazos_numeros",
                        "texto": "Traza líneas y números siguiendo el orden correcto de los trazos.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "K1"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía",
                "peso": 0.35,
                "items": [
                    {
                        "id": "sigue_instrucciones",
                        "texto": "Lee o escucha las instrucciones y las sigue con poca ayuda.",
                        "peso": 0.5,
                    },
                    {
                        "id": "concentracion",
                        "texto": "Se mantiene concentrado durante la mayor parte de la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "habilidad_suma",
                "titulo": "Habilidad de suma",
                "peso": 0.40,
                "items": [
                    {
                        "id": "responde_inmediato",
                        "texto": "Responde a sumas simples de inmediato o con poca demora.",
                        "peso": 0.5,
                    },
                    {
                        "id": "estrategia_calculo",
                        "texto": "Usa estrategias de cálculo adecuadas (dedos, memoria, series de diez).",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lapiz_escritura",
                "titulo": "Manejo del lápiz / escritura de números",
                "peso": 0.25,
                "items": [
                    {
                        "id": "escritura_numeros",
                        "texto": "Escribe los números con dirección y forma correctas.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lineas_continuas",
                        "texto": "Traza líneas continuas sin detenerse innecesariamente.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "P1"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y actitud ante la prueba",
                "peso": 0.30,
                "items": [
                    {
                        "id": "motivacion",
                        "texto": "Está motivado y trata de resolver lo que puede de forma independiente.",
                        "peso": 0.5,
                    },
                    {
                        "id": "enfrenta_dificiles",
                        "texto": "Intenta resolver los ejercicios que le resultan difíciles.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "suma_resta",
                "titulo": "Habilidad de suma y resta",
                "peso": 0.45,
                "items": [
                    {
                        "id": "responde_rapido",
                        "texto": "Responde con rapidez a sumas y restas de una cifra.",
                        "peso": 0.5,
                    },
                    {
                        "id": "estrategia_calculo",
                        "texto": "Usa estrategias de cálculo apropiadas sin depender siempre de los dedos.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "concentracion",
                "titulo": "Concentración y ritmo de trabajo",
                "peso": 0.25,
                "items": [
                    {
                        "id": "mantiene_ritmo",
                        "texto": "Mantiene un ritmo de trabajo constante, sin pausas largas.",
                        "peso": 0.5,
                    },
                    {
                        "id": "termina_tareas",
                        "texto": "Procura completar todas las secciones dentro del tiempo disponible.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "P2"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía",
                "peso": 0.30,
                "items": [
                    {
                        "id": "lee_instrucciones",
                        "texto": "Lee y sigue las instrucciones de la prueba sin apoyo constante.",
                        "peso": 0.5,
                    },
                    {
                        "id": "concentracion",
                        "texto": "Se mantiene concentrado durante toda la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "suma_resta",
                "titulo": "Suma y resta con llevar y prestar",
                "peso": 0.40,
                "items": [
                    {
                        "id": "maneja_llevar",
                        "texto": "Maneja correctamente las reservas y préstamos en cálculos verticales.",
                        "peso": 0.5,
                    },
                    {
                        "id": "tipo_ejercicio_lento",
                        "texto": "Solo se demora en ejercicios razonablemente complejos (más dígitos).",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "ritmo",
                "titulo": "Ritmo y método de cálculo",
                "peso": 0.30,
                "items": [
                    {
                        "id": "calculo_mental",
                        "texto": "Realiza parte del cálculo mentalmente sin escribir todos los pasos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "organiza_trabajo",
                        "texto": "Organiza su trabajo en la hoja sin tachones ni desorden excesivo.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "P3"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y perseverancia",
                "peso": 0.25,
                "items": [
                    {
                        "id": "resuelve_dificiles",
                        "texto": "Intenta resolver ejercicios difíciles sin abandonarlos rápidamente.",
                        "peso": 0.5,
                    },
                    {
                        "id": "concentracion",
                        "texto": "Mantiene la concentración durante el tiempo de la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "suma_resta",
                "titulo": "Suma y resta",
                "peso": 0.35,
                "items": [
                    {
                        "id": "detecta_tipo_lento",
                        "texto": "Solo se demora en sumas/restas con varios dígitos o préstamos complejos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "metodo_vertical",
                        "texto": "Aplica correctamente el método vertical (reservas, préstamos).",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "multi_div",
                "titulo": "Multiplicación y división",
                "peso": 0.40,
                "items": [
                    {
                        "id": "tablas",
                        "texto": "Recuerda con seguridad las tablas de multiplicar necesarias.",
                        "peso": 0.5,
                    },
                    {
                        "id": "metodo_division",
                        "texto": "En división, encuentra cocientes y restos con un método ordenado.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "P4"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y actitud",
                "peso": 0.25,
                "items": [
                    {
                        "id": "independencia",
                        "texto": "Resuelve lo que puede de manera independiente, incluso si duda.",
                        "peso": 0.5,
                    },
                    {
                        "id": "afronta_retos",
                        "texto": "Intenta ejercicios retadores en lugar de saltarlos.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "suma_resta",
                "titulo": "Suma y resta con varios dígitos",
                "peso": 0.35,
                "items": [
                    {
                        "id": "maneja_reservas_prestamos",
                        "texto": "Maneja con precisión reservas y préstamos en ejercicios largos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "fluidez_calculo",
                        "texto": "Resuelve cálculos sin detenerse en cada dígito individual.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "multi_div",
                "titulo": "Multiplicación y división",
                "peso": 0.40,
                "items": [
                    {
                        "id": "multi_2x2",
                        "texto": "Resuelve multiplicaciones 2×2 dígitos con buen ritmo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "division_2dig",
                        "texto": "En divisiones por 2 dígitos, escribe pasos intermedios de forma organizada.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "P5"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y concentración",
                "peso": 0.25,
                "items": [
                    {
                        "id": "mantiene_concentracion",
                        "texto": "Se mantiene concentrado incluso cuando los ejercicios se alargan.",
                        "peso": 0.5,
                    },
                    {
                        "id": "persistencia",
                        "texto": "Muestra persistencia ante ejercicios complejos.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "suma_resta",
                "titulo": "Suma y resta avanzadas",
                "peso": 0.30,
                "items": [
                    {
                        "id": "complejidad_suma_resta",
                        "texto": "Solo se demora en operaciones con muchos dígitos o varios préstamos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "metodo_ordenado",
                        "texto": "Escribe reservas y préstamos de forma clara y ordenada.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "fracciones",
                "titulo": "Cálculo con fracciones",
                "peso": 0.45,
                "items": [
                    {
                        "id": "tipos_fracciones",
                        "texto": "Resuelve conversiones y operaciones básicas con fracciones con apoyo mínimo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "estrategia_fracciones",
                        "texto": "Usa estrategias adecuadas (simplificación, equivalencias) sin perderse.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "P6"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y gestión del esfuerzo",
                "peso": 0.20,
                "items": [
                    {
                        "id": "mantiene_esfuerzo",
                        "texto": "Mantiene el esfuerzo durante toda la prueba, sin rendirse.",
                        "peso": 0.5,
                    },
                    {
                        "id": "planifica_tiempo",
                        "texto": "Distribuye el tiempo entre secciones de forma razonable.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "fracciones",
                "titulo": "Cálculo de fracciones (P6)",
                "peso": 0.50,
                "items": [
                    {
                        "id": "fracciones_complejas",
                        "texto": "Resuelve fracciones con denominadores distintos y varios pasos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "uso_mcm_simplificacion",
                        "texto": "Usa MCM y simplificación en pasos intermedios con seguridad.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "calculo_mental",
                "titulo": "Cálculo mental y estrategia",
                "peso": 0.30,
                "items": [
                    {
                        "id": "mental_rapido",
                        "texto": "Puede hacer parte del cálculo mentalmente sin escribirlo todo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "detecta_patrones",
                        "texto": "Detecta patrones o atajos razonables para simplificar cálculos.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "M1"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y responsabilidad",
                "peso": 0.20,
                "items": [
                    {
                        "id": "asume_reto",
                        "texto": "Asume la prueba como un reto serio y la completa.",
                        "peso": 0.5,
                    },
                    {
                        "id": "trabaja_sin_distracciones",
                        "texto": "Trabaja sin distracciones prolongadas.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "aritmetica_superior",
                "titulo": "Aritmética superior",
                "peso": 0.45,
                "items": [
                    {
                        "id": "multi_div_avanzada",
                        "texto": "Resuelve multiplicaciones y divisiones de varios dígitos con soltura.",
                        "peso": 0.5,
                    },
                    {
                        "id": "fracciones_m1",
                        "texto": "Opera con fracciones y números mixtos con procedimiento claro.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "razonamiento",
                "titulo": "Razonamiento y método",
                "peso": 0.35,
                "items": [
                    {
                        "id": "interpreta_problemas",
                        "texto": "Interpreta correctamente el enunciado de problemas de palabras.",
                        "peso": 0.5,
                    },
                    {
                        "id": "organiza_procedimiento",
                        "texto": "Escribe los pasos de solución en orden lógico.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "M2"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía",
                "peso": 0.20,
                "items": [
                    {
                        "id": "organiza_trabajo",
                        "texto": "Organiza su trabajo sin depender del orientador.",
                        "peso": 0.5,
                    },
                    {
                        "id": "controla_tiempo",
                        "texto": "Controla su tiempo y ajusta el ritmo cuando es necesario.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "fracciones_decimales",
                "titulo": "Fracciones, decimales y porcentajes",
                "peso": 0.45,
                "items": [
                    {
                        "id": "conecta_representaciones",
                        "texto": "Conecta fracciones, decimales y porcentajes sin confundirse.",
                        "peso": 0.5,
                    },
                    {
                        "id": "opera_representaciones",
                        "texto": "Opera correctamente usando la forma más conveniente (fracción/decimal).",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "problemas_aplicados",
                "titulo": "Problemas aplicados",
                "peso": 0.35,
                "items": [
                    {
                        "id": "traduce_enunciado",
                        "texto": "Traduce enunciados a operaciones de forma adecuada.",
                        "peso": 0.5,
                    },
                    {
                        "id": "elige_estrategia",
                        "texto": "Elige estrategias eficientes para resolver problemas multi‑paso.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "M3"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y foco en problemas largos",
                "peso": 0.20,
                "items": [
                    {
                        "id": "mantiene_foco",
                        "texto": "Mantiene el foco en problemas largos y desafiantes.",
                        "peso": 0.5,
                    },
                    {
                        "id": "no_abandona",
                        "texto": "No abandona los problemas a mitad del procedimiento.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "algebra_inicial",
                "titulo": "Álgebra inicial / estructuras",
                "peso": 0.45,
                "items": [
                    {
                        "id": "maneja_letras",
                        "texto": "Maneja letras y símbolos sin confundirlos con números concretos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "resuelve_ecuaciones",
                        "texto": "Resuelve ecuaciones sencillas siguiendo pasos lógicos.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "aplicaciones",
                "titulo": "Aplicación en problemas",
                "peso": 0.35,
                "items": [
                    {
                        "id": "modela_situaciones",
                        "texto": "Modela situaciones reales con expresiones o ecuaciones simples.",
                        "peso": 0.5,
                    },
                    {
                        "id": "verifica_resultado",
                        "texto": "Verifica si sus resultados tienen sentido en el contexto.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("matematicas", "M4"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y disciplina de estudio",
                "peso": 0.20,
                "items": [
                    {
                        "id": "gestiona_tiempo",
                        "texto": "Gestiona el tiempo de estudio de forma disciplinada.",
                        "peso": 0.5,
                    },
                    {
                        "id": "mantiene_constancia",
                        "texto": "Mantiene constancia incluso ante temas más abstractos.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "algebra_avanzada",
                "titulo": "Álgebra y razonamiento avanzado",
                "peso": 0.50,
                "items": [
                    {
                        "id": "manipula_expresiones",
                        "texto": "Manipula expresiones algebraicas complejas con seguridad.",
                        "peso": 0.5,
                    },
                    {
                        "id": "demuestra_pasos",
                        "texto": "Justifica o explica los pasos principales de su solución.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "autonomia",
                "titulo": "Autonomía y confianza matemática",
                "peso": 0.30,
                "items": [
                    {
                        "id": "toma_iniciativa",
                        "texto": "Toma iniciativa para probar distintos enfoques cuando uno no funciona.",
                        "peso": 0.5,
                    },
                    {
                        "id": "confianza_responder",
                        "texto": "Responde con confianza, incluso cuando el problema no sigue un patrón típico.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    # ── ESPAÑOL ──────────────────────────────────────────
    ("espanol", "K2"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y disposición ante la prueba",
                "peso": 0.35,
                "items": [
                    {
                        "id": "sigue_instrucciones",
                        "texto": "Puede seguir las instrucciones básicas del orientador, como sentarse correctamente o sujetar el lápiz.",
                        "peso": 0.5,
                    },
                    {
                        "id": "motivacion_independencia",
                        "texto": "Está motivado para resolver la prueba e intenta trabajar de manera independiente.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_oral_inicial",
                "titulo": "Vocabulario, dicción y lectura en voz alta",
                "peso": 0.35,
                "items": [
                    {
                        "id": "reconoce_nombra_imagenes",
                        "texto": "Reconoce y señala objetos, y dice palabras u oraciones mientras mira la imagen.",
                        "peso": 0.5,
                    },
                    {
                        "id": "intenta_repite_lee",
                        "texto": "Repite o intenta leer palabras y oraciones, y muestra fluidez inicial o autocorrección cuando se equivoca.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lapiz_escritura",
                "titulo": "Manejo del lápiz y escritura inicial",
                "peso": 0.30,
                "items": [
                    {
                        "id": "sujecion_presion_lapiz",
                        "texto": "Sujeta el lápiz adecuadamente para su etapa y controla razonablemente la presión al escribir.",
                        "peso": 0.5,
                    },
                    {
                        "id": "trazo_continuo_ordenado",
                        "texto": "Traza líneas y escribe con continuidad, respetando inicio, final y espacio de trabajo.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "K1"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía ante la prueba",
                "peso": 0.35,
                "items": [
                    {
                        "id": "lee_sigue_instrucciones",
                        "texto": "Lee o comprende las instrucciones y las sigue con poca ayuda del orientador.",
                        "peso": 0.5,
                    },
                    {
                        "id": "motivacion_concentracion",
                        "texto": "Está motivado, intenta resolver de forma independiente y puede mantenerse concentrado durante la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_comprension",
                "titulo": "Lectura, comprensión y lectura en voz alta",
                "peso": 0.40,
                "items": [
                    {
                        "id": "comprende_sin_releer",
                        "texto": "Responde preguntas de comprensión después de leer, sin depender constantemente de volver a mirar el texto.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lectura_voz_alta_fluida",
                        "texto": "Lee en voz alta con precisión básica, ritmo adecuado y pausas razonables para su nivel.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "escritura",
                "titulo": "Manejo del lápiz y escritura",
                "peso": 0.25,
                "items": [
                    {
                        "id": "escribe_letras_conocidas",
                        "texto": "Intenta escribir letras que conoce y mantiene una formación reconocible de mayúsculas o minúsculas.",
                        "peso": 0.5,
                    },
                    {
                        "id": "trazos_y_escritura_continua",
                        "texto": "Escribe letras o palabras con trazos en orden correcto y con continuidad razonable.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "P1"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y disposición de trabajo",
                "peso": 0.30,
                "items": [
                    {
                        "id": "motivacion_autonomia",
                        "texto": "Está motivado para resolver la prueba e intenta trabajar de manera independiente.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lee_instrucciones_concentra",
                        "texto": "Lee y sigue las instrucciones, lee el texto antes de responder y mantiene la concentración durante la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_escritura",
                "titulo": "Letras, estructura y comprensión",
                "peso": 0.45,
                "items": [
                    {
                        "id": "escribe_respuesta_correcta",
                        "texto": "Escribe letras y respuestas con claridad razonable y sin errores ortográficos que afecten la comprensión.",
                        "peso": 0.5,
                    },
                    {
                        "id": "responde_con_facilidad",
                        "texto": "Después de leer el enunciado y la pregunta, puede responder con relativa rapidez y escribir la respuesta con facilidad.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_oral",
                "titulo": "Lectura en voz alta",
                "peso": 0.25,
                "items": [
                    {
                        "id": "fluidez_lectora",
                        "texto": "Lee en voz alta con fluidez adecuada para su nivel, sin detenerse excesivamente en cada palabra.",
                        "peso": 0.5,
                    },
                    {
                        "id": "precision_pausas",
                        "texto": "Mantiene precisión básica, velocidad apropiada y pausas razonables al leer en voz alta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "P2"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía de trabajo",
                "peso": 0.30,
                "items": [
                    {
                        "id": "motivacion_independencia",
                        "texto": "Está motivado para resolver la prueba e intenta avanzar con independencia.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lee_indicaciones_y_texto",
                        "texto": "Lee las instrucciones y los textos antes de responder, y sostiene la concentración durante la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_escritura",
                "titulo": "Letras, estructura y comprensión",
                "peso": 0.45,
                "items": [
                    {
                        "id": "responde_sin_errores_relevantes",
                        "texto": "Responde preguntas de comprensión sin errores ortográficos relevantes y con estructura comprensible.",
                        "peso": 0.5,
                    },
                    {
                        "id": "responde_tras_leer",
                        "texto": "Tras leer el enunciado y la pregunta, responde con seguridad y escribe la respuesta sin copiar letra por letra en exceso.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_oral",
                "titulo": "Lectura en voz alta",
                "peso": 0.25,
                "items": [
                    {
                        "id": "lectura_fluida",
                        "texto": "Lee en voz alta con un nivel de fluidez acorde al grado, manteniendo continuidad en la lectura.",
                        "peso": 0.5,
                    },
                    {
                        "id": "ritmo_y_pausas",
                        "texto": "Mantiene un ritmo adecuado y hace pausas razonables al leer en voz alta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },
        ("espanol", "P3"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía de trabajo",
                "peso": 0.30,
                "items": [
                    {
                        "id": "motivacion_constancia",
                        "texto": "Está motivado para resolver la prueba y mantiene constancia durante el trabajo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lee_indicaciones_y_texto",
                        "texto": "Lee las instrucciones y los textos antes de responder, y sostiene la concentración durante la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_escritura",
                "titulo": "Letras, estructura y comprensión",
                "peso": 0.45,
                "items": [
                    {
                        "id": "responde_con_ortografia_basica",
                        "texto": "Responde preguntas de comprensión con ortografía razonable y estructura clara para su nivel.",
                        "peso": 0.5,
                    },
                    {
                        "id": "escribe_con_mayor_fluidez",
                        "texto": "Después de leer el enunciado y la pregunta, escribe la respuesta con relativa facilidad y sin depender excesivamente de copiar palabra por palabra.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_oral",
                "titulo": "Lectura en voz alta",
                "peso": 0.25,
                "items": [
                    {
                        "id": "lectura_fluida",
                        "texto": "Lee en voz alta con continuidad y fluidez acordes al nivel.",
                        "peso": 0.5,
                    },
                    {
                        "id": "precision_ritmo_pausas",
                        "texto": "Mantiene precisión básica, ritmo adecuado y pausas razonables al leer en voz alta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "P4"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y hábitos de trabajo",
                "peso": 0.30,
                "items": [
                    {
                        "id": "trabaja_con_autonomia",
                        "texto": "Aborda la prueba con autonomía y procura avanzar sin depender constantemente del orientador.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lee_y_se_concentra",
                        "texto": "Lee instrucciones y textos antes de responder, y mantiene la concentración durante la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_escritura",
                "titulo": "Letras, estructura y comprensión",
                "peso": 0.45,
                "items": [
                    {
                        "id": "estructura_respuestas_claras",
                        "texto": "Escribe respuestas comprensibles, con estructura clara y con errores ortográficos poco frecuentes o poco disruptivos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "responde_con_agilidad",
                        "texto": "Después de leer el texto y la pregunta, responde con agilidad razonable y escribe con mayor soltura.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_oral",
                "titulo": "Lectura en voz alta",
                "peso": 0.25,
                "items": [
                    {
                        "id": "fluidez_sostenida",
                        "texto": "Lee en voz alta con fluidez sostenida y sin detenerse innecesariamente.",
                        "peso": 0.5,
                    },
                    {
                        "id": "entonacion_y_pausas",
                        "texto": "Hace pausas adecuadas y mantiene una entonación comprensible al leer.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "P5"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía lectora",
                "peso": 0.30,
                "items": [
                    {
                        "id": "trabaja_con_iniciativa",
                        "texto": "Trabaja con iniciativa y busca resolver la prueba con independencia.",
                        "peso": 0.5,
                    },
                    {
                        "id": "mantiene_concentracion",
                        "texto": "Lee instrucciones y textos antes de responder, y mantiene la concentración durante toda la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_escritura",
                "titulo": "Letras, estructura y comprensión",
                "peso": 0.45,
                "items": [
                    {
                        "id": "respuestas_ortografia_adecuada",
                        "texto": "Responde ejercicios de comprensión con ortografía adecuada y con estructura de respuesta clara.",
                        "peso": 0.5,
                    },
                    {
                        "id": "escribe_respuesta_con_facilidad",
                        "texto": "Después de leer el enunciado y la pregunta, escribe la respuesta con facilidad creciente y sin excesiva dependencia del texto.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_oral",
                "titulo": "Lectura en voz alta",
                "peso": 0.25,
                "items": [
                    {
                        "id": "lectura_natural",
                        "texto": "Lee en voz alta de forma natural y con buena continuidad para su nivel.",
                        "peso": 0.5,
                    },
                    {
                        "id": "precision_y_ritmo",
                        "texto": "Mantiene precisión, velocidad y pausas adecuadas al leer en voz alta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "P6"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía de estudio",
                "peso": 0.30,
                "items": [
                    {
                        "id": "autonomia_en_prueba",
                        "texto": "Resuelve la prueba con autonomía y muestra iniciativa para avanzar por sí mismo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lectura_previa_y_concentracion",
                        "texto": "Lee instrucciones y textos antes de responder, y mantiene la concentración de forma sostenida.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_escritura",
                "titulo": "Letras, estructura y comprensión",
                "peso": 0.45,
                "items": [
                    {
                        "id": "respuestas_bien_estructuradas",
                        "texto": "Escribe respuestas bien estructuradas, comprensibles y con buen control ortográfico para su nivel.",
                        "peso": 0.5,
                    },
                    {
                        "id": "responde_con_rapidez_razonable",
                        "texto": "Después de leer el texto y la pregunta, responde con rapidez razonable y escribe con soltura.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_oral",
                "titulo": "Lectura en voz alta",
                "peso": 0.25,
                "items": [
                    {
                        "id": "fluidez_alta",
                        "texto": "Lee en voz alta con fluidez alta para su nivel, manteniendo continuidad en pasajes más largos.",
                        "peso": 0.5,
                    },
                    {
                        "id": "pausas_entonacion_control",
                        "texto": "Controla pausas, ritmo y entonación de manera adecuada al leer en voz alta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },
    ("espanol", "M1"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía lectora",
                "peso": 0.30,
                "items": [
                    {
                        "id": "motivacion_trabajo",
                        "texto": "Está motivado para resolver la prueba y trabaja con autonomía razonable.",
                        "peso": 0.5,
                    },
                    {
                        "id": "lee_antes_de_responder",
                        "texto": "Lee instrucciones, textos y preguntas antes de responder, manteniendo la concentración durante la prueba.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_redaccion",
                "titulo": "Comprensión, ortografía y redacción",
                "peso": 0.45,
                "items": [
                    {
                        "id": "responde_con_buena_ortografia",
                        "texto": "Responde ejercicios de comprensión con ortografía adecuada y estructura clara.",
                        "peso": 0.5,
                    },
                    {
                        "id": "completa_respuestas_con_constancia",
                        "texto": "En ejercicios de respuesta escrita, demuestra constancia para completar sus respuestas de forma comprensible.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_estrategica",
                "titulo": "Comprensión con menor dependencia del texto",
                "peso": 0.25,
                "items": [
                    {
                        "id": "responde_sin_releer_exceso",
                        "texto": "Después de leer inicialmente el texto y la pregunta, puede responder sin tener que consultar el texto demasiadas veces.",
                        "peso": 0.5,
                    },
                    {
                        "id": "mantiene_hilo_lectura",
                        "texto": "Mantiene el hilo de la lectura y la comprensión sin perderse fácilmente entre texto y consigna.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "M2"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y autonomía en la prueba",
                "peso": 0.30,
                "items": [
                    {
                        "id": "trabaja_con_independencia",
                        "texto": "Trabaja con independencia y enfrenta la prueba con buena disposición.",
                        "peso": 0.5,
                    },
                    {
                        "id": "concentracion_sostenida",
                        "texto": "Lee instrucciones y textos antes de responder, y mantiene la concentración de manera sostenida.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_redaccion",
                "titulo": "Comprensión, ortografía y redacción",
                "peso": 0.45,
                "items": [
                    {
                        "id": "respuestas_precisas_y_claras",
                        "texto": "Responde ejercicios de comprensión con precisión razonable, buena ortografía y redacción clara.",
                        "peso": 0.5,
                    },
                    {
                        "id": "desarrolla_respuestas_completas",
                        "texto": "Cuando debe escribir respuestas completas, mantiene constancia y logra desarrollarlas con coherencia.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_estrategica",
                "titulo": "Comprensión con apoyo mínimo del texto",
                "peso": 0.25,
                "items": [
                    {
                        "id": "consulta_texto_con_eficiencia",
                        "texto": "Después de leer el texto y la pregunta, puede responder recurriendo al texto solo cuando es realmente necesario.",
                        "peso": 0.5,
                    },
                    {
                        "id": "relaciona_texto_y_pregunta",
                        "texto": "Relaciona adecuadamente la información del texto con lo que exige la pregunta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "M3"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y disciplina de lectura",
                "peso": 0.30,
                "items": [
                    {
                        "id": "autonomia_y_disposicion",
                        "texto": "Resuelve la prueba con autonomía y muestra disposición seria frente al trabajo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "atencion_en_textos_largos",
                        "texto": "Mantiene la concentración incluso en textos más largos o preguntas más exigentes.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_redaccion",
                "titulo": "Comprensión, ortografía y redacción",
                "peso": 0.45,
                "items": [
                    {
                        "id": "argumenta_con_claridad",
                        "texto": "Responde preguntas de comprensión con claridad, estructura adecuada y buen control ortográfico.",
                        "peso": 0.5,
                    },
                    {
                        "id": "constancia_en_respuestas_largas",
                        "texto": "Demuestra constancia al completar respuestas más largas, sin abandonar ideas a mitad del desarrollo.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_estrategica",
                "titulo": "Comprensión con menor relectura",
                "peso": 0.25,
                "items": [
                    {
                        "id": "responde_con_pocas_reconsultas",
                        "texto": "Después de una lectura inicial, puede responder con pocas reconsultas al texto.",
                        "peso": 0.5,
                    },
                    {
                        "id": "interpreta_consigna_y_texto",
                        "texto": "Integra adecuadamente lo que pide la consigna con la información relevante del texto.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },

    ("espanol", "H"): {
        "secciones": [
            {
                "id": "postura",
                "titulo": "Postura y madurez de trabajo",
                "peso": 0.30,
                "items": [
                    {
                        "id": "trabajo_autonomo_serio",
                        "texto": "Aborda la prueba con autonomía, seriedad y buena disposición para sostener el esfuerzo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "concentracion_en_lectura_compleja",
                        "texto": "Mantiene la concentración al trabajar con textos y preguntas de mayor complejidad.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "comprension_redaccion",
                "titulo": "Comprensión, ortografía y redacción",
                "peso": 0.45,
                "items": [
                    {
                        "id": "respuestas_completas_y_precisas",
                        "texto": "Responde ejercicios de comprensión con precisión, buena ortografía y redacción bien estructurada.",
                        "peso": 0.5,
                    },
                    {
                        "id": "desarrollo_sostenido_respuestas",
                        "texto": "En respuestas completas, demuestra constancia y desarrolla sus ideas de forma coherente hasta el final.",
                        "peso": 0.5,
                    },
                ],
            },
            {
                "id": "lectura_estrategica",
                "titulo": "Comprensión autónoma del texto",
                "peso": 0.25,
                "items": [
                    {
                        "id": "resuelve_con_minima_relectura",
                        "texto": "Después de leer inicialmente el texto y la pregunta, puede responder con mínima necesidad de releer varias veces.",
                        "peso": 0.5,
                    },
                    {
                        "id": "interpreta_y_sintetiza",
                        "texto": "Interpreta la consigna, identifica la información relevante y la sintetiza con eficacia en su respuesta.",
                        "peso": 0.5,
                    },
                ],
            },
        ],
    },
}



# Alias de compatibilidad:
# El resto del sistema usa H para este nivel de matemáticas.
if ("matematicas", "M4") in CUESTIONARIOS and ("matematicas", "H") not in CUESTIONARIOS:
    CUESTIONARIOS[("matematicas", "H")] = CUESTIONARIOS[("matematicas", "M4")]


# ──────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────


def obtener_cuestionario(subject: str, test_code: str) -> Dict[str, Any]:
    subject, test_code = _normalizar_subject_test_code(subject, test_code)

    key = (subject, test_code)
    if key not in CUESTIONARIOS:
        return _cuestionario_generico(subject, test_code)

    base = CUESTIONARIOS[key]
    return {
        "subject": subject,
        "test_code": test_code,
        "escala": ESCALA_1_5,
        "secciones": base["secciones"],
    }


def obtener_cuestionario_con_prefill(
    subject: str,
    test_code: str,
    prefills: Optional[Dict[str, Any]] = None,
    auto_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Retorna el cuestionario con prefills y flags automáticos.

    🔧 MEJORA: ahora aplica filtrado inteligente según:
    - ALWAYS_MANUAL (postura)
    - AUTO_CAPTURED (omitir si confianza >= umbral)
    - BAJA CONFIANZA (mostrar con sugerencia)
    - SIN MÉTRICA (mostrar siempre)
    """

    cuestionario = obtener_cuestionario(subject, test_code)

    prefills = prefills or {}
    auto_flags = auto_flags or []

    # ══════════════════════════════════════════════════════════════════
    # MAPEO: MÉTRICA DE VIDEO → ITEM_IDS
    # ══════════════════════════════════════════════════════════════════
    METRICA_A_ITEMS = {
        "pausas_largas": [
            "mantiene_ritmo", "sin_pausas_largas", "mantiene_concentracion",
            "concentracion", "mantiene_foco", "controla_tiempo",
            "planifica_tiempo", "no_abandona", "mantiene_constancia",
            "persistencia", "mantiene_esfuerzo", "trabaja_sin_distracciones",
        ],
        "ritmo_trabajo": [
            "mantiene_ritmo", "termina_tareas", "termina_con_calma",
            "tipo_ejercicio_lento", "organiza_trabajo", "fluidez_calculo",
            "responde_rapido", "responde_inmediato", "responde_con_agilidad",
            "estrategia_calculo",
        ],
        "num_reescrituras": [
            "organiza_trabajo", "calculo_mental", "mental_rapido",
            "escribe_respuesta_con_facilidad",
            "responde_con_rapidez_razonable",
            "fluidez_alta", "responde_con_facilidad",
            "escribe_con_mayor_fluidez", "detecta_patrones",
        ],
        "actividad_general": [
            "motivacion", "motivacion_independencia",
            "motivacion_autonomia", "motivacion_trabajo",
            "motivacion_constancia", "trabaja_con_autonomia",
            "trabaja_con_iniciativa", "trabaja_con_independencia",
            "trabajo_autonomo_serio", "autonomia_en_prueba",
            "organiza_trabajo", "asume_reto",
            "toma_iniciativa", "confianza_responder",
        ],
    }


    # Invertir el mapeo: item_id → métricas relacionadas
    ITEM_A_METRICAS = {}
    for metrica, items in METRICA_A_ITEMS.items():
        for item in items:
            ITEM_A_METRICAS.setdefault(item, []).append(metrica)


    UMBRAL_CONFIANZA = 0.65


    secciones_filtradas = []


    for seccion in cuestionario.get("secciones", []):
        seccion_id = seccion.get("id")
        items_filtrados = []


        for item in seccion.get("items", []):
            item_id = item.get("id")


            # ════════════════════════════════════════════════════════
            # PREFILL DIRECTO DEL ITEM
            # Si el orientador ya respondió este item, su valor final
            # tiene prioridad y el item nunca debe ocultarse.
            # ════════════════════════════════════════════════════════
            item_prefill = prefills.get(item_id)
            if item_prefill and isinstance(item_prefill, dict):
                confianza_item = float(item_prefill.get("confianza", 0.0))
                item = dict(item)  # evitar mutación del original
                item["prefill_valor"] = item_prefill.get("valor")
                item["prefill_fuente"] = item_prefill.get("fuente")
                item["prefill_confianza"] = confianza_item
                items_filtrados.append(item)
                continue


            # ════════════════════════════════════════════════════════
            # REGLA 1 — ALWAYS_MANUAL (postura)
            # ════════════════════════════════════════════════════════
            if seccion_id == "postura":
                items_filtrados.append(item)
                continue


            metricas = ITEM_A_METRICAS.get(item_id, [])


            # ════════════════════════════════════════════════════════
            # REGLA 4 — SIN MÉTRICA (mostrar siempre)
            # ════════════════════════════════════════════════════════
            if not metricas:
                items_filtrados.append(item)
                continue


            prefills_metricas = []
            for metrica in metricas:
                prefill_metrica = prefills.get(metrica)
                if prefill_metrica and isinstance(prefill_metrica, dict):
                    prefills_metricas.append((metrica, prefill_metrica))


            # ════════════════════════════════════════════════════════
            # REGLA 2 — AUTO_CAPTURED (omitir si TODAS las métricas
            # relacionadas fueron capturadas automáticamente con
            # confianza alta y la fuente final no es orientador)
            # ════════════════════════════════════════════════════════
            if prefills_metricas and len(prefills_metricas) == len(metricas):
                todas_auto_capturadas = True


                for metrica, prefill_metrica in prefills_metricas:
                    confianza = float(prefill_metrica.get("confianza", 0.0))
                    fuente = prefill_metrica.get("fuente")


                    if (
                        metrica not in auto_flags
                        or fuente == "orientador"
                        or confianza < UMBRAL_CONFIANZA
                    ):
                        todas_auto_capturadas = False
                        break


                if todas_auto_capturadas:
                    continue


            # ════════════════════════════════════════════════════════
            # REGLA 3 — BAJA CONFIANZA (mostrar con sugerencia)
            # Solo se prellena automáticamente cuando hay una sola
            # métrica asociada al item. Si hay varias, no se fuerza
            # una sugerencia ambigua.
            # ════════════════════════════════════════════════════════
            if len(prefills_metricas) == 1:
                _, prefill_metrica = prefills_metricas[0]
                confianza = float(prefill_metrica.get("confianza", 0.0))
                item = dict(item)  # evitar mutación del original
                item["prefill_valor"] = prefill_metrica.get("valor")
                item["prefill_fuente"] = prefill_metrica.get("fuente")
                item["prefill_confianza"] = confianza


            items_filtrados.append(item)


        if items_filtrados:
            nueva_seccion = dict(seccion)
            nueva_seccion["items"] = items_filtrados
            secciones_filtradas.append(nueva_seccion)


    cuestionario["secciones"] = secciones_filtradas


    # Metadata (se conserva igual)
    cuestionario["prefills"] = prefills
    cuestionario["auto_flags"] = auto_flags
    cuestionario["tiene_prefills"] = bool(prefills)


    return cuestionario

def calcular_puntaje_cualitativo(
    subject: str,
    test_code: str,
    respuestas: Dict[str, Any],
) -> Dict[str, Any]:
    cuestionario = obtener_cuestionario(subject, test_code)
    escala = cuestionario["escala"]
    min_v = escala["min"]
    max_v = escala["max"]

    respuestas_norm = _normalizar_respuestas_para_calculo(
        cuestionario=cuestionario,
        respuestas=respuestas,
    )

    secciones_out = []
    total = 0.0
    peso_total = 0.0

    for seccion in cuestionario["secciones"]:
        s_id = seccion["id"]
        s_peso = seccion.get("peso", 0)
        if s_peso <= 0:
            continue

        puntaje_sec, peso_sec, preguntas_resp = _calcular_seccion(
            seccion=seccion,
            respuestas_sec=respuestas_norm.get(s_id, {}),
            min_v=min_v,
            max_v=max_v,
        )
        if peso_sec == 0 or preguntas_resp == 0:
            continue

        etiqueta_sec = _clasificar(puntaje_sec)

        secciones_out.append(
            {
                "id": s_id,
                "nombre": seccion["titulo"],
                "puntaje": round(puntaje_sec, 1),
                "etiqueta": etiqueta_sec,
                "preguntas": preguntas_resp,
            }
        )

        total += puntaje_sec * s_peso
        peso_total += s_peso

    if not secciones_out:
        raise ValueError(
            f"No hay respuestas válidas para subject={subject} test_code={test_code}"
        )

    total_final = round(total / peso_total, 1) if peso_total > 0 else 0.0
    etiqueta_total = _clasificar(total_final)

    return {
        "total_porcentaje": total_final,
        "etiqueta_total": etiqueta_total,
        "secciones": secciones_out,
    }


# ──────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────


def _cuestionario_generico(subject: str, test_code: str) -> Dict[str, Any]:
    return {
        "subject": subject,
        "test_code": test_code,
        "escala": ESCALA_1_5,
        "secciones": [
            {
                "id": "habitos_estudio",
                "titulo": "Hábitos de estudio",
                "peso": 1.0,
                "items": [
                    {
                        "id": "concentracion",
                        "texto": "Se mantuvo concentrado durante la mayor parte del tiempo.",
                        "peso": 0.5,
                    },
                    {
                        "id": "autonomia",
                        "texto": "Trabajó de forma autónoma con poca ayuda del orientador.",
                        "peso": 0.5,
                    },
                ],
            }
        ],
    }


def _normalizar_subject_test_code(subject: str, test_code: str) -> tuple[str, str]:
    subject = (subject or "").strip().lower()
    test_code = (test_code or "").strip().upper()

    if subject == "matematicas" and test_code == "M4":
        test_code = "H"

    return subject, test_code


def _extraer_valor(raw: Any) -> Any:
    if isinstance(raw, dict) and "valor" in raw:
        return raw.get("valor")
    return raw


def _normalizar_respuestas_para_calculo(
    cuestionario: Dict[str, Any],
    respuestas: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    secciones = cuestionario.get("secciones", [])
    item_to_section: Dict[str, str] = {}
    normalizadas: Dict[str, Dict[str, Any]] = {}

    for seccion in secciones:
        s_id = seccion["id"]
        normalizadas[s_id] = {}
        for item in seccion.get("items", []):
            item_to_section[item["id"]] = s_id

    if not respuestas:
        return normalizadas

    for key, value in respuestas.items():
        if key in normalizadas and isinstance(value, dict):
            for item_id, item_val in value.items():
                if item_id in item_to_section and item_to_section[item_id] == key:
                    normalizadas[key][item_id] = _extraer_valor(item_val)
            continue

        if key in item_to_section:
            s_id = item_to_section[key]
            normalizadas[s_id][key] = _extraer_valor(value)

    return normalizadas


def _calcular_seccion(
    seccion: Dict[str, Any],
    respuestas_sec: Dict[str, Any],
    min_v: int,
    max_v: int,
):
    items = seccion.get("items", [])
    if not items:
        return 0.0, 0.0, 0

    acum = 0.0
    peso_total = 0.0
    preguntas_resp = 0

    for item in items:
        i_id = item["id"]
        i_peso = item.get("peso", 0)
        if i_peso <= 0:
            continue

        raw = respuestas_sec.get(i_id)
        if not isinstance(raw, (int, float)):
            continue

        val = max(min_v, min(max_v, float(raw)))
        pct = (val - min_v) / (max_v - min_v) * 100.0

        acum += pct * i_peso
        peso_total += i_peso
        preguntas_resp += 1

    if peso_total == 0:
        return 0.0, 0.0, 0

    return acum / peso_total, peso_total, preguntas_resp


def _clasificar(porcentaje: float) -> str:
    if porcentaje >= 76:
        return "fortaleza"
    elif porcentaje >= 51:
        return "en_desarrollo"
    elif porcentaje >= 26:
        return "refuerzo"
    else:
        return "atencion"
