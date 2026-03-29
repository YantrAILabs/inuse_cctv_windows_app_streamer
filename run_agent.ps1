$projectDir = "C:\Users\WELCOME\Desktop\DO NOT DELETE MOHIT FOLDER\inuse_cctv_windows_app_streamer"
cd $projectDir

# Definitive fix for 'no Qt platform plugin could be initialized'
$env:QT_QPA_PLATFORM_PLUGIN_PATH = "$projectDir\.venv\Lib\site-packages\PySide6\plugins"
$env:QT_PLUGIN_PATH = "$projectDir\.venv\Lib\site-packages\PySide6\plugins"
$env:PATH = "$projectDir\.venv\Lib\site-packages\PySide6;" + $env:PATH

# Check if MediaMTX is running
if (!(Get-Process mediamtx -ErrorAction SilentlyContinue)) {
    Write-Host "Starting MediaMTX..."
    Start-Process -FilePath ".\.mediamtx\mediamtx.exe" -WorkingDirectory ".\.mediamtx" -WindowStyle Hidden
}

Write-Host "Launching CCTV Agent..."
& ".\.venv\Scripts\python.exe" "main.py" 2>&1 > "launch_debug.log"
