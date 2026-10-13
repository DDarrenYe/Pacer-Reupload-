"""Personal bests for the runner card: your fastest real times at the classic distances."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BestEffort, Run

TARGETS = {"5k": 5000.0, "10k": 10000.0, "Half marathon": 21097.5, "Marathon": 42195.0}
# A whole run counts for a distance if it's within 2% short (GPS often measures a real
# 10k race as 9.9-something km) to 5% long; its time is scaled to the exact distance at
# the run's average pace.
WHOLE_RUN_SHORT = 0.98
WHOLE_RUN_LONG = 1.05


@dataclass(frozen=True)
class PersonalBest:
    name: str
    distance_m: float
    time_s: float
    run_id: uuid.UUID
    started_at: datetime


def personal_bests(db: Session, user_id: uuid.UUID) -> list[PersonalBest]:
    """Only distances you've actually covered: no predictions, nothing extrapolated.

    GPX runs offer their best efforts (the fastest stretch of that length inside any run).
    Any run of about the right length also counts as a whole, which covers manual and CSV
    runs (no per-point data) and races GPS measured a little short.
    """
    best: dict[str, PersonalBest] = {}

    def offer(pb: PersonalBest) -> None:
        if pb.name not in best or pb.time_s < best[pb.name].time_s:
            best[pb.name] = pb

    efforts = db.execute(
        select(BestEffort.name, BestEffort.duration_s, Run.id, Run.started_at)
        .join(Run, Run.id == BestEffort.run_id)
        .where(Run.user_id == user_id, BestEffort.name.in_(TARGETS))
    )
    for name, duration, run_id, started in efforts:
        offer(PersonalBest(name, TARGETS[name], round(duration, 1), run_id, started))

    whole_runs = db.execute(
        select(Run.id, Run.started_at, Run.distance_m, Run.moving_time_s).where(
            Run.user_id == user_id
        )
    )
    for run_id, started, distance, moving in whole_runs:
        for name, target in TARGETS.items():
            if target * WHOLE_RUN_SHORT <= distance <= target * WHOLE_RUN_LONG:
                offer(
                    PersonalBest(
                        name, target, round(moving * target / distance, 1), run_id, started
                    )
                )

    return [best[name] for name in TARGETS if name in best]
