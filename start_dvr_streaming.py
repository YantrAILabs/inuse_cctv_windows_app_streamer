"""
Production 16-Channel DVR → Cloud RTSP Push Script
Pushes all 16 Hikvision DVR channels to MediaMTX on the cloud VM via RTSP/TCP.
Includes keepalive, auto-restart with exponential backoff, and session reset.
"""
import subprocess
import time
import os
import sys
import logging
import signal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("daemon_error.txt", mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)

# === CONFIGURATION ===
DVR_IP = "192.168.1.34"
CLOUD_IP = "34.173.17.90"
USER = "admin"
PASS = "Puran234"
AGENT_ID = "site-01"
NUM_CHANNELS = 16
FFMPEG = r"C:\Users\WELCOME\Desktop\DO NOT DELETE MOHIT FOLDER\inuse_cctv_windows_app_streamer\assets\ffmpeg\ffmpeg.exe"

# Reconnect settings
MAX_STREAM_DURATION = 900  # Force restart every 15 min to prevent silent stalls
STAGGER_DELAY = 3          # Seconds between starting each channel
BACKOFF_BASE = 5
BACKOFF_MAX = 60

processes = {}  # { channel: { "process": Popen, "log": file, "start_time": float, "restarts": int, "backoff": int } }

def start_stream(channel):
    """Launch FFmpeg to push one DVR channel to the cloud MediaMTX via RTSP/TCP."""
    # Hikvision sub-stream URL (lower bandwidth for cloud push)
    rtsp_url = f"rtsp://{USER}:{PASS}@{DVR_IP}:554/Streaming/Channels/{channel}02"
    dest_url = f"rtsp://{CLOUD_IP}:8554/{AGENT_ID}-ch{channel:02d}"
    
    cmd = [
        FFMPEG,
        "-hide_banner",
        "-loglevel", "warning",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-c:v", "copy",               # No re-encoding, just relay
        "-an",                         # Drop audio
        "-f", "rtsp",
        "-rtsp_transport", "tcp",      # Push via TCP (more reliable over internet)
        dest_url
    ]
    
    log_file = open(f"log_ch{channel}.txt", "w")
    creation_flags = 0x08000000  # CREATE_NO_WINDOW on Windows
    
    p = subprocess.Popen(
        cmd,
        creationflags=creation_flags,
        stdout=log_file,
        stderr=subprocess.STDOUT
    )
    
    logging.info(f"Started Channel {channel:02d} -> {dest_url} (PID: {p.pid})")
    
    return {
        "process": p,
        "log": log_file,
        "start_time": time.time(),
        "restarts": processes.get(channel, {}).get("restarts", 0),
        "backoff": BACKOFF_BASE
    }

def restart_stream(channel, reason="stopped"):
    """Restart a stream, closing old process and log file."""
    old = processes.get(channel)
    if old:
        try:
            old["process"].terminate()
        except:
            pass
        try:
            old["log"].close()
        except:
            pass
    
    logging.warning(f"Channel {channel:02d} {reason}. Restarting... (restart #{old['restarts'] + 1 if old else 1})")
    
    info = start_stream(channel)
    if old:
        info["restarts"] = old["restarts"] + 1
        # Reset backoff if previous run was stable (>2 min)
        if old["start_time"] and (time.time() - old["start_time"]) > 120:
            info["backoff"] = BACKOFF_BASE
        else:
            info["backoff"] = min(old["backoff"] * 2, BACKOFF_MAX)
    
    processes[channel] = info
    return info

def main():
    logging.info(f"=== Starting {NUM_CHANNELS}-Channel Cloud Push to {CLOUD_IP} ===")
    logging.info(f"    DVR: {DVR_IP} | Agent: {AGENT_ID}")
    logging.info(f"    FFmpeg: {FFMPEG}")
    logging.info(f"    Max stream duration: {MAX_STREAM_DURATION}s (auto-restart)")
    
    # Initial launch — stagger to prevent burst
    for ch in range(1, NUM_CHANNELS + 1):
        processes[ch] = start_stream(ch)
        time.sleep(STAGGER_DELAY)
    
    logging.info(f"All {NUM_CHANNELS} streams initiated. Monitoring...")
    
    try:
        while True:
            time.sleep(10)
            
            alive = 0
            for ch in range(1, NUM_CHANNELS + 1):
                info = processes.get(ch)
                if not info:
                    continue
                
                p = info["process"]
                elapsed = time.time() - info["start_time"]
                
                if p.poll() is not None:
                    # Process died — restart with backoff
                    backoff = info["backoff"]
                    logging.warning(f"Channel {ch:02d} exited (code {p.returncode}). Waiting {backoff}s...")
                    time.sleep(backoff)
                    restart_stream(ch, reason=f"exited (code {p.returncode})")
                elif elapsed > MAX_STREAM_DURATION:
                    # Force restart to prevent silent stalls (Hikvision session timeout)
                    restart_stream(ch, reason=f"session refresh ({int(elapsed)}s)")
                    time.sleep(STAGGER_DELAY)
                else:
                    alive += 1
            
            # Periodic status
            if alive < NUM_CHANNELS:
                logging.info(f"Status: {alive}/{NUM_CHANNELS} streams alive")
                
    except KeyboardInterrupt:
        logging.info("Stopping all streams...")
        for ch, info in processes.items():
            try:
                info["process"].terminate()
            except:
                pass

if __name__ == "__main__":
    main()
