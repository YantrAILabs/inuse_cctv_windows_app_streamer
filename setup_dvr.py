"""
Pre-configures the CCTVViewer config with 16 Hikvision DVR channels.
Run this once, then launch main.py — all channels appear in Live Viewer automatically.
"""
import json
import os

CONFIG_PATH = os.path.expanduser("~/CCTVViewer/config.json")
DVR_IP = "192.168.1.34"
DVR_USER = "admin"
DVR_PASS = "Puran234"

# Load existing config
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
else:
    config = {"devices": [], "grid_layout_order": [], "theme": "dark", "cloud": {}}

# Build 16 channels
channels = []
for ch in range(1, 17):
    # Hikvision RTSP URL format: /Streaming/Channels/{channel_number}01 (sub) or {channel_number}02 (main)
    sub_stream = f"rtsp://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/Streaming/Channels/{ch}02"
    main_stream = f"rtsp://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/Streaming/Channels/{ch}01"
    
    channels.append({
        "channel_number": ch,
        "name": f"Camera {ch:02d}",
        "token": f"Profile_{ch}",
        "sub_stream_uri": sub_stream,
        "main_stream_uri": main_stream,
        "resolution": "960x1088",
        "enabled": True,
        "ip": DVR_IP
    })

# Create device entry
device = {
    "ip": DVR_IP,
    "manufacturer": "Hikvision",
    "model": "DVR 16-Channel",
    "type": "DVR",
    "onvif": True,
    "channels": channels
}

# Replace existing device or add new
config["devices"] = [d for d in config.get("devices", []) if d.get("ip") != DVR_IP]
config["devices"].append(device)

# Save
os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
with open(CONFIG_PATH, "w") as f:
    json.dump(config, f, indent=4)

print(f"[OK] Config saved with {len(channels)} channels for {DVR_IP}")
print(f"   Config path: {CONFIG_PATH}")
print(f"\n   Now launch: python main.py")
print(f"   -> Go to 'Live Viewer' tab -- all 16 cameras will auto-start streaming!")
