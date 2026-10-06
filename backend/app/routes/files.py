from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.parsing.csv_parser import parse_csv, summarize_laps
from app.parsing.errors import ParseError
from app.parsing.gpx_parser import parse_gpx, summarize_track
from app.schemas.run import RunSummary

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CONTENT_TYPES = {".gpx": "application/gpx+xml", ".csv": "text/csv"}


def read_upload(file: UploadFile) -> tuple[str, bytes]:
    """Check the file type and size; return (suffix, content)."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in CONTENT_TYPES:
        raise HTTPException(415, "Upload a .gpx or .csv file.")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    return suffix, content


def summarize(suffix: str, content: bytes) -> RunSummary:
    try:
        if suffix == ".gpx":
            return summarize_track(parse_gpx(content))
        return summarize_laps(parse_csv(content))
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc
