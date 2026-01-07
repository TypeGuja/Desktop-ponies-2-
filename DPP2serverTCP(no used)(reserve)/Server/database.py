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
        self.data = {
            'players': {},
            'characters': {},
            'world_data': {
                'name': 'Эквестрия',
                'time': '12:00',
                'weather': 'солнечно',
                'day': 1,
                'online_players': 0
            },
            'gifct_settings': {
                'Gifct1': 'Основная способность',
                'Gifct2': 'Вторичная способность'
            },
            'server_stats': {
                'total_players': 0,
                'total_characters': 0,
                'total_playtime': 0,
                'start_time': datetime.now().isoformat()
            }
        }

        self.load()

        # Автосохранение
        self.autosave_thread = threading.Thread(target=self.autosave, daemon=True)
        self.autosave_thread.start()

    def load(self):
        """Загрузка данных из файла"""
        try:
            if Path(self.db_path).exists():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    self.data.update(loaded_data)
                print(f"[DATABASE] Данные загружены из {self.db_path}")
        except Exception as e:
            print(f"[DATABASE] Ошибка загрузки: {e}")

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
        player_id = str(uuid.uuid4())

        # Проверяем уникальность имени
        for player in self.data['players'].values():
            if player['username'].lower() == username.lower():
                return None, "Имя пользователя уже занято"

        # Хэшируем пароль
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        player_data = {
            'id': player_id,
            'username': username,
            'password_hash': password_hash,
            'email': email,
            'registration_date': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat(),
            'characters': [],
            'friends': [],
            'settings': {
                'theme': 'default',
                'language': 'ru'
            },
            'stats': {
                'playtime': 0,
                'characters_created': 0,
                'last_character_id': None
            }
        }

        self.data['players'][player_id] = player_data
        self.data['server_stats']['total_players'] += 1
        self.save()

        return player_id, player_data

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

        character = {
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
            'position': {
                'x': 100,
                'y': 100,
                'map': 'start_city',
                'zone': 'центральная площадь'
            },
            'stats': {
                'strength': character_data.get('strength', 10),
                'agility': character_data.get('agility', 10),
                'intelligence': character_data.get('intelligence', 10),
                'vitality': character_data.get('vitality', 10),
                'luck': character_data.get('luck', 5)
            },
            'skills': [],
            'inventory': [],
            'equipment': {
                'weapon': None,
                'armor': None,
                'helmet': None,
                'gloves': None,
                'boots': None,
                'accessory1': None,
                'accessory2': None
            },
            'appearance': character_data.get('appearance', {
                'hair_color': '#8B4513',
                'eye_color': '#0000FF',
                'skin_tone': '#FFD700',
                'height': 180,
                'body_type': 'average'
            }),
            'gifct': {
                'Gifct1': character_data.get('gifct1', self.data['gifct_settings']['Gifct1']),
                'Gifct2': character_data.get('gifct2', self.data['gifct_settings']['Gifct2'])
            },
            'creation_time': datetime.now().isoformat(),
            'last_played': datetime.now().isoformat(),
            'playtime': 0,
            'achievements': [],
            'quests': {
                'active': [],
                'completed': []
            }
        }

        self.data['characters'][character_id] = character

        # Добавляем персонажа в список персонажей игрока
        if player_id in self.data['players']:
            if 'characters' not in self.data['players'][player_id]:
                self.data['players'][player_id]['characters'] = []
            self.data['players'][player_id]['characters'].append(character_id)
            self.data['players'][player_id]['stats']['characters_created'] += 1
            self.data['players'][player_id]['stats']['last_character_id'] = character_id

        self.data['server_stats']['total_characters'] += 1
        self.save()

        return character_id, character

    def get_character(self, character_id):
        """Получение данных персонажа"""
        return self.data['characters'].get(character_id)

    def get_player_characters(self, player_id):
        """Получение всех персонажей игрока"""
        if player_id not in self.data['players']:
            return []

        characters = []
        for char_id in self.data['players'][player_id].get('characters', []):
            if char_id in self.data['characters']:
                characters.append(self.data['characters'][char_id])

        return characters

    def update_character(self, character_id, updates):
        """Обновление данных персонажа"""
        if character_id in self.data['characters']:
            if 'playtime' in updates:
                old_playtime = self.data['characters'][character_id].get('playtime', 0)
                self.data['server_stats']['total_playtime'] += (updates['playtime'] - old_playtime)

            self.data['characters'][character_id].update(updates)
            self.data['characters'][character_id]['last_played'] = datetime.now().isoformat()
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
                if character_id in self.data['players'][player_id].get('characters', []):
                    self.data['players'][player_id]['characters'].remove(character_id)

            # Удаляем персонажа
            del self.data['characters'][character_id]
            self.data['server_stats']['total_characters'] -= 1
            self.save()
            return True
        return False

    # === GIFCT НАСТРОЙКИ ===
    def get_gifct_settings(self):
        """Получение текущих настроек Gifct"""
        return self.data['gifct_settings']

    def update_gifct_settings(self, gifct1=None, gifct2=None):
        """Обновление настроек Gifct"""
        updated = False

        if gifct1 is not None:
            self.data['gifct_settings']['Gifct1'] = gifct1
            updated = True

        if gifct2 is not None:
            self.data['gifct_settings']['Gifct2'] = gifct2
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

    # В database.py добавьте в класс Database:

    def get_gifct_settings(self):
        """Получение текущих настроек Gifct"""
        if 'gifct_settings' not in self.data:
            self.data['gifct_settings'] = {
                'gifct_enabled': {
                    'Gifct1': True,
                    'Gifct2': True
                },
                'gifct_configs': {
                    'Gifct1': 'Основная способность',
                    'Gifct2': 'Вторичная способность'
                }
            }
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