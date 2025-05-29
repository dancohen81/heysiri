import os
import datetime
from PyQt5 import QtWidgets, QtCore

from src.chat_history import ChatHistory

class ChatSessionManager:
    def __init__(self, chat_history: ChatHistory, claude_api, window, status_update_signal, chat_message_signal):
        self.chat_history = chat_history
        self.claude = claude_api
        self.window = window
        self.status_update_signal = status_update_signal
        self.chat_message_signal = chat_message_signal
        self.current_session_name = self.chat_history.session_name

    def _generate_session_title_with_ai(self, messages):
        """Generiert einen Sitzungstitel basierend auf dem Chat-Verlauf mit Claude."""
        if not self.claude:
            print("Claude API nicht verfügbar für Titelgenerierung.")
            return None

        # Erstelle einen Prompt für Claude, um das Thema zu extrahieren
        prompt_messages = [
            {"role": "user", "content": "Fasse den folgenden Chat-Verlauf in einem sehr kurzen, prägnanten Titel (maximal 5-7 Wörter) zusammen, der das Hauptthema der Diskussion widerspiegelt. Antworte nur mit dem Titel, ohne zusätzliche Erklärungen oder Satzzeichen am Ende. Beispiel: 'Diskussion über Wettervorhersage' oder 'Planung des Projekts'.\n\nChat-Verlauf:\n"}
        ]
        for msg in messages:
            prompt_messages.append({"role": msg["role"], "content": msg["content"]})

        try:
            # Claude API aufrufen
            response = self.claude.send_message(prompt_messages)
            # Bereinige die Antwort, falls Claude doch mehr als nur den Titel liefert
            title = response.strip().replace('.', '').replace('"', '')
            return title
        except Exception as e:
            print(f"Fehler bei der KI-Titelgenerierung: {e}")
            return None

    def load_existing_chat(self):
        """Lädt den Chat-Verlauf der aktuellen Sitzung in die UI."""
        self.window.clear_chat_display() # Clear display before loading
        for msg in self.chat_history.messages:
            self.window.add_chat_message(msg["role"], msg["content"])
        self.status_update_signal.emit(f"Sitzung '{self.current_session_name}' geladen", "green")

    def new_chat_session(self):
        """Startet eine neue, leere Chat-Sitzung."""
        default_title = "default"
        # Try to generate a title from the *previous* session if it's not empty
        if self.chat_history.messages:
            generated_title = self._generate_session_title_with_ai(self.chat_history.messages)
            if generated_title:
                default_title = generated_title

        self.window.releaseKeyboard() # Release keyboard before opening dialog
        dialog = QtWidgets.QInputDialog(self.window)
        dialog.setWindowTitle("Neue Sitzung")
        dialog.setLabelText("Name der neuen Sitzung (leer für 'default'):")
        dialog.setTextValue(default_title)
        dialog.setOkButtonText("OK")
        dialog.setCancelButtonText("Abbrechen")
        
        # Select all text in the input field
        dialog.findChild(QtWidgets.QLineEdit).selectAll()

        ok = dialog.exec_()
        session_name = dialog.textValue()
        self.window.grabKeyboard() # Re-grab keyboard after dialog closes

        if ok:
            if not session_name:
                session_name = "default"
            self.current_session_name = session_name
            self.chat_history.new_session(session_name)
            self.load_existing_chat()
            self.status_update_signal.emit(f"Neue Sitzung '{session_name}' gestartet", "green")

    def save_chat_session_as(self):
        """Speichert die aktuelle Chat-Sitzung unter einem neuen Namen."""
        default_title = self.current_session_name
        # Try to generate a title from the current session if it's not empty
        if self.chat_history.messages:
            generated_title = self._generate_session_title_with_ai(self.chat_history.messages)
            if generated_title:
                default_title = generated_title

        self.window.releaseKeyboard() # Release keyboard before opening dialog
        dialog = QtWidgets.QInputDialog(self.window)
        dialog.setWindowTitle("Sitzung speichern unter")
        dialog.setLabelText("Name für die aktuelle Sitzung:")
        dialog.setTextValue(default_title)
        dialog.setOkButtonText("OK")
        dialog.setCancelButtonText("Abbrechen")

        # Select all text in the input field
        dialog.findChild(QtWidgets.QLineEdit).selectAll()

        ok = dialog.exec_()
        session_name = dialog.textValue()
        self.window.grabKeyboard() # Re-grab keyboard after dialog closes

        if ok and session_name:
            # Ensure the session name is valid (e.g., no special characters that would break filenames)
            # For simplicity, we'll just use it as is for now, but a more robust solution might sanitize it.
            self.current_session_name = session_name
            self.chat_history.session_name = session_name # Update session name in ChatHistory instance
            self.chat_history.filename = self.chat_history._get_session_filepath(session_name) # Update filename
            self.chat_history.save_history()
            self.status_update_signal.emit(f"Sitzung '{session_name}' gespeichert", "green")
        else:
            self.status_update_signal.emit("Speichern abgebrochen", "yellow")

    def load_chat_session(self):
        """Lädt eine bestehende Chat-Sitzung."""
        sessions = ChatHistory.list_sessions()
        if not sessions:
            self.status_update_signal.emit("Keine gespeicherten Sitzungen gefunden.", "yellow")
            return

        self.window.releaseKeyboard() # Release keyboard before opening dialog
        session_name, ok = QtWidgets.QInputDialog.getItem(
            self.window, # Use self.window as parent
            "Sitzung laden", 
            "Wähle eine Sitzung:", 
            sessions, 0, False
        )
        self.window.grabKeyboard() # Re-grab keyboard after dialog closes
        if ok and session_name:
            self.current_session_name = session_name
            self.chat_history = ChatHistory(session_name) # Re-initialize ChatHistory for the new session
            self.load_existing_chat()
            self.status_update_signal.emit(f"Sitzung '{session_name}' geladen", "green")
        else:
            self.status_update_signal.emit("Laden abgebrochen", "yellow")

    def export_chat_history(self):
        """Exportiert den Chat-Verlauf in eine Textdatei."""
        self.window.releaseKeyboard() # Release keyboard before opening dialog
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.window, # Use self.window as parent
            "Chat exportieren", 
            "chat_export.txt", 
            "Textdateien (*.txt);;Alle Dateien (*)"
        )
        self.window.grabKeyboard() # Re-grab keyboard after dialog closes
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for msg in self.chat_history.messages:
                        timestamp = datetime.datetime.fromisoformat(msg["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                        f.write(f"[{timestamp}] {msg['role'].capitalize()}: {msg['content']}\n\n")
                self.status_update_signal.emit(f"Chat exportiert nach '{os.path.basename(file_path)}'", "green")
            except Exception as e:
                self.status_update_signal.emit(f"Fehler beim Exportieren: {e}", "red")
        else:
            self.status_update_signal.emit("Export abgebrochen", "yellow")

    def clear_current_chat_session(self):
        """Löscht den gesamten Chat-Verlauf der aktuellen Sitzung."""
        reply = QtWidgets.QMessageBox.question(self.window, 'Chat löschen', 
                                               f"Möchtest du den Chat-Verlauf der aktuellen Sitzung '{self.current_session_name}' wirklich löschen?", 
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.chat_history.clear_history()
            self.window.clear_chat_display()
            self.status_update_signal.emit(f"Chat-Verlauf der Sitzung '{self.current_session_name}' gelöscht", "green")
        else:
            self.status_update_signal.emit("Löschen abgebrochen", "yellow")
