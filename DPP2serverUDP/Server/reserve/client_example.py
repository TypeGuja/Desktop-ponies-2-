#!/usr/bin/env python3
"""
Пример UDP клиента для тестирования DPP2 UDP сервера
С поддержкой системы скинов (гифок) на игроках
"""

import socket
import json
import time
import threading
import random
import os
from pathlib import Path
from PIL import Image, ImageTk  # Для отображения гифок (если используете tkinter)
import tkinter as tk
from tkinter import ttk
import base64
import hashlib


class PlayerSkinManager:
    """Менеджер скинов игроков"""

    def __init__(self):
        self.skins = {}  # character_id -> skin_data
        self.players = {}  # character_id -> player_data (имя, позиция и т.д.)
        self.active_effects = {}  # effect_id -> effect_data

    def update_skin(self, character_id, skin_data):
        """Обновление скина игрока"""
        if character_id not in self.skins:
            self.skins[character_id] = {}
        self.skins[character_id].update(skin_data)
        return self.skins[character_id]

    def get_skin(self, character_id):
        """Получение скина игрока"""
        return self.skins.get(character_id, {})

    def remove_skin(self, character_id):
        """Удаление скина игрока"""
        if character_id in self.skins:
            del self.skins[character_id]

    def update_player_position(self, character_id, position):
        """Обновление позиции игрока"""
        if character_id not in self.players:
            self.players[character_id] = {}
        if 'position' not in self.players[character_id]:
            self.players[character_id]['position'] = {}
        self.players[character_id]['position'].update(position)

    def get_player_position(self, character_id):
        """Получение позиции игрока"""
        if character_id in self.players and 'position' in self.players[character_id]:
            return self.players[character_id]['position']
        return {'x': 0, 'y': 0, 'z': 0}

    def add_effect(self, effect_id, effect_data):
        """Добавление эффекта"""
        self.active_effects[effect_id] = {
            'data': effect_data,
            'start_time': time.time(),
            'end_time': time.time() + effect_data.get('duration', 5)
        }

    def remove_expired_effects(self):
        """Удаление истекших эффектов"""
        current_time = time.time()
        expired = [eid for eid, effect in self.active_effects.items()
                   if effect['end_time'] <= current_time]
        for eid in expired:
            del self.active_effects[eid]
        return expired


