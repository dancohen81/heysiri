import sys
import os
from PyQt5 import QtWidgets
from dotenv import load_dotenv

# NEW: Import pygame and initialize mixer early
try:
    import pygame
    pygame.mixer.init()
    print("DEBUG: pygame mixer initialized successfully.")
except Exception as e:
    print(f"ERROR: Failed to initialize pygame mixer: {e}")

from src.app_logic import VoiceChatApp
from src.utils import check_api_keys

def main():
    """Hauptfunktion"""
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # .env Datei laden (falls vorhanden)
    try:
        load_dotenv()
        print("✅ .env Datei geladen")
    except ImportError:
        print("⚠️ python-dotenv nicht installiert - verwende Umgebungsvariablen")

    # API Keys prüfen
    openai_api_key = os.getenv("OPENAI_API_KEY")
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")

    missing_keys = check_api_keys(openai_api_key, claude_api_key, elevenlabs_api_key)
    if missing_keys:
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Fehlende API Keys")
        msg.setText("Folgende API Keys fehlen:")
        msg.setDetailedText("\n".join(missing_keys))
        msg.setInformativeText("Bitte setze die Umgebungsvariablen und starte die App neu.")
        msg.exec_()
        
        if "OPENAI_API_KEY (erforderlich)" in missing_keys or "CLAUDE_API_KEY (erforderlich)" in missing_keys:
            sys.exit(1)
    
    # App starten
    chat_app = VoiceChatApp(app)
    chat_app.show()
    
    # Explicitly set focus to the text input field after showing the window
    # This is crucial if a QMessageBox was shown previously or if initial focus is lost.
    if hasattr(chat_app.window, 'input_field') and chat_app.window.input_field is not None:
        chat_app.window.input_field.setFocus()
        print("DEBUG: Input field focus set at startup.")
    else:
        print("DEBUG: Input field not found or not ready for focus at startup.")
    
    print("Voice Chat App gestartet!")
    print("Leertaste halten = Aufnahme")
    print("Rechtsklick auf Tray-Icon = Menü")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
