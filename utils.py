"""
Fonctions utilitaires pour le système de monitoring EIOPA
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Optional, List, Dict
import pandas as pd

from config import (
    LOG_FORMAT, LOG_DATE_FORMAT, LOG_FILE,
    MIN_RATE, MAX_RATE, MIN_VA, MAX_VA
)


def setup_logging(log_file: Path = LOG_FILE) -> logging.Logger:
    """
    Configure le système de logging
    
    Args:
        log_file: Chemin du fichier de log
        
    Returns:
        Logger configuré
    """
    logger = logging.getLogger('EIOPA_Monitor')
    logger.setLevel(logging.INFO)
    
    # Éviter les doublons de handlers
    if logger.handlers:
        return logger
    
    # Handler fichier
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    
    # Handler console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


def parse_date_from_filename(filename: str) -> Optional[datetime]:
    """
    Extrait la date d'un nom de fichier EIOPA
    
    Args:
        filename: Nom du fichier (ex: "EIOPA_RFR_20241231.zip")
        
    Returns:
        Date extraite ou None si parsing échoue
    """
    pattern = r'(\d{8})'
    match = re.search(pattern, filename)
    
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            return None
    return None


def format_date_eiopa(date: datetime) -> str:
    """
    Formate une date au format EIOPA (YYYYMMDD)
    
    Args:
        date: Date à formater
        
    Returns:
        Date formatée
    """
    return date.strftime('%Y%m%d')


def excel_date_to_datetime(excel_date: float) -> datetime:
    """
    Convertit une date Excel (nombre de jours depuis 1900-01-01) en datetime
    
    Args:
        excel_date: Nombre de jours depuis 1900-01-01
        
    Returns:
        Date convertie
    """
    # Excel considère 1900 comme année bissextile (erreur connue)
    if excel_date > 59:
        excel_date -= 1
    
    base_date = datetime(1899, 12, 30)
    return base_date + timedelta(days=excel_date)


def validate_rate(rate: float) -> bool:
    """
    Valide qu'un taux est dans une plage acceptable
    
    Args:
        rate: Taux à valider (en décimal, ex: 0.03 pour 3%)
        
    Returns:
        True si valide, False sinon
    """
    return MIN_RATE <= rate <= MAX_RATE


def validate_va(va: float) -> bool:
    """
    Valide qu'un Volatility Adjustment est dans une plage acceptable
    
    Args:
        va: VA à valider (en décimal)
        
    Returns:
        True si valide, False sinon
    """
    return MIN_VA <= va <= MAX_VA


def calculate_bps_change(old_rate: float, new_rate: float) -> float:
    """
    Calcule la variation en points de base entre deux taux
    
    Args:
        old_rate: Ancien taux (en décimal)
        new_rate: Nouveau taux (en décimal)
        
    Returns:
        Variation en points de base
    """
    return (new_rate - old_rate) * 10000


def format_bps(bps: float) -> str:
    """
    Formate une valeur en points de base avec signe
    
    Args:
        bps: Valeur en points de base
        
    Returns:
        Chaîne formatée (ex: "+15 bps" ou "-10 bps")
    """
    sign = "+" if bps >= 0 else ""
    return f"{sign}{bps:.1f} bps"


def format_rate_pct(rate: float) -> str:
    """
    Formate un taux en pourcentage
    
    Args:
        rate: Taux en décimal (ex: 0.0285)
        
    Returns:
        Taux formaté (ex: "2.85%")
    """
    return f"{rate * 100:.2f}%"


def detect_csv_delimiter(filepath: Path, sample_lines: int = 5) -> str:
    """
    Détecte automatiquement le délimiteur d'un fichier CSV
    
    Args:
        filepath: Chemin du fichier CSV
        sample_lines: Nombre de lignes à échantillonner
        
    Returns:
        Délimiteur détecté (';', ',', '\t')
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        sample = [f.readline() for _ in range(sample_lines)]
    
    # Compter les occurrences de chaque délimiteur potentiel
    delimiters = [',', ';', '\t', '|']
    counts = {delim: sum(line.count(delim) for line in sample) for delim in delimiters}
    
    # Retourner le délimiteur le plus fréquent
    return max(counts, key=counts.get)


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise les noms de colonnes (minuscules, sans espaces)
    
    Args:
        df: DataFrame à normaliser
        
    Returns:
        DataFrame avec colonnes normalisées
    """
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    return df


def find_column(df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
    """
    Trouve une colonne parmi plusieurs noms possibles
    
    Args:
        df: DataFrame à rechercher
        possible_names: Liste de noms possibles
        
    Returns:
        Nom de la colonne trouvée ou None
    """
    df_normalized = normalize_column_names(df.copy())
    
    for name in possible_names:
        name_normalized = name.lower().replace(' ', '_')
        if name_normalized in df_normalized.columns:
            # Retourner le nom original (pas normalisé)
            idx = df_normalized.columns.tolist().index(name_normalized)
            return df.columns[idx]
    
    return None


def get_previous_month_date(reference_date: datetime) -> datetime:
    """
    Calcule la date du mois précédent (dernier jour)
    
    Args:
        reference_date: Date de référence
        
    Returns:
        Dernier jour du mois précédent
    """
    first_day_current = reference_date.replace(day=1)
    last_day_previous = first_day_current - timedelta(days=1)
    return last_day_previous


def get_year_start_date(reference_date: datetime) -> datetime:
    """
    Calcule la date de début d'année
    
    Args:
        reference_date: Date de référence
        
    Returns:
        1er janvier de l'année
    """
    return datetime(reference_date.year, 1, 1)


def safe_float_conversion(value) -> Optional[float]:
    """
    Convertit une valeur en float de manière sécurisée
    
    Args:
        value: Valeur à convertir
        
    Returns:
        Float ou None si conversion impossible
    """
    if pd.isna(value):
        return None
    
    try:
        # Gérer les formats avec virgule comme séparateur décimal
        if isinstance(value, str):
            value = value.replace(',', '.').replace(' ', '')
        return float(value)
    except (ValueError, TypeError):
        return None


def create_summary_dict(
    reference_date: datetime,
    country: str,
    rates: Dict[int, float],
    va: float,
    previous_rates: Optional[Dict[int, float]] = None,
    previous_va: Optional[float] = None,
    ytd_rates: Optional[Dict[int, float]] = None,
    ytd_va: Optional[float] = None
) -> Dict:
    """
    Crée un dictionnaire de résumé pour le rapport
    
    Args:
        reference_date: Date de référence
        country: Code pays
        rates: Dictionnaire des taux par maturité
        va: Volatility Adjustment
        previous_rates: Taux du mois précédent
        previous_va: VA du mois précédent
        ytd_rates: Taux début d'année
        ytd_va: VA début d'année
        
    Returns:
        Dictionnaire structuré
    """
    summary = {
        'reference_date': reference_date,
        'country': country,
        'rates': rates,
        'va': va,
        'changes_mom': {},
        'changes_ytd': {}
    }
    
    # Calcul des variations M/M
    if previous_rates:
        for maturity in rates.keys():
            if maturity in previous_rates:
                summary['changes_mom'][maturity] = calculate_bps_change(
                    previous_rates[maturity], rates[maturity]
                )
        
        if previous_va is not None:
            summary['changes_mom']['va'] = calculate_bps_change(previous_va, va)
    
    # Calcul des variations YTD
    if ytd_rates:
        for maturity in rates.keys():
            if maturity in ytd_rates:
                summary['changes_ytd'][maturity] = calculate_bps_change(
                    ytd_rates[maturity], rates[maturity]
                )
        
        if ytd_va is not None:
            summary['changes_ytd']['va'] = calculate_bps_change(ytd_va, va)
    
    return summary