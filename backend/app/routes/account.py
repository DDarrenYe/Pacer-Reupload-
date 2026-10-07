import logging

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from app.auth import CurrentUserId, WritableUserId, is_demo_user
from app.db import DbSession
from app.models import Feedback, Run
from app.storage import StorageDep, StorageError
from app.supabase_admin import AdminDep, AdminError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["account"])


@router.get("/account")
def get_account(user_id: CurrentUserId, db: DbSession) -> dict:
    runs = db.scalar(select(func.count(Run.id)).where(Run.user_id == user_id))
    return {"run_count": runs, "is_demo": is_demo_user(user_id)}


@router.delete("/account", status_code=204)
def delete_account(
    user_id: WritableUserId, db: DbSession, storage: StorageDep, admin: AdminDep
) -> Response:
    """Delete everything: runs (with splits and best efforts), files, feedback, login."""
    runs = db.scalars(select(Run).where(Run.user_id == user_id)).all()
    for run in runs:
        if run.raw_file_key:
            try:
                storage.delete(run.raw_file_key)
            except StorageError:
                # The data rows still go; an orphaned private file is logged for cleanup.
                logger.error("Couldn't delete %s while deleting an account", run.raw_file_key)
        db.delete(run)
    db.execute(delete(Feedback).where(Feedback.user_id == user_id))
    db.commit()
    try:
        admin.delete_user(user_id)
    except AdminError as exc:
        logger.error("Data deleted but the login wasn't: %s", exc)
        raise HTTPException(502, "Your runs were deleted, but removing your login failed.") from exc
    return Response(status_code=204)


class FeedbackIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    page: str | None = Field(default=None, max_length=200)


@router.post("/feedback", status_code=201)
def send_feedback(body: FeedbackIn, user_id: CurrentUserId, db: DbSession) -> dict:
    """Send the developer a note. The demo account can send feedback too."""
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "Write a message first.")
    db.add(Feedback(user_id=user_id, message=message, page=body.page))
    db.commit()
    return {"ok": True}
