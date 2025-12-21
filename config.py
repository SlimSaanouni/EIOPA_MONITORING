"""
Configuration centralisée pour le système de monitoring EIOPA
"""
from pathlib import Path
from datetime import datetime

# ==================== CHEMINS ET DOSSIERS ====================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOG_DIR = BASE_DIR / "logs"

# Créer les dossiers s'ils n'existent pas
for directory in [DATA_DIR, RAW_DIR, PROCESSED_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==================== FICHIERS ====================
HISTORICAL_FILE = DATA_DIR / "historical.csv"
LATEST_REPORT_FILE = DATA_DIR / "latest_report.txt"

# ==================== PARAMÈTRES EIOPA ====================
EIOPA_BASE_URL = "https://www.eiopa.europa.eu"
EIOPA_RFR_URL = f"{EIOPA_BASE_URL}/tools-and-data/risk-free-interest-rate-term-structures_en"

# Pattern des fichiers ZIP
ZIP_PATTERN = r"EIOPA_RFR_(\d{8})\.zip"
ZIP_DOWNLOAD_PATTERN = "/document/download/"

# Nom du fichier Excel dans le ZIP (peut varier)
EXPECTED_EXCEL_FILES = [
    "EIOPA_RFR_*_Term_Structures.xlsx",
    "EIOPA_RFR_Term_Structures.xlsx",
    "*Term_Structures.xlsx"
]

# Onglet Excel contenant les taux spot sans VA
EXCEL_SHEET_RFR = "RFR_spot_no_VA"

# Anciens fichiers CSV (legacy, pour compatibilité)
EXPECTED_CSV_FILES = [
    "EIOPA_RFR_Term_Structures.csv",
    "term_structure.csv",
    "RFR_spot_no_VA.csv"
]

# ==================== PAYS ET DONNÉES À SURVEILLER ====================
TARGET_COUNTRY = "FR"  # Code pays France
TARGET_MATURITIES = [1, 5, 10, 20, 30]  # Maturités à suivre (en années)

# Colonnes attendues dans les fichiers Excel/CSV
EXPECTED_COLUMNS = {
    'maturity': ['maturity', 'Maturity', 'Duration', 'Tenor', 'Year'],
}

# Structure spéciale du fichier Excel EIOPA :
# - Première ligne : Header avec pays/devises
# - Première colonne : Maturités (1 à 150 ans typiquement)
# - Données : Taux spot pour chaque pays/devise

# ==================== VOLATILITY ADJUSTMENT ====================
VA_FILE_PATTERNS = [
    "EIOPA_RFR_VA.csv",
    "RFR_VA_shock.csv",
    "Volatility_Adjustment.csv"
]

# ==================== PARAMÈTRES RÉSEAU ====================
REQUEST_TIMEOUT = 30  # secondes
MAX_RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# ==================== PARAMÈTRES DE LOGGING ====================
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_FILE = LOG_DIR / f"eiopa_monitoring_{datetime.now().strftime('%Y%m')}.log"

# ==================== PARAMÈTRES D'ANALYSE ====================
# Seuils d'alerte (en points de base)
ALERT_THRESHOLD_MOM = 50  # Variation M/M
ALERT_THRESHOLD_YTD = 100  # Variation YTD

# Conversion points de base
BPS_CONVERSION = 10000  # 1% = 100 bps

# ==================== DATES ====================
def get_current_month_info():
    """Retourne les informations du mois courant"""
    now = datetime.now()
    return {
        'year': now.year,
        'month': now.month,
        'first_day': datetime(now.year, now.month, 1),
        'last_day': datetime(now.year, now.month, now.day)
    }

def get_year_start():
    """Retourne le 1er janvier de l'année en cours"""
    now = datetime.now()
    return datetime(now.year, 1, 1)

# ==================== VALIDATION ====================
MIN_RATE = -0.05  # Taux minimum acceptable (-5%)
MAX_RATE = 0.15   # Taux maximum acceptable (15%)
MIN_VA = 0.0      # VA minimum
MAX_VA = 0.02     # VA maximum (2%)

# ==================== MESSAGES ====================
ERROR_MESSAGES = {
    'network': "Erreur réseau lors de la connexion à l'EIOPA",
    'parsing': "Erreur lors du parsing du fichier",
    'data_quality': "Problème de qualité des données détecté",
    'missing_file': "Fichier manquant dans l'archive ZIP",
    'invalid_format': "Format de fichier invalide ou inattendu"
}

SUCCESS_MESSAGES = {
    'download': "Téléchargement réussi",
    'extraction': "Extraction des données terminée",
    'analysis': "Analyse complétée avec succès"
}