from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Bulk certificate generation API with job tracking and per-recipient failure isolation.",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
