import json
import pytest
from unittest.mock import MagicMock
from src.ai_pipeline import _regex_budget_fallback, GeminiService
from backend.models import ClientProfile


def extract_preferences(client, transcript):
    return GeminiService({"GEMINI_MODEL": "gemini-2.5-flash"}, client).extract(transcript)[0].model_dump()


def batch_generate_explanations(client, communities, prefs):
    rows = [{"community_id": str(i), "rank": i+1, "final_score": 90, "reasons": ["Within budget"]} for i, _ in enumerate(communities)]
    mapped, _, _ = GeminiService({"GEMINI_MODEL": "gemini-2.5-flash", "DEMO_MODE": False}, client).explain(ClientProfile(), rows)
    return [mapped[str(i)] for i in range(len(rows))]


def _mock_client(response_content: str) -> MagicMock:
    """Mock the Google GenAI SDK with structured responses."""
    client = MagicMock()
    data = json.loads(response_content)
    if isinstance(data, list):
        data = {"explanations": [{"community_id": str(i), "explanation": text} for i, text in enumerate(data)]}
    elif "explanations" in data:
        data = {"explanations": [{"community_id": str(i), "explanation": text} for i, text in enumerate(data["explanations"])]}
    client.models.generate_content.return_value.text = json.dumps(data)
    return client


# ── _regex_budget_fallback ────────────────────────────────────────────────────

class TestRegexBudgetFallback:
    def test_extracts_dollar_amount_with_comma(self):
        assert _regex_budget_fallback("Budget is around $4,000 per month.") == 4000

    def test_extracts_dollar_amount_without_comma(self):
        assert _regex_budget_fallback("Maximum $4500 per month.") == 4500

    def test_extracts_maximum_when_multiple_amounts(self):
        result = _regex_budget_fallback("Budget is $3,000 to $4,500 per month.")
        assert result == 4500

    def test_returns_none_when_no_budget_mentioned(self):
        assert _regex_budget_fallback("She needs memory care and loves gardening.") is None

    def test_handles_up_to_phrasing(self):
        result = _regex_budget_fallback("Up to $5,000 monthly.")
        assert result == 5000

    def test_handles_budget_is_phrasing(self):
        result = _regex_budget_fallback("Her budget is $3500.")
        assert result is not None
        assert result >= 3500

    def test_ignores_non_budget_numbers(self):
        result = _regex_budget_fallback("She is 78 years old and has 2 children.")
        assert result is None


# ── extract_preferences ───────────────────────────────────────────────────────

class TestExtractPreferences:
    def _make_prefs_json(self, **overrides) -> str:
        prefs = {"patient_name": "John Doe", "age": 80, "care_level": "Assisted Living", "max_budget": 3000,
                 "preferred_locations": ["Rochester, NY"], "move_in_window": "Immediate"}
        prefs.update(overrides)
        return json.dumps(prefs)

    def test_returns_dict_with_core_keys(self):
        client = _mock_client(self._make_prefs_json())
        result = extract_preferences(client, "sample transcript")
        assert "patient_name" in result
        assert "care_level" in result
        assert "max_budget" in result

    def test_passes_transcript_to_api(self):
        client = _mock_client(self._make_prefs_json())
        extract_preferences(client, "specific transcript text")
        call_args = client.models.generate_content.call_args
        assert "specific transcript text" in call_args.kwargs["contents"]

    def test_regex_fallback_activates_when_budget_null(self):
        prefs_no_budget = self._make_prefs_json(max_budget=None)
        client = _mock_client(prefs_no_budget)
        result = extract_preferences(client, "Her budget is $4,500 per month.")
        assert result["max_budget"] == 4500

    def test_regex_fallback_skipped_when_budget_present(self):
        client = _mock_client(self._make_prefs_json(max_budget=3000))
        result = extract_preferences(client, "Her budget is $9,000 per month.")
        assert result["max_budget"] == 3000

    def test_uses_structured_json_response(self):
        client = _mock_client(self._make_prefs_json())
        extract_preferences(client, "transcript")
        call_kwargs = client.models.generate_content.call_args.kwargs
        assert call_kwargs["config"].response_mime_type == "application/json"


# ── batch_generate_explanations ───────────────────────────────────────────────

class TestBatchGenerateExplanations:
    def _make_communities(self, n: int = 3) -> list:
        return [
            {
                "Type of Service": "Assisted Living",
                "Town": "Brighton",
                "Monthly Fee": 3200 + i * 200,
                "Distance_miles": 3.5 + i,
                "Priority_Level": 1,
            }
            for i in range(n)
        ]

    def test_returns_list_of_strings(self):
        client = _mock_client('{"explanations": ["Great fit.", "Close by.", "Good value."]}')
        result = batch_generate_explanations(client, self._make_communities(3), {"care_level": "Assisted Living", "max_budget": 4000, "preferred_location": ["Rochester, NY"], "enhanced": "no", "enriched": "no"})
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_returns_correct_count(self):
        client = _mock_client('{"explanations": ["A.", "B.", "C."]}')
        result = batch_generate_explanations(client, self._make_communities(3), {})
        assert len(result) == 3

    def test_maps_explanation_ids_to_original_order(self):
        client = _mock_client('["Sentence one.", "Sentence two."]')
        result = batch_generate_explanations(client, self._make_communities(2), {})
        assert len(result) == 2

    def test_single_api_call_for_multiple_communities(self):
        client = _mock_client('{"explanations": ["A.", "B.", "C.", "D.", "E."]}')
        batch_generate_explanations(client, self._make_communities(5), {})
        assert client.models.generate_content.call_count == 1

    def test_uses_structured_json_response(self):
        client = _mock_client('{"explanations": ["A."]}')
        batch_generate_explanations(client, self._make_communities(1), {})
        call_kwargs = client.models.generate_content.call_args.kwargs
        assert call_kwargs["config"].response_mime_type == "application/json"
