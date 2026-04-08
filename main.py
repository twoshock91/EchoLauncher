# main.py
import sys
from PySide6.QtWidgets import QApplication
from utils import excepthook
from version_loader import VersionLoader
from launcher import MainWindow

def main():
    app = QApplication(sys.argv)
    loader = VersionLoader()
    loader.finished.connect(lambda vers: run_main_window(vers))
    loader.error.connect(lambda e: print(e))
    loader.run()
    sys.exit(app.exec())

def run_main_window(versions):
    window = MainWindow(versions)
    window.show()

if __name__ == "__main__":
    sys.excepthook = excepthook
    main()
