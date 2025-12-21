"""
Module d'analyse et de comparaison des données EIOPA
"""
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
import pandas as pd

from config import (
    HISTORICAL_FILE, TARGET_MATURITIES, ALERT_THRESHOLD_MOM,
    ALERT_THRESHOLD_YTD
)
from utils import (
    setup_logging, get_previous_month_date, get_year_start_date,
    calculate_bps_change, format_bps, format_rate_pct, create_summary_dict
)

logger = setup_logging()


class EIOPAAnalyzer:
    """Analyseur de données EIOPA avec historique"""
    
    def __init__(self, historical_file: Path = HISTORICAL_FILE):
        self.historical_file = historical_file
        self.historical_data = self._load_historical()
    
    def _load_historical(self) -> pd.DataFrame:
        """
        Charge les données historiques
        
        Returns:
            DataFrame des données historiques
        """
        if not self.historical_file.exists():
            logger.info("Aucun historique existant, création d'un nouveau fichier")
            # Créer un DataFrame vide avec la structure attendue
            columns = ['reference_date', 'country'] + \
                     [f'rate_{m}y' for m in TARGET_MATURITIES] + \
                     ['va', 'llp', 'alpha', 'ufr', 'cra', 'convergence', 'coupon_freq']
            return pd.DataFrame(columns=columns)
        
        try:
            df = pd.read_csv(self.historical_file, parse_dates=['reference_date'])
            logger.info(f"Historique chargé: {len(df)} enregistrements")
            return df
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'historique: {e}")
            return pd.DataFrame()
    
    def save_historical(self):
        """Sauvegarde les données historiques"""
        try:
            self.historical_data.to_csv(self.historical_file, index=False)
            logger.info(f"Historique sauvegardé: {self.historical_file}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
    
    def add_to_historical(self, data: Dict):
        """
        Ajoute une nouvelle entrée à l'historique
        
        Args:
            data: Dictionnaire contenant les données (format processor.process())
        """
        # Préparer la ligne à ajouter
        row = {
            'reference_date': data['reference_date'],
            'country': data['country']
        }
        
        # Ajouter les taux
        for maturity in TARGET_MATURITIES:
            col_name = f'rate_{maturity}y'
            row[col_name] = data['rates'].get(maturity)
        
        # Ajouter le VA
        row['va'] = data.get('va')
                
        # Vérifier si cette date existe déjà
        if not self.historical_data.empty:
            mask = (
                (self.historical_data['reference_date'] == data['reference_date']) &
                (self.historical_data['country'] == data['country'])
            )
            
            if mask.any():
                logger.info("Mise à jour d'une entrée existante")
                # Mettre à jour la ligne existante
                for col, value in row.items():
                    self.historical_data.loc[mask, col] = value
            else:
                # Ajouter une nouvelle ligne
                self.historical_data = pd.concat(
                    [self.historical_data, pd.DataFrame([row])],
                    ignore_index=True
                )
        else:
            # Premier enregistrement
            self.historical_data = pd.DataFrame([row])
        
        # Trier par date
        self.historical_data.sort_values('reference_date', inplace=True)
        
        # Sauvegarder
        self.save_historical()
        logger.info(f"Donnée ajoutée pour {data['reference_date'].strftime('%Y-%m-%d')}")

    
    def get_historical_data(
        self, 
        country: str, 
        target_date: datetime
    ) -> Optional[Dict]:
        """
        Récupère les données historiques pour une date et un pays
        
        Args:
            country: Code pays
            target_date: Date cible
            
        Returns:
            Dictionnaire des données ou None
        """
        if self.historical_data.empty:
            return None
        
        mask = (
            (self.historical_data['country'] == country) &
            (self.historical_data['reference_date'] == target_date)
        )
        
        if not mask.any():
            return None
        
        row = self.historical_data[mask].iloc[0]
        
        # Reconstruire le format des données
        rates = {}
        for maturity in TARGET_MATURITIES:
            col_name = f'rate_{maturity}y'
            if col_name in row and pd.notna(row[col_name]):
                rates[maturity] = float(row[col_name])
        
        return {
            'reference_date': row['reference_date'],
            'country': row['country'],
            'rates': rates,
            'va': float(row['va']) if pd.notna(row['va']) else None
        }
    
    def get_previous_month_data(
        self, 
        current_date: datetime, 
        country: str
    ) -> Optional[Dict]:
        """
        Récupère les données du mois précédent
        
        Args:
            current_date: Date courante
            country: Code pays
            
        Returns:
            Dictionnaire des données ou None
        """
        target_date = get_previous_month_date(current_date)
        
        # Chercher dans un intervalle (dernier jour du mois précédent ±5 jours)
        if self.historical_data.empty:
            return None
        
        mask = (
            (self.historical_data['country'] == country) &
            (self.historical_data['reference_date'] >= target_date - pd.Timedelta(days=5)) &
            (self.historical_data['reference_date'] <= target_date + pd.Timedelta(days=5))
        )
        
        if not mask.any():
            logger.warning(f"Pas de données pour le mois précédent de {current_date.strftime('%Y-%m-%d')}")
            return None
        
        # Prendre l'entrée la plus proche
        candidates = self.historical_data[mask].copy()
        candidates['diff'] = abs(candidates['reference_date'] - target_date)
        row = candidates.sort_values('diff').iloc[0]
        
        rates = {}
        for maturity in TARGET_MATURITIES:
            col_name = f'rate_{maturity}y'
            if col_name in row and pd.notna(row[col_name]):
                rates[maturity] = float(row[col_name])
        
        return {
            'reference_date': row['reference_date'],
            'country': row['country'],
            'rates': rates,
            'va': float(row['va']) if pd.notna(row['va']) else None
        }
    
    def get_ytd_data(self, current_date: datetime, country: str) -> Optional[Dict]:
        """
        Récupère les données de début d'année
        
        Args:
            current_date: Date courante
            country: Code pays
            
        Returns:
            Dictionnaire des données ou None
        """
        ytd_date = get_year_start_date(current_date)
        
        if self.historical_data.empty:
            return None
        
        mask = (
            (self.historical_data['country'] == country) &
            (self.historical_data['reference_date'] >= ytd_date - pd.Timedelta(days=10)) &
            (self.historical_data['reference_date'] <= ytd_date + pd.Timedelta(days=10))
        )
        
        if not mask.any():
            logger.warning(f"Pas de données YTD pour {current_date.year}")
            return None
        
        # Prendre l'entrée la plus proche du début d'année
        candidates = self.historical_data[mask].copy()
        candidates['diff'] = abs(candidates['reference_date'] - ytd_date)
        row = candidates.sort_values('diff').iloc[0]
        
        rates = {}
        for maturity in TARGET_MATURITIES:
            col_name = f'rate_{maturity}y'
            if col_name in row and pd.notna(row[col_name]):
                rates[maturity] = float(row[col_name])
        
        return {
            'reference_date': row['reference_date'],
            'country': row['country'],
            'rates': rates,
            'va': float(row['va']) if pd.notna(row['va']) else None
        }
    
    def analyze(self, current_data: Dict) -> Dict:
        """
        Analyse complète avec comparaisons M/M et YTD
        
        Args:
            current_data: Données courantes (format processor.process())
            
        Returns:
            Dictionnaire contenant l'analyse complète
        """
        reference_date = current_data['reference_date']
        country = current_data['country']
        
        logger.info(f"Analyse pour {country} - {reference_date.strftime('%Y-%m-%d')}")
        
        # Récupérer les données de comparaison
        previous_data = self.get_previous_month_data(reference_date, country)
        ytd_data = self.get_ytd_data(reference_date, country)
        
        # Créer le résumé
        summary = create_summary_dict(
            reference_date=reference_date,
            country=country,
            rates=current_data['rates'],
            va=current_data.get('va'),
            previous_rates=previous_data['rates'] if previous_data else None,
            previous_va=previous_data.get('va') if previous_data else None,
            ytd_rates=ytd_data['rates'] if ytd_data else None,
            ytd_va=ytd_data.get('va') if ytd_data else None
        )
        
        # Ajouter les dates de comparaison
        summary['previous_date'] = previous_data['reference_date'] if previous_data else None
        summary['ytd_date'] = ytd_data['reference_date'] if ytd_data else None
        
        # Détecter les alertes
        summary['alerts'] = self._detect_alerts(summary)
        
        return summary
    
    def _detect_alerts(self, summary: Dict) -> List[str]:
        """
        Détecte les variations significatives
        
        Args:
            summary: Résumé d'analyse
            
        Returns:
            Liste de messages d'alerte
        """
        alerts = []
        
        # Alertes M/M
        for maturity, change_bps in summary['changes_mom'].items():
            if maturity == 'va':
                continue
            
            if abs(change_bps) >= ALERT_THRESHOLD_MOM:
                direction = "hausse" if change_bps > 0 else "baisse"
                alerts.append(
                    f"⚠️ Variation M/M importante ({maturity}Y): "
                    f"{direction} de {format_bps(change_bps)}"
                )
        
        # Alertes YTD
        for maturity, change_bps in summary['changes_ytd'].items():
            if maturity == 'va':
                continue
            
            if abs(change_bps) >= ALERT_THRESHOLD_YTD:
                direction = "hausse" if change_bps > 0 else "baisse"
                alerts.append(
                    f"⚠️ Variation YTD importante ({maturity}Y): "
                    f"{direction} de {format_bps(change_bps)}"
                )
        
        return alerts
    
    def get_time_series(
        self, 
        country: str, 
        maturity: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Récupère une série temporelle pour une maturité
        
        Args:
            country: Code pays
            maturity: Maturité en années
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)
            
        Returns:
            DataFrame avec colonnes [reference_date, rate]
        """
        if self.historical_data.empty:
            return pd.DataFrame(columns=['reference_date', 'rate'])
        
        col_name = f'rate_{maturity}y'
        if col_name not in self.historical_data.columns:
            return pd.DataFrame(columns=['reference_date', 'rate'])
        
        # Filtrer par pays
        df = self.historical_data[self.historical_data['country'] == country].copy()
        
        # Filtrer par dates
        if start_date:
            df = df[df['reference_date'] >= start_date]
        if end_date:
            df = df[df['reference_date'] <= end_date]
        
        # Sélectionner les colonnes
        result = df[['reference_date', col_name]].copy()
        result.columns = ['reference_date', 'rate']
        
        # Supprimer les NaN
        result = result.dropna()
        
        return result.sort_values('reference_date')


def main():
    """Test du module d'analyse"""
    from downloader import EIOPADownloader
    from processor import EIOPAProcessor
    
    # Télécharger et traiter
    downloader = EIOPADownloader()
    zip_path = downloader.download_latest()
    
    if not zip_path:
        print("✗ Échec du téléchargement")
        return
    
    processor = EIOPAProcessor(zip_path)
    current_data = processor.process()
    
    if not current_data:
        print("✗ Échec du traitement")
        return
    
    # Analyser
    analyzer = EIOPAAnalyzer()
    
    # Ajouter à l'historique
    analyzer.add_to_historical(current_data)
    
    # Faire l'analyse
    analysis = analyzer.analyze(current_data)
    
    print("\n=== Analyse ===")
    print(f"Date: {analysis['reference_date'].strftime('%Y-%m-%d')}")
    print(f"\nTaux actuels:")
    for maturity in sorted(analysis['rates'].keys()):
        print(f"  {maturity}Y: {format_rate_pct(analysis['rates'][maturity])}")
    
    if analysis['changes_mom']:
        print(f"\nVariations M/M:")
        for maturity in sorted([k for k in analysis['changes_mom'].keys() if k != 'va']):
            print(f"  {maturity}Y: {format_bps(analysis['changes_mom'][maturity])}")
    
    if analysis['alerts']:
        print(f"\nAlertes:")
        for alert in analysis['alerts']:
            print(f"  {alert}")


if __name__ == "__main__":
    main()