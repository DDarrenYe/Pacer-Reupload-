"""Score the three prediction methods on everyone's data and print a Markdown report.

    cd backend && python scripts/evaluate_model.py

Uses DATABASE_URL from backend/.env (your Supabase database). Prints only aggregate
numbers, no individual runs, so the output can go straight into docs/MODEL.md.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.analytics.data import load_efforts, load_volumes  # noqa: E402
from app.analytics.predict import evaluate  # noqa: E402
from app.db import get_engine  # noqa: E402
from app.models import Run  # noqa: E402


def main() -> None:
    with Session(get_engine()) as db:
        efforts, volumes = load_efforts(db), load_volumes(db)
        runners = db.scalar(select(func.count(func.distinct(Run.user_id))))
        runs = db.scalar(select(func.count(Run.id)))
        races = db.scalar(select(func.count(Run.id)).where(Run.is_race.is_(True)))
    result = evaluate(efforts, volumes)

    print(f"### Results ({datetime.now(UTC):%d %b %Y})\n")
    print(f"Data: {runners} runners, {runs} runs ({races} races), {len(efforts)} efforts.")
    print(
        f"Anchor→target pairs: {result.n_pairs} "
        f"(train {result.n_train}, test {result.n_test}, split by date).\n"
    )
    if not result.enough_data:
        print("Not enough data yet: the test set needs at least 3 pairs.")
        print("Upload more runs (GPX) and mark races, then run this again.")
        return

    print("| Method | Test pairs | MAE | MAPE |")
    print("|---|---|---|---|")
    for s in result.scores:
        mae = f"{s.mae_s:.0f} s" if s.mae_s is not None else "–"
        mape = f"{s.mape_pct:.2f}%" if s.mape_pct is not None else "–"
        print(f"| {s.method} | {s.n} | {mae} | {mape} |")

    if result.coefficients:
        print(f"\nPooled regression (`{result.formula}`), fitted on the training pairs:\n")
        print("| Term | Estimate | 95% CI |")
        print("|---|---|---|")
        for c in result.coefficients:
            print(
                f"| `{c['term']}` | {c['estimate']:.4f} | {c['ci_low']:.4f} to {c['ci_high']:.4f} |"
            )


if __name__ == "__main__":
    main()
