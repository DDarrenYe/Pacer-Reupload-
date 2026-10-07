import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import load, predictions, runs, uploads
from app.storage import StorageError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Pacer API",
    description="Upload GPX or CSV runs and get splits, fatigue trends and race predictions.",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(uploads.router)
app.include_router(runs.router)
app.include_router(load.router)
app.include_router(predictions.router)


@app.exception_handler(StorageError)
def storage_error(request: Request, exc: StorageError) -> JSONResponse:
    logger.error("Storage error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "File storage is unavailable."})


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
