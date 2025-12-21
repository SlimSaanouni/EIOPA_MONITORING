#!/bin/bash

# Script de téléchargement et traitement en masse des fichiers EIOPA
# Usage: ./bulk_download.sh [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--limit N]

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paramètres par défaut
START_DATE=""
END_DATE=""
LIMIT=""
FORCE=false

# Parser les arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --start-date YYYY-MM-DD  Date de début (incluse)"
            echo "  --end-date YYYY-MM-DD    Date de fin (incluse)"
            echo "  --limit N                Nombre maximum de fichiers à traiter"
            echo "  --force                  Forcer le re-téléchargement"
            echo "  --help                   Afficher cette aide"
            echo ""
            echo "Exemples:"
            echo "  $0                                    # Tous les fichiers disponibles"
            echo "  $0 --limit 10                         # Les 10 derniers fichiers"
            echo "  $0 --start-date 2024-01-01            # Depuis janvier 2024"
            echo "  $0 --start-date 2023-01-01 --end-date 2023-12-31  # Année 2023"
            exit 0
            ;;
        *)
            echo "Option inconnue: $1"
            echo "Utilisez --help pour l'aide"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TÉLÉCHARGEMENT EN MASSE EIOPA${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Vérifier que Python est disponible
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python n'est pas installé${NC}"
    exit 1
fi

# Utiliser python3 ou python
PYTHON_CMD=$(command -v python3 || command -v python)

# Vérifier que le script main.py existe
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ main.py introuvable${NC}"
    echo "Assurez-vous d'exécuter ce script depuis le dossier eiopa-monitoring/"
    exit 1
fi

# Créer un script Python temporaire pour lister les dates
cat > /tmp/list_eiopa_dates.py << 'PYTHON_SCRIPT'
import sys
sys.path.insert(0, '.')

from src.downloader import EIOPADownloader
from datetime import datetime
import json

try:
    downloader = EIOPADownloader()
    files = downloader.get_available_files()
    
    dates_info = []
    for filename, url, date in files:
        dates_info.append({
            'filename': filename,
            'date': date.strftime('%Y-%m-%d'),
            'url': url
        })
    
    print(json.dumps(dates_info))
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT

echo -e "${YELLOW}📋 Récupération de la liste des fichiers disponibles...${NC}"

# Récupérer la liste des dates
DATES_JSON=$($PYTHON_CMD /tmp/list_eiopa_dates.py)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Erreur lors de la récupération des fichiers disponibles${NC}"
    rm -f /tmp/list_eiopa_dates.py
    exit 1
fi

rm -f /tmp/list_eiopa_dates.py

# Parser le JSON et filtrer les dates (sans jq)
DATES_TO_PROCESS=()

while IFS= read -r line; do
    # Extraire date et filename avec Python
    date=$(echo "$line" | $PYTHON_CMD -c "import sys, json; d=json.load(sys.stdin); print(d['date'])")
    filename=$(echo "$line" | $PYTHON_CMD -c "import sys, json; d=json.load(sys.stdin); print(d['filename'])")
    
    # Filtrer par date de début
    if [ -n "$START_DATE" ]; then
        if [[ "$date" < "$START_DATE" ]]; then
            continue
        fi
    fi
    
    # Filtrer par date de fin
    if [ -n "$END_DATE" ]; then
        if [[ "$date" > "$END_DATE" ]]; then
            continue
        fi
    fi
    
    DATES_TO_PROCESS+=("$date|$filename")
done < <(echo "$DATES_JSON" | $PYTHON_CMD -c "import sys, json; [print(json.dumps(x)) for x in json.load(sys.stdin)]")

# Appliquer la limite
if [ -n "$LIMIT" ]; then
    DATES_TO_PROCESS=("${DATES_TO_PROCESS[@]:0:$LIMIT}")
fi

TOTAL_FILES=${#DATES_TO_PROCESS[@]}

if [ $TOTAL_FILES -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucun fichier à traiter avec les critères sélectionnés${NC}"
    exit 0
fi

echo -e "${GREEN}✅ ${TOTAL_FILES} fichier(s) à traiter${NC}"
echo ""

# Afficher les dates qui seront traitées
echo -e "${BLUE}Dates sélectionnées :${NC}"
for entry in "${DATES_TO_PROCESS[@]}"; do
    date=$(echo "$entry" | cut -d'|' -f1)
    echo "  - $date"
done
echo ""

# Demander confirmation
read -p "Continuer ? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Annulé${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}DÉBUT DU TRAITEMENT${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Compteurs
SUCCESS_COUNT=0
ERROR_COUNT=0
SKIPPED_COUNT=0

# Créer un fichier de log
LOG_FILE="logs/bulk_download_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo "Traitement démarré à $(date)" > "$LOG_FILE"
echo "Nombre de fichiers : $TOTAL_FILES" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Traiter chaque date
CURRENT=0
for entry in "${DATES_TO_PROCESS[@]}"; do
    CURRENT=$((CURRENT + 1))
    date=$(echo "$entry" | cut -d'|' -f1)
    filename=$(echo "$entry" | cut -d'|' -f2)
    
    echo -e "${BLUE}[$CURRENT/$TOTAL_FILES]${NC} Traitement de $date ($filename)..."
    echo "----------------------------------------" | tee -a "$LOG_FILE"
    echo "[$CURRENT/$TOTAL_FILES] Date: $date" | tee -a "$LOG_FILE"
    
    # Construire la commande
    CMD="$PYTHON_CMD main.py --date $date"
    if [ "$FORCE" = true ]; then
        CMD="$CMD --force"
    fi
    
    # Exécuter le traitement
    if $CMD >> "$LOG_FILE" 2>&1; then
        echo -e "${GREEN}  ✅ Succès${NC}"
        echo "  ✅ Succès" >> "$LOG_FILE"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 2 ]; then
            echo -e "${YELLOW}  ⏭️  Déjà traité (ignoré)${NC}"
            echo "  ⏭️  Déjà traité" >> "$LOG_FILE"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo -e "${RED}  ❌ Erreur${NC}"
            echo "  ❌ Erreur (code: $EXIT_CODE)" >> "$LOG_FILE"
            ERROR_COUNT=$((ERROR_COUNT + 1))
        fi
    fi
    
    echo "" | tee -a "$LOG_FILE"
    
    # Petite pause pour ne pas surcharger le serveur
    if [ $CURRENT -lt $TOTAL_FILES ]; then
        sleep 2
    fi
done

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RÉSUMÉ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Total traité  : ${BLUE}$TOTAL_FILES${NC}"
echo -e "Succès        : ${GREEN}$SUCCESS_COUNT${NC}"
echo -e "Erreurs       : ${RED}$ERROR_COUNT${NC}"
echo -e "Ignorés       : ${YELLOW}$SKIPPED_COUNT${NC}"
echo ""
echo -e "Log détaillé  : ${LOG_FILE}"
echo ""

# Résumé dans le log
echo "========================================" >> "$LOG_FILE"
echo "RÉSUMÉ FINAL" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "Total traité : $TOTAL_FILES" >> "$LOG_FILE"
echo "Succès       : $SUCCESS_COUNT" >> "$LOG_FILE"
echo "Erreurs      : $ERROR_COUNT" >> "$LOG_FILE"
echo "Ignorés      : $SKIPPED_COUNT" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
echo "Traitement terminé à $(date)" >> "$LOG_FILE"

if [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ Traitement terminé avec succès !${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Traitement terminé avec des erreurs${NC}"
    echo -e "Consultez le log : ${LOG_FILE}"
    exit 1
fi