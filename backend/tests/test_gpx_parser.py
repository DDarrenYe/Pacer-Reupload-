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
