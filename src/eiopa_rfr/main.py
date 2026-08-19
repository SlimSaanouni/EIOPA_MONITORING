"""
Script principal pour le monitoring mensuel EIOPA
"""
import argparse
from datetime import datetime
import sys

from eiopa_rfr.config import LATEST_REPORT_FILE
from eiopa_rfr.downloader import EIOPADownloader
from eiopa_rfr.ingestion import ingest_zip
from eiopa_rfr.analyzer import EIOPAAnalyzer
from eiopa_rfr.reporter import EIOPAReporter
from eiopa_rfr.utils import setup_logging

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
            zip_path = downloader.download_by_date(specific_date, force=force_redownload)
        else:
            logger.info("Recherche du dernier fichier disponible...")
            zip_path = downloader.download_latest(force=force_redownload)
        
        if not zip_path:
            logger.error("❌ Échec du téléchargement")
            return False
        
        logger.info(f"✅ Fichier téléchargé : {zip_path.name}")
        
        # Étape 2 : Traitement (extraction + écriture dans historical.db)
        logger.info("\n[Étape 2/4] Extraction et ingestion des données...")
        try:
            current_data = ingest_zip(zip_path)
        except ValueError as e:
            logger.error(f"❌ Échec de l'ingestion : {e}")
            return False

        logger.info(f"✅ Données ingérées pour {current_data['country']} - "
                   f"{current_data['reference_date'].strftime('%Y-%m-%d')}")
        logger.info(f"   - {len(current_data['rates'])} taux extraits")
        logger.info(f"   - VA : {'Disponible' if current_data.get('va') else 'Non disponible'}")
        if current_data["status"] == "PARTIAL":
            logger.warning(f"   - ⚠️  Ingestion partielle : {'; '.join(current_data['missing_maturities'][:5])}")

        # Étape 3 : Analyse
        logger.info("\n[Étape 3/4] Analyse et comparaison...")
        analyzer = EIOPAAnalyzer()
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

        # Export CSV régénéré depuis la base (lisible, versionnable — n'est plus la source de vérité)
        analyzer.export_historical_csv()
        logger.info("✅ historical.csv régénéré depuis historical.db")

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
        
        for i, (filename, _url, date) in enumerate(files[:20], 1):  # Limiter à 20
            print(f"{i:2d}. {date.strftime('%Y-%m-%d')} - {filename}")
        
        if len(files) > 20:
            print(f"\n... et {len(files) - 20} autres fichiers")
        
        print(f"\n{'=' * 80}")
        
    except Exception as e:
        logger.error(f"Erreur : {e}")


def show_historical_stats():
    """Affiche des statistiques sur l'historique"""
    from eiopa_rfr.analyzer import EIOPAAnalyzer
    
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


def _parse_date_arg(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"❌ Format de date invalide : {date_str}")
        print("Format attendu : YYYY-MM-DD (ex: 2024-12-31)")
        sys.exit(1)


def export_curves(specific_date, va_type: str):
    """
    Exporte une courbe déjà ingérée au format d'échange (Maturity,Base,Up,Down)
    consommé par ESG et Asset_PTF. Le choix NO_VA/WITH_VA reste à la charge
    de la personne qui exporte (voir la doc externe sur la convention à
    appliquer selon l'outil cible).
    """
    from eiopa_rfr.exporter import export_curve_csv, available_export_dates

    if specific_date is None:
        dates = available_export_dates()
        if not dates:
            print("❌ Aucune courbe en base — rien à exporter.")
            sys.exit(1)
        specific_date = datetime.strptime(dates[0], "%Y-%m-%d")
        print(f"Aucune date fournie, utilisation de la plus récente disponible : "
              f"{specific_date.strftime('%Y-%m-%d')}")

    va_types = ["NO_VA", "WITH_VA"] if va_type == "BOTH" else [va_type]
    exit_code = 0
    for vt in va_types:
        try:
            path = export_curve_csv(specific_date, vt)
            print(f"✅ {vt} : {path}")
        except ValueError as e:
            print(f"❌ {vt} : {e}")
            exit_code = 1
    sys.exit(exit_code)


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Système de monitoring mensuel EIOPA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s                                 # Traite le dernier fichier disponible
  %(prog)s --date 2024-12-31               # Traite un fichier spécifique
  %(prog)s --list                          # Liste les fichiers disponibles
  %(prog)s --stats                         # Affiche les statistiques historiques
  %(prog)s --export --date 2024-12-31      # Exporte NO_VA + WITH_VA pour cette date
  %(prog)s --export --va-type WITH_VA      # Exporte WITH_VA pour la date la plus récente en base
        """
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Date spécifique (format: YYYY-MM-DD) — traitement ou export selon le mode'
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

    parser.add_argument(
        '--export',
        action='store_true',
        help="Exporter une courbe déjà ingérée au format Maturity,Base,Up,Down "
             "(sans --date : la plus récente en base)"
    )

    parser.add_argument(
        '--va-type',
        choices=['NO_VA', 'WITH_VA', 'BOTH'],
        default='BOTH',
        help="Type de courbe à exporter avec --export (défaut : BOTH)"
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

    # Mode export
    if args.export:
        specific_date = _parse_date_arg(args.date) if args.date else None
        export_curves(specific_date, args.va_type)
        return

    # Mode traitement
    specific_date = _parse_date_arg(args.date) if args.date else None

    # Exécuter le traitement
    success = run_monthly_update(specific_date, args.force)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()