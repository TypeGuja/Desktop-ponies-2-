#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DPP2 – Pony‑selector

*  Выбор темы (цветов) и масштаба пони.
*  Сохранение всех настроек в ``theme_config.json``.
*  При изменении масштаба в диалогe «Options» сразу обновляется
   ``self.current_scale``, сохраняется в конфиг и, если пони уже
   запущены – они перезапускаются с новым масштабом.
*  Работает как с PySide6, так и с PyQt5 (автоматический fallback).
"""

# ----------------------------------------------------------------------
#   Библиотеки Qt (PySide6 → PyQt5)
# ----------------------------------------------------------------------
import sys
import os
import json
import subprocess
import threading
import time
import signal

QT_LIB = None
# Попытка импортировать PySide6, иначе PyQt5
try:
    import PySide6

    QT_LIB = "PySide6"
except Exception:
    pass

if QT_LIB is None:
    try:
        import PyQt5

        QT_LIB = "PyQt5"
    except Exception:
        sys.exit("Не найден ни один из Qt‑бинда: PySide6 / PyQt5")

# -------------------------------------------------
#   Импорт нужных классов из выбранного бинда
# -------------------------------------------------
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

# -------------------------------------------------
#   Pillow – для чтения анимированных GIF
# -------------------------------------------------
try:
    from PIL import Image, ImageSequence

    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


# =========================================================
#   Вспомогательные виджеты
# =========================================================

class AnimatedGIFLabel(QLabel):
    """QLabel‑виджет с поддержкой анимированных GIF (через Pillow)."""

    def __init__(self, gif_path: str | None = None, parent=None):
        super().__init__(parent)
        self._frames: list[QPixmap] = []
        self._cur = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

        if gif_path and os.path.exists(gif_path) and PIL_AVAILABLE:
            self._load(gif_path)
        else:
            self._set_placeholder()

    def _set_placeholder(self):
        """Серый прямоугольник – запасной вариант."""
        pix = QPixmap(100, 60)
        pix.fill(QColor("#3498db"))
        self.setPixmap(pix)
        self.setAlignment(Qt.AlignCenter)

    def _load(self, path: str):
        """Читает GIF через Pillow и формирует список QPixmap‑ов."""
        try:
            pil = Image.open(path)
            frames = []

            for frame in ImageSequence.Iterator(pil):
                if frame.mode in ("P", "L"):
                    frame = frame.convert("RGBA")
                elif frame.mode != "RGBA":
                    frame = frame.convert("RGBA")

                data = frame.tobytes("raw", "RGBA")
                qimg = QImage(
                    data,
                    frame.width,
                    frame.height,
                    QImage.Format_RGBA8888,
                )
                qp = QPixmap.fromImage(qimg).scaled(
                    100,
                    60,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                frames.append(qp)

            if frames:
                self._frames = frames
                self.setPixmap(self._frames[0])
                self.setAlignment(Qt.AlignCenter)
                self._timer.start(100)
            else:
                self._set_placeholder()
        except Exception:
            self._set_placeholder()

    def _next_frame(self):
        """Показывает следующий кадр анимации."""
        if not self._frames:
            return
        self._cur = (self._cur + 1) % len(self._frames)
        self.setPixmap(self._frames[self._cur])


# -------------------------------------------------
#   Выпадающий список тем
# -------------------------------------------------
class ThemeDropdown(QWidget):
    """
    Кастомный dropdown, откуда пользователь выбирает одну из
    предопределённых цветовых схем.
    """
    theme_selected = Signal(str, str, str, str)  # bg, card, text, name

    def __init__(self, current_theme: str, parent=None):
        super().__init__(parent)
        self.current_theme = current_theme
        self.is_open = False

        # name → (bg, card, text)
        self.themes = {
            "black": ("#000000", "#454545", "white"),
            "gray": ("#808080", "#A0A0A0", "black"),
            "white": ("#FFFFFF", "#E0E0E0", "black"),
        }
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QWidget()
        self.header.setCursor(Qt.PointingHandCursor)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(10, 5, 10, 5)

        self.lbl_selected = QLabel(self.current_theme)
        self.lbl_arrow = QLabel("▼")
        hl.addWidget(self.lbl_selected)
        hl.addStretch()
        hl.addWidget(self.lbl_arrow)

        self.options = QWidget()
        self.options.setVisible(False)
        opt_layout = QVBoxLayout(self.options)
        opt_layout.setContentsMargins(0, 0, 0, 0)
        opt_layout.setSpacing(1)

        for name, (bg, card, txt) in self.themes.items():
            w = QWidget()
            w.setFixedHeight(30)
            w.setCursor(Qt.PointingHandCursor)
            l = QHBoxLayout(w)
            l.setContentsMargins(10, 0, 10, 0)

            lbl = QLabel(name)
            l.addWidget(lbl)

            w.theme_data = (bg, card, txt, name)
            w.mousePressEvent = lambda ev, w=w: self._choose_theme(*w.theme_data)

            opt_layout.addWidget(w)

        layout.addWidget(self.header)
        layout.addWidget(self.options)

        self.header.mousePressEvent = self._toggle

    def _toggle(self, ev):
        self.is_open = not self.is_open
        self.options.setVisible(self.is_open)
        self.lbl_arrow.setText("▲" if self.is_open else "▼")

    def _choose_theme(self, bg, card, txt, name):
        """Срабатывает, когда пользователь кликнул по теме."""
        self.lbl_selected.setText(name)
        self.options.setVisible(False)
        self.lbl_arrow.setText("▼")
        self.is_open = False
        self.theme_selected.emit(bg, card, txt, name)


# -------------------------------------------------
#   Диалог «Options» (тема + масштаб)
# -------------------------------------------------
class OptionsDialog(QDialog):
    """
    Диалог, в котором пользователь меняет цветовую тему и
    масштаб (scale) пони.
    """
    scale_changed = Signal(float)  # новый масштаб

    def __init__(self, current_theme_name: str, current_scale: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.setFixedSize(350, 250)
        self.setModal(True)

        self._theme_name = current_theme_name
        self._scale = current_scale

        self._setup_ui()

    def _setup_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(20, 20, 20, 20)
        vbox.setSpacing(15)

        # ========= Цветовая тема =========
        theme_group = QGroupBox("Color Theme")
        tg_layout = QVBoxLayout(theme_group)

        self.theme_dropdown = ThemeDropdown(self._theme_name)
        tg_layout.addWidget(self.theme_dropdown)

        vbox.addWidget(theme_group)

        # ========= Масштаб пони =========
        scale_group = QGroupBox("Pony Scale")
        sg_layout = QVBoxLayout(scale_group)

        self.lbl_scale = QLabel()
        self.lbl_scale.setAlignment(Qt.AlignCenter)
        sg_layout.addWidget(self.lbl_scale)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(25)
        self.slider.setMaximum(200)
        self.slider.setValue(int(self._scale * 100))
        self.slider.valueChanged.connect(self._on_slider_move)

        sg_layout.addWidget(self.slider)

        vbox.addWidget(scale_group)

        # ==== нижняя панель (Apply / Close) ====
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Apply Scale")
        self.btn_close = QPushButton("Close")
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        self.btn_apply.clicked.connect(self._apply_and_close)
        self.btn_close.clicked.connect(self.reject)

        vbox.addStretch()
        vbox.addLayout(btn_layout)

        self._on_slider_move(self.slider.value())

    def _on_slider_move(self, val: int):
        """Обновляем подпись, пока пользователь двигает ползунок."""
        self._scale = val / 100.0
        self.lbl_scale.setText(f"Scale: {val}%")

    def _apply_and_close(self):
        """
        Пользователь нажал «Apply Scale». Сигнал scale_changed
        посылается наружу, а диалог закрывается (accept).
        """
        self.scale_changed.emit(self._scale)
        self.accept()


# =========================================================
#   Главное окно приложения
# =========================================================
class DynamicPonySelector(QMainWindow):
    """Главное окно – лист выбора пони, запуск/остановка процессов."""

    CONFIG_FILENAME = "theme_config.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DPP2 – Pony Selector")
        self.setGeometry(100, 100, 560, 560)
        self.setMinimumSize(420, 420)

        # ------------ данные о пони ------------
        self.pony_names = [
            "Twilight Sparkle", "Rainbow Dash", "Pinkie Pie", "Apple Jack",
            "Fluttershy", "Rarity", "Trixie", "Starlight", "Sunset",
            "Cadance", "Celestia", "Luna"
        ]

        # короткие пути к gif‑превью (папка pony_previews должна существовать)
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

        # ------------ настройки по умолчанию ------------
        self.current_bg = "#000000"
        self.current_card_bg = "#454545"
        self.current_text_color = "white"
        self.current_theme_name = "black"
        self.current_scale = 0.95

        # Включён/выключен каждый pony
        self.selected_ponies: dict[str, bool] = {name: False for name in self.pony_names}

        # Словарь запущенных процессов: имя → (Popen‑объект, pid)
        self.running_processes: dict[str, tuple[subprocess.Popen, int]] = {}

        # Флаги UI
        self.main_window_hidden = False

        # ---------------------------------------------------
        #  Чтение сохранённого конфига
        # ---------------------------------------------------
        self._load_config()

        # ---------------------------------------------------
        #  UI
        # ---------------------------------------------------
        self._init_ui()

        # ---------------------------------------------------
        #  Таймер, следящий за завершением всех дочерних процессов
        # ---------------------------------------------------
        self.restore_timer = QTimer(self)
        self.restore_timer.timeout.connect(self._check_and_restore)
        self.restore_timer.start(2000)  # каждые 2 сек

    # -----------------------------------------------------------------
    #  Конфиг
    # -----------------------------------------------------------------
    def _config_path(self) -> str:
        """Полный путь к конфиг‑файлу рядом со скриптом."""
        return os.path.join(os.path.abspath(os.path.dirname(__file__)), self.CONFIG_FILENAME)

    def _load_config(self):
        """Считывает конфиг, если файл существует."""
        try:
            cfg_path = self._config_path()
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                self.current_bg = cfg.get("bg_color", self.current_bg)
                self.current_card_bg = cfg.get("card_color", self.current_card_bg)
                self.current_text_color = cfg.get("text_color", self.current_text_color)
                self.current_theme_name = cfg.get("theme_name", self.current_theme_name)
                self.current_scale = cfg.get("pony_scale", self.current_scale)

                saved_ponies = cfg.get("selected_ponies", {})
                for name in self.pony_names:
                    self.selected_ponies[name] = bool(saved_ponies.get(name, False))
        except Exception as e:
            print(f"[WARN] Не удалось загрузить конфиг: {e}")

    def _save_config(self):
        """Записывает текущие настройки в ``theme_config.json``."""
        try:
            self._sync_selected_ponies_from_checkboxes()

            cfg = {
                "bg_color": self.current_bg,
                "card_color": self.current_card_bg,
                "text_color": self.current_text_color,
                "theme_name": self.current_theme_name,
                "pony_scale": self.current_scale,
                "selected_ponies": self.selected_ponies,
            }

            with open(self._config_path(), "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[ERROR] Не удалось сохранить конфиг: {e}")

    # -----------------------------------------------------------------
    #  Синхронизация состояний чекбоксов
    # -----------------------------------------------------------------
    def _sync_selected_ponies_from_checkboxes(self):
        """Считывает состояния всех чекбоксов в ``self.selected_ponies``."""
        for name, cb in self.checkboxes.items():
            self.selected_ponies[name] = cb.isChecked()

    def _sync_checkboxes_from_selected_ponies(self):
        """Обновляет чекбоксы в соответствии с ``self.selected_ponies``."""
        for name, cb in self.checkboxes.items():
            cb.setChecked(self.selected_ponies.get(name, False))

    # -----------------------------------------------------------------
    #  UI
    # -----------------------------------------------------------------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_v = QVBoxLayout(central)
        main_v.setContentsMargins(10, 10, 10, 10)
        main_v.setSpacing(10)

        self.lbl_title = QLabel("DPP2 – Pony Selector")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        main_v.addWidget(self.lbl_title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setSpacing(10)
        self.cards_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.cards_container)
        main_v.addWidget(self.scroll)

        bot = QWidget()
        bot_h = QHBoxLayout(bot)
        bot_h.setContentsMargins(0, 0, 0, 0)

        self.btn_options = QPushButton("options")
        self.btn_stop = QPushButton("stop all")
        self.btn_start = QPushButton("start")

        bot_h.addWidget(self.btn_options)
        bot_h.addStretch()
        bot_h.addWidget(self.btn_stop)
        bot_h.addWidget(self.btn_start)

        main_v.addWidget(bot)

        self.btn_options.clicked.connect(self._show_options_dialog)
        self.btn_stop.clicked.connect(self.stop_all)
        self.btn_start.clicked.connect(self._launch_selected)

        self.checkboxes: dict[str, QCheckBox] = {}

        self._apply_theme()
        self._create_cards()

    # -----------------------------------------------------------------
    #  Тема
    # -----------------------------------------------------------------
    def _apply_theme(self):
        """Обновляет стили всех виджетов в соответствии с текущей темой."""
        self.setStyleSheet(f"""
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
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
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
            QScrollArea {{
                border: none;
                background-color: {self.current_bg};
            }}
            QScrollBar:vertical {{
                background: {self.current_card_bg};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: #666;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #888;
            }}
        """)

        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)

        self.lbl_title.setStyleSheet(f"""
            color: {self.current_text_color};
            font-size: 16px;
            font-weight: bold;
        """)

    # -----------------------------------------------------------------
    #  Карточки пони
    # -----------------------------------------------------------------
    def _create_cards(self):
        """Создаёт (или пересоздаёт) все карточки с учётом текущей темы."""
        for i in reversed(range(self.cards_grid.count())):
            widget = self.cards_grid.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        self.checkboxes.clear()

        area_width = self.scroll.viewport().width()
        cols = max(2, area_width // 170)

        for idx, name in enumerate(self.pony_names):
            card = QWidget()
            card.setFixedSize(150, 120)

            card.setStyleSheet(f"""
                QWidget {{
                    background-color: {self.current_card_bg};
                    border: 1px solid #555;
                    border-radius: 8px;
                }}
            """)

            c_v = QVBoxLayout(card)
            c_v.setContentsMargins(5, 5, 5, 5)
            c_v.setSpacing(3)

            gif_w = QWidget()
            gif_w.setFixedHeight(80)
            g_l = QVBoxLayout(gif_w)
            g_l.setContentsMargins(0, 0, 0, 0)

            gif_file = self.pony_gifs.get(name, "placeholder.gif")
            gif_path = os.path.join("pony_previews", gif_file)
            gif_lbl = AnimatedGIFLabel(gif_path)
            g_l.addWidget(gif_lbl)

            info_w = QWidget()
            info_w.setFixedHeight(25)
            i_h = QHBoxLayout(info_w)
            i_h.setContentsMargins(5, 0, 5, 0)

            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(f"color: {self.current_text_color}; font-weight: bold; font-size: 10px;")
            name_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            cb = QCheckBox()
            cb.setFixedSize(20, 20)
            cb.setChecked(self.selected_ponies.get(name, False))

            self.checkboxes[name] = cb

            i_h.addWidget(name_lbl)
            i_h.addStretch()
            i_h.addWidget(cb)

            c_v.addWidget(gif_w)
            c_v.addWidget(info_w)

            row = idx // cols
            col = idx % cols
            self.cards_grid.addWidget(card, row, col)

    # -----------------------------------------------------------------
    #  События окна
    # -----------------------------------------------------------------
    def resizeEvent(self, event):
        """Пересоздаём карточки при изменении размеров окна."""
        super().resizeEvent(event)
        self._create_cards()

    # -----------------------------------------------------------------
    #  Диалог настроек
    # -----------------------------------------------------------------
    def _show_options_dialog(self):
        """Открывает диалог «Options» и ловит его сигналы."""
        dlg = OptionsDialog(
            current_theme_name=self.current_theme_name,
            current_scale=self.current_scale,
            parent=self,
        )
        dlg.theme_dropdown.theme_selected.connect(self._on_theme_changed)
        dlg.scale_changed.connect(self._on_scale_changed)

        dlg.exec()

    def _on_theme_changed(self, bg, card, txt, name):
        """Слот, вызываемый темой из OptionsDialog."""
        self.current_bg = bg
        self.current_card_bg = card
        self.current_text_color = txt
        self.current_theme_name = name

        self._apply_theme()
        self._create_cards()
        self._save_config()

    def _on_scale_changed(self, new_scale: float):
        """Слот, вызываемый при изменении масштаба в OptionsDialog."""
        if abs(new_scale - self.current_scale) < 1e-6:
            return

        self.current_scale = new_scale
        self._save_config()

        # Если уже запущены пони – перезапускаем их
        self._restart_running_ponies()

    # -----------------------------------------------------------------
    #  Запуск / остановка пони
    # -----------------------------------------------------------------
    def _launch_selected(self):
        """Собирает список выбранных пони и запускает их."""
        self._sync_selected_ponies_from_checkboxes()

        to_start = [name for name, ok in self.selected_ponies.items() if ok]

        if not to_start:
            QMessageBox.warning(self, "Внимание", "Не выбрано ни одного пони!")
            return

        self._save_config()

        self.hide()
        self.main_window_hidden = True
        print(f"[DEBUG] Окно скрыто. Запускаем пони: {to_start}")

        for name in to_start:
            self._start_pony_subprocess(name)

    def stop_all(self):
        """Останавливает все запущенные пони и показывает главное окно."""
        print(f"[DEBUG] Остановка всех процессов. Всего процессов: {len(self.running_processes)}")
        for name, (proc, pid) in list(self.running_processes.items()):
            print(f"[DEBUG] Останавливаю {name} (pid={pid})")
            try:
                self._kill_process_tree(pid)
            except Exception as e:
                print(f"[DEBUG] Ошибка при остановке {name}: {e}")
        self.running_processes.clear()
        self.main_window_hidden = False
        self.show()
        print("[DEBUG] Все процессы остановлены, окно показано")

    def _kill_process_tree(self, pid: int):
        """Убивает процесс и все дочерние (кроссплатформенно)."""
        try:
            if os.name == "nt":  # Windows
                import ctypes
                PROCESS_TERMINATE = 1
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                ctypes.windll.kernel32.TerminateProcess(handle, -1)
                ctypes.windll.kernel32.CloseHandle(handle)
            else:  # POSIX (Linux/macOS)
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
        except Exception as e:
            print(f"[WARN] Не удалось завершить процесс {pid}: {e}")

    # -----------------------------------------------------------------
    def _check_and_restore(self):
        """Таймер проверяет, закончились ли все дочерние процессы."""
        if not self.main_window_hidden:
            return

        # Удаляем завершенные процессы
        dead = []
        for name, (proc, pid) in list(self.running_processes.items()):
            if proc.poll() is not None:
                dead.append(name)
                print(f"[DEBUG] Процесс {name} завершился")

        for name in dead:
            self.running_processes.pop(name, None)

        # Если не осталось процессов - показываем окно
        if not self.running_processes:
            print("[DEBUG] Все процессы завершены, показываем окно")
            self.main_window_hidden = False
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            print(f"[DEBUG] Активных процессов: {len(self.running_processes)}")

    # -----------------------------------------------------------------
    #  Перезапуск с новым масштабом
    # -----------------------------------------------------------------
    def _restart_running_ponies(self):
        """Если какие‑то пони уже запущены, останавливаем их и запускаем снова."""
        if not self.running_processes:
            return

        print(f"[DEBUG] Перезапуск {len(self.running_processes)} пони с новым масштабом {self.current_scale}")

        running = list(self.running_processes.keys())
        for name in running:
            proc, pid = self.running_processes.pop(name, (None, None))
            if pid:
                print(f"[DEBUG] Останавливаю {name} для перезапуска")
                self._kill_process_tree(pid)

        for name in running:
            print(f"[DEBUG] Запускаю {name} после перезапуска")
            self._start_pony_subprocess(name)

    # -----------------------------------------------------------------
    #  Запуск отдельного пони
    # -----------------------------------------------------------------
    def _start_pony_subprocess(self, pony_name: str):
        """
        Запускает отдельного пони (скрипт ``pony.py``) в отдельном процессе.
        """
        try:
            import shutil

            script_dir = os.path.abspath(os.path.dirname(__file__))
            meipass = getattr(sys, "_MEIPASS", None)
            exe_dir = os.path.abspath(os.path.dirname(sys.executable)) if getattr(sys, "executable", None) else None

            search_paths = [script_dir]
            if meipass:
                search_paths.append(meipass)
            if exe_dir and exe_dir not in search_paths:
                search_paths.append(exe_dir)

            rel_candidates = [
                "pony.py",
                os.path.join("DPP2serverUDP", "Client", "characters", "pony.py"),
                os.path.join("characters", "pony.py"),
            ]

            pony_script = None
            for base in search_paths:
                for rel in rel_candidates:
                    candidate = os.path.join(base, rel)
                    if os.path.isfile(candidate):
                        pony_script = os.path.abspath(candidate)
                        break
                if pony_script:
                    break

            if not pony_script:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    "Не найден файл pony.py. Поместите его рядом с DPP2.py "
                    "или в одну из поисковых папок.",
                )
                return

            exe_name = os.path.basename(sys.executable or "").lower()
            if "python" in exe_name:
                python_bin = sys.executable
            else:
                python_bin = shutil.which("pythonw") or shutil.which("python") or shutil.which("python3")
                if not python_bin:
                    QMessageBox.critical(self, "Ошибка", "Не найден интерпретатор Python для запуска pony.py.")
                    return

            cmd = [python_bin, pony_script, pony_name, str(self.current_scale)]
            print(f"[DEBUG] Запуск {pony_name}: {' '.join(cmd)}")

            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | subprocess.CREATE_NEW_PROCESS_GROUP
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=script_dir,
                    startupinfo=startupinfo,
                    creationflags=creation_flags,
                )
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=script_dir,
                    preexec_fn=os.setsid,
                )

            pid = proc.pid
            self.running_processes[pony_name] = (proc, pid)
            print(f"[DEBUG] Процесс {pony_name} (pid={pid}) запущен")

            threading.Thread(
                target=self._monitor_process,
                args=(pony_name, proc),
                daemon=True,
            ).start()

        except Exception as exc:
            print(f"[ERROR] Не удалось запустить пони {pony_name}: {exc}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось стартовать {pony_name}:\n{exc}")

    def _monitor_process(self, pony_name: str, proc: subprocess.Popen):
        """Ожидает завершения процесса и удаляет запись из словаря."""
        try:
            proc.wait()
            print(f"[DEBUG] Процесс {pony_name} завершился")
        except Exception as e:
            print(f"[DEBUG] Процесс {pony_name} завершился с ошибкой: {e}")
        finally:
            if pony_name in self.running_processes:
                self.running_processes.pop(pony_name, None)

    # -----------------------------------------------------------------
    def closeEvent(self, event):
        """Сохраняем конфиг и завершаем все подпроцессы перед закрытием."""
        self._save_config()
        self.stop_all()
        self.restore_timer.stop()
        event.accept()


# =========================================================
#   Точка входа
# =========================================================
def main() -> int:
    """Запуск GUI‑приложения."""
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        win = DynamicPonySelector()
        win.show()

        return app.exec()
    except Exception as e:
        print(f"[FATAL] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())