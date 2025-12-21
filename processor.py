"""
Module de traitement et extraction des données EIOPA
"""
import zipfile
from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
import fnmatch

from config import (
    EXPECTED_EXCEL_FILES, EXCEL_SHEET_RFR,
    TARGET_COUNTRY, TARGET_MATURITIES, PROCESSED_DIR
)
from utils import (
    setup_logging, parse_date_from_filename, safe_float_conversion,
    validate_rate
)

logger = setup_logging()


class EIOPAProcessor:
    """Processeur de fichiers EIOPA"""
    
    def __init__(self, zip_path: Path):
        self.zip_path = zip_path
        self.reference_date = parse_date_from_filename(zip_path.name)
        
        if not self.reference_date:
            logger.warning(f"Impossible d'extraire la date du fichier: {zip_path.name}")
    
    def list_files_in_zip(self) -> List[str]:
        """
        Liste tous les fichiers dans le ZIP
        
        Returns:
            Liste des noms de fichiers
        """
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                return zf.namelist()
        except zipfile.BadZipFile as e:
            logger.error(f"Fichier ZIP corrompu: {e}")
            return []
    
    def find_excel_file(self, pattern_list: List[str] = None) -> Optional[str]:
        """
        Trouve un fichier Excel dans le ZIP correspondant aux patterns
        
        Args:
            pattern_list: Liste de patterns de noms de fichiers (utilise EXPECTED_EXCEL_FILES par défaut)
            
        Returns:
            Nom du fichier trouvé ou None
        """
        if pattern_list is None:
            pattern_list = EXPECTED_EXCEL_FILES
            
        files_in_zip = self.list_files_in_zip()
        
        for pattern in pattern_list:
            for filename in files_in_zip:
                # Vérifier extension Excel
                if not filename.lower().endswith(('.xlsx', '.xls')):
                    continue
                    
                if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filename, f"*{pattern}"):
                    logger.info(f"Fichier Excel trouvé: {filename}")
                    return filename
        
        logger.warning(f"Aucun fichier Excel trouvé pour les patterns: {pattern_list}")
        return None
    
    def extract_excel_from_zip(self, excel_filename: str) -> Optional[Path]:
        """
        Extrait un fichier Excel du ZIP
        
        Args:
            excel_filename: Nom du fichier Excel dans le ZIP
            
        Returns:
            Chemin du fichier extrait ou None
        """
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                # Créer un nom de fichier unique
                output_filename = f"{self.zip_path.stem}_{Path(excel_filename).name}"
                output_path = PROCESSED_DIR / output_filename
                
                # Extraire
                with zf.open(excel_filename) as source, open(output_path, 'wb') as target:
                    target.write(source.read())
                
                logger.info(f"Fichier Excel extrait: {output_path}")
                return output_path
                
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction: {e}")
            return None
    
    def read_excel_robust(self, excel_path: Path, sheet_name: str = None) -> Optional[pd.DataFrame]:
        """
        Lit un fichier Excel de manière robuste
        
        Args:
            excel_path: Chemin du fichier Excel
            sheet_name: Nom de l'onglet (utilise EXCEL_SHEET_RFR par défaut)
            
        Returns:
            DataFrame ou None
        """
        if sheet_name is None:
            sheet_name = EXCEL_SHEET_RFR
        
        try:
            # Lire avec openpyxl
            df = pd.read_excel(excel_path, sheet_name=sheet_name, engine='openpyxl', header=1, index_col=1)
            
            if df.empty:
                logger.warning(f"Onglet '{sheet_name}' vide")
                return None
            
            logger.info(f"Excel lu avec succès: {len(df)} lignes, {len(df.columns)} colonnes (onglet: {sheet_name})")
            return df
            
        except ValueError as e:
            if "Worksheet" in str(e):
                logger.error(f"Onglet '{sheet_name}' introuvable dans le fichier Excel")
                # Lister les onglets disponibles
                try:
                    xl_file = pd.ExcelFile(excel_path)
                    logger.info(f"Onglets disponibles: {xl_file.sheet_names}")
                except:
                    pass
            else:
                logger.error(f"Erreur lors de la lecture Excel: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du fichier Excel: {e}")
            return None
    
    def extract_country_rates_from_pivot(self, df: pd.DataFrame, country_code: str = TARGET_COUNTRY) -> Optional[Dict[int, float]]:
        """
        Extrait les taux pour un pays depuis le format pivot Excel EIOPA
        
        Format attendu :
        - Première colonne : maturités (1, 2, 3, ..., 150)
        - Autres colonnes : pays/devises (Euro, France, Germany, etc.)
        
        Args:
            df: DataFrame du fichier Excel
            country_code: Code pays (ex: 'FR')
            
        Returns:
            Dictionnaire {maturité: taux} ou None
        """
        # Mapping codes pays vers noms de colonnes possibles
        country_mapping = {
            'FR': ['France', 'French', 'FR'],
            'DE': ['Germany', 'German', 'DE'],
            'IT': ['Italy', 'Italian', 'IT'],
            'ES': ['Spain', 'Spanish', 'ES'],
            'EUR': ['Euro', 'EUR', 'Eurozone'],
            'GB': ['United Kingdom', 'UK', 'GB', 'GBP'],
            'US': ['United States', 'USA', 'US', 'USD']
        }
        
        # Trouver la colonne correspondant au pays
        target_columns = country_mapping.get(country_code, [country_code])
        country_column = None
        
        for possible_name in target_columns:
            for col in df.columns:
                if possible_name.lower() in str(col).lower():
                    country_column = col
                    logger.info(f"Colonne trouvée pour {country_code}: {col}")
                    break
            if country_column:
                break
        
        if country_column is None:
            logger.error(f"Colonne pour le pays {country_code} non trouvée")
            logger.info(f"Colonnes disponibles: {list(df.columns[:10])}...")
            return None
        
        # Extraire les taux pour les maturités cibles
        rates = {}
                
        for maturity in TARGET_MATURITIES:
            # Trouver la ligne correspondant à la maturité
            mask = df.index == maturity
            
            if not mask.any():
                logger.warning(f"Maturité {maturity} non trouvée")
                continue
            
            # Extraire le taux
            rate_value = df.loc[mask, country_column].iloc[0]
            rate_float = safe_float_conversion(rate_value)
            
            if rate_float is not None:
                # Les taux dans le fichier EIOPA sont en % (ex: 2.5 pour 2.5%)
                # On les convertit en décimal (0.025)
                rate_decimal = rate_float / 100
                
                if validate_rate(rate_decimal):
                    rates[maturity] = rate_decimal
                    logger.debug(f"Taux {maturity}Y: {rate_float}% ({rate_decimal:.6f})")
                else:
                    logger.warning(f"Taux invalide pour maturité {maturity}Y: {rate_float}")
        
        if not rates:
            logger.error("Aucun taux extrait")
            return None
        
        return rates
    
    
    def process(self) -> Optional[Dict]:
        """
        Traite le fichier ZIP complet
        
        Returns:
            Dictionnaire contenant les données extraites
        """
        logger.info(f"Traitement du fichier: {self.zip_path.name}")
        
        # Trouver le fichier Excel principal
        excel_file = self.find_excel_file()
        if not excel_file:
            logger.error("Aucun fichier Excel trouvé dans le ZIP")
            return None
        
        # Extraire
        excel_path = self.extract_excel_from_zip(excel_file)
        if not excel_path:
            return None
        
        # Lire l'onglet des taux spot
        df = self.read_excel_robust(excel_path, EXCEL_SHEET_RFR)
        if df is None:
            logger.error(f"Impossible de lire l'onglet '{EXCEL_SHEET_RFR}'")
            return None
        
        # Extraire les taux pour le pays cible (format pivot)
        rates = self.extract_country_rates_from_pivot(df, TARGET_COUNTRY)
        
        if not rates:
            logger.error("Aucun taux extrait")
            return None
        
        va = None
        
        result = {
            'reference_date': self.reference_date,
            'country': TARGET_COUNTRY,
            'rates': rates,
            'va': va,
            'source_file': self.zip_path.name
        }
        
        logger.info(f"Traitement terminé: {len(rates)} taux extraits")
        
        return result


def main():
    """Test du module de traitement"""
    from downloader import EIOPADownloader
    
    # Télécharger le dernier fichier
    downloader = EIOPADownloader()
    zip_path = downloader.download_latest()
    
    if not zip_path:
        print("✗ Échec du téléchargement")
        return
    
    # Traiter le fichier
    processor = EIOPAProcessor(zip_path)
    result = processor.process()
    
    if result:
        print("\n=== Données extraites ===")
        print(f"Date: {result['reference_date'].strftime('%Y-%m-%d')}")
        print(f"Pays: {result['country']}")
        print("\nTaux:")
        for maturity, rate in sorted(result['rates'].items()):
            print(f"  {maturity}Y: {rate*100:.2f}%")
        if result['va']:
            print(f"\nVA: {result['va']*100:.2f}%")
    else:
        print("✗ Échec du traitement")


if __name__ == "__main__":
    main()