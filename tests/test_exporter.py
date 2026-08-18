import pandas as pd
import pytest

from eiopa_rfr.exporter import available_export_dates, export_curve_csv
from tests.conftest import seed_full_curve


class TestExportCurveCsv:
    def test_invalid_va_type_raises(self, test_db_path, tmp_path):
        with pytest.raises(ValueError, match="va_type invalide"):
            export_curve_csv("2026-07-31", "BOGUS", output_dir=tmp_path, db_path=test_db_path)

    def test_no_data_for_date_raises_helpful_error(self, test_db_path, tmp_path):
        with pytest.raises(ValueError, match="Aucune courbe"):
            export_curve_csv("2026-07-31", "NO_VA", output_dir=tmp_path, db_path=test_db_path)

    def test_writes_expected_filename_and_columns(self, conn, test_db_path, tmp_path):
        seed_full_curve(conn, "2026-07-31", va_type="NO_VA", base=0.02, up=0.04, down=0.01)

        path = export_curve_csv("2026-07-31", "NO_VA", output_dir=tmp_path, db_path=test_db_path)

        assert path.name == "RFR_20260731_NO_VA.csv"
        df = pd.read_csv(path)
        assert list(df.columns) == ["Maturity", "Base", "Up", "Down"]
        assert len(df) == 151

    def test_values_match_seeded_curve(self, conn, test_db_path, tmp_path):
        seed_full_curve(conn, "2026-07-31", va_type="WITH_VA", base=0.025, up=0.045, down=0.012)

        path = export_curve_csv("2026-07-31", "WITH_VA", output_dir=tmp_path, db_path=test_db_path)

        df = pd.read_csv(path).set_index("Maturity")
        assert df.loc[10, "Base"] == pytest.approx(0.025)
        assert df.loc[10, "Up"] == pytest.approx(0.045)
        assert df.loc[10, "Down"] == pytest.approx(0.012)

    def test_accepts_datetime_and_string_dates_identically(self, conn, test_db_path, tmp_path):
        from datetime import datetime
        seed_full_curve(conn, "2026-07-31")

        path_from_str = export_curve_csv("2026-07-31", "NO_VA", output_dir=tmp_path, db_path=test_db_path)
        path_from_dt = export_curve_csv(datetime(2026, 7, 31), "NO_VA", output_dir=tmp_path, db_path=test_db_path)

        assert path_from_str == path_from_dt


class TestAvailableExportDates:
    def test_empty_when_no_data(self, test_db_path):
        assert available_export_dates("FR", db_path=test_db_path) == []

    def test_sorted_descending(self, conn, test_db_path):
        seed_full_curve(conn, "2026-01-31")
        seed_full_curve(conn, "2026-07-31")
        assert available_export_dates("FR", db_path=test_db_path) == ["2026-07-31", "2026-01-31"]
