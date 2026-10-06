from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.parsing.csv_parser import parse_csv, summarize_laps
from app.parsing.errors import ParseError
from app.parsing.gpx_parser import parse_gpx, summarize_track
from app.schemas.run import RunSummary

router = APIRouter(prefix="/uploads", tags=["uploads"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/parse", response_model=RunSummary)
async def parse_upload(file: UploadFile) -> RunSummary:
    """Parse a GPX or CSV file and return a run summary. Nothing is stored yet."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".gpx", ".csv"}:
        raise HTTPException(415, "Upload a .gpx or .csv file.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")

    try:
        if suffix == ".gpx":
            return summarize_track(parse_gpx(content))
        return summarize_laps(parse_csv(content))
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc
