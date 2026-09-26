"""Great-circle distance and radius bounding boxes. Pure Python: no database, no framework.

The bounding box is a cheap SQL prefilter (it can use the latitude/longitude index); the
exact haversine distance then decides what's actually inside the radius.
"""

import math

EARTH_RADIUS_MILES = 3958.8

# Widens the box by ~0.1 mm, so float rounding can never drop a point that lies exactly
# on the circle. The box only prefilters, so being slightly generous costs nothing.
_BOX_PADDING_DEGREES = 1e-9


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two points given in degrees."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    half_dphi = math.radians(lat2 - lat1) / 2
    half_dlambda = math.radians(lon2 - lon1) / 2
    a = math.sin(half_dphi) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(half_dlambda) ** 2
    # min() guards asin against a rounding error pushing `a` just above 1 (antipodes).
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lon: float, radius_miles: float) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lon, max_lon) enclosing every point within the radius.

    A degree of longitude shrinks with cos(latitude), so the box is wider in degrees of
    longitude than of latitude away from the equator. The longitude half-width uses
    asin(sin(d) / cos(lat)) rather than d / cos(lat): the circle's widest point in longitude
    sits slightly poleward of its center, and the simpler formula would clip it.

    Two edge cases fall back to the full longitude range (still correct, just less
    selective): a pole inside the circle, and a circle crossing the 180th meridian.
    """
    for name, value in (("latitude", lat), ("longitude", lon), ("radius", radius_miles)):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number, got {value}")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"invalid coordinates: {lat}, {lon}")
    if radius_miles <= 0:
        raise ValueError(f"radius must be positive, got {radius_miles}")

    angular = radius_miles / EARTH_RADIUS_MILES
    half_height = math.degrees(angular) + _BOX_PADDING_DEGREES
    min_lat, max_lat = lat - half_height, lat + half_height
    if min_lat <= -90 or max_lat >= 90:
        return max(min_lat, -90.0), min(max_lat, 90.0), -180.0, 180.0

    # min(): near the pole limit, rounding could push the ratio just above 1.
    ratio = min(1.0, math.sin(angular) / math.cos(math.radians(lat)))
    half_width = math.degrees(math.asin(ratio)) + _BOX_PADDING_DEGREES
    min_lon, max_lon = lon - half_width, lon + half_width
    if min_lon < -180 or max_lon > 180:
        return min_lat, max_lat, -180.0, 180.0
    return min_lat, max_lat, min_lon, max_lon
