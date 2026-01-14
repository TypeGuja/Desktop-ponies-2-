import sys
import os
import subprocess
import threading
import time
import json
import tempfile
import urllib.request
import platform
from pathlib import Path
from datetime import datetime

# ========== ПРОВЕРКА И УСТАНОВКА PYSIDE6 ==========
try:
    from PySide6.QtWidgets import *
    from PySide6.QtCore import *
    from PySide6.QtGui import *

    QT_AVAILABLE = True
    QT_LIB = "PySide6"
    print("✓ PySide6 найден")
except ImportError:
    QT_AVAILABLE = False
    QT_LIB = None
    print("✗ PySide6 не найден, пробуем PyQt5...")

if not QT_AVAILABLE:
    try:
        from PyQt5.QtWidgets import *
        from PyQt5.QtCore import *
        from PyQt5.QtGui import *

        QT_AVAILABLE = True
        QT_LIB = "PyQt5"
        print("✓ PyQt5 найден")
    except ImportError:
        QT_AVAILABLE = False
        QT_LIB = None
        print("✗ PyQt5 не найден")

# Если ни одна библиотека не найдена, предлагаем установить
if not QT_AVAILABLE:
    print("\n⚠ GUI библиотеки не найдены!")
    print("Установите одну из библиотек:")
    print("1. pip install PySide6 (рекомендуется)")
    print("2. pip install PyQt5")

    # Пробуем автоматически установить PySide6
    try:
        print("\nПытаюсь установить PySide6 автоматически...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6"])
        from PySide6.QtWidgets import *
        from PySide6.QtCore import *
        from PySide6.QtGui import *

        QT_AVAILABLE = True
        QT_LIB = "PySide6"
        print("✓ PySide6 успешно установлен!")
    except:
        print("✗ Не удалось установить PySide6 автоматически")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

# ========== ОСТАЛЬНЫЕ ИМПОРТЫ ==========
try:
    import webbrowser

    WEBBROWSER_AVAILABLE = True
except ImportError:
    WEBBROWSER_AVAILABLE = False


