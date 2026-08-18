"""
Configuration centralisée pour le système de monitoring EIOPA
"""
import os
from pathlib import Path
from datetime import datetime


def _env_int(name: str, default: int) -> int:
    """Lit un entier depuis une variable d'environnement, avec repli sur `default` si absente/invalide."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

# ==================== CHEMINS ====================
# BASE_DIR = racine du dépôt (data/, logs/, assets/, .streamlit/ y vivent),
# pas le dossier du package : config.py est maintenant à src/eiopa_rfr/,
# deux niveaux sous la racine.
BASE_DIR      = Path(__file__).resolve().parents[2]
DATA_DIR      = BASE_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
EXTRACTS_DIR  = DATA_DIR / "extracts"
PROCESSED_DIR = DATA_DIR / "processed"
LOG_DIR       = BASE_DIR / "logs"

for directory in [DATA_DIR, RAW_DIR, PROCESSED_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==================== FICHIERS ====================
HISTORICAL_FILE    = DATA_DIR / "historical.csv"      # export lisible régénéré depuis la base — plus la source de vérité
LATEST_REPORT_FILE = DATA_DIR / "latest_report.txt"

# ==================== BASE DE DONNÉES ====================
HISTORICAL_DB   = DATA_DIR / "historical.db"           # source de vérité
DB_SCHEMA_FILE  = Path(__file__).parent / "schema.sql"  # colocalisé avec config.py dans le package
DB_BACKUP_DIR   = DATA_DIR / "db_backups"
DB_BACKUP_KEEP  = _env_int("EIOPA_DB_BACKUP_KEEP", 14)  # nombre de jours distincts conservés (1 backup/jour max)

DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# ==================== EIOPA ====================
EIOPA_BASE_URL    = "https://www.eiopa.europa.eu"
EIOPA_RFR_URL     = f"{EIOPA_BASE_URL}/tools-and-data/risk-free-interest-rate-term-structures_en"
ZIP_DOWNLOAD_PATTERN = "/document/download/"

EXPECTED_EXCEL_FILES = [
    "EIOPA_RFR_*_Term_Structures.xlsx",
    "EIOPA_RFR_Term_Structures.xlsx",
    "*Term_Structures.xlsx",
]

# ==================== PAYS ET MATURITÉS ====================
TARGET_COUNTRY    = "FR"
TARGET_MATURITIES = [1, 5, 10, 20, 30]

# ==================== RÉSEAU ====================
REQUEST_TIMEOUT = _env_int("EIOPA_REQUEST_TIMEOUT", 30)   # secondes
MAX_RETRIES     = _env_int("EIOPA_MAX_RETRIES", 3)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ==================== LOGGING ====================
LOG_FORMAT      = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE        = LOG_DIR / f"eiopa_monitoring_{datetime.now().strftime('%Y%m')}.log"

# ==================== ANALYSE ====================
# Surchargeables par variable d'environnement (ex: EIOPA_ALERT_THRESHOLD_MOM=75)
# pour permettre à une autre équipe déployant sa propre instance d'ajuster
# les seuils sans toucher au code.
ALERT_THRESHOLD_MOM = _env_int("EIOPA_ALERT_THRESHOLD_MOM", 50)   # bps
ALERT_THRESHOLD_YTD = _env_int("EIOPA_ALERT_THRESHOLD_YTD", 100)  # bps
BPS_CONVERSION      = 10000

# ==================== VALIDATION ====================
MIN_RATE = -0.05
MAX_RATE =  0.15
MIN_VA   =  0.0
MAX_VA   =  0.02