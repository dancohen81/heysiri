import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
import openai
import winsound
import threading
import asyncio
import datetime
from PyQt5 import QtWidgets, QtGui, QtCore
import sys
import requests

from src.config import SAMPLERATE, AUDIO_FILENAME, CLAUDE_API_KEY, ELEVENLABS_API_KEY, FILEMAN_MCP_URL
from src.chat_history import ChatHistory
from src.api_clients import ClaudeAPI, ElevenLabsTTS
from src.ui_elements import StatusWindow
from src.utils import setup_autostart, play_audio_file
from src.session_manager import ChatSessionManager
from src.audio_recorder import AudioRecorder
from src.mcp_client import MCPManager

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
        
        # MCP Manager initialisieren (NEU)
        self.mcp_manager = MCPManager()
        self.mcp_ready = False
        
        # UI Setup
        self.window = StatusWindow()
        self.window.send_message_requested.connect(self.send_message_to_claude)
        self.window.show()
        
        # Initialize MCP client (optional, if needed for persistent connection)
        self.fileman_mcp_url = FILEMAN_MCP_URL

        # Connect signals to StatusWindow slots
        self.status_update_signal.connect(self.window.set_status)
        self.chat_message_signal.connect(self.window.add_chat_message)
        self.window.stop_requested.connect(self.stop_processing_from_ui)

        # Initialize ChatSessionManager
        self.chat_history = ChatHistory("default")
        self.session_manager = ChatSessionManager(
            self.chat_history, 
            self.claude, 
            self.window, 
            self.status_update_signal, 
            self.chat_message_signal
        )
        
        # Connect session management signals
        self.window.new_session_requested.connect(self.session_manager.new_chat_session)
        self.window.save_session_requested.connect(self.session_manager.save_chat_session_as)
        self.window.load_session_requested.connect(self.session_manager.load_chat_session)
        self.window.export_chat_requested.connect(self.session_manager.export_chat_history)
        self.window.clear_chat_requested.connect(self.session_manager.clear_current_chat_session)

        # Initialize AudioRecorder
        self.audio_recorder = AudioRecorder(self.window)
        self.audio_recorder.status_update_signal.connect(self.window.set_status)
        self.audio_recorder.transcription_ready_signal.connect(self.send_message_to_claude)

        # Setup Tray Menu
        self.setup_tray_menu()

        # Timer für Tastatur-Polling
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.audio_recorder.check_keyboard)
        self.timer.start(50)  # 50ms = 20 FPS

        # Signals
        self.activated.connect(self.tray_icon_clicked)

        # Chat-Verlauf laden
        self.session_manager.load_existing_chat()
        
        # Initialize stop flag for managing threads
        self.stop_flag = threading.Event()
        
        # MCP asynchron starten (NEU)
        self.setup_mcp_async()

    def setup_mcp_async(self):
        """Startet MCP Client asynchron"""
        def run_async_setup():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self.mcp_manager.setup())
                self.mcp_ready = success
                if success:
                    self.status_update_signal.emit("✅ MCP Filesystem bereit", "green")
                    tools = self.mcp_manager.get_tools_for_claude()
                    print(f"📁 Verfügbare MCP Tools: {[tool['name'] for tool in tools]}")
                    # NEU: Tray-Status aktualisieren
                    if hasattr(self, 'mcp_status_action'):
                        self.mcp_status_action.setText(f"🔧 ✅ MCP bereit ({len(tools)} Tools)")
                else:
                    self.status_update_signal.emit("⚠️ MCP Filesystem nicht verfügbar", "yellow")
                    # NEU: Tray-Status aktualisieren  
                    if hasattr(self, 'mcp_status_action'):
                        self.mcp_status_action.setText("🔧 ❌ MCP nicht verfügbar")
                loop.close()
            except Exception as e:
                print(f"❌ MCP Setup Fehler: {e}")
                self.status_update_signal.emit("❌ MCP Setup fehlgeschlagen", "red")
                self.mcp_ready = False
        
        # Starte in separatem Thread
        threading.Thread(target=run_async_setup, daemon=True).start()

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

    def get_mcp_status(self):
        """Gibt MCP Status zurück"""
        if self.mcp_ready and self.mcp_manager.is_ready():
            tools = self.mcp_manager.get_tools_for_claude()
            return f"✅ MCP bereit ({len(tools)} Tools)"
        else:
            return "❌ MCP nicht verfügbar"
        
        
        
    # In app_logic.py - Füge diese Methode in die VoiceChatApp Klasse ein:
