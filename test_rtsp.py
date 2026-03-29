import cv2
import time

url = "rtsp://admin:Puran234@192.168.1.34:554/Streaming/Channels/101"
print(f"Connecting to {url}...")

cap = cv2.VideoCapture(url)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    print("FAILED: Could not open RTSP stream with OpenCV")
    # Try with TCP transport
    print("Retrying with CAP_PROP_OPEN_TIMEOUT_MSEC...")
    os_env = {"OPENCV_FFMPEG_CAPTURE_OPTIONS": "rtsp_transport;tcp"}
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        print("FAILED: Could not open even with FFmpeg backend")
    else:
        print("SUCCESS: Opened with FFmpeg backend")
else:
    print("SUCCESS: Stream opened!")

ret, frame = cap.read()
if ret:
    print(f"Got frame: {frame.shape}")
else:
    print("FAILED: Could not read frame")

cap.release()
print("Done")
