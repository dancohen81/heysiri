import requests
import openai
import os
from config import ELEVENLABS_VOICE_ID, ELEVENLABS_URL, SYSTEM_PROMPT, \
    ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST, ELEVENLABS_STYLE, ELEVENLABS_USE_SPEAKER_BOOST

class ClaudeAPI:
    """Handler für Claude API Kommunikation"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        
    def send_message(self, messages):
        """Sendet Nachricht an Claude API"""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1500,
            "messages": messages,
            "system": SYSTEM_PROMPT
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            
            response_json = response.json()
            if "content" in response_json and response_json["content"]:
                return response_json["content"][0]["text"]
            else:
                # Handle cases where 'content' is missing or empty
                print("Claude API response 'content' field is empty or missing.")
                return "" # Return empty string if no content
        except requests.exceptions.RequestException as e:
            raise Exception(f"Claude API Verbindungsfehler: {e}")
        except KeyError as e:
            raise Exception(f"Claude API Antwortformat unerwartet: {e}")
        except Exception as e:
            raise Exception(f"Claude API Fehler: {e}")

class ElevenLabsTTS:
    """Handler für ElevenLabs Text-to-Speech"""
    
    def __init__(self, api_key, voice_id=ELEVENLABS_VOICE_ID):
        self.api_key = api_key
        self.voice_id = voice_id
        self.url = ELEVENLABS_URL.format(ELEVENLABS_VOICE_ID=voice_id) # Use format for URL
    
    def text_to_speech(self, text, output_file=None):
        """Konvertiert Text zu Sprache"""
        # Eindeutigen Dateinamen generieren
        if output_file is None:
            import time
            timestamp = int(time.time() * 1000)
            output_file = f"claude_response_{timestamp}.mp3"
        
        # Alte Dateien aufräumen
        try:
            import glob
            old_files = glob.glob("claude_response_*.mp3")
            for old_file in old_files:
                try:
                    if os.path.exists(old_file):
                        os.remove(old_file)
                except:
                    pass  # Ignoriere Fehler beim Aufräumen
        except:
            pass
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": ELEVENLABS_STABILITY,
                "similarity_boost": ELEVENLABS_SIMILARITY_BOOST,
                "style": ELEVENLABS_STYLE,
                "use_speaker_boost": ELEVENLABS_USE_SPEAKER_BOOST
            }
        }
        
        try:
            response = requests.post(self.url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            # Sichere Datei-Erstellung
            try:
                with open(output_file, "wb") as f:
                    f.write(response.content)
                return output_file
            except PermissionError:
                # Fallback: Temp-Verzeichnis verwenden
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_file.write(response.content)
                temp_file.close()
                return temp_file.name
                
        except Exception as e:
            raise Exception(f"ElevenLabs TTS Fehler: {e}")
