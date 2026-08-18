"""
Export des courbes de taux au format interchange partagé par les outils
consommateurs (ESG, Asset_PTF) : Maturity,Base,Up,Down — voir data/processed/.

Le choix du type de courbe (NO_VA / WITH_VA) reste à la charge de la
personne qui exporte : ce module ne fixe aucun défaut, voir la doc externe
sur la convention à appliquer selon le consommateur cible.
"""
from pathlib import Path
from typing import List

import pandas as pd

from eiopa_rfr.config import HISTORICAL_DB, PROCESSED_DIR, TARGET_COUNTRY
from eiopa_rfr import db
from eiopa_rfr.utils import setup_logging

logger = setup_logging()

VA_TYPES = ("NO_VA", "WITH_VA")


def export_curve_csv(
    reference_date,
    va_type: str,
    country: str = TARGET_COUNTRY,
    output_dir: Path = PROCESSED_DIR,
    db_path: Path = HISTORICAL_DB,
) -> Path:
    """
    Écrit RFR_[DATE]_[VA_TYPE].csv (colonnes Maturity,Base,Up,Down,
    maturités 0-150) depuis historical.db.

    Args:
        reference_date: date de clôture (datetime, str 'YYYY-MM-DD', ou tout
            type accepté par pd.Timestamp)
        va_type: 'NO_VA' ou 'WITH_VA'
        country: code pays (config.TARGET_COUNTRY par défaut)
        output_dir: dossier de destination
        db_path: base à interroger (config.HISTORICAL_DB par défaut —
            paramétrable pour les tests)

    Raises:
        ValueError: va_type invalide, ou aucune courbe en base pour cette
            date/pays/va_type (mois jamais ingéré, ou ingestion en échec).
    """
    if va_type not in VA_TYPES:
        raise ValueError(f"va_type invalide : {va_type!r} (attendu {VA_TYPES})")

    ts = pd.Timestamp(reference_date)
    date_str = ts.strftime("%Y-%m-%d")
    date_compact = ts.strftime("%Y%m%d")

    conn = db.get_connection(db_path)
    try:
        base = db.get_curve(conn, date_str, country, va_type, "BASE")
        up   = db.get_curve(conn, date_str, country, va_type, "UP")
        down = db.get_curve(conn, date_str, country, va_type, "DOWN")
    finally:
        conn.close()

    if not base:
        raise ValueError(
            f"Aucune courbe {va_type} en base pour {country} au {date_str} — "
            f"ce mois a-t-il été ingéré (main.py --date {date_str}) ?"
        )
    if len(base) != 151:
        logger.warning(f"Courbe {va_type} {date_str} incomplète : {len(base)}/151 maturités.")

    maturities = sorted(base.keys())
    df = pd.DataFrame({
        "Maturity": maturities,
        "Base": [base[m] for m in maturities],
        "Up":   [up.get(m) for m in maturities],
        "Down": [down.get(m) for m in maturities],
    })

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"RFR_{date_compact}_{va_type}.csv"
    df.to_csv(output_path, index=False, float_format="%.5f")
    logger.info(f"Export écrit : {output_path} ({len(df)} lignes)")
    return output_path


def available_export_dates(country: str = TARGET_COUNTRY, db_path: Path = HISTORICAL_DB) -> List[str]:
    """Dates ('YYYY-MM-DD') disponibles en base pour l'export, triées décroissant."""
    conn = db.get_connection(db_path)
    try:
        dates = db.get_dates(conn, country)
    finally:
        conn.close()
    return sorted(dates, reverse=True)
