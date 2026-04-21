# app/main.py
import logging


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # 🔥 NUEVO


from app.routes import upload, jobs, results, cuestionario
from app.services.ocr_service import initialize_ocr_reader



logger = logging.getLogger(__name__)



app = FastAPI(
    title="automatizacion_kumon",
    version="0.1.0",
)


# 🔥 ================================
# 🔥 CORS (SOLUCIÓN DEL PROBLEMA)
# 🔥 ================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "null",               # ← file:// abierto directamente en el navegador
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 🔥 ================================



@app.on_event("startup")
async def startup_event() -> None:
    """
    Inicializa servicios globales una sola vez al arrancar la app.
    """
    logger.info("Iniciando aplicación...")
    initialize_ocr_reader()
    logger.info("Startup completado. EasyOCR listo.")



# OJO: sin prefix adicional aquí
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(results.router)
app.include_router(cuestionario.router)