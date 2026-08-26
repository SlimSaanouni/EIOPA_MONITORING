"""
Point d'entrée de la commande console `eiopa-rfr-app` (voir pyproject.toml,
[project.scripts]) — équivaut à `streamlit run app.py`.

À ne pas confondre avec app.py à la racine du dépôt, qui contient le
dashboard lui-même : celui-ci reste à la racine par convention Streamlit
(et pour que Streamlit Community Cloud le trouve). Ce module se contente
d'invoquer `streamlit run` par-dessus, programmatiquement, exactement comme
le fait le script console `streamlit` lui-même (streamlit.web.cli:main lit
sys.argv — même mécanisme que `streamlit run app.py` tapé dans un shell).

app.py n'étant pas sous src/eiopa_rfr/, il n'est jamais embarqué dans le
package (pas de wheel possible pour un fichier hors du package) : cette
commande ne fonctionne donc que depuis un checkout git (install éditable),
jamais en install standalone. C'est un choix assumé — voir eiopa-rfr-web
(eiopa_rfr.webapp/webapi) pour l'équivalent qui, lui, fonctionne aussi en
install standalone.
"""
import sys

from eiopa_rfr.paths import find_repo_root

_repo_root = find_repo_root()
_APP_PATH = (_repo_root / "app.py") if _repo_root is not None else None


def launch():
    """Lance le dashboard Streamlit. Les arguments de la commande sont transmis tels quels à `streamlit run`."""
    if _APP_PATH is None or not _APP_PATH.is_file():
        print(
            "❌ eiopa-rfr-app ne fonctionne que depuis un checkout git "
            "(install éditable) : app.py, à la racine du dépôt, n'est pas "
            "inclus dans le package installé.\n"
            "   Utilise `eiopa-rfr-web` à la place pour une install standalone.",
            file=sys.stderr,
        )
        sys.exit(1)

    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(_APP_PATH), *sys.argv[1:]]
    sys.exit(stcli.main())
