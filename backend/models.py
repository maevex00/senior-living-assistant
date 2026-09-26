"""The shared intake contract. Missing facts stay missing in all four input modes."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CareLevel = Literal["Independent Living", "Assisted Living", "Enhanced Assisted Living", "Memory Care"]


def normalize_budget(value):
    if value is None or value == "":
        return None
    if isinstance(value, str):
        match = re.fullmatch(
            r"\s*\$?([\d,]+(?:\.\d+)?)\s*(k)?\s*(?:/month|monthly|per month)?\s*", value, re.I
        )
        if not match:
            raise ValueError("Enter a monthly dollar amount")
        return float(match[1].replace(",", "")) * (1000 if match[2] else 1)
    return value


class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    patient_name: str | None = Field(default=None, max_length=200)
    age: int | None = Field(default=None, ge=0, le=120)
    care_level: CareLevel | None = None
    max_budget: float | None = Field(default=None, gt=0, le=1000000)
    preferred_locations: list[str] = Field(default_factory=list, max_length=20)
    enhanced_required: bool = False
    enriched_required: bool = False
    move_in_window: Literal["Immediate", "Near-term", "Flexible"] | None = None
    pet_required: bool | None = None
    apartment_preference: str | None = Field(default=None, max_length=100)
    mobility_needs: list[str] = Field(default_factory=list, max_length=20)
    other_preferences: list[str] = Field(default_factory=list, max_length=20)
    primary_contact_name: str | None = Field(default=None, max_length=200)
    primary_contact_phone: str | None = Field(default=None, max_length=100)
    primary_contact_email: str | None = Field(default=None, max_length=320)

    @field_validator("max_budget", mode="before")
    @classmethod
    def budget(cls, value):
        return normalize_budget(value)

    @field_validator("care_level", mode="before")
    @classmethod
    def care(cls, value):
        if not value:
            return None
        aliases = {
            "al": "Assisted Living",
            "assisted": "Assisted Living",
            "il": "Independent Living",
            "independent": "Independent Living",
            "memory": "Memory Care",
            "dementia": "Memory Care",
            "enhanced": "Enhanced Assisted Living",
        }
        return aliases.get(str(value).strip().lower(), str(value).strip().title())

    @field_validator("preferred_locations", "mobility_needs", "other_preferences")
    @classmethod
    def clean_list(cls, value):
        if any(len(item) > 300 for item in value):
            raise ValueError("Entries must be at most 300 characters")
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


QUESTIONS = {
    "care_level": "What level of care has the resident or their care team requested?",
    "max_budget": "What is the maximum monthly budget?",
    "preferred_locations": "Which cities or ZIP codes would you prefer?",
    "move_in_window": "How soon does the resident need to move?",
}


def completeness(profile: ClientProfile) -> dict:
    missing = [
        key for key in ("care_level", "max_budget", "preferred_locations") if not getattr(profile, key)
    ]
    encouraged = [] if profile.move_in_window else ["move_in_window"]
    return {
        "is_complete": not missing,
        "missing_fields": missing,
        "suggested_questions": [QUESTIONS[key] for key in missing + encouraged],
    }


class Community(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    community_id: str
    name: str
    care_levels: list[str]
    monthly_fee: float | None = Field(default=None, gt=0)
    enhanced: bool | None = None
    enriched: bool | None = None
    zip_code: str | None = None
    coordinates: tuple[float, float] | None = None
    wait_months: float | None = Field(default=None, ge=0)
    pet_friendly: bool | None = None
    apartment_types: list[str] = Field(default_factory=list)
    business_tier: int = Field(default=3, ge=1, le=3)


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: ClientProfile
    input_mode: Literal["manual", "text", "audio", "live", "demo"] = "manual"


class CRMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receipt: str = Field(max_length=50000)
    selected_community_ids: list[str] = Field(default_factory=list, max_length=5)
    advisor_notes: str = Field(default="", max_length=5000)
