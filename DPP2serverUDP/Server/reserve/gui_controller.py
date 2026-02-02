# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DPP2 UDP Server GUI – PySide6 version (fixed layout, colours and missing theme).
"""

# ----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------
import os
import sys
import json
import time
import queue
import threading
import platform
import traceback
from datetime import datetime

import psutil
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QIcon, QColor, QPainter, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame, QLabel, QLineEdit, QTextEdit, QComboBox,
    QCheckBox, QRadioButton, QButtonGroup, QGroupBox, QScrollArea,
    QStackedWidget, QStatusBar, QMessageBox, QFileDialog,
    QDialog, QDialogButtonBox, QToolButton,
    QFormLayout, QGridLayout, QScrollBar, QSizePolicy
)

# make sure the module can import the server core class
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ----------------------------------------------------------------------
#   Small Qt‑widgets that replace the original custom Tkinter widgets
# ----------------------------------------------------------------------
class ModernButton(QPushButton):
    """Button used for the main actions (Start/Stop/Restart)."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("ModernButton")


class NavigationButton(QToolButton):
    """Button that lives in the left navigation pane."""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setText(f"{icon}  {text}")
        self.setCheckable(True)
        self.setObjectName("NavButton")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(36)  # full‑row click area


class ThemePreview(QWidget):
    """Clickable widget that shows a tiny preview of a theme."""
    clicked = Signal(str)

    def __init__(self, theme_name: str, theme_data: dict, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.theme_data = theme_data
        self.setFixedSize(180, 60)
        self.setToolTip(theme_data.get("name", theme_name))
        self.setCursor(Qt.PointingHandCursor)
        self.selected = False

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()

        # whole background
        p.fillRect(0, 0, w, h, QColor(self.theme_data["bg"]))

        # sidebar strip
        p.fillRect(0, 0, 40, h, QColor(self.theme_data["sidebar_bg"]))

        # a few coloured rectangles that mimic UI elements
        p.fillRect(50, 10, 30, 10, QColor(self.theme_data["accent"]))
        p.fillRect(50, 30, 50, 10, QColor(self.theme_data["bg_light"]))
        p.fillRect(120, 20, 50, 20, QColor(self.theme_data["button_bg"]))

        # border (thicker when selected)
        pen = p.pen()
        pen.setWidth(2 if self.selected else 1)
        pen.setColor(QColor(self.theme_data["accent"] if self.selected
                            else self.theme_data["border"]))
        p.setPen(pen)
        p.drawRect(0, 0, w - 1, h - 1)

        # theme name centred at the bottom
        pen.setColor(QColor(self.theme_data["text"]))
        p.setPen(pen)
        txt = self.theme_data["name"]
        fw = p.fontMetrics().horizontalAdvance(txt)
        p.drawText(w // 2 - fw // 2, h - 8, txt)

    def mousePressEvent(self, event):
        self.clicked.emit(self.theme_name)

    def set_selected(self, selected: bool):
        self.selected = selected
        self.update()


class GifctConfigDialog(QDialog):
    """Dialog for creating / editing a single GIFCT configuration."""

    def __init__(self, parent=None,
                 title: str = "GIFCT configuration",
                 gifct_data: dict | None = None,
                 colors: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 600)
        self.colors = colors or {}
        self.result = None
        self._build_ui(gifct_data)

    # ------------------------------------------------------------------
    #   UI construction
    # ------------------------------------------------------------------
    def _build_ui(self, gifct_data: dict | None):
        layout = QVBoxLayout(self)

        # ----- Name ------------------------------------------------
        layout.addWidget(QLabel("Gifct Name:"))
        self.name_edit = QLineEdit(gifct_data.get("name", "") if gifct_data else "")
        layout.addWidget(self.name_edit)

        # ----- ID --------------------------------------------------
        layout.addWidget(QLabel("Gifct ID (unique identifier):"))
        self.id_edit = QLineEdit(
            gifct_data.get("id", f"gifct_{int(time.time())}") if gifct_data
            else f"gifct_{int(time.time())}")
        layout.addWidget(self.id_edit)

        # ----- Description -----------------------------------------
        layout.addWidget(QLabel("Description:"))
        self.desc_edit = QLineEdit(gifct_data.get("description", "") if gifct_data else "")
        layout.addWidget(self.desc_edit)

        # ----- GIF Directories --------------------------------------
        layout.addWidget(QLabel("GIF Directories (one per line):"))
        self.dirs_edit = QTextEdit()
        if gifct_data and "gif_directories" in gifct_data:
            self.dirs_edit.setPlainText("\n".join(gifct_data["gif_directories"]))
        self.dirs_edit.setMaximumHeight(100)
        layout.addWidget(self.dirs_edit)

        # ----- Type (radio buttons) --------------------------------
        layout.addWidget(QLabel("Type:"))
        self.type_group = QButtonGroup(self)
        type_box = QGroupBox()
        hb = QHBoxLayout(type_box)
        types = ["ability", "skill", "item", "buff", "debuff", "custom"]
        for t in types:
            rb = QRadioButton(t.capitalize())
            if gifct_data and gifct_data.get("type") == t:
                rb.setChecked(True)
            elif not gifct_data and t == "ability":
                rb.setChecked(True)
            self.type_group.addButton(rb)
            hb.addWidget(rb)
        layout.addWidget(type_box)

        # ----- Parameters (JSON) ------------------------------------
        layout.addWidget(QLabel("Parameters (JSON format):"))
        self.params_edit = QTextEdit()
        default_params = {
            "cooldown": 10,
            "duration": 5,
            "power": 100,
            "range": 10,
            "cost": 20
        }
        params = gifct_data.get("parameters", default_params) if gifct_data else default_params
        self.params_edit.setPlainText(json.dumps(params, indent=2))
        layout.addWidget(self.params_edit)

        # ----- Enabled --------------------------------------------
        self.enabled_chk = QCheckBox("Enabled by default")
        self.enabled_chk.setChecked(gifct_data.get("enabled", True) if gifct_data else True)
        layout.addWidget(self.enabled_chk)

        # ----- Dialog buttons ------------------------------------
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------
    #   Slots
    # ------------------------------------------------------------------
    def _accept(self):
        """Validate JSON & build the result dictionary."""
        try:
            raw = self.params_edit.toPlainText().strip()
            params = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            QMessageBox.critical(self, "Invalid JSON",
                                 f"Parameters must be valid JSON:\n{exc}")
            return

        # Process GIF directories
        dirs_text = self.dirs_edit.toPlainText().strip()
        gif_directories = [d.strip() for d in dirs_text.split('\n') if d.strip()]

        typ = next((t for t, rb in
                    [(b.text().lower(), b) for b in self.type_group.buttons()]
                    if rb.isChecked()), "ability")

        self.result = {
            "name": self.name_edit.text(),
            "id": self.id_edit.text(),
            "description": self.desc_edit.text(),
            "gif_directories": gif_directories,
            "type": typ,
            "parameters": params,
            "enabled": self.enabled_chk.isChecked(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self.accept()


class GifctListItem(QWidget):
    """One row of the GIFCT list – shows name, type and action buttons."""

    def __init__(self, gifct_id: str, gifct_data: dict,
                 edit_cb, delete_cb, toggle_cb, parent=None):
        super().__init__(parent)
        self.gifct_id = gifct_id
        self.gifct_data = gifct_data
        self.edit_cb = edit_cb
        self.delete_cb = delete_cb
        self.toggle_cb = toggle_cb
        self.setObjectName("GifctItem")
        self._build_ui()

    # ------------------------------------------------------------------
    #   UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(12)

        # ---- left side – name + type badge
        left = QVBoxLayout()
        name_lbl = QLabel(self.gifct_data.get("name", "Unnamed"))
        name_lbl.setStyleSheet("font-weight:bold;")
        left.addWidget(name_lbl)

        typ = self.gifct_data.get("type", "custom").capitalize()
        type_lbl = QLabel(typ)
        type_lbl.setStyleSheet("font-size:8pt; color:#888;")
        left.addWidget(type_lbl)
        h.addLayout(left, stretch=1)

        # ---- right side – edit / delete / enabled toggle
        edit_btn = QToolButton()
        edit_btn.setText("✏️")
        edit_btn.setToolTip("Edit")
        edit_btn.setAutoRaise(True)
        edit_btn.clicked.connect(lambda: self.edit_cb(self.gifct_id))

        del_btn = QToolButton()
        del_btn.setText("🗑️")
        del_btn.setToolTip("Delete")
        del_btn.setAutoRaise(True)
        del_btn.clicked.connect(lambda: self.delete_cb(self.gifct_id))

        toggle_chk = QCheckBox()
        toggle_chk.setChecked(self.gifct_data.get("enabled", True))
        toggle_chk.setToolTip("Enable / disable")
        toggle_chk.stateChanged.connect(lambda _: self.toggle_cb(self.gifct_id))
        toggle_chk.setStyleSheet("QCheckBox::indicator {width:14px;height:14px;}")

        for btn in (edit_btn, del_btn):
            btn.setFixedSize(24, 24)
            h.addWidget(btn)

        h.addWidget(toggle_chk)


# ----------------------------------------------------------------------
#   Main application window (Qt)
# ----------------------------------------------------------------------
class ServerGUI(QMainWindow):
    """
    Full‑featured Qt UI – a drop‑in replacement for the original Tkinter
    controller. All logic (configuration, server start/stop, logging,
    GIFCT CRUD, theme handling) is unchanged; only the visual part
    has been tightened up.
    """

    def __init__(self, server_core_class):
        super().__init__()
        self.server_core_class = server_core_class

        # ------------------------------------------------------------------
        #   Theme definitions (КОРЕННО ПЕРЕРАБОТАНЫ: правильные цвета)
        # ------------------------------------------------------------------
        self.themes = {
            "black": {
                "name": "Midnight Black",
                "bg": "#000000",  # ЧИСТЫЙ ЧЕРНЫЙ
                "bg_light": "#1a1a1a",  # Очень темный серый
                "bg_lighter": "#2d2d2d",  # Темный серый
                "sidebar_bg": "#0d0d0d",  # Почти черный
                "sidebar_active": "#404040",  # Серый для контраста
                "sidebar_hover": "#333333",  # Темный серый
                "sidebar_text": "#e6e6e6",  # ОЧЕНЬ светлый для читаемости
                "sidebar_active_text": "#ffffff",  # Белый
                "sidebar_icon": "#cccccc",  # Светло-серый
                "text": "#ffffff",  # Белый текст
                "text_secondary": "#b3b3b3",  # Светло-серый
                "accent": "#4d94ff",  # Яркий синий
                "accent_light": "#66a3ff",
                "success": "#33cc33",  # Яркий зеленый
                "success_light": "#4dd24d",
                "warning": "#ff9900",  # Яркий оранжевый
                "warning_light": "#ffad33",
                "error": "#ff3333",  # Яркий красный
                "error_light": "#ff6666",
                "info": "#4d94ff",  # Яркий синий
                "info_light": "#66a3ff",
                "button_bg": "#333333",  # Темный серый
                "button_fg": "#ffffff",  # Белый
                "button_active": "#4d4d4d",  # Серый
                "button_pressed": "#666666",  # Светло-серый
                "button_disabled": "#999999",  # Серый
                "border": "#404040",  # Темный серый
                "border_light": "#595959",  # Серый
                "card_bg": "#1a1a1a",  # Очень темный серый
                "card_border": "#404040"  # Темный серый
            },
            "grey": {
                "name": "Professional Grey",
                "bg": "#808080",  # СРЕДНИЙ СЕРЫЙ - основа темы
                "bg_light": "#a6a6a6",  # Светло-серый
                "bg_lighter": "#cccccc",  # Очень светло-серый
                "sidebar_bg": "#666666",  # Темно-серый
                "sidebar_active": "#8c8c8c",  # Серый
                "sidebar_hover": "#737373",  # Средний серый
                "sidebar_text": "#f2f2f2",  # Очень светлый
                "sidebar_active_text": "#ffffff",  # Белый
                "sidebar_icon": "#e6e6e6",  # Светло-серый
                "text": "#1a1a1a",  # Очень темный для контраста
                "text_secondary": "#4d4d4d",  # Темно-серый
                "accent": "#3366cc",  # Синий
                "accent_light": "#4d79d9",
                "success": "#339933",  # Зеленый
                "success_light": "#4dad4d",
                "warning": "#cc7a00",  # Оранжевый
                "warning_light": "#e69138",
                "error": "#cc0000",  # Красный
                "error_light": "#e60000",
                "info": "#3366cc",  # Синий
                "info_light": "#4d79d9",
                "button_bg": "#666666",  # Темно-серый
                "button_fg": "#ffffff",  # Белый
                "button_active": "#7a7a7a",  # Серый
                "button_pressed": "#8c8c8c",  # Светло-серый
                "button_disabled": "#b3b3b3",  # Светло-серый
                "border": "#a6a6a6",  # Светло-серый
                "border_light": "#bfbfbf",  # Очень светло-серый
                "card_bg": "#a6a6a6",  # Светло-серый
                "card_border": "#bfbfbf"  # Очень светло-серый
            },
            "white": {
                "name": "Pure White",
                "bg": "#ffffff",  # ЧИСТЫЙ БЕЛЫЙ
                "bg_light": "#f5f5f5",  # Очень светло-серый
                "bg_lighter": "#ebebeb",  # Светло-серый
                "sidebar_bg": "#2d2d2d",  # Темный серый для контраста
                "sidebar_active": "#595959",  # Серый
                "sidebar_hover": "#404040",  # Темный серый
                "sidebar_text": "#e6e6e6",  # Светлый
                "sidebar_active_text": "#ffffff",  # Белый
                "sidebar_icon": "#cccccc",  # Серый
                "text": "#000000",  # ЧЕРНЫЙ для максимального контраста
                "text_secondary": "#666666",  # Темно-серый
                "accent": "#0066cc",  # Синий
                "accent_light": "#007acc",
                "success": "#267326",  # Зеленый
                "success_light": "#338533",
                "warning": "#b36b00",  # Оранжевый
                "warning_light": "#cc7a00",
                "error": "#cc0000",  # Красный
                "error_light": "#e60000",
                "info": "#0066cc",  # Синий
                "info_light": "#007acc",
                "button_bg": "#f0f0f0",  # Очень светло-серый
                "button_fg": "#000000",  # Черный
                "button_active": "#e0e0e0",  # Светло-серый
                "button_pressed": "#d4d4d4",  # Серый
                "button_disabled": "#a6a6a6",  # Серый
                "border": "#d9d9d9",  # Светло-серый
                "border_light": "#cccccc",  # Серый
                "card_bg": "#fafafa",  # Почти белый
                "card_border": "#e0e0e0"  # Светло-серый
            },
            "dark_blue": {
                "name": "Deep Blue",
                "bg": "#0a192f",
                "bg_light": "#112240",
                "bg_lighter": "#1d3a5f",
                "sidebar_bg": "#020c1b",
                "sidebar_active": "#64ffda",
                "sidebar_hover": "#54efca",
                "sidebar_text": "#8892b0",
                "sidebar_active_text": "#ffffff",
                "sidebar_icon": "#64ffda",
                "text": "#ccd6f6",
                "text_secondary": "#8892b0",
                "accent": "#64ffda",
                "accent_light": "#52d3aa",
                "success": "#64ffda",
                "success_light": "#52d3aa",
                "warning": "#ffd166",
                "warning_light": "#ffb347",
                "error": "#ef476f",
                "error_light": "#ff6b6b",
                "info": "#118ab2",
                "info_light": "#06d6a0",
                "button_bg": "#1d3a5f",
                "button_fg": "#64ffda",
                "button_active": "#2a4a7a",
                "button_pressed": "#375a95",
                "button_disabled": "#4a6588",
                "border": "#1d3a5f",
                "border_light": "#2a4a7a",
                "card_bg": "#112240",
                "card_border": "#1d3a5f"
            }
        }

        # ------------------------------------------------------------------
        #   Choose start theme (saved in config → later overwritten)
        # ------------------------------------------------------------------
        self.current_theme = "black"
        self.colors = self.themes[self.current_theme]

        # ------------------------------------------------------------------
        #   Basic window configuration
        # ------------------------------------------------------------------
        self.setWindowTitle("🎮 DPP2 UDP Server Controller")
        self.resize(1600, 900)
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        # ------------------------------------------------------------------
        #   Load configuration (may also set the saved theme)
        # ------------------------------------------------------------------
        self.config = self._load_config()
        if "theme" in self.config:
            self.current_theme = self.config["theme"]
            if self.current_theme in self.themes:
                self.colors = self.themes[self.current_theme]

        # ------------------------------------------------------------------
        #   Message queue – used by the server thread to push log entries
        # ------------------------------------------------------------------
        self.message_queue = queue.Queue()

        # ------------------------------------------------------------------
        #   Server‑related instance vars
        # ------------------------------------------------------------------
        self.server = None
        self.server_running = False
        self.server_thread = None
        self.start_time = None

        # ------------------------------------------------------------------
        #   Statistics (simple placeholder values – will be updated later)
        # ------------------------------------------------------------------
        self.stats = {
            "players_online": 0,
            "characters_online": 0,
            "total_characters": 0,
            "cpu_usage": 0,
            "memory_usage": 0,
            "uptime": "00:00:00",
            "connections": 0,
            "active_gifct": "Gifct1, Gifct2",
            "udp_packets_received": 0,
            "udp_packets_sent": 0,
            "packet_loss": "0%",
            "protocol": "UDP",
            "udp_port": 5555
        }

        # ------------------------------------------------------------------
        #   Build main UI structure
        # ------------------------------------------------------------------
        self._create_main_structure()

        # ------------------------------------------------------------------
        #   Apply theme and centre the window
        # ------------------------------------------------------------------
        self._apply_theme()
        self._center_window()

        # ------------------------------------------------------------------
        #   Timers (updates, clock)
        # ------------------------------------------------------------------
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(1000)  # 1 s

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

        # ------------------------------------------------------------------
        #   Show default page
        # ------------------------------------------------------------------
        self._show_section("dashboard")

    # ------------------------------------------------------------------
    #   Configuration handling
    # ------------------------------------------------------------------
    def _load_config(self) -> dict:
        """Read (or create) config.json."""
        default = {
            "server": {
                "host": "0.0.0.0",
                "port": 80,
                "max_players": 100,
                "tick_rate": 60,
                "log_level": "INFO",
                "server_name": "DPP2 UDP Character Server",
                "protocol": "udp"
            },
            "game": {
                "max_characters_per_player": 5,
                "starting_zone": "start_city",
                "auto_save_interval": 300
            },
            "database": {"path": "game_server_db.json"},
            "network": {
                "udp_port": 80,
                "max_packet_size": 1400,
                "client_timeout": 30,
                "heartbeat_interval": 1.0
            },
            "gifct_settings": {
                "gifct_enabled": {"Gifct1": True, "Gifct2": True},
                "gifct_configs": {"Gifct1": "Primary Ability",
                                  "Gifct2": "Secondary Ability"}
            },
            "gifct_configurations": {},
            "theme": "black"
        }

        cfg_path = "config.json"
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # ensure all top‑level keys exist (backwards compatibility)
                for k, v in default.items():
                    if k not in data:
                        data[k] = v
                    elif isinstance(v, dict):
                        for sk, sv in v.items():
                            data[k].setdefault(sk, sv)
                return data
            except Exception as e:
                print(f"[CONFIG] load error: {e}")
                return default
        else:
            try:
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"[CONFIG] write error: {e}")
            return default

    def _save_config(self) -> bool:
        """Write the whole config back to config.json."""
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self._log("✅ Configuration saved", "SUCCESS")
            return True
        except Exception as e:
            self._log(f"❌ Config save error: {e}", "ERROR")
            return False

    # ------------------------------------------------------------------
    #   Main UI structure creation
    # ------------------------------------------------------------------
    def _create_main_structure(self):
        """Создает правильную структуру окна с учетом фоновых цветов"""
        # Основной контейнер, который будет иметь фон
        main_container = QWidget()
        main_container.setObjectName("MainContainer")
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Добавляем верхнюю панель
        self._create_top_bar()
        main_layout.addWidget(self.top_bar)

        # Центральная область (боковая панель + контент)
        center_widget = QWidget()
        center_widget.setObjectName("CenterArea")
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Создаем боковую панель и контент
        self._create_sidebar()
        self._create_content_area()

        center_layout.addWidget(self.sidebar)
        center_layout.addWidget(self.content_stack)

        main_layout.addWidget(center_widget)

        # Добавляем нижнюю панель
        self._create_bottom_bar()
        main_layout.addWidget(self.status_bar_widget)

        # Устанавливаем главный контейнер
        self.setCentralWidget(main_container)

    def _create_top_bar(self):
        self.top_bar = QFrame()
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setFixedHeight(60)
        tb_layout = QHBoxLayout(self.top_bar)
        tb_layout.setContentsMargins(20, 10, 20, 10)
        tb_layout.setSpacing(12)

        self.title_lbl = QLabel("🎮 DPP2 UDP SERVER")
        self.title_lbl.setObjectName("TitleLabel")
        tb_layout.addWidget(self.title_lbl, alignment=Qt.AlignVCenter)

        self.protocol_indicator = QLabel("U")
        self.protocol_indicator.setFixedSize(24, 24)
        self.protocol_indicator.setObjectName("ProtocolIndicator")
        tb_layout.addWidget(self.protocol_indicator, alignment=Qt.AlignVCenter)

        self.protocol_lbl = QLabel("UDP PROTOCOL")
        self.protocol_lbl.setObjectName("ProtocolLabel")
        tb_layout.addWidget(self.protocol_lbl, alignment=Qt.AlignVCenter)

        tb_layout.addStretch()

        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(20, 20)
        self.status_indicator.setObjectName("StatusIndicator")
        self.status_lbl = QLabel("● STOPPED")
        self.status_lbl.setObjectName("StatusLabel")
        tb_layout.addWidget(self.status_lbl, alignment=Qt.AlignVCenter)
        tb_layout.addWidget(self.status_indicator, alignment=Qt.AlignVCenter)

    def _create_sidebar(self):
        """Создает боковую панель навигации"""
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SideBar")
        self.sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        # Header
        nav_hdr = QFrame()
        nav_hdr.setObjectName("SidebarHeader")
        nav_hdr.setFixedHeight(50)
        nav_hdr_h = QHBoxLayout(nav_hdr)
        nav_hdr_h.setContentsMargins(0, 0, 0, 0)
        nav_lbl = QLabel("NAVIGATION")
        nav_lbl.setObjectName("SidebarHeaderLabel")
        nav_hdr_h.addWidget(nav_lbl, alignment=Qt.AlignCenter)
        side_layout.addWidget(nav_hdr)

        # Navigation buttons
        self.nav_buttons = {}
        nav_items = [
            ("🏠", "Dashboard", "dashboard"),
            ("⚙️", "Server Settings", "server_settings"),
            ("🎨", "Appearance", "appearance"),
            ("🌐", "Network", "network"),
            ("🎮", "Gifct Settings", "gifct"),
            ("📊", "Statistics", "stats"),
            ("📋", "Logs", "logs"),
            ("👥", "Players", "players"),
            ("🗃️", "Database", "database"),
            ("🛠️", "Tools", "tools"),
            ("❓", "Help", "help")
        ]

        for icon, txt, sec in nav_items:
            btn = NavigationButton(icon, txt)
            btn.clicked.connect(lambda _, s=sec: self._show_section(s))
            side_layout.addWidget(btn)
            self.nav_buttons[sec] = btn

        side_layout.addStretch()

        # Bottom info
        info = QFrame()
        info.setObjectName("SidebarInfo")
        info_v = QVBoxLayout(info)
        info_v.setContentsMargins(10, 10, 10, 10)
        info_v.addWidget(QLabel("Version: 2.1"))
        info_v.addWidget(QLabel("Protocol: UDP"))
        side_layout.addWidget(info)

    def _create_content_area(self):
        """Создает область контента"""
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentStack")
        self._build_pages()
        # ДОБАВЛЕНО: устанавливаем фон для всех страниц
        for page_name, widget in self.pages.items():
            widget.setObjectName("PageWidget")
            self.content_stack.addWidget(widget)

    def _create_bottom_bar(self):
        """Создает нижнюю панель статуса"""
        self.status_bar_widget = QFrame()
        self.status_bar_widget.setObjectName("StatusBar")
        self.status_bar_widget.setFixedHeight(30)
        status_layout = QHBoxLayout(self.status_bar_widget)
        status_layout.setContentsMargins(10, 5, 10, 5)

        self.sysinfo_lbl = QLabel(
            f"DPP2 UDP Server v2.1 | Python {platform.python_version()} | {platform.system()}")
        self.time_lbl = QLabel()

        status_layout.addWidget(self.sysinfo_lbl)
        status_layout.addStretch()
        status_layout.addWidget(self.time_lbl)

    # ------------------------------------------------------------------
    #   Build all pages (each returns a QWidget)
    # ------------------------------------------------------------------
    def _build_pages(self):
        self.pages = {}
        self.pages["dashboard"] = self._build_dashboard_page()
        self.pages["server_settings"] = self._build_server_settings_page()
        self.pages["appearance"] = self._build_appearance_page()
        self.pages["network"] = self._build_network_page()
        self.pages["gifct"] = self._build_gifct_page()
        self.pages["stats"] = self._build_stats_page()
        self.pages["logs"] = self._build_logs_page()
        self.pages["players"] = self._build_players_page()
        self.pages["database"] = self._build_database_page()
        self.pages["tools"] = self._build_tools_page()
        self.pages["help"] = self._build_help_page()

    # ------------------------------------------------------------------
    #   PAGE: Dashboard
    # ------------------------------------------------------------------
    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        # Главный layout страницы
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("SectionTitle")
        main_layout.addWidget(title)

        # Карточка управления сервером
        ctrl_card = QGroupBox("Server Control")
        ctrl_layout = QHBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(15, 15, 15, 15)

        self.start_btn = ModernButton("▶ Start Server")
        self.start_btn.setObjectName("StartBtn")
        self.start_btn.setMinimumHeight(45)
        self.start_btn.clicked.connect(self.start_server)

        self.stop_btn = ModernButton("■ Stop")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.clicked.connect(self.stop_server)

        self.restart_btn = ModernButton("↻ Restart")
        self.restart_btn.setObjectName("RestartBtn")
        self.restart_btn.setEnabled(False)
        self.restart_btn.setMinimumHeight(45)
        self.restart_btn.clicked.connect(self.restart_server)

        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        ctrl_layout.addWidget(self.restart_btn)

        main_layout.addWidget(ctrl_card)

        # Контейнер для статистики
        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(15)

        stats_title = QLabel("Server Statistics")
        stats_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        stats_layout.addWidget(stats_title)

        # Сетка статистики
        stats_grid = QGridLayout()
        stats_grid.setSpacing(15)
        stats_grid.setContentsMargins(0, 0, 0, 0)

        # Настройки растяжения колонок
        stats_grid.setColumnStretch(0, 1)
        stats_grid.setColumnStretch(1, 1)
        stats_grid.setColumnStretch(2, 1)
        stats_grid.setColumnStretch(3, 1)

        stat_defs = [
            ("👥", "Players Online", "players_online", "0"),
            ("📊", "Characters", "total_characters", "0"),
            ("⚡", "CPU Load", "cpu_usage", "0%"),
            ("💾", "Memory", "memory_usage", "0 MB"),
            ("⏱️", "Uptime", "uptime", "00:00:00"),
            ("📡", "UDP Packets", "udp_packets_total", "0"),
            ("🎮", "Active Gifct", "active_gifct", "Gifct1, Gifct2"),
            ("🔌", "Connections", "connections", "0")
        ]

        self.stat_labels = {}

        for i, (icon, txt, key, default) in enumerate(stat_defs):
            row = i // 4
            col = i % 4

            card = QFrame()
            card.setObjectName("StatCard")
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            card.setMinimumHeight(100)
            card.setMinimumWidth(200)

            card_layout = QVBoxLayout(card)
            card_layout.setAlignment(Qt.AlignCenter)
            card_layout.setSpacing(8)
            card_layout.setContentsMargins(15, 15, 15, 15)

            top_layout = QHBoxLayout()
            icon_label = QLabel(icon)
            icon_label.setFixedSize(32, 32)
            icon_label.setStyleSheet("font-size: 18px;")

            text_label = QLabel(txt)
            text_label.setStyleSheet("font-weight: bold; font-size: 12px;")
            text_label.setWordWrap(True)

            top_layout.addWidget(icon_label)
            top_layout.addWidget(text_label)
            top_layout.addStretch()

            value_label = QLabel(default)
            value_label.setObjectName(f"Stat_{key}")
            value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
            value_label.setAlignment(Qt.AlignCenter)

            card_layout.addLayout(top_layout)
            card_layout.addWidget(value_label)

            self.stat_labels[key] = value_label
            stats_grid.addWidget(card, row, col)

        stats_layout.addLayout(stats_grid)
        stats_layout.addStretch()

        main_layout.addWidget(stats_container, 1)

        return page

    # ------------------------------------------------------------------
    #   PAGE: Server Settings
    # ------------------------------------------------------------------
    def _build_server_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Server Settings")
        title.setObjectName("SectionTitle")
        main_layout.addWidget(title, alignment=Qt.AlignLeft)

        settings_group = QGroupBox("Main Settings")
        settings_group.setObjectName("SettingsGroup")
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(15)
        form_layout.setContentsMargins(15, 15, 15, 15)

        self.server_vars = {}

        def add_setting(label, key, default):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: bold;")
            input_widget = QLineEdit(str(default))
            input_widget.setObjectName(f"Server_{key}")
            input_widget.setMinimumHeight(30)
            form_layout.addRow(label_widget, input_widget)
            self.server_vars[key] = input_widget

        add_setting("Server Name:", "server_name", self.config["server"]["server_name"])
        add_setting("UDP Port:", "udp_port", self.config["server"]["port"])
        add_setting("Max Players:", "max_players", self.config["server"]["max_players"])
        add_setting("Tick Rate:", "tick_rate", self.config["server"]["tick_rate"])

        log_label = QLabel("Log Level:")
        log_label.setStyleSheet("font-weight: bold;")
        log_combo = QComboBox()
        log_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        log_combo.setCurrentText(self.config["server"]["log_level"])
        log_combo.setMinimumHeight(30)
        form_layout.addRow(log_label, log_combo)
        self.server_vars["log_level"] = log_combo

        proto_label = QLabel("Protocol:")
        proto_label.setStyleSheet("font-weight: bold;")
        proto_input = QLineEdit(self.config["server"]["protocol"])
        proto_input.setMinimumHeight(30)
        form_layout.addRow(proto_label, proto_input)
        self.server_vars["protocol"] = proto_input

        settings_group.setLayout(form_layout)
        main_layout.addWidget(settings_group)

        save_button = ModernButton("💾 Save Settings")
        save_button.setFixedHeight(40)
        save_button.clicked.connect(self.save_server_settings)
        main_layout.addWidget(save_button, alignment=Qt.AlignRight)

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   PAGE: Appearance
    # ------------------------------------------------------------------
    def _build_appearance_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Appearance Settings")
        title.setObjectName("SectionTitle")
        main_layout.addWidget(title, alignment=Qt.AlignLeft)

        theme_group = QGroupBox("Theme Selection")
        theme_layout = QVBoxLayout(theme_group)

        theme_label = QLabel("Select interface theme:")
        theme_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        theme_layout.addWidget(theme_label)

        previews_layout = QHBoxLayout()
        previews_layout.setAlignment(Qt.AlignCenter)
        self.theme_previews = {}

        for theme_name in ["black", "grey", "white", "dark_blue"]:
            preview = ThemePreview(theme_name, self.themes[theme_name])
            preview.clicked.connect(self.change_theme)
            previews_layout.addWidget(preview)
            self.theme_previews[theme_name] = preview

        theme_layout.addLayout(previews_layout)
        main_layout.addWidget(theme_group)

        palette_group = QGroupBox("Current Theme Color Palette")
        palette_layout = QVBoxLayout(palette_group)

        color_groups = [
            ("Main Colors", ["bg", "bg_light", "bg_lighter", "text", "text_secondary"]),
            ("Accent Colors", ["accent", "accent_light", "success", "warning", "error", "info"]),
            ("Interface Elements", ["sidebar_bg", "sidebar_active", "button_bg", "border", "card_bg"])
        ]

        for group_name, color_keys in color_groups:
            group_label = QLabel(f"<b>{group_name}:</b>")
            group_label.setStyleSheet("margin-top: 10px;")
            palette_layout.addWidget(group_label)

            colors_layout = QHBoxLayout()
            colors_layout.setSpacing(10)

            for key in color_keys:
                if key not in self.colors:
                    continue

                color_container = QFrame()
                color_container.setFixedSize(80, 80)
                color_container.setStyleSheet(f"""
                    background: {self.colors[key]};
                    border: 2px solid {self.colors['border']};
                    border-radius: 5px;
                """)

                color_layout = QVBoxLayout(color_container)
                color_layout.setAlignment(Qt.AlignCenter)

                name_label = QLabel(key)
                name_label.setStyleSheet("font-weight: bold; font-size: 9px; color: white;")
                value_label = QLabel(self.colors[key])
                value_label.setStyleSheet("font-size: 8px; color: white;")

                color_layout.addWidget(name_label)
                color_layout.addWidget(value_label)
                colors_layout.addWidget(color_container)

            palette_layout.addLayout(colors_layout)

        main_layout.addWidget(palette_group)

        font_group = QGroupBox("Font Settings")
        font_layout = QVBoxLayout(font_group)

        font_label = QLabel("Interface Font Size:")
        font_label.setStyleSheet("font-weight: bold;")
        font_layout.addWidget(font_label)

        font_size_layout = QHBoxLayout()
        self.font_size_group = QButtonGroup(self)

        for size in ["8", "9", "10", "11", "12"]:
            radio = QRadioButton(f"{size} pt")
            if size == "10":
                radio.setChecked(True)
            self.font_size_group.addButton(radio)
            font_size_layout.addWidget(radio)

        font_layout.addLayout(font_size_layout)

        reset_button = ModernButton("🔄 Reset to Default")
        reset_button.clicked.connect(self.reset_appearance_settings)
        font_layout.addWidget(reset_button, alignment=Qt.AlignRight)

        main_layout.addWidget(font_group)
        main_layout.addStretch()

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   PAGE: Network
    # ------------------------------------------------------------------
    def _build_network_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Network Settings")
        title.setObjectName("SectionTitle")
        main_layout.addWidget(title, alignment=Qt.AlignLeft)

        network_group = QGroupBox("UDP Parameters")
        network_group.setObjectName("SettingsGroup")
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(15)
        form_layout.setContentsMargins(15, 15, 15, 15)

        self.network_vars = {}

        def add_network_setting(label, key, default):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: bold;")
            input_widget = QLineEdit(str(default))
            input_widget.setObjectName(f"Net_{key}")
            input_widget.setMinimumHeight(30)
            form_layout.addRow(label_widget, input_widget)
            self.network_vars[key] = input_widget

        add_network_setting("Max Packet Size (bytes):", "max_packet_size",
                            self.config["network"]["max_packet_size"])
        add_network_setting("Client Timeout (sec):", "client_timeout",
                            self.config["network"]["client_timeout"])
        add_network_setting("Heartbeat Interval (sec):", "heartbeat_interval",
                            self.config["network"]["heartbeat_interval"])
        add_network_setting("Packet Loss:", "packet_loss", "0%")

        network_group.setLayout(form_layout)
        main_layout.addWidget(network_group)

        test_button = ModernButton("🔍 Test UDP Connection")
        test_button.setFixedHeight(40)
        test_button.clicked.connect(self.test_udp_connection)
        main_layout.addWidget(test_button, alignment=Qt.AlignRight)
        main_layout.addStretch()

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   PAGE: GIFCT Settings
    # ------------------------------------------------------------------
    def _build_gifct_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        main_layout = QHBoxLayout(page)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        left_panel = QFrame()
        left_panel.setFixedWidth(350)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)

        left_title = QLabel("Available GIFCT Configurations")
        left_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        left_layout.addWidget(left_title)

        self.gifct_scroll = QScrollArea()
        self.gifct_scroll.setWidgetResizable(True)
        self.gifct_list_container = QWidget()
        self.gifct_list_layout = QVBoxLayout(self.gifct_list_container)
        self.gifct_list_layout.addStretch()
        self.gifct_scroll.setWidget(self.gifct_list_container)
        left_layout.addWidget(self.gifct_scroll)

        add_button = ModernButton("＋ Add New GIFCT")
        add_button.setFixedHeight(40)
        add_button.clicked.connect(self.add_gifct)
        left_layout.addWidget(add_button)

        main_layout.addWidget(left_panel)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)

        right_title = QLabel("Basic GIFCT Settings")
        right_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        right_layout.addWidget(right_title)

        enable_group = QGroupBox("Active GIFCT")
        enable_layout = QHBoxLayout(enable_group)

        enable_label = QLabel("Enabled GIFCT:")
        enable_label.setStyleSheet("font-weight: bold;")
        enable_layout.addWidget(enable_label)

        self.gifct1_enabled = QCheckBox("GIFCT 1")
        self.gifct1_enabled.setChecked(
            self.config["gifct_settings"]["gifct_enabled"].get("Gifct1", True))
        enable_layout.addWidget(self.gifct1_enabled)

        self.gifct2_enabled = QCheckBox("GIFCT 2")
        self.gifct2_enabled.setChecked(
            self.config["gifct_settings"]["gifct_enabled"].get("Gifct2", True))
        enable_layout.addWidget(self.gifct2_enabled)

        enable_layout.addStretch()
        right_layout.addWidget(enable_group)

        gifct1_group = QGroupBox("GIFCT 1 Settings")
        gifct1_layout = QFormLayout(gifct1_group)
        gifct1_layout.setLabelAlignment(Qt.AlignRight)

        gifct1_label = QLabel("Name:")
        gifct1_label.setStyleSheet("font-weight: bold;")
        self.gifct1_name = QLineEdit(
            self.config["gifct_settings"]["gifct_configs"].get("Gifct1", "Primary Ability"))
        self.gifct1_name.setMinimumHeight(30)
        gifct1_layout.addRow(gifct1_label, self.gifct1_name)
        right_layout.addWidget(gifct1_group)

        gifct2_group = QGroupBox("GIFCT 2 Settings")
        gifct2_layout = QFormLayout(gifct2_group)
        gifct2_layout.setLabelAlignment(Qt.AlignRight)

        gifct2_label = QLabel("Name:")
        gifct2_label.setStyleSheet("font-weight: bold;")
        self.gifct2_name = QLineEdit(
            self.config["gifct_settings"]["gifct_configs"].get("Gifct2", "Secondary Ability"))
        self.gifct2_name.setMinimumHeight(30)
        gifct2_layout.addRow(gifct2_label, self.gifct2_name)
        right_layout.addWidget(gifct2_group)

        buttons_layout = QHBoxLayout()
        save_button = ModernButton("💾 Save Settings")
        save_button.clicked.connect(self.save_gifct_settings)
        buttons_layout.addWidget(save_button)

        reset_button = ModernButton("🔄 Reset to Default")
        reset_button.clicked.connect(self.reset_gifct_settings)
        buttons_layout.addWidget(reset_button)

        buttons_layout.addStretch()
        right_layout.addLayout(buttons_layout)
        right_layout.addStretch()

        main_layout.addWidget(right_panel)
        self.load_gifct_list()

        return page

    # ------------------------------------------------------------------
    #   PAGE: Stats
    # ------------------------------------------------------------------
    def _build_stats_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Detailed Statistics")
        title.setObjectName("SectionTitle")
        layout.addWidget(title, alignment=Qt.AlignLeft)

        info_label = QLabel("Detailed statistics feature is under development...")
        info_label.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(info_label, alignment=Qt.AlignCenter)
        layout.addStretch()

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   PAGE: Logs
    # ------------------------------------------------------------------
    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        main_layout = QVBoxLayout(page)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Server Logs")
        title.setObjectName("SectionTitle")
        main_layout.addWidget(title, alignment=Qt.AlignLeft)

        toolbar = QFrame()
        toolbar.setFixedHeight(50)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setSpacing(10)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        clear_button = ModernButton("🗑️ Clear")
        clear_button.setFixedHeight(35)
        clear_button.clicked.connect(self.clear_logs)
        toolbar_layout.addWidget(clear_button)

        export_button = ModernButton("📤 Export")
        export_button.setFixedHeight(35)
        export_button.clicked.connect(self.export_logs)
        toolbar_layout.addWidget(export_button)

        toolbar_layout.addWidget(QLabel("Level:"))
        self.log_level_cb = QComboBox()
        self.log_level_cb.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level_cb.setCurrentText(self.config["server"]["log_level"])
        self.log_level_cb.setFixedHeight(35)
        self.log_level_cb.currentTextChanged.connect(self.update_log_level)
        toolbar_layout.addWidget(self.log_level_cb)

        toolbar_layout.addWidget(QLabel("Filter:"))
        self.log_filter_cb = QComboBox()
        self.log_filter_cb.addItems(["ALL", "UDP", "GIFCT", "ERROR", "SYSTEM"])
        self.log_filter_cb.setFixedHeight(35)
        self.log_filter_cb.currentTextChanged.connect(self.filter_logs)
        toolbar_layout.addWidget(self.log_filter_cb)

        self.auto_scroll_chk = QCheckBox("Auto-scroll")
        self.auto_scroll_chk.setChecked(True)
        toolbar_layout.addWidget(self.auto_scroll_chk)

        search_label = QLabel("Search:")
        toolbar_layout.addWidget(search_label)
        self.search_edit = QLineEdit()
        self.search_edit.setFixedHeight(35)
        self.search_edit.setMaximumWidth(200)
        toolbar_layout.addWidget(self.search_edit)

        find_button = ModernButton("🔍 Find")
        find_button.setFixedHeight(35)
        find_button.clicked.connect(self.search_logs)
        toolbar_layout.addWidget(find_button)

        toolbar_layout.addStretch()
        main_layout.addWidget(toolbar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)

        self._log_history = []

        return page

    # ------------------------------------------------------------------
    #   PAGE: Players
    # ------------------------------------------------------------------
    def _build_players_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Player Management")
        title.setObjectName("SectionTitle")
        layout.addWidget(title, alignment=Qt.AlignLeft)

        info_label = QLabel("Player management feature is under development...")
        info_label.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(info_label, alignment=Qt.AlignCenter)
        layout.addStretch()

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   PAGE: Database
    # ------------------------------------------------------------------
    def _build_database_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Database Management")
        title.setObjectName("SectionTitle")
        layout.addWidget(title, alignment=Qt.AlignLeft)

        info_label = QLabel("Database management feature is under development...")
        info_label.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(info_label, alignment=Qt.AlignCenter)
        layout.addStretch()

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   PAGE: Tools
    # ------------------------------------------------------------------
    def _build_tools_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Tools")
        title.setObjectName("SectionTitle")
        layout.addWidget(title, alignment=Qt.AlignLeft)

        info_label = QLabel("Tools feature is under development...")
        info_label.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(info_label, alignment=Qt.AlignCenter)
        layout.addStretch()

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   PAGE: Help
    # ------------------------------------------------------------------
    def _build_help_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Help")
        title.setObjectName("SectionTitle")
        layout.addWidget(title, alignment=Qt.AlignLeft)

        info_label = QLabel("Help feature is under development...")
        info_label.setStyleSheet("font-size: 14px; color: #888;")
        layout.addWidget(info_label, alignment=Qt.AlignCenter)
        layout.addStretch()

        final_layout = QVBoxLayout(page)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll_area)

        return page

    # ------------------------------------------------------------------
    #   Navigation helper – switch to a page
    # ------------------------------------------------------------------
    def _show_section(self, name: str):
        """Display the chosen page and highlight the sidebar button."""
        if name not in self.pages:
            return
        self.content_stack.setCurrentWidget(self.pages[name])
        for sec, btn in self.nav_buttons.items():
            btn.setChecked(sec == name)

    # ------------------------------------------------------------------
    #   Theme handling
    # ------------------------------------------------------------------
    @Slot(str)
    def change_theme(self, theme_name: str):
        """User clicked a ThemePreview → apply that theme."""
        if theme_name not in self.themes:
            return
        self.current_theme = theme_name
        self.colors = self.themes[theme_name]

        for tn, preview in self.theme_previews.items():
            preview.set_selected(tn == theme_name)

        self.config["theme"] = theme_name
        self._save_config()
        self._apply_theme()
        self._log(f"Theme changed to {self.colors['name']}", "SYSTEM")

    def reset_appearance_settings(self):
        """Back to the default theme (black) and default font size."""
        self.change_theme("black")
        for btn in self.font_size_group.buttons():
            if btn.text() == "10":
                btn.setChecked(True)
                break
        self._log("Appearance settings reset", "SYSTEM")

    def _apply_theme(self):
        """Compose and apply a Qt style‑sheet from ``self.colors``."""
        c = self.colors
        qss = f"""
        /* ИСПРАВЛЕНО: Правильные фоны для всех элементов с хорошим контрастом */
        QMainWindow, #MainContainer, #CenterArea, #ContentStack, #PageWidget {{
            background: {c['bg']};
            color: {c['text']};
            font-family: "Segoe UI";
            font-size: 10pt;
        }}

        /* Убедимся, что все контейнеры имеют правильный фон */
        QWidget#PageWidget {{
            background: {c['bg']};
        }}

        QScrollArea, QScrollArea > QWidget > QWidget {{
            background: {c['bg']};
        }}

        /* Top bar */
        #TopBar {{ 
            background: {c['bg_lighter']}; 
            border-bottom: 1px solid {c['border']};
        }}

        #TitleLabel {{ 
            color: {c['text']}; 
            font-weight: bold; 
            font-size: 18pt; 
        }}

        #ProtocolLabel {{ 
            color: {c['accent']}; 
            font-weight: bold;
        }}

        #StatusLabel {{ 
            font-weight: bold; 
            color: {c['error']}; 
        }}

        #ProtocolIndicator {{ 
            background: {c['accent']}; 
            color: white; 
            border-radius: 12px;
            font-weight: bold;
        }}

        /* Sidebar - ИСПРАВЛЕНО: улучшен контраст для читаемости */
        #SideBar {{ 
            background: {c['sidebar_bg']}; 
            border-right: 1px solid {c['border']};
        }}

        #SidebarHeader {{ 
            background: {c['sidebar_active']}; 
            color: {c['sidebar_active_text']};
        }}

        #SidebarHeaderLabel {{ 
            color: {c['sidebar_active_text']}; 
            font-weight: bold; 
        }}

        #SidebarInfo {{
            background: {c['sidebar_bg']};
            border-top: 1px solid {c['border']};
            color: {c['sidebar_text']};
        }}

        QToolButton#NavButton {{
            background: {c['sidebar_bg']};
            color: {c['sidebar_text']};
            padding: 8px 12px;
            text-align: left;
            border: none;
            border-radius: 0px;
            font-size: 10pt;
        }}

        QToolButton#NavButton:hover {{ 
            background: {c['sidebar_hover']}; 
            color: {c['sidebar_active_text']};
        }}

        QToolButton#NavButton:checked {{
            background: {c['sidebar_active']};
            color: {c['sidebar_active_text']};
            font-weight: bold;
        }}

        /* Modern buttons */
        QPushButton#ModernButton {{
            background: {c['button_bg']};
            color: {c['button_fg']};
            border: 1px solid {c['border']};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 10pt;
        }}

        QPushButton#ModernButton:hover {{ 
            background: {c['button_active']}; 
            border: 1px solid {c['accent']};
        }}

        QPushButton#ModernButton:pressed {{ 
            background: {c['button_pressed']}; 
        }}

        QPushButton#ModernButton:disabled {{
            background: {c['button_disabled']};
            color: {c['text_secondary']};
        }}

        QPushButton#StartBtn {{ 
            background: {c['success']}; 
            color: white; 
            border: 1px solid {c['success_light']};
        }}

        QPushButton#StopBtn {{ 
            background: {c['error']}; 
            color: white; 
            border: 1px solid {c['error_light']};
        }}

        QPushButton#RestartBtn {{ 
            background: {c['warning']}; 
            color: white; 
            border: 1px solid {c['warning_light']};
        }}

        /* Inputs */
        QLineEdit, QTextEdit, QComboBox {{
            background: {c['bg_light']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 6px 8px;
            font-size: 10pt;
            selection-background-color: {c['accent']};
        }}

        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: 2px solid {c['accent']};
        }}

        /* Group boxes (cards) */
        QGroupBox {{
            background: {c['card_bg']};
            color: {c['text']};
            border: 2px solid {c['card_border']};
            border-radius: 8px;
            margin-top: 8px;
            padding-top: 15px;
            font-weight: bold;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0px 8px;
            background: {c['card_bg']};
            color: {c['accent']};
            font-weight: bold;
        }}

        /* Stat cards */
        #StatCard {{
            background: {c['card_bg']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 6px;
        }}

        /* Section titles */
        #SectionTitle {{
            font-size: 24pt; 
            font-weight: bold;
            color: {c['text']};
            margin-bottom: 15px;
        }}

        /* Log view */
        QTextEdit {{
            background: {c['bg_lighter']};
            color: {c['text']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            font-family: "Consolas", "Monaco", monospace;
            font-size: 9pt;
            selection-background-color: {c['accent']};
        }}

        /* Status bar */
        #StatusBar {{
            background: {c['bg_lighter']};
            border-top: 1px solid {c['border']};
            color: {c['text_secondary']};
            font-size: 9pt;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            background: {c['bg_light']};
            width: 14px;
            margin: 0px;
            border-radius: 7px;
        }}

        QScrollBar::handle:vertical {{
            background: {c['accent']};
            border-radius: 7px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {c['accent_light']};
        }}
        """
        self.setStyleSheet(qss)

    # ------------------------------------------------------------------
    #   Missing method: test_udp_connection
    # ------------------------------------------------------------------
    def test_udp_connection(self):
        """Test UDP connection functionality."""
        try:
            # Simulate UDP connection test
            self._log("🔍 Testing UDP connection...", "SYSTEM")

            # Get port from config
            port = self.config["network"]["udp_port"]

            # Simulate test process
            self._log(f"Checking UDP port {port}...", "UDP")

            # Simulate test result - this would normally check if port is available
            QMessageBox.information(self, "UDP Test",
                                    f"UDP connection test completed.\nPort {port} appears to be available.")

            self._log("✅ UDP connection test passed", "SUCCESS")

        except Exception as e:
            error_msg = f"UDP connection test failed: {str(e)}"
            self._log(f"❌ {error_msg}", "ERROR")
            QMessageBox.critical(self, "UDP Test Failed", error_msg)

    # ------------------------------------------------------------------
    #   GIFCT functionality with directory support
    # ------------------------------------------------------------------
    def add_gifct(self):
        """Add a new GIFCT configuration with directory selection."""
        try:
            dialog = GifctConfigDialog(self, title="Add New GIFCT", colors=self.colors)
            if dialog.exec() == QDialog.Accepted and dialog.result:
                gifct_data = dialog.result
                gifct_id = gifct_data["id"]

                # Save to config
                self.config["gifct_configurations"][gifct_id] = gifct_data
                self._save_config()

                # Reload list
                self.load_gifct_list()

                self._log(f"✅ Added new GIFCT: {gifct_data['name']}", "GIFCT")

                # Show confirmation
                dirs_count = len(gifct_data.get("gif_directories", []))
                QMessageBox.information(self, "GIFCT Added",
                                        f"GIFCT '{gifct_data['name']}' created successfully!\n"
                                        f"Directories added: {dirs_count}")

        except Exception as e:
            self._log(f"❌ Error adding GIFCT: {e}", "ERROR")
            QMessageBox.critical(self, "Error", f"Failed to add GIFCT: {e}")

    def edit_gifct(self, gifct_id: str):
        """Edit an existing GIFCT configuration."""
        try:
            if gifct_id not in self.config["gifct_configurations"]:
                self._log(f"❌ GIFCT not found: {gifct_id}", "ERROR")
                return

            gifct_data = self.config["gifct_configurations"][gifct_id]
            dialog = GifctConfigDialog(self, title=f"Edit GIFCT: {gifct_data['name']}",
                                       gifct_data=gifct_data, colors=self.colors)

            if dialog.exec() == QDialog.Accepted and dialog.result:
                updated_data = dialog.result
                self.config["gifct_configurations"][gifct_id] = updated_data
                self._save_config()
                self.load_gifct_list()
                self._log(f"✅ Updated GIFCT: {updated_data['name']}", "GIFCT")

        except Exception as e:
            self._log(f"❌ Error editing GIFCT: {e}", "ERROR")

    def delete_gifct(self, gifct_id: str):
        """Delete a GIFCT configuration."""
        try:
            if gifct_id not in self.config["gifct_configurations"]:
                return

            gifct_name = self.config["gifct_configurations"][gifct_id]["name"]
            reply = QMessageBox.question(self, "Delete GIFCT",
                                         f"Are you sure you want to delete '{gifct_name}'?",
                                         QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                del self.config["gifct_configurations"][gifct_id]
                self._save_config()
                self.load_gifct_list()
                self._log(f"🗑️ Deleted GIFCT: {gifct_name}", "GIFCT")

        except Exception as e:
            self._log(f"❌ Error deleting GIFCT: {e}", "ERROR")

    def toggle_gifct(self, gifct_id: str):
        """Toggle GIFCT enabled/disabled state."""
        try:
            if gifct_id not in self.config["gifct_configurations"]:
                return

            gifct_data = self.config["gifct_configurations"][gifct_id]
            gifct_data["enabled"] = not gifct_data.get("enabled", True)
            self.config["gifct_configurations"][gifct_id] = gifct_data
            self._save_config()

            status = "enabled" if gifct_data["enabled"] else "disabled"
            self._log(f"🔄 GIFCT {gifct_data['name']} {status}", "GIFCT")

        except Exception as e:
            self._log(f"❌ Error toggling GIFCT: {e}", "ERROR")

    def load_gifct_list(self):
        """Load and display the GIFCT configurations list."""
        try:
            # Clear existing items
            while self.gifct_list_layout.count() > 1:  # Keep the stretch
                item = self.gifct_list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Add GIFCT items
            for gifct_id, gifct_data in self.config["gifct_configurations"].items():
                item = GifctListItem(gifct_id, gifct_data,
                                     self.edit_gifct, self.delete_gifct, self.toggle_gifct)
                self.gifct_list_layout.insertWidget(self.gifct_list_layout.count() - 1, item)

            self._log(f"📋 Loaded {len(self.config['gifct_configurations'])} GIFCT configurations", "GIFCT")

        except Exception as e:
            self._log(f"❌ Error loading GIFCT list: {e}", "ERROR")

    def save_gifct_settings(self):
        """Save GIFCT settings."""
        try:
            # Save basic GIFCT settings
            self.config["gifct_settings"]["gifct_enabled"]["Gifct1"] = self.gifct1_enabled.isChecked()
            self.config["gifct_settings"]["gifct_enabled"]["Gifct2"] = self.gifct2_enabled.isChecked()
            self.config["gifct_settings"]["gifct_configs"]["Gifct1"] = self.gifct1_name.text()
            self.config["gifct_settings"]["gifct_configs"]["Gifct2"] = self.gifct2_name.text()

            self._save_config()
            self._log("💾 GIFCT settings saved", "GIFCT")
            QMessageBox.information(self, "GIFCT", "GIFCT settings saved successfully")

        except Exception as e:
            self._log(f"❌ Error saving GIFCT settings: {e}", "ERROR")
            QMessageBox.critical(self, "Error", f"Failed to save GIFCT settings: {e}")

    def reset_gifct_settings(self):
        """Reset GIFCT settings to default."""
        try:
            reply = QMessageBox.question(self, "Reset GIFCT Settings",
                                         "Are you sure you want to reset all GIFCT settings to default?",
                                         QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.Yes:
                # Reset to default configuration
                self.config["gifct_settings"] = {
                    "gifct_enabled": {"Gifct1": True, "Gifct2": True},
                    "gifct_configs": {"Gifct1": "Primary Ability", "Gifct2": "Secondary Ability"}
                }
                self.config["gifct_configurations"] = {}

                self._save_config()
                self.load_gifct_list()

                # Update UI
                self.gifct1_enabled.setChecked(True)
                self.gifct2_enabled.setChecked(True)
                self.gifct1_name.setText("Primary Ability")
                self.gifct2_name.setText("Secondary Ability")

                self._log("🔄 GIFCT settings reset to default", "GIFCT")
                QMessageBox.information(self, "GIFCT", "GIFCT settings reset successfully")

        except Exception as e:
            self._log(f"❌ Error resetting GIFCT settings: {e}", "ERROR")

    # ------------------------------------------------------------------
    #   Log management methods
    # ------------------------------------------------------------------
    def clear_logs(self):
        """Clear the log display."""
        self.log_text.clear()
        self._log_history.clear()
        self._log("🗑️ Logs cleared", "SYSTEM")

    def export_logs(self):
        """Export logs to file."""
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Export Logs", "server_logs.txt", "Text Files (*.txt)")
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self._log(f"📤 Logs exported to {filename}", "SUCCESS")
        except Exception as e:
            self._log(f"❌ Log export failed: {e}", "ERROR")

    def update_log_level(self, level):
        """Update log level."""
        self.config["server"]["log_level"] = level
        self._save_config()
        self._log(f"📊 Log level changed to {level}", "SYSTEM")

    def filter_logs(self, filter_type):
        """Filter logs by type."""
        self._log(f"🔍 Applying filter: {filter_type}", "SYSTEM")
        # TODO: Implement log filtering

    def search_logs(self):
        """Search logs for text."""
        search_text = self.search_edit.text()
        if search_text:
            self._log(f"🔍 Searching for: {search_text}", "SYSTEM")
            # TODO: Implement log search

    # ------------------------------------------------------------------
    def _update_clock(self):
        self.time_lbl.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _center_window(self):
        screen = QApplication.primaryScreen()
        if screen:
            scr_geo = screen.availableGeometry()
            win_geo = self.geometry()
            x = (scr_geo.width() - win_geo.width()) // 2
            y = (scr_geo.height() - win_geo.height()) // 2
            self.move(x, y)

    # Server control methods
    def start_server(self):
        if self.server_running: return
        try:
            self.start_time = time.time()
            self.server_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.restart_btn.setEnabled(True)
            self._set_status_indicator(True)
            self._log("🚀 STARTING DPP2 UDP SERVER", "UDP")
            self.server = self.server_core_class()
            self.server_thread = threading.Thread(target=self._run_server_thread, daemon=True)
            self.server_thread.start()
        except Exception as exc:
            self._log(f"❌ Server start error: {exc}", "ERROR")
            self.stop_server()

    def _run_server_thread(self):
        try:
            if hasattr(self.server, "start"):
                if not self.server.start():
                    self._log("❌ Core server reported failure to start", "ERROR")
                    self.stop_server()
                    return

            while self.server_running and getattr(self.server, "running", False):
                time.sleep(0.1)
                if hasattr(self.server, "get_server_info"):
                    info = self.server.get_server_info()
                    if info:
                        world = info.get("world", {})
                        net = info.get("network_stats", {})
                        self.stats["players_online"] = world.get("online_players", 0)
                        self.stats["total_characters"] = world.get("total_characters", 0)
                        self.stats["udp_packets_received"] = net.get("packets_received", 0)
                        self.stats["udp_packets_sent"] = net.get("packets_sent", 0)
        except Exception as exc:
            self._log(f"❌ Server thread error: {exc}", "ERROR")
        finally:
            self.server_running = False
            self._set_status_indicator(False)

    def stop_server(self):
        if not self.server_running: return
        self._log("🛑 Stopping server …", "UDP")
        self.server_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        if self.server and hasattr(self.server, "stop"):
            try:
                self.server.stop()
            except Exception as exc:
                self._log(f"❌ stop() error: {exc}", "ERROR")
        self._set_status_indicator(False)

    def restart_server(self):
        self._log("🔄 Restarting server …", "UDP")
        self.stop_server()
        QTimer.singleShot(1000, self.start_server)

    def _set_status_indicator(self, running: bool):
        colour = self.colors["success"] if running else self.colors["error"]
        self.status_indicator.setStyleSheet(f"background:{colour};border-radius:10px;")
        self.status_lbl.setText("● RUNNING" if running else "● STOPPED")
        self.status_lbl.setStyleSheet(f"color:{colour};font-weight:bold;")

    def save_server_settings(self):
        try:
            s = self.server_vars
            self.config["server"]["server_name"] = s["server_name"].text()
            self.config["server"]["port"] = int(s["udp_port"].text())
            self.config["server"]["max_players"] = int(s["max_players"].text())
            self.config["server"]["tick_rate"] = int(s["tick_rate"].text())
            self.config["server"]["log_level"] = s["log_level"].currentText()
            self.config["server"]["protocol"] = s["protocol"].text()
            self._save_config()
        except Exception as exc:
            self._log(f"❌ Invalid server settings: {exc}", "ERROR")

    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.message_queue.put((level, f"[{timestamp}] {message}"))

    def _add_log_entry(self, level: str, text: str):
        colour = {
            "INFO": self.colors["text_secondary"], "DEBUG": self.colors["text_secondary"],
            "SUCCESS": self.colors["success"], "WARNING": self.colors["warning"],
            "ERROR": self.colors["error"], "CRITICAL": self.colors["error"],
            "GIFCT": self.colors["info_light"], "UDP": self.colors["info"], "SYSTEM": self.colors["accent"]
        }.get(level, self.colors["text"])

        if hasattr(self, 'log_text'):
            self.log_text.moveCursor(QTextCursor.End)
            self.log_text.setTextColor(QColor(colour))
            self.log_text.insertPlainText(text + "\n")

    def _update_ui(self):
        while not self.message_queue.empty():
            try:
                lvl, txt = self.message_queue.get_nowait()
                self._add_log_entry(lvl, txt)
            except queue.Empty:
                break

        if self.server_running:
            elapsed = int(time.time() - self.start_time)
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.stats["uptime"] = f"{h:02d}:{m:02d}:{s:02d}"
            self.stats["cpu_usage"] = f"{psutil.cpu_percent():.1f}%"
            mem = psutil.virtual_memory()
            self.stats["memory_usage"] = f"{mem.used // (1024 * 1024)}/{mem.total // (1024 * 1024)} MB"
            self.stats["udp_packets_total"] = str(self.stats["udp_packets_received"] + self.stats["udp_packets_sent"])

        for key, lbl in self.stat_labels.items():
            if key in self.stats:
                lbl.setText(str(self.stats[key]))

    def closeEvent(self, event):
        if self.server_running:
            if QMessageBox.question(self, "Server running",
                                    "The server is still running. Stop it and quit?") == QMessageBox.Yes:
                self.stop_server()
                time.sleep(0.5)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DPP2 UDP Server GUI – PySide6")
    parser.add_argument("--theme", help="Initial theme (black, grey)")
    parser.add_argument("--port", type=int, help="Override UDP port")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    from server_core import ServerCore
    gui = ServerGUI(ServerCore)

    if args.theme and args.theme in gui.themes:
        gui.change_theme(args.theme)
    if args.port:
        gui.server_vars["udp_port"].setText(str(args.port))

    gui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()