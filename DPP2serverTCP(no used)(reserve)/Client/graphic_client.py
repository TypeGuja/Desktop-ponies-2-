#!/usr/bin/env python3
"""
DPP2 Graphic Client - Графический интерфейс с WASD управлением
"""

import pygame
import sys
import threading
import time
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
    """Основной графический клиент"""

    def __init__(self):
        pygame.init()

        # Настройки окна
        self.width = 1200
        self.height = 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("DPP2 Графический Клиент")

        # Игровые состояния
        self.game_state = GameState.MENU
        self.running = True
        self.clock = pygame.time.Clock()
        self.fps = 60

        # Сетевое подключение
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
        self.character_selected = False  # Флаг выбора персонажа

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
            'warning': (255, 200, 100)
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
        self.position_update_rate = 0.016 #0.1
        self.last_position_update = 0

        # Статистика
        self.stats = {
            'fps': 0,
            'players_online': 0,
            'ping': 0
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
        # Боковая панель
        side_panel_x = self.width - self.side_panel_width

        # Поля ввода (располагаем на боковой панели)
        self.input_fields = [
            {
                'name': 'server_host',
                'label': 'Адрес сервера:',
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

        # Кнопки (располагаем на боковой панели)
        button_y_start = 320
        button_height = 45
        button_spacing = 60

        self.menu_buttons = [
            {
                'id': 'connect',
                'text': '📡 Подключиться к серверу',
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
        """Запуск сетевого потока"""
        if self.network_thread and self.network_thread.is_alive():
            self.stop_network_thread = True
            self.network_thread.join(timeout=1.0)

        self.stop_network_thread = False
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.network_thread.start()

    def network_loop(self):
        """Сетевой цикл - НЕБЛОКИРУЮЩАЯ ВЕРСИЯ"""
        while self.running and not self.stop_network_thread:
            try:
                if self.network.is_connected():
                    # Неблокирующее получение данных
                    data = self.network.receive()
                    if data:
                        # Помещаем данные в очередь для обработки в главном потоке
                        self.network_queue.put(data)
                else:
                    # Если соединение потеряно, небольшая пауза
                    time.sleep(0.1)
            except Exception as e:
                print(f"⚠️ Ошибка в сетевом потоке: {e}")
                time.sleep(0.5)

    def process_network_messages(self):
        """Обработка сообщений из очереди (вызывается в главном цикле)"""
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

            # Обработка сетевых сообщений в главном потоке
            self.process_network_messages()

            self.update()
            self.render()
            self.clock.tick(self.fps)
            self.stats['fps'] = int(self.clock.get_fps())

        # Корректное завершение
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
        """Обработка нажатия клавиш"""
        # Управление WASD
        if event.key in self.keys:
            self.keys[event.key] = True

        # Enter для чата или подтверждения ввода
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

        # Escape для выхода из чата или поля ввода
        elif event.key == pygame.K_ESCAPE:
            if self.chat_active:
                self.chat_active = False
                self.chat_input = ""
            elif self.active_input_field is not None:
                self.active_input_field = None
                for field in self.input_fields:
                    field['active'] = False

        # Backspace в чате или поле ввода
        elif event.key == pygame.K_BACKSPACE:
            if self.chat_active:
                self.chat_input = self.chat_input[:-1]
            elif self.active_input_field is not None:
                field = self.input_fields[self.active_input_field]
                if len(field['text']) > 0:
                    field['text'] = field['text'][:-1]

        # Tab для переключения полей ввода
        elif event.key == pygame.K_TAB:
            self.switch_input_field()

        # Увеличение/уменьшение масштаба
        elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
            self.camera_zoom = min(self.camera_zoom * 1.1, 3.0)
        elif event.key == pygame.K_MINUS:
            self.camera_zoom = max(self.camera_zoom * 0.9, 0.5)

    def handle_keyup(self, event):
        """Обработка отпускания клавиш"""
        if event.key in self.keys:
            self.keys[event.key] = False

    def handle_mouse_click(self, event):
        """Обработка кликов мыши"""
        mouse_pos = pygame.mouse.get_pos()

        # Сброс активного поля ввода при клике вне полей
        field_clicked = False

        # Проверка кликов по полям ввода
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

        # Клики по кнопкам
        if event.button == 1:  # Левая кнопка мыши
            for button in self.menu_buttons:
                if button['rect'].collidepoint(mouse_pos) and button.get('enabled', True):
                    button['action']()

        # Колесико мыши для зума
        elif event.button == 4:  # Вверх
            self.camera_zoom = min(self.camera_zoom * 1.1, 3.0)
        elif event.button == 5:  # Вниз
            self.camera_zoom = max(self.camera_zoom * 0.9, 0.5)

    def handle_text_input(self, text):
        """Обработка текстового ввода"""
        if self.chat_active:
            if len(self.chat_input) < 100:  # Ограничение длины чата
                self.chat_input += text
        elif self.active_input_field is not None:
            field = self.input_fields[self.active_input_field]
            if len(field['text']) < field.get('max_length', 50):
                if text not in ['\t', '\r', '\n']:
                    field['text'] += text

    def switch_input_field(self):
        """Переключение между полями ввода"""
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

        # Обновление позиции игрока
        if self.in_world and self.character and not self.chat_active:
            self.update_player_position(delta_time)

        # Обновление статуса подключения
        self.update_connection_status()

        # Обновление статистики
        self.stats['players_online'] = len(self.other_players) + (1 if self.character else 0)

        # Автоматически обновляем статус кнопки "Войти в мир"
        self.update_join_world_button()

        self.last_update = current_time

    def update_player_position(self, delta_time):
        """Обновление позиции игрока по WASD"""
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

            # Сохраняем позицию в файл
            from character_manager import CharacterManager
            cm = CharacterManager()

            # ОБНОВЛЯЕМ ПОЗИЦИЮ В СУЩЕСТВУЮЩЕМ ХАРАКТЕРЕ
            self.character['position'] = pos
            cm.save_character(self.character)

            # Отправляем на сервер с троттлингом
            current_time = time.time()
            if current_time - self.last_position_update >= self.position_update_rate:
                self.send_position_update(pos)
                self.last_position_update = current_time

    def update_connection_status(self):
        """Обновление статуса подключения"""
        self.connected = self.network.is_connected()

        for button in self.menu_buttons:
            if button['id'] == 'login':
                button['enabled'] = self.connected
            elif button['id'] == 'character':
                button['enabled'] = bool(self.username)

    def update_join_world_button(self):
        """Обновление состояния кнопки 'Войти в мир'"""
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
        """Отправка обновления позиции на сервер"""
        if not self.connected or not self.character:
            return

        data = {
            'type': 'position_update',
            'character_id': self.character['id'],
            'character_name': self.character['name'],
            'position': position,
            'timestamp': datetime.now().isoformat()
        }

        self.network.send(data)

    def send_chat_message(self):
        """Отправка сообщения в чат"""
        if not self.chat_input.strip() or not self.connected:
            return

        data = {
            'type': 'chat_message',
            'character_id': self.character['id'] if self.character else None,
            'character_name': self.character['name'] if self.character else self.username,
            'text': self.chat_input,
            'timestamp': datetime.now().isoformat()
        }

        self.network.send(data)
        self.add_chat_message(f"Вы: {self.chat_input}")

    def add_chat_message(self, message):
        """Добавление сообщения в чат"""
        self.chat_messages.append(message)
        if len(self.chat_messages) > 10:
            self.chat_messages.pop(0)

    def handle_server_message(self, data):
        """Обработка сообщений от сервера"""
        msg_type = data.get('type')

        if msg_type == 'welcome':
            self.add_chat_message("[СИСТЕМА] ✅ Подключено к серверу")

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

        elif msg_type == 'chat_message':
            sender = data.get('character_name', 'Неизвестно')
            text = data.get('text', '')
            self.add_chat_message(f"{sender}: {text}")

        elif msg_type == 'position_update':
            player_id = data.get('character_id')
            if player_id != self.character.get('id') if self.character else True:
                self.other_players[player_id] = {
                    'name': data.get('character_name', 'Игрок'),
                    'position': data.get('position', {'x': 0, 'y': 0, 'z': 0}),
                    'timestamp': time.time()
                }

        elif msg_type == 'player_joined':
            player_id = data.get('player_id')
            player_name = data.get('player_name', 'Игрок')
            self.other_players[player_id] = {
                'name': player_name,
                'position': data.get('position', {'x': 0, 'y': 0, 'z': 0}),
                'timestamp': time.time()
            }
            self.add_chat_message(f"[СИСТЕМА] 👤 {player_name} присоединился")

        elif msg_type == 'player_left':
            player_id = data.get('player_id')
            player_name = data.get('player_name', 'Игрок')
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
                if 'id' in player:
                    self.other_players[player['id']] = player
            self.add_chat_message("[СИСТЕМА] ✅ Вы вошли в игровой мир!")
            self.update_join_world_button()

        elif msg_type == 'world_leave':
            self.in_world = False
            self.add_chat_message("[СИСТЕМА] Вы вышли из игрового мира")
            self.update_join_world_button()

        elif msg_type == 'error':
            error_msg = data.get('message', 'Ошибка')
            self.add_chat_message(f"[ОШИБКА] {error_msg}")

    def render(self):
        """Отрисовка игры"""
        # Фон
        self.screen.fill(self.colors['background'])

        # Рендер в зависимости от состояния
        if self.game_state == GameState.MENU:
            self.render_menu()  # <-- ИСПРАВЛЕНО: render_menu()
        elif self.game_state == GameState.IN_GAME:
            self.render_game()

        # Всегда отрисовываем боковую панель
        self.render_side_panel()

        # Чат если активен
        if self.chat_active:
            self.render_chat_input()
        elif len(self.chat_messages) > 0 and (self.in_world or self.connected):
            self.render_chat_history()

        # Верхняя панель
        self.render_top_panel()

        pygame.display.flip()

    def render_menu(self):
        """Отрисовка главного меню (если отсутствует)"""
        # Простой фон меню
        menu_width = self.width - self.side_panel_width

        # Заголовок
        title = self.fonts['title'].render("DPP2 ГРАФИЧЕСКИЙ КЛИЕНТ", True, (255, 255, 255))
        title_rect = title.get_rect(center=(menu_width // 2, self.height // 3))
        self.screen.blit(title, title_rect)

        # Подзаголовок
        subtitle = self.fonts['medium'].render("Управление персонажем в реальном времени", True, (200, 200, 220))
        subtitle_rect = subtitle.get_rect(center=(menu_width // 2, title_rect.bottom + 30))
        self.screen.blit(subtitle, subtitle_rect)

        # Инструкция
        instructions = [
            "УПРАВЛЕНИЕ:",
            "1. Подключитесь к серверу (кнопка справа)",
            "2. Введите имя пользователя",
            "3. Выберите персонажа",
            "4. Войдите в игровой мир",
            "",
            "WASD/Стрелки - Движение",
            "Пробел/Shift - Вверх/Вниз",
            "Enter - Чат",
            "+/- - Масштаб"
        ]

        y = subtitle_rect.bottom + 50
        for i, line in enumerate(instructions):
            color = (255, 255, 200) if i == 0 else (180, 180, 220)
            text = self.fonts['small'].render(line, True, color)
            text_rect = text.get_rect(center=(menu_width // 2, y + i * 25))
            self.screen.blit(text, text_rect)

    def render_side_panel(self):
            """Отрисовка боковой панели управления"""
            side_panel_x = self.width - self.side_panel_width

            # Фон боковой панели
            pygame.draw.rect(self.screen, self.colors['panel'],
                             (side_panel_x, 0, self.side_panel_width, self.height))

            # Заголовок панели
            panel_title = self.fonts['large'].render("УПРАВЛЕНИЕ", True, self.colors['text_light'])
            self.screen.blit(panel_title, (side_panel_x + 20, 30))

            # Разделитель
            pygame.draw.line(self.screen, (80, 80, 100),
                             (side_panel_x + 20, 70),
                             (side_panel_x + self.side_panel_width - 20, 70), 2)

            # Поля ввода
            for field in self.input_fields:
                if not field.get('visible', True):
                    continue

                # Метка поля
                label = self.fonts['small'].render(field['label'], True, self.colors['text'])
                self.screen.blit(label, (field['rect'].x, field['rect'].y - 22))

                # Фон поля ввода
                bg_color = self.colors['input_active'] if field['active'] else self.colors['input_bg']
                pygame.draw.rect(self.screen, bg_color, field['rect'], border_radius=4)
                pygame.draw.rect(self.screen, (255, 255, 255) if field['active'] else (100, 100, 120),
                                 field['rect'], 2, border_radius=4)

                # Текст поля
                text_surface = self.fonts['medium'].render(field['text'], True, self.colors['text'])
                text_rect = text_surface.get_rect(
                    midleft=(field['rect'].x + 10, field['rect'].y + field['rect'].height // 2))

                # Обрезка текста если не помещается
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

                # Курсор
                if field['active'] and int(time.time() * 2) % 2 == 0:
                    cursor_x = text_rect.right + 2 if text_rect.width > 0 else field['rect'].x + 10
                    cursor_rect = pygame.Rect(cursor_x, field['rect'].y + 8, 2, field['rect'].height - 16)
                    pygame.draw.rect(self.screen, (255, 255, 255), cursor_rect)

            # Кнопки
            mouse_pos = pygame.mouse.get_pos()

            for button in self.menu_buttons:
                # Определение цвета кнопки
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

                # Отрисовка кнопки
                pygame.draw.rect(self.screen, color, button['rect'], border_radius=6)
                pygame.draw.rect(self.screen, (255, 255, 255) if button.get('enabled', True) else (100, 100, 100),
                                 button['rect'], 2, border_radius=6)

                # Текст кнопки
                text = self.fonts['medium'].render(button['text'], True, text_color)
                text_rect = text.get_rect(center=button['rect'].center)
                self.screen.blit(text, text_rect)

                # Подсказка для кнопки "Войти в мир"
                if button['id'] == 'join_world' and not button['enabled'] and hover:
                    tooltip_text = ""
                    if not self.connected:
                        tooltip_text = "Нет подключения к серверу"
                    elif not self.username:
                        tooltip_text = "Сначала войдите в систему"
                    elif not self.character:
                        tooltip_text = "Сначала выберите персонажа"
                    elif self.in_world:
                        tooltip_text = "Вы уже в игровом мире"

                    if tooltip_text:
                        tooltip = self.fonts['small'].render(tooltip_text, True, self.colors['warning'])
                        tooltip_rect = tooltip.get_rect(midtop=(button['rect'].centerx, button['rect'].bottom + 5))

                        # Фон подсказки
                        tooltip_bg = pygame.Rect(
                            tooltip_rect.x - 5, tooltip_rect.y - 2,
                            tooltip_rect.width + 10, tooltip_rect.height + 4
                        )
                        pygame.draw.rect(self.screen, (40, 40, 60), tooltip_bg, border_radius=3)
                        pygame.draw.rect(self.screen, self.colors['warning'], tooltip_bg, 1, border_radius=3)

                        self.screen.blit(tooltip, tooltip_rect)

    def render_top_panel(self):
        """Отрисовка верхней панели статуса"""
        # Фон верхней панели
        pygame.draw.rect(self.screen, self.colors['panel_dark'],
                         (0, 0, self.width, self.top_panel_height))

        # Разделитель
        pygame.draw.line(self.screen, (60, 60, 80),
                         (0, self.top_panel_height),
                         (self.width, self.top_panel_height), 2)

        # Статус подключения
        status_text = "✅ ПОДКЛЮЧЕНО" if self.connected else "❌ НЕТ ПОДКЛЮЧЕНИЯ"
        status_color = self.colors['status_connected'] if self.connected else self.colors['status_disconnected']

        status = self.fonts['medium'].render(status_text, True, status_color)
        self.screen.blit(status, (20, 20))

        # Имя пользователя
        if self.username:
            user_text = self.fonts['small'].render(f"Пользователь: {self.username}", True, (200, 200, 255))
            self.screen.blit(user_text, (200, 22))

        # Персонаж
        if self.character:
            char_text = self.fonts['small'].render(f"Персонаж: {self.character['name']}", True, (200, 255, 200))
            self.screen.blit(char_text, (400, 22))

        # Статистика справа
        stats_x = self.width - 200

        # FPS
        fps_text = self.fonts['small'].render(f"FPS: {self.stats['fps']}", True, (200, 200, 200))
        self.screen.blit(fps_text, (stats_x, 22))

        # Игроки онлайн
        players_text = self.fonts['small'].render(f"Игроков: {self.stats['players_online']}", True, (200, 200, 200))
        self.screen.blit(players_text, (stats_x + 80, 22))

    def render_chat_history(self):
        """Отрисовка истории чата"""
        max_messages = 5
        start_y = self.height - 130

        for i, message in enumerate(self.chat_messages[-max_messages:]):
            # Определяем цвет сообщения
            if message.startswith("[СИСТЕМА]"):
                if "✅" in message:
                    color = self.colors['success']  # Зеленый для успеха
                elif "❌" in message or "[ОШИБКА]" in message:
                    color = self.colors['error']  # Красный для ошибок
                else:
                    color = (100, 200, 255)  # Голубой для системных
            elif message.startswith("Вы:"):
                color = (200, 200, 255)  # Светло-голубой для своих сообщений
            else:
                color = (255, 255, 255)  # Белый для остальных

            text = self.fonts['small'].render(message, True, color)

            # Полупрозрачный фон для сообщения
            text_bg = pygame.Rect(10, start_y + i * 20 - 2, text.get_width() + 10, text.get_height() + 4)
            bg_surface = pygame.Surface((text_bg.width, text_bg.height), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 150))
            self.screen.blit(bg_surface, text_bg)

            self.screen.blit(text, (15, start_y + i * 20))

    def render_game(self):
        """Отрисовка игрового мира"""
        game_width = self.width - self.side_panel_width

        # Фон игровой области
        pygame.draw.rect(self.screen, (20, 20, 30),
                         (0, self.top_panel_height, game_width, self.height - self.top_panel_height))

        # Сетка
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

        # Центральные оси
        center_x = self.camera_offset[0]
        center_y = self.camera_offset[1] + self.top_panel_height // 2

        if center_x > 0 and center_x < game_width:
            pygame.draw.line(self.screen, (255, 100, 100, 150),
                             (center_x, self.top_panel_height),
                             (center_x, self.height), 2)
        if center_y > self.top_panel_height and center_y < self.height:
            pygame.draw.line(self.screen, (100, 255, 100, 150),
                             (0, center_y),
                             (game_width, center_y), 2)

        # Отрисовка игроков
        if self.character:
            # Собственный персонаж
            player_pos = self.character.get('position', {'x': 0, 'y': 0, 'z': 0})
            player_screen_x = int(player_pos['x'] * 100 * self.camera_zoom + center_x)
            player_screen_y = int(player_pos['y'] * 100 * self.camera_zoom + center_y)

            # Проверяем, что персонаж в пределах экрана
            if (0 <= player_screen_x <= game_width and
                    self.top_panel_height <= player_screen_y <= self.height):
                # Игрок (синий кружок с градиентом)
                player_radius = int(20 * self.camera_zoom)

                # Внешний круг
                pygame.draw.circle(self.screen, self.colors['player'],
                                   (player_screen_x, player_screen_y), player_radius)

                # Внутренний круг (градиент)
                inner_radius = int(player_radius * 0.7)
                pygame.draw.circle(self.screen, (120, 170, 255),
                                   (player_screen_x, player_screen_y), inner_radius)

                # Контур
                pygame.draw.circle(self.screen, (255, 255, 255),
                                   (player_screen_x, player_screen_y), player_radius, 2)

                # Имя игрока
                name = self.fonts['small'].render(self.character['name'], True, (255, 255, 255))
                name_rect = name.get_rect(center=(player_screen_x, player_screen_y - player_radius - 10))
                self.screen.blit(name, name_rect)

                # Маркер направления
                import math
                angle = math.radians(self.character.get('rotation', {'y': 0}).get('y', 0))
                dir_x = player_screen_x + math.sin(angle) * player_radius * 0.8
                dir_y = player_screen_y - math.cos(angle) * player_radius * 0.8
                pygame.draw.circle(self.screen, (255, 255, 200), (int(dir_x), int(dir_y)), 4)

        # Другие игроки
        for player_id, player_data in self.other_players.items():
            pos = player_data.get('position', {'x': 0, 'y': 0, 'z': 0})
            screen_x = int(pos['x'] * 100 * self.camera_zoom + center_x)
            screen_y = int(pos['y'] * 100 * self.camera_zoom + center_y)

            # Проверяем, что игрок в пределах экрана
            if (0 <= screen_x <= game_width and
                    self.top_panel_height <= screen_y <= self.height):
                # Игрок (красный кружок)
                player_radius = int(15 * self.camera_zoom)
                pygame.draw.circle(self.screen, self.colors['other_player'],
                                   (screen_x, screen_y), player_radius)

                # Контур
                pygame.draw.circle(self.screen, (255, 200, 200),
                                   (screen_x, screen_y), player_radius, 1)

                # Имя игрока
                name = self.fonts['small'].render(player_data['name'], True, (255, 200, 200))
                name_rect = name.get_rect(center=(screen_x, screen_y - player_radius - 8))
                self.screen.blit(name, name_rect)

        # Информация о мире в углу
        if self.world_data:
            world_name = self.world_data.get('name', 'Неизвестный мир')
            world_text = self.fonts['small'].render(f"Мир: {world_name}", True, (200, 200, 255))
            self.screen.blit(world_text, (10, self.top_panel_height + 10))

        # Инструкция по управлению в игре
        if self.in_world:
            controls = [
                "Управление в мире:",
                "WASD/Стрелки - Движение",
                "Пробел/Shift - Вверх/Вниз",
                "Enter - Открыть чат",
                "Esc - Закрыть чат",
                "+/- - Масштаб"
            ]

            for i, control in enumerate(controls):
                color = (220, 220, 255) if i == 0 else (180, 180, 220)
                control_text = self.fonts['small'].render(control, True, color)
                self.screen.blit(control_text, (10, self.top_panel_height + 40 + i * 20))

    def connect_to_server(self):
        """Подключение к серверу - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        if self.connection_in_progress:
            return

        host_field = next(f for f in self.input_fields if f['name'] == 'server_host')
        port_field = next(f for f in self.input_fields if f['name'] == 'server_port')

        host = host_field['text']
        port = port_field['text']

        self.connection_in_progress = True
        self.add_chat_message(f"[СИСТЕМА] 🔄 Подключение к {host}:{port}...")

        try:
            # Отключаем предыдущее соединение если есть
            if self.network and self.network.is_connected():
                self.network.disconnect()
                time.sleep(0.1)

            # Создаем новый клиент
            from network_client import NetworkClient
            self.network = NetworkClient(host, int(port))

            # Подключаемся (синхронно, но с таймаутом)
            if self.network.connect():
                self.connected = True
                self.add_chat_message(f"[СИСТЕМА] ✅ Успешно подключено к {host}:{port}")

                # Запускаем сетевой поток
                self.start_network_thread()

                # Показываем поле для входа
                self.show_login_field()
            else:
                self.connected = False
                self.add_chat_message(f"[ОШИБКА] ❌ Не удалось подключиться к серверу")

        except ValueError:
            self.add_chat_message("[ОШИБКА] ❌ Неверный номер порта")
        except Exception as e:
            self.add_chat_message(f"[ОШИБКА] ❌ {str(e)}")
        finally:
            self.connection_in_progress = False

    def show_login_field(self):
        """Показать поле для входа"""
        for field in self.input_fields:
            if field['name'] == 'username':
                field['visible'] = True
                field['active'] = True
                self.active_input_field = self.input_fields.index(field)
                break

    def login(self):
        """Вход в систему"""
        username_field = next(f for f in self.input_fields if f['name'] == 'username')
        self.username = username_field['text'].strip()

        if not self.username:
            self.add_chat_message("[ОШИБКА] ❌ Введите имя пользователя")
            return

        if not self.connected:
            self.add_chat_message("[ОШИБКА] ❌ Нет подключения к серверу")
            return

        self.add_chat_message(f"[СИСТЕМА] 🔐 Авторизация как {self.username}...")

        data = {
            'type': 'auth',
            'username': self.username,
            'timestamp': datetime.now().isoformat()
        }

        self.network.send(data)

    def select_character(self):
        """Выбор персонажа"""
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
                'character_id': self.character['id'],
                'character_data': self.character,
                'timestamp': datetime.now().isoformat()
            }
            self.network.send(data)

        self.character_selected = True
        self.game_state = GameState.IN_GAME
        self.update_join_world_button()
        self.add_chat_message("[СИСТЕМА] ✅ Персонаж готов. Нажмите 'Войти в игровой мир'")

    def join_world(self):
        """Войти в игровой мир"""
        if not self.character:
            self.add_chat_message("[ОШИБКА] ❌ Сначала выберите персонажа")
            return

        if not self.connected:
            self.add_chat_message("[ОШИБКА] ❌ Нет подключения к серверу")
            return

        if self.in_world:
            self.add_chat_message("[ОШИБКА] ❌ Вы уже в игровом мире")
            return

        self.add_chat_message(f"[СИСТЕМА] 🌍 Входим в мир с {self.character['name']}...")

        data = {
            'type': 'join_world',
            'character_id': self.character['id'],
            'character_name': self.character['name'],
            'character_data': self.character,
            'timestamp': datetime.now().isoformat()
        }

        self.network.send(data)

    def quit_game(self):
        """Выход из игры"""
        if self.in_world and self.connected and self.character:
            try:
                data = {
                    'type': 'leave_world',
                    'character_id': self.character['id'],
                    'character_name': self.character['name'],
                    'timestamp': datetime.now().isoformat()
                }
                self.network.send(data)
            except:
                pass

        self.running = False