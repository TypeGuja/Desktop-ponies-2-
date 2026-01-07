#!/usr/bin/env python3
"""
Config - Конфигурация клиента (UDP версия)
"""

import json
import os


class Config:
    def __init__(self, filename='config.json'):
        self.filename = filename
        self.config = self.load()

    def load(self):
        """Загрузка конфигурации"""
        default_config = {
            'graphics': {
                'width': 1200,
                'height': 800,
                'fullscreen': False,
                'vsync': True,
                'fps_limit': 60
            },
            'controls': {
                'move_forward': ['w', 'up'],
                'move_backward': ['s', 'down'],
                'move_left': ['a', 'left'],
                'move_right': ['d', 'right'],
                'move_up': 'space',
                'move_down': 'lshift',
                'chat': 'return',
                'menu': 'escape',
                'zoom_in': ['plus', 'equals'],
                'zoom_out': 'minus',
                'toggle_ui': 'f1'
            },
            'network': {
                'protocol': 'udp',
                'default_host': '147.185.221.27',
                'default_port': 22153,
                'timeout': 2.0,
                'reconnect_attempts': 3,
                'udp_max_packet_size': 1400,
                'udp_heartbeat_interval': 1.0,
                'udp_position_update_rate': 0.016
            },
            'game': {
                'movement_speed': 200.0,
                'position_update_rate': 0.1,
                'chat_history_size': 10,
                'camera_follow_speed': 0.15,
                'camera_smoothing': True,
                'hide_ui_in_world': True
            },
            'ui': {
                'theme': 'black',
                'show_fps': True,
                'show_stats': True,
                'menu_animation_speed': 0.3,
                'side_panel_visible': True,
                'side_panel_auto_hide': True,
                'side_panel_width': 320,
                'top_panel_height': 70,
                'bottom_panel_height': 40
            },
            'camera': {
                'follow_player': True,
                'smoothing_factor': 0.1,
                'zoom_speed': 0.1,
                'min_zoom': 0.5,
                'max_zoom': 3.0,
                'default_zoom': 1.2
            },
            'color_schemes': {
                'black': {
                    'name': 'Black',
                    'black': [10, 10, 15],
                    'dark_grey': [30, 30, 35],
                    'grey': [50, 50, 60],
                    'light_grey': [80, 80, 90],
                    'white': [240, 240, 245],
                    'accent_grey': [120, 120, 130],
                    'success': [100, 220, 100],
                    'error': [220, 100, 100],
                    'warning': [220, 180, 100],
                    'player': [80, 160, 240],
                    'other_player': [240, 100, 100]
                },
                'grey': {
                    'name': 'Grey',
                    'black': [40, 40, 45],
                    'dark_grey': [60, 60, 70],
                    'grey': [80, 80, 90],
                    'light_grey': [120, 120, 130],
                    'white': [250, 250, 255],
                    'accent_grey': [160, 160, 170],
                    'success': [120, 200, 120],
                    'error': [200, 100, 100],
                    'warning': [200, 160, 100],
                    'player': [60, 140, 220],
                    'other_player': [220, 80, 80]
                },
                'white': {
                    'name': 'White',
                    'black': [245, 245, 250],
                    'dark_grey': [220, 220, 230],
                    'grey': [190, 190, 200],
                    'light_grey': [160, 160, 170],
                    'white': [30, 30, 35],
                    'accent_grey': [100, 100, 110],
                    'success': [80, 180, 80],
                    'error': [180, 80, 80],
                    'warning': [180, 140, 80],
                    'player': [40, 120, 200],
                    'other_player': [200, 60, 60]
                }
            }
        }

        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    user_config = json.load(f)
                    # Объединяем конфигурации
                    self.merge_dicts(default_config, user_config)
            except:
                pass

        return default_config

    def merge_dicts(self, base, new):
        """Рекурсивное объединение словарей"""
        for key, value in new.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self.merge_dicts(base[key], value)
            else:
                base[key] = value

    def save(self):
        """Сохранение конфигурации"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except:
            return False

    def get(self, key, default=None):
        """Получение значения по ключу"""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key, value):
        """Установка значения"""
        keys = key.split('.')
        config = self.config

        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_color_scheme(self, theme_name=None):
        """Получение цветовой схемы"""
        if theme_name is None:
            theme_name = self.get('ui.theme', 'black')

        schemes = self.get('color_schemes', {})
        if theme_name in schemes:
            return schemes[theme_name]

        # Возвращаем черную схему по умолчанию
        return schemes.get('black', {})

    def get_available_themes(self):
        """Получение списка доступных тем"""
        schemes = self.get('color_schemes', {})
        return list(schemes.keys())


# Глобальный экземпляр конфигурации
config = Config()