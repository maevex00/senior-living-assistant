import json
from unittest.mock import MagicMock

from backend.ai import GeminiService
from backend.crm import HEADERS, log_consultation
from tests.unit.test_v2_ranking import community, profile, ranked

SETTINGS = {
    "DEMO_MODE": False,
    "GEMINI_MODEL": "gemini-2.5-flash",
    "GEMINI_LIVE_MODEL": "configured-live",
    "CRM_SHEET_ID": "test-sheet",
    "CRM_WORKSHEET": "Consultations",
}


def test_extraction_retry_and_budget_fallback():
    client = MagicMock()
    client.models.generate_content.side_effect = [
        MagicMock(text="invalid"),
        MagicMock(text='{"care_level":"AL"}'),
    ]
    p, calls, warnings = GeminiService(SETTINGS, client).extract("Budget is $4,500")
    assert p.care_level == "Assisted Living" and p.max_budget == 4500
    assert calls == 2 and not warnings


def test_extraction_failure_safe_partial():
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("secret key should never appear")
    p, calls, warnings = GeminiService(SETTINGS, client).extract("Resident is 78. Budget $4500")
    assert p.max_budget == 4500 and p.age is None and p.care_level is None
    assert calls == 2 and warnings and "secret" not in str(warnings)


def test_native_audio_payload():
    client = MagicMock()
    client.models.generate_content.return_value.text = "{}"
    GeminiService(SETTINGS, client).extract(audio=b"RIFF1234WAVE", mime="audio/wav")
    part = client.models.generate_content.call_args.kwargs["contents"][0]
    assert part.inline_data.data == b"RIFF1234WAVE"
    assert part.inline_data.mime_type == "audio/wav"


def test_provider_usage_is_reported_only_when_supplied():
    client = MagicMock()
    client.models.generate_content.return_value.text = "{}"
    client.models.generate_content.return_value.usage_metadata.total_token_count = 123
    metrics = {}
    GeminiService(SETTINGS, client).extract("test", metrics=metrics)
    assert metrics["total_token_count"] == 123
    assert "prompt_token_count" not in metrics
    assert metrics["validation_ms"] >= 0


def test_explanations_one_batch_id_mapping_and_immutable_ranking():
    client = MagicMock()
    rows = ranked([community("A"), community("B")])["recommendations"]
    original = json.dumps(rows)
    client.models.generate_content.return_value.text = json.dumps(
        {
            "explanations": [
                {"community_id": "B", "explanation": "B text"},
                {"community_id": "A", "explanation": "A text"},
            ]
        }
    )
    mapped, calls, source = GeminiService(SETTINGS, client).explain(profile(), rows)
    assert mapped["A"] == "A text" and calls == 1 and source == "gemini"
    assert client.models.generate_content.call_count == 1 and json.dumps(rows) == original
    assert "patient_name" not in client.models.generate_content.call_args.kwargs["contents"]


def test_invalid_explanation_ids_fall_back_without_retry():
    client = MagicMock()
    client.models.generate_content.return_value.text = (
        '{"explanations":[{"community_id":"invented","explanation":"X"}]}'
    )
    rows = ranked([community()])["recommendations"]
    mapped, calls, source = GeminiService(SETTINGS, client).explain(profile(), rows)
    assert mapped["A"] == " ".join(rows[0]["reasons"]) and calls == 1 and source == "deterministic_fallback"


def test_ephemeral_token_limits_and_server_constraints():
    client = MagicMock()
    client.auth_tokens.create.return_value.name = "ephemeral"
    r = GeminiService(SETTINGS, client).live_token("assist")
    config = client.auth_tokens.create.call_args.kwargs["config"]
    assert config["uses"] == 1
    assert config["live_connect_constraints"]["model"] == "configured-live"
    assert (
        config["live_connect_constraints"]["config"]["tools"][0]["function_declarations"][0]["name"]
        == "updateDashboard"
    )
    assert r["token"] == "ephemeral"


def record():
    return {
        "consultation_id": "test-id",
        "timestamp": "2026-01-01",
        "profile": profile().model_dump(),
        "scores": {"A": 99},
        "input_mode": "manual",
        "processing_ms": 10,
    }


def test_crm_raw_write_dedup_and_failure():
    client = MagicMock()
    sheet = client.open_by_key.return_value.worksheet.return_value
    sheet.row_values.return_value = HEADERS
    sheet.col_values.return_value = ["consultation_id"]
    assert log_consultation(SETTINGS, record(), ["A"], '=IMPORTXML("bad")', client)["crm_logged"]
    assert sheet.append_row.call_args.kwargs["value_input_option"] == "RAW"
    assert '=IMPORTXML("bad")' in sheet.append_row.call_args.args[0]
    sheet.col_values.return_value = ["consultation_id", "test-id"]
    assert log_consultation(SETTINGS, record(), ["A"], "", client)["duplicate"]
    assert sheet.append_row.call_count == 1
    client.open_by_key.side_effect = RuntimeError("credential data")
    response = log_consultation(SETTINGS, record(), [], "", client)
    assert not response["crm_logged"] and "credential" not in str(response)
