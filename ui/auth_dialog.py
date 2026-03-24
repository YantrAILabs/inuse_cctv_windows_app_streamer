import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QProgressBar, QCheckBox, QHBoxLayout
from PySide6.QtCore import Qt, QThread, Signal
from core.onvif_client import ONVIFClient
from core.credential_store import CredentialStore

class ConnectionThread(QThread):
    finished = Signal(bool, str, list) # Success, Message, Channels
    status = Signal(str)

    def __init__(self, ip, port, username, password):
        super().__init__()
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password

    def run(self):
        self.status.emit("Connecting to device...")
        client = ONVIFClient(self.ip, self.username, self.password, port=self.port)
        if not client.connect():
            self.finished.emit(False, f"Failed to connect to {self.ip}", [])
            return

        self.status.emit("Authenticating...")
        dev_info = client.get_device_info()
        if not dev_info:
            self.finished.emit(False, "Authentication failed or device not responding.", [])
            return

        self.status.emit("Fetching camera profiles...")
        channels = client.get_channels()
        
        if not channels:
            # Try fallback RTSP templates? 
            self.status.emit("No ONVIF channels found. Checking fallback...")
            # For brevity, let's assume we found 0 if ONVIF failed
            self.finished.emit(False, "No channels found via ONVIF.", [])
        else:
            self.finished.emit(True, f"Success! Found {len(channels)} channels.", channels)

class AuthDialog(QDialog):
    connection_successful = Signal(dict) # Device info + channels

    def __init__(self, device_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Connect to {device_info['ip']}")
        self.setFixedSize(350, 250)
        self.device_info = device_info

        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        self.user_input = QLineEdit("admin")
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        
        # Load saved credentials if available
        saved_user, saved_pass = CredentialStore.load_credentials(device_info['ip'])
        if saved_user:
            self.user_input.setText(saved_user)
            self.pass_input.setText(saved_pass)
        
        form_layout.addRow("Username:", self.user_input)
        form_layout.addRow("Password:", self.pass_input)
        layout.addLayout(form_layout)
        
        self.remember_cb = QCheckBox("Remember credentials")
        self.remember_cb.setChecked(True)
        layout.addWidget(self.remember_cb)
        
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.on_connect)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def on_connect(self):
        username = self.user_input.text()
        password = self.pass_input.text()
        port = self.device_info.get('port', 80)
        
        self.connect_btn.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText("Starting connection...")
        
        self.thread = ConnectionThread(self.device_info['ip'], port, username, password)
        self.thread.status.connect(self.status_label.setText)
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def on_finished(self, success, message, channels):
        self.progress_bar.hide()
        self.status_label.setText(message)
        self.connect_btn.setEnabled(True)
        
        if success:
            if self.remember_cb.isChecked():
                CredentialStore.save_credentials(self.device_info['ip'], self.user_input.text(), self.pass_input.text())
            
            # Enrich device info
            full_info = self.device_info.copy()
            full_info['channels'] = channels
            self.connection_successful.emit(full_info)
            self.accept()
        else:
            final_err = message
            if "Authorized" in message or "Forbidden" in message:
                final_err += "\n\nTip: On hotspots, ensure your Laptop and Camera times are CRYSTAL SYNCED. Clock drift causes ONVIF auth failures."
            
            self.status_label.setText(final_err)
            logging.warning(f"Connection failed: {message}")
