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
import uuid # NEW: Import uuid for unique filenames
from pydub import AudioSegment # NEW: Import AudioSegment

from src.config import (
    SAMPLERATE, AUDIO_FILENAME, CLAUDE_API_KEY, ELEVENLABS_API_KEY, FILEMAN_MCP_URL,
    CHAT_AGENT_PROMPT, FILE_AGENT_PROMPT, INTERNET_AGENT_PROMPT, SYSTEM_PROMPT,
    OPENROUTER_API_KEY, ACTIVE_LLM, MAX_TOOL_RESULT_LENGTH # NEU: OpenRouter Imports, MAX_TOOL_RESULT_LENGTH
)
from src.chat_history import ChatHistory
from src.api_clients import ClaudeAPI, ElevenLabsTTS, OpenRouterAPI # NEU: OpenRouterAPI
from src.ui_elements import StatusWindow
from src.utils import setup_autostart, play_audio_file
from src.session_manager import ChatSessionManager
from src.audio_recorder import AudioRecorder
from src.mcp_client import MCPManager
from src.settings_window import SettingsWindow # NEU: Import SettingsWindow
from src.dsp_processor import parse_dsp_commands, _apply_effects_to_segment, clean_text_from_dsp_commands # NEU: Import DSP functions

class VoiceChatApp(QtWidgets.QSystemTrayIcon):
    """Hauptanwendung mit System Tray Integration"""
    
    # Define signals for thread-safe UI updates as class attributes
    status_update_signal = QtCore.pyqtSignal(str, str)
    chat_message_signal = QtCore.pyqtSignal(str, str, str) # role, content, message_id
    send_branch_heads_to_ui_signal = QtCore.pyqtSignal(dict) # New signal to send branch heads to the UI
    refresh_chat_display_signal = QtCore.pyqtSignal() # NEW: Signal to refresh chat display

    def __init__(self, app):
        # Icons erstellen
        self.icon_idle = self.create_icon("🎤", "#4CAF50")
        self.icon_recording = self.create_icon("🔴", "#F44336")
        
        super().__init__(self.icon_idle)
        self.setToolTip("Voice Chat mit Claude")

        # Keyboard state for F3 and F4
        self.f3_pressed = False
        self.f4_pressed = False
        self.press_start_time = None # For F3 hold duration
        self.feedback_given = False # For F3 hold feedback

        # APIs initialisieren
        self.init_apis()
        
        # NEU: Aktiven LLM setzen
        self.llm_api = None
        self.set_active_llm(ACTIVE_LLM)
        
        # MCP Manager initialisieren (NEU)
        self.mcp_manager = MCPManager()
        self.mcp_ready = False
        
        # Initialize ChatHistory and SessionManager first
        self.chat_history = ChatHistory("default")
        self.window = StatusWindow() # Initialize window first
        self.session_manager = ChatSessionManager(
            self.chat_history, 
            self.llm_api, # Pass the active LLM API
            self.window, # Pass the window instance
            self.status_update_signal, 
            self # Pass the VoiceChatApp instance itself
        )

        # UI Setup
        self.window.send_message_requested.connect(self.send_message_to_claude)
        self.window.edit_message_requested.connect(self._on_edit_message_requested) # Connect to new handler
        self.window.show_branches_requested.connect(self._on_show_branches_requested)
        self.window.branch_selected_from_ui.connect(self._on_branch_selected_from_ui)
        self.window.show()
        
        # Connect signals to StatusWindow slots (moved here to ensure window is fully set up)
        self.status_update_signal.connect(self.window.set_status)
        self.refresh_chat_display_signal.connect(self._refresh_chat_display) # NEW: Connect refresh signal
        # self.chat_message_signal.connect(self.window.add_chat_message) # Removed, now handled by _refresh_chat_display
        self.send_branch_heads_to_ui_signal.connect(self.window.show_branch_selection_dialog)
        self.window.stop_requested.connect(self.stop_processing_from_ui)
        self.window.pause_audio_requested.connect(self.toggle_audio_playback)
        
        # Connect session management signals (moved here to ensure session_manager and window are fully initialized)
        self.window.new_session_requested.connect(self.session_manager.new_chat_session)
        self.window.save_session_requested.connect(self.session_manager.save_chat_session_as)
        self.window.load_session_requested.connect(self.session_manager.load_chat_session)
        self.window.export_chat_requested.connect(self.session_manager.export_chat_history)
        self.window.clear_chat_requested.connect(self.session_manager.clear_current_chat_session)

        # Connect new branch_icon_clicked signal from ChatDisplay
        if self.window.chat_display:
            self.window.chat_display.branch_icon_clicked.connect(self._on_branch_selected_from_ui)

        # Initialize AudioRecorder
        self.audio_recorder = AudioRecorder(self.window)
        self.audio_recorder.status_update_signal.connect(self.window.set_status)
        self.audio_recorder.transcription_ready_signal.connect(self.send_message_to_claude)

        # Setup Tray Menu
        self.setup_tray_menu()

        # Initialize MCP client (optional, if needed for persistent connection)
        self.fileman_mcp_url = FILEMAN_MCP_URL

        # Initialize stop and pause flags for managing threads
        self.stop_flag = threading.Event()
        self.pause_flag = threading.Event() # New pause flag
        
        # MCP asynchron starten (NEU)
        self.setup_mcp_async()

        # Chat-Verlauf laden and start keyboard polling (delayed to ensure UI is ready)
        # Schedule _post_init_setup to run after the event loop has processed initial UI events
        QtCore.QTimer.singleShot(0, self._post_init_setup)

    def setup_mcp_async(self):
        """Startet MCP Client asynchron"""
        def run_async_setup():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self.mcp_manager.setup())
                self.mcp_ready = success
                if success:
                    tools = self.mcp_manager.get_tools_for_claude()
                    print(f"📁 Verfügbare MCP Tools: {[tool['name'] for tool in tools]}")
                else:
                    print(f"❌ MCP Setup Fehler: MCP nicht verfügbar")
                loop.close()
            except Exception as e:
                print(f"❌ MCP Setup Fehler: {e}")
                self.mcp_ready = False
        
        # Starte in separatem Thread
        threading.Thread(target=run_async_setup, daemon=True).start()

    def _post_init_setup(self):
        """Performs setup that requires the UI to be fully initialized."""
        # Emit initial status messages here, after UI is ready
        if self.mcp_ready:
            tools = self.mcp_manager.get_tools_for_claude()
            self.status_update_signal.emit(f"✅ MCP Filesystem bereit ({len(tools)} Tools)", "green")
        else:
            self.status_update_signal.emit("⚠️ MCP Filesystem nicht verfügbar", "yellow")

        # Ensure chat_display exists before clearing
        if hasattr(self.window, 'chat_display') and self.window.chat_display is not None:
            self.window.clear_chat_display() # Clear display before loading new chat
        
        self.session_manager.load_existing_chat()
        self.window.set_chat_title(self.session_manager.current_session_name) # Update chat title on load

        # Start Timer für Tastatur-Polling (moved here)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.audio_recorder.check_keyboard)
        self.timer.start(50)  # 50ms = 20 FPS

        # Signals (moved here if they depend on fully initialized UI)
        self.activated.connect(self.tray_icon_clicked)

    def keyPressEvent(self, event):
        """Handles key press events for the main window."""
        if event.key() == QtCore.Qt.Key_F3:
            if not self.f3_pressed: # Only set start time on initial press
                self.press_start_time = QtCore.QDateTime.currentMSecsSinceEpoch()
            self.f3_pressed = True
        elif event.key() == QtCore.Qt.Key_F4:
            self.f4_pressed = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handles key release events for the main window."""
        if event.key() == QtCore.Qt.Key_F3:
            self.f3_pressed = False
            self.press_start_time = None # Reset on release
            self.feedback_given = False # Reset on release
        elif event.key() == QtCore.Qt.Key_F4:
            self.f4_pressed = False
        super().keyReleaseEvent(event)

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
        """Initialisiert alle APIs (Claude, OpenRouter, ElevenLabs)"""
        self.claude_api_instance = None
        self.openrouter_api_instance = None
        self.tts = None
        
        # Claude API
        claude_key = os.getenv("CLAUDE_API_KEY")
        if claude_key:
            try:
                self.claude_api_instance = ClaudeAPI(claude_key)
                print("✅ Claude API initialisiert.")
            except Exception as e:
                print(f"❌ Claude API Init Fehler: {e}")
        
        # OpenRouter API
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            try:
                self.openrouter_api_instance = OpenRouterAPI(openrouter_key)
                print("✅ OpenRouter API initialisiert.")
            except Exception as e:
                print(f"❌ OpenRouter API Init Fehler: {e}")

        # ElevenLabs TTS (optional)
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        if elevenlabs_key:
            try:
                self.tts = ElevenLabsTTS(elevenlabs_key)
                print("✅ ElevenLabs TTS initialisiert.")
            except Exception as e:
                print(f"❌ ElevenLabs Init Fehler: {e}")

    def set_active_llm(self, llm_name: str):
        """Setzt den aktiven LLM basierend auf dem Namen."""
        if llm_name == "claude" and self.claude_api_instance:
            self.llm_api = self.claude_api_instance
            print("🧠 Aktiver LLM: Claude")
        elif llm_name == "openrouter" and self.openrouter_api_instance:
            self.llm_api = self.openrouter_api_instance
            print("🧠 Aktiver LLM: OpenRouter")
        else:
            self.llm_api = None
            print(f"❌ Kein gültiger LLM ausgewählt oder API nicht initialisiert: {llm_name}")
        
        # Update session manager with the currently active LLM
        if hasattr(self, 'session_manager'):
            self.session_manager.claude = self.llm_api # Rename claude to llm_api in session_manager

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

    def detect_internet_operation(self, user_input):
        """Erkennt ob eine Internet-Operation angefragt wird"""
        internet_keywords = [
            'hole inhalt', 'fetch', 'webseite', 'url', 'internet', 'surfe', 'besuche'
        ]
        user_lower = user_input.lower()
        return any(keyword in user_lower for keyword in internet_keywords)

    def get_system_prompt_for_request(self, user_input):
        """Wählt den passenden System Prompt basierend auf der Anfrage"""
        from src.config import CHAT_AGENT_PROMPT, FILE_AGENT_PROMPT, INTERNET_AGENT_PROMPT

        if self.detect_file_operation(user_input):
            print("🔧 FILE-AGENT aktiviert")
            return FILE_AGENT_PROMPT
        elif self.detect_internet_operation(user_input):
            print("🌐 INTERNET-AGENT aktiviert")
            return INTERNET_AGENT_PROMPT
        else:
            print("💬 CHAT-AGENT aktiviert")
            print(f"DEBUG: Aktiver System Prompt: CHAT_AGENT_PROMPT") # ADDED DEBUG PRINT
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
        self.menu.addAction("⚙️ Einstellungen", self.open_settings_window) # NEU: Einstellungen-Menüpunkt
        self.menu.addSeparator()
        # Font Size Submenu
        font_size_menu = self.menu.addMenu("🔠 Schriftgrösse")
        font_sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28]
        for size in font_sizes:
            action = font_size_menu.addAction(f"{size} pt")
            action.setData(size) # Store the font size in the action's data
            action.triggered.connect(lambda checked, s=size: self._set_font_size(s)) # Use lambda to pass size
        self.menu.addSeparator()

        self.menu.addAction("📝 System Prompt bearbeiten", self.edit_system_prompt)
        self.menu.addAction("Sound ElevenLabs Einstellungen", self.edit_elevenlabs_settings)
        self.menu.addSeparator()
        self.menu.addAction("❌ Beenden", self._quit_app)
        
        # Verbinde Menü-Öffnung mit Status-Update
        self.menu.aboutToShow.connect(self.update_tray_menu_status)
        
        self.setContextMenu(self.menu)

    def _set_font_size(self, size):
        """Sets the font size of relevant UI elements via the UI window."""
        if self.window:
            self.window.set_font_size(size)

    def update_tray_menu_status(self):
        """Aktualisiert MCP Status im Tray-Menü beim Öffnen"""
        current_status = self.get_mcp_status()
        self.mcp_status_action.setText(f"🔧 {current_status}")

    # NEU: Methode zum Öffnen des Einstellungsfensters
    def open_settings_window(self):
        """Öffnet das Einstellungsfenster."""
        # Pass the mcp_manager instance to the settings window
        settings_dialog = SettingsWindow(self.mcp_manager, self.window)
        settings_dialog.exec_()
        # After settings are saved, re-setup MCP manager to apply changes
        # This needs to be run in an async context, so we'll use a thread for now.
        # A more robust solution would involve better async integration with PyQt.
        def run_mcp_re_setup():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.mcp_manager.setup())
            self.mcp_ready = self.mcp_manager.is_ready()
            self.status_update_signal.emit("✅ MCP Manager neu initialisiert.", "green")
            loop.close()
        threading.Thread(target=run_mcp_re_setup, daemon=True).start()
        self.update_tray_menu_status() # Update tray status immediately

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
        similarity_input.setValue(ELEVENLABS_SIMILARITY_BOOST)
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

    def _refresh_chat_display(self):
        """Refreshes the chat display with messages from the current active branch."""
        print("DEBUG: _refresh_chat_display called.")
        current_branch_messages = self.chat_history.get_current_branch_messages()
        print(f"DEBUG: Messages to display: {len(current_branch_messages)}")
        current_branch_head_id = self.chat_history.current_branch_head_id
        all_messages_dict = self.chat_history.messages # Pass the full dictionary for branch point detection
        font_size = self.window.current_font_size # Get current font size from UI
        
        self.window.chat_display.display_messages(current_branch_messages, current_branch_head_id, all_messages_dict, font_size)
        print("DEBUG: chat_display.display_messages called.")

    def _on_edit_message_requested(self, message_id: str, content: str):
        """Handles the request to edit a message from the UI."""
        # Store the ID of the message being edited
        self.session_manager.editing_message_id = message_id
        # Pre-fill input field with original message content (content is passed from UI)
        # If content is empty, try to fetch from chat_history (fallback)
        if not content:
            message_obj = self.chat_history.messages.get(message_id)
            if message_obj:
                content = message_obj.get('content', '')
        self.window.set_input_text(content)
        self.status_update_signal.emit(f"Nachricht zur Bearbeitung geladen. Bearbeiten und erneut senden.", "yellow")

    def send_message_to_claude(self, user_text):
        """Sendet die Benutzer-Nachricht an Claude mit MCP Tool Support."""
        print(f"DEBUG: send_message_to_claude called with text: '{user_text}'")
        self.stop_flag.clear()
        if not user_text.strip():
            self.status_update_signal.emit("Nachricht ist leer, wird nicht gesendet.", "yellow")
            self.window.enable_send_button()
            self.window.disable_stop_button()
            return

        message_id = None
        if self.session_manager.editing_message_id:
            print(f"DEBUG: Bearbeitete Nachricht erkannt. Original ID: {self.session_manager.editing_message_id}")
            # This is an edited message, create a new branch from the original's parent
            original_message_id = self.session_manager.editing_message_id
            original_message = self.chat_history.messages.get(original_message_id)
            
            if original_message:
                # Get the parent_id of the original message. If it doesn't exist, it's a root message.
                parent_for_new_branch = original_message.get('parent_id')
                
                # Temporarily set current_branch_head_id to the parent of the original message
                # so that add_message creates the new message as a sibling/new branch.
                # Store the original current_branch_head_id to restore it later.
                # original_current_branch_head_id = self.chat_history.current_branch_head_id # Not needed if we always refresh
                self.chat_history.current_branch_head_id = parent_for_new_branch
                
                message_id = self.chat_history.add_message("user", user_text)
                
                # Set the current branch head to the newly added edited message
                self.chat_history.current_branch_head_id = message_id
                
                self.status_update_signal.emit("Nachricht bearbeitet und als neuen Branch gesendet.", "green")
            else:
                self.status_update_signal.emit("Fehler: Originalnachricht zur Bearbeitung nicht gefunden.", "red")
                # Fallback to normal add if original not found
                message_id = self.chat_history.add_message("user", user_text)
                # If fallback, ensure current_branch_head_id is set to the new message
                self.chat_history.current_branch_head_id = message_id
            
            self.session_manager.editing_message_id = None # Reset editing state
            self.refresh_chat_display_signal.emit() # Refresh display after editing
            
        else:
            print("DEBUG: Neue Nachricht erkannt.")
            # Normal new message
            message_id = self.chat_history.add_message("user", user_text)
            print(f"DEBUG: Message added to history with ID: {message_id}")
            print(f"DEBUG: Current chat history message count: {self.chat_history.get_message_count()}")
            self.status_update_signal.emit("Nachricht gesendet.", "green")
            self.refresh_chat_display_signal.emit() # Refresh display after new message
            print("DEBUG: refresh_chat_display_signal emitted.")

        if not self.llm_api:
            self.status_update_signal.emit("Kein LLM API verfügbar", "red")
            self.window.enable_send_button()
            self.window.disable_stop_button()
            return
                
        self.status_update_signal.emit(f"🤖 {self.llm_api.__class__.__name__.replace('API', '')} antwortet...", "blue")
        self.window.disable_send_button()
        self.window.enable_stop_button()
            
        # Starte LLM-Verarbeitung in separatem Thread
        threading.Thread(target=self._process_llm_with_tools, args=(user_text,), daemon=True).start()

    def _process_llm_with_tools(self, user_text): # Umbenannt von _process_claude_with_tools
        """Verarbeitet LLM-Anfrage mit MCP Tools in separatem Thread"""
        try:
            # Async MCP-Verarbeitung in eigenem Event Loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._handle_llm_with_mcp()) # Umbenannt von _handle_claude_with_mcp
            loop.close()
        except Exception as e:
            self.status_update_signal.emit(f"LLM Verarbeitungsfehler: {e}", "red")
            self.window.enable_send_button()
            self.window.disable_stop_button()
            
            
    def get_dynamic_system_prompt(self, user_input):
        """Gibt dynamischen System Prompt zurück"""
        file_keywords = ['erstelle', 'schreibe', 'lese', 'zeige', 'lösche', 'liste', 'dateien']
        user_lower = user_input.lower()
        is_file_operation = any(keyword in user_lower for keyword in file_keywords)

        if is_file_operation:
            print("🔧 FILE-AGENT aktiviert")
            return FILE_AGENT_PROMPT
        else:
            print("💬 CHAT-AGENT aktiviert")
            return CHAT_AGENT_PROMPT        

    async def _handle_llm_with_mcp(self): # Umbenannt von _handle_claude_with_mcp
        """Async Handler für LLM mit MCP Tools"""
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

            # MCP Tools für LLM laden (falls verfügbar)
            tools = []
            if self.mcp_ready and self.mcp_manager.is_ready():
                tools = self.mcp_manager.get_tools_for_claude() # Still uses Claude's tool format
                if tools:
                    self.status_update_signal.emit(f"🔧 {self.llm_api.__class__.__name__.replace('API', '')} hat Zugriff auf {len(tools)} Tools", "blue")

            if self.stop_flag.is_set():
                return

            # Erste LLM-Anfrage mit dynamischem System Prompt
            response = None
            
            print(f"DEBUG: Sende folgende Nachrichten an LLM: {context_messages}")
            print(f"DEBUG: Mit System Prompt: {system_prompt}")

            if tools:
                print(f"🤖 DEBUG: Sende {len(tools)} Tools an {self.llm_api.__class__.__name__}")
                response = self.llm_api.send_message_with_tools(context_messages, tools, system_prompt=system_prompt)
            else:
                # Fallback: Normale Nachricht ohne Tools
                content = self.llm_api.send_message(context_messages, system_prompt=system_prompt)
                # Ensure response format is consistent for both LLMs
                if isinstance(content, dict) and "text" in content: # OpenRouter returns dict
                    response = content
                elif isinstance(content, str): # Claude returns str if no tools
                    response = {
                        "text": content,
                        "tool_calls": [],
                        "raw_content": [{"type": "text", "text": content}]
                    }
                elif isinstance(content, list) and content and content[0].get("type") == "text": # Claude returns list of content blocks with tools=True but no tool_calls
                    response = {
                        "text": content[0]["text"],
                        "tool_calls": [],
                        "raw_content": content
                    }
                else:
                    response = {"text": "", "tool_calls": [], "raw_content": []}


            if self.stop_flag.is_set():
                return

            # Prüfe ob LLM Tools verwenden möchte
            if response["tool_calls"] and self.mcp_ready:
                await self._execute_tool_calls(response, context_messages, tools, system_prompt)
            else:
                # Normale Antwort ohne Tool-Verwendung
                if response["text"]:
                    await self._handle_llm_response(response["text"]) # Umbenannt von _handle_claude_response
                else:
                    self.status_update_signal.emit("❌ Leere Antwort vom LLM", "red")

        except Exception as e:
            self.status_update_signal.emit(f"LLM Verarbeitungsfehler: {e}", "red")
            print(f"❌ LLM Fehler Details: {e}")
        finally:
            self.window.enable_send_button()
            self.window.disable_stop_button()

    async def _execute_tool_calls(self, initial_response, context_messages, tools, system_prompt):
        """Führt Tool-Aufrufe aus und holt finale Antwort in einer Schleife"""
        current_response = initial_response
        current_messages = context_messages + [{
            "role": "assistant", 
            "content": initial_response["raw_content"]
        }]
        
        max_tool_iterations = 12 # Begrenze die Anzahl der Tool-Iterationen
        iteration_count = 0

        while current_response["tool_calls"] and iteration_count < max_tool_iterations:
            iteration_count += 1
            self.status_update_signal.emit(f"🔧 Führe Tool-Aktionen aus (Iteration {iteration_count})...", "blue")
            print(f"DEBUG: Starte Tool-Iteration {iteration_count}")

            tool_results = []
            for tool_call in current_response["tool_calls"]:
                if self.stop_flag.is_set():
                    print("DEBUG: Stop-Flag gesetzt, beende Tool-Ausführung.")
                    return
                    
                tool_name = tool_call["name"]
                tool_args = tool_call["input"]
                tool_id = tool_call["id"]
                
                self.status_update_signal.emit(f"🛠️ Verwende Tool: {tool_name}", "blue")
                print(f"DEBUG: Ausführen von Tool: {tool_name} mit Argumenten: {tool_args}")
                
                # Tool über MCP ausführen
                result = await self.mcp_manager.execute_tool(tool_name, tool_args)
                
                # Tool-Ergebnis für LLM formatieren (muss mit Claude's Tool-Result Format übereinstimmen)
                result_str = str(result)
                if len(result_str) > MAX_TOOL_RESULT_LENGTH:
                    original_length = len(result_str)
                    result_str = result_str[:MAX_TOOL_RESULT_LENGTH] + f"\n... (Ergebnis gekürzt von {original_length} auf {MAX_TOOL_RESULT_LENGTH} Zeichen)"
                    print(f"DEBUG: Tool-Ergebnis für {tool_name} gekürzt. Original: {original_length}, Gekürzt: {len(result_str)}")

                tool_result = {
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_str
                    }]
                }
                tool_results.append(tool_result)
                print(f"DEBUG: Tool-Ergebnis für {tool_name}: {result_str[:100]}...") # Print only first 100 chars for debug

            if self.stop_flag.is_set():
                print("DEBUG: Stop-Flag gesetzt nach Tool-Ausführung, beende.")
                return

            # Füge Tool-Ergebnisse zu den Nachrichten hinzu
            current_messages.extend(tool_results)
            
            self.status_update_signal.emit(f"🤖 {self.llm_api.__class__.__name__.replace('API', '')} verarbeitet Ergebnisse und sucht nach weiteren Tools...", "blue")
            print("DEBUG: Sende Tool-Ergebnisse zurück an LLM für nächste Runde.")
            
            # Nächste LLM-Anfrage mit Tool-Ergebnissen
            current_response = self.llm_api.send_message_with_tools(current_messages, tools, system_prompt=system_prompt)
            
            # Debug der aktuellen LLM-Antwort
            self.debug_llm_response(current_response, True, tools) # Umbenannt von debug_claude_response

            # Füge die neue Assistenten-Antwort (mit möglichen neuen Tool-Aufrufen) zu den Nachrichten hinzu
            if current_response["raw_content"]:
                current_messages.append({
                    "role": "assistant",
                    "content": current_response["raw_content"]
                })
            
            if not current_response["tool_calls"]:
                print("DEBUG: LLM hat keine weiteren Tool-Aufrufe generiert. Beende Schleife.")
                break # Keine weiteren Tool-Aufrufe, Schleife beenden

        # Finale Antwort verarbeiten (Text oder Abschlussmeldung)
        if current_response["text"]:
            await self._handle_llm_response(current_response["text"]) # Umbenannt von _handle_claude_response
        else:
            self.status_update_signal.emit("✅ Alle Tool-Aktionen abgeschlossen.", "green")
            print("DEBUG: Alle Tool-Aktionen abgeschlossen, keine Textantwort.")

        if iteration_count >= max_tool_iterations:
            self.status_update_signal.emit("⚠️ Maximale Tool-Iterationen erreicht. Möglicherweise nicht alle Aufgaben erledigt.", "yellow")
            print("DEBUG: Maximale Tool-Iterationen erreicht.")

        print("DEBUG: _execute_tool_calls beendet.")

    async def _handle_llm_response(self, llm_text): # Umbenannt von _handle_claude_response
        """Verarbeitet LLM-Antwort (Text-Ausgabe + TTS)"""
        print(f"DEBUG: _handle_llm_response called with text: '{llm_text[:50]}...'")
        try:
            self.window.grabKeyboard() # Ensure window has keyboard focus
            if self.stop_flag.is_set():
                return

            # LLM-Antwort anzeigen und speichern
            message_id = self.chat_history.add_message("assistant", llm_text)
            self.refresh_chat_display_signal.emit() # Refresh display after assistant message

            # NEU: Titel generieren, wenn noch "default" und genug Nachrichten
            if self.session_manager.current_session_name == "default" and self.chat_history.get_message_count() >= 2:
                def generate_title_and_update():
                    # Pass the current branch messages for title generation
                    generated_title = self.session_manager._generate_session_title_with_ai(self.chat_history.get_current_branch_messages())
                    if generated_title:
                        self.session_manager.current_session_name = generated_title
                        self.chat_history.session_name = generated_title # Update ChatHistory instance
                        self.chat_history.save_history() # Save with new title
                        self.window.set_chat_title(generated_title)
                        self.status_update_signal.emit(f"Titel generiert: '{generated_title}'", "green")
                    else:
                        self.status_update_signal.emit("Titelgenerierung fehlgeschlagen.", "yellow")
                
                # Führe Titelgenerierung in einem separaten Thread aus, um UI nicht zu blockieren
                threading.Thread(target=generate_title_and_update, daemon=True).start()
            
            # Text-to-Speech (optional)
            if self.tts:
                self.status_update_signal.emit("🔊 Generiere Sprache mit ElevenLabs...", "blue")
                try:
                    if self.stop_flag.is_set():
                        return
                    
                    # Parse the AI response text into segments with commands
                    text_segments_info = parse_dsp_commands(llm_text)
                    print(f"DEBUG: Parsed text segments info: {text_segments_info}") # ADDED DEBUG PRINT
                    
                    processed_audio_segments = []
                    has_dsp_effects = False

                    for i, segment_info in enumerate(text_segments_info):
                        segment_text = segment_info["text"]
                        segment_commands = segment_info["commands"]
                        print(f"DEBUG: Processing segment {i} - Text: '{segment_text[:50]}...', Commands: {segment_commands}")

                        audio_segment = AudioSegment.empty()
                        original_audio_duration_ms = 0 # Store original duration

                        # Clean segment_text from DSP commands before sending to ElevenLabs
                        cleaned_segment_text = clean_text_from_dsp_commands(segment_text)

                        if cleaned_segment_text.strip(): # Ensure cleaned_segment_text is not just empty or whitespace
                            self.status_update_signal.emit(f"🔊 Generiere Sprache für Segment: '{cleaned_segment_text[:50]}...' ", "blue")
                            audio_file_path_for_segment = self.tts.text_to_speech(cleaned_segment_text) # Use cleaned text
                            if self.stop_flag.is_set(): return
                            audio_segment = AudioSegment.from_file(audio_file_path_for_segment)
                            original_audio_duration_ms = audio_segment.duration_seconds * 1000
                        else:
                            print(f"DEBUG: Cleaned segment text is empty or only whitespace. Skipping TTS for this segment.")
                            continue # Skip TTS if there's no actual text to speak
                        
                        processed_segment = audio_segment # Default to original audio

                        # Check if this segment has echo or reverb commands
                        has_time_domain_effect = any(cmd.startswith("!echo:") or cmd.startswith("!hall:") for cmd in segment_commands)

                        # if segment_commands: # Temporarily disable DSP effects for debugging
                        #     processed_segment = _apply_effects_to_segment(audio_segment, segment_commands)
                        #     has_dsp_effects = True
                        
                        # Now, handle trimming the echo tail if the next segment doesn't have a time-domain effect
                        if has_time_domain_effect:
                            # Check the next segment
                            next_segment_has_time_domain_effect = False
                            if i + 1 < len(text_segments_info):
                                next_segment_commands = text_segments_info[i+1]["commands"]
                                next_segment_has_time_domain_effect = any(cmd.startswith("!echo:") or cmd.startswith("!hall:") for cmd in next_segment_commands)
                            
                            if not next_segment_has_time_domain_effect:
                                # If the next segment does NOT have a time-domain effect,
                                # trim the current processed_segment back to its original duration
                                # or fade it out to ensure the echo doesn't bleed.
                                # Trimming is simpler for now.
                                if processed_segment.duration_seconds * 1000 > original_audio_duration_ms:
                                    processed_segment = processed_segment[:original_audio_duration_ms]
                                    # Optionally, add a short fade out to avoid clicks
                                    # processed_segment = processed_segment.fade_out(50) # Fade out last 50ms
                        
                        processed_audio_segments.append(processed_segment)
                    
                    # Concatenate all processed segments
                    final_processed_audio = AudioSegment.empty()
                    for segment in processed_audio_segments:
                        final_processed_audio += segment

                    # Save the final processed audio to a temporary file
                    output_dir = "temp_audio"
                    os.makedirs(output_dir, exist_ok=True)
                    temp_output_path = os.path.join(output_dir, f"dsp_final_{uuid.uuid4()}.wav")
                    
                    final_processed_audio.export(temp_output_path, format="wav")
                    
                    audio_to_play = temp_output_path

                    print(f"DEBUG: Attempting to play audio from: {audio_to_play}")
                    print(f"DEBUG: File exists before playback: {os.path.exists(audio_to_play)}")

                    if has_dsp_effects:
                        self.status_update_signal.emit("✅ DSP-Verarbeitung abgeschlossen.", "green")

                    self.window.enable_pause_button() # Enable pause button when audio starts
                    play_audio_file(audio_to_play, self.stop_flag, self.pause_flag)
                    self.window.disable_pause_button() # Disable pause button when audio finishes
                    self.status_update_signal.emit("✅ Gespräch abgeschlossen", "green")
                except Exception as e:
                    self.window.disable_pause_button() # Ensure button is disabled on error
                    if "529" in str(e):
                        self.status_update_signal.emit("ElevenLabs überlastet - Text wurde trotzdem angezeigt", "yellow")
                    else:
                        self.status_update_signal.emit(f"TTS Fehler: {e}", "yellow")
            else:
                self.status_update_signal.emit("✅ Antwort erhalten", "green")
                
        except Exception as e:
            self.window.disable_pause_button() # Ensure button is disabled on error
            self.status_update_signal.emit(f"Antwort-Verarbeitung Fehler: {e}", "red")
        finally:
            self.window.releaseKeyboard() # Explicitly release keyboard after processing
            
    def debug_llm_response(self, response, expected_tool_op, tools_available): # Umbenannt von debug_claude_response
        """Debug: Analysiert LLM Response"""
        print("\n=== LLM RESPONSE DEBUG ===")
        print(f"📝 Response Text: {response['text'][:100]}...")
        print(f"🔧 Tool Calls: {len(response.get('tool_calls', []))}")
        print(f"⚙️ Expected Tool Op: {expected_tool_op}")
        print(f"🛠️ Tools Available: {len(tools_available) if tools_available else 0}")
        
        if response.get('tool_calls'):
            for i, tool_call in enumerate(response['tool_calls']):
                print(f"  Tool {i+1}: {tool_call.get('name', 'Unknown')}")
        
        print("============================\n")

    def toggle_audio_playback(self):
        """Toggles audio playback between paused and resumed states."""
        if hasattr(self, 'pause_flag'):
            if self.pause_flag.is_set():
                self.pause_flag.clear() # Resume
                self.status_update_signal.emit("▶️ Audio fortgesetzt.", "green")
            else:
                self.pause_flag.set() # Pause
                self.status_update_signal.emit("⏸️ Audio pausiert.", "yellow")
        else:
            self.status_update_signal.emit("Kein Audio zum Pausieren/Fortsetzen.", "yellow")

    def _on_show_branches_requested(self):
        """Slot to handle request for showing chat branches."""
        self.status_update_signal.emit("Lade Chat-Branches...", "blue")
        # Get branch heads from chat_history
        branch_heads = self.chat_history.get_all_branch_heads()
        self.send_branch_heads_to_ui_signal.emit(branch_heads)
        self.status_update_signal.emit("Chat-Branches geladen.", "green")

    def _on_branch_selected_from_ui(self, message_id: str):
        """Slot to handle selection of a branch from the UI."""
        self.status_update_signal.emit(f"Wechsle zu Branch: {message_id[:8]}...", "blue")
        self.chat_history.set_current_branch(message_id) # Set the new branch head
        self._refresh_chat_display() # Refresh display after branch change
        self.status_update_signal.emit("Branch gewechselt.", "green")


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

    def force_internet_operation_prompt(self, operation_type, details):
        """Erstellt einen zwingenden Prompt für Internet-Operationen"""
        prompts = {
            'fetch_url': f"""ZWINGEND: Hole JETZT den Inhalt von dieser URL mit fetch_url Tool:

