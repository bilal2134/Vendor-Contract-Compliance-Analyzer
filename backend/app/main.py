from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ingestion import router as ingestion_router
from app.api.reports import router as reports_router
from app.core.database import init_db
from app.core.settings import get_settings
from app.services.storage import ensure_storage_dirs

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)

ensure_storage_dirs()
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.on_event("startup")
def startup() -> None:
    ensure_storage_dirs()
    init_db()


app.include_router(ingestion_router, prefix=settings.api_prefix)
app.include_router(reports_router, prefix=settings.api_prefix)
