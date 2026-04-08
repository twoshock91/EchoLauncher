# mods_tab.py
import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QAbstractItemView, QLabel
from PySide6.QtCore import Qt

class ModsTab(QWidget):
    def __init__(self, mods_dir):
        super().__init__()
        self.mods_dir = mods_dir
        layout = QVBoxLayout()

        self.count_label = QLabel("Модов: 0")
        self.count_label.setStyleSheet("color: white; font-size: 14px;")
        layout.addWidget(self.count_label)

        open_btn = QPushButton("📁 Открыть папку модов")
        open_btn.setStyleSheet("background:rgba(255,255,255,100); border:1px solid white; border-radius:5px; color:white; padding:5px;")
        open_btn.clicked.connect(lambda: os.startfile(self.mods_dir) if os.path.exists(self.mods_dir) else None)
        layout.addWidget(open_btn)

        self.mod_list = QListWidget()
        self.mod_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.mod_list.setStyleSheet("background:rgba(0,0,0,100); border:1px solid white; color:white;")
        layout.addWidget(self.mod_list)

        btn_layout = QHBoxLayout()
        enable_btn = QPushButton("Включить")
        disable_btn = QPushButton("Отключить")
        delete_btn = QPushButton("Удалить")
        refresh_btn = QPushButton("Обновить")

        for btn in (enable_btn, disable_btn, delete_btn, refresh_btn):
            btn.setStyleSheet("background:rgba(255,255,255,100); border:1px solid white; border-radius:5px; color:white; padding:5px;")

        enable_btn.clicked.connect(lambda: self.toggle_mod(True))
        disable_btn.clicked.connect(lambda: self.toggle_mod(False))
        delete_btn.clicked.connect(self.delete_mod)
        refresh_btn.clicked.connect(self.refresh_mods)

        btn_layout.addWidget(enable_btn)
        btn_layout.addWidget(disable_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(refresh_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.refresh_mods()

    def refresh_mods(self):
        self.mod_list.clear()
        if not os.path.exists(self.mods_dir):
            os.makedirs(self.mods_dir, exist_ok=True)
        mod_count = 0
        for f in os.listdir(self.mods_dir):
            if f.endswith(".jar") or f.endswith(".jar.disabled"):
                full = os.path.join(self.mods_dir, f)
                if f.endswith(".jar.disabled"):
                    display_name = f.replace(".disabled", "")
                    status = "❌"
                else:
                    display_name = f
                    status = "✅"
                self.mod_list.addItem(f"{status} {display_name}")
                self.mod_list.item(self.mod_list.count()-1).setData(Qt.UserRole, full)
                mod_count += 1
        self.count_label.setText(f"Модов: {mod_count}")

    def toggle_mod(self, enable):
        item = self.mod_list.currentItem()
        if not item: return
        full_path = item.data(Qt.UserRole)
        if enable:
            if full_path.endswith(".jar.disabled"):
                new_path = full_path[:-8]
                os.rename(full_path, new_path)
        else:
            if full_path.endswith(".jar"):
                new_path = full_path + ".disabled"
                os.rename(full_path, new_path)
        self.refresh_mods()

    def delete_mod(self):
        item = self.mod_list.currentItem()
        if not item: return
        full_path = item.data(Qt.UserRole)
        base = full_path[:-8] if full_path.endswith(".jar.disabled") else full_path
        for f in [base, base + ".disabled"]:
            if os.path.exists(f):
                os.remove(f)
        self.refresh_mods()
