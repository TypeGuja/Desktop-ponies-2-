#!/usr/bin/env python3
"""
DPP2 Graphic Client - Графический интерфейс с камерой следящей за персонажем
"""

import pygame
import sys
import threading
import time
import uuid
import math
import queue
from enum import Enum
from datetime import datetime

# Импорты
from animated_character import AnimatedCharacter, CharacterSelector


class GameState(Enum):
    """Состояния игры"""
    MENU = 1
    CONNECTING = 2
    CHARACTER_SELECT = 3
    IN_GAME = 4
    CHAT = 5
    ESC_MENU = 6
    SETTINGS_MENU = 7


class Camera:
    """Камера, следящая за персонажем"""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.offset = [width // 2, height // 2]
        self.target_offset = [width // 2, height // 2]
        self.zoom = 1.2
        self.target_zoom = 1.2
        self.follow_speed = 0.15
        self.zoom_speed = 0.1
        self.smoothing = True
        self.follow_player = True
        self.grid_size = 50

    def update(self, player_position=None, delta_time=1.0):
        """Обновление позиции камеры"""
        if player_position and self.follow_player:
            # Целевая позиция камеры (центр на игроке)
            target_x = self.width // 2 - player_position['x'] * 100 * self.zoom
            target_y = self.height // 2 - player_position['y'] * 100 * self.zoom

            if self.smoothing:
                # Плавное следование
                self.target_offset[0] += (target_x - self.target_offset[0]) * self.follow_speed * delta_time * 60
                self.target_offset[1] += (target_y - self.target_offset[1]) * self.follow_speed * delta_time * 60

                # Интерполяция текущей позиции к целевой
                self.offset[0] += (self.target_offset[0] - self.offset[0]) * self.follow_speed * delta_time * 60
                self.offset[1] += (self.target_offset[1] - self.offset[1]) * self.follow_speed * delta_time * 60
            else:
                # Мгновенное следование
                self.offset[0] = target_x
                self.offset[1] = target_y
                self.target_offset[0] = target_x
                self.target_offset[1] = target_y

        # Плавный зум
        if abs(self.zoom - self.target_zoom) > 0.01:
            self.zoom += (self.target_zoom - self.zoom) * self.zoom_speed * delta_time * 60

    def world_to_screen(self, world_pos):
        """Конвертация мировых координат в экранные"""
        screen_x = int(world_pos['x'] * 100 * self.zoom + self.offset[0])
        screen_y = int(world_pos['y'] * 100 * self.zoom + self.offset[1])
        return screen_x, screen_y

    def screen_to_world(self, screen_pos):
        """Конвертация экранных координат в мировые"""
        world_x = (screen_pos[0] - self.offset[0]) / (100 * self.zoom)
        world_y = (screen_pos[1] - self.offset[1]) / (100 * self.zoom)
        return {'x': world_x, 'y': world_y}

    def zoom_in(self):
        """Увеличение масштаба"""
        self.target_zoom = min(self.target_zoom * 1.1, 3.0)

    def zoom_out(self):
        """Уменьшение масштаба"""
        self.target_zoom = max(self.target_zoom * 0.9, 0.5)

    def reset(self):
        """Сброс камеры"""
        self.offset = [self.width // 2, self.height // 2]
        self.target_offset = [self.width // 2, self.height // 2]
        self.zoom = 1.2
        self.target_zoom = 1.2


class SmoothMovement:
    """Класс для плавного интерполированного движения"""

    def __init__(self):
        self.position = {'x': 0, 'y': 0, 'z': 0}
        self.target_position = {'x': 0, 'y': 0, 'z': 0}
        self.velocity = {'x': 0, 'y': 0, 'z': 0}
        self.last_update = time.time()
        self.smooth_factor = 0.25  # Увеличили для большей плавности
        self.max_interpolation_time = 0.5

    def update_target(self, new_position, timestamp=None):
        """Обновление целевой позиции"""
        self.target_position = new_position.copy()
        self.last_update = time.time()

        # Вычисляем скорость для более плавного движения
        dx = new_position['x'] - self.position['x']
        dy = new_position['y'] - self.position['y']
        dz = new_position['z'] - self.position['z']

        # Немного сглаживаем скорость
        self.velocity['x'] = dx * 0.5 + self.velocity['x'] * 0.5
        self.velocity['y'] = dy * 0.5 + self.velocity['y'] * 0.5
        self.velocity['z'] = dz * 0.5 + self.velocity['z'] * 0.5

    def update(self, delta_time):
        """Обновление позиции с интерполяцией"""
        # Вычисляем разницу между текущей и целевой позицией
        dx = self.target_position['x'] - self.position['x']
        dy = self.target_position['y'] - self.position['y']
        dz = self.target_position['z'] - self.position['z']

        # Добавляем немного инерции на основе скорости
        dx += self.velocity['x'] * 0.1
        dy += self.velocity['y'] * 0.1
        dz += self.velocity['z'] * 0.1

        # Плавное приближение к цели
        self.position['x'] += dx * self.smooth_factor * delta_time * 60
        self.position['y'] += dy * self.smooth_factor * delta_time * 60
        self.position['z'] += dz * self.smooth_factor * delta_time * 60

        # Если очень близко, просто устанавливаем целевую позицию
        if (abs(dx) < 0.001 and abs(dy) < 0.001 and abs(dz) < 0.001):
            self.position = self.target_position.copy()
            self.velocity = {'x': 0, 'y': 0, 'z': 0}


class OtherPlayer:
    """Класс для управления другими игроками с интерполяцией и анимацией"""

    def __init__(self, player_data):
        self.id = player_data.get('id', '')
        self.name = player_data.get('name', 'Player')
        self.character_type = player_data.get('character_type', 'default')
        self.smooth_movement = SmoothMovement()
        self.position = player_data.get('position', {'x': 0, 'y': 0, 'z': 0})
        self.smooth_movement.position = self.position.copy()
        self.smooth_movement.target_position = self.position.copy()
        self.last_update_time = time.time()
        self.last_animation_update = time.time()
        self.last_direction = "right"
        self.is_active = True
        self.last_position = self.position.copy()
        self.is_moving = False

        # Инициализация анимации
        self.animation = None
        self.init_animation(player_data)

        print(f"[DEBUG] Создан игрок {self.name} с типом {self.character_type}")

    def init_animation(self, player_data):
        """Инициализация анимации персонажа"""
        try:
            # Получаем тип персонажа
            character_type = player_data.get('character_type', 'default')
            character_name = player_data.get('name', 'Player')

            # Если тип по умолчанию, пытаемся определить по имени
            if character_type == 'default':
                name_lower = character_name.lower()
                if 'celestia' in name_lower:
                    character_type = 'Celestia'
                elif 'luna' in name_lower:
                    character_type = 'Luna'
                elif 'cadance' in name_lower or 'cadence' in name_lower:
                    character_type = 'Cadance'
                elif 'twilight' in name_lower:
                    character_type = 'TwilightSparkle'
                elif 'apple' in name_lower:
                    character_type = 'AppleJack'
                elif 'rainbow' in name_lower:
                    character_type = 'RainbowDash'
                elif 'fluttershy' in name_lower:
                    character_type = 'Fluttershy'
                elif 'rarity' in name_lower:
                    character_type = 'Rarity'
                elif 'pinkie' in name_lower:
                    character_type = 'PinkiePie'

            print(f"[DEBUG] Инициализация анимации для: {character_name} (тип: {character_type})")

            char_data = {
                'name': character_name,
                'character_type': character_type
            }

            self.animation = AnimatedCharacter(char_data)
            if self.animation.load_animations():
                self.animation.set_animation("idle")
                print(f"[DEBUG] ✓ Анимация загружена для {character_type}")
                return True
            else:
                print(f"[DEBUG] ✗ Не удалось загрузить анимацию для {character_type}")
                # Создаем заглушку
                self.animation = self.create_stub_animation(character_type)
                return False
        except Exception as e:
            print(f"[ERROR] Ошибка инициализации анимации: {e}")
            # Создаем заглушку
            self.animation = self.create_stub_animation('default')
            return False

    def create_stub_animation(self, char_type):
        """Создание заглушки для анимации"""

        class StubAnimation:
            def __init__(self, char_type):
                self.char_type = char_type
                self.current_animation = "idle"
                self.current_direction = "right"

            def set_animation(self, anim):
                self.current_animation = anim
                return True

            def set_direction(self, dir):
                self.current_direction = dir
                return True

            def update(self):
                pass

            def draw(self, surface, position, scale=1.0):
                # Рисуем кружок с цветом по типу персонажа
                color_map = {
                    'Celestia': (255, 215, 0),
                    'Luna': (138, 43, 226),
                    'Cadance': (255, 182, 193),
                    'TwilightSparkle': (147, 112, 219),
                    'AppleJack': (255, 165, 0),
                    'RainbowDash': (0, 191, 255),
                    'Fluttershy': (255, 255, 0),
                    'Rarity': (192, 192, 192),
                    'PinkiePie': (255, 105, 180),
                    'default': (200, 100, 100)
                }

                color = color_map.get(char_type, color_map['default'])
                radius = int(25 * scale)
                pygame.draw.circle(surface, color,
                                   (int(position[0]), int(position[1])),
                                   radius)

                # Буква персонажа
                try:
                    font = pygame.font.Font(None, int(20 * scale))
                    char_text = char_type[0] if char_type else "?"
                    text = font.render(char_text, True, (255, 255, 255))
                    text_rect = text.get_rect(center=(int(position[0]), int(position[1])))
                    surface.blit(text, text_rect)
                except:
                    pass

        return StubAnimation(char_type)

    def update_position(self, new_position, timestamp=None):
        """Обновление позиции игрока"""
        self.last_position = self.position.copy()
        self.position = new_position.copy()
        self.smooth_movement.update_target(new_position, timestamp)
        self.last_update_time = time.time()

    def update(self, delta_time):
        """Обновление с интерполяцией и анимацией"""
        if self.is_active:
            # Сохраняем предыдущую позицию
            prev_pos = self.smooth_movement.position.copy()

            # Обновляем интерполяцию
            self.smooth_movement.update(delta_time)

            current_pos = self.smooth_movement.position

            # Проверяем, нужно ли обновлять анимацию
            current_time = time.time()
            if current_time - self.last_animation_update > 0.08:  # Обновляем каждые 80 мс
                # Вычисляем движение
                dx = current_pos['x'] - prev_pos['x']
                dy = current_pos['y'] - prev_pos['y']

                # Используем больший порог для избежания "дрожания"
                distance = math.sqrt(dx * dx + dy * dy)
                self.is_moving = distance > 0.015

                if self.animation:
                    if self.is_moving:
                        # Определяем основное направление
                        if abs(dx) > abs(dy):
                            if dx > 0:
                                direction = "right"
                            else:
                                direction = "left"
                        else:
                            if dy > 0:
                                direction = "down"
                            else:
                                direction = "up"

                        # Устанавливаем направление если оно изменилось
                        if direction != self.last_direction:
                            self.animation.set_direction(direction)
                            self.last_direction = direction

                        # Устанавливаем анимацию ходьбы
                        if self.animation.current_animation != "walk":
                            self.animation.set_animation("walk")
                    else:
                        # Игрок стоит на месте
                        if self.animation.current_animation != "idle":
                            self.animation.set_animation("idle")

                    # Обновляем анимацию
                    self.animation.update()
                    self.last_animation_update = current_time

    def get_position(self):
        """Получение интерполированной позиции"""
        return self.smooth_movement.position


class ChatMessageOverhead:
    """Сообщение над головой персонажа"""

    def __init__(self, text, character_name, duration=10.0):
        self.text = text
        self.character_name = character_name
        self.start_time = time.time()
        self.duration = duration
        self.alpha = 255
        self.fade_start = duration - 2.0
        self.position = {'x': 0, 'y': 0, 'z': 0}
        self.base_height_offset = 40
        self.current_height_offset = 40
        self.target_height_offset = 40

    def is_expired(self):
        """Проверка, истекло ли время отображения"""
        return time.time() - self.start_time > self.duration

    def update(self, character_position=None, delta_time=1.0):
        """Обновление позиции сообщения"""
        if character_position:
            self.position = character_position.copy()
        current_time = time.time() - self.start_time

        # Плавное исчезновение в конце
        if current_time > self.fade_start:
            fade_progress = (current_time - self.fade_start) / (self.duration - self.fade_start)
            self.alpha = int(255 * (1 - fade_progress))

        # Плавное перемещение к целевой высоте
        if abs(self.current_height_offset - self.target_height_offset) > 0.1:
            self.current_height_offset += (
                    (self.target_height_offset - self.current_height_offset) * 5.0 * delta_time
            )

    def set_height_offset(self, offset):
        """Установка целевой высоты для сообщения"""
        self.target_height_offset = offset

    def get_screen_position(self, camera):
        """Получение экранных координат для отрисовки"""
        if not camera:
            return None

        # Позиция над головой персонажа с текущей высотой
        overhead_pos = {
            'x': self.position['x'],
            'y': self.position['y'],
            'z': self.position['z'] + self.current_height_offset / 100.0
        }
        screen_x, screen_y = camera.world_to_screen(overhead_pos)

        return screen_x, screen_y


class DPP2GraphicClient:
    """Основной графический клиент с камерой следящей за персонажем"""

    def __init__(self):
        pygame.init()
        pygame.font.init()

        # Загрузка конфигурации
        from config import config
        self.config = config

        # Настройки окна
        self.width = self.config.get('graphics.width', 1200)
        self.height = self.config.get('graphics.height', 800)
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("DPP2 - Camera Follow System")

        # Иконка окна
        try:
            icon_surface = self.create_window_icon()
            pygame.display.set_icon(icon_surface)
        except:
            pass

        # Загрузка цветовой схемы
        self.current_theme = self.config.get('ui.theme', 'black')
        self.load_color_scheme()

        # Камера
        self.camera = Camera(self.width, self.height)
        self.camera.follow_player = self.config.get('camera.follow_player', True)
        self.camera.smoothing = self.config.get('camera.smoothing', True)
        self.camera.zoom_speed = self.config.get('camera.zoom_speed', 0.1)
        self.camera.zoom = self.config.get('camera.default_zoom', 1.2)
        self.camera.target_zoom = self.config.get('camera.default_zoom', 1.2)

        # Игровые состояния
        self.game_state = GameState.MENU
        self.running = True
        self.clock = pygame.time.Clock()
        self.fps = self.config.get('graphics.fps_limit', 60)

        # Сетевое подключение
        from network_client import NetworkClient
        self.network = NetworkClient()
        self.connected = False
        self.connection_in_progress = False

        # Очереди
        self.network_queue = queue.Queue()

        # Игровые данные
        self.username = ""
        self.character = None
        self.other_players = {}
        self.other_players_data = {}
        self.in_world = False
        self.world_data = {}
        self.character_selected = False

        # Анимация персонажа
        self.player_animation = None

        # Меню выбора персонажа
        self.character_selector = None
        self.show_character_select = False

        # Генерация уникального client_id
        self.client_id = str(uuid.uuid4())[:8]
        print(f"[SYSTEM] Generated client_id: {self.client_id}")

        # Управление
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
            pygame.K_RIGHT: False,
            pygame.K_ESCAPE: False,
            pygame.K_F1: False,
            pygame.K_j: False,
            pygame.K_k: False,
            pygame.K_l: False
        }

        # Шрифты
        self.fonts = self.load_fonts()

        # UI элементы
        self.menu_buttons = []
        self.input_fields = []
        self.chat_messages = []
        self.chat_input = ""
        self.chat_active = False
        self.active_input_field = None

        # Сообщения над головами персонажей
        self.overhead_messages = []

        # Флаги отображения UI
        self.show_esc_menu = False
        self.show_settings_menu = False
        self.side_panel_visible = True
        self.side_panel_auto_hide = self.config.get('ui.side_panel_auto_hide', True)

        # Панели
        self.side_panel_width = self.config.get('ui.side_panel_width', 320)
        self.top_panel_height = self.config.get('ui.top_panel_height', 70)
        self.bottom_panel_height = self.config.get('ui.bottom_panel_height', 40)

        # Настройки чата
        self.chat_message_lifetime = 10.0
        self.chat_message_fade_time = 3.0

        # Время
        self.last_update = time.time()
        self.position_update_rate = self.config.get('network.udp_position_update_rate', 0.016)
        self.last_position_update = 0
        self.last_heartbeat = 0
        self.heartbeat_interval = self.config.get('network.udp_heartbeat_interval', 1.0)

        # Статистика
        self.stats = {
            'fps': 0,
            'players_online': 0,
            'ping': 0,
            'udp_packets_sent': 0,
            'udp_packets_received': 0,
            'connection_time': 0,
            'camera_x': 0,
            'camera_y': 0
        }

        # Анимации
        self.menu_animation = 0.0
        self.settings_animation = 0.0
        self.side_panel_animation = 1.0
        self.menu_animation_speed = self.config.get('ui.menu_animation_speed', 0.3)

        # Настройки цветовых схем
        self.available_themes = self.config.get_available_themes()
        self.theme_buttons = []

        # Инициализация
        self.init_ui()

        # Сетевой поток
        self.stop_network_thread = False
        self.network_thread = None

    def load_color_scheme(self):
        """Загрузка цветовой схемы"""
        scheme = self.config.get_color_scheme(self.current_theme)

        self.colors = {
            'black': tuple(scheme.get('black', [10, 10, 15])),
            'dark_grey': tuple(scheme.get('dark_grey', [30, 30, 35])),
            'grey': tuple(scheme.get('grey', [50, 50, 60])),
            'light_grey': tuple(scheme.get('light_grey', [80, 80, 90])),
            'white': tuple(scheme.get('white', [240, 240, 245])),
            'accent_grey': tuple(scheme.get('accent_grey', [120, 120, 130])),
            'success': tuple(scheme.get('success', [100, 220, 100])),
            'error': tuple(scheme.get('error', [220, 100, 100])),
            'warning': tuple(scheme.get('warning', [220, 180, 100])),
            'player': tuple(scheme.get('player', [80, 160, 240])),
            'other_player': tuple(scheme.get('other_player', [240, 100, 100])),
            'chat_overhead': tuple(scheme.get('player', [200, 230, 255]))
        }

    def create_window_icon(self):
        """Создание иконки окна"""
        icon_size = 32
        surface = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)

        # Фон
        pygame.draw.rect(surface, self.colors['dark_grey'], (0, 0, icon_size, icon_size))

        # Буква D с камерой
        pygame.draw.rect(surface, self.colors['player'], (8, 8, 6, 16))
        pygame.draw.rect(surface, self.colors['player'], (14, 8, 6, 4))
        pygame.draw.rect(surface, self.colors['player'], (14, 20, 6, 4))
        pygame.draw.rect(surface, self.colors['player'], (20, 12, 2, 8))

        # Иконка камеры
        pygame.draw.circle(surface, self.colors['white'], (24, 16), 3)

        return surface

    def load_fonts(self):
        """Загрузка шрифтов"""
        try:
            title_font = pygame.font.Font(None, 42)
            large_font = pygame.font.Font(None, 28)
            medium_font = pygame.font.Font(None, 22)
            small_font = pygame.font.Font(None, 18)
            tiny_font = pygame.font.Font(None, 14)
        except:
            title_font = pygame.font.SysFont('Arial', 42, bold=True)
            large_font = pygame.font.SysFont('Arial', 28, bold=True)
            medium_font = pygame.font.SysFont('Arial', 22)
            small_font = pygame.font.SysFont('Arial', 18)
            tiny_font = pygame.font.SysFont('Arial', 14)

        return {
            'title': title_font,
            'large': large_font,
            'medium': medium_font,
            'small': small_font,
            'tiny': tiny_font
        }

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        side_panel_x = self.width - self.side_panel_width

        # Поля ввода
        self.input_fields = [
            {
                'name': 'server_host',
                'label': 'SERVER ADDRESS',
                'rect': pygame.Rect(side_panel_x + 25, 120, self.side_panel_width - 50, 42),
                'text': self.config.get('network.default_host', '127.0.0.1'),
                'active': False,
                'visible': True,
                'max_length': 50,
                'hint': 'Enter server IP'
            },
            {
                'name': 'server_port',
                'label': 'SERVER PORT',
                'rect': pygame.Rect(side_panel_x + 25, 185, self.side_panel_width - 50, 42),
                'text': str(self.config.get('network.default_port', 5555)),
                'active': False,
                'visible': True,
                'max_length': 10,
                'hint': 'Port number'
            },
            {
                'name': 'username',
                'label': 'USERNAME',
                'rect': pygame.Rect(side_panel_x + 25, 250, self.side_panel_width - 50, 42),
                'text': '',
                'active': False,
                'visible': False,
                'max_length': 20,
                'hint': 'Enter your name'
            }
        ]

        # Кнопки
        button_y_start = 320
        button_height = 48
        button_spacing = 65

        self.menu_buttons = [
            {
                'id': 'connect',
                'text': 'CONNECT TO SERVER',
                'rect': pygame.Rect(side_panel_x + 25, button_y_start, self.side_panel_width - 50, button_height),
                'action': self.connect_to_server,
                'enabled': True,
                'icon': '📡'
            },
            {
                'id': 'login',
                'text': 'LOGIN',
                'rect': pygame.Rect(side_panel_x + 25, button_y_start + button_spacing, self.side_panel_width - 50,
                                    button_height),
                'action': self.login,
                'enabled': False,
                'icon': '👤'
            },
            {
                'id': 'character',
                'text': 'SELECT CHARACTER',
                'rect': pygame.Rect(side_panel_x + 25, button_y_start + button_spacing * 2, self.side_panel_width - 50,
                                    button_height),
                'action': self.select_character,
                'enabled': False,
                'icon': '🎮'
            },
            {
                'id': 'join_world',
                'text': 'ENTER WORLD',
                'rect': pygame.Rect(side_panel_x + 25, button_y_start + button_spacing * 3, self.side_panel_width - 50,
                                    button_height),
                'action': self.join_world,
                'enabled': False,
                'icon': '🌍'
            },
            {
                'id': 'test_animations',
                'text': 'TEST ANIMATIONS',
                'rect': pygame.Rect(side_panel_x + 25, button_y_start + button_spacing * 4, self.side_panel_width - 50,
                                    button_height),
                'action': self.test_animations,
                'enabled': True,
                'icon': '🔧'
            },
            {
                'id': 'quit',
                'text': 'QUIT GAME',
                'rect': pygame.Rect(side_panel_x + 25, button_y_start + button_spacing * 5, self.side_panel_width - 50,
                                    button_height),
                'action': self.quit_game,
                'enabled': True,
                'icon': '🚪'
            }
        ]

        # Кнопки ESC меню
        self.esc_menu_buttons = [
            {
                'id': 'resume',
                'text': 'RESUME GAME',
                'action': self.resume_game,
                'icon': '▶'
            },
            {
                'id': 'settings',
                'text': 'SETTINGS',
                'action': self.open_settings,
                'icon': '⚙'
            },
            {
                'id': 'toggle_ui',
                'text': 'TOGGLE UI',
                'action': self.toggle_ui_visibility,
                'icon': '👁'
            },
            {
                'id': 'disconnect',
                'text': 'DISCONNECT',
                'action': self.disconnect_from_server,
                'icon': '📡'
            },
            {
                'id': 'quit_esc',
                'text': 'QUIT TO DESKTOP',
                'action': self.quit_game,
                'icon': '🚪'
            }
        ]

        # Инициализация кнопок цветовых схем для меню настроек
        self.init_theme_buttons()

    def init_theme_buttons(self):
        """Инициализация кнопок выбора темы"""
        self.theme_buttons = []
        themes = self.config.get('color_schemes', {})

        for i, (theme_key, theme_data) in enumerate(themes.items()):
            self.theme_buttons.append({
                'id': f'theme_{theme_key}',
                'text': theme_data.get('name', theme_key.upper()),
                'theme_key': theme_key,
                'action': lambda t=theme_key: self.change_theme(t),
                'icon': '🎨',
                'selected': theme_key == self.current_theme
            })

    def start_network_thread(self):
        """Запуск сетевого потока"""
        if self.network_thread and self.network_thread.is_alive():
            self.stop_network_thread = True
            self.network_thread.join(timeout=1.0)

        self.stop_network_thread = False
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.network_thread.start()

    def network_loop(self):
        """Сетевой цикл"""
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
                print(f"[NETWORK] Error in UDP thread: {e}")
                time.sleep(0.5)

    def process_network_messages(self):
        """Обработка сетевых сообщений"""
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
            elif event.type == pygame.MOUSEWHEEL:
                self.handle_mouse_wheel(event)
            elif event.type == pygame.TEXTINPUT:
                self.handle_text_input(event.text)

    def handle_keydown(self, event):
        """Обработка нажатия клавиш"""
        if event.key in self.keys:
            self.keys[event.key] = True

        # Обработка меню выбора персонажа
        if self.show_character_select:
            if event.key == pygame.K_LEFT:
                if self.character_selector:
                    self.character_selector.prev_character()
            elif event.key == pygame.K_RIGHT:
                if self.character_selector:
                    self.character_selector.next_character()
            elif event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                self.confirm_character_selection()
            elif event.key == pygame.K_ESCAPE:
                self.show_character_select = False
                self.character_selector = None
                self.add_chat_message("[SYSTEM] Character selection canceled")
            return

        # ESC для открытия/закрытия меню
        if event.key == pygame.K_ESCAPE:
            if self.show_settings_menu:
                self.close_settings()
            elif self.in_world and not self.chat_active and not self.show_character_select:
                self.toggle_esc_menu()
            elif self.show_esc_menu:
                self.toggle_esc_menu()
            elif self.chat_active:
                self.chat_active = False
                self.chat_input = ""

        # F1 для переключения UI
        elif event.key == pygame.K_F1:
            self.toggle_ui_visibility()

        elif event.key == pygame.K_RETURN:
            if self.chat_active:
                self.send_chat_message()
                self.chat_active = False
                self.chat_input = ""
            elif self.active_input_field is not None and not self.show_esc_menu and not self.show_settings_menu and not self.show_character_select:
                field = self.input_fields[self.active_input_field]
                if field['name'] == 'username' and field['text'].strip():
                    self.login()
            elif self.in_world and not self.show_esc_menu and not self.show_settings_menu and not self.show_character_select:
                # Активируем чат при нажатии Enter в мире
                self.chat_active = True

        elif event.key == pygame.K_BACKSPACE:
            if self.chat_active:
                self.chat_input = self.chat_input[:-1]
            elif self.active_input_field is not None and not self.show_esc_menu and not self.show_settings_menu and not self.show_character_select:
                field = self.input_fields[self.active_input_field]
                if len(field['text']) > 0:
                    field['text'] = field['text'][:-1]

        elif event.key == pygame.K_TAB and not self.show_esc_menu and not self.show_settings_menu and not self.show_character_select:
            self.switch_input_field()

        elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
            self.camera.zoom_in()

        elif event.key == pygame.K_MINUS:
            self.camera.zoom_out()

        # Тестовые клавиши для анимаций
        elif event.key == pygame.K_j and self.in_world and self.player_animation:
            self.set_player_animation("jump")
        elif event.key == pygame.K_k and self.in_world and self.player_animation:
            self.set_player_animation("attack")
        elif event.key == pygame.K_l and self.in_world and self.player_animation:
            self.set_player_animation("sleep")

    def handle_keyup(self, event):
        """Обработка отпускания клавиш"""
        if event.key in self.keys:
            self.keys[event.key] = False

    def handle_mouse_click(self, event):
        """Обработка кликов мыши"""
        if self.show_character_select and self.character_selector:
            result = self.character_selector.handle_click(event.pos)
            if result == "select":
                self.confirm_character_selection()
            elif result == "cancel":
                self.show_character_select = False
                self.character_selector = None
                self.add_chat_message("[SYSTEM] Character selection canceled")
            elif result == "select_item":
                pass
            return

        if self.show_settings_menu:
            self.handle_settings_menu_click(event)
            return

        if self.show_esc_menu:
            self.handle_esc_menu_click(event)
            return

        # Обработка кликов левой кнопкой мыши
        if event.button == 1:
            if self.side_panel_visible:
                mouse_pos = pygame.mouse.get_pos()
                field_clicked = False

                # Поля ввода
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

                # Кнопки меню
                for button in self.menu_buttons:
                    if button['rect'].collidepoint(mouse_pos) and button.get('enabled', True):
                        button['action']()

    def handle_mouse_wheel(self, event):
        """Обработка колесика мыши"""
        if self.show_character_select and self.character_selector:
            self.character_selector.handle_mouse_wheel(event)
        else:
            if event.y > 0:
                self.camera.zoom_in()
            elif event.y < 0:
                self.camera.zoom_out()

    def handle_esc_menu_click(self, event):
        """Обработка кликов в ESC меню"""
        if event.button == 1:
            mouse_pos = pygame.mouse.get_pos()
            menu_width = 400
            menu_height = 450
            menu_x = (self.width - menu_width) // 2
            menu_y = (self.height - menu_height) // 2

            button_height = 55
            button_spacing = 8
            start_y = menu_y + 80

            for i, button in enumerate(self.esc_menu_buttons):
                button_rect = pygame.Rect(
                    menu_x + 50,
                    start_y + i * (button_height + button_spacing),
                    menu_width - 100,
                    button_height
                )
                if button_rect.collidepoint(mouse_pos):
                    button['action']()

    def handle_settings_menu_click(self, event):
        """Обработка кликов в меню настроек"""
        if event.button == 1:
            mouse_pos = pygame.mouse.get_pos()
            menu_width = 500
            menu_height = 500
            menu_x = (self.width - menu_width) // 2
            menu_y = (self.height - menu_height) // 2

            # Кнопки тем
            theme_start_y = menu_y + 120
            theme_button_height = 45
            theme_button_spacing = 10

            for i, button in enumerate(self.theme_buttons):
                button_rect = pygame.Rect(
                    menu_x + 50,
                    theme_start_y + i * (theme_button_height + theme_button_spacing),
                    menu_width - 100,
                    theme_button_height
                )
                if button_rect.collidepoint(mouse_pos):
                    button['action']()

            # Кнопка назад
            back_button_rect = pygame.Rect(
                menu_x + 50,
                menu_y + menu_height - 70,
                menu_width - 100,
                50
            )
            if back_button_rect.collidepoint(mouse_pos):
                self.close_settings()

    def handle_text_input(self, text):
        """Обработка текстового ввода"""
        if self.chat_active:
            if len(self.chat_input) < 100:
                self.chat_input += text
        elif self.active_input_field is not None and not self.show_esc_menu and not self.show_settings_menu and not self.show_character_select:
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

        # Обновление анимаций меню выбора персонажа
        if self.show_character_select and self.character_selector:
            self.character_selector.update()

        # Обновление анимаций
        if self.show_esc_menu:
            self.menu_animation = min(self.menu_animation + delta_time / self.menu_animation_speed, 1.0)
        else:
            self.menu_animation = max(self.menu_animation - delta_time / self.menu_animation_speed, 0.0)

        if self.show_settings_menu:
            self.settings_animation = min(self.settings_animation + delta_time / self.menu_animation_speed, 1.0)
        else:
            self.settings_animation = max(self.settings_animation - delta_time / self.menu_animation_speed, 0.0)

        # Автоматическое скрытие боковой панели при входе в мир
        if self.in_world and self.side_panel_auto_hide:
            self.side_panel_animation = max(self.side_panel_animation - delta_time / 0.5, 0.0)
            if self.side_panel_animation <= 0:
                self.side_panel_visible = False
        else:
            self.side_panel_animation = min(self.side_panel_animation + delta_time / 0.5, 1.0)

        # Обновление позиции игрока
        if self.in_world and self.character and not self.chat_active and not self.show_esc_menu and not self.show_settings_menu and not self.show_character_select:
            self.update_player_position(delta_time)

        # Обновление анимации своего персонажа
        if self.in_world and self.player_animation:
            is_moving = any([self.keys[pygame.K_w], self.keys[pygame.K_s],
                             self.keys[pygame.K_a], self.keys[pygame.K_d]])

            if is_moving:
                # Определяем направление по клавишам
                if self.keys[pygame.K_a] or self.keys[pygame.K_LEFT]:
                    self.player_animation.set_direction("left")
                elif self.keys[pygame.K_d] or self.keys[pygame.K_RIGHT]:
                    self.player_animation.set_direction("right")

                if self.keys[pygame.K_LSHIFT]:
                    self.player_animation.set_animation("run")
                else:
                    self.player_animation.set_animation("walk")
            elif self.player_animation.current_animation in ["jump", "attack", "sleep"]:
                pass
            else:
                if self.player_animation.current_animation != "idle":
                    self.player_animation.set_animation("idle")

            self.player_animation.update()

        # Обновление камеры
        if self.in_world and self.character and self.camera.follow_player:
            player_pos = self.character.get('position', {'x': 0, 'y': 0, 'z': 0})
            self.camera.update(player_pos, delta_time)

            # Обновление статистики камеры
            self.stats['camera_x'] = int(self.camera.offset[0])
            self.stats['camera_y'] = int(self.camera.offset[1])

        # Обновление интерполяции других игроков
        current_time = time.time()
        for player_id, player in self.other_players.items():
            player.update(delta_time)

            # Дополнительное обновление анимации для движущихся игроков
            if hasattr(player, 'animation') and player.animation:
                if player.is_moving:
                    player.animation.update()

        # Обновление статуса
        self.update_connection_status()
        self.stats['players_online'] = len(self.other_players) + (1 if self.character else 0)
        self.update_join_world_button()

        # Удаление старых сообщений из истории чата
        self.cleanup_old_chat_messages()

        # Обновление сообщений над головами
        self.update_overhead_messages(delta_time)

        # Обновление высоты сообщений для каждого персонажа
        self.update_message_heights()

        if self.connected and self.stats['connection_time'] == 0:
            self.stats['connection_time'] = current_time

        self.last_update = current_time

    def update_player_position(self, delta_time):
        """Обновление позиции игрока"""
        if not self.in_world or not self.character or self.chat_active or self.show_esc_menu or self.show_settings_menu or self.show_character_select:
            return

        dx, dy, dz = 0, 0, 0
        speed = 2.0 * delta_time

        # Правильные направления движения
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

        # Определяем направление движения для анимации
        if self.player_animation:
            if dx < 0:
                self.player_animation.set_direction("left")
            elif dx > 0:
                self.player_animation.set_direction("right")

        if dx != 0 or dy != 0 or dz != 0:
            pos = self.character.get('position', {'x': 0, 'y': 0, 'z': 0})
            pos['x'] += dx
            pos['y'] += dy
            pos['z'] += dz

            from character_manager import CharacterManager
            cm = CharacterManager()
            self.character['position'] = pos
            cm.save_character(self.character)

            current_time = time.time()
            if current_time - self.last_position_update >= self.position_update_rate:
                self.send_position_update(pos)
                self.last_position_update = current_time

    def cleanup_old_chat_messages(self):
        """Удаление старых сообщений из истории чата"""
        current_time = time.time()

        if not self.chat_active:
            self.chat_messages = [
                msg for msg in self.chat_messages
                if current_time - msg['timestamp'] < self.chat_message_lifetime
            ]

        max_age = self.chat_message_lifetime + self.chat_message_fade_time
        self.chat_messages = [
            msg for msg in self.chat_messages
            if current_time - msg['timestamp'] < max_age
        ]

    def update_overhead_messages(self, delta_time):
        """Обновление сообщений над головами персонажей"""
        current_time = time.time()

        self.overhead_messages = [
            msg for msg in self.overhead_messages
            if not msg.is_expired()
        ]

        for msg in self.overhead_messages:
            if msg.character_name == self.character['name'] if self.character else False:
                msg.update(self.character.get('position') if self.character else None, delta_time)
            else:
                for player_id, player in self.other_players.items():
                    player_data = self.other_players_data.get(player_id, {'name': ''})
                    if player_data['name'] == msg.character_name:
                        msg.update(player.get_position(), delta_time)
                        break
                else:
                    msg.update(None, delta_time)

    def update_message_heights(self):
        """Обновление высоты сообщений для каждого персонажа"""
        messages_by_character = {}

        for msg in self.overhead_messages:
            if msg.character_name not in messages_by_character:
                messages_by_character[msg.character_name] = []
            messages_by_character[msg.character_name].append(msg)

        for character_name, messages in messages_by_character.items():
            messages.sort(key=lambda x: x.start_time, reverse=True)

            for i, msg in enumerate(messages):
                target_height = 40 + (i * 25)
                msg.set_height_offset(target_height)

    def get_player_by_name(self, player_name):
        """Получение данных игрока по имени"""
        for player_id, player_data in self.other_players_data.items():
            if player_data['name'] == player_name:
                return player_data
        return None

    def update_connection_status(self):
        """Обновление статуса подключения"""
        self.connected = self.network.is_connected()
        for button in self.menu_buttons:
            if button['id'] == 'login':
                button['enabled'] = self.connected
            elif button['id'] == 'character':
                button['enabled'] = bool(self.username)
            elif button['id'] == 'join_world':
                button['enabled'] = self.connected and self.username and self.character and not self.in_world

    def update_join_world_button(self):
        """Обновление кнопки входа в мир"""
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
        """Отправка обновления позиции"""
        if not self.connected or not self.character:
            return

        data = {
            'type': 'position_update',
            'client_id': self.client_id,
            'character_id': self.character['id'],
            'character_name': self.character['name'],
            'character_type': self.character.get('character_type', 'default'),
            'position': position,
            'timestamp': datetime.now().isoformat()
        }

        self.stats['udp_packets_sent'] += 1
        self.network.safe_send(data)

    def send_chat_message(self):
        """Отправка сообщения в чат"""
        if not self.chat_input.strip() or not self.connected:
            return

        self.add_chat_message(f"You: {self.chat_input}", is_self=True)

        if self.character:
            overhead_msg = ChatMessageOverhead(
                text=self.chat_input,
                character_name=self.character['name'],
                duration=10.0
            )
            overhead_msg.update(self.character.get('position') if self.character else None)
            self.overhead_messages.append(overhead_msg)

            self.update_message_heights()

        data = {
            'type': 'chat_message',
            'client_id': self.client_id,
            'character_id': self.character['id'] if self.character else None,
            'character_name': self.character['name'] if self.character else self.username,
            'character_type': self.character.get('character_type', 'default') if self.character else 'default',
            'text': self.chat_input,
            'timestamp': datetime.now().isoformat(),
            'is_overhead': True
        }

        self.stats['udp_packets_sent'] += 1
        self.network.safe_send(data)

    def add_chat_message(self, message, is_self=False):
        """Добавление сообщения в чат"""
        self.chat_messages.append({
            'text': message,
            'is_self': is_self,
            'timestamp': time.time()
        })

    def handle_server_message(self, data):
        """Обработка сообщений от сервера"""
        msg_type = data.get('type')
        print(f"[DEBUG] Получено сообщение типа: {msg_type}")

        if msg_type == 'welcome':
            self.add_chat_message("[SYSTEM] Connected to UDP server")

        elif msg_type == 'auth_response':
            success = data.get('success', False)
            if success:
                self.add_chat_message("[SYSTEM] Authentication successful")
                self.character_selected = False
            else:
                error_msg = data.get('message', 'Authentication error')
                self.add_chat_message(f"[SYSTEM] Authentication error: {error_msg}")

        elif msg_type == 'character_select_response':
            success = data.get('success', False)
            if success:
                self.character_selected = True
                self.add_chat_message("[SYSTEM] Character selected on server")
            else:
                error_msg = data.get('message', 'Character selection error')
                self.add_chat_message(f"[SYSTEM] Character selection error: {error_msg}")

        elif msg_type == 'position_update':
            character_id = data.get('character_id')
            position = data.get('position', {})
            timestamp = data.get('timestamp')
            character_type = data.get('character_type', 'default')
            character_name = data.get('character_name', 'Unknown')

            if self.character and character_id != self.character.get('id'):
                if character_type == 'default' and character_name:
                    name_lower = character_name.lower()
                    if 'celestia' in name_lower:
                        character_type = 'Celestia'
                    elif 'luna' in name_lower:
                        character_type = 'Luna'
                    elif 'cadance' in name_lower or 'cadence' in name_lower:
                        character_type = 'Cadance'
                    elif 'twilight' in name_lower:
                        character_type = 'TwilightSparkle'

                if character_id in self.other_players:
                    self.other_players[character_id].update_position(position, timestamp)
                    self.other_players_data[character_id]['position'] = position
                    self.other_players_data[character_id]['timestamp'] = time.time()

                    if character_type and character_type != self.other_players_data[character_id].get('character_type',
                                                                                                      'default'):
                        self.other_players_data[character_id]['character_type'] = character_type
                        player_data = {
                            'id': character_id,
                            'name': character_name,
                            'character_type': character_type,
                            'position': position
                        }
                        self.other_players[character_id].init_animation(player_data)
                else:
                    player_data = {
                        'id': character_id,
                        'name': character_name,
                        'character_type': character_type,
                        'position': position,
                        'timestamp': time.time()
                    }
                    self.other_players[character_id] = OtherPlayer(player_data)
                    self.other_players_data[character_id] = player_data
                    print(f"[DEBUG] Создан новый игрок {character_name} с типом {character_type}")

        elif msg_type == 'player_joined':
            player_id = data.get('character_id') or data.get('player_id')
            player_name = data.get('character_name', 'Player')
            position = data.get('position', {'x': 0, 'y': 0, 'z': 0})
            character_type = data.get('character_type', 'default')

            if character_type == 'default' and player_name:
                name_lower = player_name.lower()
                if 'celestia' in name_lower:
                    character_type = 'Celestia'
                elif 'luna' in name_lower:
                    character_type = 'Luna'
                elif 'cadance' in name_lower or 'cadence' in name_lower:
                    character_type = 'Cadance'
                elif 'twilight' in name_lower:
                    character_type = 'TwilightSparkle'

            player_data = {
                'id': player_id,
                'name': player_name,
                'character_type': character_type,
                'position': position,
                'timestamp': time.time()
            }

            self.other_players[player_id] = OtherPlayer(player_data)
            self.other_players_data[player_id] = player_data
            self.add_chat_message(f"[SYSTEM] {player_name} joined as {character_type}")
            print(f"[DEBUG] Игрок присоединился: {player_name} (тип: {character_type})")

        elif msg_type == 'player_left':
            player_id = data.get('character_id') or data.get('player_id')
            player_name = data.get('character_name', 'Player')

            if player_id in self.other_players:
                del self.other_players[player_id]
            if player_id in self.other_players_data:
                del self.other_players_data[player_id]
            self.add_chat_message(f"[SYSTEM] {player_name} left")

        elif msg_type == 'world_joined':
            self.in_world = True
            self.game_state = GameState.IN_GAME
            self.world_data = data.get('world_info', {})

            players = data.get('players', [])
            self.other_players.clear()
            self.other_players_data.clear()

            for player in players:
                player_id = player.get('id')
                if player_id:
                    character_type = player.get('character_type', 'default')
                    player_name = player.get('name', 'Player')

                    if character_type == 'default' and player_name:
                        name_lower = player_name.lower()
                        if 'celestia' in name_lower:
                            character_type = 'Celestia'
                        elif 'luna' in name_lower:
                            character_type = 'Luna'
                        elif 'cadance' in name_lower or 'cadence' in name_lower:
                            character_type = 'Cadance'
                        elif 'twilight' in name_lower:
                            character_type = 'TwilightSparkle'

                    player_data = {
                        'id': player_id,
                        'name': player_name,
                        'character_type': character_type,
                        'position': player.get('position', {'x': 0, 'y': 0, 'z': 0}),
                        'timestamp': time.time()
                    }
                    self.other_players[player_id] = OtherPlayer(player_data)
                    self.other_players_data[player_id] = player_data

            self.add_chat_message("[SYSTEM] Entered game world (UDP)!")
            self.update_join_world_button()

            if self.side_panel_auto_hide:
                self.side_panel_visible = False

        elif msg_type == 'world_leave':
            self.in_world = False
            self.add_chat_message("[SYSTEM] Left game world")
            self.update_join_world_button()

            self.side_panel_visible = True

        elif msg_type == 'chat_message':
            sender = data.get('character_name', 'Unknown')
            text = data.get('text', '')
            is_overhead = data.get('is_overhead', False)
            character_type = data.get('character_type', 'default')

            if not (sender == self.character['name'] if self.character else sender == self.username):
                if not is_overhead:
                    self.add_chat_message(f"{sender}: {text}")
                elif len(text) <= 3:
                    self.add_chat_message(f"{sender} [overhead]: {text}")

                overhead_msg = ChatMessageOverhead(
                    text=text,
                    character_name=sender,
                    duration=10.0
                )

                player = self.get_player_by_name(sender)
                if player:
                    overhead_msg.update(player.get('position'))

                self.overhead_messages.append(overhead_msg)

                self.update_message_heights()

        elif msg_type == 'error':
            error_msg = data.get('message', 'Error')
            self.add_chat_message(f"[ERROR] {error_msg}")

    def render(self):
        """Отрисовка игры"""
        self.screen.fill(self.colors['black'])

        if self.in_world:
            self.render_game_world()

        if self.side_panel_visible and self.side_panel_animation > 0:
            self.render_side_panel()

        self.render_overhead_messages()

        if self.show_character_select and self.character_selector:
            self.character_selector.render(self.screen, self.colors, self.fonts)

        if self.chat_active:
            self.render_chat_input()
        elif len(self.chat_messages) > 0 and (self.in_world or self.connected):
            self.render_chat_history()

        self.render_top_panel()

        if self.show_esc_menu or self.menu_animation > 0:
            self.render_esc_menu()

        if self.show_settings_menu or self.settings_animation > 0:
            self.render_settings_menu()

        pygame.display.flip()

    def render_game_world(self):
        """Отрисовка игрового мира"""
        if self.side_panel_visible and self.side_panel_animation > 0:
            game_width = self.width - int(self.side_panel_width * self.side_panel_animation)
        else:
            game_width = self.width

        pygame.draw.rect(self.screen, self.colors['dark_grey'],
                         (0, self.top_panel_height, game_width, self.height - self.top_panel_height))

        if self.camera.zoom < 2.0:
            grid_color = tuple(min(c + 10, 255) for c in self.colors['dark_grey'])
            grid_step = int(self.camera.grid_size * self.camera.zoom)

            start_x = -self.camera.offset[0] % grid_step
            start_y = -self.camera.offset[1] % grid_step

            for x in range(int(start_x), game_width, grid_step):
                pygame.draw.line(self.screen, grid_color,
                                 (x, self.top_panel_height),
                                 (x, self.height), 1)
            for y in range(int(start_y), self.height, grid_step):
                pygame.draw.line(self.screen, grid_color,
                                 (0, y),
                                 (game_width, y), 1)

        # Отрисовка других игроков
        for player_id, player in self.other_players.items():
            pos = player.get_position()
            screen_x, screen_y = self.camera.world_to_screen(pos)

            if (0 <= screen_x <= game_width and
                    self.top_panel_height <= screen_y <= self.height):

                if hasattr(player, 'animation') and player.animation:
                    try:
                        player.animation.draw(self.screen, (screen_x, screen_y),
                                              scale=0.6 * self.camera.zoom)
                    except Exception as e:
                        print(f"[DEBUG] Ошибка отрисовки анимации {player.name}: {e}")
                        player_radius = int(20 * self.camera.zoom)
                        color_map = {
                            'Celestia': (255, 215, 0),
                            'Luna': (138, 43, 226),
                            'Cadance': (255, 182, 193),
                            'TwilightSparkle': (147, 112, 219),
                            'AppleJack': (255, 165, 0),
                            'RainbowDash': (0, 191, 255),
                            'Fluttershy': (255, 255, 0),
                            'Rarity': (192, 192, 192),
                            'PinkiePie': (255, 105, 180),
                            'default': self.colors['other_player']
                        }
                        color = color_map.get(player.character_type, color_map['default'])
                        pygame.draw.circle(self.screen, color,
                                           (screen_x, screen_y), player_radius)

                        try:
                            font = pygame.font.Font(None, int(16 * self.camera.zoom))
                            char_text = player.character_type[0] if player.character_type else "?"
                            text = font.render(char_text, True, (255, 255, 255))
                            text_rect = text.get_rect(center=(screen_x, screen_y))
                            self.screen.blit(text, text_rect)
                        except:
                            pass
                else:
                    player_radius = int(20 * self.camera.zoom)
                    color_map = {
                        'Celestia': (255, 215, 0),
                        'Luna': (138, 43, 226),
                        'Cadance': (255, 182, 193),
                        'TwilightSparkle': (147, 112, 219),
                        'default': self.colors['other_player']
                    }
                    color = color_map.get(player.character_type, color_map['default'])
                    pygame.draw.circle(self.screen, color,
                                       (screen_x, screen_y), player_radius)

                    try:
                        font = pygame.font.Font(None, int(16 * self.camera.zoom))
                        char_text = player.character_type[0] if player.character_type else "?"
                        text = font.render(char_text, True, (255, 255, 255))
                        text_rect = text.get_rect(center=(screen_x, screen_y))
                        self.screen.blit(text, text_rect)
                    except:
                        pass

                player_data = self.other_players_data.get(player_id, {'name': 'Unknown'})
                name = self.fonts['tiny'].render(player_data['name'], True, self.colors['white'])
                name_rect = name.get_rect(center=(screen_x, screen_y - 35))
                self.screen.blit(name, name_rect)

        # Отрисовка своего персонажа
        if self.character:
            player_pos = self.character.get('position', {'x': 0, 'y': 0, 'z': 0})
            player_screen_x, player_screen_y = self.camera.world_to_screen(player_pos)

            if (0 <= player_screen_x <= game_width and
                    self.top_panel_height <= player_screen_y <= self.height):

                if self.player_animation:
                    self.player_animation.draw(self.screen,
                                               (player_screen_x, player_screen_y),
                                               scale=0.7 * self.camera.zoom)
                else:
                    player_radius = int(25 * self.camera.zoom)
                    pygame.draw.circle(self.screen, self.colors['player'],
                                       (player_screen_x, player_screen_y), player_radius)

                name = self.fonts['small'].render(self.character['name'], True, self.colors['white'])
                name_rect = name.get_rect(center=(player_screen_x, player_screen_y - 40))
                self.screen.blit(name, name_rect)

        if self.world_data:
            world_name = self.world_data.get('name', 'Unknown World')
            world_text = self.fonts['small'].render(f"World: {world_name}", True, self.colors['accent_grey'])
            self.screen.blit(world_text, (10, self.top_panel_height + 10))

            cam_text = self.fonts['tiny'].render(
                f"Camera: Follow: {'ON' if self.camera.follow_player else 'OFF'} | Zoom: {self.camera.zoom:.1f}x",
                True, self.colors['light_grey']
            )
            self.screen.blit(cam_text, (10, self.top_panel_height + 35))

    def render_overhead_messages(self):
        """Отрисовка сообщений над головами персонажей"""
        messages_by_character = {}

        for msg in self.overhead_messages:
            if msg.character_name not in messages_by_character:
                messages_by_character[msg.character_name] = []
            messages_by_character[msg.character_name].append(msg)

        for character_name, messages in messages_by_character.items():
            messages.sort(key=lambda x: x.start_time, reverse=True)

            char_pos = None
            if character_name == self.character['name'] if self.character else False:
                if self.character and 'position' in self.character:
                    char_pos = self.character['position']
            else:
                for player_id, player in self.other_players.items():
                    player_data = self.other_players_data.get(player_id, {'name': ''})
                    if player_data['name'] == character_name:
                        char_pos = player.get_position()
                        break

            if not char_pos:
                continue

            screen_pos = self.camera.world_to_screen(char_pos)
            if not screen_pos:
                continue

            screen_x, screen_y = screen_pos

            for i, msg in enumerate(messages):
                if not (0 <= screen_x <= self.width and 0 <= screen_y <= self.height):
                    continue

                text_surface = self.fonts['medium'].render(msg.text, True, (255, 255, 255))

                if msg.alpha < 255:
                    text_surface.set_alpha(msg.alpha)

                text_width = text_surface.get_width()
                text_height = text_surface.get_height()
                padding_x = 8
                padding_y = 4
                bg_width = text_width + padding_x * 2
                bg_height = text_height + padding_y * 2

                bg_x = screen_x - bg_width // 2
                text_x = screen_x - text_width // 2
                text_y = screen_y - 35 - (i * 25)
                bg_y = text_y - padding_y

                bg_surface = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
                bg_alpha = 180
                if msg.alpha < 255:
                    bg_alpha = int(msg.alpha * 0.7)

                pygame.draw.rect(bg_surface, (0, 0, 0, bg_alpha),
                                 (0, 0, bg_width, bg_height),
                                 border_radius=6)

                pygame.draw.rect(bg_surface, (100, 100, 100, bg_alpha),
                                 (0, 0, bg_width, bg_height),
                                 width=1, border_radius=6)

                self.screen.blit(bg_surface, (bg_x, bg_y))
                self.screen.blit(text_surface, (text_x, text_y))

    def render_side_panel(self):
        """Отрисовка боковой панели"""
        anim_factor = self.side_panel_animation
        side_panel_x = self.width - int(self.side_panel_width * anim_factor)

        panel_surface = pygame.Surface((self.side_panel_width, self.height), pygame.SRCALPHA)
        panel_surface.fill((*self.colors['dark_grey'][:3], int(255 * anim_factor)))
        pygame.draw.rect(panel_surface, self.colors['grey'], (0, 0, 2, self.height))
        self.screen.blit(panel_surface, (side_panel_x, 0))

        content_alpha = int(255 * anim_factor)

        title_surface = self.fonts['large'].render("CONTROL PANEL", True, self.colors['white'])
        title_surface.set_alpha(content_alpha)
        self.screen.blit(title_surface, (side_panel_x + 25, 40))

        subtitle_surface = self.fonts['tiny'].render("DPP2 - CAMERA SYSTEM", True, self.colors['accent_grey'])
        subtitle_surface.set_alpha(content_alpha)
        self.screen.blit(subtitle_surface, (side_panel_x + 25, 75))

        if anim_factor > 0.9:
            for field in self.input_fields:
                if not field.get('visible', True):
                    continue

                field['rect'].x = side_panel_x + 25

                label = self.fonts['tiny'].render(field['label'], True, self.colors['light_grey'])
                self.screen.blit(label, (field['rect'].x, field['rect'].y - 20))

                bg_color = self.colors['grey'] if not field['active'] else self.colors['light_grey']
                pygame.draw.rect(self.screen, bg_color, field['rect'], border_radius=6)

                border_color = self.colors['accent_grey'] if field['active'] else self.colors['grey']
                pygame.draw.rect(self.screen, border_color, field['rect'], 2, border_radius=6)

                display_text = field['text'] if field['text'] else field.get('hint', '')
                text_color = self.colors['white'] if field['text'] else self.colors['accent_grey']
                text_surface = self.fonts['medium'].render(display_text, True, text_color)

                max_width = field['rect'].width - 20
                if text_surface.get_width() > max_width:
                    display_text = "..." + display_text[-(max_width // 10):]
                    text_surface = self.fonts['medium'].render(display_text, True, text_color)

                text_rect = text_surface.get_rect(
                    midleft=(field['rect'].x + 15, field['rect'].y + field['rect'].height // 2))
                self.screen.blit(text_surface, text_rect)

                if field['active'] and int(time.time() * 2) % 2 == 0:
                    cursor_x = text_rect.right + 2 if field['text'] else field['rect'].x + 15
                    cursor_rect = pygame.Rect(cursor_x, field['rect'].y + 10, 2, field['rect'].height - 20)
                    pygame.draw.rect(self.screen, self.colors['white'], cursor_rect)

            mouse_pos = pygame.mouse.get_pos()
            for button in self.menu_buttons:
                button['rect'].x = side_panel_x + 25

                hover = button['rect'].collidepoint(mouse_pos)
                enabled = button.get('enabled', True)

                if not enabled:
                    bg_color = self.colors['grey']
                    text_color = self.colors['accent_grey']
                    border_color = self.colors['grey']
                elif hover:
                    bg_color = tuple(min(c + 20, 255) for c in self.colors['light_grey'])
                    text_color = self.colors['white']
                    border_color = self.colors['white']
                else:
                    bg_color = self.colors['light_grey']
                    text_color = self.colors['white']
                    border_color = self.colors['accent_grey']

                pygame.draw.rect(self.screen, bg_color, button['rect'], border_radius=8)
                pygame.draw.rect(self.screen, border_color, button['rect'], 2, border_radius=8)

                icon = self.fonts['medium'].render(button['icon'], True, text_color)
                icon_rect = icon.get_rect(midleft=(button['rect'].x + 20, button['rect'].centery))
                self.screen.blit(icon, icon_rect)

                text = self.fonts['medium'].render(button['text'], True, text_color)
                text_rect = text.get_rect(midleft=(button['rect'].x + 60, button['rect'].centery))
                self.screen.blit(text, text_rect)

    def render_top_panel(self):
        """Отрисовка верхней панели"""
        pygame.draw.rect(self.screen, self.colors['dark_grey'],
                         (0, 0, self.width, self.top_panel_height))
        pygame.draw.line(self.screen, self.colors['grey'],
                         (0, self.top_panel_height), (self.width, self.top_panel_height), 2)

        status_text = "CONNECTED" if self.connected else "DISCONNECTED"
        status_color = self.colors['success'] if self.connected else self.colors['error']

        indicator_radius = 6
        indicator_x = 25
        indicator_y = 25
        pygame.draw.circle(self.screen, status_color, (indicator_x, indicator_y), indicator_radius)
        pygame.draw.circle(self.screen, self.colors['white'], (indicator_x, indicator_y), indicator_radius, 1)

        status = self.fonts['small'].render(status_text, True, status_color)
        self.screen.blit(status, (45, 20))

        info_x = 200
        if self.username:
            user_text = self.fonts['tiny'].render(f"USER: {self.username}", True, self.colors['light_grey'])
            self.screen.blit(user_text, (info_x, 20))

        if self.character:
            char_type = self.character.get('character_type', 'default')
            char_text = self.fonts['tiny'].render(f"CHAR: {self.character['name']} ({char_type})", True,
                                                  self.colors['light_grey'])
            self.screen.blit(char_text, (info_x, 40))

        stats_x = self.width - 350

        fps_text = self.fonts['tiny'].render(f"FPS: {self.stats['fps']}", True, self.colors['light_grey'])
        self.screen.blit(fps_text, (stats_x, 20))

        players_text = self.fonts['tiny'].render(f"PLAYERS: {self.stats['players_online']}", True,
                                                 self.colors['light_grey'])
        self.screen.blit(players_text, (stats_x, 40))

        if self.in_world:
            cam_info = self.fonts['tiny'].render(
                f"CAMERA: {'FOLLOW' if self.camera.follow_player else 'FREE'}",
                True, self.colors['accent_grey']
            )
            self.screen.blit(cam_info, (stats_x + 120, 20))

            zoom_info = self.fonts['tiny'].render(
                f"ZOOM: {self.camera.zoom:.1f}x",
                True, self.colors['accent_grey']
            )
            self.screen.blit(zoom_info, (stats_x + 120, 40))

            if not self.side_panel_visible:
                ui_hint = self.fonts['tiny'].render("Press F1 to show UI", True, self.colors['warning'])
                self.screen.blit(ui_hint, (stats_x - 150, 60))

            chat_hint = self.fonts['tiny'].render("Press Enter to chat", True, self.colors['accent_grey'])
            self.screen.blit(chat_hint, (stats_x - 150, 80))

    def render_chat_history(self):
        """Отрисовка истории чата"""
        if not self.chat_messages:
            return

        max_messages = 5
        start_x = 10
        start_y = self.height - 140
        current_time = time.time()

        visible_messages = []
        for msg in reversed(self.chat_messages):
            age = current_time - msg['timestamp']

            if self.chat_active:
                visible_messages.append(msg)
            elif age < self.chat_message_lifetime:
                visible_messages.append(msg)

            if len(visible_messages) >= max_messages:
                break

        visible_messages.reverse()

        for i, msg_data in enumerate(visible_messages):
            message = msg_data['text']
            is_self = msg_data.get('is_self', False)
            age = current_time - msg_data['timestamp']

            if message.startswith("[SYSTEM]"):
                if "Connected" in message or "successful" in message or "Entered" in message:
                    color = self.colors['success']
                elif "error" in message.lower() or "[ERROR]" in message:
                    color = self.colors['error']
                else:
                    color = self.colors['accent_grey']
            elif is_self:
                color = tuple(min(c + 30, 255) for c in self.colors['player'])
            else:
                color = self.colors['white']

            alpha = 255
            if not self.chat_active and age > self.chat_message_lifetime - self.chat_message_fade_time:
                fade_progress = (age - (
                        self.chat_message_lifetime - self.chat_message_fade_time)) / self.chat_message_fade_time
                alpha = int(255 * (1 - fade_progress))

            text = self.fonts['tiny'].render(message, True, color)

            if alpha < 255:
                text.set_alpha(alpha)

            text_bg = pygame.Rect(start_x - 5, start_y + i * 22 - 3,
                                  text.get_width() + 10, text.get_height() + 6)

            bg_surface = pygame.Surface((text_bg.width, text_bg.height), pygame.SRCALPHA)
            bg_alpha = min(200, alpha)
            bg_surface.fill((*self.colors['dark_grey'][:3], bg_alpha))

            if alpha < 255:
                bg_surface.set_alpha(bg_alpha)

            self.screen.blit(bg_surface, text_bg)
            self.screen.blit(text, (start_x, start_y + i * 22))

    def render_chat_input(self):
        """Отрисовка поля ввода чата"""
        input_height = 40
        input_y = self.height - input_height - 10
        input_width = self.width - 20

        if self.chat_messages:
            max_messages = 10
            start_x = 10
            start_y = self.height - 140 - 30

            recent_messages = self.chat_messages[-max_messages:]

            for i, msg_data in enumerate(recent_messages):
                message = msg_data['text']
                is_self = msg_data.get('is_self', False)

                if message.startswith("[SYSTEM]"):
                    if "Connected" in message or "successful" in message or "Entered" in message:
                        color = self.colors['success']
                    elif "error" in message.lower() or "[ERROR]" in message:
                        color = self.colors['error']
                    else:
                        color = self.colors['accent_grey']
                elif is_self:
                    color = tuple(min(c + 30, 255) for c in self.colors['player'])
                else:
                    color = self.colors['white']

                text = self.fonts['tiny'].render(message, True, color)
                text_bg = pygame.Rect(start_x - 5, start_y + i * 22 - 3,
                                      text.get_width() + 10, text.get_height() + 6)

                bg_surface = pygame.Surface((text_bg.width, text_bg.height), pygame.SRCALPHA)
                bg_surface.fill((*self.colors['dark_grey'][:3], 230))
                self.screen.blit(bg_surface, text_bg)
                self.screen.blit(text, (start_x, start_y + i * 22))

        pygame.draw.rect(self.screen, self.colors['dark_grey'],
                         (10, input_y, input_width, input_height), border_radius=6)
        pygame.draw.rect(self.screen, self.colors['accent_grey'],
                         (10, input_y, input_width, input_height), 2, border_radius=6)

        label = self.fonts['small'].render("CHAT:", True, self.colors['white'])
        self.screen.blit(label, (20, input_y + 10))

        display_text = self.chat_input if self.chat_input else "Type your message..."
        text_color = self.colors['white'] if self.chat_input else self.colors['accent_grey']
        text = self.fonts['medium'].render(display_text, True, text_color)

        max_text_width = input_width - 100
        if text.get_width() > max_text_width:
            display_text = "..." + display_text[-(max_text_width // 10):]
            text = self.fonts['medium'].render(display_text, True, text_color)

        self.screen.blit(text, (80, input_y + 10))

        if int(time.time() * 2) % 2 == 0:
            cursor_x = 80 + text.get_width() + 2 if self.chat_input else 80
            cursor_rect = pygame.Rect(cursor_x, input_y + 12, 2, input_height - 24)
            pygame.draw.rect(self.screen, self.colors['white'], cursor_rect)

        hint = self.fonts['tiny'].render("Press ENTER to send, ESC to cancel", True, self.colors['accent_grey'])
        self.screen.blit(hint, (input_width // 2 - hint.get_width() // 2, input_y - 20))

    def render_esc_menu(self):
        """Отрисовка ESC меню"""
        anim_factor = self.menu_animation
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(150 * anim_factor)))
        self.screen.blit(overlay, (0, 0))

        menu_width = 400
        menu_height = 450
        menu_x = (self.width - menu_width) // 2
        menu_y = (self.height - menu_height) // 2
        anim_y = menu_y - (1 - anim_factor) * 50

        menu_bg = pygame.Rect(menu_x, anim_y, menu_width, menu_height)
        pygame.draw.rect(self.screen, self.colors['dark_grey'], menu_bg, border_radius=12)
        pygame.draw.rect(self.screen, self.colors['accent_grey'], menu_bg, 3, border_radius=12)

        title = self.fonts['large'].render("GAME MENU", True, self.colors['white'])
        title_rect = title.get_rect(center=(menu_x + menu_width // 2, anim_y + 50))
        self.screen.blit(title, title_rect)

        subtitle = self.fonts['tiny'].render("Press ESC to resume", True, self.colors['accent_grey'])
        subtitle_rect = subtitle.get_rect(center=(menu_x + menu_width // 2, anim_y + 85))
        self.screen.blit(subtitle, subtitle_rect)

        mouse_pos = pygame.mouse.get_pos()
        button_height = 55
        button_spacing = 8
        start_y = anim_y + 120

        for i, button in enumerate(self.esc_menu_buttons):
            button_rect = pygame.Rect(
                menu_x + 50,
                start_y + i * (button_height + button_spacing),
                menu_width - 100,
                button_height
            )

            hover = button_rect.collidepoint(mouse_pos)
            bg_color = tuple(min(c + 20, 255) for c in self.colors['light_grey']) if hover else self.colors[
                'light_grey']
            border_color = self.colors['white'] if hover else self.colors['accent_grey']

            pygame.draw.rect(self.screen, bg_color, button_rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, button_rect, 2, border_radius=8)

            icon = self.fonts['medium'].render(button['icon'], True, self.colors['white'])
            icon_rect = icon.get_rect(midleft=(button_rect.x + 20, button_rect.centery))
            self.screen.blit(icon, icon_rect)

            text = self.fonts['medium'].render(button['text'], True, self.colors['white'])
            text_rect = text.get_rect(midleft=(button_rect.x + 60, button_rect.centery))
            self.screen.blit(text, text_rect)

    def render_settings_menu(self):
        """Отрисовка меню настроек"""
        anim_factor = self.settings_animation
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(150 * anim_factor)))
        self.screen.blit(overlay, (0, 0))

        menu_width = 500
        menu_height = 500
        menu_x = (self.width - menu_width) // 2
        menu_y = (self.height - menu_height) // 2
        anim_y = menu_y - (1 - anim_factor) * 50

        menu_bg = pygame.Rect(menu_x, anim_y, menu_width, menu_height)
        pygame.draw.rect(self.screen, self.colors['dark_grey'], menu_bg, border_radius=12)
        pygame.draw.rect(self.screen, self.colors['accent_grey'], menu_bg, 3, border_radius=12)

        title = self.fonts['large'].render("SETTINGS", True, self.colors['white'])
        title_rect = title.get_rect(center=(menu_x + menu_width // 2, anim_y + 50))
        self.screen.blit(title, title_rect)

        subtitle = self.fonts['tiny'].render("Color Schemes", True, self.colors['accent_grey'])
        subtitle_rect = subtitle.get_rect(center=(menu_x + menu_width // 2, anim_y + 85))
        self.screen.blit(subtitle, subtitle_rect)

        mouse_pos = pygame.mouse.get_pos()
        theme_button_height = 45
        theme_button_spacing = 10
        theme_start_y = anim_y + 120

        for i, button in enumerate(self.theme_buttons):
            button_rect = pygame.Rect(
                menu_x + 50,
                theme_start_y + i * (theme_button_height + theme_button_spacing),
                menu_width - 100,
                theme_button_height
            )

            hover = button_rect.collidepoint(mouse_pos)
            selected = button.get('selected', False)

            if selected:
                bg_color = self.colors['player']
                border_color = self.colors['white']
                text_color = self.colors['white']
            elif hover:
                bg_color = tuple(min(c + 20, 255) for c in self.colors['light_grey'])
                border_color = self.colors['white']
                text_color = self.colors['white']
            else:
                bg_color = self.colors['light_grey']
                border_color = self.colors['accent_grey']
                text_color = self.colors['white']

            pygame.draw.rect(self.screen, bg_color, button_rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, button_rect, 2, border_radius=8)

            icon = self.fonts['medium'].render(button['icon'], True, text_color)
            icon_rect = icon.get_rect(midleft=(button_rect.x + 20, button_rect.centery))
            self.screen.blit(icon, icon_rect)

            text = self.fonts['medium'].render(button['text'], True, text_color)
            text_rect = text.get_rect(midleft=(button_rect.x + 60, button_rect.centery))
            self.screen.blit(text, text_rect)

            if selected:
                check = self.fonts['medium'].render("✓", True, self.colors['white'])
                check_rect = check.get_rect(midright=(button_rect.right - 20, button_rect.centery))
                self.screen.blit(check, check_rect)

        back_button_rect = pygame.Rect(
            menu_x + 50,
            anim_y + menu_height - 70,
            menu_width - 100,
            50
        )

        back_hover = back_button_rect.collidepoint(mouse_pos)
        back_bg_color = tuple(min(c + 20, 255) for c in self.colors['light_grey']) if back_hover else self.colors[
            'light_grey']
        back_border_color = self.colors['white'] if back_hover else self.colors['accent_grey']

        pygame.draw.rect(self.screen, back_bg_color, back_button_rect, border_radius=8)
        pygame.draw.rect(self.screen, back_border_color, back_button_rect, 2, border_radius=8)

        back_text = self.fonts['medium'].render("BACK TO MENU", True, self.colors['white'])
        back_text_rect = back_text.get_rect(center=back_button_rect.center)
        self.screen.blit(back_text, back_text_rect)

    def toggle_esc_menu(self):
        """Переключение ESC меню"""
        if self.show_settings_menu:
            self.close_settings()
        else:
            self.show_esc_menu = not self.show_esc_menu
            print(f"[UI] ESC Menu: {'Opened' if self.show_esc_menu else 'Closed'}")

    def resume_game(self):
        """Возобновление игры"""
        self.show_esc_menu = False
        print("[UI] Resuming game...")

    def open_settings(self):
        """Открытие настроек"""
        self.show_settings_menu = True
        self.show_esc_menu = False
        print("[UI] Opening settings...")

    def close_settings(self):
        """Закрытие настроек"""
        self.show_settings_menu = False
        print("[UI] Closing settings...")

    def toggle_ui_visibility(self):
        """Переключение видимости UI"""
        self.side_panel_visible = not self.side_panel_visible
        state = "shown" if self.side_panel_visible else "hidden"
        print(f"[UI] Side panel: {state}")

    def change_theme(self, theme_name):
        """Изменение цветовой схемы"""
        self.current_theme = theme_name
        self.config.set('ui.theme', theme_name)
        self.config.save()

        self.load_color_scheme()

        for button in self.theme_buttons:
            button['selected'] = (button['theme_key'] == theme_name)

        print(f"[UI] Changed theme to: {theme_name}")

    def disconnect_from_server(self):
        """Отключение от сервера"""
        if self.network and self.network.is_connected():
            self.network.disconnect()
            self.connected = False
            self.in_world = False
            self.show_esc_menu = False
            self.show_settings_menu = False
            self.side_panel_visible = True
            self.add_chat_message("[SYSTEM] Disconnected from server")
            print("[NETWORK] Disconnected from server")

    def connect_to_server(self):
        """Подключение к серверу"""
        if self.connection_in_progress:
            return

        host_field = next(f for f in self.input_fields if f['name'] == 'server_host')
        port_field = next(f for f in self.input_fields if f['name'] == 'server_port')

        host = host_field['text']
        port = port_field['text']

        self.connection_in_progress = True
        self.add_chat_message(f"[SYSTEM] Connecting to {host}:{port}...")

        try:
            if self.network and self.network.is_connected():
                self.network.disconnect()
                time.sleep(0.1)

            from network_client import NetworkClient
            self.network = NetworkClient(host, int(port))
            self.network.client_id = self.client_id

            if self.network.connect():
                self.connected = True
                self.add_chat_message(f"[SYSTEM] Connected to {host}:{port}")

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
                self.add_chat_message("[ERROR] Connection failed")

        except ValueError:
            self.add_chat_message("[ERROR] Invalid port number")
        except Exception as e:
            self.add_chat_message(f"[ERROR] {str(e)}")
        finally:
            self.connection_in_progress = False

    def show_login_field(self):
        """Показать поле логина"""
        for field in self.input_fields:
            if field['name'] == 'username':
                field['visible'] = True
                field['active'] = True
                self.active_input_field = self.input_fields.index(field)
                break

    def login(self):
        """Авторизация"""
        username_field = next(f for f in self.input_fields if f['name'] == 'username')
        self.username = username_field['text'].strip()

        if not self.username:
            self.add_chat_message("[ERROR] Enter username")
            return

        if not self.connected:
            self.add_chat_message("[ERROR] Not connected")
            return

        self.add_chat_message(f"[SYSTEM] Logging in as {self.username}...")

        data = {
            'type': 'auth',
            'client_id': self.client_id,
            'username': self.username,
            'timestamp': datetime.now().isoformat()
        }

        self.network.safe_send(data)

    def select_character(self):
        """Выбор персонажа через визуальное меню"""
        if not self.username:
            self.add_chat_message("[ERROR] Login first")
            return

        self.show_character_select = True
        self.character_selector = CharacterSelector(self.width, self.height)
        self.character_selector.load_characters()

        self.add_chat_message("[SYSTEM] Opening character selection...")
        print("[UI] Character selection opened")

    def confirm_character_selection(self):
        """Подтверждение выбора персонажа"""
        if not self.character_selector:
            return

        selected_char = self.character_selector.get_selected_character()
        if not selected_char:
            self.add_chat_message("[ERROR] No character selected")
            return

        self.show_character_select = False

        from character_manager import CharacterManager
        cm = CharacterManager()

        character_name = f"{self.username}_{selected_char['id']}"
        self.character = cm.create_default_character(character_name, self.username)

        self.character['character_type'] = selected_char['id']
        self.character['assets_path'] = selected_char['folder']

        cm.save_character(self.character)
        self.add_chat_message(f"[SYSTEM] Selected: {selected_char['name']}")

        self.player_animation = AnimatedCharacter(self.character)
        if self.player_animation.load_animations():
            self.player_animation.set_animation("idle")
            print(f"[DEBUG] Анимация загружена для {selected_char['id']}")
        else:
            print(f"[DEBUG] Не удалось загрузить анимацию для {selected_char['id']}")

        if self.connected and self.character:
            data = {
                'type': 'character_select',
                'client_id': self.client_id,
                'character_id': self.character['id'],
                'character_data': self.character,
                'character_type': selected_char['id'],
                'timestamp': datetime.now().isoformat()
            }
            self.network.safe_send(data)

        self.character_selected = True
        self.game_state = GameState.IN_GAME
        self.update_join_world_button()
        self.add_chat_message("[SYSTEM] Character ready. Click 'ENTER WORLD'")

        self.character_selector = None

    def test_animations(self):
        """Тестирование анимаций"""
        print("\n=== ТЕСТ АНИМАЦИЙ ===")
        print(f"Мой персонаж: {self.character.get('name') if self.character else 'Нет'}")
        print(f"Тип: {self.character.get('character_type') if self.character else 'Нет'}")
        print(f"Анимация: {'Есть' if self.player_animation else 'Нет'}")

        print(f"\nДругие игроки: {len(self.other_players)}")
        for player_id, player in self.other_players.items():
            player_data = self.other_players_data.get(player_id, {})
            print(
                f"  {player.name}: тип={player.character_type}, анимация={'Есть' if hasattr(player, 'animation') and player.animation else 'Нет'}")

        self.reload_all_animations()

        self.add_chat_message("[TEST] Перезагружены анимации")

    def reload_all_animations(self):
        """Перезагрузка анимаций всех игроков"""
        print("[DEBUG] Перезагрузка анимаций всех игроков")

        if self.character and self.player_animation:
            self.player_animation.load_animations()

        for player_id, player in self.other_players.items():
            player_data = self.other_players_data.get(player_id, {})
            if hasattr(player, 'init_animation'):
                player.init_animation(player_data)

    def set_player_animation(self, animation_name):
        """Установка анимации для игрока"""
        if hasattr(self, 'player_animation') and self.player_animation:
            return self.player_animation.set_animation(animation_name)
        return False

    def join_world(self):
        """Вход в игровой мир"""
        if not self.character:
            self.add_chat_message("[ERROR] Select character first")
            return

        if not self.connected:
            self.add_chat_message("[ERROR] Not connected")
            return

        if self.in_world:
            self.add_chat_message("[ERROR] Already in world")
            return

        self.add_chat_message(f"[SYSTEM] Entering world with {self.character['name']}...")

        data = {
            'type': 'join_world',
            'client_id': self.client_id,
            'character_id': self.character['id'],
            'character_name': self.character['name'],
            'character_type': self.character.get('character_type', 'default'),
            'character_data': self.character,
            'timestamp': datetime.now().isoformat()
        }

        self.network.safe_send(data)

    def quit_game(self):
        """Выход из игры"""
        if self.in_world and self.connected and self.character:
            try:
                data = {
                    'type': 'leave_world',
                    'client_id': self.client_id,
                    'character_id': self.character['id'],
                    'character_name': self.character['name'],
                    'timestamp': datetime.now().isoformat()
                }
                self.network.safe_send(data)
            except:
                pass

        self.running = False


def main():
    """Главная функция"""
    print("=" * 50)
    print("DPP2 Graphic Client - Camera Follow System")
    print("=" * 50)

    try:
        app = DPP2GraphicClient()
        app.run()
    except Exception as e:
        print(f"Startup error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()