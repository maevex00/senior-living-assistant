"""Offline system checks by default. --live explicitly measures real Gemini extraction."""

import argparse
import json
import os
import time
from pathlib import Path

from backend.ai import GeminiService
from backend.models import ClientProfile, Community
from backend.ranking import load_config, rank
from src.budget import regex_budget_fallback

ROOT = Path(__file__).parent


def evaluate(live=False):
    checks = []
    for case in json.loads((ROOT / "ranking_cases.json").read_text()):
        communities = [
            Community(
                **dict(
                    {
                        "name": c["community_id"],
                        "care_levels": ["Assisted Living"],
                        "monthly_fee": 4000,
                        "coordinates": (43.1, -77.5),
                    },
                    **c,
                )
            )
            for c in case["communities"]
        ]
        profile = ClientProfile.model_validate(case["profile"])
        first = rank(profile, communities, [(43.1, -77.5)], load_config())
        ids = [r["community_id"] for r in first["recommendations"]]
        stable = first == rank(profile, list(reversed(communities)), [(43.1, -77.5)], load_config())
        checks.append({"id": case["id"], "passed": ids == case["expected_ids"] and stable, "actual_ids": ids})
    cases = json.loads((ROOT / "extraction_cases.json").read_text())
    fallback = [
        {"id": c["id"], "passed": regex_budget_fallback(c["text"]) == c["expected"]["max_budget"]}
        for c in cases
    ]
    report = {
        "ranking": {"passed": sum(c["passed"] for c in checks), "total": len(checks), "cases": checks},
        "offline_budget_fallback": {"passed": sum(c["passed"] for c in fallback), "total": len(fallback)},
        "gemini_extraction": {
            "status": "not_run",
            "reason": "Requires --live and GEMINI_API_KEY. Offline checks are not AI accuracy.",
        },
    }
    if live:
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("--live requires GEMINI_API_KEY")
        service = GeminiService(
            {
                "GEMINI_API_KEY": os.environ["GEMINI_API_KEY"],
                "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            }
        )
        fields = ["care_level", "max_budget", "preferred_locations", "move_in_window"]
        correct = dict.fromkeys(fields, 0)
        complete = calls = 0
        timings = []
        for case in cases:
            start = time.perf_counter()
            profile, count, warnings = service.extract(text=case["text"])
            timings.append(round((time.perf_counter() - start) * 1000, 2))
            calls += count
            actual = profile.model_dump()
            matches = {field: actual[field] == case["expected"][field] and not warnings for field in fields}
            for field in fields:
                correct[field] += matches[field]
            complete += all(matches.values())
        report["gemini_extraction"] = {
            "status": "measured",
            "cases": len(cases),
            "model": service.settings["GEMINI_MODEL"],
            "exact_field_accuracy": {f: correct[f] / len(cases) for f in fields},
            "exact_profile_accuracy": complete / len(cases),
            "api_calls": calls,
            "latencies_ms": timings,
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = evaluate(args.live)
    output = json.dumps(report, indent=2)
    print(output)
    if args.output:
        Path(args.output).write_text(output + "\n")
    if (
        report["ranking"]["passed"] != report["ranking"]["total"]
        or report["offline_budget_fallback"]["passed"] != report["offline_budget_fallback"]["total"]
    ):
        raise SystemExit(1)
