import math

import pytest

from app.parsing.errors import ParseError
from app.parsing.gpx_parser import parse_gpx, summarize_track


@pytest.fixture
def sample(data_dir):
    return parse_gpx((data_dir / "sample.gpx").read_bytes())


def test_columns(sample):
    assert list(sample.columns) == [
        "time",
        "lat",
        "lon",
        "ele",
        "hr",
        "dist_m",
        "cum_dist_m",
        "elapsed_s",
        "moving",
    ]
    assert sample["cum_dist_m"].is_monotonic_increasing
    assert sample["elapsed_s"].is_monotonic_increasing


def test_gps_spike_is_dropped(sample):
    # 451 running points + 30 pause points, minus the spike
    assert len(sample) == 480
    assert sample["dist_m"].max() < 20


def test_summary(sample):
    s = summarize_track(sample)
    assert s.distance_m == pytest.approx(3000, abs=1)
    assert s.elapsed_s == 960
    assert s.moving_time_s == 900
    assert s.avg_pace_s_per_km == pytest.approx(300, abs=0.5)
    assert s.elevation_gain_m == pytest.approx(9, abs=0.1)
    assert s.start_time.isoformat() == "2026-10-04T07:00:00+00:00"
    assert s.avg_hr == pytest.approx(149, abs=0.5)  # 140 -> 158 bpm, evenly


def test_pause_marked_not_moving(sample):
    assert (~sample["moving"]).sum() == 31  # first point + 30 paused points


def test_long_gap_is_a_pause():
    # The last point covers ~1.1 km in 290 s: a running speed, but after a watch pause
    gpx = _gpx([("07:00:00", 0.0), ("07:00:10", 0.0003), ("07:05:00", 0.0103)])
    df = parse_gpx(gpx)
    assert df["moving"].tolist() == [False, True, False]


def test_duplicate_timestamps_dropped():
    gpx = _gpx([("07:00:00", 0.0), ("07:00:00", 0.0), ("07:00:10", 0.0003)])
    assert len(parse_gpx(gpx)) == 2


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("this is not xml", "valid GPX"),
        ("<gpx version='1.1'><trk><trkseg></trkseg></trk></gpx>", "no track"),
    ],
)
def test_rejects_bad_files(content, message):
    with pytest.raises(ParseError, match=message):
        parse_gpx(content)


def test_no_heart_rate_is_none():
    gpx = _gpx([("07:00:00", 0.0), ("07:00:10", 0.0003)])
    assert summarize_track(parse_gpx(gpx)).avg_hr is None


def test_treadmill_hint_when_no_track():
    with pytest.raises(ParseError, match="CSV of laps"):
        parse_gpx("<gpx version='1.1'><trk><trkseg></trkseg></trk></gpx>")


def test_rejects_missing_timestamps(data_dir):
    with pytest.raises(ParseError, match="timestamps"):
        parse_gpx((data_dir / "no_time.gpx").read_bytes())


def test_rejects_backwards_time():
    with pytest.raises(ParseError, match="backwards"):
        parse_gpx(_gpx([("07:00:10", 0.0), ("07:00:00", 0.0003)]))


def _gpx(points):
    """Build a GPX string from (HH:MM:SS, lat offset) pairs."""
    pts = "".join(
        f'<trkpt lat="{-36.8 + dlat}" lon="174.7"><time>2026-10-04T{t}Z</time></trkpt>'
        for t, dlat in points
    )
    return f"<gpx version='1.1'><trk><trkseg>{pts}</trkseg></trk></gpx>"


def _noisy_track(points):
    """GPX from (seconds, metres north, metres east, elevation) samples."""
    deg = 1 / 111_195
    rows = "".join(
        f'<trkpt lat="{-36.8 + n * deg:.8f}" lon="{174.7 + e * deg / 0.8:.8f}"><ele>{ele:.2f}</ele>'
        f"<time>2026-10-04T07:{int(t) // 60:02d}:{int(t) % 60:02d}Z</time></trkpt>"
        for t, n, e, ele in points
    )
    return f"<gpx version='1.1'><trk><trkseg>{rows}</trkseg></trk></gpx>"


def _drift(n, sd, seed, phi=0.9):
    """GPS-like error: it wanders slowly (AR(1)), it doesn't jump independently each second."""
    import random

    rnd = random.Random(seed)
    innovation = sd * math.sqrt(1 - phi**2)
    x, out = 0.0, []
    for _ in range(n):
        x = phi * x + rnd.gauss(0, innovation)
        out.append(x)
    return out


def test_gps_wobble_does_not_inflate_distance():
    # 1 km due north at 3.33 m/s, one point a second, wandering about 2 m sideways
    n = 301
    north, east = _drift(n, 2.0, seed=1), _drift(n, 2.0, seed=2)
    pts = [(t, t * 1000 / 300 + north[t], east[t], 20.0) for t in range(n)]
    raw = sum(math.dist(a[1:3], b[1:3]) for a, b in zip(pts, pts[1:], strict=False))
    assert raw > 1015  # plain point-to-point summing is noticeably long
    s = summarize_track(parse_gpx(_noisy_track(pts)))
    assert abs(s.distance_m - 1000) < abs(raw - 1000) / 2  # at least halves the error
    assert s.distance_m == pytest.approx(1000, rel=0.02)


def test_standing_still_adds_almost_no_distance():
    north, east = _drift(120, 1.5, seed=3), _drift(120, 1.5, seed=4)
    pts = [(t, north[t], east[t], 20.0) for t in range(120)]
    pts += [(120 + t, north[-1] + t * 3.0, east[-1], 20.0) for t in range(1, 101)]
    s = summarize_track(parse_gpx(_noisy_track(pts)))
    assert s.distance_m == pytest.approx(300, abs=15)


def test_elevation_noise_is_not_climb():
    # Altimeter noise of about 0.25 m that drifts, like the readings in real exports
    noise = _drift(300, 0.25, seed=5)
    flat = [(t, t * 3.0, 0.0, 20 + noise[t]) for t in range(300)]
    raw_flat = sum(max(0, b[3] - a[3]) for a, b in zip(flat, flat[1:], strict=False))
    flat_gain = summarize_track(parse_gpx(_noisy_track(flat))).elevation_gain_m
    assert raw_flat > 10  # plain summing climbs a hill that isn't there
    assert flat_gain < raw_flat / 4  # the threshold removes most of it
    hill = [(t, t * 3.0, 0.0, 20 + min(t, 100) * 0.1 + noise[t]) for t in range(300)]
    gain = summarize_track(parse_gpx(_noisy_track(hill))).elevation_gain_m
    # The real 10 m climb is counted, plus the same small noise residue as on the flat
    assert 10 <= gain <= 10 + flat_gain + 0.5
