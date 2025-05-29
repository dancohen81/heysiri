@echo off
echo 🎤 Voice Chat App (Einfacher Start)

REM Prüfen ob Python verfügbar ist
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ FEHLER: Python nicht gefunden!
    pause
    exit /b 1
)

REM Prüfen ob voice_chat_app.py existiert
if not exist "voice_chat_app.py" (
    echo ❌ FEHLER: voice_chat_app.py nicht gefunden!
    echo Bitte speichere die Hauptdatei aus dem Artifact.
    pause
    exit /b 1
)

REM .env Datei prüfen
if exist ".env" (
    echo ✅ .env Datei gefunden
) else (
    echo ⚠️ .env Datei nicht gefunden
    if exist ".env.example" (
        echo 📝 Erstelle .env aus Vorlage...
        copy .env.example .env >nul
        echo ✅ .env erstellt! Bitte fülle deine API Keys ein und starte neu.
        pause
        exit /b 0
    )
)

echo 🚀 Starte App direkt mit Python...

REM Versuche zuerst mit UV (falls vorhanden)
uv --version >nul 2>&1
if not errorlevel 1 (
    echo 📦 Verwende UV...
    uv run --with-requirements requirements.txt python voice_chat_app.py
) else (
    REM Fallback: Standard Python mit pip
    echo 📦 Verwende Standard Python...
    if not exist "venv" (
        echo 🔨 Erstelle virtuelle Umgebung...
        python -m venv venv
    )
    
    call venv\Scripts\activate.bat
    pip install -q -r requirements.txt
    python voice_chat_app.py
)

if errorlevel 1 (
    echo ❌ Fehler beim Starten!
    pause
)