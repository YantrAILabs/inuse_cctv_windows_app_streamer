import os
import logging
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame, QHBoxLayout, QToolButton, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QSize
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QAction, QIcon

class StreamTile(QFrame):
    """
    Individual camera tile widget with video display and overlays.
    """
    double_clicked = Signal(object) # Signal emitting self
    
    def __init__(self, channel_info, parent=None):
        super().__init__(parent)
        self.setObjectName("StreamTile")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.channel_info = channel_info
        self.ip = channel_info.get("ip", "Unknown")
        self.ch_num = channel_info.get("channel_number", 1)
        
        # Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Video Label
        self.video_label = QLabel("No Signal")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: #555; font-size: 24px;")
        self.layout.addWidget(self.video_label)
        
        # Overlays
        self._setup_overlays()
        
        # Timer for Local Time update
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self._update_time)
        self.time_timer.start(1000)

        # Toolbar (hidden by default)
        self.toolbar_widget = QWidget(self)
        self.toolbar_widget.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 5px;")
        self.toolbar_widget.setFixedHeight(40)
        self.toolbar_widget.hide()
        
        tb_layout = QHBoxLayout(self.toolbar_widget)
        tb_layout.setContentsMargins(5, 0, 5, 0)
        
        # Snapshot button
        self.btn_snapshot = QToolButton()
        self.btn_snapshot.setText("📸")
        self.btn_snapshot.setToolTip("Take Snapshot")
        self.btn_snapshot.clicked.connect(self.take_snapshot)
        tb_layout.addWidget(self.btn_snapshot)
        
        # Fullscreen button
        self.btn_fullscreen = QToolButton()
        self.btn_fullscreen.setText("🔍")
        self.btn_fullscreen.setToolTip("Toggle Fullscreen")
        self.btn_fullscreen.clicked.connect(lambda: self.double_clicked.emit(self))
        tb_layout.addWidget(self.btn_fullscreen)
        
        # Details button
        self.btn_details = QToolButton()
        self.btn_details.setText("ⓘ")
        self.btn_details.setToolTip("View Component Details")
        self.btn_details.clicked.connect(self.show_details)
        tb_layout.addWidget(self.btn_details)
        
        self._update_time()

    def _setup_overlays(self):
        # Top-left: Camera Name/IP
        self.label_overlay = QLabel(f"Ch {self.ch_num} - {self.ip}", self)
        self.label_overlay.setObjectName("overlay-label")
        self.label_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Top-right: Status LED
        self.status_led = QLabel(self)
        self.status_led.setFixedSize(12, 12)
        self.status_led.setStyleSheet("background-color: gray; border-radius: 6px;")
        
        # Bottom-right: Timestamp
        self.time_overlay = QLabel(self)
        self.time_overlay.setObjectName("overlay-label")
        self.time_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.label_overlay.move(5, 5)
        self.status_led.move(self.width() - 17, 5)
        self.time_overlay.move(self.width() - self.time_overlay.width() - 5, self.height() - self.time_overlay.height() - 5)
        self.toolbar_widget.move((self.width() - self.toolbar_widget.width()) // 2, self.height() - 50)

    def enterEvent(self, event):
        self.toolbar_widget.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.toolbar_widget.hide()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self)

    def update_frame(self, qt_image):
        pixmap = QPixmap.fromImage(qt_image)
        # Scaled to label size preserving aspect ratio
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def update_status(self, status):
        color = "gray"
        if status == "live":
            color = "#00ff00"
        elif status == "reconnecting":
            color = "yellow"
        elif status == "failed":
            color = "red"
        elif status == "connecting":
            color = "#0078d4"
        
        self.status_led.setStyleSheet(f"background-color: {color}; border-radius: 6px; border: 1px solid white;")

    def _update_time(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_overlay.setText(now)
        self.time_overlay.adjustSize()
        self.time_overlay.move(self.width() - self.time_overlay.width() - 5, self.height() - self.time_overlay.height() - 5)

    def take_snapshot(self):
        if self.video_label.pixmap():
            save_dir = os.path.expanduser("~/CCTVViewer/snapshots")
            os.makedirs(save_dir, exist_ok=True)
            filename = f"snapshot_{self.ip.replace('.', '_')}_ch{self.ch_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            save_path = os.path.join(save_dir, filename)
            self.video_label.pixmap().save(save_path, "JPG")
            logging.info(f"Snapshot saved: {save_path}")

    def show_details(self):
        """
        Displays a popup with camera details.
        """
        info_text = (
            f"<b>IP Address:</b> {self.ip}<br>"
            f"<b>Channel:</b> {self.ch_num} - {self.channel_info.get('name', 'N/A')}<br>"
            f"<b>Resolution:</b> {self.channel_info.get('resolution', 'Unknown')}<br>"
            f"<b>Token:</b> {self.channel_info.get('token', 'N/A')}<br>"
            f"<b>RTSP URL:</b><br><code style='color: #0078d4;'>{self.channel_info.get('sub_stream_uri', 'N/A')}</code>"
        )
        
        msg = QMessageBox(self)
        msg.setWindowTitle(f"Camera Details - {self.ip}")
        msg.setText(info_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
