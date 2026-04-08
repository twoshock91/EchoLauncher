# updater.py
import os
import sys
import tempfile
import subprocess
import requests
import gdown
from packaging import version

class DriveUpdater:
    def __init__(self, version_file_id, exe_file_id, current_version):
        """
        version_file_id: ID файла version.txt на Google Drive
        exe_file_id: ID файла EchoLauncher.exe на Google Drive
        current_version: текущая версия лаунчера (строка)
        """
        self.version_url = f"https://drive.google.com/uc?export=download&id={version_file_id}"
        self.exe_url = f"https://drive.google.com/uc?export=download&id={exe_file_id}"
        self.current_version = current_version

    def get_latest_version(self):
        """Скачивает version.txt и возвращает строку с версией."""
        try:
            resp = requests.get(self.version_url, timeout=5)
            if resp.status_code == 200:
                return resp.text.strip()
        except Exception as e:
            print(f"Ошибка получения версии: {e}")
        return None

    def download_new_exe(self, dest_path):
        """Скачивает новый exe по пути dest_path."""
        try:
            gdown.download(self.exe_url, dest_path, quiet=False)
            return True
        except Exception as e:
            print(f"Ошибка скачивания: {e}")
            return False

    def apply_update(self, new_exe_path, current_exe):
        """Заменяет текущий exe на новый и перезапускает лаунчер."""
        updater_script = f'''
import os, time, sys, subprocess
time.sleep(2)
try:
    os.remove(r"{current_exe}")
except:
    pass
os.rename(r"{new_exe_path}", r"{current_exe}")
subprocess.Popen([r"{current_exe}"])
'''
        script_path = os.path.join(tempfile.gettempdir(), "echolauncher_updater.py")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(updater_script)
        subprocess.Popen([sys.executable, script_path])
        sys.exit(0)
