import datetime
import os
import json
from src.config import CHAT_HISTORY_FILE

class ChatHistory:
    """Verwaltet den lokalen Chat-Verlauf"""
    
    def __init__(self, session_name="default"):
        self.session_name = session_name
        self.filename = self._get_session_filepath(session_name)
        self.messages = self.load_history()
    
    def _get_session_filepath(self, session_name):
        """Erstellt den Dateipfad für eine gegebene Sitzung."""
        if session_name == "default":
            return CHAT_HISTORY_FILE
        return f"chat_history_{session_name}.json"

    def load_history(self):
        """Lädt existierenden Chat-Verlauf aus der aktuellen Sitzungsdatei."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("messages", [])
            except Exception as e:
                print(f"Fehler beim Laden des Chat-Verlaufs '{self.filename}': {e}")
                return []
        return []
    
    def save_history(self):
        """Speichert Chat-Verlauf in die aktuelle Sitzungsdatei."""
        data = {
            "created": datetime.datetime.now().isoformat(),
            "session_name": self.session_name,
            "messages": self.messages
        }
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Sitzung '{self.session_name}' in '{self.filename}': {e}")
    
    def add_message(self, role, content):
        """Fügt neue Nachricht hinzu und speichert den Verlauf."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        })
        self.save_history()
    
    def get_context_messages(self, limit=8):
        """Gibt die letzten Nachrichten für API-Kontext zurück."""
        recent = self.messages[-limit:] if len(self.messages) > limit else self.messages
        return [{"role": msg["role"], "content": msg["content"]} for msg in recent]
    
    def get_message_count(self):
        """Gibt die Anzahl der Nachrichten im Chat-Verlauf zurück."""
        return len(self.messages)

    def clear_history(self):
        """Löscht den gesamten Chat-Verlauf der aktuellen Sitzung."""
        self.messages = []
        self.save_history() # Speichert den leeren Verlauf

    def new_session(self, session_name="default"):
        """Startet eine neue Sitzung und lädt diese."""
        self.session_name = session_name
        self.filename = self._get_session_filepath(session_name)
        self.messages = self.load_history() # Lädt den Verlauf der neuen Sitzung (oder leer, falls neu)
        self.save_history() # Speichert die (potenziell leere) neue Sitzung

    @staticmethod
    def list_sessions():
        """Listet alle verfügbaren Chat-Sitzungsdateien auf."""
        session_files = []
        for f in os.listdir('.'):
            if f.startswith("chat_history_") and f.endswith(".json"):
                session_name = f[len("chat_history_"):-len(".json")]
                session_files.append(session_name)
            elif f == CHAT_HISTORY_FILE and os.path.exists(CHAT_HISTORY_FILE):
                session_files.append("default")
        return sorted(list(set(session_files))) # Entfernt Duplikate und sortiert
