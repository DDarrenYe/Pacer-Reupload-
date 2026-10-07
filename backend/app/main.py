import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import load, runs, uploads
from app.storage import StorageError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Run Analytics API",
    description="Upload GPX or CSV runs and get splits, fatigue trends and race predictions.",
    version="0.3.0",
)

app.include_router(uploads.router)
app.include_router(runs.router)
app.include_router(load.router)


@app.exception_handler(StorageError)
def storage_error(request: Request, exc: StorageError) -> JSONResponse:
    logger.error("Storage error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "File storage is unavailable."})


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
