import time
import logging
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap

class StreamWorker(QThread):
    """
    RTSP stream worker using OpenCV.
    - Captures frames in a background thread.
    - Handles reconnection with exponential backoff.
    - Emits signals for UI updates.
    """
    frame_ready = Signal(QImage)
    status_changed = Signal(str) # "live", "reconnecting", "failed"
    bitrate_updated = Signal(float) # kbps

    def __init__(self, rtsp_url, channel_id, parent=None):
        super().__init__(parent)
        self.rtsp_url = rtsp_url
        self.channel_id = channel_id
        self._running = False
        self._reconnect_delay = 2
        self._max_reconnect_attempts = 10
        self._consecutive_failures = 0

    def stop(self):
        self._running = False
        self.wait()

    def run(self):
        self._running = True
        while self._running:
            self.status_changed.emit("connecting")
            cap = self._open_capture()
            
            if cap is None:
                self._handle_failure()
                if not self._running: break
                continue

            self._consecutive_failures = 0
            self._reconnect_delay = 2
            self.status_changed.emit("live")
            
            last_frame_time = time.time()
            total_bytes = 0
            
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    logging.warning(f"Stream interrupted: {self.rtsp_url}")
                    break
                
                current_time = time.time()
                dt = current_time - last_frame_time
                last_frame_time = current_time
                
                # Estimate bitrate (very rough estimation based on frame size)
                # In real scenario, we'd need more data, but let's approximate
                frame_bytes = frame.size * frame.itemsize
                total_bytes += frame_bytes
                if total_bytes > 1_000_000: # Every ~1MB
                    self.bitrate_updated.emit((total_bytes * 8) / (dt * 1024) if dt > 0 else 0)
                    total_bytes = 0
                
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self.frame_ready.emit(qt_image.copy()) # Copy to ensure data ownership
                
                # Control frame rate? OpenCV usually handles this based on RTSP stream
            
            cap.release()
            self._handle_failure()

        self.status_changed.emit("failed")

    def _open_capture(self):
        # Build URL with TCP transport if needed 
        # (Though OpenCV 4.x usually tries TCP then UDP by default)
        cap = cv2.VideoCapture(self.rtsp_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Check if opened
        if cap.isOpened():
            return cap
        return None

    def _handle_failure(self):
        if not self._running:
            return
            
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._max_reconnect_attempts:
            self._running = False
            self.status_changed.emit("failed")
            return

        self.status_changed.emit("reconnecting")
        time.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, 30) # Exponential backoff capped at 30s
