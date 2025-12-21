"""
Module de téléchargement des fichiers EIOPA
"""
import re
import time
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
import requests
from bs4 import BeautifulSoup

from config import (
    EIOPA_RFR_URL, ZIP_PATTERN, ZIP_DOWNLOAD_PATTERN,
    REQUEST_TIMEOUT, MAX_RETRIES, HEADERS, RAW_DIR
)
from utils import setup_logging, parse_date_from_filename, format_date_eiopa

logger = setup_logging()


class EIOPADownloader:
    """Gestionnaire de téléchargement des fichiers EIOPA"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def get_available_files(self) -> List[Tuple[str, str, datetime]]:
        """
        Récupère la liste des fichiers disponibles sur le site EIOPA
        
        Returns:
            Liste de tuples (nom_fichier, url, date)
        """
        logger.info(f"Récupération de la liste des fichiers depuis {EIOPA_RFR_URL}")
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(EIOPA_RFR_URL, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                break
            except requests.RequestException as e:
                logger.warning(f"Tentative {attempt + 1}/{MAX_RETRIES} échouée: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Backoff exponentiel
                else:
                    logger.error("Échec de connexion après toutes les tentatives")
                    raise
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Rechercher tous les liens de téléchargement
        files = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Vérifier si c'est un lien de téléchargement de fichier ZIP RFR
            if ZIP_DOWNLOAD_PATTERN in href and 'EIOPA_RFR_' in href:
                # Extraire le nom du fichier depuis le paramètre filename
                filename_match = re.search(r'filename=([^&]+)', href)
                if filename_match:
                    filename = filename_match.group(1)
                    
                    # Parser la date
                    file_date = parse_date_from_filename(filename)
                    if file_date:
                        # Construire l'URL complète
                        if not href.startswith('http'):
                            href = f"https://www.eiopa.europa.eu{href}"
                        
                        files.append((filename, href, file_date))
                        logger.debug(f"Fichier trouvé: {filename} - {file_date}")
        
        # Trier par date décroissante
        files.sort(key=lambda x: x[2], reverse=True)
        
        logger.info(f"{len(files)} fichiers RFR trouvés")
        return files
    
    def get_latest_file(self) -> Optional[Tuple[str, str, datetime]]:
        """
        Récupère le fichier le plus récent
        
        Returns:
            Tuple (nom_fichier, url, date) ou None
        """
        files = self.get_available_files()
        
        if not files:
            logger.warning("Aucun fichier trouvé")
            return None
        
        latest = files[0]
        logger.info(f"Dernier fichier disponible: {latest[0]} ({latest[2].strftime('%Y-%m-%d')})")
        return latest
    
    def get_file_by_date(self, target_date: datetime) -> Optional[Tuple[str, str, datetime]]:
        """
        Récupère un fichier pour une date spécifique
        
        Args:
            target_date: Date cible
            
        Returns:
            Tuple (nom_fichier, url, date) ou None
        """
        files = self.get_available_files()
        
        # Chercher une correspondance exacte ou le fichier le plus proche
        exact_match = None
        closest_match = None
        min_diff = float('inf')
        
        for filename, url, file_date in files:
            if file_date.date() == target_date.date():
                exact_match = (filename, url, file_date)
                break
            
            diff = abs((file_date - target_date).days)
            if diff < min_diff:
                min_diff = diff
                closest_match = (filename, url, file_date)
        
        if exact_match:
            logger.info(f"Correspondance exacte trouvée: {exact_match[0]}")
            return exact_match
        elif closest_match and min_diff <= 5:  # Tolérance de 5 jours
            logger.warning(
                f"Pas de correspondance exacte, fichier le plus proche: "
                f"{closest_match[0]} (écart: {min_diff} jours)"
            )
            return closest_match
        else:
            logger.error(f"Aucun fichier trouvé pour la date {target_date.strftime('%Y-%m-%d')}")
            return None
    
    def download_file(self, url: str, filename: str, output_dir: Path = RAW_DIR) -> Optional[Path]:
        """
        Télécharge un fichier depuis l'URL
        
        Args:
            url: URL du fichier
            filename: Nom du fichier
            output_dir: Dossier de sortie
            
        Returns:
            Chemin du fichier téléchargé ou None
        """
        output_path = output_dir / filename
        
        # Vérifier si le fichier existe déjà
        if output_path.exists():
            logger.info(f"Fichier déjà téléchargé: {output_path}")
            return output_path
        
        logger.info(f"Téléchargement de {filename}...")
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
                response.raise_for_status()
                
                # Télécharger par chunks
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Afficher progression (tous les 10%)
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                if progress % 10 < 1:
                                    logger.debug(f"Progression: {progress:.0f}%")
                
                logger.info(f"Téléchargement réussi: {output_path}")
                return output_path
                
            except requests.RequestException as e:
                logger.warning(f"Tentative {attempt + 1}/{MAX_RETRIES} échouée: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Échec du téléchargement après toutes les tentatives")
                    if output_path.exists():
                        output_path.unlink()  # Supprimer le fichier partiel
                    raise
        
        return None
    
    def download_latest(self) -> Optional[Path]:
        """
        Télécharge le dernier fichier disponible
        
        Returns:
            Chemin du fichier téléchargé ou None
        """
        latest = self.get_latest_file()
        
        if not latest:
            return None
        
        filename, url, file_date = latest
        return self.download_file(url, filename)
    
    def download_by_date(self, target_date: datetime) -> Optional[Path]:
        """
        Télécharge le fichier pour une date spécifique
        
        Args:
            target_date: Date cible
            
        Returns:
            Chemin du fichier téléchargé ou None
        """
        file_info = self.get_file_by_date(target_date)
        
        if not file_info:
            return None
        
        filename, url, file_date = file_info
        return self.download_file(url, filename)


def main():
    """Test du module de téléchargement"""
    downloader = EIOPADownloader()
    
    # Afficher les 5 derniers fichiers disponibles
    files = downloader.get_available_files()[:5]
    print("\n=== 5 derniers fichiers disponibles ===")
    for filename, url, date in files:
        print(f"  - {filename}: {date.strftime('%Y-%m-%d')}")
    
    # Télécharger le dernier fichier
    print("\n=== Téléchargement du dernier fichier ===")
    latest_path = downloader.download_latest()
    if latest_path:
        print(f"✓ Fichier téléchargé: {latest_path}")
    else:
        print("✗ Échec du téléchargement")


if __name__ == "__main__":
    main()