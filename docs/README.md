# Monitoring EIOPA — Taux Sans Risque (RFR)

## Objectifs

Cet outil remplit deux fonctions :

1. **Constituer une base de courbes de taux sans risque** (historique complet, avec VA et sans VA, courbes Base/Up/Down) prête à l'emploi pour d'autres outils actuariels — GSE (génération de scénarios économiques) et Asset_PTF (génération de portefeuille ALM avec chocs S2).
2. **Suivre l'évolution historique** des taux publiés mensuellement par l'EIOPA dans le cadre de Solvency II.

---

## Architecture

```
EIOPA_RFR/
├── config.py               # Tous les paramètres centralisés
├── main.py                 # Point d'entrée CLI
├── app.py                  # Dashboard Streamlit
├── requirements.txt
│
├── src/
│   ├── downloader.py       # Téléchargement depuis le site EIOPA
│   ├── ingestion.py        # Extraction Excel -> écriture SQLite (courbes + métadonnées)
│   ├── exporter.py         # Génération des CSV Maturity,Base,Up,Down (GSE / Asset_PTF)
│   ├── db.py                # Accès à historical.db (schéma, transactions, requêtes)
│   ├── schema.sql            # Définition des tables curves / curve_metadata / ingestion_runs
│   ├── analyzer.py          # Comparaisons M/M, YTD, alertes (lecture seule sur la base)
│   ├── reporter.py          # Rapports texte / CSV / Excel
│   └── utils.py              # Fonctions utilitaires partagées
│
└── data/
    ├── raw/                # ZIP téléchargés depuis l'EIOPA
    ├── extracts/           # Fichiers Excel extraits des ZIP EIOPA
    ├── processed/          # CSV exportés pour le GSE/Asset_PTF (RFR_*.csv)
    ├── db_backups/         # Sauvegardes horodatées de historical.db (locales, non versionnées)
    ├── historical.db       # Source de vérité — base SQLite versionnée dans git
    └── historical.csv      # Export lisible régénéré depuis historical.db (plus la source de vérité)
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

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Couvre la logique la plus critique : formule des chocs IR, contraintes du schéma SQLite, tolérances de date des comparaisons M/M et YTD, format des exports. Exécutés automatiquement sur chaque push/PR vers `main` (`.github/workflows/tests.yml`).

---

## Utilisation

### Dashboard interactif (recommandé)

```bash
streamlit run app.py
```

Le dashboard permet de :
- Visualiser la courbe des taux actuelle et son historique
- Télécharger un ou plusieurs mois en une seule action ("🔄 Mise à jour")
- Comparer deux dates et détecter les alertes ("📊 Analyse")
- Générer les fichiers d'export pour GSE/Asset_PTF sur une date et un type de courbe donnés ("📤 Export")

### Ligne de commande

```bash
# Télécharger et ingérer le dernier fichier disponible
python main.py

# Ingérer un mois spécifique
python main.py --date 2024-11-30

# Lister les fichiers disponibles sur le site EIOPA
python main.py --list

# Afficher les statistiques de l'historique
python main.py --stats

# Exporter une courbe déjà ingérée (les deux fichiers NO_VA + WITH_VA par défaut)
python main.py --export --date 2024-11-30

