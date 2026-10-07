from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.analytics.series import RunSeries, series_from_laps, series_from_track
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


def parse_file(suffix: str, content: bytes) -> tuple[RunSummary, RunSeries]:
    """Parse an uploaded file into its summary and the series the analytics use."""
    try:
        if suffix == ".gpx":
            track = parse_gpx(content)
            return summarize_track(track), series_from_track(track)
        laps = parse_csv(content)
        return summarize_laps(laps), series_from_laps(laps)
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc
