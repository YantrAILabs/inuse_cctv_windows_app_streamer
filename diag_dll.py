import ctypes
import os

plugin_path = r"C:\Users\WELCOME\Desktop\DO NOT DELETE MOHIT FOLDER\inuse_cctv_windows_app_streamer\.venv\Lib\site-packages\PyQt6\Qt6\plugins\platforms\qwindows.dll"
if not os.path.exists(plugin_path):
    print(f"File {plugin_path} does not exist!")
else:
    try:
        ctypes.WinDLL(plugin_path)
        print("Successfully loaded qwindows.dll!")
    except OSError as e:
        print(f"Failed to load qwindows.dll: {e}")
