#!/bin/bash

# Script d'installation pour le système de monitoring EIOPA
# Compatible : Linux, macOS

set -e  # Arrêter en cas d'erreur

echo "=========================================="
echo "Installation EIOPA Monitoring System"
echo "=========================================="
echo ""

# Vérifier Python
echo "🔍 Vérification de Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    echo "   Installez Python 3.8+ depuis https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python $PYTHON_VERSION détecté"

# Créer l'environnement virtuel
echo ""
echo "📦 Création de l'environnement virtuel..."
if [ -d "venv" ]; then
    echo "   ⚠️  venv existe déjà, suppression..."
    rm -rf venv
fi

python3 -m venv venv
echo "✅ Environnement virtuel créé"

# Activer l'environnement
echo ""
echo "🔧 Activation de l'environnement..."
source venv/bin/activate

# Mettre à jour pip
echo ""
echo "⬆️  Mise à jour de pip..."
pip install --upgrade pip > /dev/null 2>&1

# Installer les dépendances
echo ""
echo "📥 Installation des dépendances..."
pip install -r requirements.txt

echo ""
echo "✅ Installation terminée avec succès!"
echo ""
echo "=========================================="
echo "PROCHAINES ÉTAPES"
echo "=========================================="
echo ""
echo "1. Activer l'environnement :"
echo "   source venv/bin/activate"
echo ""
echo "2. Tester l'installation :"
echo "   python3 main.py --list"
echo ""
echo "3. Première exécution :"
echo "   python3 main.py"
echo ""
echo "4. Lancer le dashboard (optionnel) :"
echo "   streamlit run app.py"
echo ""
echo "5. Voir les exemples :"
echo "   python3 examples.py all"
echo ""
echo "=========================================="
echo "Documentation : README.md"
echo "=========================================="