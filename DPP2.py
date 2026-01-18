import sys
import os
import json
import subprocess
import threading
import time
import signal

# ========== ПРОВЕРКА QT БИБЛИОТЕК ==========
QT_LIB = None

# Сначала пробуем PySide6
try:
    import PySide6

    QT_LIB = "PySide6"
    print("✓ PySide6 найден")
except ImportError:
    print("✗ PySide6 не найден")

# Если PySide6 не найден, пробуем PyQt5
if QT_LIB is None:
    try:
        import PyQt5

        QT_LIB = "PyQt5"
        print("✓ PyQt5 найден")
    except ImportError:
        print("✗ PyQt5 не найден")
        print("\nУстановите одну из библиотек:")
        print("pip install PySide6")
        print("ИЛИ")
        print("pip install PyQt5")
        sys.exit(1)

# ИМПОРТЫ НА УРОВНЕ МОДУЛЯ
if QT_LIB == "PySide6":
    from PySide6.QtWidgets import *
    from PySide6.QtCore import *
    from PySide6.QtGui import *

    Signal = Signal
    Slot = Slot
    CHECKED_STATE = Qt.Checked
else:  # PyQt5
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtCore import pyqtSignal as Signal
    from PyQt5.QtCore import pyqtSlot as Slot

    CHECKED_STATE = 2

# ========== ПРОВЕРКА PILLOW ==========
try:
    from PIL import Image, ImageSequence

    PIL_AVAILABLE = True
    print("✓ Pillow (PIL) загружен")
except ImportError:
    PIL_AVAILABLE = False
    print("✗ Pillow (PIL) не найден - GIF анимации будут отключены")
    print("Установите: pip install pillow")


