from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from configs.settings import get_settings
from configs.logging_config import setup_logging
from backend.api.routes import router

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan manager handling startup and shutdown events cleanly.
    """
    logger = setup_logging(settings.LOG_LEVEL, settings.LOG_FILE)
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    version=settings.VERSION,
    description="IntelliWatch: AI-Powered Scene Understanding for Industrial Safety & Monitoring",
    lifespan=lifespan,
)

# Enable CORS for cross-origin dashboard communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)

# Mount static frontend assets if directory exists
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/", tags=["Dashboard"])
@app.get("/dashboard", tags=["Dashboard"])
async def serve_dashboard():
    """
    Serves the operator dashboard single-page interface.
    """
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "ok", "project": settings.PROJECT_NAME, "message": "Dashboard frontend ready"}
