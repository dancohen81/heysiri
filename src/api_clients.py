import requests
import openai
import os
from src.config import (
    ELEVENLABS_VOICE_ID, ELEVENLABS_URL, SYSTEM_PROMPT,
    ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST, ELEVENLABS_STYLE, ELEVENLABS_USE_SPEAKER_BOOST,
    OPENROUTER_API_KEY, ACTIVE_LLM # NEU: OpenRouter Imports
)

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

class OpenRouterAPI:
    """Handler für OpenRouter API Kommunikation mit MCP Tool Support"""
    
    def __init__(self, api_key, model="mistralai/mistral-7b-instruct"): # Standardmodell für OpenRouter
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
    def send_message(self, messages, tools=None, system_prompt=None):
        """Sendet Nachricht an OpenRouter API mit optionalem dynamischem System Prompt"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000", # Optional: Your website URL
            "X-Title": "Voice Chat App" # Optional: Your app name
        }
        
        # OpenRouter (OpenAI-kompatibel) erwartet System Prompt als erste Nachricht im messages Array
        effective_messages = []
        if system_prompt:
            effective_messages.append({"role": "system", "content": system_prompt})
        effective_messages.extend(messages)
        
        data = {
            "model": self.model,
            "max_tokens": 1500,
            "messages": effective_messages,
            "stream": False # OpenRouter supports streaming, but for simplicity, we'll use non-streaming
        }
        
        # Tools hinzufügen wenn verfügbar (OpenAI-Format)
        if tools:
            # OpenRouter expects tools in the OpenAI format, which is slightly different from Claude's
            # Claude: {"name": "tool_name", "input": {"arg1": "val1"}}
            # OpenAI: {"type": "function", "function": {"name": "tool_name", "parameters": {schema}}}
            # We need to convert the MCP tool schema to OpenAI function tool schema
            openai_tools = []
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object", "properties": {}})
                    }
                })
            data["tools"] = openai_tools
            print(f"🔧 API DEBUG: Sende {len(openai_tools)} Tools an OpenRouter")
            print(f"🔧 API DEBUG: Tool-Namen: {[t['function']['name'] for t in openai_tools[:3]]}")
        
        # DEBUG: Zeige welcher System Prompt verwendet wird
        prompt_type = "dynamisch" if system_prompt is not None else "standard"
        print(f"🧠 System Prompt (OpenRouter): {prompt_type} ({len(system_prompt)} Zeichen)")
        
        try:
            print(f"🔧 API DEBUG: Request Model (OpenRouter): {data['model']}")
            print(f"🔧 API DEBUG: Request hat Tools (OpenRouter): {'tools' in data}")
            
            response = requests.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            
            response_json = response.json()
            
            if "choices" in response_json and response_json["choices"]:
                choice = response_json["choices"][0]
                message = choice["message"]
                
                # Handle tool calls (OpenAI format)
                if message.get("tool_calls"):
                    claude_tool_calls = []
                    for tool_call in message["tool_calls"]:
                        claude_tool_calls.append({
                            "id": tool_call["id"],
                            "name": tool_call["function"]["name"],
                            "input": tool_call["function"]["arguments"] # Arguments are already JSON string
                        })
                    return {"text": message.get("content", ""), "tool_calls": claude_tool_calls}
                else:
                    return {"text": message.get("content", ""), "tool_calls": []}
            else:
                print("OpenRouter API response 'choices' field is empty or missing.")
                return {"text": "", "tool_calls": []}
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenRouter API Verbindungsfehler: {e}")
        except KeyError as e:
            raise Exception(f"OpenRouter API Antwortformat unerwartet: {e}")
        except Exception as e:
            raise Exception(f"OpenRouter API Fehler: {e}")

    def send_message_with_tools(self, messages, tools, tool_results=None, system_prompt=None):
        """
        Erweiterte Nachricht mit Tool-Support und dynamischem System Prompt für OpenRouter
        
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
        
        # Tool-Ergebnisse hinzufügen falls vorhanden (OpenAI format)
        if tool_results:
            # Convert Claude tool_result format to OpenAI tool_call format
            openai_tool_results = []
            for tr in tool_results:
                if tr.get("type") == "tool_result": # This is Claude's format
                    openai_tool_results.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_use_id"],
                        "content": tr["content"]
                    })
                else: # Assume it's already in OpenAI format or a regular message
                    openai_tool_results.append(tr)
            full_messages.extend(openai_tool_results)
        
        try:
            # OpenRouter (OpenAI-kompatibel) erwartet System Prompt als erste Nachricht im messages Array
            # send_message handles this
            response_data = self.send_message(full_messages, tools, system_prompt=system_prompt)
            
            # OpenRouter's send_message already returns {"text": ..., "tool_calls": ...}
            # We need to ensure tool_calls are in Claude's format for consistency
            claude_tool_calls = []
            if response_data.get("tool_calls"):
                for tc in response_data["tool_calls"]:
                    # Ensure arguments are a dict, not a JSON string
                    if isinstance(tc["input"], str):
                        try:
                            tc["input"] = json.loads(tc["input"])
                        except json.JSONDecodeError:
                            print(f"WARNING: Tool arguments not valid JSON: {tc['input']}")
                            tc["input"] = {} # Fallback to empty dict
                    claude_tool_calls.append(tc)

            return {
                "text": response_data.get("text", ""),
                "tool_calls": claude_tool_calls,
                "raw_content": [{"type": "text", "text": response_data.get("text", "")}] # Simplified raw_content
            }
            
        except Exception as e:
            raise Exception(f"OpenRouter Tool-Nachricht Fehler: {e}")