fetch_url(url="{details}")

SOFORT ausführen - keine Erklärungen!"""
        }
        return prompts.get(operation_type, f"ZWINGEND: Führe Internet-Operation aus: {details}")

    def create_retry_prompt(self, original_user_input):
        """Erstellt einen spezifischen Retry-Prompt für Claude."""
        return f"""Der vorherige Versuch, Ihre Anweisung "{original_user_input}" auszuführen, hat nicht die erwarteten Tool-Aufrufe generiert.

ZWINGEND: Generieren Sie JETZT die notwendigen Tool-Aufrufe, um die Aufgabe vollständig abzuschließen.
- Verwenden Sie IMMER vollständige Pfade: D:/Users/stefa/heysiri/DATEINAME
- Verwenden Sie IMMER echte MCP-Tools - KEINE Simulation oder Erklärungen
- FÜHREN Sie die Operation SOFORT aus - nicht nur darüber reden

Wenn die Aufgabe die Erstellung mehrerer Dateien beinhaltet, generieren Sie ALLE write_file-Aufrufe in EINER EINZIGEN Antwort.
Beispiel:
write_file(path="D:/Users/stefa/heysiri/datei1.txt", content="Inhalt 1")
write_file(path="D:/Users/stefa/heysiri/datei2.txt", content="Inhalt 2")

