import sys
import subprocess
import os

print("=" * 60)
print("DIAGNOSTIC COMPLET ENVIRONNEMENT EIOPA")
print("=" * 60)

# 1. Informations système
print("\n1. INFORMATIONS SYSTÈME:")
print(f"   Python exécutable: {sys.executable}")
print(f"   Version Python: {sys.version}")
print(f"   Répertoire courant: {os.getcwd()}")
print(f"   Environnement virtuel: {'venv' in sys.executable}")

# 2. Vérifier l'activation de venv
venv_path = "/Users/slimsaanouni/Desktop/Streamlit/EIOPA_RFR/venv"
print("\n2. ENVIRONNEMENT VIRTUEL:")
print(f"   Chemin venv: {venv_path}")
print(f"   Venv existe: {os.path.exists(venv_path)}")

if os.path.exists(venv_path):
    # Vérifier si activé
    if 'VIRTUAL_ENV' in os.environ:
        print(f"   ✅ Venv ACTIVÉ: {os.environ['VIRTUAL_ENV']}")
    else:
        print("   ⚠️ Venv NON activé (mais présent)")

# 3. Vérifier les packages
print("\n3. PACKAGES INSTALLÉS:")

packages_to_check = ['openpyxl', 'pandas', 'numpy', 'requests']

for package in packages_to_check:
    try:
        module = __import__(package)
        version = getattr(module, '__version__', 'version inconnue')
        print(f"   ✅ {package}: {version}")
    except ImportError:
        print(f"   ❌ {package}: NON INSTALLÉ")

# 4. Vérifier pip dans venv
print("\n4. VÉRIFICATION PIP:")
try:
    # Utiliser le pip du venv
    if sys.platform == "win32":
        pip_path = os.path.join(venv_path, "Scripts", "pip")
    else:
        pip_path = os.path.join(venv_path, "bin", "pip")
    
    if os.path.exists(pip_path):
        print(f"   ✅ Pip trouvé: {pip_path}")
        # Tester une installation
        print("\n5. TEST D'INSTALLATION:")
        print("   Installation de openpyxl...")
        subprocess.run([pip_path, "install", "openpyxl"], check=True)
        print("   ✅ Installation terminée")
    else:
        print(f"   ⚠️ Pip non trouvé à: {pip_path}")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

print("\n" + "=" * 60)