"""
Chemins de la base de courbes EIOPA, sans effet de bord (aucun mkdir).

Source de vérité pour BASE_DIR / HISTORICAL_DB / DB_SCHEMA_FILE : config.py
réexporte BASE_DIR/HISTORICAL_DB/DB_SCHEMA_FILE pour ne pas casser les imports
existants, mais un consommateur qui doit rester passif sur le disque (ex. le
health-check de main.py) importe ce module directement plutôt que config.py,
qui crée data/raw/, data/processed/, logs/ et data/db_backups/ au chargement.

find_repo_root() est le SEUL point de résolution de la racine du dépôt —
config.py et eiopa_rfr.app le réutilisent au lieu de recalculer chacun leur
propre Path(__file__).resolve().parents[N], fragile (suppose un nombre de
niveaux figé) et qui, en install non-éditable (package copié en
site-packages, hors checkout git), pointait silencieusement vers un dossier
arbitraire sous site-packages plutôt que d'échouer clairement.

COCKPIT_STUDY_DIR (variable d'environnement) prime sur tout le reste. Ce
module fait partie d'un écosystème de 4 modules (SLIM, EIOPA_RFR, ESG,
Asset_PTF) orchestrés par un Cockpit central, qui gère plusieurs "études"
(jeux de données distincts) ; à l'inverse des autres modules, celui-ci ne se
base pas sur le cwd du process lancé pour choisir ses données
(find_repo_root() remonte depuis l'emplacement du fichier source, pas depuis
le cwd), donc un simple changement de dossier courant au lancement
d'eiopa-rfr-web n'a aucun effet. Le Cockpit positionne donc
COCKPIT_STUDY_DIR dans l'environnement du subprocess pour désigner
explicitement l'étude active ; en son absence (lancement autonome, hors
Cockpit), le comportement retombe sur find_repo_root() / platformdirs,
inchangé.

COCKPIT_STUDY_DIR désigne un dossier d'étude PARTAGÉ entre les 4 modules — le
Cockpit y scaffold un sous-dossier par module, nommé par son id (voir
CockpitALM/cockpit/study_store.py et process_manager.py) :
COCKPIT_STUDY_DIR/slim/, .../eiopa_rfr/, .../esg/, .../asset_ptf/. BASE_DIR
pointe donc vers COCKPIT_STUDY_DIR/eiopa_rfr/ (pas la racine de l'étude, qui
appartiendrait aux 3 autres modules) — c'est le sous-dossier "eiopa_rfr" qui
accueille data/, logs/, etc.
"""
import os
from pathlib import Path
from typing import Optional

import platformdirs


def find_repo_root() -> Optional[Path]:
    """Remonte depuis ce fichier à la recherche d'un checkout git (marqueur :
    un pyproject.toml parent). Retourne None si aucun n'est trouvé — cas d'une
    install non-éditable, hors checkout (le code tourne alors depuis
    site-packages, qui n'a pas de pyproject.toml au-dessus de lui).
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return None


# Id du module tel que scaffoldé par le Cockpit sous COCKPIT_STUDY_DIR (voir
# CockpitALM/cockpit/study_store.py) — sous-dossier propre à ce module dans le
# dossier d'étude, partagé avec slim/, esg/ et asset_ptf/.
COCKPIT_MODULE_ID = "eiopa_rfr"


def _cockpit_study_dir() -> Optional[Path]:
    """Sous-dossier de ce module dans l'étude active imposée par le Cockpit,
    s'il est présent (COCKPIT_STUDY_DIR/eiopa_rfr/, pas la racine de l'étude,
    partagée avec les 3 autres modules)."""
    raw = os.environ.get("COCKPIT_STUDY_DIR")
    if not raw:
        return None
    return Path(raw).expanduser().resolve() / COCKPIT_MODULE_ID


# Priorité : COCKPIT_STUDY_DIR (étude active désignée par le Cockpit) > racine
# du dépôt si on tourne depuis un checkout (install éditable, cas de
# développement courant autonome) > un répertoire de données par utilisateur
# (install standalone, ex. pip install hors checkout) — jamais site-packages,
# qui peut ne pas être inscriptible et n'est de toute façon pas l'endroit où
# des données locales générées à l'exécution doivent vivre.
BASE_DIR = (
    _cockpit_study_dir()
    or find_repo_root()
    or Path(platformdirs.user_data_dir("eiopa-rfr", appauthor=False))
)

HISTORICAL_DB  = BASE_DIR / "data" / "historical.db"
DB_SCHEMA_FILE = Path(__file__).parent / "schema.sql"
