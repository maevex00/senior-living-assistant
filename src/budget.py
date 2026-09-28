"""Budget fallback extracted from the original AI pipeline; supports k notation."""

import re


def regex_budget_fallback(transcript: str) -> int | None:
    for pattern in [
        r"\$\s*([\d,]+(?:\.\d+)?)\s*(k)?",
        r"([\d,]+(?:\.\d+)?)\s*(k)?\s*(?:dollars?|per\s*month|/month)",
        r"(?:budget|maximum|max|up to)\s*(?:is|of)?\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(k)?",
    ]:
        matches = re.findall(pattern, transcript, re.IGNORECASE)
        if matches:
            values = [float(n.replace(",", "")) * (1000 if k else 1) for n, k in matches]
            maximum = max(values)
            return int(maximum) if 0 < maximum <= 1000000 else None
    return None
