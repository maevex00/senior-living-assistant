"""Sheets write-back isolated from recommendation generation."""

import json

from backend.data import sheets_client

HEADERS = [
    "consultation_id",
    "timestamp",
    "patient_name",
    "contact_name",
    "contact_phone",
    "contact_email",
    "care_level",
    "max_budget",
    "locations",
    "move_in_window",
    "selected_communities",
    "ranking_scores",
    "advisor_notes",
    "input_mode",
    "processing_ms",
]


def log_consultation(settings, record, selected, notes, client=None):
    if settings["DEMO_MODE"]:
        return {"crm_logged": False, "demo": True, "message": "Demo: no external CRM write."}
    try:
        sheet = (
            (client or sheets_client(settings))
            .open_by_key(settings["CRM_SHEET_ID"])
            .worksheet(settings["CRM_WORKSHEET"])
        )
        if sheet.row_values(1) != HEADERS:
            return {
                "crm_logged": False,
                "crm_error": "CRM worksheet headers do not match the documented schema.",
            }
        # Best-effort retry deduplication. Sheets has no atomic uniqueness constraint.
        if record["consultation_id"] in sheet.col_values(1)[1:]:
            return {"crm_logged": True, "duplicate": True}
        p = record["profile"]
        row = [
            record["consultation_id"],
            record["timestamp"],
            p.get("patient_name"),
            p.get("primary_contact_name"),
            p.get("primary_contact_phone"),
            p.get("primary_contact_email"),
            p.get("care_level"),
            p.get("max_budget"),
            ", ".join(p["preferred_locations"]),
            p.get("move_in_window"),
            ", ".join(selected),
            json.dumps(record["scores"]),
            notes,
            record["input_mode"],
            record["processing_ms"],
        ]
        # RAW prevents spreadsheet formulas supplied in names or notes from executing.
        sheet.append_row(["" if value is None else value for value in row], value_input_option="RAW")
        return {"crm_logged": True}
    except Exception:
        return {"crm_logged": False, "crm_error": "CRM is unavailable. Recommendations remain available."}
