#!/usr/bin/env python3
"""
Config - Конфигурация клиента
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
                'width': 1024,
                'height': 768,
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
                'zoom_in': ['plus', 'equals'],
                'zoom_out': 'minus'
            },
            'network': {
                'default_host': '127.0.0.1',
                'default_port': 5555,
                'timeout': 5,
                'reconnect_attempts': 3
            },
            'game': {
                'movement_speed': 200.0,
                'position_update_rate': 0.1,
                'chat_history_size': 10
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


# Глобальный экземпляр конфигурации
config = Config()