# Suche nach der Zeile "def get_mcp_status(self):" und füge DANACH ein:

    def get_mcp_status(self):
        """Gibt MCP Status zurück"""
        if self.mcp_ready and self.mcp_manager.is_ready():
            tools = self.mcp_manager.get_tools_for_claude()
            return f"✅ MCP bereit ({len(tools)} Tools)"
        else:
            return "❌ MCP nicht verfügbar"

    # NEU: Füge diese Methoden HIER ein:
    def test_write_permissions(self):
        """Testet Schreibrechte direkt"""
        test_file = "D:/Users/stefa/heysiri/write-test.txt"
        try:
            with open(test_file, 'w') as f:
                f.write("Direct write test successful!")
            print(f"✅ Direkter Schreibtest erfolgreich: {test_file}")
            os.remove(test_file)  # Aufräumen
            return True
        except Exception as e:
            print(f"❌ Direkter Schreibtest fehlgeschlagen: {e}")
            return False

    def debug_mcp_status(self):
        """Debug: MCP Status prüfen"""
        print("\n=== MCP DEBUG INFO ===")
        print(f"MCP Ready: {self.mcp_ready}")
        print(f"MCP Manager Ready: {self.mcp_manager.is_ready() if self.mcp_manager else False}")
        
        if self.mcp_ready and self.mcp_manager:
            tools = self.mcp_manager.get_tools_for_claude()
            print(f"Verfügbare Tools: {len(tools)}")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
        
        # Test Schreibrechte
        write_ok = self.test_write_permissions()
        print(f"Schreibrechte: {'✅ OK' if write_ok else '❌ Fehler'}")
        print("=====================\n")

    # Dann weiter mit setup_tray_menu...

        
        
        
        
        

        
        
        # In setup_tray_menu() nach der MCP-Status-Zeile:

    def detect_file_operation(self, user_input):
        """Erkennt ob eine Dateisystem-Operation angefragt wird"""
        file_keywords = [
            'erstelle', 'schreibe', 'speichere', 'lege an', 'mache',
            'lese', 'zeige', 'inhalt', 'öffne', 'was steht',
            'lösche', 'entferne', 'remove', 'delete',
            'liste', 'dateien', 'ordner', 'verzeichnis', 'welche dateien'
        ]

        user_lower = user_input.lower()
        return any(keyword in user_lower for keyword in file_keywords)

    def get_system_prompt_for_request(self, user_input):
        """Wählt den passenden System Prompt basierend auf der Anfrage"""
        from src.config import CHAT_AGENT_PROMPT, FILE_AGENT_PROMPT

        if self.detect_file_operation(user_input):
            print("🔧 FILE-AGENT aktiviert")
            return FILE_AGENT_PROMPT
        else:
            print("💬 CHAT-AGENT aktiviert")
            return CHAT_AGENT_PROMPT
    
    def setup_tray_menu(self):
        """Erstellt das System-Tray-Menü"""
        self.menu = QtWidgets.QMenu()
        
        self.menu.addAction("🖥️ Fenster anzeigen", self.show_window)
        
        # MCP Status wird dynamisch beim Menü-Öffnen aktualisiert
        self.mcp_status_action = self.menu.addAction("🔧 MCP wird geladen...")
        self.mcp_status_action.setEnabled(False)
        
        # DEBUG: Test-Menü hinzufügen
        self.menu.addAction("🧪 MCP Debug Test", self.debug_mcp_status)
        
        self.menu.addSeparator()
        
        # Session management actions
        self.menu.addAction("✨ Neue Sitzung", self.session_manager.new_chat_session)
        self.menu.addAction("💾 Sitzung speichern unter...", self.session_manager.save_chat_session_as)
        self.menu.addAction("📂 Sitzung laden...", self.session_manager.load_chat_session)
        self.menu.addAction("📄 Chat exportieren...", self.session_manager.export_chat_history)
        self.menu.addSeparator()

        self.menu.addAction("🗑️ Aktuelle Sitzung löschen", self.session_manager.clear_current_chat_session)
        self.menu.addAction("⚙️ Autostart aktivieren", self.enable_autostart)
        self.menu.addSeparator()
        self.menu.addAction("📝 System Prompt bearbeiten", self.edit_system_prompt)
        self.menu.addAction("Sound ElevenLabs Einstellungen", self.edit_elevenlabs_settings)
        self.menu.addSeparator()
        self.menu.addAction("❌ Beenden", self._quit_app)
        
        # Verbinde Menü-Öffnung mit Status-Update
        self.menu.aboutToShow.connect(self.update_tray_menu_status)
        
        self.setContextMenu(self.menu)

    def update_tray_menu_status(self):
        """Aktualisiert MCP Status im Tray-Menü beim Öffnen"""
        current_status = self.get_mcp_status()
        self.mcp_status_action.setText(f"🔧 {current_status}")
    def _quit_app(self):
        """Beendet App und stoppt MCP"""
        if self.mcp_manager:
            self.mcp_manager.stop()
        QtWidgets.qApp.quit()

    def edit_elevenlabs_settings(self):
        """Ermöglicht dem Benutzer, die ElevenLabs TTS-Einstellungen zu bearbeiten und zu speichern."""
        from src.config import ELEVENLABS_VOICE_ID, ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST, ELEVENLABS_STYLE, ELEVENLABS_USE_SPEAKER_BOOST
        
        self.window.releaseKeyboard()

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
        self.window.grabKeyboard()

        if ok == QtWidgets.QDialog.Accepted:
            new_voice_id = voice_id_input.text()
            new_stability = stability_input.value()
            new_similarity_boost = similarity_boost_input.value()
            new_style = style_input.value()
            new_use_speaker_boost = use_speaker_boost_checkbox.isChecked()

            try:
                with open("src/config.py", 'r', encoding='utf-8') as f:
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
                
                with open("src/config.py", 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)
                
                self.status_update_signal.emit("ElevenLabs Einstellungen gespeichert. Bitte App neu starten, damit Änderungen wirksam werden.", "green")
            except Exception as e:
                self.status_update_signal.emit(f"Fehler beim Speichern der ElevenLabs Einstellungen: {e}", "red")
        else:
            self.status_update_signal.emit("Bearbeitung der ElevenLabs Einstellungen abgebrochen", "yellow")

    def edit_system_prompt(self):
        """Ermöglicht dem Benutzer, den System Prompt zu bearbeiten und zu speichern."""
        from src.config import SYSTEM_PROMPT
        
        self.window.releaseKeyboard()

        dialog = QtWidgets.QDialog(self.window)
        dialog.setWindowTitle("System Prompt bearbeiten")
        dialog.setWindowModality(QtCore.Qt.ApplicationModal)
        dialog.resize(800, 400)
        dialog.setMinimumSize(600, 300)

        layout = QtWidgets.QVBoxLayout(dialog)

        label = QtWidgets.QLabel("Bearbeite den System Prompt:")
        layout.addWidget(label)

        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlainText(SYSTEM_PROMPT)
        text_edit.setMinimumHeight(200)
        layout.addWidget(text_edit)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        ok = dialog.exec_()
        new_prompt = text_edit.toPlainText()
        self.window.grabKeyboard()

        if ok == QtWidgets.QDialog.Accepted:
            try:
                with open("src/config.py", 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                updated_lines = []
                found = False
                for line in lines:
                    if line.strip().startswith("SYSTEM_PROMPT ="):
                        updated_lines.append(f'SYSTEM_PROMPT = "{new_prompt}"\n')
                        found = True
                    else:
                        updated_lines.append(line)
                
                if not found:
                    updated_lines.append(f'\nSYSTEM_PROMPT = "{new_prompt}"\n')

                with open("src/config.py", 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)
                
                self.status_update_signal.emit("System Prompt gespeichert. Bitte App neu starten, damit Änderungen wirksam werden.", "green")
            except Exception as e:
                self.status_update_signal.emit(f"Fehler beim Speichern des System Prompts: {e}", "red")
        else:
            self.status_update_signal.emit("Bearbeitung des System Prompts abgebrochen", "yellow")

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

    def stop_processing_from_ui(self):
        """Stoppt die Verarbeitung, ausgelöst durch die UI."""
        self.stop_processing()
        self.status_update_signal.emit("🛑 Verarbeitung über UI gestoppt.", "yellow")
        self.window.enable_send_button()
        self.window.disable_stop_button()

    def stop_processing(self):
        """Stoppt laufende API-Anfragen und Audio-Verarbeitung."""
        self.stop_flag.set()
        self.status_update_signal.emit("🛑 Verarbeitung gestoppt.", "yellow")
        self.window.enable_send_button()
        self.window.disable_stop_button()

    def process_audio_and_chat(self):
        """Verarbeitet Audio und führt Chat durch"""
        self.stop_flag.clear()
        try:
            # 1. Audio-Daten prüfen
            if not hasattr(self.audio_recorder, 'recording_data') or not self.audio_recorder.recording_data:
                self.status_update_signal.emit("Keine Audio-Daten aufgenommen", "yellow")
                self.window.enable_send_button()
                self.window.disable_stop_button()
                return

            # 2. Audio zu WAV speichern
            self.status_update_signal.emit("💾 Speichere Audio...", "blue")
            if self.stop_flag.is_set(): return
            audio_data = np.concatenate(self.audio_recorder.recording_data, axis=0)
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
                    self.window.enable_send_button()
                    self.window.disable_stop_button()
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
                self.window.enable_send_button()
                self.window.disable_stop_button()
                return

            # 4. Transkribierten Text im Eingabefeld anzeigen
            self.window.set_input_text(user_text)
            self.status_update_signal.emit("Transkribiert: " + user_text, "blue")
            self.window.enable_send_button()
            self.window.disable_stop_button()

        except Exception as e:
            self.status_update_signal.emit(f"Unerwarteter Fehler: {e}", "red")
            self.window.enable_send_button()
            self.window.disable_stop_button()
        
        finally:
            # Aufräumen
            if os.path.exists(AUDIO_FILENAME):
                try:
                    os.remove(AUDIO_FILENAME)
                except:
                    pass

    def send_message_to_claude(self, user_text):
        """Sendet die Benutzer-Nachricht an Claude mit MCP Tool Support."""
        self.stop_flag.clear()
        if not user_text.strip():
            self.status_update_signal.emit("Nachricht ist leer, wird nicht gesendet.", "yellow")
            self.window.enable_send_button()
            self.window.disable_stop_button()
            return

        # User-Nachricht zu Chat hinzufügen
        self.chat_message_signal.emit("user", user_text)
        self.chat_history.add_message("user", user_text)

        if not self.claude:
            self.status_update_signal.emit("Claude API nicht verfügbar", "red")
            self.window.enable_send_button()
            self.window.disable_stop_button()
            return
                
        self.status_update_signal.emit("🤖 Claude antwortet...", "blue")
        self.window.disable_send_button()
        self.window.enable_stop_button()
            
        # Starte Claude-Verarbeitung in separatem Thread
        threading.Thread(target=self._process_claude_with_tools, args=(user_text,), daemon=True).start()

    def _process_claude_with_tools(self, user_text):
        """Verarbeitet Claude-Anfrage mit MCP Tools in separatem Thread"""
        try:
            # Async MCP-Verarbeitung in eigenem Event Loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._handle_claude_with_mcp())
            loop.close()
        except Exception as e:
            self.status_update_signal.emit(f"Claude Verarbeitungsfehler: {e}", "red")
            self.window.enable_send_button()
            self.window.disable_stop_button()
            
            
    def get_dynamic_system_prompt(self, user_input):
        """Gibt dynamischen System Prompt zurück"""
        file_keywords = ['erstelle', 'schreibe', 'lese', 'zeige', 'lösche', 'liste', 'dateien']
        user_lower = user_input.lower()
        is_file_operation = any(keyword in user_lower for keyword in file_keywords)

        if is_file_operation:
            print("🔧 FILE-AGENT aktiviert")
            return "Du bist ein Dateisystem-Agent. Verwende IMMER echte MCP-Tools. KEINE JSON-Simulation. Vollständige Pfade: D:/Users/stefa/heysiri/DATEINAME"
        else:
            print("💬 CHAT-AGENT aktiviert")
            return "Du bist ein freundlicher Chat-Assistent auf Deutsch. Sei hilfsbereit und gesprächig."        

    async def _handle_claude_with_mcp(self):
        """Async Handler für Claude mit MCP Tools"""
        try:
            if self.stop_flag.is_set():
                return

            # Context-Nachrichten laden
            context_messages = self.chat_history.get_context_messages()

            # Letzten Benutzer-Input aus dem Chat-Verlauf holen
            last_user_message = ""
            for msg in reversed(context_messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break

            # DUAL-AGENT: System Prompt basierend auf Anfrage wählen
            system_prompt = self.get_system_prompt_for_request(last_user_message)

            # MCP Tools für Claude laden (falls verfügbar)
            tools = []
            if self.mcp_ready and self.mcp_manager.is_ready():
                tools = self.mcp_manager.get_tools_for_claude()
                if tools:
                    self.status_update_signal.emit(f"🔧 Claude hat Zugriff auf {len(tools)} Tools", "blue")

            if self.stop_flag.is_set():
                return

            # Erste Claude-Anfrage mit dynamischem System Prompt
            if tools:
                print(f"🤖 DEBUG: Sende {len(tools)} Tools an Claude API")
                # WICHTIG: Hier System Prompt verwenden (falls ClaudeAPI das unterstützt)
                response = self.claude.send_message_with_tools(context_messages, tools, system_prompt=system_prompt)
            else:
                # Fallback: Normale Nachricht ohne Tools
                content = self.claude.send_message(context_messages, system_prompt=system_prompt)
                response = {
                    "text": content if isinstance(content, str) else (content[0]["text"] if content and content[0].get("type") == "text" else ""),
                    "tool_calls": [],
                    "raw_content": content if not isinstance(content, str) else [{"type": "text", "text": content}]
                }

            if self.stop_flag.is_set():
                return

            # Prüfe ob Claude Tools verwenden möchte
            if response["tool_calls"] and self.mcp_ready:
                await self._execute_tool_calls(response, context_messages, tools)
            else:
                # Normale Antwort ohne Tool-Verwendung
                if response["text"]:
                    self._handle_claude_response(response["text"])
                else:
                    self.status_update_signal.emit("❌ Leere Antwort von Claude", "red")

        except Exception as e:
            self.status_update_signal.emit(f"Claude Fehler: {e}", "red")
        finally:
            self.window.enable_send_button()
            self.window.disable_stop_button()

# HINWEIS: Falls ClaudeAPI keinen system_prompt Parameter hat, 
# dann müssen wir api_clients.py auch anpassen!

    async def _execute_tool_calls(self, initial_response, context_messages, tools):
        """Führt Tool-Aufrufe aus und holt finale Antwort"""
        try:
            self.status_update_signal.emit("🔧 Führe Tool-Aktionen aus...", "blue")
            
            # Tool-Aufrufe ausführen
            tool_results = []
            for tool_call in initial_response["tool_calls"]:
                if self.stop_flag.is_set():
                    return
                    
                tool_name = tool_call["name"]
                tool_args = tool_call["input"]
                tool_id = tool_call["id"]
                
                self.status_update_signal.emit(f"🛠️ Verwende Tool: {tool_name}", "blue")
                
                # Tool über MCP ausführen
                result = await self.mcp_manager.execute_tool(tool_name, tool_args)
                
                # Tool-Ergebnis für Claude formatieren
                tool_result = {
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": str(result)
                    }]
                }
                tool_results.append(tool_result)

            if self.stop_flag.is_set():
                return

            # Finale Claude-Anfrage mit Tool-Ergebnissen
            self.status_update_signal.emit("🤖 Claude verarbeitet Ergebnisse...", "blue")
            
            # Vollständige Nachrichten-Kette aufbauen
            full_messages = context_messages + [{
                "role": "assistant", 
                "content": initial_response["raw_content"]
            }] + tool_results
            
            final_response = self.claude.send_message_with_tools(full_messages, tools)
            
            # Finale Antwort verarbeiten
            if final_response["text"]:
                self._handle_claude_response(final_response["text"])
            else:
                self.status_update_signal.emit("✅ Tool-Aktionen abgeschlossen", "green")

        except Exception as e:
            self.status_update_signal.emit(f"Tool-Ausführung Fehler: {e}", "red")

    def _handle_claude_response(self, claude_text):
        """Verarbeitet Claude-Antwort (Text-Ausgabe + TTS)"""
        try:
            if self.stop_flag.is_set():
                return

            # Claude-Antwort anzeigen und speichern
            self.chat_message_signal.emit("assistant", claude_text)
            self.chat_history.add_message("assistant", claude_text)
            
            # Text-to-Speech (optional)
            if self.tts:
                self.status_update_signal.emit("🔊 Generiere Sprache mit ElevenLabs...", "blue")
                try:
                    if self.stop_flag.is_set():
                        return
                    audio_file = self.tts.text_to_speech(claude_text)
                    if self.stop_flag.is_set():
                        return
                    play_audio_file(audio_file, self.stop_flag)
                    self.status_update_signal.emit("✅ Gespräch abgeschlossen", "green")
                except Exception as e:
                    if "529" in str(e):
                        self.status_update_signal.emit("ElevenLabs überlastet - Text wurde trotzdem angezeigt", "yellow")
                    else:
                        self.status_update_signal.emit(f"TTS Fehler: {e}", "yellow")
            else:
                self.status_update_signal.emit("✅ Antwort erhalten", "green")
                
        except Exception as e:
            self.status_update_signal.emit(f"Antwort-Verarbeitung Fehler: {e}", "red")
            
    # ERWEITERE app_logic.py um diese Debug-Methoden:

