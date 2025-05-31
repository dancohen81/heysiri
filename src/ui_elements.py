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

class ChatDisplay(QtWidgets.QTextBrowser):
    """Custom QTextEdit to handle context menu for message editing."""
    edit_message_requested = QtCore.pyqtSignal(str, str) # Signal for editing a message (message_id, content)
    branch_icon_clicked = QtCore.pyqtSignal(str) # Signal for clicking a branch icon

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True) # Default to read-only
        self.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard | QtCore.Qt.LinksAccessibleByMouse) # Enable link interaction
        self.setOpenLinks(False) # Prevent QTextEdit from opening links automatically
        self.anchorClicked.connect(self._handle_link_click) # Connect custom link handler
        # self.message_blocks = [] # No longer needed, display_messages will rebuild

    def _add_single_message_to_display(self, role, message, message_id, font_size, is_branch_point=False, is_active_branch_head=False):
        """Fügt eine einzelne Nachricht zum Chat-Display hinzu."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if role == "user":
            prefix = "🧑 Du:"
            color = "#4CAF50"
            edit_button_html = f"<a href='edit://{message_id}' style='color: #0d7377; text-decoration: none; font-size: {font_size * 0.8}pt; margin-left: 10px;'>✏️ Bearbeiten</a>"
        else:
            prefix = "🤖 Claude:"
            color = "#2196F3"
            edit_button_html = ""
        
        branch_icons_html = ""
        if is_branch_point:
            # Branch icon - make it clickable to switch to this branch
            branch_icons_html = f"<a href='branch://{message_id}' style='color: #0d7377; text-decoration: none; font-size: {font_size * 0.8}pt; margin-left: 10px;'>🌿</a>"
            if is_active_branch_head:
                branch_icons_html += f"<span style='color: #14a085; font-size: {font_size * 0.8}pt;'> (aktiv)</span>" # Active branch indicator

        formatted_msg = f"<div data-message-id='{message_id}' style='margin: 5px 0; padding: 8px; background-color: #333; border-left: 3px solid {color}; border-radius: 3px;'>"
        formatted_msg += f"<b style='color: {color};'>[{timestamp}] {prefix}</b>{edit_button_html}{branch_icons_html}<br>"
        formatted_msg += f"<span style='color: #ffffff; font-size: {font_size}pt;'>{message}</span>"
        formatted_msg += "</div>"
        
        self.append(formatted_msg)
        
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.setTextCursor(cursor)

    def display_messages(self, messages: list, current_branch_head_id: str, all_messages_dict: dict, font_size: int):
        """Löscht das aktuelle Display und zeigt die Nachrichten des gegebenen Zweigs an."""
        super().clear() # Clear the QTextBrowser content

        # Determine which messages are branch points
        # A message is a branch point if its ID is a parent_id for more than one message,
        # or if it's a parent_id for any message that is NOT in the current branch.
        
        # Collect all parent_ids that have multiple children
        parent_child_counts = {}
        for msg_id, msg_obj in all_messages_dict.items():
            parent_id = msg_obj.get('parent_id')
            if parent_id:
                parent_child_counts.setdefault(parent_id, []).append(msg_id)
        
        branch_points = set()
        for parent_id, children_ids in parent_child_counts.items():
            if len(children_ids) > 1:
                branch_points.add(parent_id)
            else:
                # Check if the single child is NOT in the current branch (meaning it's a divergent branch)
                # This requires knowing the full path of the current branch
                current_branch_ids = {msg['id'] for msg in messages}
                if children_ids[0] not in current_branch_ids:
                    branch_points.add(parent_id)

        for msg in messages:
            msg_id = msg["id"]
            role = msg["role"]
            content = msg["content"]
            
            is_branch_point = msg_id in branch_points
            is_active_branch_head = (msg_id == current_branch_head_id)

            self._add_single_message_to_display(role, content, msg_id, font_size, is_branch_point, is_active_branch_head)

    def clear(self):
        """Löscht Chat-Anzeige."""
        super().clear()

    def _handle_link_click(self, url: QtCore.QUrl):
        """Handles clicks on custom links within the chat display."""
        if url.scheme() == "edit":
            message_id = url.host()
            # This requires re-fetching message content, as message_blocks is removed
            # AppLogic will need to provide the content for editing.
            self.edit_message_requested.emit(message_id, "") # Content will be fetched by AppLogic
        elif url.scheme() == "branch":
            message_id = url.host()
            self.branch_icon_clicked.emit(message_id)
        else:
            QtGui.QDesktopServices.openUrl(url)

    def contextMenuEvent(self, event):
        """Handles right-click context menu events."""
        # Context menu for editing is now deprecated in favor of inline button
        # super().contextMenuEvent(event) # Call base class to show default menu if any
        pass # Disable context menu for now

class StatusWindow(QtWidgets.QWidget):
    """Haupt-UI-Fenster der Anwendung"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎤 Voice Chat mit Claude")
        self.setWindowFlags(
            # QtCore.Qt.WindowStaysOnTopHint | # Removed: Keep on top
            QtCore.Qt.WindowMinimizeButtonHint | # Keep minimize button
            QtCore.Qt.WindowMaximizeButtonHint | # Keep maximize button
            QtCore.Qt.WindowCloseButtonHint | # Keep close button
            QtCore.Qt.WindowSystemMenuHint # Keep system menu
        )
        self.setGeometry(100, 100, 800, 600) # Increased initial size, now resizable
        
        # Initialize attributes that might be accessed early
        self.status_label = None 
        self.loading_spinner = None
        self.chat_title_label = None
        self.chat_display = None
        self.input_field = None
        self.stop_button = None
        self.pause_button = None
        self.send_button = None
        self.new_session_btn = None
        self.save_session_btn = None
        self.load_session_btn = None
        self.export_chat_btn = None
        self.branches_btn = None
        self.clear_btn = None
        self.current_font_size = 11 # Initialize with default font size from stylesheet

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
        
        # Chat-Verlauf Titel
        self.chat_title_label = QtWidgets.QLabel("Chat-Verlauf:") # Make it an instance variable
        layout.addWidget(self.chat_title_label)
        
        self.chat_display = ChatDisplay(self) # Use custom ChatDisplay
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
        
        self.stop_button = QtWidgets.QPushButton("🛑 Stopp")
        self.stop_button.clicked.connect(self.stop_requested)
        self.stop_button.setEnabled(False) # Initially disabled
        send_stop_button_layout.addWidget(self.stop_button)

        self.pause_button = QtWidgets.QPushButton("⏯️ Pause/Resume")
        self.pause_button.clicked.connect(self.pause_audio_requested)
        self.pause_button.setEnabled(False) # Initially disabled
        send_stop_button_layout.addWidget(self.pause_button)

        send_stop_button_layout.addStretch(1) # Push the send button to the right

        self.send_button = QtWidgets.QPushButton("Senden")
        self.send_button.clicked.connect(self._on_send_button_clicked)
        send_stop_button_layout.addWidget(self.send_button)
        
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
        
        self.branches_btn = QtWidgets.QPushButton("🌿 Branches")
        self.branches_btn.clicked.connect(self.show_branches_requested)
        button_layout.addWidget(self.branches_btn)

        self.clear_btn = QtWidgets.QPushButton("🗑️ Aktuelle Sitzung löschen")
        self.clear_btn.clicked.connect(self._on_clear_button_clicked) # Connect to new handler method
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def setup_keyboard(self):
        """Richtet Tastatur-Events ein"""
        self.f3_pressed = False
        self.f4_pressed = False # Initialize f4_pressed
        self.press_start_time = None # To track how long the F3 key is pressed
        self.feedback_given = False # To ensure feedback is given only once at 0.5s

    def eventFilter(self, obj, event):
        """Event Filter to intercept key presses on the input field."""
        if obj is self.input_field and event.type() in [QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease]:
            if event.key() == QtCore.Qt.Key_Space:
                # Allow space to be entered into the input field
                return False
        return super().eventFilter(obj, event) # For other events, pass to base class

    def set_status(self, text, color="white"):
        """Setzt Status-Text"""
        if self.status_label is None: # Add this check
            return # Do nothing if status_label is not yet initialized

        color_map = {
            "green": "🟢",
            "red": "🔴", 
            "yellow": "🟡",
            "blue": "🔵",
            "orange": "🟠" # New color for feedback
        }
        
        if color in color_map:
            text = f"{color_map[color]} {text}"
        
        self.status_label.setHtml(f"<div align='center'>{text}</div>")
        
        if color == "blue":
            if self.loading_spinner: # Add check for spinner too
                self.loading_spinner.start_animation()
        else:
            if self.loading_spinner: # Add check for spinner too
                self.loading_spinner.stop_animation()

    def clear_chat_display(self):
        """Löscht Chat-Anzeige"""
        self.chat_display.clear()
        self.set_chat_title("Chat-Verlauf:") # Reset title when chat is cleared

    def set_chat_title(self, title: str):
        """Setzt den Titel des Chat-Verlaufs"""
        self.chat_title_label.setText(f"Chat-Verlauf: <b>{title}</b>")

    # Add new signals to StatusWindow
    new_session_requested = QtCore.pyqtSignal()
    save_session_requested = QtCore.pyqtSignal()
    load_session_requested = QtCore.pyqtSignal()
    export_chat_requested = QtCore.pyqtSignal()
    clear_chat_requested = QtCore.pyqtSignal()
    send_message_requested = QtCore.pyqtSignal(str)
    stop_requested = QtCore.pyqtSignal() # New signal for stopping processes
    pause_audio_requested = QtCore.pyqtSignal() # New signal for pausing/resuming audio
    record_feedback_signal = QtCore.pyqtSignal(str, str) # New signal for record feedback
    edit_message_requested = QtCore.pyqtSignal(str, str)
    show_branches_requested = QtCore.pyqtSignal() # Signal to request branch heads from app_logic
    branch_selected_from_ui = QtCore.pyqtSignal(str) # Signal to notify app_logic of selected branch

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
        status_layout = QtWidgets.QHBoxLayout()
        send_stop_button_layout = QtWidgets.QHBoxLayout()
        button_layout = QtWidgets.QHBoxLayout()
        
        # Create all widgets first
        self.status_label = QtWidgets.QTextEdit("🟢 Bereit - Leertaste halten zum Sprechen")
        self.loading_spinner = LoadingSpinner(self)
        self.chat_title_label = QtWidgets.QLabel("Chat-Verlauf:")
        self.chat_display = ChatDisplay(self)
        self.input_field = QtWidgets.QLineEdit()
        self.stop_button = QtWidgets.QPushButton("🛑 Stopp")
        self.pause_button = QtWidgets.QPushButton("⏯️ Pause/Resume")
        self.send_button = QtWidgets.QPushButton("Senden")
        self.new_session_btn = QtWidgets.QPushButton("✨ Neu")
        self.save_session_btn = QtWidgets.QPushButton("💾 Speichern...")
        self.load_session_btn = QtWidgets.QPushButton("📂 Laden...")
        self.export_chat_btn = QtWidgets.QPushButton("📄 Chat exportieren")
        self.branches_btn = QtWidgets.QPushButton("🌿 Branches")
        self.clear_btn = QtWidgets.QPushButton("🗑️ Aktuelle Sitzung löschen")

        # Add widgets to layout
        self.status_label.setReadOnly(True)
        self.status_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
        self.status_label.setFixedHeight(50) # Fixed height for status bar
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.loading_spinner)
        layout.addLayout(status_layout)
        
        layout.addWidget(self.chat_title_label)
        layout.addWidget(self.chat_display)

        self.input_field.setPlaceholderText("Nachricht eingeben oder Leertaste halten zum Sprechen...")
        layout.addWidget(self.input_field)

        self.stop_button.setEnabled(False) # Initially disabled
        send_stop_button_layout.addWidget(self.stop_button)

        self.pause_button.setEnabled(False) # Initially disabled
        send_stop_button_layout.addWidget(self.pause_button)

        send_stop_button_layout.addStretch(1) # Push the send button to the right
        send_stop_button_layout.addWidget(self.send_button)
        layout.addLayout(send_stop_button_layout)
        
        button_layout.addWidget(self.new_session_btn)
        button_layout.addWidget(self.save_session_btn)
        button_layout.addWidget(self.load_session_btn)
        button_layout.addWidget(self.export_chat_btn)
        button_layout.addWidget(self.branches_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Now connect signals, with defensive checks
        if self.input_field is not None:
            self.input_field.returnPressed.connect(self._on_send_button_clicked)
            self.input_field.installEventFilter(self)
        else:
            print("DEBUG: input_field is None, cannot connect signals!")

        if self.stop_button is not None:
            self.stop_button.clicked.connect(self.stop_requested)
        else:
            print("DEBUG: stop_button is None, cannot connect signals!")

        if self.pause_button is not None:
            self.pause_button.clicked.connect(self.pause_audio_requested)
        else:
            print("DEBUG: pause_button is None, cannot connect signals!")

        if self.send_button is not None:
            self.send_button.clicked.connect(self._on_send_button_clicked)
        else:
            print("DEBUG: send_button is None, cannot connect signals!")
        
        if self.new_session_btn is not None:
            self.new_session_btn.clicked.connect(self.new_session_requested)
        else:
            print("DEBUG: new_session_btn is None, cannot connect signals!")

        if self.save_session_btn is not None:
            self.save_session_btn.clicked.connect(self.save_session_requested)
        else:
            print("DEBUG: save_session_btn is None, cannot connect signals!")

        if self.load_session_btn is not None:
            self.load_session_btn.clicked.connect(self.load_session_requested)
        else:
            print("DEBUG: load_session_btn is None, cannot connect signals!")

        if self.export_chat_btn is not None:
            self.export_chat_btn.clicked.connect(self.export_chat_requested)
        else:
            print("DEBUG: export_chat_btn is None, cannot connect signals!")
        
        if self.branches_btn is not None:
            self.branches_btn.clicked.connect(self._on_show_branches_button_clicked)
        else:
            print("DEBUG: branches_btn is None, cannot connect signals!")

        if self.clear_btn is not None:
            self.clear_btn.clicked.connect(self._on_clear_button_clicked)
        else:
            print("DEBUG: clear_btn is None, cannot connect signals!")

        if self.chat_display is not None: # Defensive check
            self.chat_display.edit_message_requested.connect(self.edit_message_requested.emit)
        else:
            print("DEBUG: self.chat_display is None before connecting signal in setup_ui!")

    def _on_show_branches_button_clicked(self):
        """Handler for the 'Branches' button click."""
        self.show_branches_requested.emit() # Emit signal to request branch heads

    def show_branch_selection_dialog(self, branch_heads: dict):
        """Shows the branch selection dialog with the given branch heads."""
        dialog = BranchSelectionDialog(branch_heads, self)
        dialog.branch_selected.connect(self._on_branch_selected)
        dialog.exec_() # Show as modal dialog

    def _on_branch_selected(self, message_id: str):
        """Handler for when a branch is selected in the dialog."""
        self.branch_selected_from_ui.emit(message_id) # Emit signal to app_logic

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

    def enable_pause_button(self):
        self.pause_button.setEnabled(True)

    def disable_pause_button(self):
        self.pause_button.setEnabled(False)

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
            self.press_start_time = QtCore.QDateTime.currentMSecsSinceEpoch() # Store start time in ms
            self.feedback_given = False
        elif event.key() == QtCore.Qt.Key_F4 and not event.isAutoRepeat(): # Handle F4 key press
            self.f4_pressed = True
        super().keyPressEvent(event) # Pass other key events to base class

    def keyReleaseEvent(self, event):
        """Tasten-Loslassen-Event (Hauptfenster)"""
        if event.key() == QtCore.Qt.Key_F3 and not event.isAutoRepeat():
            self.f3_pressed = False
        elif event.key() == QtCore.Qt.Key_F4 and not event.isAutoRepeat(): # Handle F4 key release
            self.f4_pressed = False
        super().keyReleaseEvent(event) # Pass other key events to base class

    def set_font_size(self, new_size):
        """Sets the font size of relevant UI elements to a specific value."""
        elements = [self.chat_display, self.status_label, self.input_field, self.chat_title_label]
        for element in elements:
            if element:
                font = element.font()
                # Ensure font size stays within reasonable limits
                if new_size > 5 and new_size < 31:
                    font.setPointSize(new_size)
                    element.setFont(font)
                    # For QTextEdit, also adjust the document's default font
                    if isinstance(element, QtWidgets.QTextEdit):
                        cursor = element.textCursor()
                        cursor.select(QtGui.QTextCursor.Document)
                        format = cursor.charFormat()
                        format.setFontPointSize(new_size)
                        cursor.mergeCharFormat(format)
                        cursor.select(QtGui.QTextCursor.Document) # Re-select to apply to whole document
                        element.setTextCursor(cursor)
        self.current_font_size = new_size # Store the new font size


    def keyPressEvent(self, event):
        """Tastendruck-Event (Hauptfenster)"""
        if event.key() == QtCore.Qt.Key_F3 and not event.isAutoRepeat():
            self.f3_pressed = True
            self.press_start_time = QtCore.QDateTime.currentMSecsSinceEpoch() # Store start time in ms
            self.feedback_given = False
        elif event.key() == QtCore.Qt.Key_F4 and not event.isAutoRepeat(): # Handle F4 key press
            self.f4_pressed = True
        elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_Equal: # Ctrl + '=' for zoom in
            current_size = self.chat_display.font().pointSize() # Get current size from one element
            self.set_font_size(current_size + 1) # Zoom in
        elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_Minus: # Ctrl + '-' for zoom out
            current_size = self.chat_display.font().pointSize() # Get current size from one element
            self.set_font_size(current_size - 1) # Zoom out
        super().keyPressEvent(event) # Pass other key events to base class

    def keyReleaseEvent(self, event):
        """Tasten-Loslassen-Event (Hauptfenster)"""
        if event.key() == QtCore.Qt.Key_F3 and not event.isAutoRepeat():
            self.f3_pressed = False
        elif event.key() == QtCore.Qt.Key_F4 and not event.isAutoRepeat(): # Handle F4 key release
            self.f4_pressed = False
        super().keyReleaseEvent(event) # Pass other key events to base class

    def set_input_text(self, text):
        """Sets the text in the input field."""
        self.input_field.setText(text)
        self.input_field.setFocus() # Set focus to the input field after setting text
        self.input_field.selectAll() # Select all text for easy editing/overwriting

class BranchSelectionDialog(QtWidgets.QDialog):
    """Dialog to display and select chat branches."""
    branch_selected = QtCore.pyqtSignal(str) # Emits the message_id of the selected branch head

    def __init__(self, branch_heads: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chat Branches")
        self.setGeometry(200, 200, 400, 300)
        self.setModal(True) # Make it a modal dialog

        self.branch_heads = branch_heads # {message_id: first_user_message_content}

        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel("Select a chat branch:")
        layout.addWidget(label)

        self.branch_list_widget = QtWidgets.QListWidget()
        self.branch_list_widget.itemDoubleClicked.connect(self._on_branch_double_clicked)
        layout.addWidget(self.branch_list_widget)

        # Populate the list widget
        for msg_id, content in self.branch_heads.items():
            item = QtWidgets.QListWidgetItem(content)
            item.setData(QtCore.Qt.UserRole, msg_id) # Store message_id in item data
            self.branch_list_widget.addItem(item)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_branch_double_clicked(self, item):
        selected_id = item.data(QtCore.Qt.UserRole)
        self.branch_selected.emit(selected_id)
        self.accept() # Close the dialog
    
    def accept(self):
        selected_item = self.branch_list_widget.currentItem()
        if selected_item:
            selected_id = selected_item.data(QtCore.Qt.UserRole)
            self.branch_selected.emit(selected_id)
        super().accept()
