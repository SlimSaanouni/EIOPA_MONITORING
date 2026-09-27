"""`eiopa-rfr --export --result-json` : contrat lu par les pipelines du
Cockpit ALM (chemins réels des courbes exportées, statut)."""

import json
from datetime import datetime

import pytest

from eiopa_rfr import exporter
from eiopa_rfr.main import export_curves


def test_export_result_json_lists_exported_curves(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, "export_curve_csv",
                        lambda date, vt: tmp_path / f"RFR_20250630_{vt}.csv")
    result = tmp_path / "result.json"

    with pytest.raises(SystemExit) as exc:
        export_curves(datetime(2025, 6, 30), "BOTH", result_json=result)

    assert exc.value.code == 0
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["schema"] == 1 and payload["module"] == "eiopa_rfr" and payload["ok"] is True
    assert payload["outputs"] == {
        "NO_VA": str((tmp_path / "RFR_20250630_NO_VA.csv").resolve()),
        "WITH_VA": str((tmp_path / "RFR_20250630_WITH_VA.csv").resolve()),
    }
    assert payload["metrics"]["date"] == "2025-06-30"


def test_export_result_json_reports_missing_curve(tmp_path, monkeypatch):
    def _missing(date, vt):
        raise ValueError("Aucune courbe NO_VA en base")
    monkeypatch.setattr(exporter, "export_curve_csv", _missing)
    result = tmp_path / "result.json"

    with pytest.raises(SystemExit) as exc:
        export_curves(datetime(1999, 1, 31), "NO_VA", result_json=result)

    assert exc.value.code == 1
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["outputs"] == {}
    assert "Aucune courbe" in payload["error"]
