#!/usr/bin/env python3
"""
DPP2 UDP Server GUI - Графический контроллер UDP сервера с выбором Gifct
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import queue
import json
import time
import sys
import os
from datetime import datetime
import psutil
import platform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class ServerGUI:
    def __init__(self, root, server_core_class):
        self.root = root
        self.server_core_class = server_core_class
        self.root.title("DPP2 UDP Character Server Controller")
        self.root.geometry("1300x850")  # Немного увеличил размер для новых строк

        self.message_queue = queue.Queue()
        self.server = None
        self.server_running = False
        self.server_thread = None
        self.start_time = None

        self.stats = {
            'players_online': 0,
            'characters_online': 0,
            'total_characters': 0,
            'cpu_usage': 0,
            'memory_usage': 0,
            'uptime': '00:00:00',
            'connections': 0,
            'active_gifct': 'Gifct1, Gifct2',
            'udp_packets_received': 0,
            'udp_packets_sent': 0,
            'packet_loss': '0%',
            'protocol': 'UDP',
            'udp_port': 5555
        }

        self.config = self.load_config()
        self.connected_clients = []

        self.setup_ui()
        self.start_update_loop()

    def load_config(self):
        """Загрузка конфигурации"""
        config_path = "config.json"
        default_config = {
            "server": {
                "host": "0.0.0.0",
                "port": 80,
                "max_players": 100,
                "tick_rate": 60,
                "log_level": "INFO",
                "server_name": "DPP2 UDP Character Server",
                "protocol": "udp"  # Добавлен протокол
            },
            "game": {
                "max_characters_per_player": 5,
                "starting_zone": "start_city",
                "auto_save_interval": 300
            },
            "database": {
                "path": "game_server_db.json"
            },
            "network": {
                "udp_port": 80,
                "max_packet_size": 1400,
                "client_timeout": 30,
                "heartbeat_interval": 1.0
            },
            "gifct_settings": {
                "gifct_enabled": {
                    "Gifct1": True,
                    "Gifct2": True
                },
                "gifct_configs": {
                    "Gifct1": "Основная способность",
                    "Gifct2": "Вторичная способность"
                }
            }
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)

                # Проверяем и добавляем отсутствующие ключи
                for key in default_config:
                    if key not in loaded_config:
                        loaded_config[key] = default_config[key]
                    elif isinstance(default_config[key], dict):
                        for subkey in default_config[key]:
                            if subkey not in loaded_config[key]:
                                loaded_config[key][subkey] = default_config[key][subkey]

                # Убедимся что protocol указан
                if 'protocol' not in loaded_config['server']:
                    loaded_config['server']['protocol'] = 'udp'

                return loaded_config
            else:
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
                return default_config

        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
            return default_config

    def setup_ui(self):
        """Настройка интерфейса"""
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass

        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Status.TLabel', font=('Arial', 11, 'bold'))
        style.configure('UDP.TLabel', font=('Arial', 10, 'bold'), foreground='#00a8ff')

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # ========== ЗАГОЛОВОК ==========
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(title_frame,
                  text="🎮 DPP2 UDP Character Server Controller",
                  style='Title.TLabel').pack(side=tk.LEFT)

        # Индикатор протокола UDP
        protocol_label = ttk.Label(title_frame,
                                   text="🌐 UDP",
                                   style='UDP.TLabel',
                                   background='#1a1a2e',
                                   padding=(10, 2))
        protocol_label.pack(side=tk.RIGHT, padx=5)

        ttk.Label(title_frame,
                  text="v2.0 UDP",
                  font=('Arial', 9)).pack(side=tk.RIGHT, padx=10)

        # ========== ПАНЕЛЬ УПРАВЛЕНИЯ ==========
        control_frame = ttk.LabelFrame(main_frame, text="Управление UDP сервером", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=(0, 10))

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_btn = ttk.Button(btn_frame, text="▶ Запустить UDP сервер",
                                    command=self.start_server, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(btn_frame, text="■ Остановить UDP",
                                   command=self.stop_server, width=20, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.restart_btn = ttk.Button(btn_frame, text="↻ Перезапустить UDP",
                                      command=self.restart_server, width=20, state=tk.DISABLED)
        self.restart_btn.pack(side=tk.LEFT, padx=(5, 0))

        # UDP тест кнопка
        self.test_btn = ttk.Button(btn_frame, text="🔍 Тест UDP",
                                   command=self.test_udp_connection, width=15)
        self.test_btn.pack(side=tk.LEFT, padx=(10, 0))

        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(status_frame, text="Состояние: Остановлен (UDP)", style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)

        self.status_indicator = tk.Canvas(status_frame, width=20, height=20, bg='gray', highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(10, 0))

        # Индикатор UDP соединения
        self.udp_indicator = tk.Canvas(status_frame, width=20, height=20, bg='gray', highlightthickness=1,
                                       highlightbackground='#00a8ff')
        self.udp_indicator.pack(side=tk.LEFT, padx=(20, 5))
        ttk.Label(status_frame, text="UDP", font=('Arial', 9, 'bold'), foreground='#00a8ff').pack(side=tk.LEFT)

        # ========== UDP НАСТРОЙКИ ==========
        udp_settings_frame = ttk.LabelFrame(control_frame, text="Настройки UDP", padding="10")
        udp_settings_frame.pack(fill=tk.X, pady=(10, 0))

        udp_grid = ttk.Frame(udp_settings_frame)
        udp_grid.pack(fill=tk.X)

        # Порт UDP
        ttk.Label(udp_grid, text="UDP Порт:", font=('Arial', 9)).grid(row=0, column=0, sticky=tk.W, pady=2, padx=(0, 5))
        self.udp_port_var = tk.StringVar(value=str(self.config['server']['port']))
        udp_port_entry = ttk.Entry(udp_grid, textvariable=self.udp_port_var, width=10)
        udp_port_entry.grid(row=0, column=1, sticky=tk.W, pady=2)

        # Максимальный размер пакета
        ttk.Label(udp_grid, text="Макс. размер пакета:", font=('Arial', 9)).grid(row=0, column=2, sticky=tk.W, pady=2,
                                                                                 padx=(20, 5))
        self.packet_size_var = tk.StringVar(value=str(self.config['network'].get('max_packet_size', 1400)))
        packet_size_entry = ttk.Entry(udp_grid, textvariable=self.packet_size_var, width=10)
        packet_size_entry.grid(row=0, column=3, sticky=tk.W, pady=2)

        # Таймаут клиента
        ttk.Label(udp_grid, text="Таймаут клиента (сек):", font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, pady=2,
                                                                                   padx=(0, 5))
        self.client_timeout_var = tk.StringVar(value=str(self.config['network'].get('client_timeout', 30)))
        client_timeout_entry = ttk.Entry(udp_grid, textvariable=self.client_timeout_var, width=10)
        client_timeout_entry.grid(row=1, column=1, sticky=tk.W, pady=2)

        # Heartbeat интервал
        ttk.Label(udp_grid, text="Heartbeat (сек):", font=('Arial', 9)).grid(row=1, column=2, sticky=tk.W, pady=2,
                                                                             padx=(20, 5))
        self.heartbeat_var = tk.StringVar(value=str(self.config['network'].get('heartbeat_interval', 1.0)))
        heartbeat_entry = ttk.Entry(udp_grid, textvariable=self.heartbeat_var, width=10)
        heartbeat_entry.grid(row=1, column=3, sticky=tk.W, pady=2)

        # Кнопка применения UDP настроек
        udp_buttons_frame = ttk.Frame(udp_settings_frame)
        udp_buttons_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(udp_buttons_frame, text="Применить UDP настройки",
                   command=self.apply_udp_settings).pack(side=tk.LEFT)

        # ========== НАСТРОЙКИ GIFCT ==========
        gifct_frame = ttk.LabelFrame(control_frame, text="Настройки Gifct", padding="10")
        gifct_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Галочки для включения/выключения Gifct
        gifct_enable_frame = ttk.Frame(gifct_frame)
        gifct_enable_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(gifct_enable_frame, text="Активные Gifct:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        # ГАЛОЧКА Gifct1
        self.gifct1_enabled_var = tk.BooleanVar(value=self.config['gifct_settings']['gifct_enabled']['Gifct1'])
        self.gifct1_check = ttk.Checkbutton(gifct_enable_frame, text="Gifct1",
                                            variable=self.gifct1_enabled_var,
                                            command=self.update_gifct_status)
        self.gifct1_check.pack(side=tk.LEFT, padx=(20, 10))

        # ГАЛОЧКА Gifct2
        self.gifct2_enabled_var = tk.BooleanVar(value=self.config['gifct_settings']['gifct_enabled']['Gifct2'])
        self.gifct2_check = ttk.Checkbutton(gifct_enable_frame, text="Gifct2",
                                            variable=self.gifct2_enabled_var,
                                            command=self.update_gifct_status)
        self.gifct2_check.pack(side=tk.LEFT)

        # Настройки каждого Gifct
        gifct_config_frame = ttk.Frame(gifct_frame)
        gifct_config_frame.pack(fill=tk.BOTH, expand=True)

        # Gifct1 настройки
        gifct1_frame = ttk.LabelFrame(gifct_config_frame, text="Конфигурация Gifct1", padding="10")
        gifct1_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=5)

        ttk.Label(gifct1_frame, text="Название:", font=('Arial', 9)).grid(row=0, column=0, sticky=tk.W, pady=5,
                                                                          padx=(0, 5))
        self.gifct1_name_var = tk.StringVar(value=self.config['gifct_settings']['gifct_configs']['Gifct1'])
        gifct1_entry = ttk.Entry(gifct1_frame, textvariable=self.gifct1_name_var, width=25)
        gifct1_entry.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(gifct1_frame, text="Описание:", font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, pady=5,
                                                                          padx=(0, 5))
        self.gifct1_desc_var = tk.StringVar(value="Основная способность персонажа")
        gifct1_desc_entry = ttk.Entry(gifct1_frame, textvariable=self.gifct1_desc_var, width=25)
        gifct1_desc_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Gifct2 настройки
        gifct2_frame = ttk.LabelFrame(gifct_config_frame, text="Конфигурация Gifct2", padding="10")
        gifct2_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=5)

        ttk.Label(gifct2_frame, text="Название:", font=('Arial', 9)).grid(row=0, column=0, sticky=tk.W, pady=5,
                                                                          padx=(0, 5))
        self.gifct2_name_var = tk.StringVar(value=self.config['gifct_settings']['gifct_configs']['Gifct2'])
        gifct2_entry = ttk.Entry(gifct2_frame, textvariable=self.gifct2_name_var, width=25)
        gifct2_entry.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(gifct2_frame, text="Описание:", font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, pady=5,
                                                                          padx=(0, 5))
        self.gifct2_desc_var = tk.StringVar(value="Вторичная способность персонажа")
        gifct2_desc_entry = ttk.Entry(gifct2_frame, textvariable=self.gifct2_desc_var, width=25)
        gifct2_desc_entry.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Кнопки управления Gifct
        gifct_buttons_frame = ttk.Frame(gifct_frame)
        gifct_buttons_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(gifct_buttons_frame, text="Применить настройки",
                   command=self.apply_gifct_settings).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(gifct_buttons_frame, text="Сбросить",
                   command=self.reset_gifct_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(gifct_buttons_frame, text="Отключить все",
                   command=self.disable_all_gifct).pack(side=tk.LEFT)

        # ========== СТАТИСТИКА ==========
        stats_frame = ttk.LabelFrame(main_frame, text="Статистика в реальном времени", padding="10")
        stats_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 10))

        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.BOTH, expand=True)

        self.stats_vars = {}
        stats_data = [
            ("Протокол:", "protocol", "UDP"),
            ("UDP Порт:", "udp_port", "5555"),
            ("Игроков онлайн:", "players_online", "0"),
            ("Персонажей онлайн:", "characters_online", "0"),
            ("Всего персонажей:", "total_characters", "0"),
            ("Активных подключений:", "connections", "0"),
            ("Загрузка CPU:", "cpu_usage", "0%"),
            ("Исп. памяти:", "memory_usage", "0 MB"),
            ("Время работы:", "uptime", "00:00:00"),
            ("UDP пакетов получено:", "udp_packets_received", "0"),
            ("UDP пакетов отправлено:", "udp_packets_sent", "0"),
            ("Потеря пакетов:", "packet_loss", "0%"),
            ("Активные Gifct:", "active_gifct", "Gifct1, Gifct2")
        ]

        # Размещаем в 3 колонки вместо 2
        for i, (label, key, default) in enumerate(stats_data):
            row = i % 5
            col = i // 5

            frame = ttk.Frame(stats_grid)
            frame.grid(row=row, column=col, sticky=tk.W, padx=(0, 15), pady=2)

            ttk.Label(frame, text=label, font=('Arial', 9)).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            self.stats_vars[key] = var

            # Специальное форматирование для UDP статистики
            if 'udp' in key or 'пакетов' in label:
                value_label = ttk.Label(frame, textvariable=var, font=('Arial', 9, 'bold'), foreground='#00a8ff')
            elif 'Протокол' in label:
                value_label = ttk.Label(frame, textvariable=var, font=('Arial', 9, 'bold'), foreground='#00ff00')
            else:
                value_label = ttk.Label(frame, textvariable=var, font=('Arial', 9, 'bold'))

            value_label.pack(side=tk.LEFT, padx=(5, 0))

        # Индикаторы состояния Gifct
        gifct_status_frame = ttk.Frame(stats_frame)
        gifct_status_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(gifct_status_frame, text="Статус Gifct:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)

        self.gifct1_status = tk.Canvas(gifct_status_frame, width=20, height=20,
                                       bg='green' if self.gifct1_enabled_var.get() else 'gray',
                                       highlightthickness=1, highlightbackground='black')
        self.gifct1_status.pack(side=tk.LEFT, padx=(10, 5))
        ttk.Label(gifct_status_frame, text="Gifct1", font=('Arial', 9)).pack(side=tk.LEFT)

        self.gifct2_status = tk.Canvas(gifct_status_frame, width=20, height=20,
                                       bg='green' if self.gifct2_enabled_var.get() else 'gray',
                                       highlightthickness=1, highlightbackground='black')
        self.gifct2_status.pack(side=tk.LEFT, padx=(20, 5))
        ttk.Label(gifct_status_frame, text="Gifct2", font=('Arial', 9)).pack(side=tk.LEFT)

        # ========== ИНФОРМАЦИЯ О СЕРВЕРЕ ==========
        info_frame = ttk.LabelFrame(main_frame, text="Информация о UDP сервере", padding="10")
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=(0, 10))

        info_notebook = ttk.Notebook(info_frame)
        info_notebook.pack(fill=tk.BOTH, expand=True)

        # Вкладка "Основное"
        basic_tab = ttk.Frame(info_notebook)
        info_notebook.add(basic_tab, text="Основное")

        server_info = [
            ("Протокол:", self.config['server'].get('protocol', 'udp').upper()),
            ("Хост:", f"{self.config['server']['host']}:{self.config['server']['port']}"),
            ("Макс. игроков:", str(self.config['server']['max_players'])),
            ("Имя сервера:", self.config['server']['server_name']),
            ("Tick rate:", str(self.config['server']['tick_rate'])),
            ("Уровень логов:", self.config['server']['log_level'])
        ]

        for i, (label, value) in enumerate(server_info):
            ttk.Label(basic_tab, text=label, font=('Arial', 9)).grid(row=i, column=0, sticky=tk.W, pady=2, padx=(0, 5))

            # Особый цвет для протокола
            if 'Протокол' in label:
                ttk.Label(basic_tab, text=value, font=('Arial', 9, 'bold'),
                          foreground='#00a8ff').grid(row=i, column=1, sticky=tk.W, pady=2)
            else:
                ttk.Label(basic_tab, text=value, font=('Arial', 9, 'bold')).grid(row=i, column=1, sticky=tk.W, pady=2)

        # Вкладка "Сеть"
        network_tab = ttk.Frame(info_notebook)
        info_notebook.add(network_tab, text="Сеть")

        network_info = [
            ("UDP Порт:", str(self.config['server']['port'])),
            ("Макс. размер пакета:", f"{self.config['network'].get('max_packet_size', 1400)} байт"),
            ("Таймаут клиента:", f"{self.config['network'].get('client_timeout', 30)} сек"),
            ("Heartbeat интервал:", f"{self.config['network'].get('heartbeat_interval', 1.0)} сек"),
            ("Макс. клиентов:", str(self.config['server']['max_players']))
        ]

        for i, (label, value) in enumerate(network_info):
            ttk.Label(network_tab, text=label, font=('Arial', 9)).grid(row=i, column=0, sticky=tk.W, pady=2,
                                                                       padx=(0, 5))
            ttk.Label(network_tab, text=value, font=('Arial', 9, 'bold'),
                      foreground='#00a8ff').grid(row=i, column=1, sticky=tk.W, pady=2)

        # Вкладка "База данных"
        db_tab = ttk.Frame(info_notebook)
        info_notebook.add(db_tab, text="База данных")

        db_info = [
            ("Файл БД:", self.config['database']['path']),
            ("Макс. персонажей:", str(self.config['game']['max_characters_per_player'])),
            ("Стартовая зона:", self.config['game']['starting_zone']),
            ("Автосохранение:", f"каждые {self.config['game']['auto_save_interval']} сек")
        ]

        for i, (label, value) in enumerate(db_info):
            ttk.Label(db_tab, text=label, font=('Arial', 9)).grid(row=i, column=0, sticky=tk.W, pady=2, padx=(0, 5))
            ttk.Label(db_tab, text=value, font=('Arial', 9, 'bold')).grid(row=i, column=1, sticky=tk.W, pady=2)

        # ========== ЛОГИ СЕРВЕРА ==========
        log_frame = ttk.LabelFrame(main_frame, text="Логи UDP сервера", padding="10")
        log_frame.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 10))

        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(log_toolbar, text="Очистить",
                   command=self.clear_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(log_toolbar, text="Экспорт...",
                   command=self.export_logs).pack(side=tk.LEFT, padx=5)

        ttk.Label(log_toolbar, text="Уровень:").pack(side=tk.LEFT, padx=(20, 5))
        self.log_level_var = tk.StringVar(value=self.config['server']['log_level'])
        log_level_combo = ttk.Combobox(
            log_toolbar,
            textvariable=self.log_level_var,
            values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            state='readonly',
            width=12
        )
        log_level_combo.pack(side=tk.LEFT)
        log_level_combo.bind('<<ComboboxSelected>>', lambda e: self.update_log_level())

        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(log_toolbar, text="Автопрокрутка",
                        variable=self.auto_scroll_var).pack(side=tk.LEFT, padx=(20, 0))

        ttk.Label(log_toolbar, text="Поиск:").pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(log_toolbar, textvariable=self.search_var, width=15)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind('<Return>', lambda e: self.search_logs())

        # UDP фильтр логов
        ttk.Label(log_toolbar, text="Фильтр:").pack(side=tk.LEFT, padx=(20, 5))
        self.log_filter_var = tk.StringVar(value="ALL")
        log_filter_combo = ttk.Combobox(
            log_toolbar,
            textvariable=self.log_filter_var,
            values=['ALL', 'UDP', 'GIFCT', 'ERROR', 'SYSTEM'],
            state='readonly',
            width=10
        )
        log_filter_combo.pack(side=tk.LEFT)
        log_filter_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_logs())

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='white'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Настройка тегов для разных типов сообщений
        self.log_text.tag_config('INFO', foreground='#ffffff')
        self.log_text.tag_config('WARNING', foreground='#ff9900')
        self.log_text.tag_config('ERROR', foreground='#ff3333')
        self.log_text.tag_config('DEBUG', foreground='#888888')
        self.log_text.tag_config('CRITICAL', foreground='#ff0066')
        self.log_text.tag_config('SUCCESS', foreground='#00ff00')
        self.log_text.tag_config('GIFCT', foreground='#00ffff')
        self.log_text.tag_config('UDP', foreground='#00a8ff')
        self.log_text.tag_config('NETWORK', foreground='#a0a0ff')

        main_frame.rowconfigure(2, weight=1)

    def start_update_loop(self):
        """Запуск цикла обновления интерфейса"""
        self.update_ui()
        self.root.after(1000, self.start_update_loop)

    def update_ui(self):
        """Обновление интерфейса"""
        while not self.message_queue.empty():
            try:
                msg_type, msg = self.message_queue.get_nowait()
                self.add_log_message(msg, msg_type)
            except queue.Empty:
                break

        self.update_status_indicator()

        if self.server_running:
            self.update_stats()

    def update_status_indicator(self):
        """Обновление индикатора состояния"""
        self.status_indicator.delete("all")
        color = '#00ff00' if self.server_running else '#ff0000'
        self.status_indicator.create_oval(2, 2, 18, 18, fill=color, outline='#cccccc', width=1)

        # Обновляем индикатор UDP
        self.udp_indicator.delete("all")
        udp_color = '#00a8ff' if self.server_running else '#666666'
        self.udp_indicator.create_oval(2, 2, 18, 18, fill=udp_color, outline='#cccccc', width=1)
        if self.server_running:
            self.udp_indicator.create_text(10, 10, text="U", fill='white', font=('Arial', 8, 'bold'))

        # Обновляем индикаторы Gifct
        self.gifct1_status.configure(bg='green' if self.gifct1_enabled_var.get() else 'gray')
        self.gifct2_status.configure(bg='green' if self.gifct2_enabled_var.get() else 'gray')

    def add_log_message(self, message, msg_type='INFO'):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        # Применяем фильтр
        filter_type = self.log_filter_var.get()
        if filter_type != 'ALL':
            if filter_type == 'UDP' and 'UDP' not in msg_type:
                return
            elif filter_type == 'GIFCT' and 'GIFCT' not in msg_type:
                return
            elif filter_type == 'ERROR' and 'ERROR' not in msg_type and 'CRITICAL' not in msg_type:
                return
            elif filter_type == 'SYSTEM' and 'UDP' in msg_type and 'GIFCT' in msg_type:
                return

        self.log_text.insert(tk.END, log_entry, msg_type)

        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)

        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 5000:
            self.log_text.delete('1.0', f'{lines - 5000}.0')

    def log_message(self, message, msg_type='INFO'):
        """Потокобезопасное добавление сообщения"""
        self.message_queue.put((msg_type, message))

    def update_gifct_status(self):
        """Обновление статуса Gifct"""
        enabled_gifct = []
        if self.gifct1_enabled_var.get():
            enabled_gifct.append("Gifct1")
        if self.gifct2_enabled_var.get():
            enabled_gifct.append("Gifct2")

        active_text = ", ".join(enabled_gifct) if enabled_gifct else "Нет активных"
        self.stats_vars['active_gifct'].set(active_text)

        # Обновляем цвет индикаторов
        self.gifct1_status.configure(bg='green' if self.gifct1_enabled_var.get() else 'gray')
        self.gifct2_status.configure(bg='green' if self.gifct2_enabled_var.get() else 'gray')

        self.log_message(f"Статус Gifct обновлен: {active_text}", 'GIFCT')

    def apply_gifct_settings(self):
        """Применение настроек Gifct"""
        try:
            # Обновляем конфигурацию
            self.config['gifct_settings']['gifct_enabled']['Gifct1'] = self.gifct1_enabled_var.get()
            self.config['gifct_settings']['gifct_enabled']['Gifct2'] = self.gifct2_enabled_var.get()
            self.config['gifct_settings']['gifct_configs']['Gifct1'] = self.gifct1_name_var.get()
            self.config['gifct_settings']['gifct_configs']['Gifct2'] = self.gifct2_name_var.get()

            # Сохраняем конфиг
            self.save_config()

            # Обновляем статистику
            self.update_gifct_status()

            self.log_message("Настройки Gifct применены", 'SUCCESS')
            messagebox.showinfo("Успех", "Настройки Gifct успешно применены")

        except Exception as e:
            self.log_message(f"Ошибка применения настроек Gifct: {e}", 'ERROR')
            messagebox.showerror("Ошибка", f"Не удалось применить настройки:\n{str(e)}")

    def apply_udp_settings(self):
        """Применение настроек UDP"""
        try:
            # Обновляем порт
            new_port = int(self.udp_port_var.get())
            if new_port < 1 or new_port > 65535:
                raise ValueError("Порт должен быть в диапазоне 1-65535")

            self.config['server']['port'] = new_port
            self.stats_vars['udp_port'].set(str(new_port))

            # Обновляем сетевые настройки
            self.config['network']['max_packet_size'] = int(self.packet_size_var.get())
            self.config['network']['client_timeout'] = int(self.client_timeout_var.get())
            self.config['network']['heartbeat_interval'] = float(self.heartbeat_var.get())

            # Сохраняем конфиг
            self.save_config()

            self.log_message(f"Настройки UDP применены. Порт: {new_port}", 'UDP')
            messagebox.showinfo("Успех",
                                "Настройки UDP успешно применены\nПерезапустите сервер для активации изменений")

        except ValueError as e:
            self.log_message(f"Ошибка в настройках UDP: {e}", 'ERROR')
            messagebox.showerror("Ошибка", f"Неверные настройки UDP:\n{str(e)}")
        except Exception as e:
            self.log_message(f"Ошибка применения настроек UDP: {e}", 'ERROR')
            messagebox.showerror("Ошибка", f"Не удалось применить настройки UDP:\n{str(e)}")

    def reset_gifct_settings(self):
        """Сброс настроек Gifct к значениям по умолчанию"""
        if messagebox.askyesno("Подтверждение", "Сбросить настройки Gifct к значениям по умолчанию?"):
            self.gifct1_enabled_var.set(True)
            self.gifct2_enabled_var.set(True)
            self.gifct1_name_var.set("Основная способность")
            self.gifct2_name_var.set("Вторичная способность")
            self.gifct1_desc_var.set("Основная способность персонажа")
            self.gifct2_desc_var.set("Вторичная способность персонажа")

            self.update_gifct_status()
            self.log_message("Настройки Gifct сброшены", 'INFO')

    def disable_all_gifct(self):
        """Отключить все Gifct"""
        self.gifct1_enabled_var.set(False)
        self.gifct2_enabled_var.set(False)
        self.update_gifct_status()
        self.log_message("Все Gifct отключены", 'WARNING')

    def enable_all_gifct(self):
        """Включить все Gifct"""
        self.gifct1_enabled_var.set(True)
        self.gifct2_enabled_var.set(True)
        self.update_gifct_status()
        self.log_message("Все Gifct включены", 'INFO')

    def test_udp_connection(self):
        """Тестирование UDP соединения"""
        import socket
        import json

        try:
            port = int(self.udp_port_var.get())

            # Создаем тестовый сокет
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.settimeout(2.0)

            # Пытаемся отправить тестовый пакет
            test_data = {
                'type': 'ping',
                'timestamp': time.time(),
                'test': True
            }

            if self.server_running:
                # Тестируем локальный сервер
                test_socket.sendto(json.dumps(test_data).encode(), ('127.0.0.1', port))
                self.log_message(f"Отправлен тестовый UDP пакет на порт {port}", 'UDP')

                try:
                    data, addr = test_socket.recvfrom(1024)
                    response = json.loads(data.decode())
                    self.log_message(f"Получен ответ от сервера: {response.get('type', 'unknown')}", 'SUCCESS')
                    messagebox.showinfo("Успех", f"UDP сервер отвечает на порту {port}")
                except socket.timeout:
                    self.log_message("Таймаут ожидания ответа от сервера", 'WARNING')
                    messagebox.showwarning("Предупреждение", f"Сервер не ответил на порту {port}")
            else:
                # Просто проверяем доступность порта
                test_socket.bind(('127.0.0.1', 0))  # Случайный порт для теста
                self.log_message(f"Порт {port} доступен для прослушивания", 'UDP')
                messagebox.showinfo("Информация", f"Порт {port} доступен для использования")

            test_socket.close()

        except Exception as e:
            self.log_message(f"Ошибка тестирования UDP: {e}", 'ERROR')
            messagebox.showerror("Ошибка", f"Не удалось протестировать UDP соединение:\n{str(e)}")

    def start_server(self):
        """Запуск UDP сервера"""
        if not self.server_running:
            try:
                self.start_time = time.time()

                self.server_running = True
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self.restart_btn.config(state=tk.NORMAL)
                self.status_label.config(text="Состояние: Запущен (UDP)")

                # Логирование запуска
                self.log_message("=" * 70, 'INFO')
                self.log_message("🚀 ЗАПУСК DPP2 UDP CHARACTER SERVER", 'UDP')
                self.log_message("=" * 70, 'INFO')
                self.log_message(f"🌐 Протокол: UDP", 'UDP')
                self.log_message(f"📍 Хост: {self.config['server']['host']}:{self.config['server']['port']}", 'UDP')
                self.log_message(f"👥 Макс. игроков: {self.config['server']['max_players']}", 'UDP')
                self.log_message(f"⚡ Tick rate: {self.config['server']['tick_rate']}", 'UDP')
                self.log_message(f"📦 Макс. размер пакета: {self.config['network'].get('max_packet_size', 1400)} байт",
                                 'UDP')

                # Информация о Gifct
                enabled_gifct = []
                if self.gifct1_enabled_var.get():
                    enabled_gifct.append(f"Gifct1: {self.gifct1_name_var.get()}")
                if self.gifct2_enabled_var.get():
                    enabled_gifct.append(f"Gifct2: {self.gifct2_name_var.get()}")

                if enabled_gifct:
                    self.log_message("🎮 Активные Gifct:", 'GIFCT')
                    for gifct in enabled_gifct:
                        self.log_message(f"  • {gifct}", 'GIFCT')
                else:
                    self.log_message("⚠️ Внимание: Все Gifct отключены!", 'WARNING')

                self.log_message("=" * 70, 'INFO')
                self.log_message("✅ UDP сервер инициализирован", 'SUCCESS')

                # Создаем и запускаем сервер
                self.server = self.server_core_class()

                self.server_thread = threading.Thread(
                    target=self.run_server,
                    daemon=True,
                    name="UDPServerThread"
                )
                self.server_thread.start()

                # Даем время на запуск
                for i in range(10):
                    if hasattr(self.server, 'running') and self.server.running:
                        self.log_message("✅ UDP сервер успешно запущен и принимает подключения", 'SUCCESS')
                        break
                    time.sleep(0.2)
                else:
                    self.log_message("❌ Не удалось запустить UDP сервер", 'ERROR')
                    self.stop_server()

            except Exception as e:
                self.log_message(f"❌ Ошибка при запуске UDP сервера: {e}", 'ERROR')
                import traceback
                self.log_message(traceback.format_exc(), 'ERROR')
                self.stop_server()

    def run_server(self):
        """Запуск серверной логики"""
        try:
            if self.server and hasattr(self.server, 'start'):
                success = self.server.start()
                if success:
                    while self.server_running and hasattr(self.server, 'running') and self.server.running:
                        time.sleep(0.1)

                        # Обновляем статистику из сервера
                        if hasattr(self.server, 'get_server_info'):
                            server_info = self.server.get_server_info()
                            if server_info:
                                # Игровая статистика
                                world_state = server_info.get('world', {})
                                self.stats['players_online'] = world_state.get('online_players', 0)
                                self.stats['total_characters'] = world_state.get('total_characters', 0)
                                self.stats['characters_online'] = self.stats['players_online']

                                # Сетевая статистика
                                network_stats = server_info.get('network_stats', {})
                                self.stats['udp_packets_received'] = network_stats.get('packets_received', 0)
                                self.stats['udp_packets_sent'] = network_stats.get('packets_sent', 0)

                                # Расчет потери пакетов
                                total_packets = self.stats['udp_packets_received'] + self.stats['udp_packets_sent']
                                if total_packets > 0:
                                    loss_percent = (network_stats.get('packet_loss',
                                                                      0) / total_packets * 100) if total_packets > 0 else 0
                                    self.stats['packet_loss'] = f"{loss_percent:.1f}%"
                                else:
                                    self.stats['packet_loss'] = "0%"

        except Exception as e:
            self.log_message(f"❌ Ошибка в UDP серверном потоке: {e}", 'ERROR')
        finally:
            self.server_running = False

    def stop_server(self):
        """Остановка UDP сервера"""
        if self.server_running:
            self.log_message("🛑 Остановка UDP сервера...", 'UDP')

            self.server_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.restart_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Состояние: Остановлен (UDP)")

            if self.server and hasattr(self.server, 'stop'):
                try:
                    self.server.stop()
                except Exception as e:
                    self.log_message(f"Ошибка при остановке UDP сервера: {e}", 'ERROR')

            self.log_message("✅ UDP сервер остановлен", 'SUCCESS')
            self.log_message("=" * 70, 'INFO')
            self.log_message("📊 ФИНАЛЬНАЯ СТАТИСТИКА:", 'INFO')
            self.log_message(f"  • Время работы: {self.stats_vars['uptime'].get()}", 'INFO')
            self.log_message(f"  • Максимально игроков онлайн: {self.stats['players_online']}", 'INFO')
            self.log_message(f"  • UDP пакетов получено: {self.stats['udp_packets_received']}", 'UDP')
            self.log_message(f"  • UDP пакетов отправлено: {self.stats['udp_packets_sent']}", 'UDP')
            self.log_message("=" * 70, 'INFO')

    def restart_server(self):
        """Перезапуск UDP сервера"""
        self.log_message("🔄 Перезапуск UDP сервера...", 'UDP')
        self.stop_server()
        self.root.after(1000, self.start_server)

    def update_stats(self):
        """Обновление статистики"""
        if self.server_running:
            # Время работы
            if self.start_time:
                uptime = int(time.time() - self.start_time)
                hours = uptime // 3600
                minutes = (uptime % 3600) // 60
                seconds = uptime % 60
                self.stats_vars['uptime'].set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            # Системные метрики
            self.stats_vars['cpu_usage'].set(f"{psutil.cpu_percent():.1f}%")

            memory = psutil.virtual_memory()
            used_mb = memory.used // (1024 * 1024)
            total_mb = memory.total // (1024 * 1024)
            self.stats_vars['memory_usage'].set(f"{used_mb}/{total_mb} MB")

            # Игровая статистика
            self.stats_vars['players_online'].set(str(self.stats['players_online']))
            self.stats_vars['characters_online'].set(str(self.stats['characters_online']))
            self.stats_vars['total_characters'].set(str(self.stats['total_characters']))

            # UDP статистика
            self.stats_vars['udp_packets_received'].set(str(self.stats['udp_packets_received']))
            self.stats_vars['udp_packets_sent'].set(str(self.stats['udp_packets_sent']))
            self.stats_vars['packet_loss'].set(self.stats['packet_loss'])

            # Протокол и порт
            self.stats_vars['protocol'].set("UDP")
            self.stats_vars['udp_port'].set(str(self.config['server']['port']))

            # Активные подключения
            if hasattr(self.server, 'network') and hasattr(self.server.network, 'clients'):
                connections = len(self.server.network.clients)
                self.stats_vars['connections'].set(str(connections))
                self.stats['connections'] = connections
            else:
                self.stats_vars['connections'].set("0")

    def save_config(self):
        """Сохранение конфигурации"""
        try:
            # Обновляем уровень логов
            self.config['server']['log_level'] = self.log_level_var.get()

            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)

            self.log_message("✅ Конфигурация сохранена", 'SUCCESS')
            return True

        except Exception as e:
            self.log_message(f"❌ Ошибка сохранения конфигурации: {e}", 'ERROR')
            messagebox.showerror("Ошибка", f"Не удалось сохранить конфигурацию:\n{str(e)}")
            return False

    def update_log_level(self):
        """Обновление уровня логирования"""
        new_level = self.log_level_var.get()
        self.config['server']['log_level'] = new_level
        self.log_message(f"Уровень логирования изменен на: {new_level}", 'INFO')

    def filter_logs(self):
        """Фильтрация логов"""
        self.clear_logs()
        self.log_message("Логи отфильтрованы по: " + self.log_filter_var.get(), 'INFO')

    def clear_logs(self):
        """Очистка логов"""
        self.log_text.delete('1.0', tk.END)
        self.log_message("Логи очищены", 'INFO')

    def export_logs(self):
        """Экспорт логов в файл"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"udp_server_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get('1.0', tk.END))

                self.log_message(f"✅ Логи экспортированы в {os.path.basename(filename)}", 'SUCCESS')
                messagebox.showinfo("Успех", f"Логи UDP сервера успешно экспортированы в:\n{filename}")

            except Exception as e:
                self.log_message(f"❌ Ошибка экспорта логов: {e}", 'ERROR')
                messagebox.showerror("Ошибка", f"Не удалось экспортировать логи:\n{str(e)}")

    def search_logs(self):
        """Поиск в логах"""
        search_term = self.search_var.get().lower()
        if not search_term:
            return

        self.log_text.tag_remove('highlight', '1.0', tk.END)

        start_pos = '1.0'
        found = False

        while True:
            start_pos = self.log_text.search(search_term, start_pos, stopindex=tk.END, nocase=True)
            if not start_pos:
                break

            end_pos = f"{start_pos}+{len(search_term)}c"
            self.log_text.tag_add('highlight', start_pos, end_pos)
            start_pos = end_pos
            found = True

        if found:
            self.log_text.tag_config('highlight', background='yellow', foreground='black')
            self.log_message(f"Найдено по запросу: '{search_term}'", 'INFO')
        else:
            self.log_message(f"По запросу '{search_term}' ничего не найдено", 'INFO')

    def on_closing(self):
        """Обработка закрытия окна"""
        if self.server_running:
            if messagebox.askyesno("Подтверждение",
                                   "UDP сервер запущен. Завершить работу?"):
                self.stop_server()
                time.sleep(1)
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """Точка входа GUI"""
    import argparse

    parser = argparse.ArgumentParser(description='DPP2 UDP Character Server GUI')
    parser.add_argument('--theme', default='clam', help='Тема оформления')
    parser.add_argument('--port', type=int, help='UDP порт сервера')
    args = parser.parse_args()

    root = tk.Tk()

    from server_core import ServerCore

    app = ServerGUI(root, ServerCore)

    # Если указан порт в аргументах
    if args.port:
        app.udp_port_var.set(str(args.port))

    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    root.mainloop()


if __name__ == "__main__":
    main()