from PyQt5 import QtWidgets, QtCore, QtGui
import src.config as config
from src.mcp_client import MCPManager # Assuming MCPManager is accessible

class SettingsWindow(QtWidgets.QDialog):
    def __init__(self, mcp_manager: MCPManager, parent=None):
        super().__init__(parent)
        self.mcp_manager = mcp_manager
        self.setWindowTitle("Einstellungen")
        self.setGeometry(100, 100, 800, 600)
        
        # Set a dark stylesheet for the dialog and its children
        self.setStyleSheet("""
            QDialog {
                background-color: #2c2c2c; /* Dark background for the dialog */
                color: #f0f0f0; /* Light text color */
            }
            QTabWidget::pane { /* The tab widget frame */
                border: 1px solid #444;
                background-color: #2c2c2c;
            }
            QTabBar::tab {
                background: #3a3a3a; /* Darker background for inactive tabs */
                color: #f0f0f0;
                border: 1px solid #444;
                border-bottom-color: #2c2c2c; /* Same as pane color */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 8ex;
                padding: 2px;
            }
            QTabBar::tab:selected {
                background: #2c2c2c; /* Same as pane color for selected tab */
                border-bottom-color: #2c2c2c; /* Selected tab blends with pane */
            }
            QGroupBox {
                background-color: #2c2c2c;
                color: #f0f0f0;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 1ex; /* Space for the title */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left; /* Position at top left */
                padding: 0 3px;
                background-color: #3a3a3a; /* Slightly lighter background for title */
                border-radius: 2px;
            }
            QTextEdit {
                background-color: #3a3a3a; /* Dark background for text editors */
                color: #f0f0f0; /* Light text color */
                border: 1px solid #555;
                border-radius: 3px;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: #f0f0f0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px;
            }
            QDoubleSpinBox {
                background-color: #3a3a3a;
                color: #f0f0f0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px;
            }
            QCheckBox {
                color: #f0f0f0;
            }
            QPushButton {
                background-color: #007bff; /* Blue button */
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QDialogButtonBox QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #0056b3;
            }
            QTableWidget {
                background-color: #3a3a3a;
                color: #f0f0f0;
                border: 1px solid #555;
                gridline-color: #555;
            }
            QHeaderView::section {
                background-color: #444;
                color: #f0f0f0;
                padding: 4px;
                border: 1px solid #555;
            }
            QTableWidget::item {
                padding: 4px;
            }
        """)
        
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        
        tab_widget = QtWidgets.QTabWidget()
        main_layout.addWidget(tab_widget)

        # LLM Settings Tab
        llm_tab = QtWidgets.QWidget()
        self.llm_layout = QtWidgets.QVBoxLayout(llm_tab)
        tab_widget.addTab(llm_tab, "LLM Einstellungen")
        self.setup_llm_tab()

        # Prompts Tab
        prompts_tab = QtWidgets.QWidget()
        self.prompts_layout = QtWidgets.QVBoxLayout(prompts_tab)
        tab_widget.addTab(prompts_tab, "System Prompts")
        self.setup_prompts_tab()

        # MCP Tab
        mcp_tab = QtWidgets.QWidget()
        self.mcp_layout = QtWidgets.QVBoxLayout(mcp_tab)
        tab_widget.addTab(mcp_tab, "MCP Verwaltung")
        self.setup_mcp_tab()

        # Save/Close Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Close
        )
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def setup_prompts_tab(self):
        self.prompt_keys = ["CHAT_AGENT_PROMPT", "FILE_AGENT_PROMPT", "INTERNET_AGENT_PROMPT", "SYSTEM_PROMPT"]
        self.prompt_display_names = {
            "CHAT_AGENT_PROMPT": "Chat Agent Prompt",
            "FILE_AGENT_PROMPT": "File Agent Prompt",
            "INTERNET_AGENT_PROMPT": "Internet Agent Prompt",
            "SYSTEM_PROMPT": "Fallback System Prompt"
        }

        # Dropdown for prompt selection
        prompt_selection_layout = QtWidgets.QHBoxLayout()
        prompt_selection_layout.addWidget(QtWidgets.QLabel("Prompt auswählen:"))
        self.prompt_selector = QtWidgets.QComboBox()
        for key in self.prompt_keys:
            self.prompt_selector.addItem(self.prompt_display_names[key], key)
        prompt_selection_layout.addWidget(self.prompt_selector)
        self.prompts_layout.addLayout(prompt_selection_layout)

        # Single QTextEdit for displaying/editing the selected prompt
        self.current_prompt_editor = QtWidgets.QTextEdit()
        self.current_prompt_editor.setMinimumHeight(300)
        self.prompts_layout.addWidget(self.current_prompt_editor)

        # Connect dropdown to update editor
        self.prompt_selector.currentIndexChanged.connect(self.display_selected_prompt)

    def setup_mcp_tab(self):
        self.mcp_checkboxes = {}
        self.mcp_status_labels = {}

        self.mcp_table = QtWidgets.QTableWidget()
        self.mcp_table.setColumnCount(4)
        self.mcp_table.setHorizontalHeaderLabels(["Server ID", "Pfad", "Enabled", "Status"])
        self.mcp_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.mcp_layout.addWidget(self.mcp_table)

        refresh_button = QtWidgets.QPushButton("Status aktualisieren")
        refresh_button.clicked.connect(self.update_mcp_status_display)
        self.mcp_layout.addWidget(refresh_button)

    def setup_llm_tab(self):
        llm_group_box = QtWidgets.QGroupBox("Aktiver LLM")
        llm_group_layout = QtWidgets.QFormLayout(llm_group_box)

        self.llm_selector = QtWidgets.QComboBox()
        self.llm_selector.addItem("Claude", "claude")
        self.llm_selector.addItem("OpenRouter", "openrouter")
        llm_group_layout.addRow("LLM auswählen:", self.llm_selector)

        self.openrouter_key_input = QtWidgets.QLineEdit()
        self.openrouter_key_input.setPlaceholderText("Dein OpenRouter API Key")
        llm_group_layout.addRow("OpenRouter API Key:", self.openrouter_key_input)

        self.llm_layout.addWidget(llm_group_box)
        self.llm_layout.addStretch(1) # Push content to top

    def load_settings(self):
        # Load LLM Settings
        # Find the index of the item with the matching user data
        index = self.llm_selector.findData(config.ACTIVE_LLM)
        if index != -1:
            self.llm_selector.setCurrentIndex(index)
        self.openrouter_key_input.setText(config.OPENROUTER_API_KEY)

        # Load Prompts
        # Store current prompts in a temporary dict for editing
        self._current_prompts_data = {
            "CHAT_AGENT_PROMPT": config.CHAT_AGENT_PROMPT,
            "FILE_AGENT_PROMPT": config.FILE_AGENT_PROMPT,
            "INTERNET_AGENT_PROMPT": config.INTERNET_AGENT_PROMPT,
            "SYSTEM_PROMPT": config.SYSTEM_PROMPT
        }
        self.display_selected_prompt() # Display the first prompt

        # Load MCP Status
        self.update_mcp_status_display()

    def display_selected_prompt(self):
        selected_key = self.prompt_selector.currentData()
        self.current_prompt_editor.setPlainText(self._current_prompts_data.get(selected_key, ""))

    def update_mcp_status_display(self):
        mcp_status = self.mcp_manager.get_mcp_status()
        self.mcp_table.setRowCount(len(mcp_status))
        
        row = 0
        for server_id, status_info in mcp_status.items():
            # Server ID
            self.mcp_table.setItem(row, 0, QtWidgets.QTableWidgetItem(server_id))
            
            # Path
            self.mcp_table.setItem(row, 1, QtWidgets.QTableWidgetItem(status_info.get("path", "N/A")))
            
            # Enabled Checkbox
            checkbox_item = QtWidgets.QTableWidgetItem()
            checkbox_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox_item.setCheckState(QtCore.Qt.Checked if status_info.get("enabled") else QtCore.Qt.Unchecked)
            self.mcp_table.setItem(row, 2, checkbox_item)
            self.mcp_checkboxes[server_id] = checkbox_item # Store reference to update later

            # Running Status
            status_text = "Läuft" if status_info.get("running") else "Gestoppt"
            status_item = QtWidgets.QTableWidgetItem(status_text)
            status_item.setForeground(QtGui.QColor("green") if status_info.get("running") else QtGui.QColor("red"))
            self.mcp_table.setItem(row, 3, status_item)
            self.mcp_status_labels[server_id] = status_item # Store reference

            row += 1

    def save_settings(self):
        # Save LLM Settings
        selected_llm = self.llm_selector.currentData()
        openrouter_key = self.openrouter_key_input.text()
        
        # This is a simplified way to save. In a real app, you'd write to a config file.
        # For now, we'll just update the in-memory config and rely on app_logic to re-initialize.
        config.ACTIVE_LLM = selected_llm
        config.OPENROUTER_API_KEY = openrouter_key # This won't persist unless written to file
        
        # Save Prompts
        # Update the currently displayed prompt in our temporary data
        selected_key = self.prompt_selector.currentData()
        self._current_prompts_data[selected_key] = self.current_prompt_editor.toPlainText()
        
        # Save all prompts from the temporary data to file
        config.save_prompts(self._current_prompts_data)

        # Save MCP Enabled State
        changes_made_mcp = False
        for server_id, checkbox_item in self.mcp_checkboxes.items():
            current_enabled = config.MCP_SERVER_CONFIG.get(server_id, {}).get("enabled", False)
            new_enabled = checkbox_item.checkState() == QtCore.Qt.Checked
            
            if current_enabled != new_enabled:
                print(f"MCP Server '{server_id}' enabled state changed to {new_enabled}. "
                      "Application restart might be required for full effect.")
                config.MCP_SERVER_CONFIG[server_id]["enabled"] = new_enabled
                changes_made_mcp = True
        
        # Inform user about changes and potential restart
        if changes_made_mcp or (selected_llm != config.ACTIVE_LLM) or (openrouter_key != config.OPENROUTER_API_KEY): # Check if LLM settings changed
            QtWidgets.QMessageBox.information(self, "Einstellungen gespeichert", 
                                              "Einstellungen wurden gespeichert. "
                                              "Einige Änderungen erfordern möglicherweise einen Neustart der Anwendung.")
        else:
            QtWidgets.QMessageBox.information(self, "Einstellungen gespeichert", 
                                              "Einstellungen wurden gespeichert.")
        
        self.accept() # Close the dialog
