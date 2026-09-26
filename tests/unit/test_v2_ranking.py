import json
import random

import pandas as pd
import pytest
from pydantic import ValidationError

from backend.data import GeoResolver, adapt_frame, wait_months
from backend.models import ClientProfile, Community, completeness
from backend.ranking import exclusions, load_config, rank
from src.budget import regex_budget_fallback


def profile(**kwargs):
    return ClientProfile(
        **dict(
            {
                "care_level": "AL",
                "max_budget": 5000,
                "preferred_locations": ["14618"],
                "move_in_window": "Immediate",
            },
            **kwargs,
        )
    )


def community(key="A", **kwargs):
    return Community(
        **dict(
            {
                "community_id": key,
                "name": key,
                "care_levels": ["Assisted Living"],
                "monthly_fee": 3500,
                "coordinates": (43.1, -77.5),
                "wait_months": 0,
            },
            **kwargs,
        )
    )


def ranked(communities, p=None):
    return rank(p or profile(), communities, [(43.1, -77.5)], load_config())


@pytest.mark.parametrize("value", ["$4,500", "4500/month", "4.5k monthly", 4500])
def test_budget_normalization(value):
    assert profile(max_budget=value).max_budget == 4500


@pytest.mark.parametrize("value", [-1, 0, "NaN", float("inf"), "infinity"])
def test_invalid_budget_rejected(value):
    with pytest.raises(ValidationError):
        profile(max_budget=value)


@pytest.mark.parametrize("value", ["AL", "assisted", "assisted living"])
def test_care_alias(value):
    assert profile(care_level=value).care_level == "Assisted Living"


def test_required_intake_and_no_fabrication():
    empty = ClientProfile()
    assert len(completeness(empty)["missing_fields"]) == 3
    assert not ranked([community()], empty)["recommendations"]
    assert regex_budget_fallback("Budget is 4.5k monthly") == 4500
    assert regex_budget_fallback("78 years old, 2 children") is None


@pytest.mark.parametrize(
    "changes",
    [{"monthly_fee": 5001}, {"monthly_fee": None}, {"care_levels": ["Memory Care"]}, {"care_levels": []}],
)
def test_hard_filter(changes):
    assert not ranked([community(**changes)])["recommendations"]


def test_enhanced_care_implies_requirement():
    assert exclusions(profile(care_level="Enhanced Assisted Living"), community(enhanced=None))
    assert not exclusions(profile(care_level="Enhanced Assisted Living"), community(enhanced=True))
    assert exclusions(profile(enriched_required=True), community(enriched=False))


def test_budget_boundary_inclusive():
    assert ranked([community(monthly_fee=5000)])["eligible_count"] == 1


def test_distance_business_and_stable_ties():
    items = [
        community("far-contracted", coordinates=(44.1, -77.5), business_tier=1),
        community("near-other", business_tier=3),
    ]
    assert ranked(items)["recommendations"][0]["community_id"] == "near-other"
    equal = [
        community("Z", business_tier=1),
        community("A", business_tier=3),
        community("B", business_tier=1),
    ]
    assert [r["community_id"] for r in ranked(equal)["recommendations"]] == ["B", "Z", "A"]
    assert ranked(equal) == ranked(list(reversed(equal)))


def test_missing_data_does_not_boost_candidate():
    result = ranked([community("known"), community("unknown", coordinates=None, wait_months=None)])
    known, unknown = result["recommendations"]
    assert known["final_score"] > unknown["final_score"]
    assert unknown["score_breakdown"]["distance"]["score"] == 0
    assert known["active_weights"] == unknown["active_weights"]


def test_unsupported_preferences_not_scored():
    r = ranked([community()], profile(pet_required=True, apartment_preference="Studio"))["recommendations"][0]
    assert "pet_fit" not in r["active_weights"]
    assert "apartment_fit" not in r["active_weights"]


def test_preferences_and_availability():
    good = community("good", pet_friendly=True, apartment_types=["Studio"])
    bad = community("bad", pet_friendly=False, apartment_types=["2-Bedroom"], wait_months=6)
    r = ranked([bad, good], profile(pet_required=True, apartment_preference="Studio"))["recommendations"]
    assert r[0]["community_id"] == "good"
    assert r[1]["score_breakdown"]["availability"]["score"] == 0


def test_top_five_aggregation_bounds_and_reproducibility():
    rng = random.Random(42)
    rows = [community(str(i), monthly_fee=rng.randrange(2000, 6000)) for i in range(100)]
    first = ranked(rows)
    rng.shuffle(rows)
    assert first == ranked(rows)
    assert len(first["recommendations"]) == 5
    for r in first["recommendations"]:
        assert 0 <= r["final_score"] <= 100
        assert sum(r["active_weights"].values()) == pytest.approx(1)
        assert r["final_score"] == pytest.approx(
            sum(r["score_breakdown"][k]["score"] * w for k, w in r["active_weights"].items())
        )


@pytest.mark.parametrize("change", ["negative", "unknown", "sum", "business", "nan", "zero_care"])
def test_invalid_config(tmp_path, change):
    config = load_config()
    if change == "negative":
        config["weights"]["care_fit"] = -1
    if change == "unknown":
        config["weights"]["bogus"] = 0
    if change == "sum":
        config["weights"]["care_fit"] = 0.1
    if change == "business":
        config["business_policy"] = "highest_commission"
    if change == "nan":
        config["weights"]["care_fit"] = float("nan")
    if change == "zero_care":
        config["weights"].update(care_fit=0, affordability=0.5)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        load_config(path)


def test_data_unknowns_and_duplicate_ids():
    rows = pd.DataFrame(
        [
            {
                "CommunityID": "A",
                "Monthly Fee": "Call for price",
                "Type of Service": "Assisted Living",
                "Est. Waitlist Length": "",
                "Pet Friendly": "",
                "ZIP": "unknown",
            }
        ]
    )
    c = adapt_frame(rows, GeoResolver())[0]
    assert c.monthly_fee is c.wait_months is c.pet_friendly is c.coordinates is None
    with pytest.raises(ValueError):
        adapt_frame(pd.concat([rows, rows]), GeoResolver())
    assert wait_months("1-2 months") == 2
    assert wait_months("None") == 0
    assert wait_months("unknown") is None
