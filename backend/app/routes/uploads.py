from fastapi import APIRouter, UploadFile

from app.routes.files import parse_file, read_upload
from app.schemas.run import RunSummary

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/parse", response_model=RunSummary)
def parse_upload(file: UploadFile) -> RunSummary:
    """Parse a GPX or CSV file and return a run summary. Nothing is saved."""
    summary, _ = parse_file(*read_upload(file))
    return summary
