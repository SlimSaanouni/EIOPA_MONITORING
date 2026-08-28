"""
API FastAPI pour le dashboard EIOPA — remplace l'UI Streamlit (app.py,
désormais superflu) par un frontend statique (frontend/) consommant ce JSON.

Toute la logique métier reste dans les modules existants (analyzer,
downloader, ingestion, exporter, reporter, db) : ce module ne fait
qu'orchestrer les appels et sérialiser les résultats. Voir frontend/static/js/app.js
pour le détail des appels correspondant à chaque route.
"""
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from eiopa_rfr import db
from eiopa_rfr.analyzer import EIOPAAnalyzer
from eiopa_rfr.config import PROCESSED_DIR, TARGET_COUNTRY, TARGET_MATURITIES
from eiopa_rfr.downloader import EIOPADownloader
from eiopa_rfr.exporter import available_export_dates, export_curve_csv
from eiopa_rfr.ingestion import ingest_zip
from eiopa_rfr.reporter import EIOPAReporter
from eiopa_rfr.utils import setup_logging

logger = setup_logging()

# frontend/ et assets/ vivent sous src/eiopa_rfr/ (et non à la racine du
# dépôt) précisément pour pouvoir être embarqués dans le package (voir
# [tool.setuptools.package-data] dans pyproject.toml) : StaticFiles a besoin
# de ces dossiers sur disque au démarrage, y compris en install standalone
# (non-éditable), où il n'existe pas de checkout git à côté du code.
_PACKAGE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = _PACKAGE_DIR / "frontend"
ASSETS_DIR = _PACKAGE_DIR / "assets"

# Même sémantique que READONLY_DASHBOARD côté Streamlit (st.secrets), mais
# lue depuis l'environnement — plus simple à régler sur une instance hébergée
# sans dépendance à un fichier secrets.toml spécifique à Streamlit.
READONLY_DASHBOARD = os.environ.get("READONLY_DASHBOARD", "").strip().lower() in ("1", "true", "yes")

EXPORT_FILENAME_RE = re.compile(r"^RFR_\d{8}_(NO_VA|WITH_VA)\.csv$")

app = FastAPI(title="EIOPA RFR Monitoring API")


