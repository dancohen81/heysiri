import datetime
import os
import json
import re
import uuid # Import uuid for unique message IDs
from src.config import CHAT_HISTORY_FILE

class ChatHistory:
    """Verwaltet den lokalen Chat-Verlauf als Baumstruktur."""
    
    def __init__(self, session_name="default"):
        self.session_name = session_name
        self.filename = self._get_session_filepath(session_name)
        self.messages = {} # Stores messages as {message_id: message_object}
        self.current_branch_head_id = None # ID of the last message in the active branch
        self.load_history()

    def _sanitize_filename(self, name):
        """Sanitizes a string to be used as a filename."""
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized_name = sanitized_name.strip()
        if sanitized_name.endswith('.'):
            sanitized_name = sanitized_name.rstrip('.')
        return sanitized_name
    
    def _get_session_filepath(self, session_name):
        """Erstellt den Dateipfad für eine gegebene Sitzung."""
        if session_name == "default":
            return CHAT_HISTORY_FILE
        return f"chat_history_{session_name}.json"

    def load_history(self):
        """Lädt existierenden Chat-Verlauf aus der aktuellen Sitzungsdatei."""
        print(f"DEBUG: load_history called for {self.filename}")
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"DEBUG: Data loaded from {self.filename}, type: {type(data)}")
                    
                    # Handle old list format directly after loading
                    if isinstance(data, list):
                        print(f"DEBUG: Data is list format. Converting...")
                        converted_messages = {}
                        for msg in data:
                            msg_id = msg.get("id", str(uuid.uuid4())) # Use existing ID or generate new UUID
                            msg["id"] = msg_id # Ensure 'id' key exists in the message dict
                            converted_messages[msg_id] = msg
                        self.messages = converted_messages
                        if self.messages:
                            self.current_branch_head_id = list(self.messages.keys())[-1]
                        self.save_history() # Save in new format
                        print(f"DEBUG: Converted and saved. Messages count: {len(self.messages)}, Aktueller Kopf: {self.current_branch_head_id}")
                        return # Exit after successful conversion

                    # Original logic for new dictionary format
                    print(f"DEBUG: Data is dict format. Processing 'messages' key.")
                    loaded_messages_raw = data.get("messages", {})
                    if isinstance(loaded_messages_raw, list): # If 'messages' key contains a list (old format within new file structure)
                        print(f"DEBUG: 'messages' key contains a list. Converting to dict.")
                        converted_messages = {}
                        for msg in loaded_messages_raw:
                            msg_id = msg.get("id", str(uuid.uuid4())) # Use existing ID or generate new UUID
                            msg["id"] = msg_id # Ensure 'id' key exists in the message dict
                            converted_messages[msg_id] = msg
                        self.messages = converted_messages
                    elif isinstance(loaded_messages_raw, dict): # If 'messages' key contains a dict (correct new format)
                        self.messages = loaded_messages_raw
                    else: # Invalid format for 'messages'
                        print(f"ERROR: Invalid format for 'messages' key ({type(loaded_messages_raw)}). Resetting.")
                        self.messages = {}

                    self.current_branch_head_id = data.get("current_branch_head_id")
                    print(f"DEBUG: Chat history loaded. Messages: {len(self.messages)}, Current head: {self.current_branch_head_id}")
                    
                    # If no current_branch_head_id is set but messages exist, try to find the last message in a default branch
                    if not self.current_branch_head_id and self.messages:
                        print("DEBUG: No current_branch_head_id, finding latest message.")
                        all_parent_ids = {msg['parent_id'] for msg in self.messages.values() if msg.get('parent_id')}
                        potential_heads = [msg_id for msg_id in self.messages.keys() if msg_id not in all_parent_ids]
                        
                        if potential_heads:
                            latest_head = None
                            latest_timestamp = ""
                            for head_id in potential_heads:
                                msg = self.messages[head_id]
                                if msg.get('timestamp', '') > latest_timestamp:
                                    latest_timestamp = msg['timestamp']
                                    latest_head = head_id
                            self.current_branch_head_id = latest_head
                            print(f"DEBUG: Set current head to latest: {self.current_branch_head_id}")

            except json.JSONDecodeError as e:
                print(f"ERROR: JSON Decode Error in '{self.filename}': {e}. File might be corrupted or empty.")
                self.messages = {}
                self.current_branch_head_id = None
            except Exception as e: # Catch any other unexpected errors during loading
                print(f"ERROR: General error loading chat history '{self.filename}': {e}")
                self.messages = {}
                self.current_branch_head_id = None
        
        print(f"DEBUG: After try/except block, self.messages type: {type(self.messages)}")
        # Ensure messages is a dictionary and current_branch_head_id is set if messages exist
        if not isinstance(self.messages, dict):
            print(f"DEBUG: self.messages is not a dict ({type(self.messages)}). Resetting.")
            self.messages = {} # Reset if it's not a dict
            self.current_branch_head_id = None

        if not self.messages:
            print("DEBUG: self.messages is empty. Resetting current_branch_head_id.")
            self.messages = {}
            self.current_branch_head_id = None
        
        # If the current session file is empty or loading failed, try to find other session files
        # and load them if they match the sanitized name.
        # This part needs to be careful not to cause recursion.
        if not self.messages: # Only attempt fallback if current history is still empty
            print(f"DEBUG: Current history empty, attempting fallback for session '{self.session_name}'.")
            for f in os.listdir('.'):
                if f.startswith("chat_history_") and f.endswith(".json"):
                    file_session_name_raw = f[len("chat_history_"):-len(".json")]
                    sanitized_file_session_name = self._sanitize_filename(file_session_name_raw)
                    
                    if sanitized_file_session_name == self.session_name:
                        full_filepath = f"chat_history_{file_session_name_raw}.json"
                        if os.path.exists(full_filepath):
                            try:
                                print(f"DEBUG: Found potential fallback file: {full_filepath}")
                                with open(full_filepath, 'r', encoding='utf-8') as f_match:
                                    data = json.load(f_match)
                                    print(f"DEBUG: Fallback data loaded from {full_filepath}, type: {type(data)}")
                                    
                                    # Handle old list format in fallback directly after loading
                                    if isinstance(data, list):
                                        print(f"DEBUG: Fallback data is list format. Converting...")
                                        self.messages = {str(uuid.uuid4()): msg for msg in data}
                                        if self.messages:
                                            self.current_branch_head_id = list(self.messages.keys())[-1]
                                    elif isinstance(data, dict): # If it's the new dict format
                                        print(f"DEBUG: Fallback data is dict format. Processing 'messages' key.")
                                        self.messages = data.get("messages", {})
                                        self.current_branch_head_id = data.get("current_branch_head_id")
                                    else: # Invalid format
                                        print(f"DEBUG: Fallback data is invalid format ({type(data)}). Resetting.")
                                        self.messages = {}
                                        self.current_branch_head_id = None
                                        
                                    self.filename = full_filepath # Update self.filename to the actual file found
                                    print(f"DEBUG: Fallback: Chat history loaded. Messages: {len(self.messages)}, Aktueller Kopf: {self.current_branch_head_id}")
                                    
                                    if not self.current_branch_head_id and self.messages:
                                        print("DEBUG: Fallback: No current_branch_head_id, finding latest message.")
                                        all_parent_ids = {msg['parent_id'] for msg in self.messages.values() if msg.get('parent_id')}
                                        potential_heads = [msg_id for msg_id in self.messages.keys() if msg_id not in all_parent_ids]
                                        
                                        if potential_heads:
                                            latest_head = None
                                            latest_timestamp = ""
                                            for head_id in potential_heads:
                                                msg = self.messages[head_id]
                                                if msg.get('timestamp', '') > latest_timestamp:
                                                    latest_timestamp = msg['timestamp']
                                                    latest_head = head_id
                                            self.current_branch_head_id = latest_head
                                            print(f"Fallback: Kein aktueller Kopf gefunden, aber Nachrichten vorhanden. Setze Kopf auf den neuesten: {self.current_branch_head_id}")
                                    return # Exit after loading fallback
                            except Exception as e:
                                print(f"ERROR: Error loading chat history '{full_filepath}' (Fallback): {e}")
        
        # If still no messages after all attempts, ensure it's empty and consistent
        if not self.messages:
            print("DEBUG: Still no messages after all attempts. Ensuring empty and consistent.")
            self.messages = {}
            self.current_branch_head_id = None

    def save_history(self):
        """Speichert Chat-Verlauf in die aktuelle Sitzungsdatei."""
        data = {
            "created": datetime.datetime.now().isoformat(),
            "session_name": self.session_name,
            "messages": self.messages, # Save the dictionary
            "current_branch_head_id": self.current_branch_head_id # Save the current branch head
        }
        sanitized_filename = self._get_session_filepath(self._sanitize_filename(self.session_name))
        try:
            with open(sanitized_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.filename = sanitized_filename
        except Exception as e:
            print(f"Fehler beim Speichern der Sitzung '{self.session_name}' in '{sanitized_filename}': {e}")
    
    def add_message(self, role, content):
        """Fügt neue Nachricht hinzu und speichert den Verlauf."""
        new_message_id = str(uuid.uuid4())
        message = {
            "id": new_message_id,
            "parent_id": self.current_branch_head_id,
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.messages[new_message_id] = message
        self.current_branch_head_id = new_message_id # New message becomes the head of the current branch
        self.save_history()
        return new_message_id # Return the ID of the new message

    def edit_message(self, original_message_id, new_content):
        """Bearbeitet eine Nachricht, indem eine neue Nachricht mit dem bearbeiteten Inhalt erstellt wird,
        die an der gleichen Stelle im Baum beginnt wie die Originalnachricht.
        """
        if original_message_id not in self.messages:
            print(f"Fehler: Nachricht mit ID {original_message_id} nicht gefunden.")
            return False
        
        original_message = self.messages[original_message_id]
        
        if original_message['role'] != 'user':
            print(f"Fehler: Nur Benutzernachrichten können bearbeitet werden. Nachricht ist vom Typ '{original_message['role']}'.")
            return False
            
        new_message_id = str(uuid.uuid4())
        edited_message = {
            "id": new_message_id,
            "parent_id": original_message.get('parent_id'), # Safely get parent_id, default to None if not present
            "role": original_message['role'],
            "content": new_content,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.messages[new_message_id] = edited_message
        self.current_branch_head_id = new_message_id # Set the new message as the head of the active branch
        self.save_history()
        print(f"Nachricht mit ID {original_message_id} bearbeitet. Neue Nachricht ID: {new_message_id}. Aktueller Kopf: {self.current_branch_head_id}")
        return True

    def get_current_branch_messages(self):
        """Gibt alle Nachrichten des aktuellen aktiven Zweigs in chronologischer Reihenfolge zurück."""
        branch_messages = []
        current_id = self.current_branch_head_id
        while current_id and current_id in self.messages:
            branch_messages.append(self.messages[current_id])
            current_id = self.messages[current_id].get('parent_id')
        
        # Reverse to get chronological order
        return sorted(branch_messages, key=lambda x: x['timestamp'])
    
    def get_context_messages(self, limit=8):
        """Gibt die letzten Nachrichten des aktuellen Zweigs für API-Kontext zurück."""
        current_branch = self.get_current_branch_messages()
        recent = current_branch[-limit:] if len(current_branch) > limit else current_branch
        return [{"role": msg["role"], "content": msg["content"]} for msg in recent]
    
    def get_message_count(self):
        """Gibt die Anzahl der Nachrichten im aktuellen Zweig zurück."""
        return len(self.get_current_branch_messages())

    def clear_history(self):
        """Löscht den gesamten Chat-Verlauf der aktuellen Sitzung."""
        self.messages = {}
        self.current_branch_head_id = None
        self.save_history() # Speichert den leeren Verlauf

    def new_session(self, session_name="default"):
        """Startet eine neue, leere Chat-Sitzung."""
        self.session_name = session_name
        self.filename = self._get_session_filepath(session_name)
        self.messages = {}
        self.current_branch_head_id = None
        self.save_history()

    @staticmethod
    def list_sessions():
        """Listet alle verfügbaren Chat-Sitzungsdateien auf und gibt deren sanitisierten Namen zurück."""
        session_names = []
        temp_history = ChatHistory() 
        for f in os.listdir('.'):
            if f.startswith("chat_history_") and f.endswith(".json"):
                session_name = f[len("chat_history_"):-len(".json")]
                sanitized_name = temp_history._sanitize_filename(session_name)
                session_names.append(sanitized_name)
            elif f == CHAT_HISTORY_FILE and os.path.exists(CHAT_HISTORY_FILE):
                session_names.append("default")
        return sorted(list(set(session_names)))

    def get_all_branch_heads(self):
        """
        Identifiziert alle Nachrichten, die Köpfe von Konversationszweigen sind,
        und gibt ein Dictionary zurück: {branch_head_id: first_user_message_content}.
        """
        branch_heads = {}
        
        # Finde alle IDs, die als parent_id verwendet werden (d.h. Nachrichten, die Kinder haben)
        all_parented_message_ids = {msg.get('parent_id') for msg in self.messages.values() if msg.get('parent_id')}
        
        # Nachrichten, die keine Kinder haben, sind potenzielle Branch-Köpfe
        potential_branch_head_ids = [
            msg_id for msg_id in self.messages.keys() 
            if msg_id not in all_parented_message_ids
        ]

        for head_id in potential_branch_head_ids:
            current_id = head_id
            first_user_message_content = "Leerer Branch"
            
            # Traverse back to find the first user message in this branch
            branch_path = []
            while current_id and current_id in self.messages:
                branch_path.append(self.messages[current_id])
                current_id = self.messages[current_id].get('parent_id')
            
            # Reverse to get chronological order for this specific branch
            branch_path.reverse()

            for msg in branch_path:
                if msg['role'] == 'user':
                    first_user_message_content = msg['content']
                    break
            
            # Use the head_id as the key, and the first user message as the value
            branch_heads[head_id] = first_user_message_content
            
        return branch_heads

    def set_current_branch(self, message_id: str):
        """Setzt den aktuellen aktiven Zweig auf die angegebene message_id."""
        if message_id in self.messages:
            self.current_branch_head_id = message_id
            self.save_history()
            print(f"Aktueller Branch-Kopf auf {message_id} gesetzt.")
        else:
            print(f"Fehler: Nachricht mit ID {message_id} nicht gefunden. Aktueller Branch-Kopf nicht geändert.")
