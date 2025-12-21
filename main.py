"""
Script principal pour le monitoring mensuel EIOPA
"""
import argparse
from datetime import datetime
import sys

from config.config import LATEST_REPORT_FILE
from src.downloader import EIOPADownloader
from src.processor import EIOPAProcessor
from src.analyzer import EIOPAAnalyzer
from src.reporter import EIOPAReporter
from src.utils import setup_logging

logger = setup_logging()


def run_monthly_update(specific_date: datetime = None, force_redownload: bool = False):
    """
    Exécute le processus mensuel complet
    
    Args:
        specific_date: Date spécifique à traiter (None = dernière disponible)
        force_redownload: Forcer le re-téléchargement même si le fichier existe
    """
    logger.info("=" * 80)
    logger.info("DÉMARRAGE DU MONITORING MENSUEL EIOPA")
    logger.info("=" * 80)
    
    try:
        # Étape 1 : Téléchargement
        logger.info("\n[Étape 1/4] Téléchargement des données EIOPA...")
        downloader = EIOPADownloader()
        
        if specific_date:
            logger.info(f"Recherche du fichier pour la date : {specific_date.strftime('%Y-%m-%d')}")
            zip_path = downloader.download_by_date(specific_date)
        else:
            logger.info("Recherche du dernier fichier disponible...")
            zip_path = downloader.download_latest()
        
        if not zip_path:
            logger.error("❌ Échec du téléchargement")
            return False
        
        logger.info(f"✅ Fichier téléchargé : {zip_path.name}")
        
        # Étape 2 : Traitement
        logger.info("\n[Étape 2/4] Extraction et traitement des données...")
        processor = EIOPAProcessor(zip_path)
        current_data = processor.process()
        
        if not current_data:
            logger.error("❌ Échec du traitement des données")
            return False
        
        logger.info(f"✅ Données extraites pour {current_data['country']} - "
                   f"{current_data['reference_date'].strftime('%Y-%m-%d')}")
        logger.info(f"   - {len(current_data['rates'])} taux extraits")
        logger.info(f"   - VA : {'Disponible' if current_data.get('va') else 'Non disponible'}")
        
        # Étape 3 : Analyse
        logger.info("\n[Étape 3/4] Analyse et comparaison...")
        analyzer = EIOPAAnalyzer()
        
        # Ajouter à l'historique
        analyzer.add_to_historical(current_data)
        
        # Analyser avec comparaisons
        analysis = analyzer.analyze(current_data)
        
        logger.info("✅ Analyse complétée")
        if analysis.get('previous_date'):
            logger.info(f"   - Comparaison M/M : {analysis['previous_date'].strftime('%Y-%m-%d')}")
        if analysis.get('ytd_date'):
            logger.info(f"   - Comparaison YTD : {analysis['ytd_date'].strftime('%Y-%m-%d')}")
        if analysis.get('alerts'):
            logger.info(f"   - ⚠️  {len(analysis['alerts'])} alerte(s) détectée(s)")
        
        # Étape 4 : Génération des rapports
        logger.info("\n[Étape 4/4] Génération des rapports...")
        reporter = EIOPAReporter()
        
        # Rapport texte
        text_file = LATEST_REPORT_FILE
        reporter.generate_text_report(analysis, text_file)
        logger.info(f"✅ Rapport texte : {text_file}")
        
        # Rapport CSV
        csv_file = LATEST_REPORT_FILE.with_suffix('.csv')
        reporter.generate_csv_report(analysis, csv_file)
        logger.info(f"✅ Rapport CSV : {csv_file}")
        
        # Rapport Excel
        try:
            excel_file = LATEST_REPORT_FILE.with_suffix('.xlsx')
            reporter.generate_excel_report(analysis, excel_file)
            logger.info(f"✅ Rapport Excel : {excel_file}")
        except ImportError:
            logger.warning("⚠️  openpyxl non installé, rapport Excel non généré")
        
        # Afficher le rapport dans la console
        logger.info("\n" + "=" * 80)
        logger.info("RAPPORT MENSUEL")
        logger.info("=" * 80 + "\n")
        
        reporter.print_console_report(analysis)
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ TRAITEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ ERREUR FATALE : {e}", exc_info=True)
        return False


def list_available_files():
    """Liste tous les fichiers disponibles sur le site EIOPA"""
    logger.info("Récupération de la liste des fichiers disponibles...")
    
    try:
        downloader = EIOPADownloader()
        files = downloader.get_available_files()
        
        if not files:
            print("Aucun fichier trouvé")
            return
        
        print(f"\n{'=' * 80}")
        print(f"FICHIERS DISPONIBLES ({len(files)} fichiers)")
        print(f"{'=' * 80}\n")
        
        for i, (filename, url, date) in enumerate(files[:20], 1):  # Limiter à 20
            print(f"{i:2d}. {date.strftime('%Y-%m-%d')} - {filename}")
        
        if len(files) > 20:
            print(f"\n... et {len(files) - 20} autres fichiers")
        
        print(f"\n{'=' * 80}")
        
    except Exception as e:
        logger.error(f"Erreur : {e}")


def show_historical_stats():
    """Affiche des statistiques sur l'historique"""
    from src.analyzer import EIOPAAnalyzer
    
    analyzer = EIOPAAnalyzer()
    
    if analyzer.historical_data.empty:
        print("Aucune donnée historique disponible")
        return
    
    print(f"\n{'=' * 80}")
    print("STATISTIQUES HISTORIQUES")
    print(f"{'=' * 80}\n")
    
    print(f"Nombre d'enregistrements : {len(analyzer.historical_data)}")
    
    if not analyzer.historical_data.empty:
        min_date = analyzer.historical_data['reference_date'].min()
        max_date = analyzer.historical_data['reference_date'].max()
        print(f"Période couverte : {min_date.strftime('%Y-%m-%d')} à {max_date.strftime('%Y-%m-%d')}")
        
        print(f"\nPays disponibles : {', '.join(analyzer.historical_data['country'].unique())}")
    
    print(f"\n{'=' * 80}")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Système de monitoring mensuel EIOPA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s                          # Traite le dernier fichier disponible
  %(prog)s --date 2024-12-31        # Traite un fichier spécifique
  %(prog)s --list                   # Liste les fichiers disponibles
  %(prog)s --stats                  # Affiche les statistiques historiques
        """
    )
    
    parser.add_argument(
        '--date',
        type=str,
        help='Date spécifique à traiter (format: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='Lister les fichiers disponibles'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Afficher les statistiques historiques'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forcer le re-téléchargement'
    )
    
    args = parser.parse_args()
    
    # Mode listing
    if args.list:
        list_available_files()
        return
    
    # Mode stats
    if args.stats:
        show_historical_stats()
        return
    
    # Mode traitement
    specific_date = None
    if args.date:
        try:
            specific_date = datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print(f"❌ Format de date invalide : {args.date}")
            print("Format attendu : YYYY-MM-DD (ex: 2024-12-31)")
            sys.exit(1)
    
    # Exécuter le traitement
    success = run_monthly_update(specific_date, args.force)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()