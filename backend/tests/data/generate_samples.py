"""Regenerate the synthetic sample files used by the tests.

    cd backend && PYTHONPATH=. python tests/data/generate_samples.py

sample.gpx: 3 km due north at 5:00/km, one point every 2 s, with a 60 s
standing pause at 1.5 km and a single GPS spike ~900 m off course.
Expected: distance 3000 m, moving time 900 s, elapsed 960 s, gain 9 m.
Heart rate (Garmin extension) rises from 140 to 158 bpm while running.
"""

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.parsing.geo import EARTH_RADIUS_M

HERE = Path(__file__).parent
START = datetime(2026, 10, 4, 7, 0, 0, tzinfo=UTC)
LAT0, LON0 = -36.8485, 174.7633
STEP_S = 2
STEP_M = 3000 / 450  # 450 steps of 2 s at 3.333 m/s
DEG_PER_M = 180 / (math.pi * EARTH_RADIUS_M)


def sample_gpx() -> str:
    rows = []
    t, dist, ele, hr = START, 0.0, 20.0, 140.0

    def add(lat, lon):
        rows.append(
            f'      <trkpt lat="{lat:.7f}" lon="{lon:.7f}">'
            f"<ele>{ele:.2f}</ele><time>{t.strftime('%Y-%m-%dT%H:%M:%SZ')}</time>"
            f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{hr:.0f}</gpxtpx:hr>"
            "</gpxtpx:TrackPointExtension></extensions></trkpt>"
        )

    add(LAT0 + dist * DEG_PER_M, LON0)
    for step in range(1, 451):
        t += timedelta(seconds=STEP_S)
        dist += STEP_M
        ele += 0.02
        hr = 140 + step * 0.04
        lon = LON0 + (0.0113 if step == 200 else 0.0)  # GPS spike
        add(LAT0 + dist * DEG_PER_M, lon)
        if step == 225:  # stop at a crossing for 60 s
            for _ in range(30):
                t += timedelta(seconds=STEP_S)
                add(LAT0 + dist * DEG_PER_M, LON0)

    body = "\n".join(rows)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="run-analytics-tests" xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <trk>
    <name>Synthetic 3k</name>
    <trkseg>
{body}
    </trkseg>
  </trk>
</gpx>
"""


if __name__ == "__main__":
    (HERE / "sample.gpx").write_text(sample_gpx())
