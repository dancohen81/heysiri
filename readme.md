# 🎤 Voice Chat App mit Claude

Eine erweiterte Sprachaufzeichnungs-App, die es ermöglicht, per Sprache mit Claude AI zu chatten. Die App läuft im System Tray und bietet eine nahtlose Sprach-zu-Text-zu-Chat-zu-Sprache Erfahrung.

## 🚀 Features

- **🎙️ Sprachaufzeichnung:** Einfach Leertaste halten zum Aufnehmen
- **🤖 Claude AI Integration:** Direkte Kommunikation mit Claude über API
- **🔊 Text-to-Speech:** Optional mit ElevenLabs für gesprochene Antworten
- **💾 Chat-Verlauf:** Lokale Speicherung aller Gespräche
- **🖥️ System Tray:** Läuft diskret im Hintergrund
- **🎯 Kontextbewusst:** Claude "erinnert" sich an vorherige Nachrichten
- **⚡ Autostart:** Optional automatischer Start mit Windows

## 📋 Workflow

1. **Leertaste halten** → Audio wird aufgenommen
2. **Loslassen** → Whisper transkribiert zu Text  
3. **Automatisch** → Text wird an Claude gesendet
4. **Antwort** → Claude antwortet im Chat-Fenster
5. **Optional** → ElevenLabs wandelt Antwort in Sprache um

## 🛠️ Installation

### Voraussetzungen

- Python 3.8+ (getestet mit Python 3.9-3.11)
- Windows 10/11 (für System Tray Integration)
- Mikrofon
- Internetverbindung

### Schritt 1: Repository klonen/herunterladen

```bash
git clone <dein-repo-url>
cd voice-chat-app
```

### Schritt 2: Automatisches Setup (empfohlen)

```cmd
setup.bat
```

Das Setup-Skript erstellt automatisch:
- Virtuelle Python-Umgebung (`venv/`)
- Installation aller Abhängigkeiten
- Überprüfung der Installation

### Schritt 3: API Keys einrichten

Du benötigst mindestens die ersten beiden API Keys:

#### OpenAI API Key (erforderlich)
1. Gehe zu https://platform.openai.com/api-keys
2. Erstelle einen neuen API Key
3. Kopiere den Key

#### Claude API Key (erforderlich)  
1. Gehe zu https://console.anthropic.com/
2. Erstelle einen Account falls nötig
3. Generiere einen API Key
4. Kopiere den Key

#### ElevenLabs API Key (optional)
1. Gehe zu https://elevenlabs.io/
2. Erstelle einen Account (kostenlose Kontingente verfügbar)
3. Hole dir deinen API Key aus den Settings
4. Kopiere den Key

### Schritt 4: Umgebungsvariablen setzen

**Windows (permanent):**
```cmd
setx OPENAI_API_KEY "dein_openai_key_hier"
setx CLAUDE_API_KEY "dein_claude_key_hier"
setx ELEVENLABS_API_KEY "dein_elevenlabs_key_hier"
```

**WICHTIG:** Nach dem Setzen mit `setx` musst du ein neues CMD-Fenster öffnen!

**Temporär (nur für aktuelle Session):**
```cmd
set OPENAI_API_KEY=dein_openai_key_hier
set CLAUDE_API_KEY=dein_claude_key_hier
set ELEVENLABS_API_KEY=dein_elevenlabs_key_hier
```

### Schritt 5: App starten

```cmd
call venv\Scripts\activate.bat
python src/main.py
```

### Einrichtung des Fileman MCP Servers

Die Voice Chat App kann mit einem lokalen Fileman MCP Server interagieren, um Dateien zu speichern. So richten Sie ihn ein:

#### Voraussetzungen

-   **Node.js und npm (oder yarn):** Stellen Sie sicher, dass Node.js und ein Paketmanager (npm oder yarn) auf Ihrem System installiert sind. Sie können diese von der offiziellen Node.js-Website herunterladen.

#### Schritt 1: Fileman Server klonen/herunterladen

Der Fileman MCP Server ist ein separates Projekt. Sie müssen es klonen oder herunterladen:

```bash
git clone https://github.com/modelcontextprotocol/servers.git
cd servers/src/filesystem
```
*(Hinweis: Der genaue Pfad kann je nach Ihrem Setup variieren. Stellen Sie sicher, dass Sie in das Verzeichnis wechseln, das die `package.json` des Fileman Servers enthält.)*

#### Schritt 2: Abhängigkeiten installieren

Navigieren Sie im Terminal in das `fileman` Server-Verzeichnis (z.B. `servers/src/fileman`) und installieren Sie die Abhängigkeiten:

```bash
npm install
# oder
yarn install
```

#### Schritt 3: Fileman Server bauen und starten

Bauen Sie den Fileman Server und starten Sie ihn. Er wird standardmäßig auf Port `3000` laufen.

```bash
npm run build
# oder
yarn build
```

Danach starten Sie den Server:

```bash
node dist/index.js "D:/Users/stefa/heysiri"
```
*(Hinweis: Der Fileman Server benötigt mindestens ein Verzeichnis, in dem er Operationen ausführen darf. Hier wird das Hauptverzeichnis der Voice Chat App als erlaubtes Verzeichnis angegeben. Sie können auch andere Pfade hinzufügen, z.B. `node dist/index.js "D:/Users/stefa/heysiri" "C:/Users/stefa/Dokumente"`)*