# ========== КЛАСС ДЛЯ АНИМИРОВАННЫХ GIF ==========
class AnimatedGIFLabel(QLabel):
    """QLabel с поддержкой анимированных GIF"""

    def __init__(self, gif_path=None, parent=None):
        super().__init__(parent)
        self.frames = []
        self.current_frame = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        if gif_path and os.path.exists(gif_path) and PIL_AVAILABLE:
            self.load_gif(gif_path)
        else:
            self.set_default_image()

    def set_default_image(self):
        """Устанавливает изображение по умолчанию"""
        pixmap = QPixmap(100, 60)
        pixmap.fill(QColor("#3498db"))
        self.setPixmap(pixmap)
        self.setAlignment(Qt.AlignCenter)

    def load_gif(self, gif_path):
        """Загружает GIF файл"""
        try:
            pil_image = Image.open(gif_path)
            self.frames = []

            for frame in ImageSequence.Iterator(pil_image):
                # Конвертируем PIL Image в QImage
                if frame.mode == 'P':
                    frame = frame.convert("RGBA")
                elif frame.mode != 'RGBA':
                    frame = frame.convert("RGBA")

                data = frame.tobytes("raw", "RGBA")
                qimage = QImage(data, frame.width, frame.height, QImage.Format_RGBA8888)
                qpixmap = QPixmap.fromImage(qimage)
                self.frames.append(qpixmap.scaled(100, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            if self.frames:
                self.setPixmap(self.frames[0])
                self.setAlignment(Qt.AlignCenter)
                self.timer.start(100)  # 10 FPS
            else:
                self.set_default_image()
        except Exception as e:
            print(f"Ошибка загрузки GIF {gif_path}: {e}")
            self.set_default_image()

    def next_frame(self):
        """Показывает следующий кадр"""
        if self.frames:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.setPixmap(self.frames[self.current_frame])


# ========== ВЫПАДАЮЩИЙ СПИСОК ТЕМ ==========
class ThemeDropdown(QWidget):
    """Кастомный выпадающий список тем"""
    theme_selected = Signal(str, str, str, str)  # bg, card, text, name

    def __init__(self, current_theme, parent=None):
        super().__init__(parent)
        self.current_theme = current_theme
        self.is_open = False

        # Цветовые схемы для тем
        self.themes = {
            "black": ("#000000", "#454545", "white"),
            "gray": ("#808080", "#A0A0A0", "black"),
            "white": ("#FFFFFF", "#E0E0E0", "black")
        }

        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса dropdown"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Заголовок dropdown
        self.header = QWidget()
        self.header.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 5, 10, 5)

        self.selected_label = QLabel(self.current_theme)
        self.arrow_label = QLabel("▼")

        header_layout.addWidget(self.selected_label)
        header_layout.addStretch()
        header_layout.addWidget(self.arrow_label)

        # Список опций (изначально скрыт)
        self.options_widget = QWidget()
        self.options_widget.setVisible(False)
        options_layout = QVBoxLayout(self.options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(1)

        # Создаем опции для каждой темы
        for theme_name, colors in self.themes.items():
            option_widget = QWidget()
            option_widget.setFixedHeight(30)
            option_widget.setCursor(Qt.PointingHandCursor)

            option_layout = QHBoxLayout(option_widget)
            option_layout.setContentsMargins(10, 0, 10, 0)

            option_label = QLabel(theme_name)
            option_layout.addWidget(option_label)

            # Сохраняем данные темы
            option_widget.theme_data = colors + (theme_name,)

            # Обработчик клика
            option_widget.mousePressEvent = lambda e, opt=option_widget: self.select_theme(*opt.theme_data)

            options_layout.addWidget(option_widget)

        layout.addWidget(self.header)
        layout.addWidget(self.options_widget)

        # Обработчик клика по заголовку
        self.header.mousePressEvent = self.toggle_dropdown

    def toggle_dropdown(self, event):
        """Показывает/скрывает список опций"""
        if self.is_open:
            self.options_widget.setVisible(False)
            self.arrow_label.setText("▼")
        else:
            self.options_widget.setVisible(True)
            self.arrow_label.setText("▲")

        self.is_open = not self.is_open

    def select_theme(self, bg_color, card_color, text_color, theme_name):
        """Выбирает тему"""
        self.selected_label.setText(theme_name)
        self.options_widget.setVisible(False)
        self.arrow_label.setText("▼")
        self.is_open = False
        self.theme_selected.emit(bg_color, card_color, text_color, theme_name)


# ========== ДИАЛОГ НАСТРОЕК ==========
class OptionsDialog(QDialog):
    """Диалоговое окно настроек"""

    def __init__(self, current_theme, current_scale, parent=None):
        super().__init__(parent)
        self.current_theme = current_theme
        self.current_scale = current_scale

        self.setWindowTitle("Options")
        self.setFixedSize(350, 250)
        self.setModal(True)

        self.init_ui()

    def init_ui(self):
        """Инициализация интерфейса диалога"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Раздел "Color Theme"
        theme_group = QGroupBox("Color Theme")
        theme_layout = QVBoxLayout(theme_group)

        self.theme_dropdown = ThemeDropdown(self.current_theme)
        theme_layout.addWidget(self.theme_dropdown)

        layout.addWidget(theme_group)

        # Раздел "Pony Scale"
        scale_group = QGroupBox("Pony Scale")
        scale_layout = QVBoxLayout(scale_group)

        # Метка с текущим значением
        scale_percent = int(self.current_scale * 100)
        self.scale_label = QLabel(f"Scale: {scale_percent}%")
        self.scale_label.setAlignment(Qt.AlignCenter)

        # Слайдер
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setMinimum(25)  # 25%
        self.scale_slider.setMaximum(200)  # 200%
        self.scale_slider.setValue(scale_percent)
        self.scale_slider.valueChanged.connect(self.on_scale_changed)

        scale_layout.addWidget(self.scale_label)
        scale_layout.addWidget(self.scale_slider)

        layout.addWidget(scale_group)

        layout.addStretch()

        # Кнопки
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("Apply Scale")
        self.apply_btn.clicked.connect(self.apply_scale)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)

        button_layout.addWidget(self.apply_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def on_scale_changed(self, value):
        """Обработчик изменения слайдера"""
        self.current_scale = value / 100.0
        self.scale_label.setText(f"Scale: {value}%")

    def apply_scale(self):
        """Применяет масштаб"""
        print(f"Масштаб применен: {self.current_scale}")
        self.accept()


# ========== ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ ==========
class DynamicPonySelector(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()

        print("=" * 50)
        print(f"Запуск DPP2 Pony Selector с {QT_LIB}")
        print("=" * 50)

        # Конфигурационный файл
        self.config_file = "theme_config.json"
        self.should_exit = False

        # Данные пони
        self.pony_names = [
            "Twilight Sparkle", "Rainbow Dash", "Pinkie Pie", "Apple Jack",
            "Fluttershy", "Rarity", "Trixie", "Starlight", "Sunset",
            "Cadance", "Celestia", "Luna"
        ]

        self.pony_gifs = {
            "Twilight Sparkle": "twilight.gif",
            "Rainbow Dash": "rainbow.gif",
            "Pinkie Pie": "pinkie.gif",
            "Apple Jack": "applejack.gif",
            "Fluttershy": "fluttershy.gif",
            "Rarity": "rarity.gif",
            "Cadance": "cadance.gif",
            "Celestia": "celestia.gif",
            "Luna": "luna.gif"
        }

        # Настройки масштаба
        self.current_scale = 0.95

        # Инициализируем словарь состояний
        self.selected_ponies = {}
        for pony_name in self.pony_names:
            self.selected_ponies[pony_name] = False

        # Загружаем сохраненную тему
        self.load_theme()

        # Инициализация процессов
        self.running_processes = {}  # {имя_пони: (process, pid)}
        self.active_ponies_count = 0
        self.main_window_hidden = False
        self.restore_timer = QTimer()
        self.restore_timer.timeout.connect(self.check_and_restore_window)
        self.restore_timer.start(2000)  # Проверяем каждые 2 секунды

        # Храним чекбоксы
        self.checkboxes = {}

        # Инициализация UI
        self.init_ui()

        print("✓ Приложение инициализировано")

    def load_theme(self):
        """Загружает сохраненную тему"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"✓ Загружена тема: {config.get('theme_name', 'default')}")

                self.current_bg = config.get('bg_color', '#000000')
                self.current_card_bg = config.get('card_color', '#454545')
                self.current_text_color = config.get('text_color', 'white')
                self.current_theme_name = config.get('theme_name', 'black')
                self.current_scale = config.get('pony_scale', 0.95)

                # Загружаем состояния пони
                saved_ponies = config.get('selected_ponies', {})
                for pony_name in self.pony_names:
                    self.selected_ponies[pony_name] = saved_ponies.get(pony_name, False)
                print("✓ Состояния пони загружены")
            else:
                raise FileNotFoundError
        except Exception as e:
            print(f"✗ Ошибка загрузки темы: {e}")
            print("Используются значения по умолчанию")
            # Значения по умолчанию
            self.current_bg = '#000000'
            self.current_card_bg = '#454545'
            self.current_text_color = 'white'
            self.current_theme_name = 'black'
            self.current_scale = 0.95

    def save_theme(self):
        """Сохраняет текущую тему"""
        try:
            # Получаем актуальные состояния из чекбоксов
            self.get_selected_ponies_from_checkboxes()

            config = {
                'bg_color': self.current_bg,
                'card_color': self.current_card_bg,
                'text_color': self.current_text_color,
                'theme_name': self.current_theme_name,
                'pony_scale': self.current_scale,
                'selected_ponies': self.selected_ponies
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            print(f"✓ Тема '{self.current_theme_name}' сохранена")
        except Exception as e:
            print(f"✗ Ошибка сохранения темы: {e}")

    def get_selected_ponies_from_checkboxes(self):
        """Получает выбранных пони из чекбоксов"""
        for pony_name, checkbox in self.checkboxes.items():
            self.selected_ponies[pony_name] = checkbox.isChecked()

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        print("Создание интерфейса...")

        # Настройки окна
        self.setWindowTitle("DPP2 - Pony Selector")
        self.setGeometry(100, 100, 520, 500)
        self.setMinimumSize(400, 400)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Главный layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Заголовок
        self.title_label = QLabel("DPP2 - Pony Selector")
        self.title_label.setAlignment(Qt.AlignCenter)

        # Область с карточками (прокручиваемая)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_widget = QWidget()
        self.cards_layout = QGridLayout(self.cards_widget)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll_area.setWidget(self.cards_widget)

        # Кнопки внизу
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        # Кнопка Options
        self.options_btn = QPushButton("options")
        self.options_btn.clicked.connect(self.show_options)

        # Кнопка Stop All
        self.stop_btn = QPushButton("stop all")
        self.stop_btn.clicked.connect(self.stop_all)

        # Кнопка Start
        self.start_btn = QPushButton("start")
        self.start_btn.clicked.connect(self.launch_selected)

        bottom_layout.addWidget(self.options_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.stop_btn)
        bottom_layout.addWidget(self.start_btn)

        # Добавляем все виджеты
        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.scroll_area)
        main_layout.addWidget(bottom_widget)

        # Применяем текущую тему
        self.update_theme()

        # Создаем карточки
        self.create_cards()

        print("✓ Интерфейс создан")

    def update_theme(self):
        """Обновляет цвета интерфейса"""
        # Стиль главного окна
        style = f"""
            QMainWindow {{
                background-color: {self.current_bg};
            }}

            QLabel {{
                color: {self.current_text_color};
            }}

            QPushButton {{
                background-color: {self.current_card_bg};
                color: {self.current_text_color};
                border: none;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 12px;
                border-radius: 5px;
            }}

            QPushButton:hover {{
                background-color: #555555;
            }}

            QGroupBox {{
                color: {self.current_text_color};
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}

            QScrollArea {{
                border: none;
                background-color: {self.current_bg};
            }}

            QScrollBar:vertical {{
                border: none;
                background: {self.current_card_bg};
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}

            QScrollBar::handle:vertical {{
                background: #666;
                min-height: 20px;
                border-radius: 5px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: #888;
            }}
        """

        self.setStyleSheet(style)

        # Обновляем заголовок
        self.title_label.setStyleSheet(f"""
            color: {self.current_text_color};
            font-size: 16px;
            font-weight: bold;
        """)

        # Специальный стиль для кнопки stop
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)

    def create_cards(self):
        """Создает карточки пони"""
        # Очищаем старые карточки
        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Очищаем словарь чекбоксов
        self.checkboxes.clear()

        # Создаем новые карточки
        # Вычисляем количество колонок
        width = self.scroll_area.width()
        columns = max(2, width // 170)
        if columns == 0:
            columns = 2

        for i, pony_name in enumerate(self.pony_names):
            # Создаем карточку
            card_widget = QWidget()
            card_widget.setFixedSize(150, 120)

            card_style = f"""
                QWidget {{
                    background-color: {self.current_card_bg};
                    border: 1px solid #555;
                    border-radius: 8px;
                }}
            """
            card_widget.setStyleSheet(card_style)

            # Layout карточки
            card_layout = QVBoxLayout(card_widget)
            card_layout.setContentsMargins(5, 5, 5, 5)
            card_layout.setSpacing(3)

            # Область для GIF
            gif_widget = QWidget()
            gif_widget.setFixedHeight(80)
            gif_layout = QVBoxLayout(gif_widget)
            gif_layout.setContentsMargins(0, 0, 0, 0)

            # GIF файл
            gif_filename = self.pony_gifs.get(pony_name, "placeholder.gif")
            gif_path = os.path.join("pony_previews", gif_filename)
            gif_label = AnimatedGIFLabel(gif_path)
            gif_layout.addWidget(gif_label)

            # Область с именем и чекбоксом
            info_widget = QWidget()
            info_widget.setFixedHeight(25)
            info_layout = QHBoxLayout(info_widget)
            info_layout.setContentsMargins(5, 0, 5, 0)

            # Имя пони
            name_label = QLabel(pony_name)
            name_label.setStyleSheet(f"color: {self.current_text_color}; font-weight: bold; font-size: 10px;")
            name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            # Чекбокс
            checkbox = QCheckBox()
            checkbox.setFixedSize(20, 20)

            # Устанавливаем начальное состояние из словаря
            checkbox.setChecked(self.selected_ponies.get(pony_name, False))

            # Сохраняем чекбокс
            self.checkboxes[pony_name] = checkbox

            info_layout.addWidget(name_label)
            info_layout.addStretch()
            info_layout.addWidget(checkbox)

            # Собираем карточку
            card_layout.addWidget(gif_widget)
            card_layout.addWidget(info_widget)

            # Позиционируем в сетке
            row = i // columns
            col = i % columns
            self.cards_layout.addWidget(card_widget, row, col)

    def show_options(self):
        """Показывает окно настроек"""
        print("Открытие настроек...")
        dialog = OptionsDialog(self.current_theme_name, self.current_scale, self)
        dialog.theme_dropdown.theme_selected.connect(self.change_theme)
        dialog.apply_btn.clicked.connect(lambda: self.apply_scale_to_running(dialog.current_scale))

        if dialog.exec():
            print("Настройки сохранены")

    def change_theme(self, bg_color, card_color, text_color, theme_name):
        """Изменяет тему приложения"""
        print(f"Изменение темы на: {theme_name}")

        self.current_bg = bg_color
        self.current_card_bg = card_color
        self.current_text_color = text_color
        self.current_theme_name = theme_name

        # Обновляем UI
        self.update_theme()
        self.create_cards()  # Пересоздаем карточки с новой темой

        # Сохраняем тему
        self.save_theme()

    def apply_scale_to_running(self, scale):
        """Применяет масштаб к запущенным пони"""
        print(f"Применение масштаба {int(scale * 100)}% к запущенным пони...")

        if self.running_processes:
            # Перезапускаем всех пони с новым масштабом
            running_ponies = list(self.running_processes.keys())

            # Останавливаем
            for pony_name in running_ponies:
                if pony_name in self.running_processes:
                    try:
                        process, pid = self.running_processes[pony_name]
                        self.kill_process_tree(pid)
                        print(f"Остановлен: {pony_name}")
                    except:
                        pass

            # Запускаем заново
            for pony_name in running_ponies:
                self._start_via_subprocess(pony_name)

            print("✓ Масштаб применен к запущенным пони")
        else:
            print("Нет запущенных пони")

    def launch_selected(self):
        """Запускает выбранных пони"""
        # Сначала обновляем словарь из чекбоксов
        self.get_selected_ponies_from_checkboxes()

        # Получаем список выбранных пони
        selected_list = [name for name, selected in self.selected_ponies.items() if selected]

        if not selected_list:
            print("✗ Не выбрано ни одного пони!")
            print(f"Состояния: {self.selected_ponies}")

            # Показываем сообщение
            QMessageBox.warning(self, "Внимание", "Не выбрано ни одного пони!")
            return

        print(f"Запуск пони: {', '.join(selected_list)}")
        print(f"Всего выбрано: {len(selected_list)}")
        print("Главное окно скрыто")

        # Сохраняем состояния перед запуском
        self.save_theme()

        # Скрываем главное окно
        self.hide()
        self.main_window_hidden = True

        # Запускаем каждого пони
        for pony_name in selected_list:
            self._start_via_subprocess(pony_name)

        print(f"✓ Запущено {len(selected_list)} пони")

    def stop_all(self):
        """Останавливает всех запущенных пони"""
        print("Остановка всех пони...")

        # Останавливаем процессы
        for pony_name, (process, pid) in list(self.running_processes.items()):
            try:
                self.kill_process_tree(pid)
                print(f"✓ Остановлен: {pony_name} (PID: {pid})")
            except Exception as e:
                print(f"✗ Ошибка остановки {pony_name}: {e}")

        self.running_processes.clear()
        self.active_ponies_count = 0

        # Показываем главное окно
        if self.main_window_hidden:
            self.show()
            self.main_window_hidden = False
            print("Главное окно показано")

        print("✓ Все пони остановлены")

    def kill_process_tree(self, pid):
        """Убивает процесс и все его дочерние процессы"""
        try:
            if os.name == 'nt':  # Windows
                import ctypes
                PROCESS_TERMINATE = 1
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                ctypes.windll.kernel32.TerminateProcess(handle, -1)
                ctypes.windll.kernel32.CloseHandle(handle)
            else:  # Linux/Mac
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)  # Даем процессу время завершиться
        except:
            pass

    def check_and_restore_window(self):
        """Проверяет и восстанавливает окно если все пони завершились"""
        if not self.main_window_hidden:
            return

        # Проверяем завершенные процессы
        dead_processes = []
        for pony_name, (process, pid) in list(self.running_processes.items()):
            try:
                # Проверяем, жив ли процесс
                if process.poll() is not None:  # Процесс завершен
                    print(f"🔄 {pony_name} завершился (returncode: {process.poll()})")
                    dead_processes.append(pony_name)
            except:
                dead_processes.append(pony_name)

        # Удаляем завершенные процессы
        for pony_name in dead_processes:
            if pony_name in self.running_processes:
                del self.running_processes[pony_name]
                self.active_ponies_count = max(0, self.active_ponies_count - 1)

        # Если все пони завершились - восстанавливаем окно
        if self.active_ponies_count == 0 and self.main_window_hidden:
            print("🔄 Все пони завершили работу, восстанавливаю окно...")
            self._safe_restore_window()

    def _safe_restore_window(self):
        """Безопасное восстановление окна"""
        if self.main_window_hidden:
            self.show()
            self.main_window_hidden = False
            self.raise_()
            self.activateWindow()
            print("✅ Окно восстановлено и активировано")

    def resizeEvent(self, event):
        """Обработчик изменения размера окна"""
        super().resizeEvent(event)
        # Пересоздаем карточки при изменении размера окна
        self.create_cards()

    def _start_via_subprocess(self, pony_name):
        """Запускает пони через subprocess"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Пробуем разные пути к pony.py
            possible_paths = [
                "pony.py",
                os.path.join("DPP2serverUDP", "Client", "characters", "pony.py"),
                os.path.join("characters", "pony.py"),
                os.path.join(current_dir, "pony.py")
            ]

            pony_script = None
            for path in possible_paths:
                if os.path.exists(path):
                    pony_script = path
                    break

            if not pony_script:
                print(f"✗ Файл pony.py не найден по путям: {possible_paths}")
                return

            # Команда для запуска
            cmd = [sys.executable, pony_script, pony_name, str(self.current_scale)]
            print(f"Команда: {' '.join(cmd)}")

            # Запуск процесса
            if os.name == 'nt':  # Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # Скрываем окно консоли

                process = subprocess.Popen(
                    cmd,
                    startupinfo=startupinfo,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    cwd=current_dir
                )
            else:  # Linux/Mac
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    preexec_fn=os.setsid,
                    cwd=current_dir
                )

            pid = process.pid
            self.running_processes[pony_name] = (process, pid)
            self.active_ponies_count += 1

            print(f"✅ {pony_name} запущен (PID: {pid})")

            # Запускаем мониторинг процесса
            threading.Thread(
                target=self._monitor_single_process,
                args=(pony_name, process),
                daemon=True
            ).start()

        except Exception as e:
            print(f"✗ Ошибка запуска {pony_name}: {e}")
            self.active_ponies_count = max(0, self.active_ponies_count - 1)

            # Если это был последний пони - восстанавливаем окно
            if self.active_ponies_count == 0 and self.main_window_hidden:
                QTimer.singleShot(100, self._safe_restore_window)

    def _monitor_single_process(self, pony_name, process):
        """Мониторит один процесс пони"""
        try:
            # Ждем завершения процесса
            return_code = process.wait(timeout=None)

            print(f"🔄 {pony_name} завершил работу с кодом {return_code}")

            # Удаляем из running_processes
            if pony_name in self.running_processes:
                del self.running_processes[pony_name]

            self.active_ponies_count = max(0, self.active_ponies_count - 1)

            # Проверяем, нужно ли восстановить окно
            if (self.active_ponies_count == 0 and
                    not self.running_processes and
                    self.main_window_hidden):
                print(f"🔄 Все пони завершили работу, восстанавливаю окно...")
                QTimer.singleShot(100, self._safe_restore_window)

        except subprocess.TimeoutExpired:
            print(f"⚠️ {pony_name}: Таймаут ожидания")
        except Exception as e:
            print(f"❌ Ошибка мониторинга {pony_name}: {e}")
            if pony_name in self.running_processes:
                del self.running_processes[pony_name]
            self.active_ponies_count = max(0, self.active_ponies_count - 1)

            if (self.active_ponies_count == 0 and
                    not self.running_processes and
                    self.main_window_hidden):
                QTimer.singleShot(100, self._safe_restore_window)

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        print("Завершение программы...")
        self.should_exit = True
        self.restore_timer.stop()

        # Сохраняем тему и состояния перед выходом
        self.save_theme()

        # Останавливаем все процессы
        self.stop_all()
        event.accept()


# ========== ТОЧКА ВХОДА ==========
def main():
    """Главная функция"""
    try:
        # Создаем приложение
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # Создаем главное окно
        window = DynamicPonySelector()
        window.show()

        # Запускаем цикл событий
        return app.exec()

    except Exception as e:
        print(f"✗ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())