# Exporter uniquement WITH_VA pour la date la plus récente en base
python main.py --export --va-type WITH_VA
```

---

## Fichiers produits

### Pour le GSE / Asset_PTF (dans `data/processed/`, sur demande — voir "📤 Export")

Générés explicitement (dashboard ou `main.py --export`), pas automatiquement à chaque ingestion — l'ingestion mensuelle n'écrit que dans `historical.db`.

| Fichier | Contenu |
|---|---|
| `RFR_[DATE]_NO_VA.csv` | Courbe base + chocs IR, sans Volatility Adjustment |
| `RFR_[DATE]_WITH_VA.csv` | Courbe base + chocs IR, avec Volatility Adjustment |

Format : 151 lignes (maturités 0 à 150), 4 colonnes, séparateur virgule :

```
Maturity,Base,Up,Down
0,0.00000,0.00000,0.00000
1,0.02607,0.04432,0.00652
...
```

Format partagé par le GSE (New_Gen) et Asset_PTF — les deux projets lisent ce même schéma. Le choix entre `NO_VA` et `WITH_VA` pour alimenter un outil donné est une décision méthodologique documentée séparément (pas fixée par cet outil) : le dashboard/CLI demandent explicitement quel type de courbe exporter, à chaque export.

Les chocs Up/Down sont recalculés depuis l'onglet `Shocks` du fichier Excel EIOPA (les onglets de choc pré-calculés d'EIOPA contiennent des formules non fiables — cf. Dépannage) :
```
Up   = ROUND(base + MAX(0.01, shock_up   × |base|), 5)
Down = ROUND(base − MAX(0.00, shock_down × |base|), 5)
```

### Pour le suivi historique

| Fichier | Contenu |
|---|---|
| `data/historical.db` | **Source de vérité.** Base SQLite : courbes complètes (0-150, Base/Up/Down, NO_VA/WITH_VA) et métadonnées (VA, LLP, Convergence, UFR, alpha, CRA, Coupon_freq) pour chaque mois ingéré. À versionner. |
| `data/historical.csv` | Export lisible régénéré depuis `historical.db` (taux cibles 1Y/5Y/10Y/20Y/30Y + VA) — pratique pour un coup d'œil rapide ou un diff git, mais jamais écrit directement. |
| `data/latest_report.txt/.csv/.xlsx` | Rapport du dernier traitement (taux, métadonnées, variations, alertes) |

---

## Configuration (`config.py`)

| Paramètre | Défaut | Variable d'environnement | Description |
|---|---|---|---|
| `TARGET_COUNTRY` | `"FR"` | — | Pays à extraire (`"DE"`, `"IT"`, etc.) — non surchargeable, voir "Points d'attention" |
| `TARGET_MATURITIES` | `[1, 5, 10, 20, 30]` | — | Maturités suivies pour les comparaisons M/M et YTD |
| `ALERT_THRESHOLD_MOM` | `50` | `EIOPA_ALERT_THRESHOLD_MOM` | Seuil d'alerte variation M/M (bps) |
| `ALERT_THRESHOLD_YTD` | `100` | `EIOPA_ALERT_THRESHOLD_YTD` | Seuil d'alerte variation YTD (bps) |
| `REQUEST_TIMEOUT` | `30` | `EIOPA_REQUEST_TIMEOUT` | Timeout réseau (secondes) |
| `MAX_RETRIES` | `3` | `EIOPA_MAX_RETRIES` | Tentatives avant échec sur téléchargement/scraping |
| `HISTORICAL_DB` | `data/historical.db` | — | Base SQLite (source de vérité) |
| `DB_BACKUP_KEEP` | `14` | `EIOPA_DB_BACKUP_KEEP` | Nombre de jours distincts de sauvegarde conservés (1 backup/jour max) |

Les paramètres surchargeables par variable d'environnement le sont pour permettre à une autre équipe déployant sa propre instance d'ajuster ces valeurs sans toucher au code (ex. `EIOPA_ALERT_THRESHOLD_MOM=75 streamlit run app.py`). Une valeur invalide (non numérique) retombe silencieusement sur le défaut.

---

## Automatisation mensuelle

**Linux / Mac (cron) :**
```bash
crontab -e
# Exécution le 5 de chaque mois à 9h
0 9 5 * * cd /chemin/EIOPA_RFR && venv/bin/python main.py && git -C /chemin/EIOPA_RFR add data/historical.db data/historical.csv && git -C /chemin/EIOPA_RFR commit -m "DATA: ingestion $(date +\%Y-\%m)" && git -C /chemin/EIOPA_RFR push
```

**Windows (Planificateur de tâches) :**
- Programme : `C:\chemin\venv\Scripts\python.exe`
- Arguments : `main.py`
- Déclencheur : mensuel, jour 5, 09:00
- Le `git add`/`commit`/`push` reste à faire manuellement, ou via un script batch séparé.

Si le dashboard est déployé (voir ci-dessous), penser à pousser `historical.db` sur git après chaque ingestion locale — l'instance hébergée ne se met à jour qu'au redéploiement suivant.

---

## Déploiement (Streamlit Community Cloud)

L'instance hébergée est **en lecture seule** : son disque est éphémère (tout ce qui y est écrit disparaît au redémarrage/redeploy), et elle ne partage aucun système de fichiers avec la machine locale où tournent GSE/Asset_PTF. La production de donnée reste donc un processus **local**, versionné :

1. En local : `python main.py` (ou le dashboard local, page "🔄 Mise à jour") ingère le nouveau mois dans `historical.db`.
2. `git add data/historical.db data/historical.csv && git commit && git push`.
3. Streamlit Community Cloud redéploie automatiquement depuis la branche suivie et sert la base à jour.

Pour activer le mode lecture seule sur l'instance hébergée (désactive la page "Mise à jour", affiche un bandeau explicite), ajouter dans les **Secrets** de l'app sur Streamlit Community Cloud :

```toml
READONLY_DASHBOARD = true
```

Sans ce secret (cas par défaut, y compris en local), le dashboard reste pleinement fonctionnel — c'est un opt-in explicite pour l'instance hébergée, pas un comportement déduit automatiquement de l'environnement.

La page "📤 Export" reste disponible sur l'instance hébergée : elle ne fait que lire `historical.db` (déjà à jour via le push git) et proposer un téléchargement, sans écriture serveur persistante.

---

## Dépannage

| Erreur | Cause | Solution |
|---|---|---|
| `Aucun fichier trouvé pour la date X` | Fichier non encore publié | EIOPA publie début du mois suivant. Utiliser `--list` pour voir les dates disponibles. |
| `Colonne pays introuvable` | Format Excel modifié par l'EIOPA | Vérifier les noms de colonnes dans `data/extracts/` et mettre à jour `COUNTRY_ALIASES` dans `src/ingestion.py`. |
| `Aucune courbe ... en base` lors d'un export | Mois jamais ingéré | Lancer `main.py --date <date>` (ou la page "Mise à jour") avant d'exporter. |
| `Module openpyxl introuvable` | Dépendance manquante | `pip install openpyxl` |
| Chocs Up/Down à 0 dans un CSV | Formules Excel non calculées côté EIOPA | Normal : les chocs sont recalculés directement en Python depuis l'onglet `Shocks`, jamais lus depuis les onglets de choc pré-calculés d'EIOPA (peu fiables). |

---

## Points d'attention

- **Format EIOPA** : le format du fichier Excel peut évoluer. En cas de rupture, vérifier les noms d'onglets et de colonnes dans `src/ingestion.py` (`SHEET_NAMES`, `COUNTRY_ALIASES`, `METADATA_LABELS`).
- **Dates de publication** : l'EIOPA publie les données du mois M entre le 5 et le 10 du mois M+1.
- **Historique** : `data/historical.db` est la source de vérité — à versionner et sauvegarder régulièrement (des sauvegardes horodatées locales sont aussi créées automatiquement dans `data/db_backups/` avant chaque écriture).
- **Choix NO_VA/WITH_VA à l'export** : jamais décidé par cet outil — la convention à appliquer selon l'outil consommateur (GSE, Asset_PTF, ou futur outil) est une décision méthodologique à documenter séparément.
