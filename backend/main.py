from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.health import router as health_router
from app.api.upload import router as upload_router
from app.api.ocr import router as ocr_router
from app.api.extract import router as extract_router
from app.api.compliance import router as compliance_router
from app.api.history import router as history_router
from app.api.inspections import router as inspections_router
from app.db.session import init_db

# Initialize SQLite Database tables on startup
init_db()

# Initialize the FastAPI Application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for Legal Metrology (Packaged Commodities) Rules, 2011 Compliance System",
    version=settings.VERSION,
    docs_url="/docs",      # Interactive Swagger UI documentation
    redoc_url="/redoc"     # ReDoc documentation alternative
)

# Ensure uploads directory exists and mount it for static viewing
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")

# Enable CORS (Cross-Origin Resource Sharing)
# This allows our React frontend to talk to this backend server smoothly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(upload_router, prefix=settings.API_V1_STR)
app.include_router(ocr_router, prefix=settings.API_V1_STR)
app.include_router(extract_router, prefix=settings.API_V1_STR)
app.include_router(compliance_router, prefix=settings.API_V1_STR)
app.include_router(history_router, prefix=settings.API_V1_STR)
app.include_router(inspections_router)

@app.get("/", tags=["Root"])
def root():
    """
    Root landing endpoint that greets the user and points to /docs.
    """
    return {
        "message": f"Welcome to the {settings.PROJECT_NAME} API!",
        "documentation": "/docs",
        "health_check": f"{settings.API_V1_STR}/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
