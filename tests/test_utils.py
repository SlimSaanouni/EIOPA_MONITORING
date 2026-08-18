from datetime import datetime

import pytest

from eiopa_rfr.utils import (
    calculate_bps_change,
    create_summary_dict,
    format_bps,
    format_rate_pct,
    get_previous_month_date,
    get_year_start_date,
    parse_date_from_filename,
    safe_float_conversion,
    validate_rate,
)


class TestParseDateFromFilename:
    def test_extracts_date_from_standard_filename(self):
        assert parse_date_from_filename("EIOPA_RFR_20260630_Term_Structures.xlsx") == datetime(2026, 6, 30)

    def test_extracts_date_from_zip_filename(self):
        assert parse_date_from_filename("EIOPA_RFR_20231231.zip") == datetime(2023, 12, 31)

    def test_no_date_returns_none(self):
        assert parse_date_from_filename("some_file_without_a_date.xlsx") is None

    def test_invalid_date_returns_none(self):
        # 8 chiffres mais pas une date valide (mois 99)
        assert parse_date_from_filename("EIOPA_RFR_20269931.zip") is None


class TestValidateRate:
    def test_within_bounds(self):
        assert validate_rate(0.02) is True

    def test_at_lower_bound(self):
        assert validate_rate(-0.05) is True

    def test_at_upper_bound(self):
        assert validate_rate(0.15) is True

    def test_below_bounds(self):
        assert validate_rate(-0.06) is False

    def test_above_bounds(self):
        assert validate_rate(0.16) is False


class TestSafeFloatConversion:
    def test_plain_float(self):
        assert safe_float_conversion(0.025) == 0.025

    def test_comma_decimal_string(self):
        assert safe_float_conversion("0,025") == 0.025

    def test_string_with_spaces(self):
        assert safe_float_conversion(" 1 234,5 ") == 1234.5

    def test_nan_returns_none(self):
        assert safe_float_conversion(float("nan")) is None

    def test_non_numeric_string_returns_none(self):
        assert safe_float_conversion("not a number") is None


class TestBpsHelpers:
    def test_calculate_bps_change_positive(self):
        assert calculate_bps_change(0.02, 0.025) == pytest.approx(50.0)

    def test_calculate_bps_change_negative(self):
        assert calculate_bps_change(0.025, 0.02) == pytest.approx(-50.0)

    def test_format_bps_positive_has_explicit_sign(self):
        assert format_bps(23.4) == "+23.4 bps"

    def test_format_bps_negative(self):
        assert format_bps(-23.4) == "-23.4 bps"

    def test_format_bps_zero_has_plus_sign(self):
        assert format_bps(0.0) == "+0.0 bps"

    def test_format_rate_pct(self):
        assert format_rate_pct(0.02592) == "2.59%"


class TestDateHelpers:
    def test_previous_month_date_mid_month(self):
        assert get_previous_month_date(datetime(2026, 7, 31)) == datetime(2026, 6, 30)

    def test_previous_month_date_crosses_year_boundary(self):
        assert get_previous_month_date(datetime(2026, 1, 15)) == datetime(2025, 12, 31)

    def test_year_start_date(self):
        assert get_year_start_date(datetime(2026, 7, 31)) == datetime(2026, 1, 1)


class TestCreateSummaryDict:
    def test_no_previous_or_ytd_data_yields_empty_changes(self):
        summary = create_summary_dict(
            reference_date=datetime(2026, 7, 31),
            country="FR",
            rates={1: 0.02, 10: 0.03},
            va=0.0013,
        )
        assert summary["changes_mom"] == {}
        assert summary["changes_ytd"] == {}
        assert summary["rates"] == {1: 0.02, 10: 0.03}

    def test_mom_change_computed_for_common_maturities(self):
        summary = create_summary_dict(
            reference_date=datetime(2026, 7, 31),
            country="FR",
            rates={1: 0.025, 10: 0.030},
            va=0.0013,
            previous_rates={1: 0.020, 10: 0.029},
            previous_va=0.0010,
        )
        assert summary["changes_mom"][1] == pytest.approx(50.0)
        assert summary["changes_mom"][10] == pytest.approx(10.0)
        assert summary["changes_mom"]["va"] == pytest.approx(3.0)

    def test_mom_change_skips_maturity_missing_from_previous(self):
        summary = create_summary_dict(
            reference_date=datetime(2026, 7, 31),
            country="FR",
            rates={1: 0.025, 30: 0.035},
            va=None,
            previous_rates={1: 0.020},  # 30Y absent du mois précédent
        )
        assert 1 in summary["changes_mom"]
        assert 30 not in summary["changes_mom"]
