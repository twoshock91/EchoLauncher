# settings_dialog.py
import os, shutil
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QWidget, QCheckBox, QListWidget, QPushButton, QHBoxLayout, QMessageBox, QLabel, QDialogButtonBox
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle("Настройки EchoLauncher")
        self.setModal(True)
        self.resize(500, 400)
        self.cfg = config.copy()
        self.result_config = None
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Общие настройки
        general_tab = QWidget()
        tabs.addTab(general_tab, "Общие")
        g_layout = QVBoxLayout(general_tab)
        self.discord_check = QCheckBox("Включить Discord RPC")
        self.discord_check.setChecked(self.cfg.get("discord_rpc", True))
        g_layout.addWidget(self.discord_check)
        g_layout.addStretch()

        # Управление установленными версиями
        versions_tab = QWidget()
        tabs.addTab(versions_tab, "Версии")
        v_layout = QVBoxLayout(versions_tab)
        v_layout.addWidget(QLabel("Установленные версии:"))
        self.versions_list = QListWidget()
        self.refresh_versions_list()
        v_layout.addWidget(self.versions_list)

        btn_layout = QHBoxLayout()
        self.delete_version_btn = QPushButton("Удалить выбранную")
        self.delete_version_btn.clicked.connect(self.delete_selected_version)
        btn_layout.addWidget(self.delete_version_btn)
        self.refresh_btn = QPushButton("Обновить список")
        self.refresh_btn.clicked.connect(self.refresh_versions_list)
        btn_layout.addWidget(self.refresh_btn)
        v_layout.addLayout(btn_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def refresh_versions_list(self):
        self.versions_list.clear()
        vers_dir = os.path.join(os.getcwd(), "minecraft", "versions")
        if os.path.exists(vers_dir):
            for v in sorted(os.listdir(vers_dir)):
                if os.path.isdir(os.path.join(vers_dir, v)):
                    self.versions_list.addItem(v)

    def delete_selected_version(self):
        selected = self.versions_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "Удаление", "Выберите версию для удаления.")
            return
        version = selected.text()
        reply = QMessageBox.question(self, "Подтверждение", f"Удалить версию {version}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            version_dir = os.path.join(os.getcwd(), "minecraft", "versions", version)
            try:
                shutil.rmtree(version_dir)
                self.refresh_versions_list()
                QMessageBox.information(self, "Удаление", "Версия удалена.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")

    def accept(self):
        self.result_config = self.cfg.copy()
        self.result_config["discord_rpc"] = self.discord_check.isChecked()
        super().accept()
