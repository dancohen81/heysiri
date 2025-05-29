@echo off
echo 🎤 Voice Chat App wird gestartet...

REM Prüfen ob uv verfügbar ist
uv --version >nul 2>&1
if errorlevel 1 (
    echo ❌ FEHLER: UV nicht gefunden!
    echo Bitte führe zuerst setup.bat aus.
    pause
    exit /b 1
)

REM Prüfen ob virtuelle Umgebung existiert
if not exist ".venv" (
    echo ❌ FEHLER: Virtuelle Umgebung nicht gefunden!
    echo Bitte führe zuerst setup.bat aus.
    pause
    exit /b 1
)

REM API Keys prüfen
set "keys_found=0"

if exist ".env" (
    echo ✅ .env Datei gefunden
    set "keys_found=1"
) else (
    if not "%OPENAI_API_KEY%"=="" (
        echo ✅ OPENAI_API_KEY in Umgebungsvariablen gefunden
        set "keys_found=1"
    ) else (
        echo ⚠️ OPENAI_API_KEY nicht gefunden!
    )
    
    if not "%CLAUDE_API_KEY%"=="" (
        echo ✅ CLAUDE_API_KEY in Umgebungsvariablen gefunden
    ) else (
        echo ⚠️ CLAUDE_API_KEY nicht gefunden!
    )
)

if "%keys_found%"=="0" (
    echo.
    echo ❌ Keine API Keys gefunden!
    echo Lösung 1: Erstelle .env Datei mit deinen Keys
    echo Lösung 2: Setze Umgebungsvariablen mit setx
    echo.
    pause
    exit /b 1
)

REM App starten mit UV
echo 🚀 Starte Voice Chat App mit UV...
uv run python voice_chat_app.py

REM Falls Fehler auftreten
if errorlevel 1 (
    echo.
    echo ❌ App wurde mit Fehler beendet.
    echo Prüfe die Fehlermeldungen oben.
    pause
)