# ========== НОВЫЙ БЛОК ДЛЯ РАБОТЫ С ПУТЯМИ В EXE ==========
def get_base_path():
    """Получить базовый путь в зависимости от режима (скрипт или exe)"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return base_path


def find_file_relative(base_path, relative_path):
    """Найти файл относительно базового пути"""
    path = os.path.join(base_path, relative_path)

    if os.path.exists(path):
        return os.path.abspath(path)

    # Пробуем найти в родительских директориях
    parent_dir = os.path.dirname(base_path)
    attempts = 0
    while attempts < 3 and parent_dir:
        path = os.path.join(parent_dir, relative_path)
        if os.path.exists(path):
            return os.path.abspath(path)
        parent_dir = os.path.dirname(parent_dir)
        attempts += 1

    # Возвращаем путь даже если файл не существует (для отладки)
    return os.path.abspath(os.path.join(base_path, relative_path))


# Получаем базовый путь
BASE_PATH = get_base_path()

# Прописываем пути относительно базового пути
CLIENT_FILE = find_file_relative(BASE_PATH, r"DPP2serverUDP\Client\main.py")
CLIENT_OFFLINE_FILE = find_file_relative(BASE_PATH, r"DPP2.py")
SERVER_FILE = find_file_relative(BASE_PATH, r"DPP2serverUDP\Server\main.py")

print(f"Base path: {BASE_PATH}")
print(f"Client file: {CLIENT_FILE}")
print(f"Client offline file: {CLIENT_OFFLINE_FILE}")
print(f"Server file: {SERVER_FILE}")


# ========== КОНСТАНТЫ ДИЗАЙНА ==========
class Colors:
    """Цветовые схемы"""

    BLACK = {
        'DARK_BG': '#0a0a14',
        'DARKER_BG': '#05050a',
        'CARD_BG': '#151522',
        'TEXT_MAIN': '#ffffff',
        'ACCENT': '#00d4ff',
        'BTN_CLIENT': '#00ff88',
        'BTN_SERVER': '#00d4ff',
        'BTN_ALL': '#ff6b9d',
        'BTN_CLIENT_OFFLINE': '#8888aa',
        'BTN_SETTINGS': '#9d4edd',
        'WINDOW_BG': '#0a0a14',
        'TITLE_BAR': '#05050a',
        'TITLE_TEXT': '#ffffff',
        'ACCENT_HOVER': '#40e0ff',
        'ACCENT_LIGHT': '#202840',
        'BORDER': '#303050',
        'SUCCESS': '#00ff88',
        'ERROR': '#ff4444',
        'WARNING': '#ffaa00'
    }

    GRAY = {
        'DARK_BG': '#1a1a1a',
        'DARKER_BG': '#0d0d0d',
        'CARD_BG': '#2d2d2d',
        'TEXT_MAIN': '#e6e6e6',
        'ACCENT': '#4d4d4d',
        'BTN_CLIENT': '#2ecc71',
        'BTN_SERVER': '#3498db',
        'BTN_ALL': '#e74c3c',
        'BTN_CLIENT_OFFLINE': '#95a5a6',
        'BTN_SETTINGS': '#9b59b6',
        'WINDOW_BG': '#1a1a1a',
        'TITLE_BAR': '#0d0d0d',
        'TITLE_TEXT': '#e6e6e6',
        'ACCENT_HOVER': '#6d6d6d',
        'ACCENT_LIGHT': '#3a3a3a',
        'BORDER': '#404040',
        'SUCCESS': '#2ecc71',
        'ERROR': '#e74c3c',
        'WARNING': '#f39c12'
    }

    WHITE = {
        'DARK_BG': '#f0f0f0',
        'DARKER_BG': '#e0e0e0',
        'CARD_BG': '#ffffff',
        'TEXT_MAIN': '#333333',
        'ACCENT': '#007acc',
        'BTN_CLIENT': '#28a745',
        'BTN_SERVER': '#17a2b8',
        'BTN_ALL': '#dc3545',
        'BTN_CLIENT_OFFLINE': '#6c757d',
        'BTN_SETTINGS': '#6f42c1',
        'WINDOW_BG': '#f0f0f0',
        'TITLE_BAR': '#e0e0e0',
        'TITLE_TEXT': '#333333',
        'ACCENT_HOVER': '#0099e6',
        'ACCENT_LIGHT': '#cce5ff',
        'BORDER': '#cccccc',
        'SUCCESS': '#28a745',
        'ERROR': '#dc3545',
        'WARNING': '#ffc107'
    }

    def __init__(self):
        self.current_theme = 'BLACK'
        self.themes = {
            'BLACK': self.BLACK,
            'GRAY': self.GRAY,
            'WHITE': self.WHITE
        }

    def get_current(self):
        return self.themes[self.current_theme]

    def set_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False


# Список необходимых библиотек (обновленный)
REQUIRED_LIBRARIES = [
    'pygame==2.5.2',
    'numpy==1.24.3',
    'Pillow==9.5.0',
    'requests==2.31.0',
    'cryptography==41.0.7',
    'PySide6==6.6.0' if QT_LIB == "PySide6" else 'PyQt5==5.15.9',
]


class ModernButton(QPushButton):
    """Современная кнопка с анимацией и эффектами"""

    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.hover_color = self._adjust_color(color, 50)
        self.press_color = self._adjust_color(color, -30)

        self.setFixedHeight(50)
        self.setMinimumWidth(250)

        # Создаем внутренний виджет для содержимого
        self.content_widget = QWidget(self)
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 0, 20, 0)

        self.label = QLabel(text)
        self.arrow = QLabel("→")

        self.content_layout.addWidget(self.label)
        self.content_layout.addStretch()
        self.content_layout.addWidget(self.arrow)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 0px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}20;
                border-color: {self.hover_color};
            }}
            QPushButton:pressed {{
                background-color: {color}40;
                border-color: {self.press_color};
            }}
        """)

        # Стили для внутренних элементов
        self.label.setStyleSheet(f"color: {color}; font-weight: bold; background: transparent;")
        self.arrow.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 16px; background: transparent;")
        self.content_widget.setStyleSheet("background: transparent;")

        self.setCursor(Qt.CursorShape.PointingHandCursor if QT_LIB == "PySide6" else Qt.PointingHandCursor)

    def resizeEvent(self, event):
        """Переопределяем resizeEvent для позиционирования внутреннего виджета"""
        super().resizeEvent(event)
        self.content_widget.setGeometry(0, 0, self.width(), self.height())

    def _adjust_color(self, color, delta):
        """Корректировка цвета для hover/pressed эффектов"""
        if color.startswith('#'):
            r = int(color[1:3], 16) + delta
            g = int(color[3:5], 16) + delta
            b = int(color[5:7], 16) + delta

            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            return f'#{r:02x}{g:02x}{b:02x}'
        return color


