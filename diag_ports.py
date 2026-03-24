import socket

def test_port(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=3):
            print(f"Port {port}: OPEN")
            return True
    except Exception as e:
        print(f"Port {port}: CLOSED ({e})")
        return False

ip = "10.229.11.166"
ports = [80, 8000, 8080, 8888, 554]

print(f"Probing {ip} on common ports...")
for p in ports:
    test_port(ip, p)
