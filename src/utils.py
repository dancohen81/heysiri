import os
import sys
import winsound
import winshell
from win32com.client import Dispatch
from PyQt5 import QtWidgets
import openai
import threading # Added for pause/resume functionality
import time # Added for pause/resume functionality

def setup_autostart():
    """Richtet Windows Autostart ein"""
    try:
        startup = winshell.startup()
        shortcut_path = os.path.join(startup, "VoiceChatApp.lnk")
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = sys.executable
        # Point to the main application entry point in the src directory
        shortcut.Arguments = f'"{os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))}"'
        shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(__file__))
        shortcut.save()
        return True
    except Exception as e:
        print(f"Autostart Setup Fehler: {e}")
        return False

def play_audio_file(filename, stop_event=None, pause_event=None):
    """Spielt Audio-Datei ab (Windows) - robustere Version, mit Stopp- und Pause-Möglichkeit"""
    try:
        # Prüfen ob Datei existiert
        if not os.path.exists(filename):
            print(f"Audio-Datei nicht gefunden: {filename}")
            return False
            
        # Methode 1: pygame (bevorzugt)
        print("DEBUG: Attempting playback with pygame...")
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            
            # Warten bis Wiedergabe fertig oder Stopp-Event gesetzt
            while pygame.mixer.music.get_busy():
                if stop_event and stop_event.is_set():
                    pygame.mixer.music.stop()
                    print("DEBUG: Playback stopped by stop_event.")
                    break
                
                if pause_event and pause_event.is_set():
                    pygame.mixer.music.pause()
                    print("DEBUG: Playback paused.")
                    while pause_event.is_set():
                        time.sleep(0.1) # Wait while paused
                    pygame.mixer.music.unpause()
                    print("DEBUG: Playback unpaused.")
                
                pygame.time.wait(100)
            
            pygame.mixer.quit()
            print("DEBUG: Playback with pygame successful.")
            return True
            
        except ImportError:
            print("DEBUG: pygame not available - falling back.")
        except Exception as e:
            print(f"DEBUG: pygame error: {e} - falling back.")
        
        # Fallback-Methoden (nicht stoppbar, nur für Notfälle)
        # Methode 2: Windows Media Player
        print("DEBUG: Attempting playback with os.startfile...")
        try:
            os.startfile(filename)
            print("DEBUG: Playback with os.startfile successful (may run in background).")
            # For non-interruptible playback, we might still want to wait a bit
            # or just let it play in the background. For now, just return.
            return True
        except Exception as e:
            print(f"DEBUG: os.startfile error: {e} - falling back.")
        
        # Methode 3: System-Befehl
        print("DEBUG: Attempting playback with subprocess.run...")
        try:
            subprocess.run(['start', '', filename], shell=True, check=True)
            print("DEBUG: Playback with subprocess.run successful (may run in background).")
            return True
        except Exception as e:
            print(f"DEBUG: subprocess error: {e} - playback failed.")
            
        return False
        
    except Exception as e:
        print(f"DEBUG: Audio playback failed: {e}")
        return False
    
    finally:
        # Audio-Datei nach Wiedergabe löschen (nach kurzer Verzögerung)
        # Nur löschen, wenn nicht gestoppt wurde oder es sich um eine temporäre Datei handelt
        try:
            def cleanup_audio():
                # Only clean up if playback finished naturally or it's a temp file
                # If stop_event is set, it means it was interrupted, so don't delete immediately
                # unless it's a temporary file that should always be deleted.
                try:
                    # Check if the file is still there and if it's a temporary response file
                    if os.path.exists(filename) and (filename.startswith("claude_response") or "temp" in filename):
                        os.remove(filename)
                except Exception as e:
                    print(f"Cleanup-Fehler für {filename}: {e}")
            
            threading.Thread(target=cleanup_audio, daemon=True).start()
        except Exception as e:
            print(f"Cleanup Thread Fehler: {e}")

def check_api_keys(openai_api_key, claude_api_key, elevenlabs_api_key):
    """Prüft verfügbare API Keys"""
    missing_keys = []
    
    if not openai_api_key:
        missing_keys.append("OPENAI_API_KEY (erforderlich)")
    if not claude_api_key:
        missing_keys.append("CLAUDE_API_KEY (erforderlich)")
    if not elevenlabs_api_key:
        missing_keys.append("ELEVENLABS_API_KEY (optional)")
    
    return missing_keys
