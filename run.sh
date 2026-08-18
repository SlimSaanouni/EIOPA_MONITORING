#!/bin/bash
# Lance le dashboard avec l'interpréteur du venv du projet directement
# (venv/bin/streamlit), sans dépendre du PATH ni d'une activation manuelle
# du venv — évite l'écueil "un autre Streamlit, installé ailleurs sur la
# machine, résolu en premier dans le PATH" (cause du TypeError classique
# sur st.dataframe(width=...) avec un Streamlit trop ancien).
set -e
cd "$(dirname "$0")"

if [ ! -x "venv/bin/streamlit" ]; then
    echo "❌ venv/bin/streamlit introuvable. Créez le venv d'abord :"
    echo "   python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

exec venv/bin/streamlit run app.py "$@"
