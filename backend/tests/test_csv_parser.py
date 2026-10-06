import math

import pytest

from app.parsing.csv_parser import parse_csv, summarize_laps
from app.parsing.errors import ParseError


def test_treadmill_laps(data_dir):
    df = parse_csv((data_dir / "treadmill.csv").read_bytes())
    assert df["distance_m"].tolist() == [1000.0] * 5
    assert df["duration_s"].tolist() == [300, 295, 290, 285, 280]
    assert df["avg_hr"].iloc[0] == 142
    assert math.isnan(df["avg_hr"].iloc[-1])
    assert df["cum_dist_m"].iloc[-1] == 5000

    s = summarize_laps(df)
    assert s.distance_m == 5000
    assert s.moving_time_s == 1450
    assert s.avg_pace_s_per_km == 290


@pytest.mark.parametrize(
    ("header", "value", "expected_m"),
    [
        ("distance_m", "400", 400),
        ("distance", "400", 400),  # > 50, so metres
        ("distance", "1.5", 1500),  # <= 50, so km
        ("miles", "1", 1609.344),
        ("Distance KM", "2", 2000),
    ],
)
def test_distance_units(header, value, expected_m):
    df = parse_csv(f"{header},time\n{value},60\n")
    assert df["distance_m"].iloc[0] == pytest.approx(expected_m)


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("90", 90), ("1:30", 90), ("1:00:00", 3600), ("4:05.5", 245.5)],
)
def test_time_formats(value, seconds):
    df = parse_csv(f"distance_m,duration\n1000,{value}\n")
    assert df["duration_s"].iloc[0] == seconds


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "valid CSV"),
        ("distance_m,time\n", "no rows"),
        ("pace,hr\n5:00,150\n", "missing a distance and time column"),
        ("distance_m,notes\n1000,easy\n", "missing a time column"),
        ("distance_m,time\n1000,5:00\nabc,5:00\n", "row 3"),
        ("distance_m,time\n1000,five minutes\n", "Couldn't read time"),
        ("distance_m,time\n1000,0\n", "greater than zero"),
        ("distance_m,time\n-400,90\n", "greater than zero"),
    ],
)
def test_rejects_bad_files(content, message):
    with pytest.raises(ParseError, match=message):
        parse_csv(content)
