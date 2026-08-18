"""
Point d'entrée de la commande console `eiopa-rfr-app` (voir pyproject.toml,
[project.scripts]) — équivaut à `streamlit run app.py`.

À ne pas confondre avec app.py à la racine du dépôt, qui contient le
dashboard lui-même : celui-ci reste à la racine par convention Streamlit
(et pour que Streamlit Community Cloud le trouve). Ce module se contente
d'invoquer `streamlit run` par-dessus, programmatiquement, exactement comme
le fait le script console `streamlit` lui-même (streamlit.web.cli:main lit
sys.argv — même mécanisme que `streamlit run app.py` tapé dans un shell).
"""
import sys
from pathlib import Path

# Chemin du vrai app.py, à la racine du dépôt (deux niveaux au-dessus de
# src/eiopa_rfr/) — indépendant du répertoire de travail courant.
_APP_PATH = Path(__file__).resolve().parents[2] / "app.py"


def launch():
    """Lance le dashboard Streamlit. Les arguments de la commande sont transmis tels quels à `streamlit run`."""
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(_APP_PATH), *sys.argv[1:]]
    sys.exit(stcli.main())