Fahren Sie mit der Aufgabe fort, bis sie vollständig abgeschlossen ist.
"""

    def detect_operation_type(self, user_input):
        """Erkennt spezifischen Typ der Operation (Datei, Internet, etc.)"""
        user_lower = user_input.lower()
        
        # Internet-Operationen
        if any(word in user_lower for word in ['hole inhalt von', 'fetch', 'webseite', 'url', 'internet', 'surfe', 'besuche']):
            return 'fetch_url'

        # Dateisystem-Operationen
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
        
        return 'generic_chat'

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

            # Erkenne spezifischen Typ der Operation
            operation_type = self.detect_operation_type(last_user_message)
            expected_tool_operation = operation_type != 'generic_chat'

            print(f"🔍 Erkannt: {operation_type}, Tool-Op erwartet: {expected_tool_operation}")

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
            self.debug_claude_response(response, expected_tool_operation, tools)

            if self.stop_flag.is_set():
                return

            # 🔄 SMART RETRY: Spezifische Retry-Strategien
            if (not response["tool_calls"] and expected_tool_operation and tools):

                self.status_update_signal.emit("🔄 Keine Tools verwendet - Smart Retry...", "yellow")

                # Wähle spezifischen Retry-Prompt
                if operation_type == 'create_weekday_files':
                    retry_prompt = self.create_weekday_files_prompt()
                    system_prompt_for_retry = FILE_AGENT_PROMPT
                elif operation_type == 'fetch_url':
                    # Extrahiere URL aus der letzten Benutzernachricht für den Retry-Prompt
                    import re
                    url_match = re.search(r'(https?://[^\s]+)', last_user_message)
                    url_to_fetch = url_match.group(0) if url_match else "https://example.com" # Fallback
                    retry_prompt = self.force_internet_operation_prompt('fetch_url', url_to_fetch)
                    system_prompt_for_retry = INTERNET_AGENT_PROMPT
                else:
                    retry_prompt = self.create_retry_prompt(last_user_message)
                    system_prompt_for_retry = FILE_AGENT_PROMPT # Default for file ops

                retry_messages = context_messages + [{
                    "role": "user", 
                    "content": retry_prompt
                }]

                # Zweiter Versuch mit sehr direktem Prompt
                print(f"🔄 RETRY mit spezifischem Prompt für: {operation_type}")
                response = self.claude.send_message_with_tools(retry_messages, tools, system_prompt=system_prompt_for_retry)

                # Debug der Retry-Response
                print("🔄 RETRY Response:")
                self.debug_claude_response(response, expected_tool_operation, tools)

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
    
    # OpenAI API key is used by Whisper for transcription
    if not openai.api_key:
        missing_keys.append("OPENAI_API_KEY (erforderlich für Whisper)")
    
    # Check for at least one LLM API key
    if not CLAUDE_API_KEY and not OPENROUTER_API_KEY:
        missing_keys.append("CLAUDE_API_KEY oder OPENROUTER_API_KEY (mindestens einer erforderlich)")
    
    if not ELEVENLABS_API_KEY:
        missing_keys.append("ELEVENLABS_API_KEY (optional für TTS)")
    
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
