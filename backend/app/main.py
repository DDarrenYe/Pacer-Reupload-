from fastapi import FastAPI

from app.routes import uploads

app = FastAPI(
    title="Run Analytics API",
    description="Upload GPX or CSV runs and get splits, fatigue trends and race predictions.",
    version="0.1.0",
)

app.include_router(uploads.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
