import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QHeaderView, QMenu
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from core.onvif_scanner import ONVIFScanner
from ui.auth_dialog import AuthDialog

class DiscoveryTab(QWidget):
    device_connected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Rescan Network")
        self.scan_btn.clicked.connect(self.start_scan)
        header_layout.addWidget(self.scan_btn)
        header_layout.addStretch()
        
        self.status_label = QLabel("Ready")
        header_layout.addWidget(self.status_label)
        layout.addLayout(header_layout)
        
        # Device Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Status", "IP Address", "Manufacturer", "Model", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.doubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)
        
        self.scanner = ONVIFScanner()
        self.scanner.progress.connect(self.status_label.setText)
        self.scanner.finished.connect(self.on_scan_finished)
        
        self.discovered_devices = []

    def start_scan(self):
        self.scan_btn.setEnabled(False)
        self.table.setRowCount(0)
        self.scanner.start()

    def on_scan_finished(self, devices):
        self.scan_btn.setEnabled(True)
        self.discovered_devices = devices
        self.table.setRowCount(len(devices))
        
        for i, dev in enumerate(devices):
            status_item = QTableWidgetItem("New") # TODO: Check if previously connected
            ip_item = QTableWidgetItem(dev['ip'])
            man_item = QTableWidgetItem(dev['manufacturer'])
            model_item = QTableWidgetItem(dev['model'])
            type_item = QTableWidgetItem(dev['type'])
            
            self.table.setItem(i, 0, status_item)
            self.table.setItem(i, 1, ip_item)
            self.table.setItem(i, 2, man_item)
            self.table.setItem(i, 3, model_item)
            self.table.setItem(i, 4, type_item)
        
        self.status_label.setText(f"Scan complete. Found {len(devices)} devices.")

    def on_row_double_clicked(self, index):
        row = index.row()
        device_info = self.discovered_devices[row]
        self.open_auth_dialog(device_info)

    def open_auth_dialog(self, device_info):
        dialog = AuthDialog(device_info, self)
        dialog.connection_successful.connect(self.device_connected.emit)
        dialog.exec()

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        
        row = index.row()
        device_info = self.discovered_devices[row]
        
        menu = QMenu(self)
        copy_ip_act = menu.addAction("Copy IP Address")
        forget_act = menu.addAction("Forget Credentials")
        
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == copy_ip_act:
            from PyQt6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(device_info['ip'])
        elif action == forget_act:
            from core.credential_store import CredentialStore
            CredentialStore.delete_credentials(device_info['ip'])
