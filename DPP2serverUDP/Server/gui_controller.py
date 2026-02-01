#!/usr/bin/env python3
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
        self.setMinimumHeight(36)


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
        p.fillRect(0, 0, w, h, QColor(self.theme_data["bg"]))
        p.fillRect(0, 0, 40, h, QColor(self.theme_data["sidebar_bg"]))
        p.fillRect(50, 10, 30, 10, QColor(self.theme_data["accent"]))
        p.fillRect(50, 30, 50, 10, QColor(self.theme_data["bg_light"]))
        p.fillRect(120, 20, 50, 20, QColor(self.theme_data["button_bg"]))

        pen = p.pen()
        pen.setWidth(2 if self.selected else 1)
        pen.setColor(QColor(self.theme_data["accent"] if self.selected
                            else self.theme_data["border"]))
        p.setPen(pen)
        p.drawRect(0, 0, w - 1, h - 1)

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

    def __init__(self, parent=None, title: str = "GIFCT configuration",
                 gifct_data: dict | None = None, colors: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 600)
        self.colors = colors or {}
        self.result = None
        self._build_ui(gifct_data)

    def _build_ui(self, gifct_data: dict | None):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Gifct Name:"))
        self.name_edit = QLineEdit(gifct_data.get("name", "") if gifct_data else "")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Gifct ID (unique identifier):"))
        self.id_edit = QLineEdit(
            gifct_data.get("id", f"gifct_{int(time.time())}") if gifct_data
            else f"gifct_{int(time.time())}")
        layout.addWidget(self.id_edit)

        layout.addWidget(QLabel("Description:"))
        self.desc_edit = QLineEdit(gifct_data.get("description", "") if gifct_data else "")
        layout.addWidget(self.desc_edit)

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

        layout.addWidget(QLabel("Parameters (JSON format):"))
        self.params_edit = QTextEdit()
        default_params = {
            "cooldown": 10, "duration": 5, "power": 100, "range": 10, "cost": 20
        }
        params = gifct_data.get("parameters", default_params) if gifct_data else default_params
        self.params_edit.setPlainText(json.dumps(params, indent=2))
        layout.addWidget(self.params_edit)

        self.enabled_chk = QCheckBox("Enabled by default")
        self.enabled_chk.setChecked(gifct_data.get("enabled", True) if gifct_data else True)
        layout.addWidget(self.enabled_chk)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        try:
            raw = self.params_edit.toPlainText().strip()
            params = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            QMessageBox.critical(self, "Invalid JSON", f"Parameters must be valid JSON:\n{exc}")
            return

        typ = next((t for t, rb in [(b.text().lower(), b) for b in self.type_group.buttons()]
                    if rb.isChecked()), "ability")

        self.result = {
            "name": self.name_edit.text(), "id": self.id_edit.text(),
            "description": self.desc_edit.text(), "type": typ, "parameters": params,
            "enabled": self.enabled_chk.isChecked(),
            "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()
        }
        self.accept()


