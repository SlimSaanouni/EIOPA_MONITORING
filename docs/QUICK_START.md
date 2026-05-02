# Démarrage rapide — EIOPA RFR Monitoring

## En 3 minutes

### 1. Installation

```bash
python -m venv venv
source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Lancer le dashboard

```bash
streamlit run app.py
```

→ Ouvre `http://localhost:8501` dans le navigateur.

### 3. Télécharger les données

Dans le dashboard, aller dans **Mise à jour** :
- Les dates disponibles sur le site EIOPA s'affichent automatiquement
- Sélectionner les mois souhaités
- Cliquer sur **Lancer le téléchargement**

Chaque traitement produit :
- `data/processed/RFR_[DATE]_NO_VA.csv` — courbe pour le GSE sans VA
- `data/processed/RFR_[DATE]_WITH_VA.csv` — courbe pour le GSE avec VA
- Une ligne ajoutée dans `data/historical.csv`

---

## En ligne de commande

```bash
# Dernier mois disponible
python main.py

# Mois spécifique
python main.py --date 2024-11-30

# Voir les fichiers disponibles sur l'EIOPA
python main.py --list
```

---

## Format des CSV produits

```
Maturity, Base, IR Upward Shock, IR Downward shock
0, 0.0, 0.0, 0.0
1, 0.02607, 0.04432, 0.00652
...
150, 0.03165, 0.04164, 0.02539
```

151 lignes (maturités 0 à 150). À brancher directement sur le GSE.

---

## Configuration rapide

Tout se règle dans `config.py` :

```python
TARGET_COUNTRY    = "FR"              # Changer pour "DE", "IT", etc.
TARGET_MATURITIES = [1, 5, 10, 20, 30]  # Maturités du suivi historique
ALERT_THRESHOLD_MOM = 50              # Alerte si variation M/M > 50 bps
ALERT_THRESHOLD_YTD = 100             # Alerte si variation YTD > 100 bps
```

---

## Structure des données

```
data/
├── raw/            → ZIP téléchargés depuis l'EIOPA
├── extracts/       → Fichiers Excel extraits
├── processed/      → CSV pour le GSE  ← fichiers à brancher sur le GSE
├── historical.csv  → Historique consolidé  ← à versionner
└── latest_report.* → Dernier rapport (txt / csv / xlsx)
```

---

## En cas de problème

Consulter les logs :
```
logs/eiopa_monitoring_YYYYMM.log
```

Documentation complète → `README.md`