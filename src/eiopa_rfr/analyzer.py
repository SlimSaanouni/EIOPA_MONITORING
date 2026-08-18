"""
Module d'analyse et de comparaison des données EIOPA — lit la base SQLite
(historical.db), écrite par src/ingestion.py. Ce module ne fait plus
qu'interroger : l'écriture est entièrement du ressort de l'ingestion.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from eiopa_rfr.config import (
    ALERT_THRESHOLD_MOM, ALERT_THRESHOLD_YTD, HISTORICAL_DB, HISTORICAL_FILE,
    TARGET_COUNTRY, TARGET_MATURITIES,
)
from eiopa_rfr import db
from eiopa_rfr.utils import (
    create_summary_dict, format_bps, get_previous_month_date, get_year_start_date,
    setup_logging,
)

logger = setup_logging()

# Métadonnées lues depuis curve_metadata (colonnes DB) -> clés attendues par reporter.py
METADATA_KEY_MAP = {
    "coupon_freq": "Coupon_freq",
    "llp":         "LLP",
    "convergence": "Convergence",
    "ufr":         "UFR",
    "alpha":       "alpha",
    "cra":         "CRA",
}


def _date_str(d) -> str:
    """Normalise une date (datetime, pd.Timestamp, np.datetime64, date) en 'YYYY-MM-DD'."""
    return pd.Timestamp(d).strftime("%Y-%m-%d")


class EIOPAAnalyzer:
    """Analyseur de données EIOPA — lecture seule sur historical.db."""

    def __init__(self, db_path: Path = HISTORICAL_DB):
        self.db_path = db_path

    def _connect(self):
        return db.get_connection(self.db_path)

    # ------------------------------------------------------------------
    # Résumé "5 maturités clés" — remplace l'ancien historical.csv en mémoire
    # ------------------------------------------------------------------

    def historical_summary(self, country: str = TARGET_COUNTRY) -> pd.DataFrame:
        """
        DataFrame [reference_date, country, rate_1y, ..., rate_30y, va] —
        même forme que l'ancien historical.csv, reconstruite depuis curves
        (BASE/NO_VA) et curve_metadata (WITH_VA.va) à chaque appel.
        """
        conn = self._connect()
        try:
            dates = db.get_dates(conn, country)
            rows = []
            for reference_date in dates:
                row = {"reference_date": reference_date, "country": country}
                for maturity in TARGET_MATURITIES:
                    row[f"rate_{maturity}y"] = db.get_rate(conn, reference_date, country, "NO_VA", "BASE", maturity)
                meta = db.get_metadata(conn, reference_date, country, "WITH_VA")
                row["va"] = meta["va"] if meta else None
                rows.append(row)
        finally:
            conn.close()

        columns = ["reference_date", "country"] + [f"rate_{m}y" for m in TARGET_MATURITIES] + ["va"]
        df = pd.DataFrame(rows, columns=columns)
        if not df.empty:
            df["reference_date"] = pd.to_datetime(df["reference_date"])
        return df

    @property
    def historical_data(self) -> pd.DataFrame:
        """Compatibilité : équivalent de l'ancien attribut chargé depuis historical.csv."""
        return self.historical_summary()

    def export_historical_csv(self, output_file: Path = HISTORICAL_FILE, country: str = TARGET_COUNTRY) -> Path:
        """Régénère l'export CSV lisible depuis la base (n'est plus la source de vérité)."""
        df = self.historical_summary(country)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False)
        logger.info(f"Export CSV régénéré depuis la base : {output_file}")
        return output_file

    # ------------------------------------------------------------------
    # Récupération ponctuelle
    # ------------------------------------------------------------------

    def _fetch_summary(self, conn, country: str, reference_date: str) -> Optional[Dict]:
        """Construit {reference_date, country, rates, va} pour une date exacte."""
        rates = {}
        for maturity in TARGET_MATURITIES:
            rate = db.get_rate(conn, reference_date, country, "NO_VA", "BASE", maturity)
            if rate is not None:
                rates[maturity] = rate
        if not rates:
            return None
        meta = db.get_metadata(conn, reference_date, country, "WITH_VA")
        return {
            "reference_date": datetime.strptime(reference_date, "%Y-%m-%d"),
            "country": country,
            "rates": rates,
            "va": meta["va"] if meta else None,
        }

    def get_historical_data(self, country: str, target_date) -> Optional[Dict]:
        conn = self._connect()
        try:
            return self._fetch_summary(conn, country, _date_str(target_date))
        finally:
            conn.close()

    def _get_nearest_data(self, country: str, target_date: datetime, tolerance_days: int) -> Optional[Dict]:
        """Récupère l'entrée la plus proche d'une date cible, dans une tolérance donnée (en jours)."""
        conn = self._connect()
        try:
            available = [datetime.strptime(d, "%Y-%m-%d") for d in db.get_dates(conn, country)]
            if not available:
                return None
            candidates = [d for d in available if abs((d - target_date).days) <= tolerance_days]
            if not candidates:
                return None
            nearest = min(candidates, key=lambda d: abs((d - target_date).days))
            return self._fetch_summary(conn, country, nearest.strftime("%Y-%m-%d"))
        finally:
            conn.close()

    def get_previous_month_data(self, current_date: datetime, country: str) -> Optional[Dict]:
        target = get_previous_month_date(current_date)
        result = self._get_nearest_data(country, target, tolerance_days=5)
        if result is None:
            logger.warning(f"Pas de données M-1 pour {current_date.strftime('%Y-%m-%d')}.")
        return result

    def get_ytd_data(self, current_date: datetime, country: str) -> Optional[Dict]:
        target = get_year_start_date(current_date)
        result = self._get_nearest_data(country, target, tolerance_days=10)
        if result is None:
            logger.warning(f"Pas de données YTD pour {current_date.year}.")
        return result

    def get_metadata(self, country: str, target_date, va_type: str = "WITH_VA") -> Optional[Dict]:
        conn = self._connect()
        try:
            return db.get_metadata(conn, _date_str(target_date), country, va_type)
        finally:
            conn.close()

    def get_ingestion_issues(self, country: str = TARGET_COUNTRY, limit: int = 20) -> List[Dict]:
        """Runs d'ingestion PARTIAL/FAILED (jamais SUCCESS), les plus récents d'abord."""
        conn = self._connect()
        try:
            return db.get_ingestion_issues(conn, country, limit)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Séries temporelles
    # ------------------------------------------------------------------

    def get_time_series(
        self,
        country: str,
        maturity: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        va_type: str = "NO_VA",
        curve_type: str = "BASE",
    ) -> pd.DataFrame:
        """Série temporelle d'une maturité pour un pays — colonnes [reference_date, rate]."""
        conn = self._connect()
        try:
            rows = db.get_time_series(
                conn, country, maturity, va_type=va_type, curve_type=curve_type,
                start_date=_date_str(start_date) if start_date else None,
                end_date=_date_str(end_date) if end_date else None,
            )
        finally:
            conn.close()

        df = pd.DataFrame(rows, columns=["reference_date", "rate"])
        if not df.empty:
            df["reference_date"] = pd.to_datetime(df["reference_date"])
        return df

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------

    def analyze(self, current_data: Dict) -> Dict:
        """Analyse complète : taux courants + comparaisons M/M et YTD + alertes + métadonnées."""
        reference_date = current_data["reference_date"]
        country = current_data["country"]
        logger.info(f"Analyse pour {country} — {reference_date.strftime('%Y-%m-%d')}")

        previous_data = self.get_previous_month_data(reference_date, country)
        ytd_data = self.get_ytd_data(reference_date, country)

        summary = create_summary_dict(
            reference_date=reference_date,
            country=country,
            rates=current_data["rates"],
            va=current_data.get("va"),
            previous_rates=previous_data["rates"] if previous_data else None,
            previous_va=previous_data.get("va") if previous_data else None,
            ytd_rates=ytd_data["rates"] if ytd_data else None,
            ytd_va=ytd_data.get("va") if ytd_data else None,
        )
        summary["previous_date"] = previous_data["reference_date"] if previous_data else None
        summary["ytd_date"] = ytd_data["reference_date"] if ytd_data else None
        summary["source_file"] = current_data.get("source_file")
        summary["alerts"] = self._detect_alerts(summary)

        metadata_row = self.get_metadata(country, reference_date, va_type="WITH_VA")
        if metadata_row:
            metadata = {
                display_key: metadata_row[db_key]
                for db_key, display_key in METADATA_KEY_MAP.items()
                if metadata_row.get(db_key) is not None
            }
            if metadata:
                summary["metadata"] = metadata

        return summary

    def _detect_alerts(self, summary: Dict) -> List[str]:
        alerts = []
        for maturity, change_bps in summary["changes_mom"].items():
            if maturity != "va" and abs(change_bps) >= ALERT_THRESHOLD_MOM:
                direction = "hausse" if change_bps > 0 else "baisse"
                alerts.append(f"⚠️ Variation M/M importante ({maturity}Y) : {direction} de {format_bps(change_bps)}")

        for maturity, change_bps in summary["changes_ytd"].items():
            if maturity != "va" and abs(change_bps) >= ALERT_THRESHOLD_YTD:
                direction = "hausse" if change_bps > 0 else "baisse"
                alerts.append(f"⚠️ Variation YTD importante ({maturity}Y) : {direction} de {format_bps(change_bps)}")

        return alerts
