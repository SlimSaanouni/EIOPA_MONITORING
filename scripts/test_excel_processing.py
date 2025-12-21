"""
Script de test pour valider le traitement des fichiers Excel EIOPA
"""
import sys
from pathlib import Path

from src.downloader import EIOPADownloader
from src.processor import EIOPAProcessor
from config.config import EXPECTED_EXCEL_FILES, EXCEL_SHEET_RFR
from src.utils import setup_logging

logger = setup_logging()


def test_download():
    """Test du téléchargement"""
    print("\n" + "=" * 80)
    print("TEST 1 : TÉLÉCHARGEMENT")
    print("=" * 80 + "\n")
    
    downloader = EIOPADownloader()
    
    # Lister les fichiers disponibles
    files = downloader.get_available_files()
    if not files:
        print("❌ Aucun fichier disponible")
        return None
    
    print(f"✅ {len(files)} fichiers trouvés sur le site EIOPA")
    print(f"\nDernier fichier : {files[0][0]}")
    
    # Télécharger le dernier
    zip_path = downloader.download_latest()
    if not zip_path:
        print("❌ Échec du téléchargement")
        return None
    
    print(f"✅ Fichier téléchargé : {zip_path}")
    return zip_path


def test_zip_content(zip_path: Path):
    """Test du contenu du ZIP"""
    print("\n" + "=" * 80)
    print("TEST 2 : CONTENU DU ZIP")
    print("=" * 80 + "\n")
    
    processor = EIOPAProcessor(zip_path)
    files_in_zip = processor.list_files_in_zip()
    
    if not files_in_zip:
        print("❌ ZIP vide ou corrompu")
        return False
    
    print(f"✅ {len(files_in_zip)} fichiers dans le ZIP\n")
    print("Fichiers trouvés :")
    for f in files_in_zip:
        print(f"  - {f}")
    
    # Chercher le fichier Excel
    print("\n" + "-" * 80)
    print("Recherche du fichier Excel...")
    excel_file = processor.find_excel_file()
    
    if not excel_file:
        print("❌ Aucun fichier Excel trouvé")
        print(f"Patterns recherchés : {EXPECTED_EXCEL_FILES}")
        return False
    
    print(f"✅ Fichier Excel trouvé : {excel_file}")
    return True


def test_excel_extraction(zip_path: Path):
    """Test de l'extraction et lecture Excel"""
    print("\n" + "=" * 80)
    print("TEST 3 : EXTRACTION ET LECTURE EXCEL")
    print("=" * 80 + "\n")
    
    processor = EIOPAProcessor(zip_path)
    
    # Trouver et extraire
    excel_file = processor.find_excel_file()
    if not excel_file:
        print("❌ Fichier Excel introuvable")
        return False
    
    excel_path = processor.extract_excel_from_zip(excel_file)
    if not excel_path:
        print("❌ Échec de l'extraction")
        return False
    
    print(f"✅ Fichier extrait : {excel_path}")
    
    # Lister les onglets disponibles
    print("\n" + "-" * 80)
    print("Analyse des onglets du fichier Excel...")
    
    try:
        import pandas as pd
        xl_file = pd.ExcelFile(excel_path)
        sheet_names = xl_file.sheet_names
        
        print(f"✅ {len(sheet_names)} onglets trouvés :\n")
        for i, sheet in enumerate(sheet_names, 1):
            print(f"  {i}. {sheet}")
        
        # Vérifier la présence de l'onglet cible
        print("\n" + "-" * 80)
        if EXCEL_SHEET_RFR in sheet_names:
            print(f"✅ Onglet cible '{EXCEL_SHEET_RFR}' trouvé")
        else:
            print(f"⚠️  Onglet '{EXCEL_SHEET_RFR}' NON trouvé")
            print(f"Onglets disponibles : {', '.join(sheet_names)}")
            print("→ Ajustez EXCEL_SHEET_RFR dans config.py")
            return False
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse : {e}")
        return False
    
    return True


