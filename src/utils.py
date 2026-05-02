"""
Fonctions utilitaires pour le système de monitoring EIOPA
"""
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from config import LOG_FORMAT, LOG_DATE_FORMAT, LOG_FILE, MIN_RATE, MAX_RATE


def setup_logging(log_file: Path = LOG_FILE) -> logging.Logger:
    logger = logging.getLogger("EIOPA_Monitor")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def parse_date_from_filename(filename: str) -> Optional[datetime]:
    """Extrait la date (YYYYMMDD) d'un nom de fichier EIOPA."""
    match = re.search(r"(\d{8})", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d")
        except ValueError:
            return None
    return None


def validate_rate(rate: float) -> bool:
    """Vérifie qu'un taux est dans la plage acceptable."""
    return MIN_RATE <= rate <= MAX_RATE


def safe_float_conversion(value) -> Optional[float]:
    """Convertit une valeur en float de manière sécurisée."""
    if pd.isna(value):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", ".").replace(" ", "")
        return float(value)
    except (ValueError, TypeError):
        return None


def calculate_bps_change(old_rate: float, new_rate: float) -> float:
    """Calcule la variation en points de base entre deux taux."""
    return (new_rate - old_rate) * 10000


def format_bps(bps: float) -> str:
    sign = "+" if bps >= 0 else ""
    return f"{sign}{bps:.1f} bps"


def format_rate_pct(rate: float) -> str:
    return f"{rate * 100:.2f}%"


def get_previous_month_date(reference_date: datetime) -> datetime:
    """Retourne le dernier jour du mois précédent."""
    return reference_date.replace(day=1) - timedelta(days=1)


def get_year_start_date(reference_date: datetime) -> datetime:
    """Retourne le 1er janvier de l'année de référence."""
    return datetime(reference_date.year, 1, 1)


def create_summary_dict(
    reference_date: datetime,
    country: str,
    rates: Dict[int, float],
    va: Optional[float],
    previous_rates: Optional[Dict[int, float]] = None,
    previous_va: Optional[float] = None,
    ytd_rates: Optional[Dict[int, float]] = None,
    ytd_va: Optional[float] = None,
) -> Dict:
    """Construit le dictionnaire de résumé avec variations M/M et YTD."""
    summary = {
        "reference_date": reference_date,
        "country": country,
        "rates": rates,
        "va": va,
        "changes_mom": {},
        "changes_ytd": {},
    }

    if previous_rates:
        for maturity in rates:
            if maturity in previous_rates:
                summary["changes_mom"][maturity] = calculate_bps_change(
                    previous_rates[maturity], rates[maturity]
                )
        if previous_va is not None and va is not None:
            summary["changes_mom"]["va"] = calculate_bps_change(previous_va, va)

    if ytd_rates:
        for maturity in rates:
            if maturity in ytd_rates:
                summary["changes_ytd"][maturity] = calculate_bps_change(
                    ytd_rates[maturity], rates[maturity]
                )
        if ytd_va is not None and va is not None:
            summary["changes_ytd"]["va"] = calculate_bps_change(ytd_va, va)

    return summary