# Système de Monitoring Mensuel EIOPA

## 📋 Description

Outil automatisé pour la surveillance mensuelle des **taux sans risque (Risk-Free Rates)** et du **Volatility Adjustment** publiés par l'EIOPA (European Insurance and Occupational Pensions Authority) dans le cadre de Solvency II.

### Fonctionnalités principales

✅ **Téléchargement automatique** des fichiers mensuels depuis le site EIOPA  
✅ **Extraction robuste** des données (courbes de taux, VA)  
✅ **Analyse comparative** : variations M/M et YTD  
✅ **Alertes** sur variations significatives  
✅ **Historique consolidé** en CSV  
✅ **Rapports multi-formats** : texte, CSV, Excel  
✅ **Logging détaillé** de toutes les opérations  

---

## 🏗️ Architecture

```
eiopa-monitoring/
├── config.py           # Configuration centralisée
├── utils.py            # Fonctions utilitaires
├── downloader.py       # Téléchargement EIOPA
├── processor.py        # Traitement des fichiers ZIP/CSV
├── analyzer.py         # Analyse et comparaisons
├── reporter.py         # Génération de rapports
├── main.py             # Script principal
├── requirements.txt    # Dépendances Python
├── README.md          # Cette documentation
├── data/
│   ├── raw/           # Fichiers ZIP téléchargés
│   ├── processed/     # CSV extraits
│   ├── historical.csv # Historique consolidé
│   ├── latest_report.txt
│   ├── latest_report.csv
│   └── latest_report.xlsx
└── logs/
    └── eiopa_monitoring_YYYYMM.log
```

---

## 🚀 Installation

### Prérequis

- **Python 3.8+**
- Accès Internet (pour télécharger depuis EIOPA)

### Étapes

```bash
# 1. Cloner ou télécharger le projet
cd eiopa-monitoring/

# 2. Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# 3. Installer les dépendances
pip install -r requirements.txt
```

---

## 💻 Utilisation

### Mode standard : Traitement du dernier fichier disponible

```bash
python main.py
```

**Résultat** :
1. Télécharge le fichier EIOPA le plus récent
2. Extrait les taux pour la France (EUR)
3. Compare avec le mois précédent et le début d'année
4. Génère les rapports dans `data/`
5. Affiche le résumé dans la console

### Mode date spécifique

```bash
python main.py --date 2024-11-30
```

Traite le fichier pour une date précise (format: `YYYY-MM-DD`)

### Lister les fichiers disponibles

```bash
python main.py --list
```

Affiche les 20 derniers fichiers disponibles sur le site EIOPA.

### Afficher les statistiques historiques

```bash
python main.py --stats
```

Montre le nombre d'enregistrements, la période couverte, etc.

### Options avancées

```bash
# Forcer le re-téléchargement
python main.py --force

# Combiner plusieurs options
python main.py --date 2024-10-31 --force
```

---

## 📊 Exemple de rapport

```
================================================================================
RAPPORT MENSUEL EIOPA - TAUX SANS RISQUE ET VOLATILITY ADJUSTMENT
================================================================================

📅 Date d'analyse : 30/11/2024
🌍 Pays           : FR
📦 Source         : EIOPA_RFR_20241130.zip

--------------------------------------------------------------------------------
📊 DONNÉES EXTRAITES
--------------------------------------------------------------------------------

Courbe des taux sans risque (EUR):
  • Taux  1Y : 2.45%
  • Taux  5Y : 2.68%
  • Taux 10Y : 2.85%
  • Taux 20Y : 3.10%
  • Taux 30Y : 3.25%

Volatility Adjustment (VA) : 0.15%

--------------------------------------------------------------------------------
📈 ÉVOLUTIONS vs MOIS PRÉCÉDENT
--------------------------------------------------------------------------------

Référence : 31/10/2024

Variation des taux (en points de base):
  🟢 Taux  1Y : +5.2 bps
  🟢 Taux  5Y : +12.3 bps
  🔴 Taux 10Y : +58.5 bps  ⚠️ Variation importante
  🟢 Taux 20Y : +35.1 bps
  🟢 Taux 30Y : +28.7 bps
  • VA        : +2.0 bps

--------------------------------------------------------------------------------
⚠️  ALERTES
--------------------------------------------------------------------------------

  ⚠️ Variation M/M importante (10Y): hausse de +58.5 bps

================================================================================
```

---

## 🔧 Configuration

### Personnalisation dans `config.py`

```python
# Pays à surveiller
TARGET_COUNTRY = "FR"  # Changer pour "DE", "IT", "ES", etc.

# Maturités à extraire
TARGET_MATURITIES = [1, 5, 10, 20, 30]

# Seuils d'alerte (en points de base)
ALERT_THRESHOLD_MOM = 50   # Alerte si variation M/M > 50 bps
ALERT_THRESHOLD_YTD = 100  # Alerte si variation YTD > 100 bps
```

---

## 📈 Utilisation de l'historique

### Format du fichier `historical.csv`

