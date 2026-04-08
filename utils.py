# utils.py (исправленное – добавим функции для работы с Java с учётом версии Minecraft)

import sys, os, time, traceback, subprocess, secrets, webbrowser, re
from PySide6.QtWidgets import QMessageBox, QApplication

log_file = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd(), 'error.log')

def log_error(e):
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{time.ctime()}: {str(e)}\n{traceback.format_exc()}\n")

def excepthook(exc_type, exc_value, exc_traceback):
    log_error(exc_value)
    if QApplication.instance():
        QMessageBox.critical(None, "Критическая ошибка", f"Произошла ошибка:\n{exc_value}\n\nПодробности в файле {log_file}")
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def resource_path(rel):
    return os.path.join(sys._MEIPASS if getattr(sys,'frozen',False) else os.path.dirname(__file__), rel)

def find_bg():
    cand = [resource_path("bg.png"), os.path.join(os.getcwd(),"bg.png")]
    if getattr(sys,'frozen',False):
        cand.append(os.path.join(os.path.dirname(sys.executable),"bg.png"))
    return next((p for p in cand if os.path.exists(p)), None)

def get_java_version(java_path):
    try:
        output = subprocess.run([java_path, '-version'], capture_output=True, text=True)
        output_str = output.stderr + output.stdout
        match = re.search(r'version "([^"]+)"', output_str)
        if match:
            ver_str = match.group(1)
            if ver_str.startswith('1.'):
                major = int(ver_str.split('.')[1])
                return major
            else:
                major = int(ver_str.split('.')[0])
                return major
    except:
        pass
    return None

def required_java_version(mc_version):
    try:
        parts = mc_version.split('.')
        major = int(parts[0])
        minor = int(parts[1])
    except:
        return 21
    if major == 1 and minor >= 21:
        return 21
    if major == 1 and minor >= 18:
        return 17
    return 8

def find_java_for_version(required_version):
    """Возвращает путь к Java с версией >= required_version, если найдена, иначе None."""
    # Проверяем JAVA_HOME
    java_home = os.environ.get('JAVA_HOME')
    if java_home:
        path = os.path.join(java_home, 'bin', 'java.exe')
        if os.path.exists(path):
            ver = get_java_version(path)
            if ver is not None and ver >= required_version:
                return path
    # Ищем через where
    try:
        result = subprocess.run(['where', 'java'], capture_output=True, text=True, check=True)
        paths = result.stdout.strip().split('\n')
        for path in paths:
            path = path.strip()
            if path:
                ver = get_java_version(path)
                if ver is not None and ver >= required_version:
                    return path
    except:
        pass
    return None

def suggest_java_for_version(required_version):
    url = f"https://adoptium.net/temurin/releases/?version={required_version}"
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(f"Требуется Java {required_version}")
    msg.setText(f"Для выбранной версии Minecraft требуется Java {required_version} или выше.\nНе найдено подходящей Java.")
    msg.setInformativeText(f"Хотите перейти на страницу загрузки Java {required_version}?")
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.Yes)
    if msg.exec() == QMessageBox.Yes:
        webbrowser.open(url)

def generate_client_token():
    return secrets.token_hex(16)
