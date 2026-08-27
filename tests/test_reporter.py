from datetime import datetime

from eiopa_rfr.reporter import EIOPAReporter


def make_analysis(**overrides):
    analysis = {
        "reference_date": datetime(2026, 7, 31),
        "country": "FR",
        "rates": {1: 0.028, 10: 0.030},
        "va": 0.0013,
        "changes_mom": {1: 12.0, 10: -60.0, "va": 2.0},
        "changes_ytd": {1: 30.0, 10: 110.0, "va": 5.0},
        "previous_date": datetime(2026, 6, 30),
        "ytd_date": datetime(2026, 1, 1),
        "source_file": "EIOPA_RFR_20260731.zip",
        "alerts": ["⚠️ Variation M/M importante (10Y) : baisse de -60.0 bps"],
    }
    analysis.update(overrides)
    return analysis


class TestGenerateTextReport:
    def test_includes_header_fields(self):
        report = EIOPAReporter.generate_text_report(make_analysis())
        assert "31/07/2026" in report
        assert "FR" in report
        assert "EIOPA_RFR_20260731.zip" in report

    def test_includes_rates_and_va(self):
        report = EIOPAReporter.generate_text_report(make_analysis())
        assert "1Y" in report
        assert "2.80%" in report  # rate_1y formaté en %
        assert "Volatility Adjustment (VA) : 0.13%" in report

    def test_va_absent_shown_as_non_disponible(self):
        report = EIOPAReporter.generate_text_report(make_analysis(va=None))
        assert "Volatility Adjustment (VA) : Non disponible" in report

    def test_mom_indicator_uses_configured_threshold_not_hardcoded_50(self, monkeypatch):
        # Variation de 60 bps : sous le seuil ALERT_THRESHOLD_MOM par défaut (50) ->
        # rouge, mais si le seuil est relevé à 75 (cas d'une instance qui l'a
        # surchargé via EIOPA_ALERT_THRESHOLD_MOM), l'indicateur doit suivre —
        # sinon le rapport texte contredit les alertes réellement détectées
        # par analyzer._detect_alerts(), qui lit ce même seuil.
        monkeypatch.setattr("eiopa_rfr.reporter.ALERT_THRESHOLD_MOM", 75)
        report = EIOPAReporter.generate_text_report(make_analysis())
        lines = [l for l in report.splitlines() if "Taux 10Y" in l and "bps" in l]
        assert lines, "ligne de variation M/M pour 10Y introuvable"
        assert "🟢" in lines[0]
        assert "🔴" not in lines[0]

    def test_ytd_indicator_uses_configured_threshold_not_hardcoded_100(self, monkeypatch):
        monkeypatch.setattr("eiopa_rfr.reporter.ALERT_THRESHOLD_YTD", 200)
        report = EIOPAReporter.generate_text_report(make_analysis())
        ytd_section = report.split("ÉVOLUTIONS DEPUIS DÉBUT D'ANNÉE")[1]
        ytd_10y_line = [l for l in ytd_section.splitlines() if "Taux 10Y" in l][0]
        assert "🟢" in ytd_10y_line

    def test_no_alerts_shows_success_banner(self):
        report = EIOPAReporter.generate_text_report(make_analysis(alerts=[]))
        assert "Aucune variation anormale détectée" in report

    def test_writes_output_file(self, tmp_path):
        output_file = tmp_path / "report.txt"
        EIOPAReporter.generate_text_report(make_analysis(), output_file)
        assert output_file.exists()
        assert "FR" in output_file.read_text(encoding="utf-8")


class TestGenerateCsvReport:
    def test_writes_one_row_per_rate_plus_va(self, tmp_path):
        import pandas as pd

        output_file = tmp_path / "report.csv"
        EIOPAReporter.generate_csv_report(make_analysis(), output_file)

        df = pd.read_csv(output_file)
        assert set(df["type"]) == {"rate_1y", "rate_10y", "va"}
        assert len(df) == 3

        va_row = df[df["type"] == "va"].iloc[0]
        assert va_row["value"] == 0.0013
        assert va_row["change_mom_bps"] == 2.0

    def test_no_va_row_when_va_absent(self, tmp_path):
        import pandas as pd

        output_file = tmp_path / "report.csv"
        EIOPAReporter.generate_csv_report(make_analysis(va=None), output_file)

        df = pd.read_csv(output_file)
        assert "va" not in set(df["type"])
