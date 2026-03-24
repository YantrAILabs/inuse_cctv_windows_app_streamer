import logging
import time
import psutil
import httpx
from datetime import datetime
from PySide6.QtCore import QThread, Signal

class HeartbeatWorker(QThread):
    """
    Background worker that reports agent status to the cloud every 30 seconds.
    """
    heartbeat_sent = Signal(bool, str, str) # success, timestamp, message

    def __init__(self, config_manager, tunnel_manager):
        super().__init__()
        self.config_manager = config_manager
        self.tunnel_manager = tunnel_manager
        self.is_running = True
        self._ffmpeg_version = "Unknown"
        self._detect_ffmpeg_version()

    def _detect_ffmpeg_version(self):
        try:
            cloud = self.config_manager.get_cloud_settings()
            path = cloud.get("ffmpeg_path", "ffmpeg")
            import subprocess
            result = subprocess.run([path, "-version"], capture_output=True, text=True, check=True)
            self._ffmpeg_version = result.stdout.splitlines()[0]
        except Exception:
            pass

    def run(self):
        while self.is_running:
            try:
                cloud = self.config_manager.get_cloud_settings()
                api_url = cloud.get("api_url", "")
                api_key = cloud.get("api_key", "")
                agent_id = cloud.get("agent_id", "site-01")
                
                if not api_url:
                    time.sleep(5)
                    continue

                # Collect Telemetry
                streams = self.tunnel_manager.get_all_telemetry()
                total_bw = self.tunnel_manager.get_total_bandwidth_kbps()
                
                payload = {
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "api_key": api_key,
                    "streams": streams,
                    "system": {
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "upload_bandwidth_kbps": total_bw,
                        "ffmpeg_version": self._ffmpeg_version
                    }
                }
                
                headers = {
                    "X-Agent-Key": api_key,
                    "Content-Type": "application/json"
                }
                
                # POST to heartbeat endpoint
                heartbeat_url = f"{api_url.rstrip('/')}/agent/heartbeat"
                
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(heartbeat_url, json=payload, headers=headers)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    if response.status_code == 200:
                        self.heartbeat_sent.emit(True, timestamp, "Heartbeat successful")
                    else:
                        self.heartbeat_sent.emit(False, timestamp, f"Server error: {response.status_code}")
                
            except Exception as e:
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.heartbeat_sent.emit(False, timestamp, f"Network error: {str(e)}")
            
            # Wait for 30 seconds (with interrupt check)
            for _ in range(30):
                if not self.is_running: break
                time.sleep(1)

    def stop(self):
        self.is_running = False
        self.wait(2000)
