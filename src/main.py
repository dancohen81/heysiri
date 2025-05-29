import sys
import os
from PyQt5 import QtWidgets
from dotenv import load_dotenv

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
    
    print("Voice Chat App gestartet!")
    print("Leertaste halten = Aufnahme")
    print("Rechtsklick auf Tray-Icon = Menü")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
