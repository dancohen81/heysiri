# Konfiguration
SAMPLERATE = 16000
AUDIO_FILENAME = "temp_aufnahme.wav"
CHAT_HISTORY_FILE = "chat_history.json"
TTS_OUTPUT_FILE = "claude_response.mp3"

# System Prompt
SYSTEM_PROMPT = "Du bist ein hilfsreicher Assistent in einer Voice-Chat App. Antworte natürlich und gesprächig auf Deutsch. Halte deine Antworten relativ kurz und prägnant für das Sprachformat. Wenn der Benutzer dich bittet, Informationen in einer Datei zu speichern, antworte ausschließlich mit dem Befehl im Format: /fileman save_file <Dateipfad> <Inhalt>. Ersetze <Dateipfad> durch den gewünschten Dateipfad und <Inhalt> durch den zu speichernden Text. Gib keine weiteren Erklärungen oder zusätzlichen Text aus, wenn du diesen Befehl verwendest."

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
