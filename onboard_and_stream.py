import sys
import os
import time
import json
import logging
import socket
from core.onvif_scanner import ONVIFScanner
from core.onvif_client import ONVIFClient
from core.config_manager import ConfigManager
from core.credential_store import CredentialStore
from core.tunnel_manager import TunnelManager
from PyQt6.QtCore import QCoreApplication

# Mock logging for CLI usage
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def main():
    app = QCoreApplication(sys.argv)
    config_manager = ConfigManager()
    
    # 1. Update Config for Cloud
    cloud = config_manager.get_cloud_settings()
    cloud["server_host"] = "34.173.119.48"
    cloud["stream_quality"] = "Main Stream"
    config_manager.save_cloud_settings(cloud)
    
    print("--- Starting 16-Camera Discovery ---")
    scanner = ONVIFScanner()
    
    found_devices = []
    
    def on_finished(devices):
        nonlocal found_devices
        found_devices = devices
        print(f"Found {len(devices)} potential devices via scan.")
        app.quit()
        
    scanner.finished.connect(on_finished)
    scanner.start()
    app.exec() # Wait for scan to finish
    
    if not found_devices:
        print("No devices found. Exiting.")
        return

    # Limit to 16
    targets = found_devices[:16]
    
    onboarded_devices = []
    
    print("\n--- Connecting to Cameras ---")
    for dev in targets:
        ip = dev["ip"]
        print(f"Configuring {ip}...")
        client = ONVIFClient(ip, "admin", "Puran234")
        if client.connect():
            info = client.get_device_info()
            channels = client.get_channels()
            
            # Select Main Stream URI
            main_stream_url = None
            if channels:
                # Find profile with highest resolution or 'Main' in name
                # For now just pick first or look for Main
                for ch in channels:
                    if "main" in ch['name'].lower() or "hd" in ch['name'].lower():
                        main_stream_url = ch['sub_stream_uri'] # URIs are named sub_stream_uri in client but it pulls all
                
                if not main_stream_url:
                    main_stream_url = channels[0]['sub_stream_uri']

            device_info = {
                "ip": ip,
                "manufacturer": info["manufacturer"] if info else "Unknown",
                "model": info["model"] if info else "ONVIF",
                "onvif_port": dev.get("port", 80),
                "channels": channels
            }
            config_manager.add_device(device_info)
            onboarded_devices.append((ip, 1, main_stream_url, 8890))
            print(f"Successfully onboarded {ip}")
        else:
            print(f"Failed to connect to {ip}")

    if not onboarded_devices:
        print("No cameras could be authenticated. Check credentials.")
        return

    print("\n--- Starting Cloud Streaming ---")
    tunnel_manager = TunnelManager(config_manager)
    tunnel_manager.start_all(onboarded_devices)
    
    print(f"\n--- Monitoring Streams (30 seconds) ---")
    for _ in range(30):
        time.sleep(1)
        stats = tunnel_manager.get_all_telemetry()
        live = sum(1 for s in stats if s['status'] == 'live')
        total_bw = tunnel_manager.get_total_bandwidth_kbps()
        print(f"Active Streams: {live}/{len(onboarded_devices)} | Total Bandwidth: {total_bw / 1024:.2f} Mbps", end='\r')
    
    print("\n\nAll systems initiated. Check Cloud VM for incoming data.")
    sys.exit(0)

if __name__ == '__main__':
    main()
