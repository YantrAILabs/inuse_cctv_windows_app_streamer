import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
venv_dir = os.path.join(base_dir, ".venv")
qt_plugin_path = os.path.join(venv_dir, "Lib", "site-packages", "PyQt6", "plugins")
os.environ["QT_PLUGIN_PATH"] = qt_plugin_path
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(qt_plugin_path, "platforms")

from PyQt6.QtWidgets import QApplication, QWidget

print("Initializing QApplication...")
try:
    app = QApplication(sys.argv)
    print("QApplication initialized.")
    if len(sys.argv) > 1 and sys.argv[1] == 'headless':
        print("Success.")
        sys.exit(0)
except Exception as e:
    print(f"Error: {e}")
