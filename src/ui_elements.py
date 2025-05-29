from PyQt5 import QtWidgets, QtGui, QtCore
import datetime
import math

class LoadingSpinner(QtWidgets.QWidget):
    """Ein Lade-Spinner mit wandernden Punkten."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50) # Fixed size for the spinner
        self.dot_count = 4
        self.current_angle = 0
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.dot_radius = 4
        self.spinner_radius = 15
        self.animation_speed = 100 # ms per frame
        self.hide() # Start hidden

    def start_animation(self):
        self.show()
        self.timer.start(self.animation_speed)

    def stop_animation(self):
        self.timer.stop()
        self.hide()
        self.current_angle = 0 # Reset angle

    def update_animation(self):
        self.current_angle = (self.current_angle + 10) % 360 # Rotate by 10 degrees
        self.update() # Request repaint

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        center_x = self.width() / 2
        center_y = self.height() / 2
        
        painter.setBrush(QtGui.QColor("#0d7377")) # Dot color
        painter.setPen(QtCore.Qt.NoPen)
        
        for i in range(self.dot_count):
            angle_offset = (360 / self.dot_count) * i
            angle_rad = math.radians(self.current_angle + angle_offset)
            
            x = center_x + self.spinner_radius * math.cos(angle_rad)
            y = center_y + self.spinner_radius * math.sin(angle_rad)
            
            painter.drawEllipse(QtCore.QPointF(x, y), self.dot_radius, self.dot_radius)

class StatusWindow(QtWidgets.QWidget):
    """Haupt-UI-Fenster der Anwendung"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎤 Voice Chat mit Claude")
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint | # Keep on top
            QtCore.Qt.WindowMinimizeButtonHint | # Keep minimize button
            QtCore.Qt.WindowMaximizeButtonHint | # Keep maximize button
            QtCore.Qt.WindowCloseButtonHint | # Keep close button
            QtCore.Qt.WindowSystemMenuHint # Keep system menu
        )
        self.setGeometry(100, 100, 800, 600) # Increased initial size, now resizable
        self.setup_ui()
        self.setup_keyboard()
        self.input_field.setFocus() # Set initial focus to the input field

    def setup_ui(self):
        """Erstellt die Benutzeroberfläche"""
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11pt;
            }
            QLabel {
                padding: 5px;
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 10px;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #0d7377;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #14a085;
            }
            QPushButton:pressed {
                background-color: #0a5d61;
            }
        """)

        layout = QtWidgets.QVBoxLayout()
        
        # Status-Anzeige und Spinner in einem horizontalen Layout
        status_layout = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QTextEdit("🟢 Bereit - Leertaste halten zum Sprechen")
        self.status_label.setReadOnly(True)
        self.status_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
        self.status_label.setFixedHeight(50) # Fixed height for status bar
        status_layout.addWidget(self.status_label)
        
        self.loading_spinner = LoadingSpinner(self)
        status_layout.addWidget(self.loading_spinner)
        
        layout.addLayout(status_layout)
        
        # Chat-Verlauf
        chat_label = QtWidgets.QLabel("Chat-Verlauf:")
        layout.addWidget(chat_label)
        
        self.chat_display = QtWidgets.QTextEdit()
        # Removed setMaximumHeight to allow chat display to expand with window
        layout.addWidget(self.chat_display)

        # Input field for manual text entry
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("Nachricht eingeben oder Leertaste halten zum Sprechen...")
        self.input_field.returnPressed.connect(self._on_send_button_clicked) # Send on Enter key
        self.input_field.installEventFilter(self) # Install event filter on input field
        layout.addWidget(self.input_field)

        # Send and Stop buttons
        send_stop_button_layout = QtWidgets.QHBoxLayout()
        self.send_button = QtWidgets.QPushButton("Senden")
        self.send_button.clicked.connect(self._on_send_button_clicked)
        send_stop_button_layout.addWidget(self.send_button)

        self.stop_button = QtWidgets.QPushButton("🛑 Stopp")
        self.stop_button.clicked.connect(self.stop_requested)
        self.stop_button.setEnabled(False) # Initially disabled
        send_stop_button_layout.addWidget(self.stop_button)
        
        send_stop_button_layout.addStretch(1) # Push buttons to the right
        layout.addLayout(send_stop_button_layout)
        
        # Other Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.new_session_btn = QtWidgets.QPushButton("✨ Neu")
        self.new_session_btn.clicked.connect(self.new_session_requested)
        button_layout.addWidget(self.new_session_btn)

        self.save_session_btn = QtWidgets.QPushButton("💾 Speichern...")
        self.save_session_btn.clicked.connect(self.save_session_requested)
        button_layout.addWidget(self.save_session_btn)

        self.load_session_btn = QtWidgets.QPushButton("📂 Laden...")
        self.load_session_btn.clicked.connect(self.load_session_requested)
        button_layout.addWidget(self.load_session_btn)

        self.export_chat_btn = QtWidgets.QPushButton("📄 Chat exportieren")
        self.export_chat_btn.clicked.connect(self.export_chat_requested)
        button_layout.addWidget(self.export_chat_btn)
        
        self.clear_btn = QtWidgets.QPushButton("🗑️ Aktuelle Sitzung löschen")
        self.clear_btn.clicked.connect(self._on_clear_button_clicked) # Connect to new handler method
        button_layout.addWidget(self.clear_btn)
        
        # Removed minimize and close buttons as per user request
        # self.minimize_btn = QtWidgets.QPushButton("📱 Minimieren")
        # self.minimize_btn.clicked.connect(self.hide)
        # button_layout.addWidget(self.minimize_btn)
        
        # self.close_btn = QtWidgets.QPushButton("❌ Schliessen")
        # self.close_btn.clicked.connect(QtWidgets.qApp.quit)
        # button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def setup_keyboard(self):
        """Richtet Tastatur-Events ein"""
        self.f3_pressed = False
        # self.grabKeyboard() # Removed: No longer needed with event filter

    def eventFilter(self, obj, event):
        """Event Filter to intercept key presses on the input field."""
        if obj is self.input_field and event.type() in [QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease]:
            if event.key() == QtCore.Qt.Key_Space:
                # Allow space to be entered into the input field
                return False
            # Allow F3 key events to propagate to the main window's keyPressEvent
            # This ensures that F3 can be used for recording even when the input field has focus.
            # The f3_pressed flag will be handled by the main window's keyPressEvent/keyReleaseEvent.
        return super().eventFilter(obj, event) # For other events, pass to base class

    def set_status(self, text, color="white"):
        """Setzt Status-Text"""
        color_map = {
            "green": "🟢",
            "red": "🔴", 
            "yellow": "🟡",
            "blue": "🔵"
        }
        
        if color in color_map:
            text = f"{color_map[color]} {text}"
        
        # For QTextEdit, use setHtml or setPlainText and then set alignment
        self.status_label.setHtml(f"<div align='center'>{text}</div>")
        
        # Control spinner based on status color
        if color == "blue":
            self.loading_spinner.start_animation()
        else:
            self.loading_spinner.stop_animation()

    def add_chat_message(self, role, message):
        """Fügt Nachricht zum Chat-Display hinzu"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if role == "user":
            prefix = "🧑 Du:"
            color = "#4CAF50"
        else:
            prefix = "🤖 Claude:"
            color = "#2196F3"
        
        # Formatierte Nachricht
        formatted_msg = f"<div style='margin: 5px 0; padding: 8px; background-color: #333; border-left: 3px solid {color}; border-radius: 3px;'>"
        formatted_msg += f"<b style='color: {color};'>[{timestamp}] {prefix}</b><br>"
        formatted_msg += f"<span style='color: #ffffff;'>{message}</span>"
        formatted_msg += "</div>"
        
        self.chat_display.append(formatted_msg)
        
        # Auto-scroll
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.chat_display.setTextCursor(cursor)

    def clear_chat_display(self):
        """Löscht Chat-Anzeige"""
        self.chat_display.clear()

    # Add new signals to StatusWindow
    new_session_requested = QtCore.pyqtSignal()
    save_session_requested = QtCore.pyqtSignal()
    load_session_requested = QtCore.pyqtSignal()
    export_chat_requested = QtCore.pyqtSignal()
    clear_chat_requested = QtCore.pyqtSignal()
    send_message_requested = QtCore.pyqtSignal(str)
    stop_requested = QtCore.pyqtSignal() # New signal for stopping processes

    def enable_send_button(self):
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)

    def disable_send_button(self):
        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)

    def enable_stop_button(self):
        self.stop_button.setEnabled(True)

    def disable_stop_button(self):
        self.stop_button.setEnabled(False)

    def _on_clear_button_clicked(self):
        """Handler for clear button click, emits clear_chat_requested signal."""
        self.clear_chat_requested.emit()

    def _on_send_button_clicked(self):
        """Handler for send button click or Enter key press in input field."""
        message = self.input_field.text().strip()
        if message:
            self.send_message_requested.emit(message)
            self.input_field.clear() # Clear input field after sending

    def keyPressEvent(self, event):
        """Tastendruck-Event (Hauptfenster)"""
        if event.key() == QtCore.Qt.Key_F3 and not event.isAutoRepeat():
            self.f3_pressed = True
        super().keyPressEvent(event) # Pass other key events to base class

    def keyReleaseEvent(self, event):
        """Tasten-Loslassen-Event (Hauptfenster)"""
        if event.key() == QtCore.Qt.Key_F3 and not event.isAutoRepeat():
            self.f3_pressed = False
        super().keyReleaseEvent(event) # Pass other key events to base class

    def set_input_text(self, text):
        """Sets the text in the input field."""
        self.input_field.setText(text)
        self.input_field.setFocus() # Set focus to the input field after setting text
        self.input_field.selectAll() # Select all text for easy editing/overwriting
