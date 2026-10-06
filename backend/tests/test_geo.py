import numpy as np
import pytest

from app.parsing.geo import haversine_m


def test_zero_distance():
    assert haversine_m(-36.85, 174.76, -36.85, 174.76) == 0


def test_one_degree_of_latitude():
    assert haversine_m(0, 0, 1, 0) == pytest.approx(111_195, rel=1e-4)


def test_known_city_pair():
    # Auckland -> Wellington, roughly 493 km
    assert haversine_m(-36.8485, 174.7633, -41.2865, 174.7762) / 1000 == pytest.approx(493, abs=2)


def test_vectorised():
    out = haversine_m(np.array([0, 0]), np.array([0, 0]), np.array([0, 1]), np.array([0, 0]))
    assert out.shape == (2,)
    assert out[0] == 0
