import json
import pytest
from unittest.mock import MagicMock
from src.ai_pipeline import _regex_budget_fallback, extract_preferences, batch_generate_explanations


def _mock_client(response_content: str) -> MagicMock:
    """Create a mock OpenAI client that returns a fixed JSON string."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = response_content
    client.chat.completions.create.return_value.choices = [MagicMock(message=msg)]
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
        prefs = {
            "name_of_patient": "John Doe",
            "age_of_patient": "80",
            "injury_or_reason": "Hip fracture",
            "primary_contact_information": {"name": "Jane", "phone_number": "555-1234", "email": ""},
            "mentally": "sharp",
            "care_level": "Assisted Living",
            "preferred_location": ["Rochester, NY"],
            "enhanced": "no",
            "enriched": "no",
            "move_in_window": "Immediate (0-1 months)",
            "max_budget": 3000,
            "pet_friendly": "no",
            "tour_availability": [],
            "other_keywords": {},
        }
        prefs.update(overrides)
        return json.dumps(prefs)

    def test_returns_dict_with_core_keys(self):
        client = _mock_client(self._make_prefs_json())
        result = extract_preferences(client, "sample transcript")
        assert "name_of_patient" in result
        assert "care_level" in result
        assert "max_budget" in result

    def test_passes_transcript_to_api(self):
        client = _mock_client(self._make_prefs_json())
        extract_preferences(client, "specific transcript text")
        call_args = client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "specific transcript text" in user_content

    def test_regex_fallback_activates_when_budget_null(self):
        prefs_no_budget = self._make_prefs_json(max_budget=None)
        client = _mock_client(prefs_no_budget)
        result = extract_preferences(client, "Her budget is $4,500 per month.")
        assert result["max_budget"] == 4500

    def test_regex_fallback_skipped_when_budget_present(self):
        client = _mock_client(self._make_prefs_json(max_budget=3000))
        result = extract_preferences(client, "Her budget is $9,000 per month.")
        assert result["max_budget"] == 3000

    def test_uses_json_object_response_format(self):
        client = _mock_client(self._make_prefs_json())
        extract_preferences(client, "transcript")
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}


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

    def test_handles_direct_list_response(self):
        client = _mock_client('["Sentence one.", "Sentence two."]')
        result = batch_generate_explanations(client, self._make_communities(2), {})
        assert len(result) == 2

    def test_single_api_call_for_multiple_communities(self):
        client = _mock_client('{"explanations": ["A.", "B.", "C.", "D.", "E."]}')
        batch_generate_explanations(client, self._make_communities(5), {})
        assert client.chat.completions.create.call_count == 1

    def test_uses_json_object_response_format(self):
        client = _mock_client('{"explanations": ["A."]}')
        batch_generate_explanations(client, self._make_communities(1), {})
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("response_format") == {"type": "json_object"}
