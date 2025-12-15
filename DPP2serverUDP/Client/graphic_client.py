#!/usr/bin/env python3
"""
DPP2 Graphic Client - Графический интерфейс с WASD управлением (UDP версия)
"""

import pygame
import sys
import threading
import time
import uuid
from enum import Enum
from datetime import datetime
import math
import queue


class GameState(Enum):
    """Состояния игры"""
    MENU = 1
    CONNECTING = 2
    CHARACTER_SELECT = 3
    IN_GAME = 4
    CHAT = 5


class DPP2GraphicClient:
    """Основной графический клиент (UDP версия)"""

    def __init__(self):
        pygame.init()

        # Настройки окна
        self.width = 1200
        self.height = 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("DPP2 Графический Клиент (UDP)")

        # Игровые состояния
        self.game_state = GameState.MENU
        self.running = True
        self.clock = pygame.time.Clock()
        self.fps = 60

        # Сетевое подключение (UDP)
        from network_client import NetworkClient
        self.network = NetworkClient()
        self.connected = False
        self.connection_in_progress = False

        # Очередь для сообщений от сетевого потока
        self.network_queue = queue.Queue()

        # Игровые данные
        self.username = ""
        self.character = None
        self.other_players = {}
        self.in_world = False
        self.world_data = {}
        self.character_selected = False

        # Генерация уникального client_id
        self.client_id = str(uuid.uuid4())[:8]
        print(f"🆔 Сгенерирован client_id: {self.client_id}")

        # Управление WASD
        self.keys = {
            pygame.K_w: False,
            pygame.K_a: False,
            pygame.K_s: False,
            pygame.K_d: False,
            pygame.K_SPACE: False,
            pygame.K_LSHIFT: False,
            pygame.K_UP: False,
            pygame.K_DOWN: False,
            pygame.K_LEFT: False,
            pygame.K_RIGHT: False
        }

        # UI элементы
        self.fonts = {
            'small': pygame.font.SysFont('Arial', 14),
            'medium': pygame.font.SysFont('Arial', 18),
            'large': pygame.font.SysFont('Arial', 24, bold=True),
            'title': pygame.font.SysFont('Arial', 36, bold=True)
        }

        # Цвета
        self.colors = {
            'background': (25, 25, 35),
            'panel': (40, 40, 55),
            'panel_dark': (30, 30, 45),
            'text': (220, 220, 220),
            'text_light': (255, 255, 255),
            'button': (65, 85, 185),
            'button_hover': (85, 105, 205),
            'button_disabled': (80, 80, 100),
            'input_bg': (50, 50, 65),
            'input_active': (70, 90, 180),
            'player': (80, 140, 255),
            'other_player': (255, 80, 80),
            'grid': (45, 45, 60),
            'chat_bg': (40, 40, 50, 220),
            'status_connected': (100, 255, 100),
            'status_disconnected': (255, 100, 100),
            'success': (100, 255, 100),
            'error': (255, 100, 100),
            'warning': (255, 200, 100),
            'udp_indicator': (100, 200, 255)
        }

        # UI элементы меню
        self.menu_buttons = []
        self.input_fields = []
        self.chat_messages = []
        self.chat_input = ""
        self.chat_active = False
        self.active_input_field = None

        # Камера
        self.camera_offset = [self.width // 2, self.height // 2]
        self.camera_zoom = 1.0
        self.grid_size = 50

        # Время
        self.last_update = time.time()
        self.position_update_rate = 0.016
        self.last_position_update = 0
        self.last_heartbeat = 0
        self.heartbeat_interval = 1.0

        # Статистика
        self.stats = {
            'fps': 0,
            'players_online': 0,
            'ping': 0,
            'udp_packets_sent': 0,
            'udp_packets_received': 0
        }

        # Панели интерфейса
        self.side_panel_width = 300
        self.top_panel_height = 60

        # Инициализация UI
        self.init_ui()

        # Флаг для остановки сетевого потока
        self.stop_network_thread = False
        self.network_thread = None

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        side_panel_x = self.width - self.side_panel_width

        self.input_fields = [
            {
                'name': 'server_host',
                'label': 'Адрес сервера (UDP):',
                'rect': pygame.Rect(side_panel_x + 20, 120, self.side_panel_width - 40, 35),
                'text': '127.0.0.1',
                'active': False,
                'visible': True,
                'max_length': 50
            },
            {
                'name': 'server_port',
                'label': 'Порт сервера:',
                'rect': pygame.Rect(side_panel_x + 20, 185, self.side_panel_width - 40, 35),
                'text': '5555',
                'active': False,
                'visible': True,
                'max_length': 10
            },
            {
                'name': 'username',
                'label': 'Имя пользователя:',
                'rect': pygame.Rect(side_panel_x + 20, 250, self.side_panel_width - 40, 35),
                'text': '',
                'active': False,
                'visible': False,
                'max_length': 20
            }
        ]

        button_y_start = 320
        button_height = 45
        button_spacing = 60

        self.menu_buttons = [
            {
                'id': 'connect',
                'text': '📡 Подключиться (UDP)',
                'rect': pygame.Rect(side_panel_x + 20, button_y_start, self.side_panel_width - 40, button_height),
                'action': self.connect_to_server,
                'enabled': True
            },
            {
                'id': 'login',
                'text': '👤 Войти в систему',
                'rect': pygame.Rect(side_panel_x + 20, button_y_start + button_spacing, self.side_panel_width - 40,
                                    button_height),
                'action': self.login,
                'enabled': False
            },
            {
                'id': 'character',
                'text': '🎮 Выбрать персонажа',
                'rect': pygame.Rect(side_panel_x + 20, button_y_start + button_spacing * 2, self.side_panel_width - 40,
                                    button_height),
                'action': self.select_character,
                'enabled': False
            },
            {
                'id': 'join_world',
                'text': '🌍 Войти в игровой мир',
                'rect': pygame.Rect(side_panel_x + 20, button_y_start + button_spacing * 3, self.side_panel_width - 40,
                                    button_height),
                'action': self.join_world,
                'enabled': False
            },
            {
                'id': 'quit',
                'text': '🚪 Выход из игры',
                'rect': pygame.Rect(side_panel_x + 20, button_y_start + button_spacing * 4, self.side_panel_width - 40,
                                    button_height),
                'action': self.quit_game,
                'enabled': True
            }
        ]

    def start_network_thread(self):
        """Запуск сетевого потока для UDP"""
        if self.network_thread and self.network_thread.is_alive():
            self.stop_network_thread = True
            self.network_thread.join(timeout=1.0)

        self.stop_network_thread = False
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.network_thread.start()

    def network_loop(self):
        """Сетевой цикл для UDP"""
        while self.running and not self.stop_network_thread:
            try:
                if self.network.is_connected():
                    data = self.network.receive()
                    if data:
                        self.stats['udp_packets_received'] += 1
                        self.network_queue.put(data)
                else:
                    time.sleep(0.1)

                current_time = time.time()
                if (self.network.is_connected() and
                        current_time - self.last_heartbeat >= self.heartbeat_interval):
                    self.network.send_heartbeat()
                    self.last_heartbeat = current_time

            except Exception as e:
                print(f"⚠️ Ошибка в UDP сетевом потоке: {e}")
                time.sleep(0.5)

    def process_network_messages(self):
        """Обработка сообщений из очереди"""
        try:
            while not self.network_queue.empty():
                data = self.network_queue.get_nowait()
                self.handle_server_message(data)
        except queue.Empty:
            pass

    def run(self):
        """Главный игровой цикл"""
        while self.running:
            self.handle_events()
            self.process_network_messages()
            self.update()
            self.render()
            self.clock.tick(self.fps)
            self.stats['fps'] = int(self.clock.get_fps())

        self.cleanup()
        pygame.quit()
        sys.exit()

    def cleanup(self):
        """Очистка ресурсов"""
        self.stop_network_thread = True
        if self.network_thread:
            self.network_thread.join(timeout=1.0)

        if self.network and self.network.is_connected():
            self.network.disconnect()

    def handle_events(self):
        """Обработка событий"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event)
            elif event.type == pygame.KEYUP:
                self.handle_keyup(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_click(event)
            elif event.type == pygame.TEXTINPUT:
                self.handle_text_input(event.text)

    def handle_keydown(self, event):
        if event.key in self.keys:
            self.keys[event.key] = True
        elif event.key == pygame.K_RETURN:
            if self.chat_active:
                self.send_chat_message()
                self.chat_active = False
                self.chat_input = ""
            elif self.active_input_field is not None:
                field = self.input_fields[self.active_input_field]
                if field['name'] == 'username' and field['text'].strip():
                    self.login()
            elif self.in_world:
                self.chat_active = True
        elif event.key == pygame.K_ESCAPE:
            if self.chat_active:
                self.chat_active = False
                self.chat_input = ""
            elif self.active_input_field is not None:
                self.active_input_field = None
                for field in self.input_fields:
                    field['active'] = False
        elif event.key == pygame.K_BACKSPACE:
            if self.chat_active:
                self.chat_input = self.chat_input[:-1]
            elif self.active_input_field is not None:
                field = self.input_fields[self.active_input_field]
                if len(field['text']) > 0:
                    field['text'] = field['text'][:-1]
        elif event.key == pygame.K_TAB:
            self.switch_input_field()
        elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
            self.camera_zoom = min(self.camera_zoom * 1.1, 3.0)
        elif event.key == pygame.K_MINUS:
            self.camera_zoom = max(self.camera_zoom * 0.9, 0.5)

    def handle_keyup(self, event):
        if event.key in self.keys:
            self.keys[event.key] = False

    def handle_mouse_click(self, event):
        mouse_pos = pygame.mouse.get_pos()
        field_clicked = False

        for i, field in enumerate(self.input_fields):
            if field.get('visible', True) and field['rect'].collidepoint(mouse_pos):
                self.active_input_field = i
                field['active'] = True
                field_clicked = True
                break

        if not field_clicked:
            self.active_input_field = None
            for field in self.input_fields:
                field['active'] = False

        if event.button == 1:
            for button in self.menu_buttons:
                if button['rect'].collidepoint(mouse_pos) and button.get('enabled', True):
                    button['action']()
        elif event.button == 4:
            self.camera_zoom = min(self.camera_zoom * 1.1, 3.0)
        elif event.button == 5:
            self.camera_zoom = max(self.camera_zoom * 0.9, 0.5)

    def handle_text_input(self, text):
        if self.chat_active:
            if len(self.chat_input) < 100:
                self.chat_input += text
        elif self.active_input_field is not None:
            field = self.input_fields[self.active_input_field]
            if len(field['text']) < field.get('max_length', 50):
                if text not in ['\t', '\r', '\n']:
                    field['text'] += text

    def switch_input_field(self):
        if self.active_input_field is not None:
            visible_fields = [i for i, f in enumerate(self.input_fields) if f.get('visible', True)]
            if visible_fields:
                current_index = visible_fields.index(
                    self.active_input_field) if self.active_input_field in visible_fields else -1
                next_index = (current_index + 1) % len(visible_fields)
                self.active_input_field = visible_fields[next_index]
                for i, field in enumerate(self.input_fields):
                    field['active'] = (i == self.active_input_field)
        else:
            visible_fields = [i for i, f in enumerate(self.input_fields) if f.get('visible', True)]
            if visible_fields:
                self.active_input_field = visible_fields[0]
                self.input_fields[self.active_input_field]['active'] = True

    def update(self):
        """Обновление игры"""
        current_time = time.time()
        delta_time = current_time - self.last_update

        if self.in_world and self.character and not self.chat_active:
            self.update_player_position(delta_time)

        self.update_connection_status()
        self.stats['players_online'] = len(self.other_players) + (1 if self.character else 0)
        self.update_join_world_button()
        self.last_update = current_time

    def update_player_position(self, delta_time):
        if not self.in_world or not self.character or self.chat_active:
            return

        dx, dy, dz = 0, 0, 0
        speed = 200.0 * delta_time

        if self.keys[pygame.K_w] or self.keys[pygame.K_UP]:
            dy -= speed
        if self.keys[pygame.K_s] or self.keys[pygame.K_DOWN]:
            dy += speed
        if self.keys[pygame.K_a] or self.keys[pygame.K_LEFT]:
            dx -= speed
        if self.keys[pygame.K_d] or self.keys[pygame.K_RIGHT]:
            dx += speed
        if self.keys[pygame.K_SPACE]:
            dz += speed
        if self.keys[pygame.K_LSHIFT]:
            dz -= speed

        if dx != 0 or dy != 0 or dz != 0:
            pos = self.character.get('position', {'x': 0, 'y': 0, 'z': 0})
            pos['x'] += dx / 100
            pos['y'] += dy / 100
            pos['z'] += dz / 100

            from character_manager import CharacterManager
            cm = CharacterManager()
            self.character['position'] = pos
            cm.save_character(self.character)

            current_time = time.time()
            if current_time - self.last_position_update >= self.position_update_rate:
                self.send_position_update(pos)
                self.last_position_update = current_time

    def update_connection_status(self):
        self.connected = self.network.is_connected()
        for button in self.menu_buttons:
            if button['id'] == 'login':
                button['enabled'] = self.connected
            elif button['id'] == 'character':
                button['enabled'] = bool(self.username)

    def update_join_world_button(self):
        for button in self.menu_buttons:
            if button['id'] == 'join_world':
                should_enable = (
                        self.connected and
                        self.username and
                        self.character and
                        not self.in_world
                )
                button['enabled'] = should_enable
                break

    def send_position_update(self, position):
        """Отправка обновления позиции на сервер через UDP"""
        if not self.connected or not self.character:
            return

        data = {
            'type': 'position_update',
            'client_id': self.client_id,  # Уникальный ID клиента
            'character_id': self.character['id'],  # ID персонажа
            'character_name': self.character['name'],
            'position': position,
            'timestamp': datetime.now().isoformat()
        }

        print(f"📤 Отправка позиции на сервер: x={position['x']:.2f}, y={position['y']:.2f}")
        self.stats['udp_packets_sent'] += 1
        self.network.safe_send(data)

    def send_chat_message(self):
        if not self.chat_input.strip() or not self.connected:
            return

        data = {
            'type': 'chat_message',
            'client_id': self.client_id,  # Добавляем client_id
            'character_id': self.character['id'] if self.character else None,
            'character_name': self.character['name'] if self.character else self.username,
            'text': self.chat_input,
            'timestamp': datetime.now().isoformat()
        }

        self.stats['udp_packets_sent'] += 1
        self.network.safe_send(data)
        self.add_chat_message(f"Вы: {self.chat_input}")

    def add_chat_message(self, message):
        self.chat_messages.append(message)
        if len(self.chat_messages) > 10:
            self.chat_messages.pop(0)

    def handle_server_message(self, data):
        """Обработка сообщений от сервера"""
        msg_type = data.get('type')

        # Отладочный вывод для позиций
        if msg_type == 'position_update':
            print(f"📥 Получена позиция от сервера: {data}")

        if msg_type == 'welcome':
            self.add_chat_message("[СИСТЕМА] ✅ Подключено к UDP серверу")

        elif msg_type == 'auth_response':
            success = data.get('success', False)
            if success:
                self.add_chat_message("[СИСТЕМА] ✅ Авторизация успешна")
                self.character_selected = False
            else:
                error_msg = data.get('message', 'Ошибка авторизации')
                self.add_chat_message(f"[СИСТЕМА] ❌ Ошибка авторизации: {error_msg}")

        elif msg_type == 'character_select_response':
            success = data.get('success', False)
            if success:
                self.character_selected = True
                self.add_chat_message("[СИСТЕМА] ✅ Персонаж выбран на сервере")
            else:
                error_msg = data.get('message', 'Ошибка выбора персонажа')
                self.add_chat_message(f"[СИСТЕМА] ❌ Ошибка выбора персонажа: {error_msg}")

        elif msg_type == 'position_update':
            # Получаем данные персонажа из сообщения
            character_id = data.get('character_id')
            position = data.get('position', {})

            # Проверяем, что это не наша собственная позиция
            if self.character and character_id != self.character.get('id'):
                character_name = data.get('character_name', 'Неизвестно')

                # Создаем или обновляем запись игрока
                self.other_players[character_id] = {
                    'id': character_id,
                    'name': character_name,
                    'position': position,
                    'timestamp': time.time()
                }

                print(
                    f"📍 Обновлена позиция {character_name}: x={position.get('x', 0):.2f}, y={position.get('y', 0):.2f}")

        elif msg_type == 'player_joined':
            player_id = data.get('character_id') or data.get('player_id')
            player_name = data.get('character_name', 'Игрок')
            position = data.get('position', {'x': 0, 'y': 0, 'z': 0})

            self.other_players[player_id] = {
                'id': player_id,
                'name': player_name,
                'position': position,
                'timestamp': time.time()
            }
            self.add_chat_message(f"[СИСТЕМА] 👤 {player_name} присоединился")

        elif msg_type == 'player_left':
            player_id = data.get('character_id') or data.get('player_id')
            player_name = data.get('character_name', 'Игрок')

            if player_id in self.other_players:
                del self.other_players[player_id]
                self.add_chat_message(f"[СИСТЕМА] 👋 {player_name} покинул мир")

        elif msg_type == 'world_joined':
            self.in_world = True
            self.game_state = GameState.IN_GAME
            self.world_data = data.get('world_info', {})

            players = data.get('players', [])
            self.other_players.clear()

            for player in players:
                player_id = player.get('id')
                if player_id:
                    self.other_players[player_id] = {
                        'id': player_id,
                        'name': player.get('name', 'Игрок'),
                        'position': player.get('position', {'x': 0, 'y': 0, 'z': 0}),
                        'timestamp': time.time()
                    }

            self.add_chat_message("[СИСТЕМА] ✅ Вы вошли в игровой мир (UDP)!")
            self.update_join_world_button()

        elif msg_type == 'world_leave':
            self.in_world = False
            self.add_chat_message("[СИСТЕМА] Вы вышли из игрового мира")
            self.update_join_world_button()

        elif msg_type == 'chat_message':
            sender = data.get('character_name', 'Неизвестно')
            text = data.get('text', '')
            self.add_chat_message(f"{sender}: {text}")

        elif msg_type == 'error':
            error_msg = data.get('message', 'Ошибка')
            self.add_chat_message(f"[ОШИБКА] {error_msg}")

        elif msg_type == 'pong':
            pass

    # Остальные методы рендеринга остаются без изменений
    def render(self):
        self.screen.fill(self.colors['background'])

        if self.game_state == GameState.MENU:
            self.render_menu()
        elif self.game_state == GameState.IN_GAME:
            self.render_game()

        self.render_side_panel()

        if self.chat_active:
            self.render_chat_input()
        elif len(self.chat_messages) > 0 and (self.in_world or self.connected):
            self.render_chat_history()

        self.render_top_panel()
        pygame.display.flip()

    def render_menu(self):
        menu_width = self.width - self.side_panel_width
        title = self.fonts['title'].render("DPP2 UDP КЛИЕНТ", True, self.colors['udp_indicator'])
        title_rect = title.get_rect(center=(menu_width // 2, self.height // 3))
        self.screen.blit(title, title_rect)

    def render_side_panel(self):
        side_panel_x = self.width - self.side_panel_width
        pygame.draw.rect(self.screen, self.colors['panel'],
                         (side_panel_x, 0, self.side_panel_width, self.height))

        panel_title = self.fonts['large'].render("UDP УПРАВЛЕНИЕ", True, self.colors['udp_indicator'])
        self.screen.blit(panel_title, (side_panel_x + 20, 30))

        for field in self.input_fields:
            if not field.get('visible', True):
                continue

            label = self.fonts['small'].render(field['label'], True, self.colors['text'])
            self.screen.blit(label, (field['rect'].x, field['rect'].y - 22))

            bg_color = self.colors['input_active'] if field['active'] else self.colors['input_bg']
            pygame.draw.rect(self.screen, bg_color, field['rect'], border_radius=4)
            pygame.draw.rect(self.screen, (255, 255, 255) if field['active'] else (100, 100, 120),
                             field['rect'], 2, border_radius=4)

            text_surface = self.fonts['medium'].render(field['text'], True, self.colors['text'])
            text_rect = text_surface.get_rect(
                midleft=(field['rect'].x + 10, field['rect'].y + field['rect'].height // 2))

            if text_rect.width > field['rect'].width - 20:
                display_text = field['text']
                while len(display_text) > 1 and text_rect.width > field['rect'].width - 25:
                    display_text = display_text[1:]
                    text_surface = self.fonts['medium'].render(display_text, True, self.colors['text'])
                    text_rect = text_surface.get_rect(
                        midleft=(field['rect'].x + 10, field['rect'].y + field['rect'].height // 2))

                if len(display_text) < len(field['text']):
                    display_text = "..." + display_text[3:] if len(display_text) > 3 else "..."
                    text_surface = self.fonts['medium'].render(display_text, True, self.colors['text'])

            self.screen.blit(text_surface, text_rect)

            if field['active'] and int(time.time() * 2) % 2 == 0:
                cursor_x = text_rect.right + 2 if text_rect.width > 0 else field['rect'].x + 10
                cursor_rect = pygame.Rect(cursor_x, field['rect'].y + 8, 2, field['rect'].height - 16)
                pygame.draw.rect(self.screen, (255, 255, 255), cursor_rect)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.menu_buttons:
            hover = button['rect'].collidepoint(mouse_pos)

            if not button.get('enabled', True):
                color = self.colors['button_disabled']
                text_color = (150, 150, 150)
            elif hover:
                color = self.colors['button_hover']
                text_color = self.colors['text_light']
            else:
                color = self.colors['button']
                text_color = self.colors['text']

            if button['id'] == 'connect' and button.get('enabled', True):
                if hover:
                    color = (100, 150, 255)
                else:
                    color = (80, 130, 240)

            pygame.draw.rect(self.screen, color, button['rect'], border_radius=6)
            pygame.draw.rect(self.screen, (255, 255, 255) if button.get('enabled', True) else (100, 100, 100),
                             button['rect'], 2, border_radius=6)

            text = self.fonts['medium'].render(button['text'], True, text_color)
            text_rect = text.get_rect(center=button['rect'].center)
            self.screen.blit(text, text_rect)

    def render_top_panel(self):
        pygame.draw.rect(self.screen, self.colors['panel_dark'],
                         (0, 0, self.width, self.top_panel_height))

        status_text = "✅ UDP ПОДКЛЮЧЕНО" if self.connected else "❌ UDP ОТКЛЮЧЕНО"
        status_color = self.colors['status_connected'] if self.connected else self.colors['status_disconnected']
        status = self.fonts['medium'].render(status_text, True, status_color)
        self.screen.blit(status, (20, 20))

        if self.username:
            user_text = self.fonts['small'].render(f"Пользователь: {self.username}", True, (200, 200, 255))
            self.screen.blit(user_text, (220, 22))

        if self.character:
            char_text = self.fonts['small'].render(f"Персонаж: {self.character['name']}", True, (200, 255, 200))
            self.screen.blit(char_text, (400, 22))

        stats_x = self.width - 350
        fps_text = self.fonts['small'].render(f"FPS: {self.stats['fps']}", True, (200, 200, 200))
        self.screen.blit(fps_text, (stats_x, 22))

        players_text = self.fonts['small'].render(f"Игроков: {self.stats['players_online']}", True, (200, 200, 200))
        self.screen.blit(players_text, (stats_x + 80, 22))

        udp_stats = self.fonts['small'].render(
            f"UDP: ↑{self.stats['udp_packets_sent']} ↓{self.stats['udp_packets_received']}",
            True, self.colors['udp_indicator']
        )
        self.screen.blit(udp_stats, (stats_x + 170, 22))

    def render_chat_history(self):
        max_messages = 5
        start_y = self.height - 130

        for i, message in enumerate(self.chat_messages[-max_messages:]):
            if message.startswith("[СИСТЕМА]"):
                if "✅" in message:
                    color = self.colors['success']
                elif "❌" in message or "[ОШИБКА]" in message:
                    color = self.colors['error']
                else:
                    color = self.colors['udp_indicator']
            elif message.startswith("Вы:"):
                color = (200, 200, 255)
            else:
                color = (255, 255, 255)

            text = self.fonts['small'].render(message, True, color)
            text_bg = pygame.Rect(10, start_y + i * 20 - 2, text.get_width() + 10, text.get_height() + 4)
            bg_surface = pygame.Surface((text_bg.width, text_bg.height), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 150))
            self.screen.blit(bg_surface, text_bg)
            self.screen.blit(text, (15, start_y + i * 20))

    def render_game(self):
        game_width = self.width - self.side_panel_width
        pygame.draw.rect(self.screen, (20, 20, 30),
                         (0, self.top_panel_height, game_width, self.height - self.top_panel_height))

        grid_color = self.colors['grid']
        grid_step = int(self.grid_size * self.camera_zoom)
        start_x = -self.camera_offset[0] % grid_step
        start_y = -self.camera_offset[1] % grid_step

        for x in range(int(start_x), game_width, grid_step):
            pygame.draw.line(self.screen, grid_color,
                             (x, self.top_panel_height),
                             (x, self.height), 1)
        for y in range(int(start_y), self.height, grid_step):
            pygame.draw.line(self.screen, grid_color,
                             (0, y),
                             (game_width, y), 1)

        center_x = self.camera_offset[0]
        center_y = self.camera_offset[1] + self.top_panel_height // 2

        if self.character:
            player_pos = self.character.get('position', {'x': 0, 'y': 0, 'z': 0})
            player_screen_x = int(player_pos['x'] * 100 * self.camera_zoom + center_x)
            player_screen_y = int(player_pos['y'] * 100 * self.camera_zoom + center_y)

            if (0 <= player_screen_x <= game_width and
                    self.top_panel_height <= player_screen_y <= self.height):
                player_radius = int(20 * self.camera_zoom)
                pygame.draw.circle(self.screen, self.colors['player'],
                                   (player_screen_x, player_screen_y), player_radius)
                inner_radius = int(player_radius * 0.7)
                pygame.draw.circle(self.screen, (120, 170, 255),
                                   (player_screen_x, player_screen_y), inner_radius)
                pygame.draw.circle(self.screen, (255, 255, 255),
                                   (player_screen_x, player_screen_y), player_radius, 2)

                name = self.fonts['small'].render(self.character['name'], True, (255, 255, 255))
                name_rect = name.get_rect(center=(player_screen_x, player_screen_y - player_radius - 10))
                self.screen.blit(name, name_rect)

        for player_id, player_data in self.other_players.items():
            pos = player_data.get('position', {'x': 0, 'y': 0, 'z': 0})
            screen_x = int(pos['x'] * 100 * self.camera_zoom + center_x)
            screen_y = int(pos['y'] * 100 * self.camera_zoom + center_y)

            if (0 <= screen_x <= game_width and
                    self.top_panel_height <= screen_y <= self.height):
                player_radius = int(15 * self.camera_zoom)
                pygame.draw.circle(self.screen, self.colors['other_player'],
                                   (screen_x, screen_y), player_radius)
                pygame.draw.circle(self.screen, (255, 200, 200),
                                   (screen_x, screen_y), player_radius, 1)

                name = self.fonts['small'].render(player_data['name'], True, (255, 200, 200))
                name_rect = name.get_rect(center=(screen_x, screen_y - player_radius - 8))
                self.screen.blit(name, name_rect)

        if self.world_data:
            world_name = self.world_data.get('name', 'Неизвестный мир')
            world_text = self.fonts['small'].render(f"Мир: {world_name} (UDP)", True, self.colors['udp_indicator'])
            self.screen.blit(world_text, (10, self.top_panel_height + 10))

    def render_chat_input(self):
        chat_bg = pygame.Surface((self.width - self.side_panel_width - 20, 40), pygame.SRCALPHA)
        chat_bg.fill((40, 40, 50, 220))
        self.screen.blit(chat_bg, (10, self.height - 50))

        chat_label = self.fonts['small'].render("Чат (UDP):", True, self.colors['udp_indicator'])
        self.screen.blit(chat_label, (15, self.height - 45))

        input_text = self.fonts['medium'].render(self.chat_input, True, (255, 255, 255))
        self.screen.blit(input_text, (80, self.height - 45))

        if int(time.time() * 2) % 2 == 0:
            cursor_x = 80 + input_text.get_width() + 2
            cursor_rect = pygame.Rect(cursor_x, self.height - 45, 2, 25)
            pygame.draw.rect(self.screen, (255, 255, 255), cursor_rect)

    def connect_to_server(self):
        """Подключение к UDP серверу"""
        if self.connection_in_progress:
            return

        host_field = next(f for f in self.input_fields if f['name'] == 'server_host')
        port_field = next(f for f in self.input_fields if f['name'] == 'server_port')

        host = host_field['text']
        port = port_field['text']

        self.connection_in_progress = True
        self.add_chat_message(f"[СИСТЕМА] 🔄 Подключение к UDP серверу {host}:{port}...")

        try:
            if self.network and self.network.is_connected():
                self.network.disconnect()
                time.sleep(0.1)

            from network_client import NetworkClient
            self.network = NetworkClient(host, int(port))

            # Передаем client_id в network клиент
            self.network.client_id = self.client_id

            if self.network.connect():
                self.connected = True
                self.add_chat_message(f"[СИСТЕМА] ✅ Успешно подключено через UDP к {host}:{port}")

                # Отправляем инициализацию с client_id
                init_data = {
                    'type': 'client_init',
                    'client_id': self.client_id,
                    'timestamp': datetime.now().isoformat()
                }
                self.network.safe_send(init_data)

                self.start_network_thread()
                self.show_login_field()
            else:
                self.connected = False
                self.add_chat_message(f"[ОШИБКА] ❌ Не удалось подключиться к UDP серверу")

        except ValueError:
            self.add_chat_message("[ОШИБКА] ❌ Неверный номер порта")
        except Exception as e:
            self.add_chat_message(f"[ОШИБКА] ❌ {str(e)}")
        finally:
            self.connection_in_progress = False

    def show_login_field(self):
        for field in self.input_fields:
            if field['name'] == 'username':
                field['visible'] = True
                field['active'] = True
                self.active_input_field = self.input_fields.index(field)
                break

    def login(self):
        username_field = next(f for f in self.input_fields if f['name'] == 'username')
        self.username = username_field['text'].strip()

        if not self.username:
            self.add_chat_message("[ОШИБКА] ❌ Введите имя пользователя")
            return

        if not self.connected:
            self.add_chat_message("[ОШИБКА] ❌ Нет подключения к UDP серверу")
            return

        self.add_chat_message(f"[СИСТЕМА] 🔐 Авторизация как {self.username}...")

        data = {
            'type': 'auth',
            'client_id': self.client_id,  # Добавляем client_id
            'username': self.username,
            'timestamp': datetime.now().isoformat()
        }

        self.network.safe_send(data)

    def select_character(self):
        if not self.username:
            self.add_chat_message("[ОШИБКА] ❌ Сначала войдите в систему")
            return

        self.add_chat_message("[СИСТЕМА] 🎮 Выбор персонажа...")

        from character_manager import CharacterManager
        cm = CharacterManager()
        characters = cm.load_characters(self.username)

        if not characters:
            character_name = f"{self.username}_персонаж"
            self.character = cm.create_default_character(character_name, self.username)
            cm.save_character(self.character)
            self.add_chat_message(f"[СИСТЕМА] ✅ Создан персонаж: {character_name}")
        else:
            self.character = characters[0]
            self.add_chat_message(f"[СИСТЕМА] ✅ Выбран персонаж: {self.character['name']}")

        if self.connected and self.character:
            data = {
                'type': 'character_select',
                'client_id': self.client_id,  # Добавляем client_id
                'character_id': self.character['id'],
                'character_data': self.character,
                'timestamp': datetime.now().isoformat()
            }
            self.network.safe_send(data)

        self.character_selected = True
        self.game_state = GameState.IN_GAME
        self.update_join_world_button()
        self.add_chat_message("[СИСТЕМА] ✅ Персонаж готов. Нажмите 'Войти в игровой мир'")

    def join_world(self):
        if not self.character:
            self.add_chat_message("[ОШИБКА] ❌ Сначала выберите персонажа")
            return

        if not self.connected:
            self.add_chat_message("[ОШИБКА] ❌ Нет подключения к UDP серверу")
            return

        if self.in_world:
            self.add_chat_message("[ОШИБКА] ❌ Вы уже в игровом мире")
            return

        self.add_chat_message(f"[СИСТЕМА] 🌍 Входим в мир с {self.character['name']}...")

        data = {
            'type': 'join_world',
            'client_id': self.client_id,  # Добавляем client_id
            'character_id': self.character['id'],
            'character_name': self.character['name'],
            'character_data': self.character,
            'timestamp': datetime.now().isoformat()
        }

        self.network.safe_send(data)

    def quit_game(self):
        if self.in_world and self.connected and self.character:
            try:
                data = {
                    'type': 'leave_world',
                    'client_id': self.client_id,  # Добавляем client_id
                    'character_id': self.character['id'],
                    'character_name': self.character['name'],
                    'timestamp': datetime.now().isoformat()
                }
                self.network.safe_send(data)
            except:
                pass

        self.running = False