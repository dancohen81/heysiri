# Konfiguration
SAMPLERATE = 16000
AUDIO_FILENAME = "temp_aufnahme.wav"
CHAT_HISTORY_FILE = "chat_history.json"
TTS_OUTPUT_FILE = "claude_response.mp3"

# System Prompt
SYSTEM_PROMPT = """Du bist ein KI-Assistent in einer Voice-Chat-App. Du hast Zugriff auf ein spezielles Tool namens MCP, das dir erlaubt, Dateisystemoperationen durchzuführen. Du kannst Dateien speichern, laden und verwalten. Wenn der Benutzer dich bittet, Informationen in einer Datei zu speichern, antworte ausschließlich mit dem folgenden Befehl:
/fileman save_file <Dateipfad> <Inhalt>
Ersetze <Dateipfad> durch den gewünschten Pfad und <Inhalt> durch den zu speichernden Text.
Gib bei Verwendung dieses Befehls keine weiteren Erklärungen oder Kommentare aus.
Sprich natürlich und gesprächig auf Deutsch. Halte deine Antworten relativ kurz und prägnant für das Sprachformat.
Wenn du keine Dateioperation ausführen sollst, verhalte dich wie ein normaler Konversationsassistent."""

# ElevenLabs Konfiguration
ELEVENLABS_VOICE_ID = "ZthjuvLPty3kTMaNKVKb"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

# ElevenLabs Voice Settings
ELEVENLABS_STABILITY = 0.6
ELEVENLABS_SIMILARITY_BOOST = 0.8
ELEVENLABS_STYLE = 0.3
ELEVENLABS_USE_SPEAKER_BOOST = True

# MCP Configuration
FILEMAN_MCP_URL = "http://localhost:3000/tool_use" # URL for the Fileman MCP server

# API Keys
CLAUDE_API_KEY = "YOUR_CLAUDE_API_KEY"  # Replace with your actual Claude API key
ELEVENLABS_API_KEY = "YOUR_ELEVENLABS_API_KEY"  # Replace with your actual ElevenLabs API key