import re
import time # Import time for timestamp
import glob # Import glob for file cleanup
import tempfile # Import tempfile for fallback

def parse_voice_commands_for_speed_param(text):
    """
    Parses voice commands from the text to determine speed and remove them.
    Returns (cleaned_text, speed_multiplier).
    """
    speed_multiplier = 1.0 # Default normal speed
    temp_text = text # Use a temporary variable for iterative cleaning

    # Process !schnell: first, as it might be overridden by !langsam:
    if re.search(r"!schnell:\s*", temp_text):
        temp_text = re.sub(r"!schnell:\s*", "", temp_text)
        speed_multiplier = 1.2

    # Process !langsam: (this will override !schnell: if both are present)
    if re.search(r"!langsam:\s*", temp_text):
        temp_text = re.sub(r"!langsam:\s*", "", temp_text)
        speed_multiplier = 0.7
    
    cleaned_text = temp_text.strip() # Strip only once at the end
    
    print(f"DEBUG: Parsed for speed param: Text='{cleaned_text[:50]}...', Speed={speed_multiplier}")
    return cleaned_text, speed_multiplier

class ElevenLabsTTS:
    """Handler für ElevenLabs Text-to-Speech"""
    
    def __init__(self, api_key, voice_id=ELEVENLABS_VOICE_ID):
        self.api_key = api_key
        self.voice_id = voice_id
        self.url = ELEVENLABS_URL.format(ELEVENLABS_VOICE_ID=voice_id)
    
    def text_to_speech(self, original_text, output_file=None):
        """Konvertiert Text zu Sprache"""
        # Parse voice commands to get speed multiplier and cleaned text
        # Note: This function now expects original_text to be a segment,
        # so speed commands should be at the beginning of the segment if present.
        text_to_send, speed_multiplier = parse_voice_commands_for_speed_param(original_text)

        # Eindeutigen Dateinamen generieren
        if output_file is None:
            timestamp = int(time.time() * 1000)
            output_file = f"claude_response_{timestamp}.mp3"
        
        # Alte Dateien aufräumen (only if not a temp file from previous segment)
        # This cleanup logic should ideally be handled by the caller (app_logic)
        # or a dedicated cleanup function, not here for every segment.
        # For now, let's keep it simple and assume temp files are managed.
        # Removed glob cleanup from here to avoid issues with concurrent segment processing.
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "text": text_to_send, # Use the cleaned text
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": ELEVENLABS_STABILITY,
                "similarity_boost": ELEVENLABS_SIMILARITY_BOOST,
                "style": ELEVENLABS_STYLE,
                "use_speaker_boost": ELEVENLABS_USE_SPEAKER_BOOST,
                "speed": speed_multiplier # ADDED speed parameter
            }
        }
        
        print(f"DEBUG: ElevenLabs API Payload: {data}") # Keep this for now to verify speed param

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
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_file.write(response.content)
                temp_file.close()
                return temp_file.name
                
        except Exception as e:
            raise Exception(f"ElevenLabs TTS Fehler: {e}")
