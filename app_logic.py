import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
import openai
import winsound
import threading
from PyQt5 import QtWidgets, QtGui, QtCore
import sys # Added for sys.exit() in main
import requests # Import the requests library

from config import SAMPLERATE, AUDIO_FILENAME, CLAUDE_API_KEY, ELEVENLABS_API_KEY, FILEMAN_MCP_URL
from chat_history import ChatHistory
from api_clients import ClaudeAPI, ElevenLabsTTS
from ui_elements import StatusWindow
from utils import setup_autostart, play_audio_file
from session_manager import ChatSessionManager # New import
from audio_recorder import AudioRecorder # New import

class VoiceChatApp(QtWidgets.QSystemTrayIcon):
    """Hauptanwendung mit System Tray Integration"""
    
    # Define signals for thread-safe UI updates as class attributes
    status_update_signal = QtCore.pyqtSignal(str, str)
    chat_message_signal = QtCore.pyqtSignal(str, str)

    def __init__(self, app):
        # Icons erstellen
        self.icon_idle = self.create_icon("🎤", "#4CAF50")
        self.icon_recording = self.create_icon("🔴", "#F44336")
        
        super().__init__(self.icon_idle)
        self.setToolTip("Voice Chat mit Claude")

        # APIs initialisieren
        self.init_apis()
        
        # UI Setup
        self.window = StatusWindow()
        # Connect StatusWindow signals to VoiceChatApp slots
        self.window.send_message_requested.connect(self.send_message_to_claude) # Connect new signal
        self.window.show()
        
        # Initialize MCP client (optional, if needed for persistent connection)
        self.fileman_mcp_url = FILEMAN_MCP_URL

        # Connect signals to StatusWindow slots (now that they are class attributes)
        self.status_update_signal.connect(self.window.set_status)
        self.chat_message_signal.connect(self.window.add_chat_message)
        self.window.stop_requested.connect(self.stop_processing_from_ui) # Connect stop signal from UI

        # Initialize ChatSessionManager
        self.chat_history = ChatHistory("default") # Initialize with a default session
        self.session_manager = ChatSessionManager(
            self.chat_history, 
            self.claude, 
            self.window, 
            self.status_update_signal, 
            self.chat_message_signal
        )
        # Connect session management signals to the session manager's slots
        self.window.new_session_requested.connect(self.session_manager.new_chat_session)
        self.window.save_session_requested.connect(self.session_manager.save_chat_session_as)
        self.window.load_session_requested.connect(self.session_manager.load_chat_session)
        self.window.export_chat_requested.connect(self.session_manager.export_chat_history)
        self.window.clear_chat_requested.connect(self.session_manager.clear_current_chat_session)

        # Initialize AudioRecorder
        self.audio_recorder = AudioRecorder(self.window)
        self.audio_recorder.status_update_signal.connect(self.window.set_status)
        self.audio_recorder.transcription_ready_signal.connect(self.send_message_to_claude)

        self.setup_tray_menu() # Call after session_manager is initialized

        # Timer für Tastatur-Polling
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.audio_recorder.check_keyboard) # Connect to AudioRecorder's check_keyboard
        self.timer.start(50)  # 50ms = 20 FPS

        # Signals
        self.activated.connect(self.tray_icon_clicked)

        # Chat-Verlauf laden
        self.session_manager.load_existing_chat() # Use session manager to load chat
        
        # Initialize stop flag for managing threads
        self.stop_flag = threading.Event()

    def create_icon(self, emoji, color):
        """Erstellt ein Icon mit Emoji"""
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QColor(color))
        font = painter.font()
        font.setPointSize(16)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, emoji)
        painter.end()
        return QtGui.QIcon(pixmap)

    def init_apis(self):
        """Initialisiert alle APIs"""
        self.claude = None
        self.tts = None
        
        # Claude API
        if os.getenv("CLAUDE_API_KEY"):
            try:
                self.claude = ClaudeAPI(os.getenv("CLAUDE_API_KEY"))
            except Exception as e:
                print(f"Claude API Init Fehler: {e}")
        
        # ElevenLabs TTS (optional)
        if os.getenv("ELEVENLABS_API_KEY"):
            try:
                self.tts = ElevenLabsTTS(os.getenv("ELEVENLABS_API_KEY"))
            except Exception as e:
                print(f"ElevenLabs Init Fehler: {e}")

    def setup_tray_menu(self):
        """Erstellt das System-Tray-Menü"""
        self.menu = QtWidgets.QMenu()
        
        self.menu.addAction("🖥️ Fenster anzeigen", self.show_window)
        self.menu.addSeparator()
        
        # New session management actions
        self.menu.addAction("✨ Neue Sitzung", self.session_manager.new_chat_session)
        self.menu.addAction("💾 Sitzung speichern unter...", self.session_manager.save_chat_session_as)
        self.menu.addAction("📂 Sitzung laden...", self.session_manager.load_chat_session)
        self.menu.addAction("📄 Chat exportieren...", self.session_manager.export_chat_history)
        self.menu.addSeparator()

        self.menu.addAction("🗑️ Aktuelle Sitzung löschen", self.session_manager.clear_current_chat_session)
        self.menu.addAction("⚙️ Autostart aktivieren", self.enable_autostart)
        self.menu.addSeparator()
        self.menu.addAction("📝 System Prompt bearbeiten", self.edit_system_prompt) # New action
        self.menu.addAction("Sound ElevenLabs Einstellungen", self.edit_elevenlabs_settings) # New action for ElevenLabs
        self.menu.addSeparator()
        self.menu.addAction("❌ Beenden", QtWidgets.qApp.quit)
        
        self.setContextMenu(self.menu)

    def edit_elevenlabs_settings(self):
        """Ermöglicht dem Benutzer, die ElevenLabs TTS-Einstellungen zu bearbeiten und zu speichern."""
        from config import ELEVENLABS_VOICE_ID, ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST, ELEVENLABS_STYLE, ELEVENLABS_USE_SPEAKER_BOOST
        
        self.window.releaseKeyboard() # Release keyboard before opening dialog

        dialog = QtWidgets.QDialog(self.window)
        dialog.setWindowTitle("ElevenLabs Einstellungen bearbeiten")
        dialog.setWindowModality(QtCore.Qt.ApplicationModal)
        dialog.resize(400, 300)
        dialog.setMinimumSize(350, 250)

        layout = QtWidgets.QFormLayout(dialog)

        # Voice ID
        voice_id_label = QtWidgets.QLabel("Voice ID:")
        voice_id_input = QtWidgets.QLineEdit(ELEVENLABS_VOICE_ID)
        layout.addRow(voice_id_label, voice_id_input)

        # Stability
        stability_label = QtWidgets.QLabel("Stability (0.0 - 1.0):")
        stability_input = QtWidgets.QDoubleSpinBox()
        stability_input.setRange(0.0, 1.0)
        stability_input.setSingleStep(0.01)
        stability_input.setValue(ELEVENLABS_STABILITY)
        layout.addRow(stability_label, stability_input)

        # Similarity Boost
        similarity_boost_label = QtWidgets.QLabel("Similarity Boost (0.0 - 1.0):")
        similarity_boost_input = QtWidgets.QDoubleSpinBox()
        similarity_boost_input.setRange(0.0, 1.0)
        similarity_boost_input.setSingleStep(0.01)
        similarity_boost_input.setValue(ELEVENLABS_SIMILARITY_BOOST)
        layout.addRow(similarity_boost_label, similarity_boost_input)

        # Style
        style_label = QtWidgets.QLabel("Style (0.0 - 1.0):")
        style_input = QtWidgets.QDoubleSpinBox()
        style_input.setRange(0.0, 1.0)
        style_input.setSingleStep(0.01)
        style_input.setValue(ELEVENLABS_STYLE)
        layout.addRow(style_label, style_input)

        # Use Speaker Boost
        use_speaker_boost_checkbox = QtWidgets.QCheckBox("Use Speaker Boost")
        use_speaker_boost_checkbox.setChecked(ELEVENLABS_USE_SPEAKER_BOOST)
        layout.addRow(use_speaker_boost_checkbox)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addRow(button_box)

        ok = dialog.exec_()
        self.window.grabKeyboard() # Re-grab keyboard after dialog closes

        if ok == QtWidgets.QDialog.Accepted:
            new_voice_id = voice_id_input.text()
            new_stability = stability_input.value()
            new_similarity_boost = similarity_boost_input.value()
            new_style = style_input.value()
            new_use_speaker_boost = use_speaker_boost_checkbox.isChecked()

            try:
                with open("config.py", 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                updated_lines = []
                for line in lines:
                    if line.strip().startswith("ELEVENLABS_VOICE_ID ="):
                        updated_lines.append(f'ELEVENLABS_VOICE_ID = "{new_voice_id}"\n')
                    elif line.strip().startswith("ELEVENLABS_STABILITY ="):
                        updated_lines.append(f'ELEVENLABS_STABILITY = {new_stability}\n')
                    elif line.strip().startswith("ELEVENLABS_SIMILARITY_BOOST ="):
                        updated_lines.append(f'ELEVENLABS_SIMILARITY_BOOST = {new_similarity_boost}\n')
                    elif line.strip().startswith("ELEVENLABS_STYLE ="):
                        updated_lines.append(f'ELEVENLABS_STYLE = {new_style}\n')
                    elif line.strip().startswith("ELEVENLABS_USE_SPEAKER_BOOST ="):
                        updated_lines.append(f'ELEVENLABS_USE_SPEAKER_BOOST = {new_use_speaker_boost}\n')
                    else:
                        updated_lines.append(line)
                
                with open("config.py", 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)
                
                self.status_update_signal.emit("ElevenLabs Einstellungen gespeichert. Bitte App neu starten, damit Änderungen wirksam werden.", "green")
            except Exception as e:
                self.status_update_signal.emit(f"Fehler beim Speichern der ElevenLabs Einstellungen: {e}", "red")
        else:
            self.status_update_signal.emit("Bearbeitung der ElevenLabs Einstellungen abgebrochen", "yellow")

    def edit_system_prompt(self):
        """Ermöglicht dem Benutzer, den System Prompt zu bearbeiten und zu speichern."""
        from config import SYSTEM_PROMPT # Import here to get current value
        
        self.window.releaseKeyboard() # Release keyboard before opening dialog

        dialog = QtWidgets.QDialog(self.window)
        dialog.setWindowTitle("System Prompt bearbeiten")
        dialog.setWindowModality(QtCore.Qt.ApplicationModal)
        dialog.resize(800, 400) # Set initial size
        dialog.setMinimumSize(600, 300) # Set minimum size

        layout = QtWidgets.QVBoxLayout(dialog)

        label = QtWidgets.QLabel("Bearbeite den System Prompt:")
        layout.addWidget(label)

        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlainText(SYSTEM_PROMPT)
        text_edit.setMinimumHeight(200) # Ensure text edit has a decent height
        layout.addWidget(text_edit)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        ok = dialog.exec_()
        new_prompt = text_edit.toPlainText()
        self.window.grabKeyboard() # Re-grab keyboard after dialog closes

        if ok == QtWidgets.QDialog.Accepted:
            try:
                # Read the entire config.py file
                with open("config.py", 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Find and update the SYSTEM_PROMPT line
                updated_lines = []
                found = False
                for line in lines:
                    if line.strip().startswith("SYSTEM_PROMPT ="):
                        updated_lines.append(f'SYSTEM_PROMPT = "{new_prompt}"\n')
                        found = True
                    else:
                        updated_lines.append(line)
                
                # If not found (shouldn't happen if config.py is structured as expected), add it
                if not found:
                    updated_lines.append(f'\nSYSTEM_PROMPT = "{new_prompt}"\n')

                # Write the updated content back to config.py
                with open("config.py", 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)
                
                self.status_update_signal.emit("System Prompt gespeichert. Bitte App neu starten, damit Änderungen wirksam werden.", "green")
            except Exception as e:
                self.status_update_signal.emit(f"Fehler beim Speichern des System Prompts: {e}", "red")
        else:
            self.status_update_signal.emit("Bearbeitung des System Prompts abgebrochen", "yellow")

    def load_existing_chat(self):
        """Lädt den Chat-Verlauf der aktuellen Sitzung in die UI."""
        self.window.clear_chat_display() # Clear display before loading
        for msg in self.chat_history.messages:
            self.window.add_chat_message(msg["role"], msg["content"])
        self.window.set_status(f"Sitzung '{self.current_session_name}' geladen", "green")

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
            self.window.set_status(f"Neue Sitzung '{session_name}' gestartet", "green")

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
            self.window.set_status(f"Sitzung '{session_name}' gespeichert", "green")
        else:
            self.window.set_status("Speichern abgebrochen", "yellow")

    def load_chat_session(self):
        """Lädt eine bestehende Chat-Sitzung."""
        sessions = ChatHistory.list_sessions()
        if not sessions:
            self.window.set_status("Keine gespeicherten Sitzungen gefunden.", "yellow")
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
            self.window.set_status(f"Sitzung '{session_name}' geladen", "green")
        else:
            self.window.set_status("Laden abgebrochen", "yellow")

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
                self.window.set_status(f"Chat exportiert nach '{os.path.basename(file_path)}'", "green")
            except Exception as e:
                self.window.set_status(f"Fehler beim Exportieren: {e}", "red")
        else:
            self.window.set_status("Export abgebrochen", "yellow")

    def clear_current_chat_session(self):
        """Löscht den gesamten Chat-Verlauf der aktuellen Sitzung."""
        reply = QtWidgets.QMessageBox.question(self.window, 'Chat löschen', 
                                               f"Möchtest du den Chat-Verlauf der aktuellen Sitzung '{self.current_session_name}' wirklich löschen?", 
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.chat_history.clear_history()
            self.window.clear_chat_display()
            self.window.set_status(f"Chat-Verlauf der Sitzung '{self.current_session_name}' gelöscht", "green")
        else:
            self.window.set_status("Löschen abgebrochen", "yellow")

    def tray_icon_clicked(self, reason):
        """System Tray Icon Click Handler"""
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.show_window()

    def show_window(self):
        """Zeigt das Hauptfenster"""
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def clear_chat_history(self):
        """Löscht den gesamten Chat-Verlauf"""
        self.chat_history.clear_history()
        self.window.clear_chat_display()
        self.window.set_status("Chat-Verlauf gelöscht", "green")

    def enable_autostart(self):
        """Aktiviert Windows Autostart"""
        if setup_autostart():
            self.window.set_status("Autostart aktiviert", "green")
        else:
            self.window.set_status("Autostart-Setup fehlgeschlagen", "red")

    def check_keyboard(self):
        """Prüft Tastatur-Status (Alt-Taste)"""
        if self.window.alt_pressed:
            if not self.is_recording:
                self.start_recording()
        else:
            if self.is_recording:
                self.stop_recording()

    def start_recording(self):
        """Startet Audio-Aufnahme"""
        try:
            self.setIcon(self.icon_recording)
            self.recording_data = []
            
            self.stream = sd.InputStream(
                samplerate=SAMPLERATE, 
                channels=1, 
                dtype='int16', 
                callback=self.audio_callback
            )
            self.stream.start()
            self.is_recording = True
            self.window.grabKeyboard() # Grab keyboard when recording starts
            self.window.setFocus() # Ensure main window has focus for spacebar
            
            # Audio-Feedback
            winsound.Beep(1000, 150)
            self.status_update_signal.emit("🎙️ Aufnahme läuft...", "red")
            self.window.disable_send_button() # Disable send button during recording
            self.window.enable_stop_button() # Enable stop button during recording
            
        except Exception as e:
            self.status_update_signal.emit(f"Aufnahme-Fehler: {e}", "red")
            self.window.enable_send_button() # Re-enable on error
            self.window.disable_stop_button() # Disable stop on error

    def stop_recording(self):
        """Stoppt Audio-Aufnahme"""
        try:
            self.setIcon(self.icon_idle)
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            self.is_recording = False
            self.window.releaseKeyboard() # Release keyboard when recording stops
            self.window.input_field.setFocus() # Return focus to input field
            
            # Audio-Feedback
            winsound.Beep(800, 100)
            winsound.Beep(600, 100)
            
            self.status_update_signal.emit("🔄 Verarbeite Audio...", "yellow")
            self.window.disable_send_button() # Keep send button disabled during processing
            self.window.enable_stop_button() # Keep stop button enabled during processing
            
            # Verarbeitung in separatem Thread
            threading.Thread(target=self.process_audio_and_chat, daemon=True).start()
            
        except Exception as e:
            self.status_update_signal.emit(f"Stop-Fehler: {e}", "red")
            self.window.enable_send_button() # Re-enable on error
            self.window.disable_stop_button() # Disable stop on error

    def stop_processing_from_ui(self):
        """Stoppt die Verarbeitung, ausgelöst durch die UI."""
        self.stop_processing() # Call the existing stop_processing method
        self.status_update_signal.emit("🛑 Verarbeitung über UI gestoppt.", "yellow")
        self.window.enable_send_button() # Re-enable send button
        self.window.disable_stop_button() # Disable stop button

    def stop_processing(self):
        """Stoppt laufende API-Anfragen und Audio-Verarbeitung."""
        self.stop_flag.set() # Signal threads to stop
        self.status_update_signal.emit("🛑 Verarbeitung gestoppt.", "yellow")
        self.window.enable_send_button() # Re-enable send button
        self.window.disable_stop_button() # Disable stop button

    def audio_callback(self, indata, frames, time, status):
        """Callback für Audio-Stream"""
        if status:
            print(f"Audio Status: {status}")
        self.recording_data.append(indata.copy())

    def process_audio_and_chat(self):
        """Verarbeitet Audio und führt Chat durch"""
        self.stop_flag.clear() # Reset stop flag for new process
        try:
            # 1. Audio-Daten prüfen
            if not self.recording_data:
                self.status_update_signal.emit("Keine Audio-Daten aufgenommen", "yellow")
                self.window.enable_send_button() # Re-enable send button
                self.window.disable_stop_button() # Disable stop button
                return

            # 2. Audio zu WAV speichern
            self.status_update_signal.emit("💾 Speichere Audio...", "blue")
            if self.stop_flag.is_set(): return
            audio_data = np.concatenate(self.recording_data, axis=0)
            wavfile.write(AUDIO_FILENAME, SAMPLERATE, audio_data)

            # 3. Whisper Transkription
            self.status_update_signal.emit("🎯 Transkribiere mit Whisper...", "blue")
            if self.stop_flag.is_set(): return
            
            try:
                with open(AUDIO_FILENAME, "rb") as f:
                    result = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        response_format="text",
                        language="de"
                    )
                
                user_text = result.strip()
                if not user_text:
                    self.status_update_signal.emit("Kein Text erkannt", "yellow")
                    self.window.enable_send_button() # Re-enable send button
                    self.window.disable_stop_button() # Disable stop button
                    return
                    
            except Exception as e:
                if "529" in str(e):
                    self.status_update_signal.emit("OpenAI Server überlastet (529) - warte und versuche nochmal", "red")
                elif "401" in str(e):
                    self.status_update_signal.emit("OpenAI API Key ungültig", "red")
                elif "429" in str(e):
                    self.status_update_signal.emit("OpenAI Rate Limit erreicht", "red")
                else:
                    self.status_update_signal.emit(f"Whisper Fehler: {e}", "red")
                self.window.enable_send_button() # Re-enable send button
                self.window.disable_stop_button() # Disable stop button
                return

            # 4. Transkribierten Text im Eingabefeld anzeigen
            self.window.set_input_text(user_text)
            self.status_update_signal.emit("Transkribiert: " + user_text, "blue")
            self.window.enable_send_button() # Re-enable send button after transcription is displayed
            self.window.disable_stop_button() # Disable stop button

        except Exception as e:
            self.status_update_signal.emit(f"Unerwarteter Fehler: {e}", "red")
            self.window.enable_send_button() # Re-enable on error
            self.window.disable_stop_button() # Disable stop on error
        
        finally:
            # Aufräumen
            if os.path.exists(AUDIO_FILENAME):
                try:
                    os.remove(AUDIO_FILENAME)
                except:
                    pass

    def send_message_to_claude(self, user_text):
        """Sendet die Benutzer-Nachricht an Claude und verarbeitet die Antwort."""
        self.stop_flag.clear() # Reset stop flag for new process
        if not user_text.strip(): # Add this check for empty messages
            self.status_update_signal.emit("Nachricht ist leer, wird nicht gesendet.", "yellow")
            self.window.enable_send_button() # Re-enable send button
            self.window.disable_stop_button() # Disable stop button
            return

        # Add user message to chat display and history immediately
        # Check for MCP commands first
        if self.handle_mcp_command(user_text):
            self.window.enable_send_button()
            self.window.disable_stop_button()
            return

        self.chat_message_signal.emit("user", user_text)
        self.chat_history.add_message("user", user_text)

        if not self.claude:
            self.status_update_signal.emit("Claude API nicht verfügbar", "red")
            self.window.enable_send_button() # Re-enable send button
            self.window.disable_stop_button() # Disable stop button
            return
                
        self.status_update_signal.emit("🤖 Claude antwortet...", "blue")
        self.window.disable_send_button() # Disable send button during Claude processing
        self.window.enable_stop_button() # Enable stop button during Claude processing
            
        try:
            if self.stop_flag.is_set(): return
            context_messages = self.chat_history.get_context_messages()
            claude_response = self.claude.send_message(context_messages)
            if self.stop_flag.is_set(): return
                
            # 6. Claude-Antwort anzeigen und speichern
            self.chat_message_signal.emit("assistant", claude_response)
            self.chat_history.add_message("assistant", claude_response)
                
        except Exception as e:
            self.status_update_signal.emit(f"Claude Fehler: {e}", "red")
            self.window.enable_send_button() # Re-enable on error
            self.window.disable_stop_button() # Disable stop on error
            return
            
        # 7. Text-to-Speech (optional)
        if self.tts:
            self.status_update_signal.emit(" Generiere Sprache mit ElevenLabs...", "blue")
            try:
                if self.stop_flag.is_set(): return
                audio_file = self.tts.text_to_speech(claude_response)
                if self.stop_flag.is_set(): return
                play_audio_file(audio_file, self.stop_flag) # Pass stop_flag to play_audio_file
                self.status_update_signal.emit("✅ Gespräch abgeschlossen", "green")
            except Exception as e:
                if "529" in str(e):
                    self.status_update_signal.emit("ElevenLabs überlastet - Text wurde trotzdem angezeigt", "yellow")
                else:
                    self.status_update_signal.emit(f"TTS Fehler: {e}", "yellow")
        else:
            self.status_update_signal.emit("✅ Antwort erhalten", "green")
        
        self.window.enable_send_button() # Re-enable send button after processing
        self.window.disable_stop_button() # Disable stop button

    def handle_mcp_command(self, user_text):
        """Handles MCP commands from user input."""
        if not user_text.startswith("/fileman"):
            return False

        command_parts = user_text.split(' ', 2) # Split into command, tool, and rest
        if len(command_parts) < 2:
            self.chat_message_signal.emit("assistant", "Ungültiger Fileman-Befehl. Syntax: /fileman <tool> <args>")
            return True

        tool_name = command_parts[1]
        args_str = command_parts[2] if len(command_parts) > 2 else ""

        self.status_update_signal.emit(f"Sende Befehl an Fileman MCP: {tool_name}", "blue")
        self.chat_message_signal.emit("assistant", f"Versuche, Fileman-Tool '{tool_name}' auszuführen...")

        try:
            if tool_name == "save_file":
                # Expected format: /fileman save_file <filePath> <content>
                # Need to parse filePath and content from args_str
                # For simplicity, let's assume args_str is "filePath content" for now
                # A more robust parser would be needed for complex arguments
                parts = args_str.split(' ', 1)
                if len(parts) < 2:
                    self.chat_message_signal.emit("assistant", "Syntax: /fileman save_file <filePath> <content>")
                    return True
                file_path = parts[0]
                content = parts[1]
                
                payload = {
                    "server_name": "fileman",
                    "tool_name": "save_file",
                    "arguments": {
                        "filePath": file_path,
                        "content": content
                    }
                }
            elif tool_name == "describe_file":
                # Expected format: /fileman describe_file <filePath> <description>
                parts = args_str.split(' ', 1)
                if len(parts) < 2:
                    self.chat_message_signal.emit("assistant", "Syntax: /fileman describe_file <filePath> <description>")
                    return True
                file_path = parts[0]
                description = parts[1]

                payload = {
                    "server_name": "fileman",
                    "tool_name": "describe_file",
                    "arguments": {
                        "filePath": file_path,
                        "description": description
                    }
                }
            else:
                self.chat_message_signal.emit("assistant", f"Unbekanntes Fileman-Tool: {tool_name}")
                return True

            headers = {'Content-Type': 'application/json'}
            response = requests.post(self.fileman_mcp_url, json=payload, headers=headers)
            response.raise_for_status() # Raise an exception for HTTP errors

            mcp_response = response.json()
            self.chat_message_signal.emit("assistant", f"Fileman-Antwort: {mcp_response.get('result', 'Keine Antwort')}")
            self.status_update_signal.emit("✅ Fileman-Befehl erfolgreich", "green")

        except requests.exceptions.RequestException as e:
            self.chat_message_signal.emit("assistant", f"Fehler bei der Kommunikation mit Fileman MCP: {e}")
            self.status_update_signal.emit("❌ Fileman-Befehl fehlgeschlagen", "red")
        except Exception as e:
            self.chat_message_signal.emit("assistant", f"Fehler bei der Verarbeitung des Fileman-Befehls: {e}")
            self.status_update_signal.emit("❌ Fileman-Befehl fehlgeschlagen", "red")
        
        return True # Command was handled

def check_api_keys():
    """Prüft verfügbare API Keys"""
    missing_keys = []
    
    if not openai.api_key:
        missing_keys.append("OPENAI_API_KEY (erforderlich)")
    if not CLAUDE_API_KEY:
        missing_keys.append("CLAUDE_API_KEY (erforderlich)")
    if not ELEVENLABS_API_KEY:
        missing_keys.append("ELEVENLABS_API_KEY (optional)")
    
    return missing_keys

def main():
    """Hauptfunktion"""
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # API Keys prüfen
    missing_keys = check_api_keys()
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
