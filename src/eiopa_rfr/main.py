"""
Script principal pour le monitoring mensuel EIOPA
"""
import json
import sys


def _health_check() -> dict:
    """
    Health-check "cockpit-ready" : contrat partagé avec les 3 autres modules
    orchestrés en subprocess (boîte noire) par alm_cockpit. Doit rester <1s
    et n'écrire aucun fichier — volontairement limité au stdlib + eiopa_rfr,
    sans importer pandas/requests/bs4 (downloader/ingestion/analyzer), qui
    alourdiraient le budget de temps et déclencheraient setup_logging()
    (FileHandler -> écriture sur disque) dès l'import de ce module.
    """
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    def _error(detail: str) -> dict:
        return {"status": "error", "module": "eiopa_rfr", "version": None, "detail": detail}

    try:
        import eiopa_rfr  # noqa: F401
    except Exception as e:
        return _error(f"import eiopa_rfr impossible : {e}")

    try:
        pkg_version = _pkg_version("eiopa-rfr-monitoring")
    except PackageNotFoundError as e:
        return _error(f"package non installé : {e}")

    try:
        import sqlite3
        # eiopa_rfr.paths (pas eiopa_rfr.config) : paths.py n'a aucun effet de
        # bord à l'import (pas de mkdir), et surtout ne déclenche pas la
        # résolution de la racine du dépôt que fait config.py pour DATA_DIR et
        # consorts — HISTORICAL_DB (voir paths.py) reste utilisable même hors
        # checkout (install non-éditable), ce qui n'est pas garanti pour
        # config.py.
        from eiopa_rfr.paths import DB_SCHEMA_FILE, HISTORICAL_DB

        if not DB_SCHEMA_FILE.exists():
            return _error(f"schema.sql introuvable : {DB_SCHEMA_FILE}")
        schema_sql = DB_SCHEMA_FILE.read_text(encoding="utf-8")

        if HISTORICAL_DB.exists():
            # mode=ro seul ne suffit pas : le schéma active PRAGMA journal_mode
            # = WAL, et SQLite crée quand même historical.db-wal/-shm à
            # l'ouverture pour rester cohérent avec un éventuel autre writer.
            # immutable=1 indique que le fichier ne changera pas pendant la
            # connexion : aucun fichier -wal/-shm n'est créé.
            conn = sqlite3.connect(f"file:{HISTORICAL_DB}?mode=ro&immutable=1", uri=True)
            try:
                tables = {
                    row[0] for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            finally:
                conn.close()
            missing = {"curves", "curve_metadata", "ingestion_runs"} - tables
            if missing:
                return _error(f"tables manquantes dans historical.db : {', '.join(sorted(missing))}")
        else:
            # Base pas encore créée : on vérifie que le schéma est initialisable
            # sur une DB en mémoire, sans jamais toucher le disque.
            conn = sqlite3.connect(":memory:")
            try:
                conn.executescript(schema_sql)
            finally:
                conn.close()
    except Exception as e:
        return _error(f"DB/schema inaccessible : {e}")

    return {"status": "ok", "module": "eiopa_rfr", "version": pkg_version, "detail": ""}


if "--health" in sys.argv:
    # Interception avant les imports lourds ci-dessous (pandas, requests...) et
    # avant setup_logging() (ouvre un FileHandler sur logs/) : les deux
    # casseraient le contrat "<1s, aucune écriture" du health-check si on les
    # laissait s'exécuter en premier, comme le ferait un `import eiopa_rfr.main`
    # classique (c'est ainsi que le point d'entrée `eiopa-rfr` charge ce module).
    _result = _health_check()
    print(json.dumps(_result))
    sys.exit(0 if _result["status"] == "ok" else 1)


import argparse
from datetime import datetime
from pathlib import Path

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


def _write_result_json(path, ok: bool, outputs=None, metrics=None, error=None,
                       command: str = "eiopa-rfr --export") -> None:
    """--result-json : contrat partagé par les 4 modules du Cockpit ALM
    (SLIM, EIOPA_RFR, ESG, Asset_PTF) - {schema, module, command, ok, error,
    outputs: {nom: chemin absolu}, metrics: {nom: scalaire}}. No-op si
    l'option n'est pas fournie."""
    if path is None:
        return
    payload = {
        "schema": 1,
        "module": "eiopa_rfr",
        "command": command,
        "ok": ok,
        "error": error,
        "outputs": {k: str(Path(v).resolve()) for k, v in (outputs or {}).items()},
        "metrics": metrics or {},
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def export_curves(specific_date, va_type: str, result_json=None):
    """
    Exporte une courbe déjà ingérée au format d'échange (Maturity,Base,Up,Down)
    consommé par ESG et Asset_PTF. Le choix NO_VA/WITH_VA reste à la charge
    de la personne qui exporte (voir la doc externe sur la convention à
    appliquer selon l'outil cible).

    result_json : chemin du résumé machine-lisible (--result-json) —
    outputs indexés par type de VA ({"NO_VA": chemin, ...}) : sous le
    Cockpit, l'export vit sous COCKPIT_STUDY_DIR/eiopa_rfr/, l'appelant ne
    doit pas avoir à le deviner.
    """
    from eiopa_rfr.exporter import export_curve_csv, available_export_dates

    if specific_date is None:
        dates = available_export_dates()
        if not dates:
            print("❌ Aucune courbe en base — rien à exporter.")
            _write_result_json(result_json, ok=False, error="Aucune courbe en base — rien à exporter.")
            sys.exit(1)
        specific_date = datetime.strptime(dates[0], "%Y-%m-%d")
        print(f"Aucune date fournie, utilisation de la plus récente disponible : "
              f"{specific_date.strftime('%Y-%m-%d')}")

    va_types = ["NO_VA", "WITH_VA"] if va_type == "BOTH" else [va_type]
    exit_code = 0
    outputs, errors = {}, []
    for vt in va_types:
        try:
            path = export_curve_csv(specific_date, vt)
            print(f"✅ {vt} : {path}")
            outputs[vt] = path
        except ValueError as e:
            print(f"❌ {vt} : {e}")
            errors.append(f"{vt} : {e}")
            exit_code = 1
    _write_result_json(result_json, ok=exit_code == 0, outputs=outputs,
                       metrics={"date": specific_date.strftime("%Y-%m-%d")},
                       error="\n".join(errors) or None)
    sys.exit(exit_code)


def list_available_curves(result_json=None):
    """Dates de courbes déjà ingérées en base (exportables sans téléchargement),
    lecture seule — sous le Cockpit, celles de l'étude active. Permet à un
    pipeline de vérifier qu'une date est disponible avant de lancer quoi que
    ce soit."""
    from eiopa_rfr.exporter import available_export_dates

    dates = available_export_dates()
    for d in dates:
        print(d)
    if not dates:
        print("Aucune courbe en base.")
    _write_result_json(result_json, ok=True, metrics={"dates": dates},
                       command="eiopa-rfr --available")


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

    parser.add_argument(
        '--available',
        action='store_true',
        help="Lister les dates de courbes déjà ingérées en base (lecture seule, sans réseau)"
    )

    parser.add_argument(
        '--result-json',
        type=Path,
        default=None,
        metavar='CHEMIN',
        help="Avec --export, --available ou le traitement d'une date : écrit un "
             "résumé JSON machine-lisible (chemins, dates, statut) — lu par les "
             "pipelines du Cockpit ALM"
    )

    parser.add_argument(
        '--health',
        action='store_true',
        help="Health-check rapide (<1s, aucune écriture) pour supervision externe "
             "(ex. alm_cockpit) — affiche un JSON {status, module, version, detail} "
             "sur stdout et sort en code 0/1. Interceptée avant le parsing normal ; "
             "présente ici pour --help et par défense en profondeur."
    )

    args = parser.parse_args()

    # Mode health (normalement déjà intercepté plus haut avant les imports
    # lourds — ce garde-fou ne joue que si main() est appelé directement)
    if args.health:
        result = _health_check()
        print(json.dumps(result))
        sys.exit(0 if result["status"] == "ok" else 1)

    # Mode listing
    if args.list:
        list_available_files()
        return

    # Mode stats
    if args.stats:
        show_historical_stats()
        return

    # Mode dates disponibles
    if args.available:
        list_available_curves(result_json=args.result_json)
        return

    # Mode export
    if args.export:
        specific_date = _parse_date_arg(args.date) if args.date else None
        export_curves(specific_date, args.va_type, result_json=args.result_json)
        return

    # Mode traitement
    specific_date = _parse_date_arg(args.date) if args.date else None

    # Exécuter le traitement
    success = run_monthly_update(specific_date, args.force)

    _write_result_json(args.result_json, ok=success,
                       metrics={"date": specific_date.strftime("%Y-%m-%d") if specific_date else None},
                       error=None if success else "traitement en échec (voir le journal)",
                       command="eiopa-rfr --date")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()