import logging
from onvif import ONVIFCamera

# Set up logging to console
logging.basicConfig(level=logging.INFO)

ip = '192.168.1.12'
port = 8000
user = 'admin'
password = 'mohit123'

print(f"Attempting ONVIF connection to {ip}:{port}...")

try:
    # Most ONVIF devices expect WSDL files. If they aren't provided, some libraries fail.
    # But onvif-zeep should try to fetch them or use local ones if configured.
    device = ONVIFCamera(ip, port, user, password)
    print("Connection object created. Attempting to get device information...")
    
    info = device.devicemgmt.GetDeviceInformation()
    print("SUCCESS: Device Information:")
    print(f"  Manufacturer: {info.Manufacturer}")
    print(f"  Model: {info.Model}")
    print(f"  HardwareId: {info.HardwareId}")
    print(f"  FirmwareVersion: {info.FirmwareVersion}")
    
except Exception as e:
    print(f"FAILED to connect: {e}")
