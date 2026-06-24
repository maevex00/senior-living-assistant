import functools
import pandas as pd
import pgeocode
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

_PGEO = pgeocode.Nominatim("us")


@functools.lru_cache(maxsize=512)
def coords_from_zip(zip_code: str) -> tuple | None:
    """Fast offline ZIP-to-coordinates lookup via pgeocode. Returns (lat, lon) or None."""
    try:
        row = _PGEO.query_postal_code(str(zip_code).zfill(5))
        if pd.notna(row.latitude) and pd.notna(row.longitude):
            return (float(row.latitude), float(row.longitude))
    except Exception:
        pass
    return None


@functools.lru_cache(maxsize=512)
def place_from_zip(zip_code: str) -> tuple:
    """Return (place_name, state_code) for a ZIP via pgeocode."""
    try:
        row = _PGEO.query_postal_code(str(zip_code).zfill(5))
        name = row.place_name if pd.notna(row.place_name) else None
        state = row.state_code if pd.notna(row.state_code) else None
        return (name, state)
    except Exception:
        return (None, None)


@functools.lru_cache(maxsize=64)
def coords_from_city(city_str: str) -> tuple | None:
    """Nominatim geocoding for city/state strings (used only for preferred locations)."""
    try:
        geo = Nominatim(user_agent="senior_living_app").geocode(city_str, timeout=5)
        if geo:
            return (float(geo.latitude), float(geo.longitude))
    except Exception:
        pass
    return None


def add_geodata(df: pd.DataFrame, preferred_locations: list) -> pd.DataFrame:
    """Attach Distance_miles, Town, State using pgeocode (no rate limits or API calls)."""
    ref_coords = [c for c in (coords_from_city(loc) for loc in preferred_locations) if c]
    if not ref_coords:
        ref_coords = [(43.1566, -77.6088)]  # Rochester, NY fallback

    zip_col = next((c for c in df.columns if "zip" in c.lower()), None)
    df = df.copy()

    if zip_col:
        zips = df[zip_col].astype(str).str.zfill(5)
        df["Community_Coords"] = zips.map(coords_from_zip)
        place_info = zips.map(place_from_zip)
        df["Town"] = place_info.map(lambda p: p[0])
        df["State"] = place_info.map(lambda p: p[1])
    else:
        df["Community_Coords"] = None
        df["Town"] = None
        df["State"] = None

    def min_dist(coord):
        if coord is None:
            return None
        try:
            return min(geodesic(coord, ref).miles for ref in ref_coords)
        except Exception:
            return None

    df["Distance_miles"] = df["Community_Coords"].apply(min_dist)
    df = df.sort_values(["Priority_Level", "Distance_miles"], na_position="last")
    df["Rank_Within_Priority"] = df.groupby("Priority_Level").cumcount() + 1
    return df
