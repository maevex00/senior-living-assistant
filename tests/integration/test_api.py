import io
import json
from unittest.mock import patch

import pytest

from backend.app import create_app


@pytest.fixture
def client():
    return create_app({"TESTING": True, "DEMO_MODE": True, "RATE_LIMIT": 1000}).test_client()


def test_offline_demo_end_to_end(client):
    with patch("socket.socket.connect", side_effect=AssertionError("No network allowed")):
        p = client.get("/api/demo").json["profile"]
        r = client.post("/api/recommend", json={"profile": p, "input_mode": "demo"})
        assert r.status_code == 200
        result = r.json
        assert len(result["recommendations"]) == 5 and result["eligible_count"] == 7
        assert result["metrics"]["ai_calls"] == 0
        assert all(item["score_breakdown"] for item in result["recommendations"])
        crm = client.post("/api/consultations/log", json={"receipt": result["receipt"]}).json
        assert crm["demo"] and not crm["crm_logged"]


def test_manual_missing_and_validation(client):
    r = client.post("/api/intake/manual", json={"care_level": "AL", "max_budget": "4.5k monthly"})
    assert r.json["profile"]["max_budget"] == 4500
    assert r.json["intake"]["missing_fields"] == ["preferred_locations"]
    assert client.post("/api/intake/manual", json={"max_budget": -1}).status_code == 422
    assert client.post("/api/intake/manual", json={"ranking": ["A"]}).status_code == 422
    assert client.post("/api/intake/manual", data="bad", content_type="application/json").status_code == 400


def test_text_offline_partial_and_errors(client):
    r = client.post("/api/intake/text", json={"text": "Budget $4000"}).json
    assert r["profile"]["max_budget"] == 4000 and r["warnings"]
    for body in ({"text": ""}, [], {"text": "a" * 50001}):
        assert client.post("/api/intake/text", json=body).status_code == 422


@pytest.mark.parametrize(
    "name,data", [("bad.exe", b"RIFF0000WAVE"), ("test.wav", b"not audio"), ("test.mp3", b"")]
)
def test_audio_invalid(client, name, data):
    r = client.post("/api/intake/audio", data={"audio": (io.BytesIO(data), name)})
    assert r.status_code == 422


def test_production_auth_and_cors():
    settings = {"DEMO_MODE": False, "ADVISOR_ACCESS_TOKEN": "a" * 32, "SIGNING_SECRET": "b" * 32}
    c = create_app(settings).test_client()
    assert c.post("/api/intake/manual", json={}).status_code == 401
    r = c.post(
        "/api/intake/manual",
        json={},
        headers={"Authorization": "Bearer " + "a" * 32, "Origin": "https://evil.invalid"},
    )
    assert r.status_code == 200 and "Access-Control-Allow-Origin" not in r.headers
    with pytest.raises(ValueError):
        create_app({"DEMO_MODE": False})


def test_production_audio_and_text_mocked():
    from unittest.mock import MagicMock

    from backend.ai import GeminiService

    sdk = MagicMock()
    sdk.models.generate_content.return_value.text = (
        '{"care_level":"AL","max_budget":4500,"preferred_locations":["14618"]}'
    )
    ai = GeminiService({"GEMINI_MODEL": "gemini-2.5-flash"}, sdk)
    c = create_app(
        {"DEMO_MODE": False, "ADVISOR_ACCESS_TOKEN": "a" * 32, "SIGNING_SECRET": "b" * 32, "AI_SERVICE": ai}
    ).test_client()
    headers = {"Authorization": "Bearer " + "a" * 32}
    text = c.post("/api/intake/text", json={"text": "AL budget $4500 near 14618"}, headers=headers)
    audio = c.post(
        "/api/intake/audio",
        data={"audio": (io.BytesIO(b"RIFF0000WAVE0000"), "../../unsafe.wav")},
        headers=headers,
    )
    assert text.status_code == audio.status_code == 200
    assert text.json["profile"] == audio.json["profile"]


def test_crm_tampering_and_failure_isolation(client):
    p = client.get("/api/demo").json["profile"]
    result = client.post("/api/recommend", json={"profile": p}).json
    assert client.post("/api/consultations/log", json={"receipt": "forged"}).status_code == 422
    assert (
        client.post(
            "/api/consultations/log", json={"receipt": result["receipt"], "selected_community_ids": ["FAKE"]}
        ).status_code
        == 422
    )
    with patch(
        "backend.app.log_consultation", return_value={"crm_logged": False, "crm_error": "Unavailable"}
    ):
        assert not client.post("/api/consultations/log", json={"receipt": result["receipt"]}).json[
            "crm_logged"
        ]
    assert (
        client.post("/api/recommend", json={"profile": p}).json["recommendations"]
        == result["recommendations"]
    )


def test_logs_and_errors_do_not_leak_pii(client, caplog):
    with caplog.at_level("INFO", logger="placement"):
        client.post("/api/intake/manual", json={"patient_name": "PRIVATE PERSON", "age": -1})
    assert "PRIVATE PERSON" not in caplog.text
    assert all(json.loads(r.message) for r in caplog.records if r.name == "placement")


def test_rate_limit_and_upload_limit():
    c = create_app({"DEMO_MODE": True, "RATE_LIMIT": 1, "MAX_CONTENT_LENGTH": 100}).test_client()
    assert c.post("/api/intake/text", json={"text": "x" * 200}).status_code == 413
    assert c.post("/api/intake/manual", json={}).status_code == 429
