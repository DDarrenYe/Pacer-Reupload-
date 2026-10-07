"""Fill the read-only demo account with ~16 weeks of realistic synthetic runs.

    cd backend && python scripts/seed_demo.py

Uses backend/.env (your Supabase database and storage). It goes through the real upload
code, so parsing, analytics and storage are exactly what users get. Running it again
replaces the demo's runs. The runs are synthetic: no real person's route or data.
"""

import math
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import get_current_user_id, get_writable_user_id  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.parsing.geo import EARTH_RADIUS_M  # noqa: E402

DEG = 180 / (math.pi * EARTH_RADIUS_M)
EXPONENT, FIVE_K_S = 1.07, 1290  # the demo runner: about a 21:30 5k, getting fitter


def gpx(
    start: datetime, dist_m: float, total_s: float, rnd: random.Random, trend: float = 0.0
) -> str:
    """A run along a gently curving synthetic route with heart rate.

    trend > 0 speeds up through the run (negative split), < 0 fades (positive split).
    """
    n = int(total_s / 2)
    # Speed at each 2 s step: a gentle trend plus noise, scaled so the total distance holds.
    speeds = [1 + trend * (i / n - 0.5) + rnd.uniform(-0.03, 0.03) for i in range(n)]
    scale = dist_m / sum(speeds)
    lat, lon, heading, pts = -36.85, 174.76, rnd.uniform(0, 6.28), []
    for i in range(n + 1):
        t = start + timedelta(seconds=2 * i)
        hr = 132 + 35 * (i / n) ** 0.7 + rnd.uniform(-2, 2)
        ele = 20 + 12 * math.sin(i / 90)
        pts.append(
            f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}"><ele>{ele:.1f}</ele>'
            f"<time>{t:%Y-%m-%dT%H:%M:%SZ}</time><extensions><gpxtpx:TrackPointExtension>"
            f"<gpxtpx:hr>{hr:.0f}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions></trkpt>"
        )
        step = speeds[i - 1] * scale if i else 0.0
        heading += rnd.uniform(-0.05, 0.05)
        lat += step * math.cos(heading) * DEG
        lon += step * math.sin(heading) * DEG / math.cos(math.radians(lat))
    return (
        '<?xml version="1.0"?><gpx version="1.1" creator="pacer-demo" '
        'xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">'
        "<trk><trkseg>" + "".join(pts) + "</trkseg></trk></gpx>"
    )


def main() -> None:
    demo_id = uuid.UUID(get_settings().demo_user_id)
    # Act as the demo user. The read-only guard is for visitors; this script runs with
    # your server credentials, so it's allowed to write the demo's data.
    app.dependency_overrides[get_current_user_id] = lambda: demo_id
    app.dependency_overrides[get_writable_user_id] = lambda: demo_id
    client = TestClient(app)

    for run in client.get("/runs").json():
        client.delete(f"/runs/{run['id']}")

    rnd = random.Random(42)
    today = datetime.now(UTC).replace(hour=6, minute=30, second=0, microsecond=0)
    uploaded = 0
    for w in range(16, 0, -1):
        fitness = FIVE_K_S * (1 - 0.05 * (16 - w) / 16)
        monday = today - timedelta(days=today.weekday(), weeks=w - 1)
        # (day, distance, effort factor, race?, name, pace trend)
        week = [
            (1, rnd.choice([6000, 7000, 8000]), 1.22, False, "Easy run", rnd.uniform(-0.02, 0.02)),
            (3, 5000, 1.03 if w % 2 else 1.14, False, "Tempo 5k" if w % 2 else "Steady 5k", 0.05),
            (6, rnd.choice([12000, 14000, 16000]), 1.26, False, "Long run", -0.07),
        ]
        if w % 4 == 0:
            dist = rnd.choice([5000, 10000])
            name = "5k parkrun" if dist == 5000 else "10k race"
            week[1] = (5, dist, 1.0, True, name, rnd.uniform(-0.04, 0.04))
        for offset, dist, factor, race, name, trend in week:
            day = monday + timedelta(days=offset)
            if day > today:
                continue
            secs = fitness * (dist / 5000) ** EXPONENT * factor
            r = client.post(
                "/runs",
                files={"file": (f"demo-{day:%Y%m%d}.gpx", gpx(day, dist, secs, rnd, trend))},
                data={"is_race": str(race).lower(), "name": name},
            )
            r.raise_for_status()
            uploaded += 1

    # One treadmill session entered by hand, like a runner without a watch.
    client.post(
        "/runs/manual",
        json={
            "distance_km": 6.4,
            "duration_s": 2280,
            "started_at": (today - timedelta(days=2)).isoformat(),
            "name": "Treadmill (entered manually)",
        },
    ).raise_for_status()
    print(f"Demo account ready: {uploaded + 1} runs for user {demo_id}.")


if __name__ == "__main__":
    main()
