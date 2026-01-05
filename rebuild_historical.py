"""
Script de reconstruction du fichier historical.csv
à partir des fichiers Excel déjà traités dans data/processed/
"""
import pandas as pd

from config import PROCESSED_DIR, HISTORICAL_FILE, TARGET_MATURITIES, TARGET_COUNTRY, EXCEL_SHEET_RFR
from src.analyzer import EIOPAAnalyzer
from src.utils import setup_logging, parse_date_from_filename

logger = setup_logging()


def rebuild_historical():
    """Reconstruit l'historique depuis les fichiers processed"""
    
    print("=" * 80)
    print("RECONSTRUCTION DU FICHIER HISTORICAL.CSV")
    print("=" * 80)
    print()
    
    # Sauvegarder l'ancien historique si existe
    if HISTORICAL_FILE.exists():
        backup_file = HISTORICAL_FILE.with_suffix('.csv.backup')
        HISTORICAL_FILE.rename(backup_file)
        print(f"✅ Ancien historique sauvegardé : {backup_file}")
    
    # Créer un nouvel analyzer (historique vide)
    analyzer = EIOPAAnalyzer()
    
    # Chercher tous les fichiers Excel dans processed/
    excel_files = list(PROCESSED_DIR.glob("*.xlsx")) + list(PROCESSED_DIR.glob("*.xls"))
    
    if not excel_files:
        print("❌ Aucun fichier Excel trouvé dans data/processed/")
        return
    
    print(f"📁 {len(excel_files)} fichiers Excel trouvés")
    print()
    
    processed_count = 0
    errors = []
    
    for excel_file in sorted(excel_files):
        print(f"Traitement : {excel_file.name}...", end=" ")
        
        try:
            # Lire le fichier Excel
            df = pd.read_excel(excel_file, sheet_name=EXCEL_SHEET_RFR, engine='openpyxl', header=1, index_col=1)
            
            # Extraire la date du nom du fichier
            reference_date = parse_date_from_filename(excel_file.name)
            if not reference_date:
                print("⚠️  Date non identifiable, ignoré")
                continue
            
            # Extraire les taux (sans division par 100 cette fois!)
            rates = {}
            country_column = None
            
            # Trouver la colonne France
            for col in df.columns:
                if 'france' in str(col).lower() or 'fr' in str(col).lower():
                    country_column = col
                    break
            
            if country_column is None:
                print("⚠️  Colonne France non trouvée")
                errors.append(excel_file.name)
                continue
            
            # Extraire les taux pour chaque maturité
            for maturity in TARGET_MATURITIES:
                if maturity in df.index:
                    rate_value = df.loc[maturity, country_column]
                    if pd.notna(rate_value):
                        # Directement utiliser la valeur (déjà en décimal)
                        rates[maturity] = float(rate_value)
            
            if not rates:
                print("⚠️  Aucun taux extrait")
                errors.append(excel_file.name)
                continue
            
            # Créer l'entrée
            data = {
                'reference_date': reference_date,
                'country': TARGET_COUNTRY,
                'rates': rates,
                'va': None  # VA non disponible dans les fichiers processed
            }
            
            # Ajouter à l'historique
            analyzer.add_to_historical(data)
            processed_count += 1
            print(f"✅ {reference_date.strftime('%Y-%m-%d')}")
            
        except Exception as e:
            print(f"❌ Erreur : {e}")
            errors.append(excel_file.name)
    
    print()
    print("=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    print(f"Fichiers traités avec succès : {processed_count}")
    print(f"Erreurs                      : {len(errors)}")
    
    if errors:
        print("\nFichiers en erreur :")
        for error_file in errors:
            print(f"  - {error_file}")
    
    print()
    print(f"✅ Historique reconstruit : {HISTORICAL_FILE}")
    print(f"   Nombre d'enregistrements : {len(analyzer.historical_data)}")
    
    if not analyzer.historical_data.empty:
        min_date = analyzer.historical_data['reference_date'].min()
        max_date = analyzer.historical_data['reference_date'].max()
        print(f"   Période : {min_date.strftime('%Y-%m-%d')} à {max_date.strftime('%Y-%m-%d')}")
    
    print("=" * 80)


if __name__ == "__main__":
    rebuild_historical()