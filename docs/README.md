# Monitoring EIOPA — Taux Sans Risque (RFR)

## Objectifs

Cet outil remplit deux fonctions :

1. **Alimenter un Générateur de Scénarios Économiques (GSE)** en produisant les courbes de taux sans risque au format standard (`RFR_[DATE]_NO_VA.csv` et `RFR_[DATE]_WITH_VA.csv`).
2. **Suivre l'évolution historique** des taux publiés mensuellement par l'EIOPA dans le cadre de Solvency II.

---

## Architecture

```
eiopa-monitoring/
├── config.py               # Tous les paramètres centralisés
├── main.py                 # Point d'entrée CLI
├── app.py                  # Dashboard Streamlit
├── requirements.txt
│
├── src/
│   ├── downloader.py       # Téléchargement depuis le site EIOPA
│   ├── processor.py        # Extraction des données depuis le ZIP
│   ├── rfr_exporter.py     # Génération des CSV pour le GSE
│   ├── analyzer.py         # Comparaisons M/M, YTD, alertes
│   ├── reporter.py         # Rapports texte / CSV / Excel
│   └── utils.py            # Fonctions utilitaires partagées
│
└── data/
    ├── extracts/           # Fichiers Excel extraits des ZIP EIOPA
    ├── processed/          # CSV produits pour le GSE (RFR_*.csv)
    ├── raw/                # Fichiers ZIP téléchargés
    ├── historical.csv      # Historique consolidé des taux
    └── latest_report.txt   # Dernier rapport généré
```

---

## Installation

```bash
# Créer et activer l'environnement virtuel
python -m venv venv
source venv/bin/activate      # Linux / Mac
venv\Scripts\activate         # Windows

# Installer les dépendances
pip install -r requirements.txt
```

---

## Utilisation

### Dashboard interactif (recommandé)

```bash
streamlit run app.py
```

Le dashboard permet de :
- Visualiser la courbe des taux actuelle et son historique
- Télécharger un ou plusieurs mois en une seule action
- Comparer deux dates et détecter les alertes

### Ligne de commande

```bash
# Télécharger et traiter le dernier fichier disponible
python main.py

# Traiter un mois spécifique
python main.py --date 2024-11-30

# Lister les fichiers disponibles sur le site EIOPA
python main.py --list

# Afficher les statistiques de l'historique local
python main.py --stats
```

---

## Fichiers produits

### Pour le GSE (dans `data/processed/`)

| Fichier | Contenu |
|---|---|
| `RFR_[DATE]_NO_VA.csv` | Courbe base + chocs IR, sans Volatility Adjustment |
| `RFR_[DATE]_WITH_VA.csv` | Courbe base + chocs IR, avec Volatility Adjustment |

Format : 151 lignes (maturités 0 à 150), 4 colonnes :

```
Maturity, Base, IR Upward Shock, IR Downward shock
0, 0.0, 0.0, 0.0
1, 0.02607, 0.04432, 0.00652
...
```

Les chocs IR sont recalculés depuis l'onglet `Shocks` du fichier Excel EIOPA :
```
UP   = ROUND(base + MAX(0.01, shock_up   × |base|), 5)
DOWN = ROUND(base − MAX(0.00, shock_down × |base|), 5)
```

### Pour le suivi historique (dans `data/`)

| Fichier | Contenu |
|---|---|
| `historical.csv` | Taux cibles (1Y, 5Y, 10Y, 20Y, 30Y) pour tous les mois traités |
| `latest_report.txt` | Rapport du dernier traitement (taux, variations, alertes) |
| `latest_report.csv` | Même contenu en format tabulaire |
| `latest_report.xlsx` | Même contenu en format Excel |

---

## Configuration (`config.py`)

| Paramètre | Défaut | Description |
|---|---|---|
| `TARGET_COUNTRY` | `"FR"` | Pays à extraire (`"DE"`, `"IT"`, etc.) |
| `TARGET_MATURITIES` | `[1, 5, 10, 20, 30]` | Maturités suivies dans l'historique |
| `ALERT_THRESHOLD_MOM` | `50` | Seuil d'alerte variation M/M (bps) |
| `ALERT_THRESHOLD_YTD` | `100` | Seuil d'alerte variation YTD (bps) |

---

## Automatisation mensuelle

**Linux / Mac (cron) :**
```bash
crontab -e
# Exécution le 5 de chaque mois à 9h
0 9 5 * * cd /chemin/eiopa-monitoring && venv/bin/python main.py
```

**Windows (Planificateur de tâches) :**
- Programme : `C:\chemin\venv\Scripts\python.exe`
- Arguments : `main.py`
- Déclencheur : mensuel, jour 5, 09:00

---

## Dépannage

| Erreur | Cause | Solution |
|---|---|---|
| `Aucun fichier trouvé pour la date X` | Fichier non encore publié | EIOPA publie début du mois suivant. Utiliser `--list` pour voir les dates disponibles. |
| `Colonne pays non trouvée` | Format Excel modifié par l'EIOPA | Vérifier les noms de colonnes dans `data/extracts/` et mettre à jour `country_aliases` dans `processor.py`. |
| `Module openpyxl introuvable` | Dépendance manquante | `pip install openpyxl` |
| Chocs IR à 0 dans le CSV | Formules Excel non calculées | Normal : les chocs sont recalculés directement en Python depuis l'onglet `Shocks`. |

---

## Points d'attention

- **Format EIOPA** : le format du fichier Excel peut évoluer. En cas de rupture, vérifier les noms d'onglets dans `rfr_exporter.py` et les noms de colonnes dans `processor.py`.
- **Dates de publication** : l'EIOPA publie les données du mois M entre le 5 et le 10 du mois M+1.
- **Historique** : le fichier `data/historical.csv` est la source de vérité pour le suivi — le versionner ou le sauvegarder régulièrement.