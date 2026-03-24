import logging
import os
import subprocess
import shutil
import httpx
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLineEdit, QPushButton, QLabel, QComboBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QGroupBox, QFileDialog, QMessageBox, QAbstractItemView,
                             QSplitter, QCheckBox, QMenu, QTextEdit)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from core.config_manager import ConfigManager
from core.tunnel_manager import TunnelManager
from core.heartbeat_worker import HeartbeatWorker

class CloudTestThread(QThread):
    finished = Signal(bool, str)

    def __init__(self, api_url):
        super().__init__()
        self.api_url = api_url

    def run(self):
        try:
            health_url = f"{self.api_url.rstrip('/')}/health"
            response = httpx.get(health_url, timeout=5.0)
            if response.status_code == 200:
                self.finished.emit(True, "Connection Successful!")
            else:
                self.finished.emit(False, f"Server responded with code {response.status_code}")
        except Exception as e:
            self.finished.emit(False, f"Connection Failed: {str(e)}")

class LogViewerDialog(QMessageBox):
    def __init__(self, title, logs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText("Historical Logs (last 1000 lines):")
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(logs)
        self.text_edit.setMinimumSize(600, 400)
        
        self.layout().addWidget(self.text_edit, 1, 0, 1, self.layout().columnCount())
        self.setStandardButtons(QMessageBox.Ok)

class CloudTab(QWidget):
    cloud_status_changed = Signal(int, int, float, bool)

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.tunnel_manager = TunnelManager(config_manager)
        self.heartbeat_worker = None
        self.setup_ui()
        self.load_settings()
        self.detect_ffmpeg()
        self.refresh_channels()
        
        # Connect Tunnel Manager signals
        self.tunnel_manager.status_updated.connect(self.update_row_status)

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)
        
        # --- Left Panel: Settings ---
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        
        settings_group = QGroupBox("Cloud Settings")
        form_layout = QFormLayout(settings_group)
        
        self.edit_host = QLineEdit()
        self.edit_api_url = QLineEdit()
        self.edit_api_key = QLineEdit()
        self.edit_agent_id = QLineEdit("site-01")
        self.combo_protocol = QComboBox()
        self.combo_protocol.addItems(["SRT", "RTMP"])
        self.combo_protocol.currentTextChanged.connect(self.on_protocol_changed)
        
        self.edit_srt_base_port = QLineEdit("8890")
        self.edit_rtmp_port = QLineEdit("1935")
        
        self.edit_srt_latency = QLineEdit("300")
        self.edit_srt_passphrase = QLineEdit()
        self.edit_srt_passphrase.setEchoMode(QLineEdit.Password)
        
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["Sub Stream", "Main Stream"])
        
        ffmpeg_layout = QHBoxLayout()
        self.edit_ffmpeg_path = QLineEdit()
        self.btn_browse_ffmpeg = QPushButton("Browse")
        self.btn_browse_ffmpeg.clicked.connect(self.browse_ffmpeg)
        ffmpeg_layout.addWidget(self.edit_ffmpeg_path)
        ffmpeg_layout.addWidget(self.btn_browse_ffmpeg)
        
        self.cb_always_resume = QCheckBox("Always resume on startup")
        
        form_layout.addRow("Server Host/IP:", self.edit_host)
        form_layout.addRow("API URL:", self.edit_api_url)
        form_layout.addRow("API Key:", self.edit_api_key)
        form_layout.addRow("Agent ID:", self.edit_agent_id)
        form_layout.addRow("Protocol:", self.combo_protocol)
        
        # SRT Settings
        self.row_srt_port = form_layout.addRow("SRT Base Port:", self.edit_srt_base_port)
        self.row_srt_latency = form_layout.addRow("SRT Latency (ms):", self.edit_srt_latency)
        self.row_srt_pass = form_layout.addRow("SRT Passphrase:", self.edit_srt_passphrase)
        
        # RTMP Settings
        self.row_rtmp_port = form_layout.addRow("RTMP Port:", self.edit_rtmp_port)
        form_layout.addRow("Stream Quality:", self.combo_quality)
        form_layout.addRow("FFmpeg Path:", ffmpeg_layout)
        form_layout.addRow("", self.cb_always_resume)
        
        # FFmpeg Warning Banner
        self.lbl_ffmpeg_warning = QLabel("⚠ FFmpeg not found at saved path. Cloud streaming unavailable.")
        self.lbl_ffmpeg_warning.setStyleSheet("background-color: #800; color: white; padding: 5px; border-radius: 3px;")
        self.lbl_ffmpeg_warning.setHidden(True)
        left_layout.insertWidget(0, self.lbl_ffmpeg_warning)
        
        left_layout.addWidget(settings_group)
        
        # FFmpeg Info
        self.ffmpeg_info_label = QLabel("Detecting FFmpeg...")
        self.ffmpeg_info_label.setWordWrap(True)
        self.ffmpeg_info_label.setStyleSheet("color: #888; font-size: 11px;")
        left_layout.addWidget(self.ffmpeg_info_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_test_connection = QPushButton("Test Connection")
        self.btn_test_connection.clicked.connect(self.test_connection)
        self.btn_save_settings = QPushButton("Save Settings")
        self.btn_save_settings.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.btn_test_connection)
        btn_layout.addWidget(self.btn_save_settings)
        left_layout.addLayout(btn_layout)
        left_layout.addStretch()
        
        self.splitter.addWidget(self.left_panel)
        
        # --- Right Panel: Channel Table ---
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Push", "Camera Name", "Device IP", "Channel", "SRT Port", "Status", "Bitrate"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        right_layout.addWidget(self.table)
        
        # Table Controls
        table_btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self.deselect_all)
        self.btn_refresh_cameras = QPushButton("Refresh from Cameras")
        self.btn_refresh_cameras.clicked.connect(self.refresh_channels)
        table_btn_layout.addWidget(self.btn_select_all)
        table_btn_layout.addWidget(self.btn_deselect_all)
        table_btn_layout.addWidget(self.btn_refresh_cameras)
        right_layout.addLayout(table_btn_layout)
        
        # Start/Stop Controls
        control_layout = QHBoxLayout()
        self.btn_start_all = QPushButton("Start All")
        self.btn_start_all.setEnabled(True)
        self.btn_start_all.clicked.connect(self.start_all)
        self.btn_stop_all = QPushButton("Stop All")
        self.btn_stop_all.setEnabled(True)
        self.btn_stop_all.clicked.connect(self.stop_all)
        control_layout.addWidget(self.btn_start_all)
        control_layout.addWidget(self.btn_stop_all)
        right_layout.addLayout(control_layout)
        
        # Cloud Status Strip
        self.status_strip = QHBoxLayout()
        self.lbl_cloud_summary = QLabel("☁ Cloud: Off")
        self.lbl_heartbeat_status = QLabel("Heartbeat: —")
        self.lbl_server_warning = QLabel("")
        self.lbl_server_warning.setStyleSheet("color: #ffaa00; font-weight: bold;")
        
        self.status_strip.addWidget(self.lbl_cloud_summary)
        self.status_strip.addStretch()
        self.status_strip.addWidget(self.lbl_heartbeat_status)
        right_layout.addLayout(self.status_strip)
        right_layout.addWidget(self.lbl_server_warning)
        
        # Table Context Menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(1, 2)
        main_layout.addWidget(self.splitter)

    def browse_ffmpeg(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Executable", "", "Executables (*.exe);;All Files (*)")
        if file_path:
            self.edit_ffmpeg_path.setText(file_path)
            self.detect_ffmpeg(file_path)

    def detect_ffmpeg(self, manual_path=None):
        path = manual_path or self.edit_ffmpeg_path.text() or shutil.which("ffmpeg")
        
        # Check common Windows locations if not found
        if not path:
            common_paths = [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\ffmpeg\ffmpeg.exe"]
            for cp in common_paths:
                if os.path.exists(cp):
                    path = cp
                    break
        
        if path and os.path.exists(path):
            try:
                result = subprocess.run([path, "-version"], capture_output=True, text=True, check=True)
                version_line = result.stdout.splitlines()[0]
                self.ffmpeg_info_label.setText(f"FFmpeg found: {version_line}")
                self.edit_ffmpeg_path.setText(path)
                self.lbl_ffmpeg_warning.setHidden(True)
                self.btn_start_all.setEnabled(True)
            except Exception:
                self.ffmpeg_info_label.setText("FFmpeg found but failed to execute.")
                self.lbl_ffmpeg_warning.setHidden(False)
                self.btn_start_all.setEnabled(False)
        else:
            self.lbl_ffmpeg_warning.setHidden(False)
            self.btn_start_all.setEnabled(False)
            self.ffmpeg_info_label.setText("FFmpeg not found. Download from: <a href='https://www.gyan.dev/ffmpeg/builds/' style='color: #0078d4;'>gyan.dev/ffmpeg/builds</a>")
            self.ffmpeg_info_label.setOpenExternalLinks(True)

    def load_settings(self):
        cloud = self.config_manager.get_cloud_settings()
        self.edit_host.setText(cloud.get("server_host", ""))
        self.edit_api_url.setText(cloud.get("api_url", ""))
        self.edit_api_key.setText(cloud.get("api_key", ""))
        self.edit_agent_id.setText(cloud.get("agent_id", "site-01"))
        
        protocol = cloud.get("protocol", "SRT")
        self.combo_protocol.setCurrentText(protocol)
        
        self.edit_srt_base_port.setText(str(cloud.get("srt_base_port", 8890)))
        self.edit_rtmp_port.setText(str(cloud.get("rtmp_port", 1935)))
        
        self.edit_srt_latency.setText(str(cloud.get("srt_latency_ms", 300)))
        self.edit_srt_passphrase.setText(cloud.get("srt_passphrase", ""))
        self.combo_quality.setCurrentText(cloud.get("stream_quality", "Sub Stream"))
        self.edit_ffmpeg_path.setText(cloud.get("ffmpeg_path", ""))
        self.cb_always_resume.setChecked(cloud.get("always_resume", False))
        self.on_protocol_changed(protocol)

    def save_settings(self):
        try:
            settings = {
                "server_host": self.edit_host.text(),
                "api_url": self.edit_api_url.text(),
                "api_key": self.edit_api_key.text(),
                "agent_id": self.edit_agent_id.text(),
                "protocol": self.combo_protocol.currentText(),
                "srt_base_port": int(self.edit_srt_base_port.text()),
                "rtmp_port": int(self.edit_rtmp_port.text()),
                "srt_latency_ms": int(self.edit_srt_latency.text()),
                "srt_passphrase": self.edit_srt_passphrase.text(),
                "stream_quality": self.combo_quality.currentText(),
                "ffmpeg_path": self.edit_ffmpeg_path.text(),
                "always_resume": self.cb_always_resume.isChecked()
            }
            self.config_manager.save_cloud_settings(settings)
            QMessageBox.information(self, "Success", "Cloud settings saved successfully.")
            self.refresh_channels() # Update SRT ports in table if base port changed
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid numeric value for port or latency.")

    def on_protocol_changed(self, protocol):
        is_srt = protocol == "SRT"
        
        # Show/Hide SRT fields
        self.edit_srt_base_port.setVisible(is_srt)
        self.edit_srt_latency.setVisible(is_srt)
        self.edit_srt_passphrase.setVisible(is_srt)
        
        # Show/Hide RTMP fields
        self.edit_rtmp_port.setVisible(not is_srt)
        
        # Find labels in form layout
        form = self.left_panel.findChild(QFormLayout)
        if form:
            for i in range(form.rowCount()):
                item = form.itemAt(i, QFormLayout.LabelRole)
                if not item: continue
                label = item.widget()
                if not label: continue
                txt = label.text()
                if "SRT" in txt:
                    label.setVisible(is_srt)
                elif "RTMP" in txt:
                    label.setVisible(not is_srt)

    def test_connection(self):
        api_url = self.edit_api_url.text()
        if not api_url:
            QMessageBox.warning(self, "Input Error", "Please enter an API URL first.")
            return
        
        self.btn_test_connection.setEnabled(False)
        self.test_thread = CloudTestThread(api_url)
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()

    def on_test_finished(self, success, message):
        self.btn_test_connection.setEnabled(True)
        if success:
            QMessageBox.information(self, "Test Result", message)
        else:
            QMessageBox.critical(self, "Test Result", message)

    def refresh_channels(self):
        self.table.setRowCount(0)
        devices = self.config_manager.get_devices()
        base_port = int(self.edit_srt_base_port.text() or 8001)
        
        all_channels = []
        for dev in devices:
            for ch in dev.get('channels', []):
                # Determine RTSP URL based on quality
                # Note: Currently we only save one URI. We should ideally save both.
                # For now, we use sub_stream_uri if it exists.
                rtsp_url = ch.get('sub_stream_uri', '')
                
                all_channels.append({
                    "name": dev.get('manufacturer', 'Generic'),
                    "ip": dev['ip'],
                    "ch_num": ch['channel_number'],
                    "rtsp_url": rtsp_url
                })
        
        prev_active_count = 0
        self.table.setRowCount(len(all_channels))
        for i, ch_data in enumerate(all_channels):
            # Checkbox
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb = QCheckBox()
            
            # Auto-Resume Check
            is_active = self.config_manager.is_stream_previously_active(ch_data['ip'], ch_data['ch_num'])
            if is_active:
                cb.setChecked(True)
                prev_active_count += 1
            
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(i, 0, cb_widget)
            
            self.table.setItem(i, 1, QTableWidgetItem(ch_data['name']))
            self.table.setItem(i, 2, QTableWidgetItem(ch_data['ip']))
            self.table.setItem(i, 3, QTableWidgetItem(str(ch_data['ch_num'])))
            
            srt_port = base_port + i
            self.table.setItem(i, 4, QTableWidgetItem(str(srt_port)))
            
            # Status Item
            status_item = QTableWidgetItem("⚫ Off")
            self.table.setItem(i, 5, status_item)
            
            # Bitrate Item
            bitrate_item = QTableWidgetItem("—")
            self.table.setItem(i, 6, bitrate_item)
            
            # Store hidden data
            cb.setProperty("ch_data", ch_data)
            cb.setProperty("srt_port", srt_port)
            cb.setProperty("row", i)
        
        # Trigger resume dialog if needed
        if prev_active_count > 0:
            QTimer.singleShot(500, lambda: self.check_auto_resume(prev_active_count))

    def check_auto_resume(self, count):
        cloud = self.config_manager.get_cloud_settings()
        if cloud.get("always_resume", False):
            self.start_all()
            return
            
        res = QMessageBox.question(self, "Resume Streaming", 
                                f"Cloud streaming was active last session ({count} channels). Resume now?",
                                QMessageBox.Yes | QMessageBox.No)
        
        # Checkbox for "Always resume"
        if res == QMessageBox.Yes:
            # We don't have a standard way to add a checkbox to QMessageBox.question easily without custom class
            # but we can ask separately or just implement it. 
            self.start_all()
            
    def sync_devices(self):
        """Called when a new device is added in another tab."""
        self.refresh_channels()

    def update_row_status(self, ip, ch_num, status, bitrate):
        # Find row by IP and Channel
        for i in range(self.table.rowCount()):
            row_ip = self.table.item(i, 2).text()
            row_ch = self.table.item(i, 3).text()
            
            if row_ip == ip and row_ch == str(ch_num):
                # Update Status
                status_text = "⚫ Off"
                if status == "live":
                    status_text = "🟢 Live"
                    self.config_manager.set_stream_active(ip, ch_num, True)
                elif status == "reconnecting":
                    status_text = "🟡 Reconnecting"
                    self.config_manager.set_stream_active(ip, ch_num, True)
                elif status == "failed":
                    status_text = "🔴 Failed"
                elif status == "off":
                    self.config_manager.set_stream_active(ip, ch_num, False)
                
                self.table.item(i, 5).setText(status_text)
                self.table.item(i, 5).setForeground(Qt.GlobalColor.white if status == "off" else Qt.GlobalColor.black) # Placeholder
                # Actually, colored icons or background is better but text+emoji works
                
                # Update Bitrate
                if status == "live" and bitrate != "0":
                    self.table.item(i, 6).setText(f"{bitrate} kbps")
                else:
                    self.table.item(i, 6).setText("—")
                break
        
        self.refresh_status_strip()

    def refresh_status_strip(self):
        telemetry = self.tunnel_manager.get_all_telemetry()
        total = len(telemetry)
        active = sum(1 for t in telemetry if t['status'] == 'live')
        total_kbps = self.tunnel_manager.get_total_bandwidth_kbps()
        total_mbps = total_kbps / 1024.0
        
        if active > 0:
            self.lbl_cloud_summary.setText(f"☁ Cloud: {active}/{total} streams | ↑ {total_mbps:.1f} Mbps")
            self.start_heartbeat()
        else:
            self.lbl_cloud_summary.setText("☁ Cloud: Off")
            self.stop_heartbeat()
            self.lbl_heartbeat_status.setText("Heartbeat: —")
            self.lbl_server_warning.setText("")
        
        # Notify MainWindow
        server_unreachable = "unreachable" in self.lbl_server_warning.text().lower()
        self.cloud_status_changed.emit(active, total, total_kbps, server_unreachable)

    def start_heartbeat(self):
        if self.heartbeat_worker and self.heartbeat_worker.isRunning():
            return
            
        self.heartbeat_worker = HeartbeatWorker(self.config_manager, self.tunnel_manager)
        self.heartbeat_worker.heartbeat_sent.connect(self.on_heartbeat_sent)
        self.heartbeat_worker.start()

    def stop_heartbeat(self):
        if self.heartbeat_worker:
            self.heartbeat_worker.stop()
            self.heartbeat_worker = None

    def on_heartbeat_sent(self, success, timestamp, message):
        if success:
            self.lbl_heartbeat_status.setText(f"Last heartbeat: {timestamp}")
            self.lbl_server_warning.setText("")
        else:
            self.lbl_heartbeat_status.setText(f"Last heartbeat: Failed ({timestamp})")
            self.lbl_server_warning.setText("⚠ Cloud server unreachable — streams continue pushing")
        
        # Refresh strip for unreachable status update to MainWindow
        self.refresh_status_strip()

    def start_all(self):
        selected = []
        for i in range(self.table.rowCount()):
            cb_widget = self.table.cellWidget(i, 0)
            if cb_widget:
                cb = cb_widget.findChild(QCheckBox)
                if cb.isChecked():
                    ch_data = cb.property("ch_data")
                    srt_port = cb.property("srt_port")
                    selected.append((ch_data['ip'], ch_data['ch_num'], ch_data['rtsp_url'], srt_port))
        
        if not selected:
            QMessageBox.warning(self, "Selection Required", "Please select at least one channel to push.")
            return

        self.tunnel_manager.start_all(selected)

    def stop_all(self):
        self.tunnel_manager.stop_all()

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid(): return
        
        row = index.row()
        ip = self.table.item(row, 2).text()
        ch_num = int(self.table.item(row, 3).text())
        
        menu = QMenu(self)
        
        restart_act = menu.addAction("Restart Stream")
        restart_act.triggered.connect(lambda: self.restart_stream(ip, ch_num))
        
        view_log_act = menu.addAction("View FFmpeg Log (Full)")
        view_log_act.triggered.connect(lambda: self.view_log(ip, ch_num))
        
        view_last_log_act = menu.addAction("View FFmpeg Output (Last 50 lines)")
        view_last_log_act.triggered.connect(lambda: self.view_log(ip, ch_num, 50))
        
        menu.addSeparator()
        
        copy_srt_act = menu.addAction("Copy SRT URI")
        copy_srt_act.triggered.connect(lambda: self.copy_srt_uri(row))
        
        copy_rtsp_act = menu.addAction("Copy RTSP Source")
        copy_rtsp_act.triggered.connect(lambda: self.copy_rtsp_uri(row))
        
        menu.addSeparator()
        
        toggle_act = menu.addAction("Disable Push" if self.table.cellWidget(row, 0).findChild(QCheckBox).isChecked() else "Enable Push")
        toggle_act.triggered.connect(lambda: self.toggle_push(row))
        
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def toggle_push(self, row):
        cb = self.table.cellWidget(row, 0).findChild(QCheckBox)
        cb.setChecked(not cb.isChecked())
        # If running, stop it
        if not cb.isChecked() and self.tunnel_manager.is_streaming(self.table.item(row, 2).text(), int(self.table.item(row, 3).text())):
            self.tunnel_manager.stop_stream(self.table.item(row, 2).text(), int(self.table.item(row, 3).text()))

    def copy_rtsp_uri(self, row):
        cb = self.table.cellWidget(row, 0).findChild(QCheckBox)
        ch_data = cb.property("ch_data")
        uri = ch_data.get('rtsp_url', '')
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(uri)
        QMessageBox.information(self, "Copied", f"Copied RTSP Source:\n{uri}")

    def restart_stream(self, ip, ch_num):
        self.tunnel_manager.stop_stream(ip, ch_num)
        # Find row data and start again
        for i in range(self.table.rowCount()):
            if self.table.item(i, 2).text() == ip and self.table.item(i, 3).text() == str(ch_num):
                cb_widget = self.table.cellWidget(i, 0)
                cb = cb_widget.findChild(QCheckBox)
                ch_data = cb.property("ch_data")
                srt_port = cb.property("srt_port")
                self.tunnel_manager.start_all([(ip, ch_num, ch_data['rtsp_url'], srt_port)])
                break

    def copy_srt_uri(self, row):
        host = self.edit_host.text() or "localhost"
        port = self.table.item(row, 4).text()
        uri = f"srt://{host}:{port}"
        from PySide6.QtGui import QClipboard
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(uri)
        QMessageBox.information(self, "Copied", f"Copied to clipboard:\n{uri}")

    def view_log(self, ip, ch_num):
        logs = self.tunnel_manager.get_logs(ip, ch_num)
        dialog = LogViewerDialog(f"FFmpeg Log - {ip} (Ch {ch_num})", logs, self)
        dialog.exec()

    def select_all(self):
        for i in range(self.table.rowCount()):
            cb_widget = self.table.cellWidget(i, 0)
            if cb_widget:
                cb_widget.findChild(QCheckBox).setChecked(True)

    def deselect_all(self):
        for i in range(self.table.rowCount()):
            cb_widget = self.table.cellWidget(i, 0)
            if cb_widget:
                cb_widget.findChild(QCheckBox).setChecked(False)
