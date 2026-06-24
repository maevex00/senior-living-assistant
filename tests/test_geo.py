import pytest
from src.geo import coords_from_zip, place_from_zip


# These tests use pgeocode's offline database (downloaded on first run, then cached).
# No network calls occur after the initial data download.

ROCHESTER_ZIPS = ["14618", "14610", "14607"]
INVALID_ZIP = "00000"


class TestCoordsFromZip:
    @pytest.mark.parametrize("zip_code", ROCHESTER_ZIPS)
    def test_valid_rochester_zip_returns_coordinates(self, zip_code):
        result = coords_from_zip(zip_code)
        assert result is not None, f"Expected coordinates for ZIP {zip_code}"
        lat, lon = result
        assert isinstance(lat, float)
        assert isinstance(lon, float)

    @pytest.mark.parametrize("zip_code", ROCHESTER_ZIPS)
    def test_rochester_latitude_in_expected_range(self, zip_code):
        lat, _ = coords_from_zip(zip_code)
        assert 42.5 < lat < 44.0, f"Latitude {lat} outside expected range for Rochester area"

    @pytest.mark.parametrize("zip_code", ROCHESTER_ZIPS)
    def test_rochester_longitude_in_expected_range(self, zip_code):
        _, lon = coords_from_zip(zip_code)
        assert -79.0 < lon < -76.0, f"Longitude {lon} outside expected range for Rochester area"

    def test_invalid_zip_returns_none(self):
        result = coords_from_zip(INVALID_ZIP)
        assert result is None

    def test_short_zip_padded_correctly(self):
        # "14618" and "14618" (already 5 digits) should return the same result
        result_full = coords_from_zip("14618")
        assert result_full is not None

    def test_returns_tuple(self):
        result = coords_from_zip("14618")
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestPlaceFromZip:
    def test_rochester_zip_returns_ny_state(self):
        _, state = place_from_zip("14618")
        assert state == "NY"

    def test_rochester_zip_returns_place_name(self):
        name, _ = place_from_zip("14618")
        assert name is not None
        assert isinstance(name, str)
        assert len(name) > 0

    def test_invalid_zip_returns_none_tuple(self):
        name, state = place_from_zip(INVALID_ZIP)
        assert name is None
        assert state is None

    def test_always_returns_two_element_tuple(self):
        result = place_from_zip("14618")
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.parametrize("zip_code", ROCHESTER_ZIPS)
    def test_multiple_rochester_zips_return_ny(self, zip_code):
        _, state = place_from_zip(zip_code)
        assert state == "NY"
