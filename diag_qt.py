import os, sys, subprocess
env = os.environ.copy()
env['QT_DEBUG_PLUGINS'] = '1'
try:
    p = subprocess.run([sys.executable, '-c', 'from PyQt6.QtWidgets import QApplication; app=QApplication([])'], env=env, capture_output=True, text=True, timeout=8)
    print("=== STDOUT ===")
    print(p.stdout)
    print("=== STDERR ===")
    print(p.stderr)
except subprocess.TimeoutExpired as e:
    print("Timeout expired!")
    if e.stdout: print("STDOUT:", e.stdout.decode('utf-8', errors='ignore'))
    if e.stderr: print("STDERR:", e.stderr.decode('utf-8', errors='ignore'))
