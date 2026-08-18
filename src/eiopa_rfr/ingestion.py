"""
Ingestion unifiée EIOPA : ZIP -> SQLite, en un seul chemin d'extraction.

Remplace processor.py + rfr_exporter.py (retirés à l'étape suivante) : chaque
onglet base (RFR_spot_no_VA / RFR_spot_with_VA) est lu une seule fois, et sert
à la fois à construire la courbe complète (0-150, Base/Up/Down) et les
métadonnées scalaires (VA, LLP, Convergence, UFR, alpha, CRA, Coupon_freq),
au lieu d'être relu séparément par les deux anciens modules.

Formules EIOPA (onglet Shocks) :
    UP   = ROUND(base + MAX(0.01, shock_up   * ABS(base)), 5)
    DOWN = ROUND(base - MAX(0.00, shock_down * ABS(base)), 5)
"""
import fnmatch
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from eiopa_rfr.config import BPS_CONVERSION, EXPECTED_EXCEL_FILES, EXTRACTS_DIR, TARGET_COUNTRY
from eiopa_rfr import db
from eiopa_rfr.utils import parse_date_from_filename, setup_logging, validate_rate

logger = setup_logging()

SHEET_NAMES = {"NO_VA": "RFR_spot_no_VA", "WITH_VA": "RFR_spot_with_VA"}
SHEET_SHOCKS = "Shocks"
SHOCKS_MATURITY_COL = 1
SHOCKS_DOWN_COL     = 3
SHOCKS_UP_COL       = 4
SHOCKS_SKIPROWS     = 10
EXPECTED_MATURITIES = list(range(0, 151))
METADATA_LABELS     = ["Coupon_freq", "LLP", "Convergence", "UFR", "alpha", "CRA", "VA"]
SUMMARY_MATURITIES  = (1, 5, 10, 20, 30)  # affichage/alertes M-M, YTD

COUNTRY_ALIASES = {
    "FR":  ["france", "french", "fr"],
    "DE":  ["germany", "german", "de"],
    "IT":  ["italy", "italian", "it"],
    "ES":  ["spain", "spanish", "es"],
    "EUR": ["euro", "eur", "eurozone"],
    "GB":  ["united kingdom", "uk", "gb", "gbp"],
    "US":  ["united states", "usa", "us", "usd"],
}


def find_country_column(columns, country_code: str) -> Optional[str]:
    """Localise la colonne pays dans un DataFrame pivot EIOPA (alias insensibles à la casse)."""
    targets = COUNTRY_ALIASES.get(country_code.upper(), [country_code.lower()])
    for col in columns:
        if any(alias in str(col).lower() for alias in targets):
            return col
    return None


# ---------------------------------------------------------------------------
# ZIP / Excel
# ---------------------------------------------------------------------------

def _find_excel_in_zip(zip_path: Path) -> Optional[str]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    for pattern in EXPECTED_EXCEL_FILES:
        for filename in names:
            if filename.lower().endswith((".xlsx", ".xls")) and (
                fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filename, f"*{pattern}")
            ):
                return filename
    return None


def _extract_excel(zip_path: Path, excel_filename: str) -> Path:
    output_path = EXTRACTS_DIR / Path(excel_filename).name
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open(excel_filename) as src, open(output_path, "wb") as dst:
            dst.write(src.read())
    return output_path


def _read_base_sheet(excel_path: Path, sheet_name: str) -> Optional[pd.DataFrame]:
    """Lit un onglet base EIOPA : header ligne 2, index (label/maturité) colonne 2."""
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=1, index_col=1)
        if df.empty:
            logger.warning(f"Onglet '{sheet_name}' vide.")
            return None
        return df
    except Exception as exc:
        logger.error(f"Erreur lecture '{sheet_name}' : {exc}")
        return None


def _read_shocks(excel_path: Path) -> Optional[pd.DataFrame]:
    try:
        raw = pd.read_excel(
            excel_path, sheet_name=SHEET_SHOCKS,
            engine="openpyxl", header=None, skiprows=SHOCKS_SKIPROWS,
        )
        shocks = pd.DataFrame({
            "maturity": pd.to_numeric(raw.iloc[:, SHOCKS_MATURITY_COL], errors="coerce"),
            "up":       pd.to_numeric(raw.iloc[:, SHOCKS_UP_COL],       errors="coerce"),
            "down":     pd.to_numeric(raw.iloc[:, SHOCKS_DOWN_COL],     errors="coerce"),
        }).dropna(subset=["maturity"])
        shocks["maturity"] = shocks["maturity"].astype(int)
        return shocks.set_index("maturity")
    except Exception as exc:
        logger.error(f"Erreur lecture Shocks : {exc}")
        return None


# ---------------------------------------------------------------------------
# Extraction depuis un onglet base déjà chargé
# ---------------------------------------------------------------------------

def _extract_curve_series(df: pd.DataFrame, country_col: str) -> pd.Series:
    """Isole les lignes de maturité numérique (0-150) ; écarte les lignes de métadonnées (texte)."""
    series = df[country_col]
    numeric_index = pd.to_numeric(series.index, errors="coerce")
    series = series[numeric_index.notna()]
    series.index = numeric_index[numeric_index.notna()].astype(int)
    return pd.to_numeric(series, errors="coerce")


def _extract_metadata(df: pd.DataFrame, country_col: str) -> Dict[str, Optional[float]]:
    """Isole les lignes de label (Coupon_freq..VA), situées au-dessus des maturités numériques."""
    values = {}
    for label in METADATA_LABELS:
        if label in df.index:
            raw = df.loc[label, country_col]
            values[label] = float(raw) if pd.notna(raw) else None
        else:
            values[label] = None
    return values