def test_data_reading(zip_path: Path):
    """Test de la lecture des données"""
    print("\n" + "=" * 80)
    print("TEST 4 : LECTURE DES DONNÉES")
    print("=" * 80 + "\n")
    
    processor = EIOPAProcessor(zip_path)
    
    # Extraire le fichier Excel
    excel_file = processor.find_excel_file()
    excel_path = processor.extract_excel_from_zip(excel_file)
    
    # Lire l'onglet
    df = processor.read_excel_robust(excel_path, EXCEL_SHEET_RFR)
    
    if df is None:
        print(f"❌ Impossible de lire l'onglet '{EXCEL_SHEET_RFR}'")
        return False
    
    print(f"✅ Données lues : {len(df)} lignes, {len(df.columns)} colonnes\n")
    
    # Afficher la structure
    print("Structure du fichier :")
    print(f"  - Première colonne (maturités) : {df.columns[0]}")
    print("  - Colonnes pays/devises (10 premières) :")
    for i, col in enumerate(list(df.columns)[1:11], 1):
        print(f"    {i}. {col}")
    
    if len(df.columns) > 11:
        print(f"    ... et {len(df.columns) - 11} autres colonnes")
    
    # Afficher un échantillon
    print("\n" + "-" * 80)
    print("Aperçu des premières maturités :\n")
    print(df.head(10).to_string())
    
    return True


def test_country_extraction(zip_path: Path):
    """Test de l'extraction des données France"""
    print("\n" + "=" * 80)
    print("TEST 5 : EXTRACTION DONNÉES FRANCE")
    print("=" * 80 + "\n")
    
    processor = EIOPAProcessor(zip_path)
    
    # Lire les données
    excel_file = processor.find_excel_file()
    excel_path = processor.extract_excel_from_zip(excel_file)
    df = processor.read_excel_robust(excel_path, EXCEL_SHEET_RFR)
    
    if df is None:
        print("❌ Données non lisibles")
        return False
    
    # Extraire les taux France
    print("Extraction des taux pour la France...")
    rates = processor.extract_country_rates_from_pivot(df, 'FR')
    
    if rates is None or not rates:
        print("❌ Aucune donnée pour la France")
        print("Colonnes disponibles:", list(df.columns)[:10])
        return False
    
    print(f"✅ {len(rates)} taux extraits pour la France\n")
    
    print("Taux spot sans VA :")
    for maturity in sorted(rates.keys()):
        rate_pct = rates[maturity] * 100
        print(f"  {maturity:2d}Y : {rate_pct:6.2f}%")
    
    return True


def test_full_processing(zip_path: Path):
    """Test du traitement complet"""
    print("\n" + "=" * 80)
    print("TEST 6 : TRAITEMENT COMPLET")
    print("=" * 80 + "\n")
    
    processor = EIOPAProcessor(zip_path)
    result = processor.process()
    
    if not result:
        print("❌ Échec du traitement complet")
        return False
    
    print("✅ Traitement réussi\n")
    print(f"Date de référence : {result['reference_date'].strftime('%Y-%m-%d')}")
    print(f"Pays              : {result['country']}")
    print(f"Fichier source    : {result['source_file']}")
    
    print(f"\nTaux extraits ({len(result['rates'])}) :")
    for maturity, rate in sorted(result['rates'].items()):
        print(f"  - {maturity:2d}Y : {rate*100:6.4f}%")
    
    if result['va'] is not None:
        print(f"\nVolatility Adjustment : {result['va']*100:.4f}%")
    else:
        print("\nVolatility Adjustment : Non disponible")
    
    return True


def run_all_tests():
    """Exécute tous les tests"""
    print("\n" + "🧪" * 40)
    print("SUITE DE TESTS - TRAITEMENT EXCEL EIOPA")
    print("🧪" * 40)
    
    # Test 1 : Téléchargement
    zip_path = test_download()
    if not zip_path:
        print("\n❌ Tests interrompus : échec du téléchargement")
        return False
    
    # Test 2 : Contenu ZIP
    if not test_zip_content(zip_path):
        print("\n⚠️  Tests interrompus : problème avec le contenu du ZIP")
        return False
    
    # Test 3 : Extraction Excel
    if not test_excel_extraction(zip_path):
        print("\n⚠️  Tests interrompus : problème avec l'extraction Excel")
        return False
    
    # Test 4 : Lecture données
    if not test_data_reading(zip_path):
        print("\n⚠️  Tests interrompus : problème de lecture des données")
        return False
    
    # Test 5 : Extraction France
    if not test_country_extraction(zip_path):
        print("\n⚠️  Tests interrompus : problème d'extraction des données France")
        return False
        
    # Test 6 : Traitement complet
    if not test_full_processing(zip_path):
        print("\n❌ Tests interrompus : échec du traitement complet")
        return False
    
    # Résumé final
    print("\n" + "=" * 80)
    print("✅ TOUS LES TESTS RÉUSSIS")
    print("=" * 80)
    print("\nLe système est prêt à être utilisé !")
    print("Commande : python main.py")
    print("=" * 80 + "\n")
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)