Lassen Sie dieses Terminalfenster geöffnet, da der Server im Hintergrund laufen muss, damit die Voice Chat App mit ihm kommunizieren kann. Die App erwartet, dass der Server unter `http://localhost:3000/tool_use` erreichbar ist (konfiguriert in `config.py`).

## 🎯 Verwendung

### Erste Schritte
1. Nach dem Start erscheint ein kleines Fenster und ein Icon im System Tray
2. **Leertaste gedrückt halten** um zu sprechen
3. **Loslassen** um die Aufnahme zu beenden
4. Warten bis Claude antwortet
5. Optional wird die Antwort vorgelesen

### UI-Bedienung
- **Linksklick auf Tray-Icon:** Fenster anzeigen/verstecken
- **Rechtsklick auf Tray-Icon:** Kontextmenü
- **Chat löschen Button:** Löscht den gesamten Verlauf
- **Minimieren Button:** Versteckt das Fenster

### Tastenkombinationen
- **Leertaste halten:** Aufnahme starten/stoppen
- **ESC:** Fenster schließen (App läuft im Tray weiter)

## 🔧 Konfiguration

### Chat-Verlauf
- Wird automatisch in `chat_history.json` gespeichert
- Enthält alle Nachrichten mit Zeitstempel
- Kann über die UI gelöscht werden

### Audio-Einstellungen
```python
SAMPLERATE = 16000  # Audio-Samplerate
```

### Claude API Einstellungen
```python
# Im Code anpassbar:
"model": "claude-3-sonnet-20240229"  # Claude Modell
"max_tokens": 1500  # Maximale Antwortlänge
```

### ElevenLabs Stimme ändern
```python
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel (Standard)
```

Andere Stimmen findest du bei ElevenLabs unter "Voice Library".

## 💰 Kosten (ungefähr)

- **OpenAI Whisper:** ~$0.006 pro Minute Audio
- **Claude API:** ~$0.001-0.01 pro Nachricht (je nach Länge)
- **ElevenLabs:** Kostenlose Kontingente, dann ~$0.30 pro 1000 Zeichen

**Für normale Nutzung:** Wenige Cent bis Euro pro Tag.

## ❓ Troubleshooting

### "API Key nicht gefunden"
- Prüfe die Umgebungsvariablen: `echo %OPENAI_API_KEY%`
- Starte CMD neu nach `setx` Befehlen
- Stelle sicher, dass keine Anführungszeichen in den Keys sind

### "Audio-Aufnahme funktioniert nicht"
- Überprüfe dein Mikrofon in Windows-Einstellungen
- Stelle sicher, dass keine andere App das Mikrofon blockiert
- Teste mit: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### "Claude antwortet nicht"
- Prüfe Internetverbindung
- Validiere den Claude API Key bei Anthropic
- Prüfe dein API-Kontingent

### "PyQt5 Installation Fehler"
Manchmal gibt es Probleme mit PyQt5 auf Windows:
```cmd
pip install --upgrade pip
pip install PyQt5 --force-reinstall
```

### "Kann Audio nicht abspielen"
Die App funktioniert auch ohne Audio-Ausgabe. Für bessere TTS-Unterstützung:
```cmd
pip install pygame
```

## 📁 Projektstruktur

```
voice-chat-app/
├── src/                   # Haupt-Source-Code
│   ├── api_clients.py
│   ├── app_logic.py
│   ├── audio_recorder.py
│   ├── chat_history.py
│   ├── config.py
│   ├── debug_tool.py
│   ├── main.py            # Hauptanwendung
│   ├── mcp_client.py
│   ├── session_manager.py
│   ├── ui_elements.py
│   ├── utils.py
│   └── voice_chat_app.py
├── requirements.txt       # Python-Abhängigkeiten  
├── setup.bat             # Windows Setup-Skript
├── .env.example          # API Key Vorlage
├── README.md             # Diese Anleitung
├── chat_history.json     # Chat-Verlauf (wird erstellt)
├── venv/                 # Virtuelle Umgebung (wird erstellt)
└── temp_aufnahme.wav     # Temporäre Audio-Datei
```

## 🔒 Datenschutz & Sicherheit

- **Chat-Verlauf:** Wird nur lokal gespeichert
- **API Keys:** Werden als Umgebungsvariablen gespeichert
- **Audio:** Temporäre Dateien werden nach Verarbeitung gelöscht
- **Netzwerk:** Nur HTTPS-Verbindungen zu APIs

**Wichtig:** Chat-Gespräche erscheinen **NICHT** auf der Claude-Webseite, da die API getrennt ist!

## 🤝 Beitragen

Ideen für Verbesserungen:
- [ ] Linux/macOS Support
- [ ] Andere TTS-Anbieter (Google, Azure)
- [ ] Hotkey-Anpassung
- [ ] Verschiedene Claude-Modelle
- [ ] Plugin-System
- [ ] Sprachenerkennung für andere Sprachen

## 📄 Lizenz

MIT License - siehe LICENSE Datei für Details.

## 🆘 Support

Bei Problemen:
1. Prüfe diese README
2. Validiere API Keys und Internetverbindung  
3. Teste alle Komponenten einzeln
4. Erstelle ein Issue mit Fehlermeldung und Python-Version

## 🎉 Viel Spaß!

Jetzt kannst du per Sprache mit Claude chatten! Halte einfach die Leertaste gedrückt und sprich drauf los.