```csv
reference_date,country,rate_1y,rate_5y,rate_10y,rate_20y,rate_30y,va
2024-01-31,FR,0.0245,0.0268,0.0285,0.0310,0.0325,0.0015
2024-02-29,FR,0.0250,0.0272,0.0290,0.0315,0.0330,0.0016
...
```

### Accéder programmatiquement aux données

```python
from analyzer import EIOPAAnalyzer
from datetime import datetime

analyzer = EIOPAAnalyzer()

# Récupérer une série temporelle
ts = analyzer.get_time_series(
    country='FR',
    maturity=10,
    start_date=datetime(2024, 1, 1)
)

print(ts)
# Output:
#   reference_date      rate
# 0     2024-01-31  0.0285
# 1     2024-02-29  0.0290
# ...
```

---

## 🔄 Automatisation avec Cron/Task Scheduler

### Linux/Mac (cron)

Éditer la crontab :
```bash
crontab -e
```

Ajouter une ligne pour exécution mensuelle (ex : 5ème jour du mois à 9h) :
```cron
0 9 5 * * cd /path/to/eiopa-monitoring && /path/to/venv/bin/python main.py >> /path/to/logs/cron.log 2>&1
```

### Windows (Task Scheduler)

1. Ouvrir le **Planificateur de tâches**
2. Créer une tâche de base
3. Déclencheur : **Mensuel** → Jour 5 à 09:00
4. Action : **Démarrer un programme**
   - Programme : `C:\path\to\venv\Scripts\python.exe`
   - Arguments : `main.py`
   - Dossier : `C:\path\to\eiopa-monitoring`

---

## 🐛 Gestion des erreurs

Le système gère automatiquement :

✅ **Connexion réseau** : Retry automatique (3 tentatives)  
✅ **Formats CSV variables** : Détection automatique du délimiteur  
✅ **En-têtes multiples** : Gestion des headers complexes  
✅ **Fichiers manquants** : Fallback sur fichiers alternatifs  
✅ **Dates Excel** : Conversion automatique  
✅ **Validation des données** : Vérification des plages de valeurs  

### Logs

Tous les événements sont tracés dans :
```
logs/eiopa_monitoring_YYYYMM.log
```

Exemple :
```
2024-12-09 10:30:15 - EIOPA_Monitor - INFO - Téléchargement réussi: EIOPA_RFR_20241130.zip
2024-12-09 10:30:20 - EIOPA_Monitor - INFO - CSV lu avec succès: 5000 lignes, 15 colonnes
2024-12-09 10:30:22 - EIOPA_Monitor - WARNING - Colonne VA non trouvée
```

---

## 🚨 Points d'attention

1. **Changements de format EIOPA** : Les noms de fichiers et colonnes peuvent évoluer. Le système utilise des patterns flexibles mais peut nécessiter une mise à jour du `config.py`.

2. **Dates de publication** : EIOPA publie généralement début du mois suivant (ex : données novembre → publiées ~5 décembre).

3. **Connexion réseau** : Le site EIOPA peut être temporairement indisponible. Le système réessaie automatiquement.

4. **Premier lancement** : Pas de comparaisons M/M et YTD si l'historique est vide. Exécuter plusieurs fois pour constituer la base.

---

## 📝 Améliorations futures

### Déjà implémenté
- ✅ Téléchargement automatique
- ✅ Extraction multi-format
- ✅ Analyse comparative
- ✅ Rapports texte/CSV/Excel
- ✅ Historique consolidé

### Roadmap
- 🔲 **Dashboard Streamlit** interactif
- 🔲 **Alertes email** automatiques
- 🔲 **Graphiques** de courbes de taux
- 🔲 **Export vers bases de données** (PostgreSQL, SQLite)
- 🔲 **API REST** pour interrogation des données
- 🔲 **Multi-pays simultané** (traiter plusieurs courbes)
- 🔲 **Calcul d'indicateurs** dérivés (spreads, pentes)

---

## 📚 Ressources EIOPA

- **Site officiel** : https://www.eiopa.europa.eu
- **Section RFR** : https://www.eiopa.europa.eu/tools-and-data/risk-free-interest-rate-term-structures_en
- **Documentation technique** : Disponible dans la section "Background material"
- **Calendrier de publication** : Publié annuellement sur le site

---

## 🤝 Support et contributions

### Problèmes courants

**Q : "Aucun fichier trouvé pour la date X"**  
R : Vérifier que la date est au dernier jour du mois et que le fichier est publié (généralement début du mois suivant).

**Q : "Colonne pays non trouvée"**  
R : Le format CSV a peut-être changé. Vérifier les fichiers dans `data/processed/` et ajuster `EXPECTED_COLUMNS` dans `config.py`.

**Q : "Module 'openpyxl' introuvable"**  
R : Le rapport Excel nécessite `openpyxl`. Installer avec `pip install openpyxl`.

### Contact

Pour toute question ou amélioration, consulter les logs détaillés et adapter la configuration selon vos besoins spécifiques.

---

## 📄 Licence

Ce projet est fourni tel quel, à des fins de surveillance réglementaire actuarielle. Les données sont la propriété de l'EIOPA.

---

**Version** : 1.0  
**Dernière mise à jour** : Décembre 2024