def debug_claude_response(self, response, expected_file_op, tools_available):
    """Debug: Analysiert Claude Response"""
    print("\n=== CLAUDE RESPONSE DEBUG ===")
    print(f"📝 Response Text: {response['text'][:100]}...")
    print(f"🔧 Tool Calls: {len(response.get('tool_calls', []))}")
    print(f"📁 Expected File Op: {expected_file_op}")
    print(f"🛠️ Tools Available: {len(tools_available) if tools_available else 0}")
    
    if response.get('tool_calls'):
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call.get('name', 'Unknown')}")
    
    print("============================\n")

def force_file_operation_prompt(self, operation_type, details):
    """Erstellt einen zwingenden Prompt für Dateisystem-Operationen"""
    prompts = {
        'create_files': f"""ZWINGEND: Erstelle JETZT diese Dateien mit write_file Tool:

{details}

Verwende für jede Datei:
write_file(path="D:/Users/stefa/heysiri/[DATEINAME]", content="[INHALT]")

SOFORT ausführen - keine Erklärungen!""",
        
        'list_files': """ZWINGEND: Verwende JETZT list_directory Tool:

list_directory(path="D:/Users/stefa/heysiri")

SOFORT ausführen!""",
        
        'read_file': f"""ZWINGEND: Verwende JETZT read_file Tool:

read_file(path="D:/Users/stefa/heysiri/{details}")

SOFORT ausführen!"""
    }
    
    return prompts.get(operation_type, f"ZWINGEND: Führe Dateisystem-Operation aus: {details}")

