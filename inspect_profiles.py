import logging
from onvif import ONVIFCamera

logging.basicConfig(level=logging.ERROR)

ip = '192.168.1.12'
port = 8000
user = 'admin'
password = 'mohit123'

try:
    device = ONVIFCamera(ip, port, user, password)
    media_service = device.create_media_service()
    profiles = media_service.GetProfiles()
    
    print(f"Found {len(profiles)} profiles for {ip}:")
    for i, p in enumerate(profiles):
        print(f"\nProfile {i+1}:")
        print(f"  Name: {p.Name}")
        print(f"  Token: {p.token}")
        if hasattr(p, 'VideoEncoderConfiguration'):
            vec = p.VideoEncoderConfiguration
            print(f"  Encoding: {vec.Encoding}")
            print(f"  Resolution: {vec.Resolution.Width}x{vec.Resolution.Height}")
            # print(f"  Bitrate: {vec.RateControl.BitrateLimit} kbps")
            
except Exception as e:
    print(f"Error: {e}")