@app.middleware("http")
async def _no_cache_frontend(request: Request, call_next) -> Response:
    """La page et les assets statiques (JS/CSS) ne doivent jamais être
    resservis depuis le cache du navigateur : un onglet qui recharge la page
    doit toujours voir le code à jour, pas une version figée au premier
    chargement — même sans hard refresh explicite.

    Tout ce qui n'est pas une route /api/* passe par les mounts StaticFiles
    (/assets/* et le mount "/" qui sert aussi index.html via html=True) : on
    applique no-store à tout sauf /api/*, plutôt que de lister chaque chemin
    statique. Ça laisse un endpoint comme /api/export/download/{filename}
    (export CSV généré une fois, potentiellement volumineux) avec son
    comportement de cache par défaut.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


_analyzer = EIOPAAnalyzer()


def _bps_delta(current, previous) -> Optional[dict]:
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return None
    change_bps = (current - previous) * 10000
    return {"bps": round(change_bps, 1), "direction": "up" if change_bps >= 0 else "down"}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@app.get("/api/config")
def get_config():
    history = _analyzer.historical_data
    latest_date = None
    if not history.empty:
        latest_date = history["reference_date"].max().strftime("%Y-%m-%d")
    return {
        "country": TARGET_COUNTRY,
        "maturities": TARGET_MATURITIES,
        "readonly": READONLY_DASHBOARD,
        "latest_date": latest_date,
    }


# ---------------------------------------------------------------------------
# Vue d'ensemble
# ---------------------------------------------------------------------------

@app.get("/api/overview")
def get_overview():
    history = _analyzer.historical_data
    if history.empty:
        return {"empty": True}

    latest_row = history.iloc[-1]
    previous_row = history.iloc[-2] if len(history) >= 2 else None
    latest_date = latest_row["reference_date"]

    stats = []
    for maturity in TARGET_MATURITIES:
        col = f"rate_{maturity}y"
        if col in latest_row and pd.notna(latest_row[col]):
            prev_val = previous_row[col] if previous_row is not None else None
            stats.append({
                "maturity": maturity,
                "rate": float(latest_row[col]),
                "delta": _bps_delta(latest_row[col], prev_val),
            })

    va = None
    if pd.notna(latest_row["va"]):
        prev_va = previous_row["va"] if previous_row is not None else None
        va = {"rate": float(latest_row["va"]), "delta": _bps_delta(latest_row["va"], prev_va)}

    issues = _analyzer.get_ingestion_issues()

    rates = {
        m: float(latest_row[f"rate_{m}y"])
        for m in TARGET_MATURITIES
        if f"rate_{m}y" in latest_row and pd.notna(latest_row[f"rate_{m}y"])
    }
    maturities_sorted = sorted(rates.keys())
    curve = {"maturities": maturities_sorted, "rates": [rates[m] for m in maturities_sorted]}

    six_months_ago = latest_date - timedelta(days=180)
    ts = _analyzer.get_time_series(country=TARGET_COUNTRY, maturity=10, start_date=six_months_ago)
    series_10y = {
        "dates": ts["reference_date"].dt.strftime("%Y-%m-%d").tolist() if not ts.empty else [],
        "rates": ts["rate"].tolist() if not ts.empty else [],
    }

    return {
        "empty": False,
        "latest_date": latest_date.strftime("%Y-%m-%d"),
        "stats": stats,
        "va": va,
        "issues": [{"reference_date": i["reference_date"], "status": i["status"]} for i in issues[:5]],
        "issues_total": len(issues),
        "curve": curve,
        "series_10y": series_10y,
    }


# ---------------------------------------------------------------------------
# Mise à jour
# ---------------------------------------------------------------------------

@app.get("/api/update/available")
def get_available_updates():
    conn = db.get_connection()
    try:
        local_dates = set(db.get_dates(conn, TARGET_COUNTRY))
    finally:
        conn.close()

    try:
        downloader = EIOPADownloader()
        available_files = downloader.get_available_files()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Impossible de contacter l'EIOPA : {e}") from e

    files = []
    for filename, url, file_date in available_files:
        date_str = file_date.strftime("%Y-%m-%d")
        files.append({
            "date": date_str,
            "label": file_date.strftime("%d/%m/%Y"),
            "filename": filename,
            "url": url,
            "status": "done" if date_str in local_dates else "pending",
        })

    return {"readonly": READONLY_DASHBOARD, "files": files}


class UpdateItem(BaseModel):
    date: str
    label: str
    filename: str
    url: str


class UpdateRequest(BaseModel):
    items: List[UpdateItem]


@app.post("/api/update/run")
def run_update(payload: UpdateRequest):
    if READONLY_DASHBOARD:
        raise HTTPException(status_code=403, detail="Instance en lecture seule.")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Aucune date sélectionnée.")

    results = []
    any_success = False

    for item in payload.items:
        try:
            downloader = EIOPADownloader()
            zip_path = downloader.download_file(item.url, item.filename)
            if not zip_path:
                logger.error(f"[Mise à jour] Échec du téléchargement pour {item.label} ({item.filename})")
                results.append({"date": item.date, "label": item.label, "success": False, "message": "Échec du téléchargement"})
                continue

            current_data = ingest_zip(zip_path)
            analysis = _analyzer.analyze(current_data)
            EIOPAReporter.generate_text_report(analysis)

            message = f"{len(current_data['rates'])} taux extraits"
            if current_data["status"] == "PARTIAL":
                message += f" (partiel : {'; '.join(current_data['missing_maturities'][:3])})"
            results.append({"date": item.date, "label": item.label, "success": True, "message": message})
            any_success = True

        except Exception as e:
            logger.error(f"[Mise à jour] Échec du traitement pour {item.label} : {e}", exc_info=True)
            results.append({"date": item.date, "label": item.label, "success": False, "message": str(e)})

    if any_success:
        _analyzer.export_historical_csv()

    return {"results": results}


# ---------------------------------------------------------------------------
# Historique
# ---------------------------------------------------------------------------

@app.get("/api/historical/summary")
def get_historical_summary():
    df = _analyzer.historical_data
    if df.empty:
        return {"empty": True}
    issues = _analyzer.get_ingestion_issues()
    return {
        "empty": False,
        "count": len(df),
        "first_date": df["reference_date"].min().strftime("%Y-%m-%d"),
        "last_date": df["reference_date"].max().strftime("%Y-%m-%d"),
        "issues": issues,
    }


@app.get("/api/historical/series")
def get_historical_series(maturity: int, start: Optional[str] = None, end: Optional[str] = None):
    if maturity not in TARGET_MATURITIES:
        raise HTTPException(status_code=400, detail="Maturité invalide.")
    start_date = datetime.strptime(start, "%Y-%m-%d") if start else None
    end_date = datetime.strptime(end, "%Y-%m-%d") if end else None
    ts = _analyzer.get_time_series(country=TARGET_COUNTRY, maturity=maturity, start_date=start_date, end_date=end_date)
    if ts.empty:
        return {"dates": [], "rates": []}
    return {
        "dates": ts["reference_date"].dt.strftime("%Y-%m-%d").tolist(),
        "rates": ts["rate"].tolist(),
    }


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------

@app.get("/api/analysis/dates")
def get_analysis_dates():
    df = _analyzer.historical_data
    if df.empty:
        return {"dates": []}
    dates = sorted(df["reference_date"].dt.strftime("%Y-%m-%d").unique().tolist(), reverse=True)
    return {"dates": dates}


@app.get("/api/analysis/compare")
def get_analysis_compare(date1: str, date2: str):
    data1 = _analyzer.get_historical_data(TARGET_COUNTRY, date1)
    data2 = _analyzer.get_historical_data(TARGET_COUNTRY, date2)
    if not data1 or not data2:
        raise HTTPException(status_code=404, detail="Données manquantes pour les dates sélectionnées.")

    variations = []
    for maturity in sorted(data1["rates"].keys()):
        if maturity in data2["rates"]:
            rate1 = data1["rates"][maturity]
            rate2 = data2["rates"][maturity]
            variations.append({
                "maturity": maturity,
                "rate1": rate1,
                "rate2": rate2,
                "change_bps": round((rate1 - rate2) * 10000, 1),
                "change_pct": round((rate1 / rate2 - 1) * 100, 2) if rate2 else None,
            })

    return {
        "date1": {"date": date1, "rates": data1["rates"]},
        "date2": {"date": date2, "rates": data2["rates"]},
        "variations": variations,
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@app.get("/api/export/dates")
def get_export_dates():
    return {"dates": available_export_dates(TARGET_COUNTRY)}


class ExportRequest(BaseModel):
    date: str
    va_types: List[str]


@app.post("/api/export")
def post_export(payload: ExportRequest):
    generated = []
    errors = []
    for va_type in payload.va_types:
        try:
            path = export_curve_csv(payload.date, va_type)
            generated.append({"va_type": va_type, "filename": path.name})
        except ValueError as e:
            errors.append({"va_type": va_type, "message": str(e)})
    return {"generated": generated, "errors": errors}


@app.get("/api/export/download/{filename}")
def download_export(filename: str):
    if not EXPORT_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
    path = PROCESSED_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return FileResponse(path, media_type="text/csv", filename=filename)


# ---------------------------------------------------------------------------
# Frontend statique — routes /api/* déclarées au-dessus prennent priorité
# sur ces montages, qui doivent donc rester en dernier.
# ---------------------------------------------------------------------------

app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
