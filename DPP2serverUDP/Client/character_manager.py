# [file name]: character_manager.py
# [file content begin]
#!/usr/bin/env python3
"""
Character Manager - Управление персонажами
"""

import json
import os
import uuid
from datetime import datetime


class CharacterManager:
    def __init__(self, filename='characters.json'):
        self.filename = filename

    def load_characters(self, username):
        """Загрузка персонажей пользователя"""
        if not os.path.exists(self.filename):
            return []

        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(username, [])
        except:
            return []

    def save_character(self, character):
        """Сохранение персонажа"""
        username = character.get('owner')
        if not username:
            return False

        # Загружаем существующие данные
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                data = {}
        else:
            data = {}

        # Инициализируем список персонажей
        if username not in data:
            data[username] = []

        # Проверяем, существует ли персонаж
        char_id = character.get('id')
        for i, existing in enumerate(data[username]):
            if existing.get('id') == char_id:
                data[username][i] = character  # Обновляем
                break
        else:
            data[username].append(character)  # Добавляем новый

        # Сохраняем
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False

    def update_position(self, character_id, username, position, character=None):
        """Обновление позиции персонажа"""
        username = character.get('owner')
        if not username:
            return False

        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                data = {}

        if username in data:
            for i, char in enumerate(data[username]):
                if char.get('id') == character_id:
                    data[username][i]['position'] = position
                    try:
                        with open(self.filename, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        return True
                    except:
                        return False
        return False

    def create_default_character(self, name, username, character_type="default"):
        """Создание персонажа по умолчанию с указанием типа"""
        return {
            'id': str(uuid.uuid4()),
            'name': name,
            'owner': username,
            'character_type': character_type,
            'created': datetime.now().isoformat(),
            'level': 1,
            'health': 100,
            'position': {'x': 0, 'y': 0, 'z': 0},
            'rotation': {'x': 0, 'y': 0, 'z': 0},
            'inventory': [],
            'stats': {
                'strength': 10,
                'agility': 10,
                'intelligence': 10
            }
        }

    def delete_character(self, character_id, username):
        """Удаление персонажа"""
        if not os.path.exists(self.filename):
            return False

        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if username in data:
                initial_count = len(data[username])
                data[username] = [c for c in data[username] if c.get('id') != character_id]

                if len(data[username]) != initial_count:
                    with open(self.filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    return True
        except:
            pass

        return False
# [file content end]