# ERWEITERE detect_file_operation() für spezifischere Erkennung:

def detect_file_operation_type(self, user_input):
    """Erkennt spezifischen Typ der Dateisystem-Operation"""
    user_lower = user_input.lower()
    
    # Wochentage-Dateien speziell erkennen
    if any(day in user_lower for day in ['montag', 'dienstag', 'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag', 'wochentag', 'woche']):
        return 'create_weekday_files'
    
    if any(word in user_lower for word in ['erstelle', 'schreibe', 'mache', 'lege an']):
        return 'create_files'
    elif any(word in user_lower for word in ['liste', 'zeige dateien', 'welche dateien']):
        return 'list_files'  
    elif any(word in user_lower for word in ['lese', 'inhalt', 'was steht']):
        return 'read_file'
    elif any(word in user_lower for word in ['lösche', 'entferne']):
        return 'delete_file'
    
    return 'generic_file_op'

def create_weekday_files_prompt(self):
    """Spezial-Prompt für Wochentags-Dateien"""
    return """ZWINGEND: Erstelle JETZT 7 Dateien für jeden Wochentag:

    write_file(path="D:/Users/stefa/heysiri/montag.txt", content="Montag")
    write_file(path="D:/Users/stefa/heysiri/dienstag.txt", content="Dienstag")  
    write_file(path="D:/Users/stefa/heysiri/mittwoch.txt", content="Mittwoch")
    write_file(path="D:/Users/stefa/heysiri/donnerstag.txt", content="Donnerstag")
    write_file(path="D:/Users/stefa/heysiri/freitag.txt", content="Freitag")
    write_file(path="D:/Users/stefa/heysiri/samstag.txt", content="Samstag")
    write_file(path="D:/Users/stefa/heysiri/sonntag.txt", content="Sonntag")

    ALLE 7 Tools SOFORT ausführen - keine Erklärungen!"""

    # ERWEITERE _handle_claude_with_mcp() um bessere Spezial-Behandlung:

    async def _handle_claude_with_mcp(self):
        """Async Handler mit verbesserter Self-Correction"""
        try:
            if self.stop_flag.is_set():
                return

            context_messages = self.chat_history.get_context_messages()

            # Letzten Benutzer-Input holen
            last_user_message = ""
            for msg in reversed(context_messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break

            # Erkenne spezifischen Typ der Dateisystem-Operation
            operation_type = self.detect_file_operation_type(last_user_message)
            expected_file_operation = operation_type != 'generic_file_op' if operation_type else False

            print(f"🔍 Erkannt: {operation_type}, File-Op erwartet: {expected_file_operation}")

            # System Prompt wählen
            system_prompt = self.get_system_prompt_for_request(last_user_message)

            # MCP Tools laden
            tools = []
            if self.mcp_ready and self.mcp_manager.is_ready():
                tools = self.mcp_manager.get_tools_for_claude()
                if tools:
                    self.status_update_signal.emit(f"🔧 Claude hat Zugriff auf {len(tools)} Tools", "blue")

            if self.stop_flag.is_set():
                return

            # Erste Claude-Anfrage
            response = None
            if tools:
                response = self.claude.send_message_with_tools(context_messages, tools, system_prompt=system_prompt)
            else:
                content = self.claude.send_message(context_messages, system_prompt=system_prompt)
                response = {
                    "text": content if isinstance(content, str) else (content[0]["text"] if content and content[0].get("type") == "text" else ""),
                    "tool_calls": [],
                    "raw_content": content if not isinstance(content, str) else [{"type": "text", "text": content}]
                }

            # Debug der ersten Response
            self.debug_claude_response(response, expected_file_operation, tools)

            if self.stop_flag.is_set():
                return

            # 🔄 SMART RETRY: Spezifische Retry-Strategien
            if (not response["tool_calls"] and expected_file_operation and tools):

                self.status_update_signal.emit("🔄 Keine Tools verwendet - Smart Retry...", "yellow")

                # Wähle spezifischen Retry-Prompt
                if operation_type == 'create_weekday_files':
                    retry_prompt = self.create_weekday_files_prompt()
                else:
                    retry_prompt = self.create_retry_prompt(last_user_message)

                retry_messages = context_messages + [{
                    "role": "user", 
                    "content": retry_prompt
                }]

                # Zweiter Versuch mit sehr direktem Prompt
                print(f"🔄 RETRY mit spezifischem Prompt für: {operation_type}")
                response = self.claude.send_message_with_tools(retry_messages, tools, system_prompt=FILE_AGENT_PROMPT)

                # Debug der Retry-Response
                print("🔄 RETRY Response:")
                self.debug_claude_response(response, expected_file_operation, tools)

            # Tool-Ausführung oder normale Antwort
            if response["tool_calls"] and self.mcp_ready:
                await self._execute_tool_calls(response, context_messages, tools, system_prompt)
            else:
                if response["text"]:
                    self._handle_claude_response(response["text"])
                else:
                    self.status_update_signal.emit("❌ Leere Antwort von Claude", "red")

        except Exception as e:
            self.status_update_signal.emit(f"Claude Fehler: {e}", "red")
            print(f"❌ Claude Fehler Details: {e}")
        finally:
            self.window.enable_send_button()
            self.window.disable_stop_button()

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
    print("🔧 MCP Filesystem wird initialisiert...")
    print("Leertaste halten = Aufnahme")
    print("Rechtsklick auf Tray-Icon = Menü")
    
    sys.exit(app.exec_())
	
    

if __name__ == "__main__":
    main()
