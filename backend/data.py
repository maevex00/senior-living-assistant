"""Adapt the existing spreadsheet schema; preserve unknown values explicitly."""

import json
import re
from pathlib import Path

import pandas as pd

from backend.models import Community, normalize_budget
from src.data_loader import load_demo_communities
from src.ranking import assign_priority


def optional_bool(value):
    value = str(value).strip().lower()
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    return None


def wait_months(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = str(value).strip().lower()
    if value in {"none", "no wait", "available", "available now", "0"}:
        return 0
    if re.fullmatch(r"\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\s*months?", value):
        return max(float(n) for n in re.findall(r"\d+(?:\.\d+)?", value))
    return None


class GeoResolver:
    def __init__(self, path=None):
        # Explicit local lookup: never download or guess a default location in a request.
        self.places = json.loads(Path(path or Path(__file__).parent / "fixtures/locations.json").read_text())

    def resolve(self, location):
        item = self.places.get(str(location).strip().lower())
        if item is None:
            return None
        lat, lon = map(float, item[:2])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon


def adapt_frame(frame: pd.DataFrame, geo: GeoResolver) -> list[Community]:
    required = {"CommunityID", "Type of Service", "Monthly Fee"}
    if not required.issubset(frame.columns):
        raise ValueError("Community data is missing required columns")
    result, seen = [], set()
    for row in frame.fillna("").to_dict("records"):
        community_id = str(row["CommunityID"]).strip()
        if not community_id or community_id in seen:
            raise ValueError("Community IDs must be nonempty and unique")
        seen.add(community_id)
        try:
            fee = normalize_budget(row["Monthly Fee"])
            if fee is not None and fee <= 0:
                fee = None
        except (ValueError, TypeError):
            fee = None
        services = str(row["Type of Service"])
        levels = [
            level
            for level in ("Assisted Living", "Independent Living", "Memory Care")
            if level.lower() in services.lower()
        ]
        zip_code = str(row.get("ZIP", "")).split(".")[0].zfill(5)
        coords = geo.resolve(zip_code)
        if (
            row.get("Latitude") != ""
            and row.get("Longitude") != ""
            and "Latitude" in row
            and "Longitude" in row
        ):
            lat, lon = float(row["Latitude"]), float(row["Longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Invalid community coordinates")
            coords = (lat, lon)
        result.append(
            Community(
                community_id=community_id,
                name=str(row.get("Community Name") or community_id),
                care_levels=levels,
                monthly_fee=fee,
                enhanced=optional_bool(row.get("Enhanced")),
                enriched=optional_bool(row.get("Enriched")),
                zip_code=zip_code,
                coordinates=coords,
                wait_months=wait_months(row.get("Est. Waitlist Length")),
                pet_friendly=optional_bool(row.get("Pet Friendly")),
                apartment_types=[
                    a.strip() for a in re.split(r"[,;|]", str(row.get("Apartment Type", ""))) if a.strip()
                ],
                business_tier=assign_priority(row),
            )
        )
    return result


def sheets_client(settings):
    import gspread
    from google.oauth2.service_account import Credentials

    info = json.loads(settings["GOOGLE_SERVICE_ACCOUNT_JSON"])
    credentials = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(credentials)
    client.set_timeout(15)
    return client


def load_communities(settings, geo):
    if settings["DEMO_MODE"]:
        frame = load_demo_communities()
    elif settings.get("COMMUNITIES_FILE"):
        path = Path(settings["COMMUNITIES_FILE"])
        frame = (
            pd.read_excel(path, dtype=str, keep_default_na=False)
            if path.suffix == ".xlsx"
            else pd.read_csv(path, dtype=str, keep_default_na=False)
        )
    else:
        sheet = sheets_client(settings).open_by_key(settings["COMMUNITIES_SHEET_ID"])
        frame = pd.DataFrame(
            sheet.worksheet(settings["COMMUNITIES_WORKSHEET"]).get_all_records(default_blank="")
        )
    return adapt_frame(frame, geo)