class SettingsDialog(QDialog):
    """Диалоговое окно настроек"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Settings")
        self.setFixedSize(500, 500)
        self.setModal(True)

        # Основной layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # Раздел: Общие настройки
        general_group = QGroupBox("General Settings")
        general_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #303050;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        general_layout = QVBoxLayout(general_group)
        general_layout.setSpacing(10)

        # Developer Mode
        self.dev_checkbox = QCheckBox("Developer Mode")
        self.dev_checkbox.setChecked(self.parent.settings['developer_mode'])
        general_layout.addWidget(self.dev_checkbox)

        dev_label = QLabel("Shows Server and Start All buttons")
        dev_label.setStyleSheet("color: #888888; margin-left: 20px;")
        general_layout.addWidget(dev_label)

        # Auto-check environment
        self.auto_check_checkbox = QCheckBox("Auto-check environment on startup")
        self.auto_check_checkbox.setChecked(self.parent.settings.get('auto_check_environment', True))
        general_layout.addWidget(self.auto_check_checkbox)

        auto_check_label = QLabel("Automatically check Python and libraries on launch")
        auto_check_label.setStyleSheet("color: #888888; margin-left: 20px;")
        general_layout.addWidget(auto_check_label)

        general_layout.addStretch()

        # Раздел: Темы
        theme_group = QGroupBox("Appearance")
        theme_group.setStyleSheet(general_group.styleSheet())

        theme_layout = QVBoxLayout(theme_group)
        theme_layout.setSpacing(10)

        theme_label = QLabel("Color Theme:")
        theme_label.setStyleSheet("font-weight: bold;")
        theme_layout.addWidget(theme_label)

        # ComboBox для выбора темы
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Black", "Gray", "White"])
        current_theme = self.parent.colors.current_theme
        self.theme_combo.setCurrentText(current_theme.title())

        # Стилизация ComboBox
        self.theme_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #303050;
                border-radius: 4px;
                padding: 5px;
                background: #151522;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #303050;
                background: #151522;
                color: white;
                selection-background-color: #00d4ff;
            }
        """)

        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        layout.addWidget(general_group)
        layout.addWidget(theme_group)

        # Кнопки
        button_layout = QHBoxLayout()

        save_btn = ModernButton("Apply & Save", "#00ff88")
        save_btn.clicked.connect(self.apply_settings)

        cancel_btn = ModernButton("Cancel", "#8888aa")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def apply_settings(self):
        """Применение настроек"""
        self.parent.settings['developer_mode'] = self.dev_checkbox.isChecked()
        self.parent.settings['auto_check_environment'] = self.auto_check_checkbox.isChecked()

        theme_map = {"Black": "BLACK", "Gray": "GRAY", "White": "WHITE"}
        theme = theme_map[self.theme_combo.currentText()]
        self.parent.settings['theme'] = theme

        self.parent.save_settings()
        self.parent.apply_settings_changes()
        self.accept()


