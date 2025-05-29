import os
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
import openai
import winsound
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
        self.stop_flag = threading.Event() # Event to signal stopping processes

    def check_keyboard(self):
        """Prüft Tastatur-Status (Alt-Taste)"""
        if self.window.f3_pressed:
            if not self.is_recording:
                self.start_recording()
        else:
            if self.is_recording:
                self.stop_recording()

    def start_recording(self):
        """Startet Audio-Aufnahme"""
        try:
            # self.setIcon(self.icon_recording) # This will be handled by VoiceChatApp
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
            # self.setIcon(self.icon_idle) # This will be handled by VoiceChatApp
            
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
