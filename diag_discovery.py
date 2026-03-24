import socket
import time
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
from urllib.parse import urlparse
import threading

def check_port(ip, port, timeout=0.1):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((ip, port))
    sock.close()
    return result == 0

def scan_subnet(subnet):
    print(f"Scanning subnet {subnet}.0/24 for RTSP/ONVIF ports...")
    found = []
    ports = [554, 8554, 8000, 8080, 8899, 3911]
    
    def worker(ip):
        for port in ports:
            if check_port(ip, port):
                print(f"  [Found] {ip}:{port}")
                found.append((ip, port))
                break

    threads = []
    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        t = threading.Thread(target=worker, args=(ip,))
        threads.append(t)
        t.start()
        if len(threads) > 50:
            for t in threads: t.join()
            threads = []
    for t in threads: t.join()
    return found

def test_discovery():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    subnet = ".".join(local_ip.split(".")[:-1])
    print(f"Local IP: {local_ip}, Subnet: {subnet}")
    
    wsd = WSDiscovery()
    try:
        wsd.start()
        print("Searching for WS-Discovery services...")
        time.sleep(5)
        services = wsd.searchServices()
        print(f"WS-Discovery found {len(services)} services:")
        for s in services:
            print(f"  XAddrs: {s.getXAddrs()}")
            print(f"  Scopes: {s.getScopes()}")
        wsd.stop()
    except Exception as e:
        print(f"WS-Discovery error: {e}")

    scan_subnet(subnet)

if __name__ == "__main__":
    test_discovery()
