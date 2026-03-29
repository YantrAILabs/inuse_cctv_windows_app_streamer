import socket
import logging
from PyQt6.QtCore import QThread, pyqtSignal as Signal
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
from wsdiscovery import Scope
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

class ONVIFScanner(QThread):
    """
    Scans the network for ONVIF devices using WS-Discovery and RTSP port scanning.
    """
    finished = Signal(list)
    progress = Signal(str)

    def __init__(self):
        super().__init__()
        self.wsd = WSDiscovery()

    def run(self):
        self.progress.emit("Starting WS-Discovery...")
        discovered_devices = []
        
        try:
            self.wsd.start()
            # Wait for some time to gather responses
            import time
            time.sleep(10) # Increased timeout for slow/hotspot devices
            
            services = self.wsd.searchServices()
            for service in services:
                ip = self._extract_ip(service.getXAddrs())
                if ip:
                    device = {
                        "ip": ip,
                        "manufacturer": "Unknown", # Will be updated via ONVIF Client
                        "model": "ONVIF Device",
                        "type": "Camera",
                        "onvif": True,
                        "xaddr": service.getXAddrs()[0] if service.getXAddrs() else None
                    }
                    discovered_devices.append(device)
            
            self.wsd.stop()
        except Exception as e:
            logging.error(f"WS-Discovery error: {e}")
            self.progress.emit(f"WS-Discovery failed: {e}")

        # Fallback: RTSP/ONVIF Port Scan on local subnet
        self._fallback_scan(discovered_devices)

        self.progress.emit(f"Discovery finished. Found {len(discovered_devices)} devices.")
        self.finished.emit(discovered_devices)

    def _extract_ip(self, xaddrs):
        for addr in xaddrs:
            # Simple IP extraction from URL
            try:
                from urllib.parse import urlparse
                parsed = urlparse(addr)
                return parsed.hostname
            except:
                continue
        return None

    def _fallback_scan(self, discovered_devices):
        self.progress.emit("Running optimized subnet port scan...")
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            parts = local_ip.split(".")
            if len(parts) >= 3:
                subnet = ".".join(parts[:3])
            else:
                subnet = "192.168.1"
            
            # Common ports for ONVIF and RTSP
            # ONVIF: 80, 8080, 8899, 3911, 8000
            # RTSP: 554, 8554, 5543, 10554
            target_ports = [8899, 80, 8080, 554, 8000, 3911, 8554, 5543, 10554]
            
            def check_ip(ip):
                for port in target_ports:
                    if self._check_port(ip, port, timeout=0.2): # Increased timeout
                        return {"ip": ip, "port": port}
                return None

            max_workers = 50
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for i in range(1, 255):
                    target_ip = f"{subnet}.{i}"
                    # Skip already discovered
                    if any(d["ip"] == target_ip for d in discovered_devices):
                        continue
                    futures.append(executor.submit(check_ip, target_ip))
                
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        ip = result["ip"]
                        port = result["port"]
                        # Determine if it's likely ONVIF or just RTSP
                        is_onvif = port in [8899, 80, 8080, 3911, 8000]
                        discovered_devices.append({
                            "ip": ip,
                            "manufacturer": "Generic",
                            "model": "ONVIF Device" if is_onvif else "RTSP Device",
                            "type": "Camera",
                            "onvif": is_onvif,
                            "port": port
                        })
        except Exception as e:
            logging.error(f"Fallback scan error: {e}")
            self.progress.emit(f"Fallback scan failed: {e}")

    def _check_port(self, ip, port, timeout=0.2):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                return result == 0
        except:
            return False
