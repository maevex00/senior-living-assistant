from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.data import GeoResolver, load_communities, sheets_client, wait_months


@pytest.mark.parametrize("value", [None, float("nan"), "", "unknown"])
def test_missing_availability_is_not_available_now(value):
    assert wait_months(value) is None


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_file_repository_preserves_no_wait_and_zip(tmp_path, extension):
    path = tmp_path / f"communities.{extension}"
    frame = pd.DataFrame(
        [
            {
                "CommunityID": "A",
                "Type of Service": "Assisted Living",
                "Monthly Fee": "$4,000",
                "ZIP": "14618",
                "Est. Waitlist Length": "None",
            }
        ]
    )
    if extension == "csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_excel(path, index=False)
    result = load_communities({"DEMO_MODE": False, "COMMUNITIES_FILE": str(path)}, GeoResolver())
    assert result[0].wait_months == 0 and result[0].monthly_fee == 4000
    assert result[0].coordinates is not None


def test_sheets_read_uses_explicit_sheet_id_and_worksheet():
    client = MagicMock()
    ws = client.open_by_key.return_value.worksheet.return_value
    ws.get_all_records.return_value = [
        {"CommunityID": "A", "Type of Service": "Memory Care", "Monthly Fee": 6000}
    ]
    with patch("backend.data.sheets_client", return_value=client):
        rows = load_communities(
            {"DEMO_MODE": False, "COMMUNITIES_SHEET_ID": "sheet-id", "COMMUNITIES_WORKSHEET": "Communities"},
            GeoResolver(),
        )
    client.open_by_key.assert_called_once_with("sheet-id")
    assert rows[0].care_levels == ["Memory Care"]


def test_sheets_auth_scope_and_timeout():
    with (
        patch("google.oauth2.service_account.Credentials.from_service_account_info") as credentials,
        patch("gspread.authorize") as authorize,
    ):
        sheets_client({"GOOGLE_SERVICE_ACCOUNT_JSON": "{}"})
    assert credentials.call_args.kwargs["scopes"] == ["https://www.googleapis.com/auth/spreadsheets"]
    authorize.return_value.set_timeout.assert_called_once_with(15)
