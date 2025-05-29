@echo off
echo ====================================
echo Voice Chat App Setup (mit UV)
echo ====================================
echo.

REM Prüfen ob requirements.txt existiert
if not exist "requirements.txt" (
    echo FEHLER: requirements.txt nicht gefunden!
    echo Bitte kopiere alle Dateien aus den Artifacts in diesen Ordner.
    echo Benötigt: voice_chat_app.py, requirements.txt, etc.
    pause
    exit /b 1
)

REM Prüfen ob uv installiert ist
echo [1/5] Prüfe UV Installation...
uv --version >nul 2>&1
if errorlevel 1 (
    echo UV nicht gefunden. Installiere UV...
    echo Lade UV herunter...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://astral.sh/uv/install.ps1' -OutFile 'install-uv.ps1'; .\install-uv.ps1; Remove-Item 'install-uv.ps1'}"
    
    REM UV zum PATH hinzufügen für diese Session
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
    
    REM Nochmal prüfen
    uv --version >nul 2>&1
    if errorlevel 1 (
        echo FEHLER: UV Installation fehlgeschlagen!
        echo Bitte installiere UV manuell: https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
)

echo [2/5] Erstelle Projekt mit UV...
uv init --python 3.11 voice-chat-project
if errorlevel 1 (
    echo Verwende lokales Verzeichnis...
)

echo [3/5] Virtuelle Umgebung wird erstellt...
uv venv
if errorlevel 1 (
    echo FEHLER: Konnte virtuelle Umgebung nicht erstellen!
    pause
    exit /b 1
)

echo [4/5] Abhängigkeiten werden installiert...
uv pip install -r requirements.txt
if errorlevel 1 (
    echo FEHLER: Installation der Abhängigkeiten fehlgeschlagen!
    pause
    exit /b 1
)

echo [5/5] Setup überprüfen...
uv run python -c "import PyQt5, openai, sounddevice, scipy, numpy; print('✅ Alle wichtigen Module verfügbar!')"
if errorlevel 1 (
    echo ⚠️ WARNUNG: Einige Module könnten fehlen!
)

echo.
echo ====================================
echo ✅ Setup abgeschlossen!
echo ====================================
echo.
echo 🔑 NÄCHSTER SCHRITT: API Keys einrichten
echo.
echo Option 1 - .env Datei (EMPFOHLEN):
echo   1. copy .env.example .env
echo   2. Bearbeite .env mit deinen echten API Keys
echo.
echo Option 2 - Windows Umgebungsvariablen:
echo   setx OPENAI_API_KEY "dein_openai_key"
echo   setx CLAUDE_API_KEY "dein_claude_key"  
echo   setx ELEVENLABS_API_KEY "dein_elevenlabs_key"
echo.
echo 🚀 Danach starten mit:
echo   start.bat
echo.
echo oder manuell:
echo   uv run python -m src.main
echo.

REM .env Datei automatisch erstellen falls nicht vorhanden
if not exist ".env" (
    if exist ".env.example" (
        echo 📝 Erstelle .env Datei aus Vorlage...
        copy .env.example .env >nul
        echo ✅ .env Datei erstellt! Bitte fülle deine API Keys ein.
    )
)

pause
