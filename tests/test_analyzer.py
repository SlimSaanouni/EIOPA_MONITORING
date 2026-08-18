from datetime import datetime

import pytest

from src.analyzer import EIOPAAnalyzer
from tests.conftest import seed_curve, seed_metadata


@pytest.fixture
def analyzer(test_db_path):
    return EIOPAAnalyzer(db_path=test_db_path)


def seed_month(conn, date, rates, va=None, va_type_for_rates="NO_VA"):
    seed_curve(conn, date, va_type=va_type_for_rates, curve_type="BASE", rates=rates)
    if va is not None:
        seed_metadata(conn, date, va_type="WITH_VA", va=va)


class TestHistoricalSummary:
    def test_empty_db_returns_empty_dataframe(self, analyzer):
        df = analyzer.historical_summary()
        assert df.empty
        assert list(df.columns) == ["reference_date", "country", "rate_1y", "rate_5y", "rate_10y", "rate_20y", "rate_30y", "va"]

    def test_one_month_seeded(self, conn, analyzer):
        seed_month(conn, "2026-07-31", {1: 0.028, 10: 0.030}, va=0.0013)
        df = analyzer.historical_summary()
        assert len(df) == 1
        row = df.iloc[0]
        assert row["rate_1y"] == pytest.approx(0.028)
        assert row["rate_10y"] == pytest.approx(0.030)
        assert row["va"] == pytest.approx(0.0013)

    def test_historical_data_property_matches_summary(self, conn, analyzer):
        seed_month(conn, "2026-07-31", {1: 0.028})
        assert analyzer.historical_data.equals(analyzer.historical_summary())


class TestGetHistoricalData:
    def test_exact_match(self, conn, analyzer):
        seed_month(conn, "2026-07-31", {1: 0.028, 10: 0.030})
        result = analyzer.get_historical_data("FR", datetime(2026, 7, 31))
        assert result["rates"][1] == pytest.approx(0.028)

    def test_no_match_returns_none(self, analyzer):
        assert analyzer.get_historical_data("FR", datetime(2026, 7, 31)) is None


class TestPreviousMonthAndYtd:
    def test_previous_month_within_tolerance(self, conn, analyzer):
        seed_month(conn, "2026-06-30", {10: 0.029})
        seed_month(conn, "2026-07-31", {10: 0.030})
        result = analyzer.get_previous_month_data(datetime(2026, 7, 31), "FR")
        assert result is not None
        assert result["rates"][10] == pytest.approx(0.029)

    def test_previous_month_missing_returns_none(self, conn, analyzer):
        seed_month(conn, "2026-07-31", {10: 0.030})
        assert analyzer.get_previous_month_data(datetime(2026, 7, 31), "FR") is None

    def test_ytd_matches_year_start(self, conn, analyzer):
        # get_year_start_date() vise le 1er janvier, tolérance de 10 jours
        seed_month(conn, "2026-01-05", {10: 0.027})
        seed_month(conn, "2026-07-31", {10: 0.030})
        result = analyzer.get_ytd_data(datetime(2026, 7, 31), "FR")
        assert result is not None
        assert result["rates"][10] == pytest.approx(0.027)

    def test_ytd_outside_tolerance_returns_none(self, conn, analyzer):
        seed_month(conn, "2026-01-31", {10: 0.027})  # 30 jours après le 1er janvier, hors tolérance (10j)
        assert analyzer.get_ytd_data(datetime(2026, 7, 31), "FR") is None


class TestAnalyze:
    def test_mom_change_and_no_alert_below_threshold(self, conn, analyzer):
        seed_month(conn, "2026-06-30", {10: 0.0300})
        current = {
            "reference_date": datetime(2026, 7, 31), "country": "FR",
            "rates": {10: 0.0310}, "va": None, "source_file": "x.zip",
        }
        summary = analyzer.analyze(current)
        assert summary["changes_mom"][10] == pytest.approx(10.0)  # +10 bps, sous le seuil de 50
        assert summary["alerts"] == []

    def test_alert_triggered_above_mom_threshold(self, conn, analyzer):
        seed_month(conn, "2026-06-30", {10: 0.0300})
        current = {
            "reference_date": datetime(2026, 7, 31), "country": "FR",
            "rates": {10: 0.0360}, "va": None, "source_file": "x.zip",  # +60 bps > seuil 50
        }
        summary = analyzer.analyze(current)
        assert len(summary["alerts"]) == 1
        assert "10Y" in summary["alerts"][0]

    def test_metadata_attached_when_available(self, conn, analyzer):
        seed_metadata(conn, "2026-07-31", va_type="WITH_VA", va=0.0013, llp=20)
        current = {
            "reference_date": datetime(2026, 7, 31), "country": "FR",
            "rates": {10: 0.03}, "va": 0.0013, "source_file": "x.zip",
        }
        summary = analyzer.analyze(current)
        assert summary["metadata"]["LLP"] == 20

    def test_no_metadata_row_omits_metadata_key(self, analyzer):
        current = {
            "reference_date": datetime(2026, 7, 31), "country": "FR",
            "rates": {10: 0.03}, "va": None, "source_file": "x.zip",
        }
        summary = analyzer.analyze(current)
        assert "metadata" not in summary


class TestDetectAlerts:
    def test_mom_alert_direction_wording(self, analyzer):
        summary = {"changes_mom": {10: 60.0}, "changes_ytd": {}}
        alerts = analyzer._detect_alerts(summary)
        assert "hausse" in alerts[0]

    def test_mom_alert_negative_direction_wording(self, analyzer):
        summary = {"changes_mom": {10: -60.0}, "changes_ytd": {}}
        alerts = analyzer._detect_alerts(summary)
        assert "baisse" in alerts[0]

    def test_va_change_never_triggers_alert(self, analyzer):
        # "va" est une clé spéciale de changes_mom/ytd, jamais une maturité à alerter
        summary = {"changes_mom": {"va": 500.0}, "changes_ytd": {}}
        assert analyzer._detect_alerts(summary) == []

    def test_ytd_uses_its_own_higher_threshold(self, analyzer):
        # 60 bps déclenche en M/M (seuil 50) mais pas en YTD (seuil 100)
        summary = {"changes_mom": {}, "changes_ytd": {10: 60.0}}
        assert analyzer._detect_alerts(summary) == []