class UDPTestClient:
    """Тестовый UDP клиент с поддержкой скинов"""

    def __init__(self, host='127.0.0.1', port=5555, use_gui=False):
        self.host = host
        self.port = port
        self.address = (host, port)

        # Создаем UDP сокет
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(2.0)

        # Основные данные
        self.client_id = None
        self.connected = False
        self.running = False
        self.authenticated = False
        self.in_world = False

        # Данные для тестирования
        self.test_username = f"test_user_{random.randint(1000, 9999)}"
        self.character_id = None
        self.character_name = f"TestChar_{random.randint(1000, 9999)}"
        self.player_id = None

        # Позиция и состояние
        self.position = {'x': random.uniform(0, 100), 'y': random.uniform(0, 100), 'z': 0}
        self.rotation = 0
        self.health = 100
        self.level = 1

        # Менеджер скинов
        self.skin_manager = PlayerSkinManager()

        # Текущий скин
        self.current_skin = {
            'gif_url': f'skins/player_{random.choice(["red", "blue", "green", "purple"])}.gif',
            'gif_name': f'player_{random.choice(["red", "blue", "green", "purple"])}',
            'animation_speed': random.uniform(0.8, 1.2),
            'color_tint': f'#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}',
            'scale': random.uniform(0.8, 1.2),
            'rotation_offset': 0,
            'visible': True,
            'layer': 'character',
            'loop': True,
            'start_frame': 0
        }

        # Очередь сообщений
        self.messages = []
        self.message_lock = threading.Lock()

        # Статистика
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'connected_at': None,
            'ping': 0
        }

        # GUI (опционально)
        self.use_gui = use_gui
        self.root = None
        self.canvas = None
        self.gui_thread = None
        self.gui_ready = False

        # Поток для обновления GUI
        if self.use_gui:
            self.start_gui()

    # ==================== ГРАФИЧЕСКИЙ ИНТЕРФЕЙС ====================

    def start_gui(self):
        """Запуск графического интерфейса"""
        self.gui_thread = threading.Thread(target=self._gui_main, daemon=True)
        self.gui_thread.start()

        # Ждем инициализации GUI
        for _ in range(10):
            if self.gui_ready:
                break
            time.sleep(0.1)

    def _gui_main(self):
        """Основной цикл GUI"""
        self.root = tk.Tk()
        self.root.title(f"DPP2 UDP Client - {self.test_username}")
        self.root.geometry("800x600")
        self.root.configure(bg='#2b2b2b')

        # Основной фрейм
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Панель управления
        control_frame = tk.Frame(main_frame, bg='#3c3c3c', height=100)
        control_frame.pack(fill=tk.X, side=tk.TOP, padx=10, pady=10)

        # Кнопки управления
        button_frame = tk.Frame(control_frame, bg='#3c3c3c')
        button_frame.pack(pady=10)

        self.connect_btn = tk.Button(button_frame, text="Подключиться",
                                     command=self.connect, bg='#4caf50', fg='white')
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        self.auth_btn = tk.Button(button_frame, text="Авторизация",
                                  command=self.authenticate, bg='#2196f3', fg='white', state=tk.DISABLED)
        self.auth_btn.pack(side=tk.LEFT, padx=5)

        self.create_char_btn = tk.Button(button_frame, text="Создать персонажа",
                                         command=self.create_character, bg='#ff9800', fg='white', state=tk.DISABLED)
        self.create_char_btn.pack(side=tk.LEFT, padx=5)

        self.join_world_btn = tk.Button(button_frame, text="Войти в мир",
                                        command=self.join_world, bg='#9c27b0', fg='white', state=tk.DISABLED)
        self.join_world_btn.pack(side=tk.LEFT, padx=5)

        # Кнопки скинов
        skin_frame = tk.Frame(control_frame, bg='#3c3c3c')
        skin_frame.pack(pady=5)

        tk.Label(skin_frame, text="Скины:", bg='#3c3c3c', fg='white').pack(side=tk.LEFT, padx=5)

        skin_colors = ['red', 'blue', 'green', 'purple', 'gold', 'silver']
        for color in skin_colors:
            btn = tk.Button(skin_frame, text=color.capitalize(),
                            command=lambda c=color: self.change_skin_color(c),
                            bg='#555555', fg='white', width=8)
            btn.pack(side=tk.LEFT, padx=2)

        # Канвас для отрисовки игроков
        canvas_frame = tk.Frame(main_frame, bg='#1e1e1e')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(canvas_frame, bg='#1e1e1e', highlightthickness=0)
        scrollbar_y = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        scrollbar_x = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Настройка прокрутки
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind('<Button-4>', self._on_mousewheel)
        self.canvas.bind('<Button-5>', self._on_mousewheel)

        # Фрейм для контента
        self.content_frame = tk.Frame(self.canvas, bg='#1e1e1e')
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content_frame, anchor=tk.NW)

        # Панель информации
        info_frame = tk.Frame(main_frame, bg='#3c3c3c', height=100)
        info_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)

        # Статистика
        stats_frame = tk.Frame(info_frame, bg='#3c3c3c')
        stats_frame.pack(pady=5)

        self.stats_label = tk.Label(stats_frame,
                                    text="Не подключено | Игроков: 0 | Пинг: 0ms",
                                    bg='#3c3c3c', fg='white', font=('Arial', 10))
        self.stats_label.pack()

        # Состояние
        self.status_label = tk.Label(info_frame,
                                     text="Состояние: Отключено",
                                     bg='#3c3c3c', fg='#ff4444', font=('Arial', 9))
        self.status_label.pack()

        # Настройка размера канваса
        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        # Бинд для обновления прокрутки
        self.content_frame.bind('<Configure>', self._update_scrollregion)

        self.gui_ready = True

        # Запуск обновления GUI
        self.root.after(100, self._update_gui)

        # Закрытие окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_gui_close)

        self.root.mainloop()

    def _on_mousewheel(self, event):
        """Обработка колесика мыши"""
        if event.delta:
            self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _update_scrollregion(self, event=None):
        """Обновление области прокрутки"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _update_gui(self):
        """Обновление GUI"""
        if not self.root or not self.gui_ready:
            return

        try:
            # Обновление статистики
            players_count = len(self.skin_manager.skins) + (1 if self.in_world else 0)
            status_text = f"{'Подключено' if self.connected else 'Отключено'} | "
            status_text += f"Игроков: {players_count} | "
            status_text += f"Пинг: {self.stats['ping']}ms | "
            status_text += f"Сообщений: {self.stats['messages_received']}"

            self.stats_label.config(text=status_text)

            # Обновление состояния
            if self.in_world:
                status = "В мире"
                color = "#4caf50"
            elif self.authenticated:
                status = "Авторизован"
                color = "#2196f3"
            elif self.connected:
                status = "Подключен"
                color = "#ff9800"
            else:
                status = "Отключен"
                color = "#ff4444"

            self.status_label.config(text=f"Состояние: {status}", fg=color)

            # Обновление кнопок
            self.auth_btn.config(state=tk.NORMAL if self.connected else tk.DISABLED)
            self.create_char_btn.config(state=tk.NORMAL if self.authenticated else tk.DISABLED)
            self.join_world_btn.config(state=tk.NORMAL if self.character_id else tk.DISABLED)

            # Отрисовка игроков на канвасе
            self._draw_players()

            # Планируем следующее обновление
            self.root.after(50, self._update_gui)

        except Exception as e:
            print(f"[GUI] Ошибка обновления: {e}")

    def _draw_players(self):
        """Отрисовка игроков на канвасе"""
        if not self.canvas:
            return

        # Очищаем предыдущие рисунки
        for item in self.canvas.find_withtag("player"):
            self.canvas.delete(item)

        # Размер области отрисовки
        canvas_width = 600
        canvas_height = 400

        # Отрисовка сетки
        grid_size = 50
        for x in range(0, canvas_width, grid_size):
            self.canvas.create_line(x, 0, x, canvas_height, fill='#333333', tags="grid", width=1)
        for y in range(0, canvas_height, grid_size):
            self.canvas.create_line(0, y, canvas_width, y, fill='#333333', tags="grid", width=1)

        # Отрисовка текущего игрока
        if self.in_world and self.character_id:
            # Центрируем на текущем игроке
            center_x = canvas_width // 2
            center_y = canvas_height // 2

            # Отрисовка текущего игрока (больше и ярче)
            self._draw_player_sprite(
                center_x, center_y,
                self.current_skin['gif_name'].replace('player_', ''),
                "Вы",  # Имя текущего игрока
                is_current=True
            )

            # Отрисовка других игроков относительно текущего
            for char_id, skin_data in self.skin_manager.skins.items():
                if char_id == self.character_id:
                    continue

                # Получаем позицию игрока
                pos = self.skin_manager.get_player_position(char_id)
                player_pos = self.skin_manager.players.get(char_id, {})

                # Преобразуем мировые координаты в координаты канваса
                # (простая проекция: каждый 1.0 в мире = 10 пикселей)
                offset_x = int((pos.get('x', 0) - self.position['x']) * 10 + center_x)
                offset_y = int((pos.get('y', 0) - self.position['y']) * 10 + center_y)

                # Проверяем, находится ли игрок в пределах видимости
                if 0 <= offset_x <= canvas_width and 0 <= offset_y <= canvas_height:
                    color = skin_data.get('gif_name', 'player_blue').replace('player_', '')
                    name = player_pos.get('name', f'Игрок_{char_id[:8]}')

                    self._draw_player_sprite(
                        offset_x, offset_y,
                        color,
                        name,
                        is_current=False
                    )

        # Отрисовка эффектов
        self._draw_effects(canvas_width, canvas_height)

    def _draw_player_sprite(self, x, y, color, name, is_current=False):
        """Отрисовка спрайта игрока"""
        # Цвета для разных скинов
        color_map = {
            'red': '#ff4444',
            'blue': '#4444ff',
            'green': '#44ff44',
            'purple': '#aa44ff',
            'gold': '#ffaa00',
            'silver': '#cccccc',
            'default': '#ffffff'
        }

        base_color = color_map.get(color, color_map['default'])

        # Размер спрайта
        size = 30 if is_current else 25

        # Основной круг (тело игрока)
        self.canvas.create_oval(
            x - size // 2, y - size // 2,
            x + size // 2, y + size // 2,
            fill=base_color,
            outline='#ffffff' if is_current else '#888888',
            width=2 if is_current else 1,
            tags="player"
        )

        # Индикатор направления
        if is_current:
            dir_size = size + 10
            self.canvas.create_line(
                x, y,
                x + dir_size * self.rotation,
                y,
                arrow=tk.LAST,
                arrowshape=(8, 10, 5),
                fill='#ffffff',
                width=2,
                tags="player"
            )

        # Имя игрока
        self.canvas.create_text(
            x, y - size // 2 - 10,
            text=name,
            fill='#ffffff',
            font=('Arial', 9, 'bold' if is_current else 'normal'),
            tags="player"
        )

        # Индикатор здоровья (если не полное)
        if not is_current:
            health_width = 20
            health_height = 4
            self.canvas.create_rectangle(
                x - health_width // 2, y - size // 2 - 5,
                x + health_width // 2, y - size // 2 - 1,
                outline='#444444',
                fill='#444444',
                tags="player"
            )
            self.canvas.create_rectangle(
                x - health_width // 2, y - size // 2 - 5,
                x - health_width // 2 + int(health_width * 0.8), y - size // 2 - 1,
                outline='#44ff44',
                fill='#44ff44',
                tags="player"
            )

    def _draw_effects(self, canvas_width, canvas_height):
        """Отрисовка эффектов"""
        center_x = canvas_width // 2
        center_y = canvas_height // 2

        for effect_id, effect in self.skin_manager.active_effects.items():
            effect_data = effect['data']

            # Преобразуем мировые координаты
            pos = effect_data.get('position', {})
            effect_x = int((pos.get('x', 0) - self.position['x']) * 10 + center_x)
            effect_y = int((pos.get('y', 0) - self.position['y']) * 10 + center_y)

            # Только если в пределах видимости
            if 0 <= effect_x <= canvas_width and 0 <= effect_y <= canvas_height:
                # Анимированный круг для эффекта
                time_alive = time.time() - effect['start_time']
                duration = effect_data.get('duration', 5)

                # Размер пульсирует
                pulse = 0.5 + 0.5 * abs((time_alive % 1) - 0.5)
                effect_size = int(20 + 10 * pulse)

                # Цвет эффекта
                effect_type = effect_data.get('gifct_name', 'default')
                colors = {
                    'fire': '#ff5500',
                    'ice': '#55ffff',
                    'lightning': '#ffff55',
                    'heal': '#55ff55',
                    'default': '#ffffff'
                }
                effect_color = colors.get(effect_type, colors['default'])

                # Прозрачность уменьшается со временем
                opacity = 1.0 - (time_alive / duration)
                if opacity > 0:
                    # Рисуем несколько концентрических кругов для эффекта свечения
                    for i in range(3):
                        size = effect_size + i * 5
                        alpha = int(100 * opacity * (0.7 - i * 0.2))

                        self.canvas.create_oval(
                            effect_x - size // 2, effect_y - size // 2,
                            effect_x + size // 2, effect_y + size // 2,
                            outline=effect_color,
                            stipple='gray50',
                            tags="player"
                        )

    def on_gui_close(self):
        """Обработка закрытия GUI"""
        self.running = False
        if self.root:
            self.root.quit()
            self.root.destroy()

    # ==================== СЕТЕВОЕ ВЗАИМОДЕЙСТВИЕ ====================

    def connect(self):
        """Подключение к UDP серверу"""
        try:
            print(f"[CLIENT] Подключение к UDP серверу {self.host}:{self.port}...")

            # Отправляем инициализационное сообщение
            init_msg = {
                'type': 'client_init',
                'timestamp': time.time(),
                'client_info': {
                    'version': '1.0',
                    'protocol': 'udp',
                    'supports_skins': True,
                    'username': self.test_username
                }
            }

            self.send(init_msg)
            self.stats['connected_at'] = time.time()

            # Ждем ответ
            start_time = time.time()
            while time.time() - start_time < 5:
                response = self.receive()
                if response and response.get('type') == 'welcome':
                    self.client_id = response.get('client_id')
                    self.connected = True
                    print(f"[CLIENT] ✅ Подключено! ID клиента: {self.client_id}")

                    # Обновляем GUI
                    if self.use_gui:
                        self.status_label.config(text="Состояние: Подключен", fg='#ff9800')

                    # Запускаем цикл приема
                    if not self.running:
                        self.running = True
                        receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
                        receive_thread.start()

                    return True
                time.sleep(0.1)

            print(f"[CLIENT] ❌ Таймаут подключения")
            return False

        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка подключения: {e}")
            return False

    def send(self, data):
        """Отправка данных"""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            packet = json_str.encode('utf-8')

            self.socket.sendto(packet, self.address)

            self.stats['messages_sent'] += 1
            self.stats['bytes_sent'] += len(packet)

            print(f"[CLIENT] 📤 Отправлено: {data.get('type', 'unknown')}")
            return True

        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка отправки: {e}")
            return False

    def receive(self):
        """Получение данных"""
        try:
            data, addr = self.socket.recvfrom(4096)
            if data:
                message = json.loads(data.decode('utf-8'))

                with self.message_lock:
                    self.messages.append(message)

                self.stats['messages_received'] += 1
                self.stats['bytes_received'] += len(data)

                # Расчет пинга для ответных сообщений
                if message.get('type') == 'pong':
                    sent_time = message.get('ping_sent', 0)
                    if sent_time:
                        self.stats['ping'] = int((time.time() - sent_time) * 1000)

                return message

        except socket.timeout:
            pass
        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка приема: {e}")
        return None

    def authenticate(self):
        """Аутентификация"""
        print(f"[CLIENT] 🔐 Аутентификация как {self.test_username}...")

        auth_msg = {
            'type': 'auth',
            'username': self.test_username,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(auth_msg)

        # Ждем ответ
        start_time = time.time()
        while time.time() - start_time < 5:
            response = self.receive()
            if response and response.get('type') == 'auth_response':
                if response.get('success'):
                    self.authenticated = True
                    self.player_id = response.get('player_id')
                    print(f"[CLIENT] ✅ Аутентификация успешна! Player ID: {self.player_id}")

                    # Обновляем GUI
                    if self.use_gui:
                        self.status_label.config(text="Состояние: Авторизован", fg='#2196f3')

                    return True
                else:
                    print(f"[CLIENT] ❌ Ошибка аутентификации: {response.get('message')}")
                    return False
            time.sleep(0.1)

        print(f"[CLIENT] ❌ Таймаут аутентификации")
        return False

    def create_character(self):
        """Создание тестового персонажа"""
        print(f"[CLIENT] 🎮 Создание персонажа {self.character_name}...")

        character_data = {
            'id': f"test_char_{random.randint(10000, 99999)}",
            'name': self.character_name,
            'owner': self.test_username,
            'position': self.position,
            'stats': {
                'strength': random.randint(8, 15),
                'agility': random.randint(8, 15),
                'intelligence': random.randint(8, 15),
                'vitality': random.randint(8, 15),
                'luck': random.randint(1, 10)
            },
            'appearance': {
                'hair_color': f'#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}',
                'eye_color': f'#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}',
                'height': random.randint(160, 200),
                'body_type': random.choice(['slim', 'average', 'muscular'])
            },
            'level': 1,
            'health': 100,
            'class': random.choice(['warrior', 'mage', 'archer', 'rogue']),
            'race': random.choice(['human', 'elf', 'dwarf', 'orc'])
        }

        char_msg = {
            'type': 'character_select',
            'character_id': character_data['id'],
            'character_data': character_data,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(char_msg)

        # Ждем ответ
        start_time = time.time()
        while time.time() - start_time < 5:
            response = self.receive()
            if response and response.get('type') == 'character_select_response':
                if response.get('success'):
                    self.character_id = response.get('character_id')
                    self.character_name = response.get('character_data', {}).get('name', self.character_name)
                    print(f"[CLIENT] ✅ Персонаж создан! ID: {self.character_id}, Имя: {self.character_name}")
                    return True
                else:
                    print(f"[CLIENT] ❌ Ошибка создания персонажа: {response.get('message')}")
                    return False
            time.sleep(0.1)

        print(f"[CLIENT] ❌ Таймаут создания персонажа")
        return False

    def join_world(self):
        """Вход в игровой мир"""
        print(f"[CLIENT] 🌍 Вход в игровой мир...")

        join_msg = {
            'type': 'join_world',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'position': self.position,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(join_msg)

        # Ждем ответ
        start_time = time.time()
        while time.time() - start_time < 5:
            response = self.receive()
            if response:
                if response.get('type') == 'world_joined' and response.get('success'):
                    self.in_world = True
                    print(f"[CLIENT] ✅ Вошли в мир!")
                    print(f"[CLIENT] Мир: {response.get('world_info', {}).get('name', 'Неизвестно')}")
                    print(f"[CLIENT] Игроков онлайн: {response.get('world_info', {}).get('online_players', 0)}")

                    # Обновляем GUI
                    if self.use_gui:
                        self.status_label.config(text="Состояние: В мире", fg='#4caf50')

                    # Отправляем информацию о нашем скине
                    self.send_skin_update()

                    return True
                elif response.get('type') == 'error':
                    print(f"[CLIENT] ❌ Ошибка входа в мир: {response.get('message')}")
                    return False
            time.sleep(0.1)

        print(f"[CLIENT] ❌ Таймаут входа в мир")
        return False

    def send_skin_update(self, skin_data=None):
        """Отправка обновления скина"""
        if not skin_data:
            skin_data = self.current_skin

        skin_msg = {
            'type': 'skin_update',
            'client_id': self.client_id,
            'character_id': self.character_id,
            'character_name': self.character_name,
            'skin_data': skin_data,
            'timestamp': time.time(),
            'position': self.position
        }

        return self.send(skin_msg)

    def change_skin_color(self, color):
        """Изменение цвета скина"""
        if not self.in_world:
            print(f"[CLIENT] ❌ Не в мире, нельзя сменить скин")
            return

        new_skin = {
            'gif_url': f'skins/player_{color}.gif',
            'gif_name': f'player_{color}',
            'color_tint': self._get_color_hex(color)
        }

        self.current_skin.update(new_skin)
        self.send_skin_update(new_skin)
        print(f"[CLIENT] 🎨 Сменен скин на {color}")

    def _get_color_hex(self, color):
        """Получение HEX кода цвета"""
        colors = {
            'red': '#ff4444',
            'blue': '#4444ff',
            'green': '#44ff44',
            'purple': '#aa44ff',
            'gold': '#ffaa00',
            'silver': '#cccccc'
        }
        return colors.get(color, '#ffffff')

    # ==================== ОБРАБОТКА СООБЩЕНИЙ ====================

    def receive_loop(self):
        """Цикл приема сообщений"""
        print(f"[CLIENT] 🔄 Запущен цикл приема сообщений")

        while self.running:
            try:
                response = self.receive()
                if response:
                    self.process_message(response)

                # Обработка сообщений из очереди
                with self.message_lock:
                    if self.messages:
                        for msg in self.messages:
                            self.process_message(msg)
                        self.messages.clear()

                # Удаление истекших эффектов
                self.skin_manager.remove_expired_effects()

                # Короткая пауза
                time.sleep(0.01)

            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Ошибка в цикле приема: {e}")

    def process_message(self, message):
        """Обработка одного сообщения"""
        msg_type = message.get('type')

        # Основные игровые сообщения
        if msg_type == 'position_update':
            self.handle_position_update(message)

        elif msg_type == 'chat_message':
            self.handle_chat_message(message)

        elif msg_type == 'player_joined':
            self.handle_player_joined(message)

        elif msg_type == 'player_left':
            self.handle_player_left(message)

        elif msg_type == 'skin_update':
            self.handle_skin_update(message)

        elif msg_type == 'player_skin_info':
            self.handle_player_skin_info(message)

        elif msg_type == 'effect_spawn':
            self.handle_effect_spawn(message)

        elif msg_type == 'world_update':
            self.handle_world_update(message)

        elif msg_type == 'error':
            print(f"[CLIENT] ❌ Ошибка от сервера: {message.get('message')}")

        elif msg_type in ['pong', 'heartbeat_response']:
            pass  # Игнорируем, уже обработано в receive()

        else:
            print(f"[CLIENT] 📥 Получено: {msg_type}")

    def handle_position_update(self, response):
        """Обработка обновления позиции другого игрока"""
        character_id = response.get('character_id')
        position = response.get('position', {})
        character_name = response.get('character_name')

        if character_id and character_id != self.character_id:
            self.skin_manager.update_player_position(character_id, position)

            # Сохраняем имя игрока
            if character_id not in self.skin_manager.players:
                self.skin_manager.players[character_id] = {}
            self.skin_manager.players[character_id]['name'] = character_name

            if random.random() < 0.01:  # 1% шанс логировать
                print(
                    f"[CLIENT] 👤 Движение {character_name}: x={position.get('x', 0):.2f}, y={position.get('y', 0):.2f}")

    def handle_chat_message(self, response):
        """Обработка сообщения чата"""
        character_name = response.get('character_name')
        text = response.get('text', '')
        channel = response.get('channel', 'global')

        print(f"[CLIENT] 💬 {channel.upper()} | {character_name}: {text}")

    def handle_player_joined(self, response):
        """Обработка входа игрока в мир"""
        character_id = response.get('character_id')
        character_name = response.get('character_name')
        position = response.get('position', {})

        print(f"[CLIENT] 👤 {character_name} присоединился к миру")

        # Сохраняем информацию об игроке
        self.skin_manager.update_player_position(character_id, position)
        self.skin_manager.players[character_id] = {
            'name': character_name,
            'position': position
        }

        # Запрашиваем скин игрока
        self.request_player_skin(character_id)

    def handle_player_left(self, response):
        """Обработка выхода игрока из мира"""
        character_id = response.get('character_id')
        character_name = response.get('character_name')

        print(f"[CLIENT] 👋 {character_name} покинул мир")

        # Удаляем скин и информацию об игроке
        self.skin_manager.remove_skin(character_id)
        if character_id in self.skin_manager.players:
            del self.skin_manager.players[character_id]

    def handle_skin_update(self, response):
        """Обработка обновления скина другого игрока"""
        character_id = response.get('character_id')
        skin_data = response.get('skin_data', {})
        character_name = response.get('character_name')

        if character_id and character_id != self.character_id:
            updated_skin = self.skin_manager.update_skin(character_id, skin_data)
            print(f"[CLIENT] 🎨 Обновлен скин игрока {character_name}: {skin_data.get('gif_name', 'default')}")

    def handle_player_skin_info(self, response):
        """Обработка информации о скине игрока"""
        character_id = response.get('character_id')
        skin_data = response.get('skin_data', {})
        character_name = response.get('character_name')

        self.skin_manager.update_skin(character_id, skin_data)
        print(f"[CLIENT] 🎨 Получен скин игрока {character_name}")

    def handle_effect_spawn(self, response):
        """Обработка появления эффекта"""
        effect_data = response.get('effect_data', {})
        character_name = response.get('character_name')
        effect_type = effect_data.get('gifct_name', 'default')

        # Создаем уникальный ID для эффекта
        effect_id = f"{effect_data.get('character_id', 'unknown')}_{int(time.time() * 1000)}"

        self.skin_manager.add_effect(effect_id, effect_data)
        print(f"[CLIENT] ✨ {character_name} использует {effect_type}")

    def handle_world_update(self, response):
        """Обработка обновления мира"""
        update_type = response.get('update_type')

        if update_type == 'time':
            new_time = response.get('time')
            print(f"[CLIENT] 🕐 Время в мире: {new_time}")

        elif update_type == 'weather':
            weather = response.get('weather')
            print(f"[CLIENT] 🌤️ Погода изменилась: {weather}")

    def request_player_skin(self, character_id):
        """Запрос скина конкретного игрока"""
        request_msg = {
            'type': 'request_skin',
            'client_id': self.client_id,
            'target_character_id': character_id,
            'timestamp': time.time()
        }
        self.send(request_msg)

    # ==================== ТЕСТОВЫЕ ДЕЙСТВИЯ ====================

    def move_randomly(self):
        """Случайное движение"""
        if not self.in_world:
            return

        # Обновляем позицию
        self.position['x'] += random.uniform(-2, 2)
        self.position['y'] += random.uniform(-2, 2)
        self.rotation = random.uniform(-1, 1)

        move_msg = {
            'type': 'position_update',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'position': self.position,
            'rotation': self.rotation,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(move_msg)
        print(f"[CLIENT] 🚶 Движение: x={self.position['x']:.2f}, y={self.position['y']:.2f}")

    def send_chat(self, message):
        """Отправка сообщения в чат"""
        if not self.in_world:
            return

        chat_msg = {
            'type': 'chat_message',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'text': message,
            'timestamp': time.time(),
            'client_id': self.client_id,
            'channel': 'global'
        }

        self.send(chat_msg)
        print(f"[CLIENT] 💬 Чат: {message}")

    def heartbeat(self):
        """Отправка heartbeat"""
        if not self.connected:
            return

        hb_msg = {
            'type': 'heartbeat',
            'timestamp': time.time(),
            'ping_sent': time.time(),
            'client_id': self.client_id
        }

        self.send(hb_msg)

    def activate_gifct(self, gifct_id='fireball'):
        """Активация Gifct-способности"""
        if not self.in_world:
            return

        effect_data = {
            'gifct_id': gifct_id,
            'gifct_name': gifct_id,
            'gif_url': f'effects/{gifct_id}.gif',
            'position': self.position.copy(),
            'duration': random.uniform(2, 5),
            'scale': random.uniform(0.5, 2.0)
        }

        gifct_msg = {
            'type': 'gifct_activation',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'gifct_id': gifct_id,
            'gifct_data': effect_data,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(gifct_msg)
        print(f"[CLIENT] ✨ Активирован {gifct_id}")

    # ==================== ТЕСТОВЫЕ СЦЕНАРИИ ====================

    def test_scenario(self):
        """Тестовый сценарий"""
        print(f"\n{'=' * 50}")
        print(f"🚀 Запуск тестового UDP сценария с поддержкой скинов")
        print(f"{'=' * 50}\n")

        # 1. Подключение
        if not self.connect():
            return False

        # 2. Аутентификация
        if not self.authenticate():
            return False

        # 3. Создание персонажа
        if not self.create_character():
            return False

        # 4. Вход в мир
        if not self.join_world():
            return False

        print(f"\n{'=' * 50}")
        print(f"✅ Тестовый сценарий выполнен успешно!")
        print(f"👤 Имя: {self.character_name}")
        print(f"🎨 Скин: {self.current_skin['gif_name']}")
        print(f"📍 Позиция: x={self.position['x']:.2f}, y={self.position['y']:.2f}")
        print(f"{'=' * 50}\n")

        # Основной цикл действий (если не используется GUI)
        if not self.use_gui:
            try:
                for i in range(30):  # 30 циклов действий
                    if not self.running:
                        break

                    print(f"\n[ЦИКЛ {i + 1}/30]")

                    # Движение
                    self.move_randomly()

                    # Heartbeat
                    if i % 5 == 0:
                        self.heartbeat()

                    # Чат (каждый 3й цикл)
                    if i % 3 == 0:
                        self.send_chat(f"Тестовое сообщение {i + 1} от {self.character_name}")

                    # Смена скина (каждый 10й цикл)
                    if i % 10 == 0 and i > 0:
                        color = random.choice(['red', 'blue', 'green', 'purple', 'gold'])
                        self.change_skin_color(color)

                    # Активация способности (каждый 7й цикл)
                    if i % 7 == 0 and i > 0:
                        gifct = random.choice(['fireball', 'heal', 'shield', 'lightning'])
                        self.activate_gifct(gifct)

                    # Ожидание
                    time.sleep(2)

            except KeyboardInterrupt:
                print("\n[CLIENT] Прервано пользователем")

            finally:
                self.cleanup()

        return True

    def simple_test(self):
        """Простой тест подключения"""
        print(f"[CLIENT] Простой тест UDP подключения...")

        if self.connect():
            print(f"[CLIENT] ✅ Подключение успешно!")

            # Отправляем ping
            ping_msg = {
                'type': 'ping',
                'timestamp': time.time(),
                'ping_sent': time.time(),
                'client_id': self.client_id
            }
            self.send(ping_msg)

            # Ждем ответ
            for _ in range(3):
                response = self.receive()
                if response and response.get('type') == 'pong':
                    print(f"[CLIENT] ✅ Ping-Pong успешен!")
                    self.cleanup()
                    return True
                time.sleep(0.5)

            print(f"[CLIENT] ❌ Нет ответа на ping")
            self.cleanup()
            return False

        return False

    def cleanup(self):
        """Очистка и отключение"""
        self.running = False

        # Выход из мира
        if self.in_world:
            leave_msg = {
                'type': 'leave_world',
                'character_id': self.character_id,
                'character_name': self.character_name,
                'timestamp': time.time(),
                'client_id': self.client_id
            }
            self.send(leave_msg)

        # Отключение
        if self.connected:
            disconnect_msg = {
                'type': 'client_disconnect',
                'timestamp': time.time(),
                'client_id': self.client_id
            }
            self.send(disconnect_msg)

        # Закрытие сокета
        if hasattr(self, 'socket'):
            try:
                self.socket.close()
            except:
                pass

        print("[CLIENT] 📡 Отключено")

    def run_interactive(self):
        """Интерактивный режим"""
        print(f"DPP2 UDP Test Client - Интерактивный режим")
        print(f"Сервер: {self.host}:{self.port}")
        print(f"{'=' * 50}\n")

        while True:
            print("\nДоступные команды:")
            print("  1. Подключиться")
            print("  2. Авторизация")
            print("  3. Создать персонажа")
            print("  4. Войти в мир")
            print("  5. Двигаться случайно")
            print("  6. Отправить сообщение в чат")
            print("  7. Сменить скин")
            print("  8. Использовать способность")
            print("  9. Показать статистику")
            print("  0. Выход")

            choice = input("\nВыберите команду: ")

            if choice == '1':
                self.connect()
            elif choice == '2':
                self.authenticate()
            elif choice == '3':
                self.create_character()
            elif choice == '4':
                self.join_world()
            elif choice == '5' and self.in_world:
                self.move_randomly()
            elif choice == '6' and self.in_world:
                msg = input("Введите сообщение: ")
                self.send_chat(msg)
            elif choice == '7' and self.in_world:
                colors = ['red', 'blue', 'green', 'purple', 'gold', 'silver']
                for i, color in enumerate(colors):
                    print(f"  {i + 1}. {color}")
                color_choice = input("Выберите цвет: ")
                try:
                    idx = int(color_choice) - 1
                    if 0 <= idx < len(colors):
                        self.change_skin_color(colors[idx])
                except:
                    print("Неверный выбор")
            elif choice == '8' and self.in_world:
                gifcts = ['fireball', 'heal', 'shield', 'lightning', 'ice']
                for i, gifct in enumerate(gifcts):
                    print(f"  {i + 1}. {gifct}")
                gifct_choice = input("Выберите способность: ")
                try:
                    idx = int(gifct_choice) - 1
                    if 0 <= idx < len(gifcts):
                        self.activate_gifct(gifcts[idx])
                except:
                    print("Неверный выбор")
            elif choice == '9':
                print(f"\nСтатистика:")
                print(f"  Сообщений отправлено: {self.stats['messages_sent']}")
                print(f"  Сообщений получено: {self.stats['messages_received']}")
                print(f"  Пинг: {self.stats['ping']}ms")
                print(f"  Подключен: {self.connected}")
                print(f"  Авторизован: {self.authenticated}")
                print(f"  В мире: {self.in_world}")
                print(f"  Скинов других игроков: {len(self.skin_manager.skins)}")
            elif choice == '0':
                self.cleanup()
                break
            else:
                print("Неверная команда или действие недоступно")


def main():
    """Главная функция тестового клиента"""
    import argparse

    parser = argparse.ArgumentParser(description='DPP2 UDP Test Client с поддержкой скинов')
    parser.add_argument('--host', default='127.0.0.1', help='Адрес сервера')
    parser.add_argument('--port', type=int, default=5555, help='Порт сервера')
    parser.add_argument('--simple', action='store_true', help='Простой тест подключения')
    parser.add_argument('--gui', action='store_true', help='Использовать графический интерфейс')
    parser.add_argument('--interactive', action='store_true', help='Интерактивный режим')
    parser.add_argument('--username', help='Имя пользователя для теста')

    args = parser.parse_args()

    print(f"DPP2 UDP Test Client с поддержкой скинов")
    print(f"Сервер: {args.host}:{args.port}")
    print(f"{'=' * 50}\n")

    client = UDPTestClient(args.host, args.port, use_gui=args.gui)

    if args.username:
        client.test_username = args.username

    if args.simple:
        success = client.simple_test()
    elif args.interactive:
        client.run_interactive()
        success = True
    elif args.gui:
        # GUI запускается автоматически в конструкторе
        success = True
        # Ожидаем завершения GUI
        if client.gui_thread:
            client.gui_thread.join()
    else:
        success = client.test_scenario()

    if success:
        print(f"\n{'=' * 50}")
        print(f"✅ Клиент завершил работу!")
        print(f"{'=' * 50}")
        return 0
    else:
        print(f"\n{'=' * 50}")
        print(f"❌ Клиент завершил работу с ошибками!")
        print(f"{'=' * 50}")
        return 1


if __name__ == "__main__":
    import sys

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        sys.exit(0)