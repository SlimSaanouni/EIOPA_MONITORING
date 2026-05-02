"""
Module d'analyse et de comparaison des données EIOPA
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import HISTORICAL_FILE, TARGET_MATURITIES, ALERT_THRESHOLD_MOM, ALERT_THRESHOLD_YTD
from src.utils import (
    setup_logging,
    get_previous_month_date,
    get_year_start_date,
    format_bps,
    create_summary_dict,
)

logger = setup_logging()


class EIOPAAnalyzer:
    """Analyseur de données EIOPA avec historique persistant."""

    def __init__(self, historical_file: Path = HISTORICAL_FILE):
        self.historical_file = historical_file
        self.historical_data = self._load_historical()

    # ------------------------------------------------------------------
    # Chargement / sauvegarde
    # ------------------------------------------------------------------

    def _load_historical(self) -> pd.DataFrame:
        if not self.historical_file.exists():
            logger.info("Aucun historique existant — création d'un nouveau fichier.")
            columns = ["reference_date", "country"] + [f"rate_{m}y" for m in TARGET_MATURITIES] + ["va"]
            return pd.DataFrame(columns=columns)
        try:
            df = pd.read_csv(self.historical_file, parse_dates=["reference_date"])
            logger.info(f"Historique chargé : {len(df)} enregistrements.")
            return df
        except Exception as e:
            logger.error(f"Erreur chargement historique : {e}")
            return pd.DataFrame()

    def save_historical(self):
        try:
            self.historical_data.to_csv(self.historical_file, index=False)
            logger.info(f"Historique sauvegardé : {self.historical_file}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde : {e}")

    # ------------------------------------------------------------------
    # Ajout / mise à jour
    # ------------------------------------------------------------------

    def add_to_historical(self, data: Dict):
        """Ajoute ou met à jour une entrée dans l'historique."""
        row = {"reference_date": data["reference_date"], "country": data["country"]}
        for maturity in TARGET_MATURITIES:
            row[f"rate_{maturity}y"] = data["rates"].get(maturity)
        row["va"] = data.get("va")

        if not self.historical_data.empty:
            mask = (
                (self.historical_data["reference_date"] == data["reference_date"])
                & (self.historical_data["country"] == data["country"])
            )
            if mask.any():
                for col, value in row.items():
                    self.historical_data.loc[mask, col] = value
                logger.info("Entrée existante mise à jour.")
            else:
                self.historical_data = pd.concat(
                    [self.historical_data, pd.DataFrame([row])], ignore_index=True
                )
        else:
            self.historical_data = pd.DataFrame([row])

        self.historical_data.sort_values("reference_date", inplace=True)
        self.save_historical()
        logger.info(f"Donnée ajoutée : {data['reference_date'].strftime('%Y-%m-%d')}")

    # ------------------------------------------------------------------
    # Récupération des données historiques
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: pd.Series) -> Dict:
        """Convertit une ligne de l'historique en dictionnaire standard."""
        rates = {}
        for maturity in TARGET_MATURITIES:
            col = f"rate_{maturity}y"
            if col in row and pd.notna(row[col]):
                rates[maturity] = float(row[col])
        return {
            "reference_date": row["reference_date"],
            "country": row["country"],
            "rates": rates,
            "va": float(row["va"]) if pd.notna(row.get("va")) else None,
        }

    def get_historical_data(self, country: str, target_date: datetime) -> Optional[Dict]:
        if self.historical_data.empty:
            return None
        mask = (
            (self.historical_data["country"] == country)
            & (self.historical_data["reference_date"] == target_date)
        )
        if not mask.any():
            return None
        return self._row_to_dict(self.historical_data[mask].iloc[0])

    def _get_nearest_data(self, country: str, target_date: datetime, tolerance_days: int) -> Optional[Dict]:
        """Récupère l'entrée la plus proche d'une date cible, dans une tolérance donnée."""
        if self.historical_data.empty:
            return None
        td = pd.Timedelta(days=tolerance_days)
        mask = (
            (self.historical_data["country"] == country)
            & (self.historical_data["reference_date"] >= target_date - td)
            & (self.historical_data["reference_date"] <= target_date + td)
        )
        if not mask.any():
            return None
        candidates = self.historical_data[mask].copy()
        candidates["_diff"] = (candidates["reference_date"] - target_date).abs()
        return self._row_to_dict(candidates.sort_values("_diff").iloc[0])

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

    # ------------------------------------------------------------------
    # Séries temporelles
    # ------------------------------------------------------------------

    def get_time_series(
        self,
        country: str,
        maturity: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Retourne la série temporelle d'une maturité pour un pays."""
        col = f"rate_{maturity}y"
        if self.historical_data.empty or col not in self.historical_data.columns:
            return pd.DataFrame(columns=["reference_date", "rate"])

        df = self.historical_data[self.historical_data["country"] == country].copy()
        if start_date:
            df = df[df["reference_date"] >= start_date]
        if end_date:
            df = df[df["reference_date"] <= end_date]

        result = df[["reference_date", col]].rename(columns={col: "rate"}).dropna()
        return result.sort_values("reference_date")

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------

    def analyze(self, current_data: Dict) -> Dict:
        """Analyse complète : taux courants + comparaisons M/M et YTD + alertes."""
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
        summary["alerts"] = self._detect_alerts(summary)
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