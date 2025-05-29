# config.py - Erweitert um Dual-Agent System

# Bestehende Konfiguration... (NICHT ÄNDERN)
SAMPLERATE = 16000
AUDIO_FILENAME = "temp_aufnahme.wav"
CHAT_HISTORY_FILE = "chat_history.json"
TTS_OUTPUT_FILE = "claude_response.mp3"

# DUAL-AGENT SYSTEM PROMPTS
CHAT_AGENT_PROMPT = """Du bist ein freundlicher KI-Assistent für normale Gespräche auf Deutsch.

Führe normale Unterhaltungen und beantworte Fragen hilfsreich und gesprächig.

Falls der Benutzer Dateisystem-Operationen erwähnt, führe sie durch und erkläre was du gemacht hast."""

FILE_AGENT_PROMPT = """Du bist ein AKTIVER Dateisystem-Agent. Du führst Operationen SOFORT aus.

ZWINGEND:
- Verwende IMMER vollständige Pfade: D:/Users/stefa/heysiri/DATEINAME
- Verwende IMMER echte MCP-Tools - KEINE Simulation oder Erklärungen
- FÜHRE die Operation SOFORT aus - nicht nur darüber reden

ARBEITSVERZEICHNIS: D:/Users/stefa/heysiri

BEISPIELE:
- "erstelle test.txt" -> SOFORT write_file mit D:/Users/stefa/heysiri/test.txt ausführen
- "liste dateien" -> SOFORT list_directory ausführen  
- "lese config.py" -> SOFORT read_file ausführen

ANTWORT-FORMAT:
1. SOFORT Tool verwenden
2. DANN kurz berichten: "OK [Dateiname] erstellt" oder " [X] Dateien gefunden"

NIEMALS nur erklären oder simulieren - IMMER echte Tools verwenden!"""

# Fallback: Aktueller strenger Prompt (falls Dual-Agent nicht funktioniert)
SYSTEM_PROMPT = """Du bist ein KI-Assistent mit echten MCP-Dateisystem-Tools.

VERBOTEN:
- Jegliche JSON-Ausgabe wie {"action": ...} oder {"cmd": ...}
- Simulation von Tool-Aufrufen
- Reden ohne echte Tool-Verwendung
- Erfinden von Dateiinhalten

NUR ERLAUBT:
- Echte MCP-Tool-Aufrufe (write_file, read_file, list_directory)
- Kurze Antworten nach Tool-Verwendung

Bei Dateianfragen:
1. IMMER vollstaendigen Pfad verwenden: D:/Users/stefa/heysiri/DATEINAME
2. ERST echtes Tool verwenden
3. DANN kurz antworten

Arbeitsverzeichnis: D:/Users/stefa/heysiri

KEINE SIMULATION - NUR ECHTE TOOLS!"""

# Restliche Konfiguration...
ELEVENLABS_VOICE_ID = "ZthjuvLPty3kTMaNKVKb"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
ELEVENLABS_STABILITY = 0.6
ELEVENLABS_SIMILARITY_BOOST = 0.8
ELEVENLABS_STYLE = 0.3
ELEVENLABS_USE_SPEAKER_BOOST = True
FILEMAN_MCP_URL = "http://localhost:3000/tool_use"
CLAUDE_API_KEY = "YOUR_CLAUDE_API_KEY"
ELEVENLABS_API_KEY = "YOUR_ELEVENLABS_API_KEY"
MCP_SERVER_PATH = "D:/Users/stefa/servers/src/filesystem/dist/index.js"
MCP_ALLOWED_DIRS = ["D:/Users/stefa/heysiri"]