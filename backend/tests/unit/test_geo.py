import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.services.geo import EARTH_RADIUS_MILES, bounding_box, haversine_miles

NYC = (40.7128, -74.0060)
PHILADELPHIA = (39.9526, -75.1652)

finite = {"allow_nan": False, "allow_infinity": False}


def _destination(lat: float, lon: float, bearing: float, miles: float) -> tuple[float, float]:
    """The point `miles` from (lat, lon) along `bearing` radians, on the same sphere."""
    d = miles / EARTH_RADIUS_MILES
    phi1, lambda1 = math.radians(lat), math.radians(lon)
    phi2 = math.asin(
        math.sin(phi1) * math.cos(d) + math.cos(phi1) * math.sin(d) * math.cos(bearing)
    )
    lambda2 = lambda1 + math.atan2(
        math.sin(bearing) * math.sin(d) * math.cos(phi1),
        math.cos(d) - math.sin(phi1) * math.sin(phi2),
    )
    # Wrap into [-180, 180).
    return math.degrees(phi2), (math.degrees(lambda2) + 540) % 360 - 180


def test_haversine_nyc_to_philadelphia() -> None:
    assert haversine_miles(*NYC, *PHILADELPHIA) == pytest.approx(80.6, abs=1)


def test_haversine_is_zero_for_same_point_and_symmetric() -> None:
    assert haversine_miles(*NYC, *NYC) == 0
    assert haversine_miles(*NYC, *PHILADELPHIA) == haversine_miles(*PHILADELPHIA, *NYC)


def test_bounding_box_widens_in_longitude_away_from_equator() -> None:
    min_lat, max_lat, min_lon, max_lon = bounding_box(*NYC, 25)

    half_height = (max_lat - min_lat) / 2
    half_width = (max_lon - min_lon) / 2
    # 25 miles is ~0.362 degrees of latitude; at 40.7 N a degree of longitude is ~0.758 as long.
    assert half_height == pytest.approx(0.3618, abs=1e-3)
    assert half_width == pytest.approx(0.3618 / math.cos(math.radians(NYC[0])), abs=1e-3)


def test_bounding_box_near_pole_or_antimeridian_spans_all_longitudes() -> None:
    assert bounding_box(89.9, 10, 50)[2:] == (-180.0, 180.0)
    assert bounding_box(0, 179.9, 50)[2:] == (-180.0, 180.0)


@pytest.mark.parametrize(
    "args", [(math.nan, 0, 10), (0, math.inf, 10), (91, 0, 10), (0, 181, 10), (0, 0, 0)]
)
def test_bounding_box_rejects_invalid_input(args: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError):
        bounding_box(*args)


@given(
    lat=st.floats(min_value=-90, max_value=90, **finite),
    lon=st.floats(min_value=-180, max_value=180, **finite),
    radius=st.floats(min_value=0.1, max_value=1000, **finite),
    bearing=st.floats(min_value=0, max_value=2 * math.pi, **finite),
    fraction=st.floats(min_value=0, max_value=1, **finite),
)
def test_every_point_within_radius_is_inside_bounding_box(
    lat: float, lon: float, radius: float, bearing: float, fraction: float
) -> None:
    point_lat, point_lon = _destination(lat, lon, bearing, radius * fraction)
    # The search keeps points by haversine distance, so that's the definition to honor.
    assume(haversine_miles(lat, lon, point_lat, point_lon) <= radius)

    min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius)

    assert min_lat <= point_lat <= max_lat
    assert min_lon <= point_lon <= max_lon
