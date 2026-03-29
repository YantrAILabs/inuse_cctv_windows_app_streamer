import keyring
import socket
import logging

def save_credentials(ip, username, password):
    service_name = "CCTVViewer"
    try:
        keyring.set_password(service_name, f"{ip}_user", username)
        keyring.set_password(service_name, f"{ip}_pass", password)
        print(f"Saved credentials for {ip}")
    except Exception as e:
        print(f"Failed to save credentials for {ip}: {e}")

def main():
    username = "admin"
    password = "Puran234"
    
    # Pre-configure for the 192.168.1.0/24 subnet
    for i in range(1, 255):
        target_ip = f"192.168.1.{i}"
        save_credentials(target_ip, username, password)

if __name__ == "__main__":
    main()
