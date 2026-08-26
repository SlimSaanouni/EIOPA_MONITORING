"""
Point d'entrée de la commande console `eiopa-rfr-web` (voir pyproject.toml,
[project.scripts]) — lance l'API FastAPI (eiopa_rfr.webapi:app) qui sert à
la fois le JSON et le frontend statique (frontend/), via uvicorn.

Remplace `eiopa-rfr-app` (Streamlit, voir eiopa_rfr.app) comme interface de
monitoring — voir frontend/ pour l'UI correspondante.
"""
import argparse
import os
import socket
import threading
import time
import webbrowser


def _find_free_port(host: str, start_port: int, max_attempts: int = 20) -> int:
    """Retourne start_port s'il est libre, sinon le premier port libre suivant."""
    port = start_port
    for _ in range(max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    raise RuntimeError(f"Aucun port libre trouvé entre {start_port} et {port - 1}")


def _wait_and_open_browser(host: str, port: int, timeout: float = 10.0) -> None:
    """Attend que le serveur accepte les connexions, puis ouvre le navigateur.

    Tourne dans un thread à part pendant que uvicorn.run() bloque le thread
    principal — évite d'ouvrir le navigateur avant que le serveur ne réponde.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                webbrowser.open(f"http://{host}:{port}")
                return
        except OSError:
            time.sleep(0.2)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lance le dashboard web d'EIOPA_RFR (API FastAPI + frontend statique).")
    parser.add_argument("--no-browser", action="store_true",
                        help="Ne pas ouvrir le navigateur automatiquement")
    return parser.parse_args(argv)


def launch():
    """Lance le serveur web. Port/host surchageables via EIOPA_WEB_PORT / EIOPA_WEB_HOST.

    Si le port demandé est déjà occupé (cas fréquent avec plusieurs projets
    locaux tournant en parallèle), bascule automatiquement sur le premier
    port libre suivant plutôt que d'échouer.
    """
    import uvicorn

    args = _parse_args()

    host = os.environ.get("EIOPA_WEB_HOST", "127.0.0.1")
    requested_port = int(os.environ.get("EIOPA_WEB_PORT", "8000"))
    port = _find_free_port(host, requested_port)
    if port != requested_port:
        print(f"⚠️  Port {requested_port} déjà utilisé — démarrage sur le port {port} à la place.")
    print(f"→ Dashboard disponible sur http://{host}:{port}")

    # Même sémantique que READONLY_DASHBOARD dans webapi.py : sur une instance
    # hébergée en lecture seule, il n'y a pas de navigateur local à ouvrir.
    readonly = os.environ.get("READONLY_DASHBOARD", "").strip().lower() in ("1", "true", "yes")
    if not readonly and not args.no_browser:
        threading.Thread(target=_wait_and_open_browser, args=(host, port), daemon=True).start()

    uvicorn.run("eiopa_rfr.webapi:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    launch()
