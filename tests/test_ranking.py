import pytest
import pandas as pd
from src.ranking import assign_priority, filter_and_rank


def _row(**kwargs) -> dict:
    defaults = {
        "Type of Service": "Assisted Living",
        "Enhanced": "no",
        "Enriched": "no",
        "Monthly Fee": "3000",
        "Contract (w rate)?": "no",
        "Work with Placement?": "no",
    }
    defaults.update(kwargs)
    return defaults


def _df(*rows) -> pd.DataFrame:
    return pd.DataFrame([_row(**r) for r in rows])


# ── assign_priority ───────────────────────────────────────────────────────────

class TestAssignPriority:
    def test_contracted_rate_is_priority_1(self):
        assert assign_priority({"Contract (w rate)?": "yes", "Work with Placement?": "no"}) == 1

    def test_non_empty_contract_value_is_priority_1(self):
        assert assign_priority({"Contract (w rate)?": "$3,200/mo", "Work with Placement?": "yes"}) == 1

    def test_no_contract_placement_partner_is_priority_2(self):
        assert assign_priority({"Contract (w rate)?": "no", "Work with Placement?": "yes"}) == 2

    def test_neither_is_priority_3(self):
        assert assign_priority({"Contract (w rate)?": "no", "Work with Placement?": "no"}) == 3

    def test_empty_contract_is_priority_3(self):
        assert assign_priority({"Contract (w rate)?": "", "Work with Placement?": "no"}) == 3

    def test_nan_string_contract_is_priority_3(self):
        assert assign_priority({"Contract (w rate)?": "nan", "Work with Placement?": "no"}) == 3

    def test_missing_keys_default_to_priority_3(self):
        assert assign_priority({}) == 3


# ── filter_and_rank ───────────────────────────────────────────────────────────

class TestCareLevel:
    def test_filters_assisted_living(self):
        df = _df(
            {"Type of Service": "Assisted Living"},
            {"Type of Service": "Memory Care"},
            {"Type of Service": "Independent Living"},
        )
        result = filter_and_rank(df, {"care_level": "Assisted Living"})
        assert len(result) == 1
        assert result.iloc[0]["Type of Service"] == "Assisted Living"

    def test_filters_memory_care(self):
        df = _df(
            {"Type of Service": "Assisted Living"},
            {"Type of Service": "Memory Care"},
        )
        result = filter_and_rank(df, {"care_level": "Memory Care"})
        assert len(result) == 1
        assert result.iloc[0]["Type of Service"] == "Memory Care"

    def test_filters_independent_living(self):
        df = _df(
            {"Type of Service": "Assisted Living"},
            {"Type of Service": "Independent Living"},
        )
        result = filter_and_rank(df, {"care_level": "Independent Living"})
        assert len(result) == 1

    def test_enhanced_assisted_living_matches_assisted(self):
        df = _df({"Type of Service": "Assisted Living"})
        result = filter_and_rank(df, {"care_level": "Enhanced Assisted Living"})
        assert len(result) == 1


class TestBudgetFilter:
    def test_excludes_communities_over_budget(self):
        df = _df(
            {"Monthly Fee": "2000"},
            {"Monthly Fee": "4000"},
            {"Monthly Fee": "6000"},
        )
        result = filter_and_rank(df, {"care_level": "Assisted Living", "max_budget": 4000})
        assert len(result) == 2
        assert all(result["Monthly Fee"] <= 4000)

    def test_no_budget_returns_all(self):
        df = _df({"Monthly Fee": "2000"}, {"Monthly Fee": "9000"})
        result = filter_and_rank(df, {"care_level": "Assisted Living", "max_budget": None})
        assert len(result) == 2

    def test_cleans_dollar_sign_and_comma(self):
        df = _df({"Monthly Fee": "$3,500"})
        result = filter_and_rank(df, {"care_level": "Assisted Living", "max_budget": 4000})
        assert len(result) == 1
        assert result.iloc[0]["Monthly Fee"] == 3500.0

    def test_budget_boundary_is_inclusive(self):
        df = _df({"Monthly Fee": "4000"})
        result = filter_and_rank(df, {"care_level": "Assisted Living", "max_budget": 4000})
        assert len(result) == 1


class TestEnhancedEnriched:
    def test_filters_enhanced_requirement(self):
        df = _df({"Enhanced": "yes"}, {"Enhanced": "no"})
        result = filter_and_rank(df, {"care_level": "Assisted Living", "enhanced": "yes"})
        assert len(result) == 1
        assert result.iloc[0]["Enhanced"] == "yes"

    def test_filters_enriched_requirement(self):
        df = _df({"Enriched": "yes"}, {"Enriched": "no"})
        result = filter_and_rank(df, {"care_level": "Assisted Living", "enriched": "yes"})
        assert len(result) == 1

    def test_no_enhanced_requirement_keeps_all(self):
        df = _df({"Enhanced": "yes"}, {"Enhanced": "no"})
        result = filter_and_rank(df, {"care_level": "Assisted Living", "enhanced": "no"})
        assert len(result) == 2


class TestPriorityAssignment:
    def test_all_three_priority_levels_assigned(self):
        df = _df(
            {"Contract (w rate)?": "no",  "Work with Placement?": "no"},
            {"Contract (w rate)?": "yes", "Work with Placement?": "yes"},
            {"Contract (w rate)?": "no",  "Work with Placement?": "yes"},
        )
        result = filter_and_rank(df, {"care_level": "Assisted Living"})
        # Sorting by distance happens in add_geodata; here we verify tier assignment only
        assert set(result["Priority_Level"]) == {1, 2, 3}
        assert len(result[result["Priority_Level"] == 1]) == 1
        assert len(result[result["Priority_Level"] == 2]) == 1
        assert len(result[result["Priority_Level"] == 3]) == 1

    def test_output_is_a_copy_not_mutating_original(self):
        df = _df({"Monthly Fee": "3000"})
        original_cols = set(df.columns)
        filter_and_rank(df, {"care_level": "Assisted Living"})
        assert set(df.columns) == original_cols
