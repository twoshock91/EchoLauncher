# launcher.py (полная версия с автообновлением)
import sys, os, json, threading, subprocess, time, fnmatch, tempfile
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QTextCursor, QImageReader

from utils import log_error, find_bg, generate_client_token, get_java_version, required_java_version, find_java_for_version, suggest_java_for_version
from mods_tab import ModsTab
from settings_dialog import SettingsDialog
from updater import DriveUpdater

try:
    from pypresence import Presence
    DISCORD = True
except:
    DISCORD = False

from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.command import get_minecraft_command
from minecraft_launcher_lib.fabric import install_fabric, is_minecraft_version_supported, get_latest_loader_version as get_latest_fabric
from minecraft_launcher_lib.forge import install_forge_version, find_forge_version

class MainWindow(QMainWindow):
    status_signal = Signal(str)
    progress_signal = Signal(bool)
    update_available = Signal(str, object)   # для автообновления

    def __init__(self, versions):
        super().__init__()
        self.versions = versions
        self.setWindowTitle("EchoLauncher")
        self.setFixedSize(900,600)
        self.minecraft_dir = os.path.join(os.getcwd(),"minecraft")
        os.makedirs(self.minecraft_dir, exist_ok=True)
        self.mods_dir = os.path.join(self.minecraft_dir,"mods")
        os.makedirs(self.mods_dir, exist_ok=True)
        self.cfg_file = "config.json"
        self.cfg = self.load_config()
        self.discord = None
        self.discord_connected = False
        self.update_discord_connection()
        self.game_status = "Minecraft не запущен"
        self.current_ver = None
        threading.Thread(target=self._discord_loop, daemon=True).start()
        self.setup_ui()
        self.status_signal.connect(lambda m: (self.console.moveCursor(QTextCursor.End), self.console.insertPlainText(m+'\n'), self.console.moveCursor(QTextCursor.End)))
        self.progress_signal.connect(self.toggle_progress)
        self.update_available.connect(self._on_update_available)
        self.update_stats_display()
        # Проверка обновлений в фоне
        self.check_for_updates()

    def update_discord_connection(self):
        if DISCORD and self.cfg.get("discord_rpc", True):
            try:
                self.discord = Presence(self.cfg.get("discord_client_id", "1482424006161207478"))
                self.discord.connect()
                self.discord_connected = True
            except Exception as e:
                log_error(e)
                self.discord_connected = False
        else:
            self.discord_connected = False

    def _discord_loop(self):
        while True:
            if self.discord_connected:
                try:
                    self.discord.update(state=self.game_status, details=f"Minecraft {self.current_ver}" if self.current_ver else "Ожидание",
                                        large_image="logo", large_text="EchoLauncher", start=int(time.time()))
                except: pass
            time.sleep(15)

    def load_config(self):
        default = {
            "username": "EchoPlayer",
            "ram": 2048,
            "mod_loader": "none",
            "discord_rpc": True,
            "discord_client_id": "1482424006161207478",
            "account_type": "offline",
            "elyby_login": "",
            "elyby_password": "",
            "elyby_token": None,
            "elyby_username": "",
            "elyby_uuid": "",
            "client_token": generate_client_token(),
            "total_playtime": 0,
            "last_session": 0,
            "launcher_version": "0.6.2"   # текущая версия лаунчера
        }
        try:
            with open(self.cfg_file,'r',encoding='utf-8') as f:
                cfg = json.load(f)
                for k in default:
                    cfg.setdefault(k, default[k])
                if "client_token" not in cfg:
                    cfg["client_token"] = generate_client_token()
                return cfg
        except:
            return default

    def save_config(self):
        with open(self.cfg_file,'w',encoding='utf-8') as f:
            json.dump(self.cfg, f, indent=4)

    def format_time(self, seconds):
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} мин."
        else:
            hours = seconds / 3600
            return f"{hours:.1f} ч."

    def update_stats_display(self):
        total = self.cfg.get("total_playtime", 0)
        last = self.cfg.get("last_session", 0)
        self.total_label.setText(f"📊 Общее время: {self.format_time(total)}")
        self.last_label.setText(f"🕒 Последний сеанс: {self.format_time(last)}")

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0,0,0,0)

        self.bg = QLabel(central)
        self.bg.setGeometry(0, 0, self.width(), self.height())
        self.bg.lower()
        self.load_background()

        self.overlay = QWidget(central)
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setAttribute(Qt.WA_TranslucentBackground)

        self.notebook = QTabWidget()
        self.notebook.setStyleSheet("""
            QTabWidget::pane { background: rgba(30,30,30,200); border: none; }
            QTabBar::tab { background: rgba(40,40,40,180); color: white; padding: 8px 16px; margin-right: 2px; border-radius: 5px; }
            QTabBar::tab:selected { background: rgba(60,60,60,220); }
            QTabBar::tab:hover { background: rgba(50,50,50,200); }
        """)

        tab_launcher = QWidget()
        tab_launcher.setAttribute(Qt.WA_TranslucentBackground)
        self.notebook.addTab(tab_launcher, "Запуск")

        self.tab_mods = ModsTab(self.mods_dir)
        self.tab_mods.setAttribute(Qt.WA_TranslucentBackground)
        self.notebook.addTab(self.tab_mods, "Моды")

        tab_settings = QWidget()
        tab_settings.setAttribute(Qt.WA_TranslucentBackground)
        self.notebook.addTab(tab_settings, "Настройки")

        launcher_layout = QHBoxLayout(tab_launcher)
        launcher_layout.setContentsMargins(20, 20, 20, 20)

        # Левая панель: статистика + консоль
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.setSpacing(10)

        self.stats_panel = QFrame()
        self.stats_panel.setStyleSheet("background:rgba(255,255,255,50); border:2px solid white; border-radius:10px;")
        self.stats_panel.setFixedHeight(80)
        stats_inner = QVBoxLayout(self.stats_panel)
        stats_inner.setContentsMargins(10,10,10,10)
        self.total_label = QLabel("📊 Общее время: 0 мин.")
        self.total_label.setStyleSheet("color:white; font-size:13px; background:transparent;")
        self.last_label = QLabel("🕒 Последний сеанс: 0 мин.")
        self.last_label.setStyleSheet("color:white; font-size:13px; background:transparent;")
        stats_inner.addWidget(self.total_label)
        stats_inner.addWidget(self.last_label)
        left_layout.addWidget(self.stats_panel)

        self.console_panel = QFrame()
        self.console_panel.setStyleSheet("background:rgba(255,255,255,50); border:2px solid white; border-radius:10px;")
        console_layout = QVBoxLayout(self.console_panel)
        console_layout.addWidget(QLabel("Информация", styleSheet="color:white; font-size:16px; background:transparent;"))
        self.console = QTextEdit(readOnly=True, styleSheet="background:rgba(0,0,0,100); border:1px solid white; color:white; font:11px Consolas;")
        console_layout.addWidget(self.console)
        left_layout.addWidget(self.console_panel)

        # Правая панель
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("background:rgba(255,255,255,50); border:2px solid white; border-radius:10px;")
        self.right_panel.setMinimumWidth(300)
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(15,15,15,15)

        account_label = QLabel("Аккаунт:", styleSheet="color:white; font-size:14px; background:transparent;")
        layout.addWidget(account_label)
        self.account_combo = QComboBox()
        self.account_combo.setStyleSheet("background:rgba(255,255,255,100); border:1px solid white; color:white;")
        self.account_combo.currentIndexChanged.connect(self.on_account_selected)
        layout.addWidget(self.account_combo)

        self.offline_nick_widget = QWidget()
        offline_layout = QHBoxLayout(self.offline_nick_widget)
        offline_layout.addWidget(QLabel("Ник:", styleSheet="color:white; font-size:14px; background:transparent;"))
        self.offline_nick_edit = QLineEdit(self.cfg["username"])
        self.offline_nick_edit.setStyleSheet("background:rgba(255,255,255,100); border:1px solid white; color:white;")
        offline_layout.addWidget(self.offline_nick_edit)
        layout.addWidget(self.offline_nick_widget)

        self.elyby_button = QPushButton("Войти в Ely.by")
        self.elyby_button.setStyleSheet("background:rgba(255,255,255,100); border:1px solid white; border-radius:3px; color:white; padding:5px;")
        self.elyby_button.clicked.connect(self.elyby_action)
        layout.addWidget(self.elyby_button)
        self.elyby_button.hide()

        ram_box = QHBoxLayout()
        ram_box.addWidget(QLabel("RAM (MB):", styleSheet="color:white; font-size:14px; background:transparent;"))
        self.ram_spin = QSpinBox(minimum=512, maximum=16384, value=self.cfg["ram"], singleStep=256,
                                  styleSheet="background:rgba(255,255,255,100); border:1px solid white; color:white;")
        ram_box.addWidget(self.ram_spin)
        layout.addLayout(ram_box)

        ver_box = QHBoxLayout()
        ver_box.addWidget(QLabel("Версия:", styleSheet="color:white; font-size:14px; background:transparent;"))
        self.ver_combo = QComboBox(styleSheet="background:rgba(255,255,255,100); border:1px solid white; color:white;")
        self.ver_combo.addItems(self.versions)
        ver_box.addWidget(self.ver_combo)
        layout.addLayout(ver_box)

        loader_box = QHBoxLayout()
        loader_box.addWidget(QLabel("Мод-лоадер:", styleSheet="color:white; font-size:14px; background:transparent;"))
        self.mod_loader_combo = QComboBox(styleSheet="background:rgba(255,255,255,100); border:1px solid white; color:white;")
        self.mod_loader_combo.addItem("Без модов", "none")
        self.mod_loader_combo.addItem("Fabric", "fabric")
        self.mod_loader_combo.addItem("Forge", "forge")
        idx = self.mod_loader_combo.findData(self.cfg["mod_loader"])
        if idx >= 0: self.mod_loader_combo.setCurrentIndex(idx)
        loader_box.addWidget(self.mod_loader_combo)
        layout.addLayout(loader_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background:rgba(255,255,255,100); border:1px solid white; border-radius:5px; color:white; } QProgressBar::chunk { background:white; }")
        layout.addWidget(self.progress_bar)

        self.launch_btn = QPushButton("ЗАПУСТИТЬ", styleSheet="""
            QPushButton{background:rgba(255,255,255,150); border:2px solid white; border-radius:5px; color:black; font-size:16px; padding:8px;}
            QPushButton:hover{background:rgba(255,255,255,200);}
            QPushButton:disabled{background:rgba(150,150,150,150); color:#666;}
        """)
        self.launch_btn.clicked.connect(self.launch)
        layout.addWidget(self.launch_btn)

        self.open_folder_btn = QPushButton("📂 Открыть папку Minecraft", styleSheet="""
            QPushButton{background:rgba(255,255,255,100); border:1px solid white; border-radius:5px; color:white; font-size:12px; padding:5px;}
            QPushButton:hover{background:rgba(255,255,255,150);}
        """)
        self.open_folder_btn.clicked.connect(lambda: os.startfile(self.minecraft_dir) if os.path.exists(self.minecraft_dir) else None)
        layout.addWidget(self.open_folder_btn)

        self.settings_btn = QPushButton("⚙️ Настройки", styleSheet="""
            QPushButton{background:rgba(255,255,255,100); border:1px solid white; border-radius:5px; color:white; font-size:12px; padding:5px;}
            QPushButton:hover{background:rgba(255,255,255,150);}
        """)
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        layout.addWidget(self.settings_btn)

        launcher_layout.addWidget(left_panel)
        launcher_layout.addWidget(self.right_panel)

        # Вкладка настроек
        settings_layout = QVBoxLayout(tab_settings)
        settings_layout.addWidget(QLabel("Настройки приложения", styleSheet="color:white; font-size:16px;"))
        open_settings_btn = QPushButton("Открыть диалог настроек")
        open_settings_btn.clicked.connect(self.open_settings_dialog)
        settings_layout.addWidget(open_settings_btn)
        settings_layout.addStretch()

        overlay_layout = QVBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(0,0,0,0)
        overlay_layout.addWidget(self.notebook)
        self.overlay.setLayout(overlay_layout)

        # Сохранение конфига при изменениях
        self.offline_nick_edit.textChanged.connect(self.save_offline_config)
        self.ram_spin.valueChanged.connect(self.save_config)
        self.mod_loader_combo.currentIndexChanged.connect(self.save_config)
        self.ver_combo.currentIndexChanged.connect(self.save_config)

        self.refresh_account_list()
        self.on_account_selected(self.account_combo.currentIndex())

    def load_background(self):
        bg = find_bg()
        if bg:
            reader = QImageReader(bg)
            if reader.canRead():
                img = reader.read()
                if not img.isNull():
                    scaled = QPixmap.fromImage(img).scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    self.bg.setPixmap(scaled)
                    return
        self.bg.setStyleSheet("background:#2d2d2d;")

    def resizeEvent(self, e):
        self.bg.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.load_background()

    def refresh_account_list(self):
        self.account_combo.clear()
        offline_nick = self.cfg.get("username", "EchoPlayer")
        self.account_combo.addItem(f"Офлайн: {offline_nick}", "offline")
        if self.cfg.get("elyby_token") and self.cfg.get("elyby_username"):
            self.account_combo.addItem(f"Ely.by: {self.cfg['elyby_username']}", "elyby")
        self.account_combo.addItem("➕ Добавить Ely.by...", "add_elyby")
        current_type = self.cfg.get("account_type", "offline")
        for i in range(self.account_combo.count()):
            if self.account_combo.itemData(i) == current_type:
                self.account_combo.setCurrentIndex(i)
                break
        self.on_account_selected(self.account_combo.currentIndex())

    def on_account_selected(self, index):
        account_type = self.account_combo.itemData(index)
        if account_type == "offline":
            self.offline_nick_widget.show()
            self.elyby_button.hide()
            self.cfg["account_type"] = "offline"
        elif account_type == "elyby":
            self.offline_nick_widget.hide()
            self.elyby_button.setText("Выйти из Ely.by")
            self.elyby_button.show()
            self.cfg["account_type"] = "elyby"
        elif account_type == "add_elyby":
            self.open_elyby_auth_dialog()
            self.account_combo.setCurrentIndex(self.account_combo.findData(self.cfg.get("account_type", "offline")))

    def save_offline_config(self):
        if self.account_combo.currentData() == "offline":
            self.cfg["username"] = self.offline_nick_edit.text()
            self.save_config()

    def save_config(self):
        self.cfg["ram"] = self.ram_spin.value()
        self.cfg["mod_loader"] = self.mod_loader_combo.currentData()
        self.cfg["last_version"] = self.ver_combo.currentText()
        with open(self.cfg_file,'w',encoding='utf-8') as f:
            json.dump(self.cfg, f, indent=4)

    # --- Ely.by ---
    def open_elyby_auth_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Вход в Ely.by")
        dlg.setModal(True)
        dlg.resize(300, 200)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Логин/E-mail:"))
        login_edit = QLineEdit()
        layout.addWidget(login_edit)

        layout.addWidget(QLabel("Пароль:"))
        pass_edit = QLineEdit()
        pass_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(pass_edit)

        btn_layout = QHBoxLayout()
        login_btn = QPushButton("Войти")
        cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(login_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def do_login():
            login = login_edit.text().strip()
            password = pass_edit.text().strip()
            if not login or not password:
                QMessageBox.warning(dlg, "Ошибка", "Введите логин и пароль")
                return
            self.authenticate_elyby(login, password, dlg)

        login_btn.clicked.connect(do_login)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def authenticate_elyby(self, login, password, parent_dlg=None):
        import urllib.request, urllib.parse, json
        if "client_token" not in self.cfg:
            self.cfg["client_token"] = generate_client_token()

        payload = {
            "username": login,
            "password": password,
            "clientToken": self.cfg["client_token"],
            "requestUser": True
        }
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request("https://authserver.ely.by/auth/authenticate", data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=10) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                access_token = resp_data.get("accessToken")
                client_token = resp_data.get("clientToken")
                selected_profile = resp_data.get("selectedProfile", {})
                if access_token and selected_profile:
                    uuid = selected_profile.get("id", "")
                    username = selected_profile.get("name", "")
                    self.cfg["elyby_token"] = access_token
                    self.cfg["client_token"] = client_token
                    self.cfg["elyby_username"] = username
                    self.cfg["elyby_uuid"] = uuid
                    self.cfg["elyby_login"] = login
                    self.cfg["account_type"] = "elyby"
                    self.save_config()
                    self.refresh_account_list()
                    if parent_dlg:
                        parent_dlg.accept()
                    QMessageBox.information(self, "Успех", f"Вы вошли как {username}")
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось получить данные профиля")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_body)
                error_msg = error_json.get("errorMessage", str(e))
            except:
                error_msg = error_body or str(e)
            if "two factor auth" in error_msg.lower():
                token_2fa, ok = QInputDialog.getText(self, "Двухфакторная аутентификация",
                                                      "Введите код из приложения-аутентификатора:")
                if ok and token_2fa:
                    password_with_token = f"{password}:{token_2fa}"
                    self.authenticate_elyby(login, password_with_token, parent_dlg)
                else:
                    QMessageBox.warning(self, "Ошибка", "Вход отменён")
            else:
                QMessageBox.critical(self, "Ошибка авторизации", f"Не удалось войти:\n{error_msg}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при авторизации:\n{str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def elyby_action(self):
        if self.cfg.get("elyby_token") and self.cfg.get("elyby_username"):
            self.cfg["elyby_token"] = None
            self.cfg["elyby_username"] = ""
            self.cfg["elyby_uuid"] = ""
            self.cfg["account_type"] = "offline"
            self.save_config()
            self.refresh_account_list()
            QMessageBox.information(self, "Выход", "Вы вышли из аккаунта Ely.by")
        else:
            self.open_elyby_auth_dialog()

    # --- Запуск игры ---
    def toggle_progress(self, show):
        self.progress_bar.setVisible(show)
        self.progress_bar.setRange(0, 100 if show else 0)
        if show:
            self.progress_bar.setValue(0)

    def launch(self):
        ver = self.ver_combo.currentText()
        if not ver or ver in ("Загрузка...","Ошибка загрузки"): return

        required = required_java_version(ver)
        java_path = find_java_for_version(required)
        if not java_path:
            suggest_java_for_version(required)
            return

        java_ver = get_java_version(java_path)
        if java_ver is None or java_ver < required:
            suggest_java_for_version(required)
            return

        if self.cfg.get("account_type") == "elyby" and self.cfg.get("elyby_username"):
            username = self.cfg["elyby_username"]
        else:
            username = self.offline_nick_edit.text().strip() or "EchoPlayer"

        loader = self.mod_loader_combo.currentData()
        ram = self.ram_spin.value()
        self.cfg["last_version"] = ver
        self.save_config()

        self.launch_btn.setEnabled(False)
        self.launch_btn.setText("ЗАПУСК...")
        self.progress_signal.emit(True)
        self.start_time = time.time()
        threading.Thread(target=self.run_game, args=(ver, username, ram, loader, java_path), daemon=True).start()

    def run_game(self, ver, username, ram, loader, java_path):
        self.game_status, self.current_ver = "Minecraft запускается...", ver
        try:
            if not self.is_installed(ver):
                self.status_signal.emit(f"📥 Установка {ver}...")
                install_minecraft_version(ver, self.minecraft_dir)
                self.status_signal.emit(f"✅ {ver} установлен")
            launch_ver = ver
            if loader == "fabric":
                fab = self.find_fabric(ver)
                if not fab:
                    self.status_signal.emit(f"🛠 Установка Fabric...")
                    if is_minecraft_version_supported(ver):
                        latest = get_latest_fabric()
                        install_fabric(ver, self.minecraft_dir, latest)
                        for _ in range(10):
                            time.sleep(1)
                            fab = self.find_fabric(ver)
                            if fab: break
                        if fab:
                            self.status_signal.emit(f"✅ Fabric: {fab}")
                        else:
                            self.status_signal.emit(f"⚠ Fabric не найден. Доступны: {', '.join(self.list_all_versions())}")
                    else:
                        self.status_signal.emit(f"⚠ Fabric не поддерживается")
                if fab:
                    launch_ver = fab
            elif loader == "forge":
                forge_ver = self.find_forge(ver)
                if not forge_ver:
                    self.status_signal.emit(f"🛠 Установка Forge...")
                    try:
                        forge_version = find_forge_version(ver)
                        if forge_version:
                            install_forge_version(forge_version, self.minecraft_dir)
                            for _ in range(10):
                                time.sleep(1)
                                forge_ver = self.find_forge(ver)
                                if forge_ver: break
                            if forge_ver:
                                self.status_signal.emit(f"✅ Forge: {forge_ver}")
                            else:
                                self.status_signal.emit(f"⚠ Forge установлен, но не найден. Доступны: {', '.join(self.list_all_versions())}")
                        else:
                            self.status_signal.emit(f"⚠ Forge не доступен для {ver}")
                    except Exception as e:
                        self.status_signal.emit(f"⚠ Ошибка установки Forge: {e}")
                if forge_ver:
                    launch_ver = forge_ver
            self.status_signal.emit(f"🚀 Запуск {launch_ver}...")
            options = {
                "username": username,
                "uuid": "",
                "token": "",
                "jvmArguments": [f"-Xmx{ram}M"],
                "gameDirectory": self.minecraft_dir,
                "launcherName": "EchoLauncher",
                "launcherVersion": self.cfg.get("launcher_version", "0.6.2"),
                "executablePath": java_path
            }
            proc = subprocess.run(get_minecraft_command(launch_ver, self.minecraft_dir, options), capture_output=True, text=True)
            self.status_signal.emit("✅ Игра завершена" if proc.returncode==0 else f"❌ Ошибка: {proc.stderr}")
        except Exception as e:
            log_error(e)
            self.status_signal.emit(f"❌ Ошибка: {str(e)}")
        finally:
            duration = int(time.time() - self.start_time)
            self.cfg["total_playtime"] += duration
            self.cfg["last_session"] = duration
            self.save_config()
            self.update_stats_display()
            self.status_signal.emit(f"🕒 Сеанс: {self.format_time(duration)}")

            self.game_status, self.current_ver = "Minecraft не запущен", None
            self.launch_btn.setEnabled(True)
            self.launch_btn.setText("ЗАПУСТИТЬ")
            self.progress_signal.emit(False)

    def is_installed(self, v):
        d = os.path.join(self.minecraft_dir,"versions",v)
        return os.path.exists(d) and os.path.exists(os.path.join(d,f"{v}.json"))

    def find_fabric(self, v):
        d = os.path.join(self.minecraft_dir,"versions")
        if not os.path.exists(d): return None
        cand = fnmatch.filter(os.listdir(d), f"fabric-loader-*-{v}")
        return sorted(cand)[-1] if cand else None

    def find_forge(self, v):
        d = os.path.join(self.minecraft_dir,"versions")
        if not os.path.exists(d): return None
        cand = [name for name in os.listdir(d) if 'forge' in name.lower() and v in name]
        return sorted(cand)[-1] if cand else None

    def list_all_versions(self):
        try: return os.listdir(os.path.join(self.minecraft_dir,"versions"))
        except: return []

    def open_settings_dialog(self):
        dlg = SettingsDialog(self, self.cfg)
        if dlg.exec():
            self.cfg = dlg.result_config
            self.save_config()
            self.update_discord_connection()
            self.update_stats_display()

    # --- Автообновление ---
    def check_for_updates(self):
        """Фоновая проверка обновлений через Google Drive."""
        def _check():
            version_file_id = "1zu8762x_t72KWyvdkfurxHqeuMtyMNff"  # ID для version.txt
            exe_file_id = "1gu3RFiPtEhpMv3nZxqBssKhJ3i0m17C0"   # замени на реальный ID твоего exe файла
            current_ver = self.cfg.get("launcher_version", "0.7.0")
            updater = DriveUpdater(version_file_id, exe_file_id, current_ver)
            latest = updater.get_latest_version()
            if latest and latest != current_ver:
                self.update_available.emit(latest, updater)

        thread = threading.Thread(target=_check)
        thread.daemon = True
        thread.start()

    def _on_update_available(self, latest_version, updater):
        reply = QMessageBox.question(self, "Доступно обновление",
                                     f"Версия {latest_version} уже здесь!\nУстановить сейчас?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            tmp_exe = tempfile.NamedTemporaryFile(delete=False, suffix='.exe').name
            if updater.download_new_exe(tmp_exe):
                updater.apply_update(tmp_exe, sys.argv[0])
