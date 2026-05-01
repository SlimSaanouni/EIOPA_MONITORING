"""
Module d'export des courbes RFR EIOPA au format CSV standardisé.

Génère deux fichiers par publication mensuelle :
  - RFR_[DATE]_NO_VA.csv  : taux spot + chocs IR sans Volatility Adjustment
  - RFR_[DATE]_WITH_VA.csv : taux spot + chocs IR avec Volatility Adjustment

Chaque fichier contient 151 lignes (maturités 0 à 150) et 4 colonnes :
  Maturity | Base | IR Upward Shock | IR Downward shock

Les chocs IR sont recalculés en Python depuis les onglets base et Shocks,
car les onglets de choc contiennent des formules non évaluées par openpyxl.

Formules EIOPA :
  UP   = ROUND(base + MAX(0.01, shock_up   * ABS(base)), 5)
  DOWN = ROUND(base - MAX(0.00, shock_down * ABS(base)), 5)
"""

from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import numpy as np

from config import TARGET_COUNTRY, PROCESSED_DIR
from src.utils import setup_logging

logger = setup_logging()

# ---------------------------------------------------------------------------
# Onglets source
# ---------------------------------------------------------------------------
SHEET_NO_VA_BASE   = "RFR_spot_no_VA"
SHEET_WITH_VA_BASE = "RFR_spot_with_VA"
SHEET_SHOCKS       = "Shocks"

# Structure de l'onglet Shocks (0-indexé, header=None)
SHOCKS_MATURITY_COL = 1   # colonne maturité
SHOCKS_DOWN_COL     = 3   # colonne shock downwards
SHOCKS_UP_COL       = 4   # colonne shock upwards
SHOCKS_SKIPROWS     = 10  # lignes de métadonnées avant les données

# Nombre de maturités attendues (0 à 150 inclus)
EXPECTED_MATURITIES = list(range(0, 151))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_country_column(df: pd.DataFrame, country_code: str) -> Optional[str]:
    """Localise la colonne pays dans un DataFrame pivot EIOPA."""
    country_aliases = {
        "FR": ["france", "french", "fr"],
        "DE": ["germany", "german", "de"],
        "IT": ["italy", "italian", "it"],
        "ES": ["spain", "spanish", "es"],
        "EUR": ["euro", "eur", "eurozone"],
        "GB": ["united kingdom", "uk", "gb", "gbp"],
        "US": ["united states", "usa", "us", "usd"],
    }
    targets = country_aliases.get(country_code.upper(), [country_code.lower()])
    for col in df.columns:
        if any(alias in str(col).lower() for alias in targets):
            return col
    logger.error(f"Colonne pays '{country_code}' introuvable. Colonnes : {list(df.columns[:15])}")
    return None


def _read_base_sheet(excel_path: Path, sheet_name: str) -> Optional[pd.DataFrame]:
    """Lit un onglet base EIOPA (header ligne 2, index maturité colonne 2)."""
    try:
        df = pd.read_excel(
            excel_path, sheet_name=sheet_name,
            engine="openpyxl", header=1, index_col=1,
        )
        if df.empty:
            logger.warning(f"Onglet '{sheet_name}' vide.")
            return None
        logger.info(f"Onglet '{sheet_name}' lu : {len(df)} lignes.")
        return df
    except Exception as exc:
        logger.error(f"Erreur lecture '{sheet_name}' : {exc}")
        return None


def _read_shocks(excel_path: Path) -> Optional[pd.DataFrame]:
    """
    Lit l'onglet Shocks et retourne un DataFrame indexé par maturité (int)
    avec colonnes 'up' et 'down'.
    """
    try:
        df = pd.read_excel(
            excel_path, sheet_name=SHEET_SHOCKS,
            engine="openpyxl", header=None, skiprows=SHOCKS_SKIPROWS,
        )
        shocks = pd.DataFrame({
            "maturity": pd.to_numeric(df.iloc[:, SHOCKS_MATURITY_COL], errors="coerce"),
            "up":       pd.to_numeric(df.iloc[:, SHOCKS_UP_COL],       errors="coerce"),
            "down":     pd.to_numeric(df.iloc[:, SHOCKS_DOWN_COL],     errors="coerce"),
        }).dropna(subset=["maturity"])

        shocks["maturity"] = shocks["maturity"].astype(int)
        shocks = shocks.set_index("maturity")
        logger.info(f"Onglet Shocks lu : {len(shocks)} maturités.")
        return shocks
    except Exception as exc:
        logger.error(f"Erreur lecture Shocks : {exc}")
        return None


