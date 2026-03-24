import logging
import subprocess
import time
import re
import os
from PySide6.QtCore import QThread, Signal, QObject
from core.credential_store import CredentialStore

class FFmpegWorker(QThread):
    """
    Handles a single FFmpeg subprocess for one stream.
    Monitors stderr for progress and bitrate.
    Handles auto-restarts with exponential backoff.
    """
    status_changed = Signal(str, str, int) # status, bitrate_kbps, attempts
    log_message = Signal(str)

    def __init__(self, ffmpeg_path, rtsp_url, dest_url, latency_ms):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.rtsp_url = rtsp_url
        self.dest_url = dest_url
        self.latency_ms = latency_ms
        self.is_running = True
        self.attempts = 0
        self.restarts = 0
        self.max_attempts = 20
        self.stable_time_threshold = 60 # seconds
        self.start_time = None
        self.current_bitrate = "0"
        self.current_status = "off"
        self.last_error = ""
        self.stable_since = None

    def run(self):
        backoff = 5
        while self.is_running and self.attempts < self.max_attempts:
            if self.attempts > 0:
                self.restarts += 1
            
            self.attempts += 1
            self.current_status = "reconnecting"
            self.status_changed.emit(self.current_status, "0", self.attempts)
            
            # Reset backoff if previous run was stable
            start_time = time.time()
            
            # FFmpeg Command
            is_rtmp = self.dest_url.startswith("rtmp://")
            
            if is_rtmp:
                full_dest_url = self.dest_url
                output_format = "flv"
            else:
                # SRT Logic
                srt_url_params = f"mode=caller&latency={self.latency_ms}000&peerlatency={self.latency_ms}000"
                if "streamid=" not in self.dest_url:
                    full_dest_url = f"{self.dest_url}?{srt_url_params}"
                else:
                    full_dest_url = f"{self.dest_url}&{srt_url_params}"
                output_format = "mpegts"

            cmd = [
                self.ffmpeg_path,
                "-hide_banner",
                "-rtsp_transport", "tcp",
                "-i", self.rtsp_url,
                "-c:v", "copy",
                "-an",
                "-f", output_format,
                full_dest_url
            ]
            
            logging.info(f"CLOUD: Starting {output_format.upper()} stream {self.rtsp_url} -> {self.dest_url}")
            self.log_message.emit(f"CMD: {' '.join(cmd)}")
            
            # Windows specific flag to hide window
            creation_flags = 0
            if os.name == 'nt':
                creation_flags = 0x08000000 # CREATE_NO_WINDOW
            
            try:
                process = subprocess.Popen(
                    cmd,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    creationflags=creation_flags
                )
                
                # Monitor stderr for bitrate and status
                bitrate_pattern = re.compile(r"bitrate=\s*([\d\.]+)kbits/s")
                
                while process.poll() is None:
                    if not self.is_running:
                        process.terminate()
                        break
                        
                    line = process.stderr.readline()
                    if line:
                        self.log_message.emit(line.strip())
                        match = bitrate_pattern.search(line)
                        if match:
                            bitrate = match.group(1)
                            self.current_bitrate = bitrate
                            self.current_status = "live"
                            self.status_changed.emit(self.current_status, bitrate, self.attempts)
                            
                            if self.start_time is None:
                                self.start_time = time.time()
                            
                            # If streaming for > 60s, reset backoff and attempts
                            if time.time() - start_time > self.stable_time_threshold:
                                self.attempts = 1
                                backoff = 5
                
                process.wait()
                if self.is_running:
                    self.last_error = f"Exit code {process.returncode}"
                    logging.warning(f"CLOUD: Stream failed {self.rtsp_url} (Format: {output_format}) — Exit code {process.returncode}")
                    self.log_message.emit(f"PROCESS EXITED (Code: {process.returncode}). Restarting in {backoff}s...")
                    self.current_status = "reconnecting"
                    self.current_bitrate = "0"
                    self.status_changed.emit(self.current_status, "0", self.attempts)
                    
                    # Sleep with interrupt check
                    for _ in range(backoff):
                        if not self.is_running: break
                        time.sleep(1)
                    
                    # Exponential backoff
                    backoff = min(60, backoff * 2)
                
            except Exception as e:
                logging.error(f"FFmpeg Popen error: {e}")
                self.log_message.emit(f"ERROR: {e}")
                time.sleep(backoff)
                backoff = min(60, backoff * 2)

        if self.attempts >= self.max_attempts:
            self.current_status = "failed"
            self.status_changed.emit(self.current_status, "0", self.attempts)
            logging.error(f"CLOUD: Max attempts reached for {self.rtsp_url}. Stopping.")
            self.log_message.emit("MAX ATTEMPTS REACHED. STOPPING.")
        else:
            self.current_status = "off"
            self.status_changed.emit(self.current_status, "0", 0)

    def stop(self):
        self.is_running = False
        self.wait(2000) # Give it 2s to exit gracefully

