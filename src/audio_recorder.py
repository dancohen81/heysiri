import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
import openai
import threading
from PyQt5 import QtCore, QtWidgets # Import QtWidgets for QInputDialog, QFileDialog, QMessageBox

from src.config import SAMPLERATE, AUDIO_FILENAME

class AudioRecorder(QtCore.QObject):
    """Handles audio recording, transcription, and related UI updates."""

    # Define signals for thread-safe UI updates
    status_update_signal = QtCore.pyqtSignal(str, str)
    chat_message_signal = QtCore.pyqtSignal(str, str)
    transcription_ready_signal = QtCore.pyqtSignal(str) # Signal to emit transcribed text

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.is_recording = False
        self.recording_data = []
        self.stream = None
        self.recording_start_time = None # To track the actual start of recording

        # Connect the record_feedback_signal from StatusWindow
        self.window.record_feedback_signal.connect(self.status_update_signal.emit)

    def check_keyboard(self):
        """Prüft Tastatur-Status (F3) und steuert Aufnahme basierend auf Haltedauer."""
        current_time = QtCore.QDateTime.currentMSecsSinceEpoch()

        if self.window.f3_pressed:
            if not self.is_recording:
                # F3 just pressed or held, but not yet recording
                if self.window.press_start_time is not None:
                    press_duration = (current_time - self.window.press_start_time) / 1000.0 # in seconds

                    if press_duration >= 1.0: # Minimum hold time to start recording
                        if not self.is_recording: # Double check to prevent multiple starts
                            self.start_recording()
                    elif press_duration >= 0.5 and not self.window.feedback_given:
                        # Provide feedback after 0.5 seconds of holding
                        self.window.record_feedback_signal.emit("🟠 Halten für Aufnahme...", "orange")
                        self.window.feedback_given = True
        else: # F3 is not pressed
            if self.is_recording:
                self.stop_recording()
            elif self.window.press_start_time is not None:
                # F3 was pressed but released before 1.0s
                press_duration = (current_time - self.window.press_start_time) / 1000.0
                if press_duration < 1.0:
                    self.window.record_feedback_signal.emit("🟡 Taste zu kurz gedrückt", "yellow")
                self.window.press_start_time = None # Reset press time
                self.window.feedback_given = False # Reset feedback flag

    def start_recording(self):
        """Startet Audio-Aufnahme"""
        try:
            self.recording_data = []
            
            self.stream = sd.InputStream(
                samplerate=SAMPLERATE, 
                channels=1, 
                dtype='int16', 
                callback=self.audio_callback
            )
            self.stream.start()
            self.is_recording = True
            self.recording_start_time = QtCore.QDateTime.currentMSecsSinceEpoch() # Actual recording start time
            self.window.grabKeyboard() # Grab keyboard when recording starts
            self.window.setFocus() # Ensure main window has focus for spacebar
            
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
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            self.is_recording = False
            self.recording_start_time = None # Reset recording start time
            self.window.releaseKeyboard() # Release keyboard when recording stops
            self.window.input_field.setFocus() # Return focus to input field
            
            self.status_update_signal.emit("🔄 Verarbeite Audio...", "yellow")
            self.window.disable_send_button() # Keep send button disabled during processing
            self.window.enable_stop_button() # Keep stop button enabled during processing
            
            # Verarbeitung in separatem Thread
            threading.Thread(target=self.process_audio_and_chat, daemon=True).start()
            
        except Exception as e:
            self.status_update_signal.emit(f"Stop-Fehler: {e}", "red")
            self.window.enable_send_button() # Re-enable on error
            self.window.disable_stop_button() # Disable stop on error

    def audio_callback(self, indata, frames, time, status):
        """Callback für Audio-Stream"""
        if status:
            print(f"Audio Status: {status}")
        self.recording_data.append(indata.copy())

    def process_audio_and_chat(self):
        """Verarbeitet Audio und führt Chat durch"""
        # The stop_flag is managed by app_logic.py, so we don't clear it here.
        # We need to access the stop_flag from the app_logic.py instance.
        # For now, I'll assume app_logic will pass its stop_flag to AudioRecorder if needed,
        # or AudioRecorder will emit a signal that app_logic listens to for stopping.
        # Given the current structure, app_logic.py calls this method, so it should manage the stop_flag.
        # I will remove the stop_flag.clear() and stop_flag.is_set() checks here,
        # as they are handled by the calling context (VoiceChatApp).

        try:
            # 1. Audio-Daten prüfen
            if not self.recording_data:
                self.status_update_signal.emit("Keine Audio-Daten aufgenommen", "yellow")
                self.window.enable_send_button() # Re-enable send button
                self.window.disable_stop_button() # Disable stop button
                return

            # 2. Audio zu WAV speichern
            self.status_update_signal.emit("💾 Speichere Audio...", "blue")
            # if self.stop_flag.is_set(): return # Removed, handled by app_logic
            audio_data = np.concatenate(self.recording_data, axis=0)
            wavfile.write(AUDIO_FILENAME, SAMPLERATE, audio_data)

            # 3. Whisper Transkription
            self.status_update_signal.emit("🎯 Transkribiere mit Whisper...", "blue")
            # if self.stop_flag.is_set(): return # Removed, handled by app_logic
            
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
            
            self.transcription_ready_signal.emit(user_text) # Emit signal with transcribed text

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
