#!/bin/bash
# Lance le dashboard web (FastAPI + frontend statique, voir src/eiopa_rfr/webapi.py
# et frontend/) avec l'interpréteur du venv du projet directement, comme run.sh
# le fait pour Streamlit — évite les mêmes écueils de résolution d'interpréteur.
set -e
cd "$(dirname "$0")"

if [ ! -x "venv/bin/python" ]; then
    echo "❌ venv/bin/python introuvable. Créez le venv d'abord :"
    echo "   python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

exec venv/bin/python -m eiopa_rfr.webapp
