"""
Module de traitement et extraction des données EIOPA
"""
import fnmatch
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import EXPECTED_EXCEL_FILES, EXCEL_SHEET_RFR, TARGET_COUNTRY, TARGET_MATURITIES, PROCESSED_DIR
from src.rfr_exporter import export_rfr_csv
from src.utils import setup_logging, parse_date_from_filename, safe_float_conversion, validate_rate

logger = setup_logging()


class EIOPAProcessor:
    """Traite un fichier ZIP EIOPA : extraction Excel, taux cibles et export CSV complets."""

    def __init__(self, zip_path: Path):
        self.zip_path = zip_path
        self.reference_date = parse_date_from_filename(zip_path.name)
        if not self.reference_date:
            logger.warning(f"Impossible d'extraire la date de : {zip_path.name}")

    # ------------------------------------------------------------------
    # ZIP
    # ------------------------------------------------------------------

    def list_files_in_zip(self) -> List[str]:
        try:
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                return zf.namelist()
        except zipfile.BadZipFile as e:
            logger.error(f"Fichier ZIP corrompu : {e}")
            return []

    def find_excel_file(self) -> Optional[str]:
        """Trouve le fichier Excel Term Structures dans le ZIP."""
        files = self.list_files_in_zip()
        for pattern in EXPECTED_EXCEL_FILES:
            for filename in files:
                if filename.lower().endswith((".xlsx", ".xls")) and (
                    fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filename, f"*{pattern}")
                ):
                    logger.info(f"Fichier Excel trouvé : {filename}")
                    return filename
        logger.warning(f"Aucun fichier Excel trouvé pour les patterns : {EXPECTED_EXCEL_FILES}")
        return None

    def extract_excel_from_zip(self, excel_filename: str) -> Optional[Path]:
        """Extrait le fichier Excel du ZIP vers PROCESSED_DIR."""
        try:
            output_path = PROCESSED_DIR / Path(excel_filename).name
            with zipfile.ZipFile(self.zip_path, "r") as zf:
                with zf.open(excel_filename) as src, open(output_path, "wb") as dst:
                    dst.write(src.read())
            logger.info(f"Fichier Excel extrait : {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Erreur extraction : {e}")
            return None

    # ------------------------------------------------------------------
    # Lecture Excel
    # ------------------------------------------------------------------

    def _read_sheet(self, excel_path: Path, sheet_name: str) -> Optional[pd.DataFrame]:
        """Lit un onglet EIOPA (header ligne 2, index maturité colonne 2)."""
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=1, index_col=1)
            if df.empty:
                logger.warning(f"Onglet '{sheet_name}' vide.")
                return None
            logger.info(f"Onglet '{sheet_name}' lu : {len(df)} lignes, {len(df.columns)} colonnes.")
            return df
        except ValueError as e:
            logger.error(f"Onglet '{sheet_name}' introuvable : {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lecture '{sheet_name}' : {e}")
            return None

    def extract_country_rates(self, df: pd.DataFrame, country_code: str = TARGET_COUNTRY) -> Optional[Dict[int, float]]:
        """Extrait les taux TARGET_MATURITIES pour un pays depuis le DataFrame pivot."""
        country_aliases = {
            "FR": ["France", "French", "FR"],
            "DE": ["Germany", "German", "DE"],
            "IT": ["Italy", "Italian", "IT"],
            "ES": ["Spain", "Spanish", "ES"],
            "EUR": ["Euro", "EUR", "Eurozone"],
            "GB": ["United Kingdom", "UK", "GB", "GBP"],
            "US": ["United States", "USA", "US", "USD"],
        }
        country_column = None
        for name in country_aliases.get(country_code, [country_code]):
            for col in df.columns:
                if name.lower() in str(col).lower():
                    country_column = col
                    break
            if country_column:
                break

        if country_column is None:
            logger.error(f"Colonne pays '{country_code}' introuvable. Colonnes : {list(df.columns[:10])}")
            return None

        rates = {}
        for maturity in TARGET_MATURITIES:
            mask = df.index == maturity
            if not mask.any():
                logger.warning(f"Maturité {maturity} non trouvée.")
                continue
            value = safe_float_conversion(df.loc[mask, country_column].iloc[0])
            if value is not None and validate_rate(value):
                rates[maturity] = value
            elif value is not None:
                logger.warning(f"Taux invalide pour maturité {maturity}Y : {value}")

        if not rates:
            logger.error("Aucun taux extrait.")
            return None
        return rates

    # ------------------------------------------------------------------
    # Pipeline principal
    # ------------------------------------------------------------------

    def process(self) -> Optional[Dict]:
        """
        Pipeline complet :
          1. Trouve et extrait le fichier Excel du ZIP
          2. Extrait les taux TARGET_MATURITIES pour TARGET_COUNTRY
          3. Génère RFR_[DATE]_NO_VA.csv et RFR_[DATE]_WITH_VA.csv (maturités 0–150)

        Retourne un dictionnaire avec les taux et les chemins des CSV générés.
        """
        logger.info(f"Traitement : {self.zip_path.name}")

        excel_filename = self.find_excel_file()
        if not excel_filename:
            return None

        excel_path = self.extract_excel_from_zip(excel_filename)
        if not excel_path:
            return None

        df = self._read_sheet(excel_path, EXCEL_SHEET_RFR)
        if df is None:
            return None

        rates = self.extract_country_rates(df, TARGET_COUNTRY)
        if not rates:
            return None

        result = {
            "reference_date": self.reference_date,
            "country": TARGET_COUNTRY,
            "rates": rates,
            "va": None,
            "source_file": self.zip_path.name,
        }

        # Export CSV complets (maturités 0–150)
        date_str = self.reference_date.strftime("%Y%m%d")
        no_va_path, with_va_path = export_rfr_csv(
            excel_path=excel_path,
            reference_date_str=date_str,
            country_code=TARGET_COUNTRY,
            output_dir=PROCESSED_DIR,
        )
        result["rfr_no_va_csv"]   = no_va_path
        result["rfr_with_va_csv"] = with_va_path

        logger.info(f"Traitement terminé : {len(rates)} taux extraits.")
        if no_va_path:
            logger.info(f"CSV NO_VA   : {no_va_path.name}")
        if with_va_path:
            logger.info(f"CSV WITH_VA : {with_va_path.name}")

        return result