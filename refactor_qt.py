import os
import glob

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace('PyQt6', 'PyQt6')
    new_content = new_content.replace('from PyQt6.QtCore import Qt, pyqtSignal as Signal', 'from PyQt6.QtCore import Qt, pyqtSignal as Signal')
    new_content = new_content.replace('from PyQt6.QtCore import Qt, QThread, pyqtSignal as Signal', 'from PyQt6.QtCore import Qt, QThread, pyqtSignal as Signal')
    new_content = new_content.replace('from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QSize', 'from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QSize')
    new_content = new_content.replace('from PyQt6.QtCore import Qt, pyqtSignal as Signal, QThread, QTimer', 'from PyQt6.QtCore import Qt, pyqtSignal as Signal, QThread, QTimer')
    
    # Catch any remaining standalone Signal imports
    if 'import Signal' in new_content and 'pyqtSignal as Signal' not in new_content:
        new_content = new_content.replace('import Signal', 'import pyqtSignal as Signal')
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('.'):
    for dir in ['.venv', '.git', '__pycache__']:
        if dir in dirs:
            dirs.remove(dir)
    for file in files:
        if file.endswith('.py'):
            replace_in_file(os.path.join(root, file))

print("Done replacing PyQt6 with PyQt6")
