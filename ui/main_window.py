import logging
from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QStatusBar, QMenuBar, 
                             QMenu, QSystemTrayIcon, QStyle, QLabel, QMessageBox,
                             QPushButton)
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QShortcut
from PyQt6.QtCore import Qt
import psutil
from ui.discovery_tab import DiscoveryTab
from ui.viewer_tab import ViewerTab
from ui.cloud_tab import CloudTab
from core.config_manager import ConfigManager

class MainWindow(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self.setWindowTitle("Onsite Agent")
        self.resize(1200, 800)
        self.config_manager = config_manager
        
        # Tabs
        self.tabs = QTabWidget()
        self.discovery_tab = DiscoveryTab()
        self.viewer_tab = ViewerTab()
        
        self.tabs.addTab(self.discovery_tab, "Discovery")
        self.tabs.addTab(self.viewer_tab, "Live Viewer")
        
        # Cloud Tab
        self.cloud_tab = CloudTab(self.config_manager)
        self.tabs.addTab(self.cloud_tab, "☁ Cloud")
        
        self.setCentralWidget(self.tabs)
        
        # Connect Discovery to Viewer
        self.discovery_tab.device_connected.connect(self.on_device_connected)
        
        # Connect Cloud status
        self.cloud_tab.cloud_status_changed.connect(self.update_cloud_status)
        
        # Sync Cloud Tab on new device
        self.discovery_tab.device_connected.connect(self.cloud_tab.sync_devices)
        
        # Shortcut: Ctrl+Shift+C
        self.cloud_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self.cloud_shortcut.activated.connect(self.toggle_cloud_streaming)
        
        # Menus
        self._create_menus()
        
        # Status Bar
        self.statusBar().showMessage("Ready")
        self.cloud_status_label = QLabel("")
        self.statusBar().addPermanentWidget(self.cloud_status_label)
        
        # Tray Icon
        self.tray_icon = QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
        self.tray_icon.setToolTip("CCTV Viewer Running")
        
        # Tray Menu
        self.tray_menu = QMenu()
        self.tray_status_act = QAction("Cloud: Off", self)
        self.tray_status_act.setEnabled(False)
        self.tray_menu.addAction(self.tray_status_act)
        self.tray_menu.addSeparator()
        
        show_act = QAction("Show App", self)
        show_act.triggered.connect(self.showNormal)
        self.tray_menu.addAction(show_act)
        
        exit_tray_act = QAction("Exit", self)
        exit_tray_act.triggered.connect(self.close)
        self.tray_menu.addAction(exit_tray_act)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        
        # Detect Orphaned FFmpeg processes
        self._detect_orphaned_ffmpeg()
        
        # Load existing devices from config
        self._load_saved_devices()

    def _create_menus(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        exit_act = QAction("E&xit", self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)
        
        # View Menu
        view_menu = menubar.addMenu("&View")
        fullscreen_act = QAction("Toggle Fullscreen", self)
        fullscreen_act.setShortcut("F11")
        fullscreen_act.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_act)
        
        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        rescan_act = QAction("&Rescan Network", self)
        rescan_act.setShortcut("F5")
        rescan_act.triggered.connect(self.discovery_tab.start_scan)
        tools_menu.addAction(rescan_act)

    def on_device_connected(self, device_info):
        # Save to config
        self.config_manager.add_device(device_info)
        
        # Add to viewer
        self.viewer_tab.add_device(device_info)
        
        # Switch to Viewer Tab
        self.tabs.setCurrentWidget(self.viewer_tab)
        self.statusBar().showMessage(f"Connected to {device_info['ip']}")

    def _load_saved_devices(self):
        devices = self.config_manager.get_devices()
        for dev in devices:
            self.viewer_tab.add_device(dev)
        
        if devices:
            self.tabs.setCurrentWidget(self.viewer_tab)

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def update_cloud_status(self, active, total, kbps, unreachable):
        if active > 0:
            mbps = kbps / 1024.0
            status_text = f"☁ {active}/{total} streams ↑ {mbps:.1f} Mbps"
            if unreachable:
                status_text += " (⚠ Unreachable)"
            
            self.cloud_status_label.setText(status_text)
            self.tray_status_act.setText(status_text)
        else:
            self.cloud_status_label.setText("")
            self.tray_status_act.setText("Cloud: Off")

    def toggle_cloud_streaming(self):
        active = any(w.current_status == "live" for w in self.cloud_tab.tunnel_manager.workers.values())
        if active:
            self.cloud_tab.stop_all()
            self.statusBar().showMessage("CLOUD: Stopping all streams...", 3000)
        else:
            self.cloud_tab.start_all()
            self.statusBar().showMessage("CLOUD: Starting enabled streams...", 3000)

    def _detect_orphaned_ffmpeg(self):
        orphans = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                    cmdline = proc.info.get('cmdline') or []
                    if any('srt://' in arg for arg in cmdline):
                        orphans.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if orphans:
            res = QMessageBox.question(self, "Orphaned Streams Detected",
                                    f"Found {len(orphans)} cloud streaming processes running from a previous session. "
                                    "Continue linking with them?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.No:
                for proc in orphans:
                    try:
                        proc.terminate()
                    except:
                        pass
                self.statusBar().showMessage(f"Killed {len(orphans)} orphaned processes", 3000)
            else:
                self.statusBar().showMessage(f"Linked with {len(orphans)} running processes", 3000)

    def closeEvent(self, event):
        active_streams = [w for w in self.cloud_tab.tunnel_manager.workers.values() if w.current_status in ["live", "reconnecting"]]
        
        if active_streams:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Cloud Streaming Active")
            msg_box.setText(f"Cloud streaming is currently active ({len(active_streams)} streams).")
            msg_box.setInformativeText("What would you like to do?")
            
            stop_btn = msg_box.addButton("Stop & Exit", QMessageBox.ButtonRole.ActionRole)
            keep_btn = msg_box.addButton("Keep Running & Exit", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)
            
            msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            msg_box.exec()
            
            if msg_box.clickedButton() == stop_btn:
                logging.info("CLOUD: Stopping all streams on exit.")
                self.cloud_tab.stop_all()
                self.config_manager.save_config()
                event.accept()
            elif msg_box.clickedButton() == keep_btn:
                logging.info("CLOUD: Exiting while keeping streams running in background.")
                self.config_manager.save_config()
                event.accept()
            else:
                event.ignore()
        else:
            self.config_manager.save_config()
            super().closeEvent(event)