class GifctListItem(QWidget):
    """One row of the GIFCT list – shows name, type and action buttons."""

    def __init__(self, gifct_id: str, gifct_data: dict, edit_cb, delete_cb, toggle_cb, parent=None):
        super().__init__(parent)
        self.gifct_id = gifct_id
        self.gifct_data = gifct_data
        self.edit_cb = edit_cb
        self.delete_cb = delete_cb
        self.toggle_cb = toggle_cb
        self.setObjectName("GifctItem")
        self._build_ui()

    def _build_ui(self):
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(12)

        left = QVBoxLayout()
        name_lbl = QLabel(self.gifct_data.get("name", "Unnamed"))
        name_lbl.setStyleSheet("font-weight:bold;")
        left.addWidget(name_lbl)

        typ = self.gifct_data.get("type", "custom").capitalize()
        type_lbl = QLabel(typ)
        type_lbl.setStyleSheet("font-size:8pt; color:#888;")
        left.addWidget(type_lbl)
        h.addLayout(left, stretch=1)

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
    def __init__(self, server_core_class):
        super().__init__()
        self.server_core_class = server_core_class

        self.themes = {
            "black": {
                "name": "Midnight Black", "bg": "#0d1117", "bg_light": "#161b22",
                "bg_lighter": "#21262d", "sidebar_bg": "#010409", "sidebar_active": "#1f6feb",
                "sidebar_hover": "#1f6feb", "sidebar_text": "#8b949e", "sidebar_active_text": "#ffffff",
                "sidebar_icon": "#8b949e", "text": "#f0f6fc", "text_secondary": "#8b949e",
                "accent": "#1f6feb", "accent_light": "#388bfd", "success": "#238636",
                "success_light": "#2ea043", "warning": "#9e6a03", "warning_light": "#d29922",
                "error": "#da3633", "error_light": "#f85149", "info": "#58a6ff", "info_light": "#79c0ff",
                "button_bg": "#21262d", "button_fg": "#c9d1d9", "button_active": "#30363d",
                "button_pressed": "#484f58", "button_disabled": "#6e7681", "border": "#30363d",
                "border_light": "#3c444d", "card_bg": "#161b22", "card_border": "#30363d"
            },
            "grey": {
                "name": "Professional Grey", "bg": "#f8f9fa", "bg_light": "#ffffff",
                "bg_lighter": "#e9ecef", "sidebar_bg": "#2b2d42", "sidebar_active": "#ef233c",
                "sidebar_hover": "#ef233c", "sidebar_text": "#adb5bd", "sidebar_active_text": "#ffffff",
                "sidebar_icon": "#adb5bd", "text": "#212529", "text_secondary": "#6c757d",
                "accent": "#4361ee", "accent_light": "#4895ef", "success": "#4cc9f0",
                "success_light": "#38b000", "warning": "#f8961e", "warning_light": "#f9844a",
                "error": "#f72585", "error_light": "#7209b7", "info": "#4361ee", "info_light": "#3a0ca3",
                "button_bg": "#4361ee", "button_fg": "#ffffff", "button_active": "#3a56d4",
                "button_pressed": "#2f4ab2", "button_disabled": "#6c757d", "border": "#dee2e6",
                "border_light": "#ced4da", "card_bg": "#ffffff", "card_border": "#dee2e6"
            }
        }

        self.current_theme = "black"
        self.colors = self.themes[self.current_theme]

        self.setWindowTitle("🎮 DPP2 UDP Server Controller")
        self.resize(1600, 900)
        if os.path.exists("icon.ico"):
            self.setWindowIcon(QIcon("icon.ico"))

        self.config = self._load_config()
        if "theme" in self.config:
            self.current_theme = self.config["theme"]
            if self.current_theme in self.themes:
                self.colors = self.themes[self.current_theme]

        self.message_queue = queue.Queue()
        self.server = None
        self.server_running = False
        self.server_thread = None
        self.start_time = None

        self.stats = {
            "players_online": 0, "characters_online": 0, "total_characters": 0,
            "cpu_usage": 0, "memory_usage": 0, "uptime": "00:00:00", "connections": 0,
            "active_gifct": "Gifct1, Gifct2", "udp_packets_received": 0, "udp_packets_sent": 0,
            "packet_loss": "0%", "protocol": "UDP", "udp_port": 5555
        }

        self._create_main_structure()
        self._apply_theme()
        self._center_window()

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(1000)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

        self._show_section("dashboard")

    def _load_config(self) -> dict:
        default = {
            "server": {
                "host": "0.0.0.0", "port": 80, "max_players": 100, "tick_rate": 60,
                "log_level": "INFO", "server_name": "DPP2 UDP Character Server", "protocol": "udp"
            },
            "game": {
                "max_characters_per_player": 5, "starting_zone": "start_city", "auto_save_interval": 300
            },
            "database": {"path": "game_server_db.json"},
            "network": {
                "udp_port": 80, "max_packet_size": 1400, "client_timeout": 30, "heartbeat_interval": 1.0
            },
            "gifct_settings": {
                "gifct_enabled": {"Gifct1": True, "Gifct2": True},
                "gifct_configs": {"Gifct1": "Primary Ability", "Gifct2": "Secondary Ability"}
            },
            "gifct_configurations": {}, "theme": "black"
        }

        cfg_path = "config.json"
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
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
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self._log("✅ Configuration saved", "SUCCESS")
            return True
        except Exception as e:
            self._log(f"❌ Config save error: {e}", "ERROR")
            return False

    def _create_main_structure(self):
        main_container = QWidget()
        main_container.setObjectName("MainContainer")
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._create_top_bar()
        main_layout.addWidget(self.top_bar)

        center_widget = QWidget()
        center_widget.setObjectName("CenterArea")
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._create_sidebar()
        self._create_content_area()

        center_layout.addWidget(self.sidebar)
        center_layout.addWidget(self.content_stack)

        main_layout.addWidget(center_widget)

        self._create_bottom_bar()
        main_layout.addWidget(self.status_bar_widget)

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
        tb_layout.addWidget(self.title_lbl)

        self.protocol_indicator = QLabel("U")
        self.protocol_indicator.setFixedSize(24, 24)
        self.protocol_indicator.setObjectName("ProtocolIndicator")
        tb_layout.addWidget(self.protocol_indicator)

        self.protocol_lbl = QLabel("UDP PROTOCOL")
        self.protocol_lbl.setObjectName("ProtocolLabel")
        tb_layout.addWidget(self.protocol_lbl)

        tb_layout.addStretch()

        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(20, 20)
        self.status_indicator.setObjectName("StatusIndicator")
        self.status_lbl = QLabel("● STOPPED")
        self.status_lbl.setObjectName("StatusLabel")
        tb_layout.addWidget(self.status_lbl)
        tb_layout.addWidget(self.status_indicator)

    def _create_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SideBar")
        self.sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        nav_hdr = QFrame()
        nav_hdr.setObjectName("SidebarHeader")
        nav_hdr.setFixedHeight(50)
        nav_hdr_h = QHBoxLayout(nav_hdr)
        nav_lbl = QLabel("NAVIGATION")
        nav_lbl.setObjectName("SidebarHeaderLabel")
        nav_hdr_h.addWidget(nav_lbl, alignment=Qt.AlignCenter)
        side_layout.addWidget(nav_hdr)

        self.nav_buttons = {}
        nav_items = [
            ("🏠", "Dashboard", "dashboard"), ("⚙️", "Server Settings", "server_settings"),
            ("🎨", "Appearance", "appearance"), ("🌐", "Network", "network"),
            ("🎮", "Gifct Settings", "gifct"), ("📊", "Statistics", "stats"),
            ("📋", "Logs", "logs"), ("👥", "Players", "players"),
            ("🗃️", "Database", "database"), ("🛠️", "Tools", "tools"), ("❓", "Help", "help")
        ]

        for icon, txt, sec in nav_items:
            btn = NavigationButton(icon, txt)
            btn.clicked.connect(lambda _, s=sec: self._show_section(s))
            side_layout.addWidget(btn)
            self.nav_buttons[sec] = btn

        side_layout.addStretch()

        info = QFrame()
        info.setObjectName("SidebarInfo")
        info_v = QVBoxLayout(info)
        info_v.addWidget(QLabel("Version: 2.1"))
        info_v.addWidget(QLabel("Protocol: UDP"))
        side_layout.addWidget(info)

    def _create_content_area(self):
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("ContentStack")
        self._build_pages()
        for widget in self.pages.values():
            self.content_stack.addWidget(widget)

    def _create_bottom_bar(self):
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

        # Карточка управления сервером - растягивается по ширине
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

        # Кнопки занимают всю ширину равномерно
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        ctrl_layout.addWidget(self.restart_btn)

        main_layout.addWidget(ctrl_card)

        # Контейнер для статистики с адаптивной сеткой
        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(15)

        stats_title = QLabel("Server Statistics")
        stats_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        stats_layout.addWidget(stats_title)

        # АДАПТИВНАЯ СЕТКА - ключевое изменение
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
            row = i // 4  # 4 колонки в ряду
            col = i % 4

            # Карточка с правильной политикой размеров
            card = QFrame()
            card.setObjectName("StatCard")
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            card.setMinimumHeight(100)
            card.setMinimumWidth(200)

            card_layout = QVBoxLayout(card)
            card_layout.setAlignment(Qt.AlignCenter)
            card_layout.setSpacing(8)
            card_layout.setContentsMargins(15, 15, 15, 15)

            # Верхняя часть
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

            # Значение
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

        # Добавляем статистику с растяжением
        main_layout.addWidget(stats_container, 1)  # stretch=1 для заполнения пространства

        return page

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
        main_layout.addWidget(title)

        settings_group = QGroupBox("Main Settings")
        settings_group.setObjectName("SettingsGroup")
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(15)

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
        main_layout.addWidget(title)

        theme_group = QGroupBox("Theme Selection")
        theme_layout = QVBoxLayout(theme_group)

        theme_label = QLabel("Select interface theme:")
        theme_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        theme_layout.addWidget(theme_label)

        previews_layout = QHBoxLayout()
        previews_layout.setAlignment(Qt.AlignCenter)
        self.theme_previews = {}

        for theme_name in ["black", "grey"]:
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
            ("Accent Colors", ["accent", "accent_light", "success", "warning", "error", "info"])
        ]

        for group_name, color_keys in color_groups:
            group_label = QLabel(f"<b>{group_name}:</b>")
            group_label.setStyleSheet("margin-top: 10px;")
            palette_layout.addWidget(group_label)

            colors_layout = QHBoxLayout()
            colors_layout.setSpacing(10)

            for key in color_keys:
                if key not in self.colors: continue

                color_container = QFrame()
                color_container.setFixedSize(80, 80)
                color_container.setStyleSheet(
                    f"background: {self.colors[key]}; border: 2px solid {self.colors['border']}; border-radius: 5px;")

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
            if size == "10": radio.setChecked(True)
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

    # Остальные методы страниц остаются аналогичными, но укорочены для brevity
    def _build_network_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Network Settings - Under Development"))
        return page

    def _build_gifct_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("GIFCT Settings - Under Development"))
        return page

    def _build_stats_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Statistics - Under Development"))
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PageWidget")
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Logs - Under Development"))
        return page

    def _build_players_page(self) -> QWidget:
        return self._build_placeholder_page("Player Management")

    def _build_database_page(self) -> QWidget:
        return self._build_placeholder_page("Database Management")

    def _build_tools_page(self) -> QWidget:
        return self._build_placeholder_page("Tools")

    def _build_help_page(self) -> QWidget:
        return self._build_placeholder_page("Help")

    def _build_placeholder_page(self, title_text):
        page = QWidget()
        page.setObjectName("PageWidget")
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(f"{title_text} - Under Development"))
        return page

    def _show_section(self, name: str):
        if name not in self.pages: return
        self.content_stack.setCurrentWidget(self.pages[name])
        for sec, btn in self.nav_buttons.items():
            btn.setChecked(sec == name)

    @Slot(str)
    def change_theme(self, theme_name: str):
        if theme_name not in self.themes: return
        self.current_theme = theme_name
        self.colors = self.themes[theme_name]

        for tn, preview in self.theme_previews.items():
            preview.set_selected(tn == theme_name)

        self.config["theme"] = theme_name
        self._save_config()
        self._apply_theme()
        self._log(f"Theme changed to {self.colors['name']}", "SYSTEM")

    def reset_appearance_settings(self):
        self.change_theme("black")
        for btn in self.font_size_group.buttons():
            if btn.text() == "10": btn.setChecked(True); break
        self._log("Appearance settings reset", "SYSTEM")

    def _apply_theme(self):
        c = self.colors
        qss = f"""
        QMainWindow, #MainContainer, #CenterArea, #ContentStack, #PageWidget {{
            background: {c['bg']}; color: {c['text']}; font-family: "Segoe UI"; font-size: 10pt;
        }}

        #TopBar {{ background: {c['bg_lighter']}; border-bottom: 1px solid {c['border']}; }}
        #TitleLabel {{ color: {c['text']}; font-weight: bold; font-size: 18pt; }}
        #ProtocolLabel {{ color: {c['accent']}; font-weight: bold; }}
        #StatusLabel {{ font-weight: bold; color: {c['error']}; }}
        #ProtocolIndicator {{ background: {c['accent']}; color: white; border-radius: 12px; font-weight: bold; }}

        #SideBar {{ background: {c['sidebar_bg']}; border-right: 1px solid {c['border']}; }}
        #SidebarHeader {{ background: {c['sidebar_active']}; color: {c['sidebar_active_text']}; }}
        #SidebarHeaderLabel {{ color: {c['sidebar_active_text']}; font-weight: bold; }}
        #SidebarInfo {{ background: {c['sidebar_bg']}; border-top: 1px solid {c['border']}; color: {c['sidebar_text']}; }}

        QToolButton#NavButton {{
            background: {c['sidebar_bg']}; color: {c['sidebar_text']}; padding: 8px 12px;
            text-align: left; border: none; border-radius: 0px; font-size: 10pt;
        }}
        QToolButton#NavButton:hover {{ background: {c['sidebar_hover']}; color: {c['sidebar_active_text']}; }}
        QToolButton#NavButton:checked {{ background: {c['sidebar_active']}; color: {c['sidebar_active_text']}; font-weight: bold; }}

        QPushButton#ModernButton {{
            background: {c['button_bg']}; color: {c['button_fg']}; border: 1px solid {c['border']};
            border-radius: 6px; padding: 8px 16px; font-weight: bold; font-size: 10pt;
        }}
        QPushButton#ModernButton:hover {{ background: {c['button_active']}; border: 1px solid {c['accent']}; }}
        QPushButton#ModernButton:pressed {{ background: {c['button_pressed']}; }}

        QPushButton#StartBtn {{ background: {c['success']}; color: white; border: 1px solid {c['success_light']}; }}
        QPushButton#StopBtn {{ background: {c['error']}; color: white; border: 1px solid {c['error_light']}; }}
        QPushButton#RestartBtn {{ background: {c['warning']}; color: white; border: 1px solid {c['warning_light']}; }}

        QLineEdit, QTextEdit, QComboBox {{
            background: {c['bg_light']}; color: {c['text']}; border: 1px solid {c['border']};
            border-radius: 4px; padding: 6px 8px; font-size: 10pt;
        }}

        QGroupBox {{
            background: {c['card_bg']}; color: {c['text']}; border: 2px solid {c['card_border']};
            border-radius: 8px; margin-top: 8px; padding-top: 15px; font-weight: bold;
        }}
        QGroupBox::title {{ background: {c['card_bg']}; color: {c['accent']}; font-weight: bold; }}

        #StatCard {{
            background: {c['card_bg']}; color: {c['text']}; border: 1px solid {c['border']};
            border-radius: 6px;
        }}

        #SectionTitle {{ font-size: 24pt; font-weight: bold; color: {c['text']}; }}

        #StatusBar {{ background: {c['bg_lighter']}; border-top: 1px solid {c['border']}; color: {c['text_secondary']}; }}
        """
        self.setStyleSheet(qss)

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