def _compute_shocks(base: pd.Series, shocks: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    idx = pd.Index(EXPECTED_MATURITIES)
    base_r   = base.reindex(idx, fill_value=0.0)
    shock_up = shocks["up"].reindex(idx, fill_value=0.0)
    shock_dn = shocks["down"].reindex(idx, fill_value=0.0)

    up   = np.round(base_r + np.maximum(0.01, shock_up * base_r.abs()), 5)
    down = np.round(base_r - np.maximum(0.00, shock_dn * base_r.abs()), 5)
    up.loc[0], down.loc[0] = 0.0, 0.0
    return up, down


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def ingest_zip(zip_path: Path, country: str = TARGET_COUNTRY) -> Dict:
    """
    ZIP EIOPA -> lignes SQLite (curves + curve_metadata + ingestion_runs), en
    une seule transaction : soit le mois est ingéré en entier, soit rien ne
    change en base.

    Retourne un résumé {reference_date, country, rates, va, source_file,
    status, missing_maturities} — `rates`/`va` couvrent les 5 maturités clés
    pour compatibilité avec l'affichage existant (alertes M/M, YTD).
    """
    reference_date_dt = parse_date_from_filename(zip_path.name)
    if not reference_date_dt:
        raise ValueError(f"Date illisible dans le nom de fichier : {zip_path.name}")
    reference_date = reference_date_dt.strftime("%Y-%m-%d")

    excel_filename = _find_excel_in_zip(zip_path)
    if not excel_filename:
        _record_failure(reference_date, country, zip_path.name, "Fichier Excel Term Structures introuvable dans le ZIP.")
        raise ValueError("Fichier Excel Term Structures introuvable dans le ZIP.")

    excel_path = _extract_excel(zip_path, excel_filename)

    shocks = _read_shocks(excel_path)
    if shocks is None:
        _record_failure(reference_date, country, zip_path.name, "Onglet Shocks illisible.")
        raise ValueError("Onglet Shocks illisible.")

    curve_rows: List[Tuple] = []
    metadata_rows: List[Dict] = []
    missing: List[str] = []
    summary_rates: Dict[int, float] = {}
    summary_va: Optional[float] = None

    for va_type, sheet_name in SHEET_NAMES.items():
        df = _read_base_sheet(excel_path, sheet_name)
        if df is None:
            missing.append(f"{va_type}: onglet illisible")
            continue

        country_col = find_country_column(df.columns, country)
        if country_col is None:
            missing.append(f"{va_type}: colonne pays introuvable")
            continue

        base_series = _extract_curve_series(df, country_col)
        base_filled = base_series.reindex(EXPECTED_MATURITIES).fillna(0.0)
        up_series, down_series = _compute_shocks(base_filled, shocks)

        for maturity in EXPECTED_MATURITIES:
            raw = base_series.get(maturity)
            # Maturité 0 : jamais publiée par l'EIOPA (la série démarre à 1),
            # 0.0 est la convention attendue, pas une anomalie à signaler.
            if maturity != 0 and (raw is None or pd.isna(raw)):
                missing.append(f"{va_type}: maturité {maturity} manquante (0.0 substitué)")
            curve_rows.append((reference_date, country, va_type, "BASE", maturity, float(base_filled.loc[maturity])))
            curve_rows.append((reference_date, country, va_type, "UP",   maturity, float(up_series.loc[maturity])))
            curve_rows.append((reference_date, country, va_type, "DOWN", maturity, float(down_series.loc[maturity])))

        meta = _extract_metadata(df, country_col)
        va_decimal = (meta["VA"] / BPS_CONVERSION) if meta["VA"] is not None else None
        metadata_rows.append({
            "reference_date": reference_date, "country": country, "va_type": va_type,
            "coupon_freq": meta["Coupon_freq"], "llp": meta["LLP"], "convergence": meta["Convergence"],
            "ufr": meta["UFR"], "alpha": meta["alpha"], "cra": meta["CRA"], "va": va_decimal,
        })

        if va_type == "NO_VA":
            for maturity in SUMMARY_MATURITIES:
                rate = base_series.get(maturity)
                if rate is not None and pd.notna(rate) and validate_rate(rate):
                    summary_rates[maturity] = float(rate)
        else:
            summary_va = va_decimal

    if not curve_rows:
        _record_failure(reference_date, country, zip_path.name, "Aucune courbe extraite (NO_VA et WITH_VA en échec).")
        raise ValueError("Aucune courbe extraite.")

    status = "PARTIAL" if missing else "SUCCESS"

    with db.session() as conn:
        db.upsert_curve_rows(conn, curve_rows)
        for meta_row in metadata_rows:
            db.upsert_metadata(conn, meta_row)
        db.record_ingestion_run(
            conn, reference_date=reference_date, country=country, source_file=zip_path.name,
            status=status, missing_maturities="; ".join(missing) if missing else None,
        )

    logger.info(
        f"Ingestion {status} : {reference_date} — "
        f"{len(curve_rows)} lignes de courbe, {len(metadata_rows)} lignes de métadonnées."
    )
    if missing:
        logger.warning(f"Ingestion partielle ({len(missing)} anomalies) : {'; '.join(missing[:10])}")

    return {
        "reference_date": reference_date_dt,
        "country": country,
        "rates": summary_rates,
        "va": summary_va,
        "source_file": zip_path.name,
        "status": status,
        "missing_maturities": missing,
    }


def _record_failure(reference_date: str, country: str, source_file: str, reason: str) -> None:
    with db.session() as conn:
        db.record_ingestion_run(
            conn, reference_date=reference_date, country=country, source_file=source_file,
            status="FAILED", notes=reason,
        )
