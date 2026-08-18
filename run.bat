@echo off
REM Lance le dashboard avec l'interpreteur du venv du projet directement
REM (venv\Scripts\streamlit.exe), sans dependre du PATH ni d'une activation
REM manuelle du venv.
cd /d "%~dp0"

if not exist "venv\Scripts\streamlit.exe" (
    echo venv\Scripts\streamlit.exe introuvable. Creez le venv d'abord :
    echo    python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
    exit /b 1
)

venv\Scripts\streamlit.exe run app.py %*
