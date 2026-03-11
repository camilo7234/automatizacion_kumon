# ============================================================
# BLOQUE 1 — Imports principales de FastAPI
# ============================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config.settings import settings
from config.database import verificar_conexion
from app.routes.upload import router as upload_router
from app.routes.jobs import router as jobs_router

# ============================================================
# BLOQUE 2 — Instancia principal de la aplicación
# Metadata visible en /docs (Swagger) y /redoc
# ============================================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de procesamiento de tests Kumon — Módulo Processing",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================
# BLOQUE 3 — Middleware CORS
# Permite que el frontend React de tu compañero consuma la API
# En desarrollo acepta cualquier origen, en producción cambiar
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# BLOQUE 4 — Registro de routers
# Cada nuevo router se agrega aquí con include_router
# ============================================================
app.include_router(upload_router)
app.include_router(jobs_router)


# ============================================================
# BLOQUE 5 — Endpoint de diagnóstico /health
# Primer endpoint a probar — verifica que API + BD funcionan
# Tu compañero puede usar este endpoint para saber si tu
# módulo está activo antes de hacer llamadas reales
# ============================================================
@app.get("/health", tags=["diagnostico"])
async def health_check():
    """
    Verifica que la API y la conexión a PostgreSQL funcionan.
    Retorna estado de la aplicación.
    """
    db_ok = verificar_conexion()
    return {
        "status": "ok" if db_ok else "degraded",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "conectada" if db_ok else "error de conexión",
    }


# ============================================================
# BLOQUE 6 — Handler global de excepciones no controladas
# Evita que errores internos expongan stack traces al cliente
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "type": type(exc).__name__,
        },
    )


# ============================================================
# BLOQUE 7 — Punto de entrada para ejecutar con uvicorn
# Usar: python app/main.py  O  uvicorn app.main:app --reload
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
