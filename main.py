import sys
import msvc_runtime
import logging
import os
import signal
import subprocess

# --- HOTFIX FOR WINDOWS QT PLUGIN CRASH ---
base_dir = os.path.dirname(os.path.abspath(__file__))
venv_dir = os.path.join(base_dir, ".venv")
qt_plugin_path = os.path.join(venv_dir, "Lib", "site-packages", "PyQt6", "plugins")
# os.environ["QT_PLUGIN_PATH"] = qt_plugin_path
# os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(qt_plugin_path, "platforms")
# ------------------------------------------

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.config_manager import ConfigManager

def setup_logging():
    log_dir = os.path.expanduser("~/CCTVViewer/logs")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "app.log")),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("Starting Onsite Agent Application...")

def ensure_single_instance():
    """
    Ensures only one instance of the app is running.
    Kills the old instance if it exists.
    """
    pid_file = os.path.expanduser("~/CCTVViewer/app.pid")
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    
    current_pid = os.getpid()
    
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            
            # Check if old process is still running
            # In Windows, we can use TASKLIST or just try to signal it
            # But taskkill /PID is more reliable for killing
            if old_pid != current_pid:
                # Use taskkill to kill the old PID
                subprocess.run(['taskkill', '/F', '/PID', str(old_pid)], 
                              capture_output=True)
                logging.info(f"Terminated old instance (PID: {old_pid})")
        except Exception as e:
            # If the PID is not found or other error, ignore
            pass
            
    # Save the current PID
    try:
        with open(pid_file, "w") as f:
            f.write(str(current_pid))
    except Exception as e:
        logging.error(f"Failed to save PID file: {e}")

def main():
    setup_logging()
    ensure_single_instance()
    
    app = QApplication(sys.argv)
    app.setApplicationName("Onsite Agent")
    
    # Load Stylesheet
    try:
        style_path = os.path.join(os.path.dirname(__file__), "ui", "styles.qss")
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        logging.error(f"Failed to load stylesheet: {e}")
    
    config_manager = ConfigManager()
    
    window = MainWindow(config_manager)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