class InstallationWizard(QDialog):
    """Мастер установки Python и библиотек"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.python_installer = PythonInstaller()
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Environment Setup Wizard")
        self.setFixedSize(600, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Заголовок
        title = QLabel("Environment Setup")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter if QT_LIB == "PySide6" else Qt.AlignCenter)
        layout.addWidget(title)

        # Info frame
        self.info_frame = QFrame()
        self.info_frame.setFrameStyle(QFrame.Shape.Box if QT_LIB == "PySide6" else QFrame.Box)
        layout.addWidget(self.info_frame)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Log text
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)

        # Кнопки
        button_layout = QHBoxLayout()

        self.check_btn = ModernButton("Check Environment", "#00ff88")
        self.check_btn.clicked.connect(self.start_check)

        close_btn = ModernButton("Close", "#8888aa")
        close_btn.clicked.connect(self.close)

        button_layout.addWidget(self.check_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # Запуск проверки при открытии
        QTimer.singleShot(100, self.start_check)

    def log_message(self, message, color=None):
        """Добавление сообщения в лог"""
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End if QT_LIB == "PySide6" else QTextCursor.End)

        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"

        self.log_text.setTextCursor(cursor)
        self.log_text.insertPlainText(full_message)

        # Прокрутка вниз
        cursor.movePosition(QTextCursor.MoveOperation.End if QT_LIB == "PySide6" else QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def update_progress(self, value, message=None):
        """Обновление прогресс бара"""
        self.progress_bar.setValue(value)
        if message:
            self.log_message(message)
        QApplication.processEvents()

    def start_check(self):
        """Запуск проверки окружения"""
        self.check_btn.setEnabled(False)
        threading.Thread(target=self.perform_check, daemon=True).start()

    def perform_check(self):
        """Выполнение проверки и установки"""
        try:
            self.update_progress(10, "Checking Python installation...")
            python_installed, python_version = self.python_installer.check_python_installed()

            if not python_installed:
                self.log_message("Python not found!", "#ff4444")
                self.update_progress(20, "Python needs to be installed...")

                # Запрашиваем установку
                reply = QMessageBox.question(
                    self,
                    "Python Installation",
                    "Python is not installed on your computer.\n"
                    "Do you want to install Python 3.11.5 automatically?\n\n"
                    "Python is required to run the game.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No if QT_LIB == "PySide6" else QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.StandardButton.Yes if QT_LIB == "PySide6" else reply == QMessageBox.Yes:
                    self.update_progress(30, "Downloading Python installer...")
                    installer_path = self.python_installer.download_python_installer()

                    if installer_path:
                        self.update_progress(50, "Running Python installer...")
                        self.log_message("Please wait for installation to complete...", "#ffaa00")

                        success = self.python_installer.run_python_installer(installer_path)

                        if success:
                            self.update_progress(70, "Python successfully installed!")
                            self.log_message("Python installed successfully!", "#00ff88")

                            time.sleep(2)
                            self.update_progress(80, "Restarting check...")
                            python_installed, python_version = self.python_installer.check_python_installed()
                        else:
                            self.log_message("Python installation failed!", "#ff4444")
                            self.update_progress(100)
                            return
                    else:
                        self.log_message("Failed to download Python installer", "#ff4444")
                        self.log_message("Please install Python manually from python.org", "#ffaa00")
                        self.update_progress(100)
                        return
                else:
                    self.log_message("Python installation cancelled", "#ffaa00")
                    self.log_message("Game cannot run without Python", "#ff4444")
                    self.update_progress(100)
                    return
            else:
                self.log_message(f"Python found: {python_version}", "#00ff88")
                self.update_progress(40, "Python installed ✓")

            self.update_progress(50, "Checking required libraries...")
            installed_libs, missing_libs = self.python_installer.check_libraries()

            if installed_libs:
                self.log_message(f"Found {len(installed_libs)} libraries", "#00ff88")

            if missing_libs:
                self.log_message(f"Missing {len(missing_libs)} libraries", "#ffaa00")
                self.update_progress(60, f"Installing {len(missing_libs)} libraries...")

                def progress_callback(msg, percent):
                    self.update_progress(60 + int(percent * 0.4), msg)

                success, message = self.python_installer.install_libraries(missing_libs, progress_callback)

                if success:
                    self.log_message(message, "#00ff88")
                    self.update_progress(95, "All libraries installed!")
                else:
                    self.log_message(message, "#ff4444")
                    self.update_progress(100)
                    return
            else:
                self.log_message("All required libraries are installed!", "#00ff88")
                self.update_progress(90, "Environment configured ✓")

            self.update_progress(95, "Final check...")
            time.sleep(1)

            installed_libs, missing_libs = self.python_installer.check_libraries()

            if not missing_libs:
                self.log_message("✓ All checks passed successfully!", "#00ff88")
                self.log_message("✓ Environment is ready!", "#00ff88")
                self.update_progress(100, "Done!")
            else:
                self.log_message(f"⚠ {len(missing_libs)} issues remain after installation", "#ffaa00")
                for lib in missing_libs:
                    self.log_message(f"  - {lib}", "#ff4444")
                self.update_progress(100)

        except Exception as e:
            self.log_message(f"Error: {str(e)}", "#ff4444")
            self.update_progress(100)
        finally:
            self.check_btn.setEnabled(True)


class UltraModernLauncher(QMainWindow):
    """Основной класс лаунчера"""

    def __init__(self):
        super().__init__()

        # Инициализация цветов
        self.colors = Colors()
        self.current_colors = self.colors.get_current()

        # Настройки
        self.settings = {
            'developer_mode': False,
            'theme': 'BLACK',
            'auto_check_environment': True
        }
        self.load_settings()

        # Переменные для управления
        self.running_apps = []
        self.is_hidden = False
        self.python_installer = PythonInstaller()

        # Проверяем файлы
        self.check_files()

        # Настройка интерфейса
        self.setup_ui()

        # Проверка окружения при старте
        if self.settings['auto_check_environment']:
            QTimer.singleShot(500, self.check_environment_on_startup)

    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.setWindowTitle("🎮 DPP2 LAUNCHER")
        self.setFixedSize(800, 500)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Верхняя панель с заголовком
        header_widget = QWidget()
        header_widget.setObjectName("header")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 20, 0, 20)

        title = QLabel("🎮 DPP2 LAUNCHER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter if QT_LIB == "PySide6" else Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 32px;
            font-weight: bold;
            padding: 10px;
        """)

        subtitle = QLabel("Select an option below")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter if QT_LIB == "PySide6" else Qt.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #00d4ff;
            padding-bottom: 10px;
        """)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        # Кнопка настроек окружения
        env_btn = QPushButton("🛠️ Setup Environment")
        env_btn.setCursor(Qt.CursorShape.PointingHandCursor if QT_LIB == "PySide6" else Qt.PointingHandCursor)
        env_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9d4edd;
                border: 1px solid #9d4edd;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #9d4edd20;
            }
        """)
        env_btn.clicked.connect(self.open_environment_wizard)

        # Размещаем кнопку в правом верхнем углу заголовка
        header_layout.addWidget(env_btn, 0, Qt.AlignmentFlag.AlignRight if QT_LIB == "PySide6" else Qt.AlignRight)

        main_layout.addWidget(header_widget)

        # Контейнер для кнопок
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(40, 0, 40, 40)

        # Левая панель с кнопками
        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        # Создаем кнопки
        self.client_btn = ModernButton("Client", self.current_colors['BTN_CLIENT'])
        self.client_btn.clicked.connect(self.launch_client)

        self.client_offline_btn = ModernButton("Client Offline", self.current_colors['BTN_CLIENT_OFFLINE'])
        self.client_offline_btn.clicked.connect(self.launch_client_offline)

        self.server_btn = ModernButton("Server", self.current_colors['BTN_SERVER'])
        self.server_btn.clicked.connect(self.launch_server)

        self.all_btn = ModernButton("Start All (Server+Client)", self.current_colors['BTN_ALL'])
        self.all_btn.clicked.connect(self.launch_all)

        left_layout.addWidget(self.client_btn)
        left_layout.addWidget(self.client_offline_btn)
        left_layout.addWidget(self.server_btn)
        left_layout.addWidget(self.all_btn)
        left_layout.addStretch()

        container_layout.addWidget(left_panel)
        container_layout.addStretch()

        main_layout.addWidget(container)

        # Кнопка настроек в правом нижнем углу
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor if QT_LIB == "PySide6" else Qt.PointingHandCursor)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #9d4edd;
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
            }
            QPushButton:hover {
                color: #b97fdd;
            }
        """)
        settings_btn.clicked.connect(self.open_settings)

        # Создаем виджет для правого нижнего угла
        bottom_right_widget = QWidget()
        bottom_right_layout = QHBoxLayout(bottom_right_widget)
        bottom_right_layout.addStretch()
        bottom_right_layout.addWidget(settings_btn)

        main_layout.addWidget(bottom_right_widget)

        # Применяем стили
        self.apply_styles()

        # Обновляем видимость кнопок
        self.update_hidden_buttons_visibility()

    def apply_styles(self):
        """Применение стилей ко всему окну"""
        style = f"""
            QMainWindow {{
                background-color: {self.current_colors['WINDOW_BG']};
            }}
            QWidget#header {{
                background-color: {self.current_colors['WINDOW_BG']};
                border-bottom: 1px solid {self.current_colors['BORDER']};
            }}
            QLabel {{
                color: {self.current_colors['TEXT_MAIN']};
            }}
            QGroupBox {{
                color: {self.current_colors['TEXT_MAIN']};
                border: 1px solid {self.current_colors['BORDER']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {self.current_colors['TEXT_MAIN']};
            }}
            QTextEdit {{
                background-color: {self.current_colors['DARKER_BG']};
                color: {self.current_colors['TEXT_MAIN']};
                border: 1px solid {self.current_colors['BORDER']};
                border-radius: 4px;
                font-family: Consolas, Monospace;
            }}
            QProgressBar {{
                border: 1px solid {self.current_colors['BORDER']};
                border-radius: 4px;
                text-align: center;
                background: {self.current_colors['DARKER_BG']};
            }}
            QProgressBar::chunk {{
                background-color: {self.current_colors['ACCENT']};
                border-radius: 4px;
            }}
        """
        self.setStyleSheet(style)

    def check_files(self):
        """Проверка существования файлов"""
        print("\n" + "=" * 50)
        print("FILE CHECK:")
        print("=" * 50)

        self.client_path = CLIENT_FILE
        self.client_offline_path = CLIENT_OFFLINE_FILE
        self.server_path = SERVER_FILE

        files = [
            ("CLIENT", self.client_path),
            ("OFFLINE CLIENT", self.client_offline_path),
            ("SERVER", self.server_path)
        ]

        all_files_exist = True
        for name, path in files:
            if os.path.exists(path):
                print(f"✓ {name}: {path}")
            else:
                print(f"✗ {name}: {path} - NOT FOUND!")
                all_files_exist = False

        return all_files_exist

    def load_settings(self):
        """Загрузка настроек из файла"""
        try:
            settings_file = Path('launcher_settings.json')
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)

                    if 'theme' in loaded_settings:
                        self.colors.set_theme(loaded_settings['theme'])
                        self.current_colors = self.colors.get_current()
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Сохранение настроек в файл"""
        try:
            settings_file = Path('launcher_settings.json')
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def check_environment_on_startup(self):
        """Проверка окружения при запуске"""
        try:
            python_installed, _ = self.python_installer.check_python_installed()
            if not python_installed:
                self.show_environment_warning()
        except:
            pass

    def show_environment_warning(self):
        """Показ предупреждения о необходимости настройки окружения"""
        reply = QMessageBox.question(
            self,
            "Environment Setup",
            "Python and required libraries are needed to run the game.\n"
            "Do you want to run the environment setup wizard?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No if QT_LIB == "PySide6" else QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.StandardButton.Yes if QT_LIB == "PySide6" else reply == QMessageBox.Yes:
            self.open_environment_wizard()

    def open_environment_wizard(self):
        """Открытие мастера настройки окружения"""
        wizard = InstallationWizard(self)
        wizard.exec()

    def open_settings(self):
        """Открытие окна настроек"""
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()

    def apply_settings_changes(self):
        """Применение изменений настроек"""
        self.save_settings()
        self.current_colors = self.colors.get_current()
        self.apply_styles()
        self.update_button_colors()
        self.update_hidden_buttons_visibility()

    def update_button_colors(self):
        """Обновление цветов всех кнопок"""
        if hasattr(self, 'client_btn'):
            self.client_btn.color = self.current_colors['BTN_CLIENT']
            self.client_btn.setStyleSheet(self.client_btn.styleSheet())

        if hasattr(self, 'client_offline_btn'):
            self.client_offline_btn.color = self.current_colors['BTN_CLIENT_OFFLINE']
            self.client_offline_btn.setStyleSheet(self.client_offline_btn.styleSheet())

        if hasattr(self, 'server_btn'):
            self.server_btn.color = self.current_colors['BTN_SERVER']
            self.server_btn.setStyleSheet(self.server_btn.styleSheet())

        if hasattr(self, 'all_btn'):
            self.all_btn.color = self.current_colors['BTN_ALL']
            self.all_btn.setStyleSheet(self.all_btn.styleSheet())

    def update_hidden_buttons_visibility(self):
        """Обновление видимости скрытых кнопок"""
        if self.settings['developer_mode']:
            self.server_btn.show()
            self.all_btn.show()
        else:
            self.server_btn.hide()
            self.all_btn.hide()

    def run_python_script_simple(self, script_path, script_name):
        """Запуск Python скрипта"""
        try:
            if not os.path.exists(script_path):
                QMessageBox.critical(
                    self,
                    "Error",
                    f"File {script_name} not found!\n\nPath: {script_path}"
                )
                return None

            # Проверяем Python
            python_installed, _ = self.python_installer.check_python_installed()
            if not python_installed:
                QMessageBox.critical(
                    self,
                    "Error",
                    "Python is not installed!\n"
                    "Click 'Setup Environment' button to install."
                )
                return None

            work_dir = os.path.dirname(script_path)

            print(f"\n🚀 Launching {script_name}:")
            print(f"📁 File: {script_path}")
            print(f"📂 Directory: {work_dir}")

            try:
                # Определяем команду в зависимости от ОС
                if os.name == 'nt':  # Windows
                    python_cmd = 'python'
                else:  # Linux/Mac
                    python_cmd = 'python3'

                cmd = [python_cmd, script_path]
                print(f"Command: {' '.join(cmd)}")

                # Запускаем процесс
                process = subprocess.Popen(
                    cmd,
                    cwd=work_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

                print(f"✅ {script_name} launched (PID: {process.pid})")
                self.running_apps.append({
                    'process': process,
                    'name': script_name,
                    'pid': process.pid
                })

                print(f"Running apps count: {len(self.running_apps)}")

                # Мониторинг процесса
                threading.Thread(
                    target=self.monitor_process,
                    args=(process, script_name),
                    daemon=True
                ).start()

                return process

            except Exception as e:
                print(f"❌ Error launching {script_name}: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to launch {script_name}:\n{str(e)}"
                )
                return None

        except Exception as e:
            print(f"❌ General error launching {script_name}: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to launch {script_name}:\n{str(e)}"
            )
            return None

    def monitor_process(self, process, process_name):
        """Мониторинг процесса"""
        try:
            stdout, stderr = process.communicate()

            if stdout:
                output = stdout.decode('utf-8', errors='ignore')
                if output.strip():
                    print(f"[{process_name} stdout]: {output[:500]}")
            if stderr:
                error = stderr.decode('utf-8', errors='ignore')
                if error.strip():
                    print(f"[{process_name} stderr]: {error[:500]}")

            print(f"✅ Process {process_name} completed with code {process.returncode}")

        except Exception as e:
            print(f"❌ Error monitoring {process_name}: {e}")
        finally:
            # Удаляем процесс из списка запущенных
            self.running_apps = [app for app in self.running_apps if app['process'] != process]

            print(f"Remaining apps: {len(self.running_apps)}")

            # Если все процессы завершены и окно скрыто - показываем лаунчер
            if not self.running_apps and self.is_hidden:
                print("All applications closed, showing launcher...")
                # Используем QTimer для безопасного вызова в главном потоке
                QTimer.singleShot(500, self.show_launcher)

    def show_launcher(self):
        """Показать лаунчер (вызывается в главном потоке)"""
        if not self.running_apps and self.is_hidden:
            print("Restoring launcher window...")
            self.show()
            self.is_hidden = False
            # Поднимаем окно на передний план
            self.raise_()
            self.activateWindow()
            print("Launcher restored and activated")

    def show_and_reset(self):
        """Показать окно и сбросить состояние"""
        self.show()
        self.is_hidden = False
        print("Launcher restored")

    def launch_client(self):
        """Запуск клиента"""
        print("Launching Client...")
        self.hide()
        self.is_hidden = True
        process = self.run_python_script_simple(self.client_path, "Client")
        if not process:
            # Если не удалось запустить, показываем лаунчер снова
            self.show_launcher()

    def launch_client_offline(self):
        """Запуск офлайн клиента"""
        print("Launching Client Offline...")
        self.hide()
        self.is_hidden = True
        process = self.run_python_script_simple(self.client_offline_path, "Client Offline")
        if not process:
            # Если не удалось запустить, показываем лаунчер снова
            self.show_launcher()

    def launch_server(self):
        """Запуск сервера"""
        print("Launching Server...")
        self.hide()
        self.is_hidden = True
        process = self.run_python_script_simple(self.server_path, "Server")
        if not process:
            # Если не удалось запустить, показываем лаунчер снова
            self.show_launcher()

    def launch_all(self):
        """Запуск всего (Server+Client)"""
        print("Launching All (Server + Client)...")
        self.hide()
        self.is_hidden = True

        def launch():
            server_process = self.run_python_script_simple(self.server_path, "Server")
            if server_process:
                time.sleep(3)
                client_process = self.run_python_script_simple(self.client_path, "Client")
                if not client_process:
                    print("Failed to launch Client")
            else:
                print("Failed to launch Server")
                # Если не удалось запустить сервер, показываем лаунчер
                QTimer.singleShot(1000, self.show_launcher)

        threading.Thread(target=launch, daemon=True).start()


class PythonInstaller:
    """Класс для установки Python и библиотек"""

    @staticmethod
    def check_python_installed():
        """Проверка установлен ли Python"""
        try:
            # Пробуем python
            result = subprocess.run(['python', '--version'],
                                    capture_output=True,
                                    text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✓ Python found: {version}")
                return True, version

            # Пробуем python3
            result = subprocess.run(['python3', '--version'],
                                    capture_output=True,
                                    text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✓ Python3 found: {version}")
                return True, version

        except Exception as e:
            print(f"✗ Python not found: {e}")

        return False, None

    @staticmethod
    def check_libraries():
        """Проверка установленных библиотек"""
        missing_libs = []
        installed_libs = []

        for lib in REQUIRED_LIBRARIES:
            lib_name = lib.split('==')[0]
            try:
                # Проверяем доступность pip
                subprocess.run(['pip', '--version'],
                               capture_output=True,
                               check=True,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

                # Проверяем наличие библиотеки
                result = subprocess.run(['python', '-c', f'import {lib_name}'],
                                        capture_output=True,
                                        text=True,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

                if result.returncode == 0:
                    installed_libs.append(lib)
                    print(f"✓ Library installed: {lib_name}")
                else:
                    missing_libs.append(lib)
                    print(f"✗ Library missing: {lib_name}")

            except subprocess.CalledProcessError:
                missing_libs.append(lib)
                print(f"✗ Error checking library: {lib_name}")
            except Exception as e:
                missing_libs.append(lib)
                print(f"✗ Exception checking {lib_name}: {e}")

        return installed_libs, missing_libs

    @staticmethod
    def install_libraries(missing_libs, progress_callback=None):
        """Установка недостающих библиотек"""
        if not missing_libs:
            return True, "All libraries are already installed"

        try:
            total = len(missing_libs)
            installed_count = 0

            for i, lib in enumerate(missing_libs):
                if progress_callback:
                    progress_callback(f"Installing {lib}...", int((i / total) * 100))

                print(f"Installing library: {lib}")

                try:
                    # Используем pip install с таймаутом
                    result = subprocess.run(['pip', 'install', lib, '--timeout', '30'],
                                            capture_output=True,
                                            text=True,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

                    if result.returncode == 0:
                        installed_count += 1
                        print(f"✓ Successfully installed: {lib}")
                    else:
                        print(f"✗ Installation error {lib}: {result.stderr[:200]}")

                        # Пробуем установить без версии
                        lib_name = lib.split('==')[0]
                        result = subprocess.run(['pip', 'install', lib_name],
                                                capture_output=True,
                                                text=True,
                                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

                        if result.returncode == 0:
                            installed_count += 1
                            print(f"✓ Installed latest version: {lib_name}")
                        else:
                            return False, f"Failed to install {lib}"

                except Exception as e:
                    print(f"✗ Exception installing {lib}: {e}")

            if progress_callback:
                progress_callback("Installation complete!", 100)

            return True, f"Successfully installed {installed_count} of {len(missing_libs)} libraries"

        except Exception as e:
            error_msg = f"Error installing libraries: {str(e)}"
            print(error_msg)
            return False, error_msg

    @staticmethod
    def download_python_installer():
        """Скачивание установщика Python"""
        python_url = "https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "python_installer.exe")

        try:
            print(f"Downloading Python installer to {installer_path}...")
            urllib.request.urlretrieve(python_url, installer_path)
            print("Download complete")
            return installer_path
        except Exception as e:
            print(f"Download error: {e}")
            return None

    @staticmethod
    def run_python_installer(installer_path):
        """Запуск установщика Python"""
        try:
            print(f"Running installer: {installer_path}")

            if not os.path.exists(installer_path):
                print(f"Installer file not found: {installer_path}")
                return False

            # Параметры для автоматической установки
            args = [installer_path, '/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_launcher=0']

            process = subprocess.run(args,
                                     creationflags=subprocess.CREATE_NO_WINDOW,
                                     timeout=300)  # 5 минут таймаут

            if process.returncode == 0:
                print("Python installation completed successfully")

                # Обновляем переменные окружения
                os.environ['PATH'] = os.environ['PATH'] + ';' + os.path.join(
                    os.environ.get('SystemRoot', 'C:\\Windows'), 'System32')

                return True
            else:
                print(f"Python installation error: code {process.returncode}")
                return False

        except subprocess.TimeoutExpired:
            print("Python installation timed out")
            return False
        except Exception as e:
            print(f"Error running installer: {e}")
            return False


# ========== ЗАПУСК ЛАУНЧЕРА ==========
if __name__ == "__main__":
    try:
        print("=" * 50)
        print("DPP2 LAUNCHER - Starting...")
        print("=" * 50)
        print(f"Current directory: {os.getcwd()}")
        print(f"Python version: {sys.version}")
        print(f"Operating system: {platform.system()} {platform.release()}")
        print(f"Base path (BASE_PATH): {BASE_PATH}")
        print(f"EXE mode: {getattr(sys, 'frozen', False)}")
        print(f"GUI library: {QT_LIB}")

        if not QT_AVAILABLE:
            print("\n❌ GUI libraries not available!")
            print("Try to install manually:")
            print("pip install PySide6")
            input("Press Enter to exit...")
            sys.exit(1)

        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Современный стиль

        # Установка шрифта
        font = QFont("Arial", 10)
        app.setFont(font)

        launcher = UltraModernLauncher()
        launcher.show()

        sys.exit(app.exec())

    except Exception as e:
        print(f"CRITICAL ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

        input("Press Enter to exit...")