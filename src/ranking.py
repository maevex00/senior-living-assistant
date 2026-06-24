import pandas as pd


def assign_priority(row) -> int:
    """Return priority tier: 1=contracted, 2=placement partner, 3=other."""
    c = str(row.get("Contract (w rate)?", "")).lower()
    p = str(row.get("Work with Placement?", "")).lower()
    if c not in ["no", "nan", ""]:
        return 1
    if c == "no" and p == "yes":
        return 2
    return 3


def filter_and_rank(df: pd.DataFrame, prefs: dict) -> pd.DataFrame:
    """Apply care-level, enhanced/enriched, and budget filters; assign priority tiers."""
    df = df.copy()

    # Normalize Monthly Fee to numeric
    if "Monthly Fee" in df.columns:
        df["Monthly Fee"] = (
            df["Monthly Fee"].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.extract(r"(\d+\.?\d*)")[0]
        )
        df["Monthly Fee"] = pd.to_numeric(df["Monthly Fee"], errors="coerce")

    # Care level
    care = str(prefs.get("care_level", "")).lower()
    if any(k in care for k in ["assisted", "al", "enhanced"]):
        df = df[df["Type of Service"].str.contains("Assisted", case=False, na=False)]
    elif any(k in care for k in ["memory", "dementia"]):
        df = df[df["Type of Service"].str.contains("Memory", case=False, na=False)]
    elif any(k in care for k in ["independent", "il"]):
        df = df[df["Type of Service"].str.contains("Independent", case=False, na=False)]

    # Enhanced / enriched
    if prefs.get("enhanced") in [True, "true", "True", "yes", "Yes"]:
        df = df[df["Enhanced"].astype(str).str.lower() == "yes"]
    if prefs.get("enriched") in [True, "true", "True", "yes", "Yes"]:
        df = df[df["Enriched"].astype(str).str.lower() == "yes"]

    # Budget ceiling
    budget = prefs.get("max_budget")
    if budget:
        try:
            budget = float(str(budget).replace(",", "").strip())
            df = df[df["Monthly Fee"] <= budget]
        except (ValueError, TypeError):
            pass

    df["Priority_Level"] = df.apply(assign_priority, axis=1)
    return df
