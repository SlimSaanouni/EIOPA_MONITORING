"""
Chemins de la base de courbes EIOPA, sans effet de bord (aucun mkdir).

Source de vérité pour HISTORICAL_DB / DB_SCHEMA_FILE : config.py les
réexporte pour ne pas casser les imports existants, mais un consommateur qui
doit rester passif sur le disque (ex. le health-check de main.py) importe ce
module directement plutôt que config.py, qui crée data/raw/, data/processed/,
logs/ et data/db_backups/ au chargement.
"""
from pathlib import Path

BASE_DIR       = Path(__file__).resolve().parents[2]
HISTORICAL_DB  = BASE_DIR / "data" / "historical.db"
DB_SCHEMA_FILE = Path(__file__).parent / "schema.sql"
