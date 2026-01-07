import json
import threading
import time
from datetime import datetime
from pathlib import Path
import uuid
import hashlib


class Database:
    def __init__(self, db_path='game_server_db.json'):
        self.db_path = db_path
        self.save_lock = threading.Lock()
        self.save_interval = 30
        self.last_save = time.time()

        # Инициализация структуры данных
        self.data = self._init_data_structure()
        self.load()

        # Автосохранение
        self.autosave_thread = threading.Thread(target=self.autosave, daemon=True)
        self.autosave_thread.start()

    def _init_data_structure(self):
        """Инициализация структуры данных"""
        return {
            'players': {},
            'characters': {},
            'world_data': self._default_world_data(),
            'gifct_settings': self._default_gifct_settings(),
            'server_stats': self._default_server_stats()
        }

    def _default_world_data(self):
        """Данные мира по умолчанию"""
        return {
            'name': 'Эквестрия',
            'time': '12:00',
            'weather': 'солнечно',
            'day': 1,
            'online_players': 0,
            'protocol': 'udp',
            'udp_port': 5555
        }

    def _default_gifct_settings(self):
        """Настройки Gifct по умолчанию"""
        return {
            'gifct_enabled': {'Gifct1': True, 'Gifct2': True},
            'gifct_configs': {
                'Gifct1': 'Основная способность',
                'Gifct2': 'Вторичная способность'
            }
        }

    def _default_server_stats(self):
        """Статистика сервера по умолчанию"""
        return {
            'total_players': 0,
            'total_characters': 0,
            'total_playtime': 0,
            'start_time': datetime.now().isoformat(),
            'protocol': 'udp'
        }

    def load(self):
        """Загрузка данных из файла"""
        try:
            if Path(self.db_path).exists():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    self._merge_data(loaded_data)
                print(f"[DATABASE] UDP Данные загружены из {self.db_path}")
        except Exception as e:
            print(f"[DATABASE] Ошибка загрузки: {e}")

    def _merge_data(self, loaded_data):
        """Объединение загруженных данных с дефолтными"""
        for key in self.data:
            if key in loaded_data:
                if isinstance(self.data[key], dict):
                    self.data[key].update(loaded_data[key])
                else:
                    self.data[key] = loaded_data[key]

    def save(self):
        """Сохранение данных в файл"""
        with self.save_lock:
            try:
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
                self.last_save = time.time()
            except Exception as e:
                print(f"[DATABASE] Ошибка сохранения: {e}")

    def autosave(self):
        """Автоматическое сохранение"""
        while True:
            time.sleep(self.save_interval)
            if time.time() - self.last_save >= self.save_interval:
                self.save()

    # === ИГРОКИ ===
    def register_player(self, username, password, email=None):
        """Регистрация нового игрока"""
        # Проверка уникальности имени
        if self._username_exists(username):
            return None, "Имя пользователя уже занято"

        player_id = str(uuid.uuid4())
        player_data = self._create_player_data(player_id, username, password, email)

        self.data['players'][player_id] = player_data
        self.data['server_stats']['total_players'] += 1
        self.save()

        return player_id, player_data

    def _username_exists(self, username):
        """Проверка существования имени пользователя"""
        return any(p['username'].lower() == username.lower()
                   for p in self.data['players'].values())

    def _create_player_data(self, player_id, username, password, email):
        """Создание данных игрока"""
        return {
            'id': player_id,
            'username': username,
            'password_hash': hashlib.sha256(password.encode()).hexdigest(),
            'email': email,
            'registration_date': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat(),
            'characters': [],
            'friends': [],
            'settings': {'theme': 'default', 'language': 'ru'},
            'stats': {
                'playtime': 0,
                'characters_created': 0,
                'last_character_id': None
            }
        }

    def authenticate_player(self, username, password):
        """Аутентификация игрока"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        for player_id, player in self.data['players'].items():
            if player['username'].lower() == username.lower():
                if player['password_hash'] == password_hash:
                    player['last_login'] = datetime.now().isoformat()
                    self.save()
                    return player_id, player
                else:
                    return None, "Неверный пароль"

        return None, "Пользователь не найден"

    def get_player(self, player_id):
        """Получение данных игрока"""
        return self.data['players'].get(player_id)

    def update_player(self, player_id, updates):
        """Обновление данных игрока"""
        if player_id in self.data['players']:
            self.data['players'][player_id].update(updates)
            self.save()
            return True
        return False

    # === ПЕРСОНАЖИ ===
    def create_character(self, player_id, character_data):
        """Создание нового персонажа"""
        character_id = str(uuid.uuid4())
        character = self._create_character_data(character_id, player_id, character_data)

        self.data['characters'][character_id] = character
        self._add_character_to_player(player_id, character_id)
        self.data['server_stats']['total_characters'] += 1
        self.save()

        return character_id, character

    def _create_character_data(self, character_id, player_id, character_data):
        """Создание данных персонажа"""
        return {
            'id': character_id,
            'player_id': player_id,
            'name': character_data.get('name', 'Безымянный'),
            'race': character_data.get('race', 'человек'),
            'class': character_data.get('class', 'воин'),
            'level': 1,
            'experience': 0,
            'health': 100,
            'max_health': 100,
            'mana': 50,
            'max_mana': 50,
            'stamina': 100,
            'gold': 100,
            'position': character_data.get('position', self._default_position()),
            'stats': character_data.get('stats', self._default_stats(character_data)),
            'skills': [],
            'inventory': [],
            'equipment': self._default_equipment(),
            'appearance': character_data.get('appearance', self._default_appearance()),
            'gifct': character_data.get('gifct', self._default_gifct_config()),
            'creation_time': datetime.now().isoformat(),
            'last_played': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'playtime': 0,
            'achievements': [],
            'quests': {'active': [], 'completed': []}
        }

    def _default_position(self):
        """Позиция по умолчанию"""
        return {
            'x': 100, 'y': 100, 'z': 0,
            'map': 'start_city', 'zone': 'центральная площадь'
        }

    def _default_stats(self, character_data):
        """Характеристики по умолчанию"""
        return {
            'strength': character_data.get('strength', 10),
            'agility': character_data.get('agility', 10),
            'intelligence': character_data.get('intelligence', 10),
            'vitality': character_data.get('vitality', 10),
            'luck': character_data.get('luck', 5)
        }

    def _default_equipment(self):
        """Экипировка по умолчанию"""
        return {
            'weapon': None, 'armor': None, 'helmet': None,
            'gloves': None, 'boots': None, 'accessory1': None, 'accessory2': None
        }

    def _default_appearance(self):
        """Внешность по умолчанию"""
        return {
            'hair_color': '#8B4513', 'eye_color': '#0000FF',
            'skin_tone': '#FFD700', 'height': 180, 'body_type': 'average'
        }

    def _default_gifct_config(self):
        """Конфигурация Gifct по умолчанию"""
        return {
            'Gifct1': self.data['gifct_settings']['gifct_configs']['Gifct1'],
            'Gifct2': self.data['gifct_settings']['gifct_configs']['Gifct2']
        }

    def _add_character_to_player(self, player_id, character_id):
        """Добавление персонажа игроку"""
        if player_id in self.data['players']:
            player = self.data['players'][player_id]
            if 'characters' not in player:
                player['characters'] = []
            player['characters'].append(character_id)
            player['stats']['characters_created'] += 1
            player['stats']['last_character_id'] = character_id

    def get_character(self, character_id):
        """Получение данных персонажа"""
        return self.data['characters'].get(character_id)

    def get_player_characters(self, player_id):
        """Получение всех персонажей игрока"""
        if player_id not in self.data['players']:
            return []

        return [self.data['characters'][char_id]
                for char_id in self.data['players'][player_id].get('characters', [])
                if char_id in self.data['characters']]

    def update_character(self, character_id, updates):
        """Обновление данных персонажа"""
        if character_id in self.data['characters']:
            character = self.data['characters'][character_id]

            # Обновление общего времени игры
            if 'playtime' in updates:
                old_playtime = character.get('playtime', 0)
                self.data['server_stats']['total_playtime'] += (updates['playtime'] - old_playtime)

            character.update(updates)
            character['last_played'] = datetime.now().isoformat()

            # Для UDP обновляем время активности
            if 'position' in updates or 'last_activity' not in updates:
                character['last_activity'] = datetime.now().isoformat()

            self.save()
            return True
        return False

    def delete_character(self, character_id):
        """Удаление персонажа"""
        if character_id in self.data['characters']:
            character = self.data['characters'][character_id]
            player_id = character.get('player_id')

            # Удаляем из списка персонажей игрока
            if player_id and player_id in self.data['players']:
                player = self.data['players'][player_id]
                if character_id in player.get('characters', []):
                    player['characters'].remove(character_id)

            # Удаляем персонажа
            del self.data['characters'][character_id]
            self.data['server_stats']['total_characters'] -= 1
            self.save()
            return True
        return False

    # === GIFCT НАСТРОЙКИ ===
    def get_gifct_settings(self):
        """Получение текущих настроек Gifct"""
        if 'gifct_settings' not in self.data:
            self.data['gifct_settings'] = self._default_gifct_settings()
            self.save()
        return self.data['gifct_settings']

    def update_gifct_settings(self, gifct_enabled=None, gifct_configs=None):
        """Обновление настроек Gifct"""
        if 'gifct_settings' not in self.data:
            self.get_gifct_settings()

        updated = False

        if gifct_enabled:
            for key, value in gifct_enabled.items():
                if key in self.data['gifct_settings']['gifct_enabled']:
                    self.data['gifct_settings']['gifct_enabled'][key] = value
                    updated = True

        if gifct_configs:
            for key, value in gifct_configs.items():
                if key in self.data['gifct_settings']['gifct_configs']:
                    self.data['gifct_settings']['gifct_configs'][key] = value
                    updated = True

        if updated:
            self.save()

        return updated

    # === МИР ===
    def get_world_data(self):
        """Получение данных мира"""
        return self.data['world_data']

    def update_world_data(self, updates):
        """Обновление данных мира"""
        self.data['world_data'].update(updates)
        self.save()

    # === СТАТИСТИКА ===
    def get_server_stats(self):
        """Получение статистики сервера"""
        return self.data['server_stats']

    def increment_online_players(self):
        """Увеличение счетчика онлайн игроков"""
        self.data['world_data']['online_players'] += 1
        self.save()

    def decrement_online_players(self):
        """Уменьшение счетчика онлайн игроков"""
        if self.data['world_data']['online_players'] > 0:
            self.data['world_data']['online_players'] -= 1
            self.save()

    # === ПОИСК ===
    def find_character_by_name(self, character_name):
        """Поиск персонажа по имени"""
        for character in self.data['characters'].values():
            if character['name'].lower() == character_name.lower():
                return character
        return None

    def find_player_by_username(self, username):
        """Поиск игрока по имени пользователя"""
        for player in self.data['players'].values():
            if player['username'].lower() == username.lower():
                return player
        return None