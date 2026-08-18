import pandas as pd
import pytest

from eiopa_rfr.ingestion import (
    _compute_shocks,
    _extract_curve_series,
    _extract_metadata,
    find_country_column,
)


class TestFindCountryColumn:
    def test_matches_french_alias(self):
        columns = ["Germany", "France", "Italy"]
        assert find_country_column(columns, "FR") == "France"

    def test_case_insensitive(self):
        columns = ["GERMANY", "france", "ITALY"]
        assert find_country_column(columns, "FR") == "france"

    def test_no_match_returns_none(self):
        assert find_country_column(["Germany", "Italy"], "FR") is None

    def test_unknown_country_code_falls_back_to_lowercase_literal(self):
        # Pas dans COUNTRY_ALIASES : on cherche le code lui-même en minuscule
        assert find_country_column(["Some XY Column"], "XY") == "Some XY Column"


class TestExtractCurveSeries:
    def test_keeps_only_numeric_index_rows(self):
        df = pd.DataFrame(
            {"France": [1, 20, 40, 3.3, 0.05, 10, 0.02607, 0.02829]},
            index=["Coupon_freq", "LLP", "Convergence", "UFR", "alpha", "CRA", 1, 5],
        )
        series = _extract_curve_series(df, "France")
        assert list(series.index) == [1, 5]
        assert series.loc[1] == pytest.approx(0.02607)

    def test_index_becomes_int(self):
        df = pd.DataFrame({"France": [0.02, 0.03]}, index=[1.0, 10.0])
        series = _extract_curve_series(df, "France")
        assert list(series.index) == [1, 10]
        assert series.index.dtype == int


class TestExtractMetadata:
    def test_extracts_known_labels(self):
        df = pd.DataFrame(
            {"France": [1, 20, 40, 3.3, 0.05, 10, 14]},
            index=["Coupon_freq", "LLP", "Convergence", "UFR", "alpha", "CRA", "VA"],
        )
        meta = _extract_metadata(df, "France")
        assert meta["LLP"] == 20
        assert meta["VA"] == 14
        assert meta["alpha"] == pytest.approx(0.05)

    def test_missing_label_is_none(self):
        df = pd.DataFrame({"France": [1]}, index=["Coupon_freq"])
        meta = _extract_metadata(df, "France")
        assert meta["Coupon_freq"] == 1
        assert meta["VA"] is None

    def test_nan_value_is_none(self):
        df = pd.DataFrame({"France": [float("nan")]}, index=["VA"])
        meta = _extract_metadata(df, "France")
        assert meta["VA"] is None


class TestComputeShocks:
    def test_formula_matches_eiopa_spec(self):
        # UP   = ROUND(base + MAX(0.01, shock_up   * ABS(base)), 5)
        # DOWN = ROUND(base - MAX(0.00, shock_down * ABS(base)), 5)
        base = pd.Series({1: 0.02, 10: 0.03})
        shocks = pd.DataFrame({"up": [0.5, 0.3], "down": [0.2, 0.15]}, index=[1, 10])

        up, down = _compute_shocks(base, shocks)

        assert up.loc[1] == pytest.approx(0.03)     # 0.02 + max(0.01, 0.5*0.02=0.01)
        assert down.loc[1] == pytest.approx(0.016)  # 0.02 - max(0.0, 0.2*0.02=0.004)
        assert up.loc[10] == pytest.approx(0.04)    # 0.03 + max(0.01, 0.3*0.03=0.009)
        assert down.loc[10] == pytest.approx(0.0255)  # 0.03 - max(0.0, 0.15*0.03=0.0045)

    def test_maturity_zero_forced_to_zero(self):
        base = pd.Series({0: 0.05, 1: 0.02})  # valeur non-nulle en maturité 0 malgré tout
        shocks = pd.DataFrame({"up": [1.0, 0.5], "down": [1.0, 0.2]}, index=[0, 1])
        up, down = _compute_shocks(base, shocks)
        assert up.loc[0] == 0.0
        assert down.loc[0] == 0.0

    def test_missing_maturities_default_to_zero_base(self):
        # base ne couvre pas toutes les 151 maturités attendues -> reindex fill 0.0
        base = pd.Series({1: 0.02})
        shocks = pd.DataFrame({"up": [0.5], "down": [0.2]}, index=[1])
        up, down = _compute_shocks(base, shocks)
        # maturité 50 absente de base et de shocks -> base 0, shock 0 -> up = max(0.01, 0) = 0.01
        assert up.loc[50] == pytest.approx(0.01)
        assert down.loc[50] == pytest.approx(0.0)

    def test_result_covers_all_expected_maturities(self):
        base = pd.Series({1: 0.02})
        shocks = pd.DataFrame({"up": [0.5], "down": [0.2]}, index=[1])
        up, down = _compute_shocks(base, shocks)
        assert list(up.index) == list(range(151))
        assert list(down.index) == list(range(151))