def _extract_base_series(df: pd.DataFrame, country_col: str) -> pd.Series:
    """Extrait la série de taux base pour le pays, indexée par maturité (int)."""
    series = df[country_col].copy()
    numeric_index = pd.to_numeric(series.index, errors="coerce")
    series = series[numeric_index.notna()]
    series.index = numeric_index[numeric_index.notna()].astype(int)
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _compute_shocks(base: pd.Series, shocks: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """
    Recalcule les chocs IR selon les formules EIOPA :
      UP   = ROUND(base + MAX(0.01, shock_up   * ABS(base)), 5)
      DOWN = ROUND(base - MAX(0.00, shock_down * ABS(base)), 5)

    Retourne (up_series, down_series) indexées par maturité.
    """
    idx = pd.Index(EXPECTED_MATURITIES)

    base_r   = base.reindex(idx, fill_value=0.0)
    shock_up  = shocks["up"].reindex(idx, fill_value=0.0)
    shock_dn  = shocks["down"].reindex(idx, fill_value=0.0)

    up   = np.round(base_r + np.maximum(0.01, shock_up  * base_r.abs()), 5)
    down = np.round(base_r - np.maximum(0.00, shock_dn  * base_r.abs()), 5)

    # Maturité 0 → zéro
    up.loc[0]   = 0.0
    down.loc[0] = 0.0

    return up, down


def _build_output_df(
    base_series: pd.Series,
    up_series: pd.Series,
    down_series: pd.Series,
) -> pd.DataFrame:
    """Assemble le DataFrame de sortie (151 lignes, maturités 0–150)."""
    idx = pd.Index(EXPECTED_MATURITIES, name="Maturity")
    df = pd.DataFrame(index=idx)
    df["Base"]               = base_series.reindex(idx, fill_value=0.0)
    df["IR Upward Shock"]    = up_series.reindex(idx, fill_value=0.0)
    df[" IR Downward shock"] = down_series.reindex(idx, fill_value=0.0)
    df.loc[0, :] = 0.0
    return df.reset_index()


# ---------------------------------------------------------------------------
# Fonction principale publique
# ---------------------------------------------------------------------------

def export_rfr_csv(
    excel_path: Path,
    reference_date_str: str,
    country_code: str = TARGET_COUNTRY,
    output_dir: Path = PROCESSED_DIR,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Génère RFR_[DATE]_NO_VA.csv et RFR_[DATE]_WITH_VA.csv.

    Parameters
    ----------
    excel_path : Path
        Fichier Excel extrait du ZIP EIOPA.
    reference_date_str : str
        Date au format YYYYMMDD.
    country_code : str
        Code pays (config.TARGET_COUNTRY).
    output_dir : Path
        Dossier de destination.

    Returns
    -------
    (path_no_va, path_with_va)
    """
    logger.info(f"Export RFR CSV — date={reference_date_str}, pays={country_code}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Chocs communs aux deux blocs
    shocks = _read_shocks(excel_path)
    if shocks is None:
        logger.error("Onglet Shocks illisible — export annulé.")
        return None, None

    no_va_path = _export_bloc(
        excel_path=excel_path,
        sheet_base=SHEET_NO_VA_BASE,
        shocks=shocks,
        country_code=country_code,
        label="NO_VA",
        reference_date_str=reference_date_str,
        output_dir=output_dir,
    )

    with_va_path = _export_bloc(
        excel_path=excel_path,
        sheet_base=SHEET_WITH_VA_BASE,
        shocks=shocks,
        country_code=country_code,
        label="WITH_VA",
        reference_date_str=reference_date_str,
        output_dir=output_dir,
    )

    return no_va_path, with_va_path


def _export_bloc(
    excel_path: Path,
    sheet_base: str,
    shocks: pd.DataFrame,
    country_code: str,
    label: str,
    reference_date_str: str,
    output_dir: Path,
) -> Optional[Path]:
    """Lit l'onglet base, recalcule les chocs, écrit le CSV."""
    df_base = _read_base_sheet(excel_path, sheet_base)
    if df_base is None:
        logger.error(f"[{label}] Onglet base manquant.")
        return None

    col_base = _find_country_column(df_base, country_code)
    if col_base is None:
        logger.error(f"[{label}] Colonne pays introuvable.")
        return None

    base_series = _extract_base_series(df_base, col_base)
    up_series, down_series = _compute_shocks(base_series, shocks)

    output_df   = _build_output_df(base_series, up_series, down_series)
    filename    = f"RFR_{reference_date_str}_{label}.csv"
    output_path = output_dir / filename

    output_df.to_csv(output_path, index=False, float_format="%.5f")
    logger.info(f"[{label}] CSV écrit : {output_path} ({len(output_df)} lignes)")
    return output_path