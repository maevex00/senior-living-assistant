"""Pure, reproducible scoring: no AI, I/O, clocks or mutable global state."""

import json
import math
from pathlib import Path

from geopy.distance import geodesic

from backend.models import ClientProfile, Community, completeness

DIMENSIONS = {
    "care_fit",
    "affordability",
    "distance",
    "availability",
    "enhanced_enriched",
    "pet_fit",
    "apartment_fit",
}


def load_config(path=None):
    config = json.loads(Path(path or Path(__file__).parent / "config/ranking.json").read_text())
    weights = config["weights"]
    if set(weights) != DIMENSIONS or any(not math.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError("Ranking weights must be finite, nonnegative and use the documented dimensions")
    if not math.isclose(sum(weights.values()), 1, abs_tol=1e-6):
        raise ValueError("Ranking weights must sum to one")
    if weights["care_fit"] <= 0 or weights["affordability"] <= 0:
        raise ValueError("Care and affordability must have positive weights")
    if not math.isfinite(config["distance_limit_miles"]) or config["distance_limit_miles"] <= 0:
        raise ValueError("Distance limit must be positive")
    if config["business_policy"] != "tie_break_only":
        raise ValueError("Business value may only break suitability ties")
    return config


def exclusions(profile: ClientProfile, c: Community) -> list[str]:
    reasons = []
    care = "Assisted Living" if profile.care_level == "Enhanced Assisted Living" else profile.care_level
    if care not in c.care_levels:
        reasons.append("Requested care level is not confirmed.")
    if (
        profile.enhanced_required or profile.care_level == "Enhanced Assisted Living"
    ) and c.enhanced is not True:
        reasons.append("Required enhanced care is not confirmed.")
    if profile.enriched_required and c.enriched is not True:
        reasons.append("Required enriched care is not confirmed.")
    if c.monthly_fee is None:
        reasons.append("Monthly price is unknown; budget eligibility cannot be confirmed.")
    elif profile.max_budget is not None and c.monthly_fee > profile.max_budget:
        reasons.append("Monthly fee exceeds the maximum budget.")
    return reasons


def score_dimensions(profile, c, refs, config):
    dims = {}

    def add(name, score, reason, **evidence):
        dims[name] = {"score": round(max(0, min(100, score)), 6), "reason": reason, "evidence": evidence}

    add("care_fit", 100, f"Confirmed support for {profile.care_level}.", care_levels=c.care_levels)
    ratio = c.monthly_fee / profile.max_budget
    add(
        "affordability",
        60 + 40 * min(1, (1 - ratio) / 0.3),
        f"${c.monthly_fee:,.0f}/month within ${profile.max_budget:,.0f} ceiling; base fee only.",
        monthly_fee=c.monthly_fee,
        budget=profile.max_budget,
    )
    if refs and c.coordinates:
        distance = min(geodesic(c.coordinates, ref).miles for ref in refs)
        add(
            "distance",
            100 * (1 - distance / config["distance_limit_miles"]),
            f"{distance:.1f} straight-line miles from nearest resolved preferred area.",
            miles=round(distance, 3),
        )
    if c.wait_months is not None and profile.move_in_window:
        allowance = {"Immediate": 0, "Near-term": 3, "Flexible": 6}[profile.move_in_window]
        add(
            "availability",
            100 - max(0, c.wait_months - allowance) * 25,
            f"Estimated wait {c.wait_months:g} months for {profile.move_in_window.lower()} move; confirm with community.",
            wait_months=c.wait_months,
        )
    required = [
        c.enhanced
        for _ in [0]
        if profile.enhanced_required or profile.care_level == "Enhanced Assisted Living"
    ]
    required += [c.enriched for _ in [0] if profile.enriched_required]
    if required:
        add("enhanced_enriched", 100, "All required enhanced/enriched services are confirmed.")
    if profile.pet_required is True and c.pet_friendly is not None:
        add(
            "pet_fit",
            100 if c.pet_friendly else 0,
            "Pets allowed."
            if c.pet_friendly
            else "Pet policy conflicts with preference; advisor must resolve.",
        )
    if profile.apartment_preference and c.apartment_types:
        matched = profile.apartment_preference.lower() in [a.lower() for a in c.apartment_types]
        add(
            "apartment_fit",
            100 if matched else 0,
            "Preferred apartment listed." if matched else "Preferred apartment not listed.",
            apartment_types=c.apartment_types,
        )
    return dims


def filter_communities(profile: ClientProfile, communities: list[Community]) -> tuple[list, list]:
    eligible, excluded = [], []
    if not completeness(profile)["is_complete"]:
        return eligible, excluded
    for community in communities:
        blocked = exclusions(profile, community)
        if blocked:
            excluded.append({"community_id": community.community_id, "reasons": blocked})
        else:
            eligible.append(community)
    return eligible, sorted(excluded, key=lambda item: item["community_id"])


def rank(
    profile: ClientProfile, communities: list[Community], refs: list[tuple], config: dict, *, prepared=None
) -> dict:
    intake = completeness(profile)
    base = {
        "recommendations": [],
        "exclusions": [],
        "intake": intake,
        "total_communities": len(communities),
        "eligible_count": 0,
        "ranking_version": config["version"],
        "configured_weights": config["weights"],
        "business_policy": config["business_policy"],
    }
    if not intake["is_complete"]:
        return base
    eligible, excluded = prepared if prepared is not None else filter_communities(profile, communities)
    base["exclusions"] = excluded
    candidates = [(c, score_dimensions(profile, c, refs, config)) for c in eligible]
    # Use the same active dimensions across this cohort. Unknown data scores 0,
    # rather than redistributing an individual candidate's missing weight to inflate its score.
    active = {name for _, dims in candidates for name in dims if config["weights"][name] > 0}
    total_weight = sum(config["weights"][name] for name in active)
    weights = {name: config["weights"][name] / total_weight for name in sorted(active)}
    ranked = []
    for c, dims in candidates:
        for name in active - dims.keys():
            dims[name] = {"score": 0, "reason": "Unknown data; verify before placement.", "evidence": {}}
        score = sum(dims[name]["score"] * weights[name] for name in weights)
        ranked.append(
            {
                "community_id": c.community_id,
                "community": c.model_dump(),
                "final_score": score,
                "score_breakdown": dims,
                "active_weights": weights,
                "business_value": {
                    "score": {1: 100, 2: 50, 3: 0}[c.business_tier],
                    "weight": 0,
                    "reason": "Contract / partner / other: suitability tie-break only.",
                },
                "reasons": [dims[name]["reason"] for name in sorted(dims)],
                "unscored_dimensions": sorted(DIMENSIONS - active),
            }
        )
    ranked.sort(key=lambda r: (-r["final_score"], -r["business_value"]["score"], r["community_id"]))
    for position, item in enumerate(ranked, 1):
        item["rank"] = position
        item["final_score"] = round(item["final_score"], 6)
    base["exclusions"].sort(key=lambda item: item["community_id"])
    base.update(recommendations=ranked[:5], eligible_count=len(ranked))
    return base
