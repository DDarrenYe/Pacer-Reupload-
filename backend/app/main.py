import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import account, demo, load, predictions, runs, uploads
from app.storage import StorageError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Pacer API",
    description="Upload GPX or CSV runs and get splits, fatigue trends and race predictions.",
    version="0.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(uploads.router)
app.include_router(runs.router)
app.include_router(load.router)
app.include_router(predictions.router)
app.include_router(account.router)
app.include_router(demo.router)


@app.exception_handler(StorageError)
def storage_error(request: Request, exc: StorageError) -> JSONResponse:
    logger.error("Storage error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "File storage is unavailable."})


@app.exception_handler(Exception)
def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Log the details for us; never send a stack trace to the browser.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side."})


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
