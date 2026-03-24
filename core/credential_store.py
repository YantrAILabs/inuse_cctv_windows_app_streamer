import keyring
import logging

class CredentialStore:
    """
    Saves and loads camera credentials securely using Windows DPAPI (via keyring).
    """
    SERVICE_NAME = "CCTVViewer"

    @staticmethod
    def save_credentials(ip, username, password):
        try:
            keyring.set_password(CredentialStore.SERVICE_NAME, f"{ip}_user", username)
            keyring.set_password(CredentialStore.SERVICE_NAME, f"{ip}_pass", password)
            return True
        except Exception as e:
            logging.error(f"Failed to save credentials for {ip}: {e}")
            return False

    @staticmethod
    def load_credentials(ip):
        try:
            username = keyring.get_password(CredentialStore.SERVICE_NAME, f"{ip}_user")
            password = keyring.get_password(CredentialStore.SERVICE_NAME, f"{ip}_pass")
            if username and password:
                return username, password
        except Exception as e:
            logging.error(f"Failed to load credentials for {ip}: {e}")
        return None, None

    @staticmethod
    def delete_credentials(ip):
        try:
            keyring.delete_password(CredentialStore.SERVICE_NAME, f"{ip}_user")
            keyring.delete_password(CredentialStore.SERVICE_NAME, f"{ip}_pass")
            return True
        except Exception as e:
            logging.error(f"Failed to delete credentials for {ip}: {e}")
            return False
