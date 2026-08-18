"""
Point d'entrée CLI — délègue à eiopa_rfr.main (voir src/eiopa_rfr/main.py).

Reste à la racine pour que `python main.py ...` continue de fonctionner tel
quel (doc, cron, scripts) ; la logique réelle vit dans le package installable.
"""
from eiopa_rfr.main import main

if __name__ == "__main__":
    main()
