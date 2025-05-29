import requests
import openai
import os
from src.config import ELEVENLABS_VOICE_ID, ELEVENLABS_URL, SYSTEM_PROMPT, \
    ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST, ELEVENLABS_STYLE, ELEVENLABS_USE_SPEAKER_BOOST

class ClaudeAPI:
    """Handler für Claude API Kommunikation mit MCP Tool Support"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        
    def send_message(self, messages, tools=None, system_prompt=None):
        """Sendet Nachricht an Claude API mit optionalem dynamischem System Prompt"""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Dynamischen oder Standard System Prompt verwenden
        effective_system_prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT
        
        data = {
            "model": "claude-3-5-sonnet-20241022",  # NEUES Modell für Tools!
            "max_tokens": 1500,
            "messages": messages,
            "system": effective_system_prompt  # 🎯 HIER ist der Fix!
        }
        
        # Tools hinzufügen wenn verfügbar
        if tools:
            data["tools"] = tools
            print(f"🔧 API DEBUG: Sende {len(tools)} Tools an Claude")
            print(f"🔧 API DEBUG: Tool-Namen: {[t['name'] for t in tools[:3]]}")
        
        # DEBUG: Zeige welcher System Prompt verwendet wird
        prompt_type = "dynamisch" if system_prompt is not None else "standard"
        print(f"🧠 System Prompt: {prompt_type} ({len(effective_system_prompt)} Zeichen)")
        
        try:
            print(f"🔧 API DEBUG: Request Model: {data['model']}")
            print(f"🔧 API DEBUG: Request hat Tools: {'tools' in data}")
            
            response = requests.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            
            response_json = response.json()
            
            if "content" in response_json and response_json["content"]:
                # Für Kompatibilität: Wenn nur Text zurückgegeben werden soll
                if not tools:
                    return response_json["content"][0]["text"]
                else:
                    return response_json["content"]
            else:
                print("Claude API response 'content' field is empty or missing.")
                return "" if not tools else [{"type": "text", "text": ""}]
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Claude API Verbindungsfehler: {e}")
        except KeyError as e:
            raise Exception(f"Claude API Antwortformat unerwartet: {e}")
        except Exception as e:
            raise Exception(f"Claude API Fehler: {e}")
    
    def send_message_with_tools(self, messages, tools, tool_results=None, system_prompt=None):
        """
        Erweiterte Nachricht mit Tool-Support und dynamischem System Prompt
        
        Args:
            messages: Basis-Nachrichten
            tools: Verfügbare Tools
            tool_results: Optional - Ergebnisse von Tool-Aufrufen
            system_prompt: Optional - Dynamischer System Prompt
            
        Returns:
            Dict mit response und tool_calls
        """
        # Erstelle vollständige Nachrichten-Liste
        full_messages = messages.copy()
        
        # Tool-Ergebnisse hinzufügen falls vorhanden
        if tool_results:
            full_messages.extend(tool_results)
        
        try:
            # 🎯 HIER: System Prompt an send_message weitergeben
            content = self.send_message(full_messages, tools, system_prompt=system_prompt)
            
            # Prüfe ob Claude Tools verwenden möchte
            text_content = []
            tool_calls = []
            
            for item in content:
                if item.get("type") == "text":
                    text_content.append(item["text"])
                elif item.get("type") == "tool_use":
                    tool_calls.append(item)
            
            return {
                "text": "\n".join(text_content) if text_content else "",
                "tool_calls": tool_calls,
                "raw_content": content
            }
            
        except Exception as e:
            raise Exception(f"Claude Tool-Nachricht Fehler: {e}")

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
