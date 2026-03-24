import json
import os
import logging
from pathlib import Path

class ConfigManager:
    """
    Manages application configuration (JSON).
    """
    DEFAULT_PATH = Path(os.path.expanduser("~/CCTVViewer/config.json"))

    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else self.DEFAULT_PATH
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = self.load_config()

    def load_config(self):
        if not self.config_path.exists():
            return self._get_default_config()
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            return self._get_default_config()

    def save_config(self, config=None):
        if config:
            self.config = config
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            logging.error(f"Failed to save config: {e}")
            return False

    def _get_default_config(self):
        return {
            "devices": [],
            "grid_layout_order": [],
            "theme": "dark",
            "cloud": {
                "server_host": "",
                "api_url": "",
                "api_key": "",
                "agent_id": "site-01",
                "srt_base_port": 8001,
                "srt_latency_ms": 300,
                "srt_passphrase": "",
                "stream_quality": "Sub Stream",
                "ffmpeg_path": ""
            }
        }

    def add_device(self, device_info):
        # Prevent duplicates
        self.config["devices"] = [d for d in self.config["devices"] if d["ip"] != device_info["ip"]]
        self.config["devices"].append(device_info)
        self.save_config()

    def get_devices(self):
        return self.config.get("devices", [])

    def get_cloud_settings(self):
        return self.config.get("cloud", {
            "agent_id": "site-01",
            "srt_base_port": 8001,
            "srt_latency_ms": 300,
            "always_resume": False,
            "active_streams": []
        })

    def save_cloud_settings(self, settings):
        self.config["cloud"] = settings
        self.save_config()

    def set_stream_active(self, ip, ch_num, active):
        cloud = self.get_cloud_settings()
        active_list = cloud.get("active_streams", [])
        key = f"{ip}:{ch_num}"
        
        if active and key not in active_list:
            active_list.append(key)
        elif not active and key in active_list:
            active_list.remove(key)
            
        cloud["active_streams"] = active_list
        self.save_cloud_settings(cloud)

    def is_stream_previously_active(self, ip, ch_num):
        cloud = self.get_cloud_settings()
        return f"{ip}:{ch_num}" in cloud.get("active_streams", [])
