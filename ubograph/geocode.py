"""Free, keyless address geocoding for the satellite-view panel on an address
entity's report.

Uses OpenStreetMap's Nominatim (geocoding) and Esri's World Imagery service
(satellite tiles) — both free, both requiring no API key, no billing account,
and no secret to configure. Good enough for "is this a real building or a
brass-plate address", not for anything requiring survey-grade accuracy.
"""
from functools import lru_cache
from typing import Optional

import requests

import config

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent identifying the
# application, and caps unregistered use at roughly one request per second —
# both honoured here. Not for bulk/automated lookups.
USER_AGENT = "UBOgraph/1.0 (beneficial-ownership due-diligence tool)"

SATELLITE_DELTA = 0.0015  # ~166m at the equator: close enough to see one building


class GeocodeError(Exception):
    pass


@lru_cache(maxsize=256)
def geocode(address: str) -> Optional[dict]:
    """Best-effort forward geocode of a free-text address. None when nothing
    matched or no address was given; raises GeocodeError on a network/service
    failure so the caller can show it rather than silently guess."""
    address = (address or "").strip()
    if not address:
        return None
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=config.HTTP_TIMEOUT,
        )
    except requests.RequestException:
        raise GeocodeError("Could not reach the geocoding service — try again shortly.")
    if not response.ok:
        raise GeocodeError(f"Nominatim lookup failed: {response.status_code}")
    results = response.json() or []
    if not results:
        return None
    top = results[0]
    return {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "display_name": top.get("display_name") or address,
    }


def satellite_image_url(lat: float, lon: float, size: int = 500) -> str:
    """A static satellite PNG centred on lat/lon — Esri's World Imagery
    export endpoint, no key required."""
    d = SATELLITE_DELTA
    bbox = f"{lon - d},{lat - d},{lon + d},{lat + d}"
    return (
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
        f"MapServer/export?bbox={bbox}&bboxSR=4326&imageSR=4326"
        f"&size={size},{size}&format=png&f=image"
    )


def osm_url(lat: float, lon: float) -> str:
    """A link to the same point on the full interactive OpenStreetMap, for
    panning/zooming beyond the static image."""
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
