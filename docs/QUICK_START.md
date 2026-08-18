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

### 3. Ingérer les données

Dans le dashboard, aller dans **🔄 Mise à jour** :
- Les dates disponibles sur le site EIOPA s'affichent automatiquement, avec leur statut ("Déjà traité" / "À télécharger")
- Sélectionner les mois souhaités
- Cliquer sur **Lancer le téléchargement**

Chaque mois ingéré est écrit dans `data/historical.db` (courbes complètes 0-150 Base/Up/Down, NO_VA et WITH_VA, métadonnées VA/LLP/UFR/alpha/CRA/Coupon_freq). Rien n'est exporté en CSV à cette étape.

### 4. Exporter pour le GSE / Asset_PTF

Aller dans **📤 Export** :
- Choisir la date de clôture et le type de courbe (NO_VA / WITH_VA / les deux)
- Cliquer sur **Générer l'export**, puis télécharger le(s) CSV produit(s)

---

## En ligne de commande

```bash
# Ingestion : dernier mois disponible
python main.py

# Ingestion : mois spécifique
python main.py --date 2024-11-30

# Voir les fichiers disponibles sur l'EIOPA
python main.py --list

# Export : les deux fichiers (NO_VA + WITH_VA) pour un mois déjà ingéré
python main.py --export --date 2024-11-30

# Export : uniquement WITH_VA, pour le mois le plus récent en base
python main.py --export --va-type WITH_VA
```

---

## Format du CSV exporté

```
Maturity,Base,Up,Down
0,0.00000,0.00000,0.00000
1,0.02607,0.04432,0.00652
...
150,0.03165,0.04164,0.02539
```

151 lignes (maturités 0 à 150). Format partagé par le GSE et Asset_PTF — à brancher directement sur l'un ou l'autre.

---

## Configuration rapide

Tout se règle dans `config.py` :

```python
TARGET_COUNTRY    = "FR"                # Changer pour "DE", "IT", etc.
TARGET_MATURITIES = [1, 5, 10, 20, 30]  # Maturités des comparaisons M/M et YTD
ALERT_THRESHOLD_MOM = 50                # Alerte si variation M/M > 50 bps
ALERT_THRESHOLD_YTD = 100               # Alerte si variation YTD > 100 bps
```

---

## Structure des données

```
data/
├── raw/            → ZIP téléchargés depuis l'EIOPA
├── extracts/       → Fichiers Excel extraits
├── processed/      → CSV exportés (Maturity,Base,Up,Down) pour GSE/Asset_PTF
├── db_backups/     → Sauvegardes locales de historical.db (non versionnées)
├── historical.db   → Source de vérité, base SQLite ← à versionner
├── historical.csv  → Export lisible régénéré depuis historical.db (informatif)
└── latest_report.* → Dernier rapport (txt / csv / xlsx)
```

---

## Déploiement hébergé (Streamlit Community Cloud)

L'instance hébergée est en lecture seule par nature (disque éphémère) : la production reste locale (`main.py` ou dashboard local), suivie d'un `git push` de `historical.db`. Détails et activation du mode lecture seule → `README.md`, section "Déploiement".

---

## En cas de problème

Consulter les logs :
```
logs/eiopa_monitoring_YYYYMM.log
```

Documentation complète → `README.md`
