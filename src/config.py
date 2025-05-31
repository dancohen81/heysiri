# config.py - Erweitert um Dual-Agent System

# Bestehende Konfiguration... (NICHT ÄNDERN)
SAMPLERATE = 16000
AUDIO_FILENAME = "temp_aufnahme.wav"
CHAT_HISTORY_FILE = "chat_history.json"
TTS_OUTPUT_FILE = "claude_response.mp3"
MAX_TOOL_RESULT_LENGTH = 4000 # Maximale Länge für Tool-Ergebnisse, die an LLM gesendet werden

import json
import os

# Set FFmpeg and FFprobe paths for pydub
os.environ["FFMPEG_PATH"] = r"C:\ProgramData\Chocolatey\bin\ffmpeg.exe"
os.environ["FFPROBE_PATH"] = r"C:\ProgramData\Chocolatey\bin\ffprobe.exe"

# Pfad zur prompts.json Datei
PROMPTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'prompts.json')

# Prompts laden
try:
    with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
        _prompts = json.load(f)
except FileNotFoundError:
    _prompts = {}
    print(f"⚠️ Prompts file not found: {PROMPTS_FILE}. Using empty prompts.")
except json.JSONDecodeError:
    _prompts = {}
    print(f"❌ Error decoding prompts from {PROMPTS_FILE}. Using empty prompts.")

CHAT_AGENT_PROMPT = _prompts.get("CHAT_AGENT_PROMPT", "")
FILE_AGENT_PROMPT = _prompts.get("FILE_AGENT_PROMPT", "")
INTERNET_AGENT_PROMPT = _prompts.get("INTERNET_AGENT_PROMPT", "")
SYSTEM_PROMPT = _prompts.get("SYSTEM_PROMPT", "")

# Funktion zum Speichern der Prompts
def save_prompts(new_prompts: dict):
    global CHAT_AGENT_PROMPT, FILE_AGENT_PROMPT, INTERNET_AGENT_PROMPT, SYSTEM_PROMPT
    _prompts.update(new_prompts)
    try:
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_prompts, f, indent=4, ensure_ascii=False)
        CHAT_AGENT_PROMPT = _prompts.get("CHAT_AGENT_PROMPT", "")
        FILE_AGENT_PROMPT = _prompts.get("FILE_AGENT_PROMPT", "")
        INTERNET_AGENT_PROMPT = _prompts.get("INTERNET_AGENT_PROMPT", "")
        SYSTEM_PROMPT = _prompts.get("SYSTEM_PROMPT", "")
        print(f"✅ Prompts saved to {PROMPTS_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving prompts to {PROMPTS_FILE}: {e}")
        return False

# Restliche Konfiguration...
ELEVENLABS_VOICE_ID = "ZthjuvLPty3kTMaNKVKb"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
ELEVENLABS_STABILITY = 0.6
ELEVENLABS_SIMILARITY_BOOST = 0.8
ELEVENLABS_STYLE = 0.3
ELEVENLABS_USE_SPEAKER_BOOST = True
FILEMAN_MCP_URL = "http://localhost:3000/tool_use" # This is likely a placeholder, the actual path is used in MCP_SERVER_CONFIG
INTERNET_MCP_URL = "http://localhost:3001/tool_use" # Placeholder for internet MCP server
CLAUDE_API_KEY = "YOUR_CLAUDE_API_KEY"
ELEVENLABS_API_KEY = "YOUR_ELEVENLABS_API_KEY"
OPENROUTER_API_KEY = "YOUR_OPENROUTER_API_KEY" # NEU: OpenRouter API Key

# Aktiver LLM (Large Language Model)
# Optionen: "claude", "openrouter"
ACTIVE_LLM = "claude" # Standardmäßig Claude verwenden

# MCP Server Konfiguration
# Jeder Eintrag enthält den Pfad zum Server und einen 'enabled' Status
MCP_SERVER_CONFIG = {
    "fileman": {
        "path": "D:/Users/stefa/servers/src/filesystem/dist/index.js",
        "enabled": True
    },
    "internet": {
        "path": "D:/Users/stefa/heysiri/mcp-internet/build/index.js",
        "enabled": True
    }
}

# Funktion zum Speichern der MCP Server Konfiguration
def save_mcp_config(new_config: dict):
    global MCP_SERVER_CONFIG
    MCP_SERVER_CONFIG.update(new_config)
    # For simplicity, we'll save this back to config.py itself for now,
    # but in a real app, this might go to a separate user settings file.
    # This part would require more complex file manipulation or a dedicated settings manager.
    # For now, we'll assume direct modification of this dict is sufficient for runtime.
    # Persistence would need a more robust solution (e.g., writing to a JSON file).
    print("✅ MCP Server configuration updated in memory.")
    # To persist this, we would need to write this dict back to a file.
    # For now, we'll just update the in-memory representation.
    return True

MCP_ALLOWED_DIRS = ["D:/Users/stefa/heysiri"] # This might need to be per-server in the future, but for now, keep it global.
