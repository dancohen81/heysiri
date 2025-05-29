import datetime
import os
import json
import re # Import the re module for regular expressions
from src.config import CHAT_HISTORY_FILE

class ChatHistory:
    """Verwaltet den lokalen Chat-Verlauf"""
    
    def __init__(self, session_name="default"):
        self.session_name = session_name
        self.filename = self._get_session_filepath(session_name)
        self.messages = self.load_history()

    def _sanitize_filename(self, name):
        """Sanitizes a string to be used as a filename."""
        # Replace invalid characters with an underscore
        # Invalid characters for Windows filenames: < > : " / \ | ? *
        # Also remove leading/trailing spaces and periods
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized_name = sanitized_name.strip()
        # Remove any periods at the end of the filename
        if sanitized_name.endswith('.'):
            sanitized_name = sanitized_name.rstrip('.')
        return sanitized_name
    
    def _get_session_filepath(self, session_name):
        """Erstellt den Dateipfad für eine gegebene Sitzung."""
        if session_name == "default":
            return CHAT_HISTORY_FILE
        return f"chat_history_{session_name}.json"

    def load_history(self):
        """Lädt existierenden Chat-Verlauf aus der aktuellen Sitzungsdatei.
        Versucht zuerst, die Datei mit dem sanitisierten Namen zu laden.
        Wenn nicht gefunden, sucht es nach einer Datei, deren sanitierter Name mit der aktuellen Sitzung übereinstimmt.
        """
        # Try to load from the current filename (which is based on the sanitized session_name)
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("messages", [])
            except Exception as e:
                print(f"Fehler beim Laden des Chat-Verlaufs '{self.filename}': {e}")
                # Fallback to searching for other files if loading fails
        
        # If the file with the sanitized name doesn't exist or loading failed,
        # iterate through all chat history files and try to match their sanitized names.
        temp_history = ChatHistory() # Use a temporary instance to access _sanitize_filename
        for f in os.listdir('.'):
            if f.startswith("chat_history_") and f.endswith(".json"):
                file_session_name = f[len("chat_history_"):-len(".json")]
                sanitized_file_session_name = temp_history._sanitize_filename(file_session_name)
                
                if sanitized_file_session_name == self.session_name:
                    # Found a file whose sanitized name matches the current session_name
                    full_filepath = f"chat_history_{file_session_name}.json"
                    if os.path.exists(full_filepath):
                        try:
                            with open(full_filepath, 'r', encoding='utf-8') as f_match:
                                data = json.load(f_match)
                                # Update self.filename to the actual file found
                                self.filename = full_filepath
                                return data.get("messages", [])
                        except Exception as e:
                            print(f"Fehler beim Laden des Chat-Verlaufs '{full_filepath}' (Fallback): {e}")
        return []
    
    def save_history(self):
        """Speichert Chat-Verlauf in die aktuelle Sitzungsdatei."""
        data = {
            "created": datetime.datetime.now().isoformat(),
            "session_name": self.session_name,
            "messages": self.messages
        }
        # Sanitize the filename before saving
        sanitized_filename = self._get_session_filepath(self._sanitize_filename(self.session_name))
        try:
            with open(sanitized_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # Update self.filename to the sanitized version after successful save
            self.filename = sanitized_filename
        except Exception as e:
            print(f"Fehler beim Speichern der Sitzung '{self.session_name}' in '{sanitized_filename}': {e}")
    
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
        """Startet eine neue, leere Chat-Sitzung."""
        self.session_name = session_name
        # When creating a new session, we always want it to be empty initially.
        # The filename will be set based on the new session_name, and then an empty history will be saved.
        self.filename = self._get_session_filepath(session_name)
        self.messages = [] # Explicitly clear messages for a new session
        self.save_history() # Save the empty history for the new session

    @staticmethod
    def list_sessions():
        """Listet alle verfügbaren Chat-Sitzungsdateien auf und gibt deren sanitisierten Namen zurück."""
        session_names = []
        # Create a temporary ChatHistory instance to access _sanitize_filename
        temp_history = ChatHistory() 
        for f in os.listdir('.'):
            if f.startswith("chat_history_") and f.endswith(".json"):
                session_name = f[len("chat_history_"):-len(".json")]
                # Sanitize the name extracted from the filename
                sanitized_name = temp_history._sanitize_filename(session_name)
                session_names.append(sanitized_name)
            elif f == CHAT_HISTORY_FILE and os.path.exists(CHAT_HISTORY_FILE):
                session_names.append("default")
        return sorted(list(set(session_names))) # Entfernt Duplikate und sortiert
