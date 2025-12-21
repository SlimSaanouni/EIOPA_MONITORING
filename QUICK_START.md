# 🚀 Guide de Démarrage Rapide - EIOPA Monitoring

## ⏱️ Mise en route en 5 minutes

### 1️⃣ Installation (1 minute)

**Linux/Mac :**
```bash
chmod +x install.sh
./install.sh
source venv/bin/activate
```

**Windows :**
```cmd
install.bat
venv\Scripts\activate
```

### 2️⃣ Première exécution (2 minutes)

```bash
python main.py
```

Cela va :
- ✅ Télécharger le dernier fichier EIOPA
- ✅ Extraire les taux EUR/FR
- ✅ Créer l'historique
- ✅ Générer les rapports

**Fichiers créés :**
- `data/historical.csv` - Base de données historique
- `data/latest_report.txt` - Rapport texte
- `data/latest_report.csv` - Rapport CSV
- `data/latest_report.xlsx` - Rapport Excel
- `logs/eiopa_monitoring_YYYYMM.log` - Logs

### 3️⃣ Visualiser les résultats (1 minute)

**Console :**
Le rapport s'affiche automatiquement dans le terminal.

**Dashboard interactif (optionnel) :**
```bash
pip install streamlit plotly  # Si pas encore fait
streamlit run app.py
```

→ Ouvre automatiquement dans votre navigateur à `http://localhost:8501`

### 4️⃣ Exécutions suivantes (1 minute)

**Mode automatique :**
```bash
python main.py  # Traite le dernier mois disponible
```

**Mode date spécifique :**
```bash
python main.py --date 2024-11-30
```

**Voir les fichiers disponibles :**
```bash
python main.py --list
```

---

## 📊 Cas d'usage typiques

### 🔄 Monitoring mensuel régulier

**Ajoutez à votre crontab (Linux/Mac) :**
```bash
# Tous les 5 du mois à 9h
0 9 5 * * cd /path/to/eiopa-monitoring && /path/to/venv/bin/python main.py
```

**Ou Task Scheduler (Windows) :**
1. Ouvrir "Planificateur de tâches"
2. Créer une tâche mensuelle
3. Action : `C:\path\to\venv\Scripts\python.exe`
4. Arguments : `main.py`
5. Dossier : `C:\path\to\eiopa-monitoring`

### 📈 Analyse d'une période

```python
from analyzer import EIOPAAnalyzer
from datetime import datetime

analyzer = EIOPAAnalyzer()

# Récupérer les taux 10Y sur 2024
ts = analyzer.get_time_series(
    country='FR',
    maturity=10,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)

print(ts)
```

### 🎯 Alertes sur variations importantes

Le système détecte automatiquement :
- ⚠️ Variations M/M > 50 bps
- ⚠️ Variations YTD > 100 bps

Personnalisable dans `config.py` :
```python
ALERT_THRESHOLD_MOM = 50   # Votre seuil M/M
ALERT_THRESHOLD_YTD = 100  # Votre seuil YTD
```

### 📊 Export vers Excel pour reporting

```python
from reporter import EIOPAReporter
from analyzer import EIOPAAnalyzer

# Charger la dernière analyse
analyzer = EIOPAAnalyzer()
# ... (récupérer les données)

# Générer Excel
reporter = EIOPAReporter()
reporter.generate_excel_report(analysis, "mon_rapport.xlsx")
```

---

## 🔧 Configuration rapide

**Changer le pays surveillé** (`config.py`) :
```python
TARGET_COUNTRY = "DE"  # Allemagne
TARGET_COUNTRY = "IT"  # Italie
TARGET_COUNTRY = "ES"  # Espagne
```

**Changer les maturités suivies** :
```python
TARGET_MATURITIES = [1, 2, 5, 10, 15, 20, 30, 50]
```

**Personnaliser les seuils d'alerte** :
```python
ALERT_THRESHOLD_MOM = 30   # Plus sensible
ALERT_THRESHOLD_YTD = 75
```

---

## 🆘 Résolution de problèmes

### ❌ "Module 'openpyxl' introuvable"
```bash
pip install openpyxl
```

### ❌ "Aucun fichier trouvé pour la date X"
→ Le fichier n'est peut-être pas encore publié. EIOPA publie début du mois suivant.

```bash
# Voir les dates disponibles
python main.py --list
```

### ❌ "Colonne pays non trouvée"
→ Format CSV changé. Vérifier `data/processed/` et ajuster `EXPECTED_COLUMNS` dans `config.py`.

### ❌ "Timeout lors du téléchargement"
→ Problème réseau ou site EIOPA indisponible. Le système réessaie 3 fois automatiquement.

### ⚠️ "Pas de comparaison M/M disponible"
→ Normal au premier lancement. Exécutez plusieurs fois pour constituer l'historique.

---

## 📚 Commandes essentielles

```bash
# Installation
./install.sh                    # Linux/Mac
install.bat                     # Windows

# Utilisation de base
python main.py                  # Dernier fichier
python main.py --date 2024-11-30  # Date spécifique
python main.py --list           # Lister fichiers
python main.py --stats          # Statistiques historique

# Dashboard
streamlit run app.py            # Interface web

# Exemples
python examples.py 1            # Exemple 1
python examples.py all          # Tous les exemples

# Tests modules individuels
python downloader.py            # Test téléchargement
python processor.py             # Test traitement
python analyzer.py              # Test analyse
python reporter.py              # Test rapports
```

---

## 💡 Astuces

### 1. Automatiser la sauvegarde des rapports

```bash
# Copier le rapport dans un dossier daté
python main.py && cp data/latest_report.xlsx "rapports/EIOPA_$(date +%Y%m%d).xlsx"
```

### 2. Surveiller plusieurs pays

Créer un script `multi_pays.py` :
```python
from config import TARGET_COUNTRY
import config

for pays in ['FR', 'DE', 'IT', 'ES']:
    config.TARGET_COUNTRY = pays
    # Exécuter le traitement
    ...
```

### 3. Intégration avec email

```python
import smtplib
from email.mime.text import MIMEText

def send_alert_email(analysis):
    if analysis['alerts']:
        msg = MIMEText(f"Alertes EIOPA: {analysis['alerts']}")
        msg['Subject'] = '⚠️ Alertes EIOPA'
        # Configurer SMTP et envoyer
```

### 4. Export vers base de données

```python
import sqlite3

def save_to_db(data):
    conn = sqlite3.connect('eiopa.db')
    # Insérer les données
    conn.close()
```

---

## 🎓 Prochaines étapes

Une fois familiarisé avec le système de base :

1. **Personnaliser les rapports** → Modifier `reporter.py`
2. **Ajouter des calculs** → Étendre `analyzer.py` (duration, convexité, etc.)
3. **Créer des visualisations** → Utiliser `matplotlib` ou `plotly`
4. **Automatiser complètement** → Scheduler + alertes email
5. **Intégrer à vos outils** → API, base de données, Excel VBA, etc.

---

## 📖 Documentation complète

→ Voir **README.md** pour la documentation détaillée

---

## ✅ Checklist de validation

Avant de mettre en production :

- [ ] Installation testée
- [ ] Premier téléchargement réussi
- [ ] Rapports générés correctement
- [ ] Historique constitué (≥2 mois)
- [ ] Comparaisons M/M/YTD fonctionnelles
- [ ] Alertes personnalisées configurées
- [ ] Automatisation planifiée (cron/Task Scheduler)
- [ ] Backup de `data/historical.csv` configuré

---

**Besoin d'aide ?** Consultez les logs dans `logs/` et la documentation complète dans `README.md`.

**Bon monitoring ! 📊**