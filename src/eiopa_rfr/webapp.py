"""
Point d'entrée de la commande console `eiopa-rfr-web` (voir pyproject.toml,
[project.scripts]) — lance l'API FastAPI (eiopa_rfr.webapi:app) qui sert à
la fois le JSON et le frontend statique (frontend/), via uvicorn.

Remplace `eiopa-rfr-app` (Streamlit, voir eiopa_rfr.app) comme interface de
monitoring — voir frontend/ pour l'UI correspondante.
"""
import os


def launch():
    """Lance le serveur web. Port/host surchageables via EIOPA_WEB_PORT / EIOPA_WEB_HOST."""
    import uvicorn

    host = os.environ.get("EIOPA_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("EIOPA_WEB_PORT", "8000"))
    uvicorn.run("eiopa_rfr.webapi:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    launch()