class TunnelManager(QObject):
    """
    Manages a collection of FFmpegWorker threads.
    """
    status_updated = Signal(str, str, str, str) # ip, ch_num, status, bitrate

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.workers = {} # { (ip, ch_num): worker }
        self.logs = {} # { (ip, ch_num): [lines] }

    def start_all(self, selected_channels):
        """
        Starts streams for selected channels with a stagger.
        selected_channels: list of (ip, ch_num, rtsp_url, srt_port)
        """
        cloud = self.config_manager.get_cloud_settings()
        ffmpeg_path = cloud.get("ffmpeg_path", "ffmpeg")
        server_host = cloud.get("server_host", "")
        latency = cloud.get("srt_latency_ms", 300)

        for ip, ch_num, rtsp_url, srt_port in selected_channels:
            if (ip, ch_num) in self.workers:
                continue
            
            # Inject credentials if available and not already present
            creds = CredentialStore.load_credentials(ip)
            if creds and creds[0] and creds[1] and f"{creds[0]}:{creds[1]}@" not in rtsp_url:
                user, pw = creds
                if "://" in rtsp_url:
                    parts = rtsp_url.split("://", 1)
                    rtsp_url = f"{parts[0]}://{user}:{pw}@{parts[1]}"
            
            agent_id = cloud.get("agent_id", "site-01")
            protocol = cloud.get("protocol", "SRT")
            
            if protocol == "RTMP":
                rtmp_port = int(cloud.get("rtmp_port", 1935))
                # RTMP format: rtmp://host:port/path
                # We use agent_id/chXX to organize on MediaMTX
                dest_url = f"rtmp://{server_host}:{rtmp_port}/{agent_id}/ch{ch_num:02d}"
            else:
                # MediaMTX recommends 'publish:path' for SRT publishing
                stream_id = f"publish:{agent_id}-ch{ch_num:02d}"
                # Use the base port for multiplexing multiple cameras over one SRT port
                base_port = int(cloud.get("srt_base_port", 8890))
                dest_url = f"srt://{server_host}:{base_port}?streamid={stream_id}"

            worker = FFmpegWorker(ffmpeg_path, rtsp_url, dest_url, latency)
            
            # Connect signals
            worker.status_changed.connect(
                lambda s, b, a, i=ip, c=ch_num: self.status_updated.emit(i, str(c), s, b)
            )
            worker.log_message.connect(
                lambda m, i=ip, c=ch_num: self._append_log(i, c, m)
            )
            
            self.workers[(ip, ch_num)] = worker
            worker.start()
            
            # Stagger start
            time.sleep(2)

    def stop_all(self):
        for key in list(self.workers.keys()):
            self.stop_stream(key[0], key[1])

    def _append_log(self, ip, ch_num, message):
        key = (ip, ch_num)
        if key not in self.logs:
            self.logs[key] = []
        self.logs[key].append(message)
        # Keep last 1000 lines
        if len(self.logs[key]) > 1000:
            self.logs[key].pop(0)

    def get_logs(self, ip, ch_num, lines=None):
        logs = self.logs.get((ip, ch_num), ["No logs available."])
        if lines:
            return "\n".join(logs[-lines:])
        return "\n".join(logs)

    def stop_stream(self, ip, ch_num):
        worker = self.workers.pop((ip, ch_num), None)
        if worker:
            logging.info(f"CLOUD: Stopped stream {ip} (Ch {ch_num})")
            worker.stop()
            self.status_updated.emit(ip, str(ch_num), "off", "0")

    def is_streaming(self, ip, ch_num):
        return (ip, ch_num) in self.workers

    def get_all_telemetry(self):
        """
        Returns stats for all channels for heartbeat.
        """
        stats = []
        # Get all devices to match names
        devices = self.config_manager.get_devices()
        
        for dev in devices:
            for ch in dev.get('channels', []):
                ip = dev['ip']
                ch_num = ch['channel_number']
                worker = self.workers.get((ip, ch_num))
                
                stat = {
                    "name": dev.get('manufacturer', 'Generic'),
                    "ip": ip,
                    "channel": ch_num,
                    "status": "off",
                    "bitrate": 0,
                    "uptime": 0,
                    "restarts": 0,
                    "last_error": ""
                }
                
                if worker:
                    stat["status"] = worker.current_status
                    stat["bitrate"] = float(worker.current_bitrate)
                    stat["restarts"] = worker.restarts
                    stat["last_error"] = worker.last_error
                    if worker.start_time:
                        stat["uptime"] = int(time.time() - worker.start_time)
                
                stats.append(stat)
        return stats

    def get_total_bandwidth_kbps(self):
        total = 0
        for worker in self.workers.values():
            if worker.current_status == "live":
                total += float(worker.current_bitrate)
        return total
