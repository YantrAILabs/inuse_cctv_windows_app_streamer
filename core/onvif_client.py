import logging
from onvif import ONVIFCamera
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery

class ONVIFClient:
    """
    Handles ONVIF device connection and metadata retrieval.
    """
    def __init__(self, ip, login, password, port=80):
        self.ip = ip
        self.login = login
        self.password = password
        self.port = port
        self.device = None

    def connect(self):
        try:
            # Note: wsdl_dir might need to be specified depending on environment
            self.device = ONVIFCamera(self.ip, self.port, self.login, self.password)
            
            # Check for time sync issues (common on hotspots)
            try:
                dt = self.device.devicemgmt.GetSystemDateAndTime()
                # If we get here, the connection is alive even if auth fails later
                return True
            except Exception as e:
                if "Sender not Authorized" in str(e):
                    logging.error(f"ONVIF Auth Failed for {self.ip}: Check Credentials or Time Sync. {e}")
                else:
                    logging.error(f"ONVIF Connection Error for {self.ip}: {e}")
                return False
        except Exception as e:
            logging.error(f"Failed to initialize ONVIF device {self.ip}: {e}")
            return False

    def get_device_info(self):
        if not self.device:
            return None
        try:
            info = self.device.devicemgmt.GetDeviceInformation()
            return {
                "manufacturer": info.Manufacturer,
                "model": info.Model,
                "hw_id": info.HardwareId,
                "fw_version": info.FirmwareVersion
            }
        except Exception as e:
            logging.error(f"Failed to get device info for {self.ip}: {e}")
            return None

    def get_channels(self):
        """
        Retrieves all media profiles and their stream URIs.
        """
        if not self.device:
            return []
        
        channels = []
        try:
            media_service = self.device.create_media_service()
            profiles = media_service.GetProfiles()
            
            for i, profile in enumerate(profiles):
                token = profile.token
                name = profile.Name
                
                # Get Sub-stream (lower quality)
                sub_stream_uri = self._get_stream_uri(media_service, token, stream_type='RTP-Unicast', protocol='RTSP')
                
                # Get Main-stream (higher quality)
                # Usually another profile? Or same profile with different options?
                # For most NVRs, each profile corresponds to a channel/stream type.
                
                # Get resolution if available
                resolution = ""
                if hasattr(profile, 'VideoEncoderConfiguration'):
                    res = profile.VideoEncoderConfiguration.Resolution
                    resolution = f"{res.Width}x{res.Height}"

                channels.append({
                    "channel_number": i + 1, # Default index
                    "name": name,
                    "token": token,
                    "sub_stream_uri": sub_stream_uri,
                    "resolution": resolution,
                    "enabled": True
                })
        except Exception as e:
            logging.error(f"Failed to get channels for {self.ip}: {e}")
        
        return channels

    def _get_stream_uri(self, media_service, profile_token, stream_type='RTP-Unicast', protocol='RTSP'):
        try:
            request = media_service.create_type('GetStreamUri')
            request.ProfileToken = profile_token
            request.StreamSetup = {
                'Stream': stream_type,
                'Transport': {
                    'Protocol': protocol
                }
            }
            res = media_service.GetStreamUri(request)
            return res.Uri
        except Exception as e:
            logging.error(f"Failed to get stream URI for {profile_token}: {e}")
            return None
