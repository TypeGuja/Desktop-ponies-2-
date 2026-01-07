import time
import random
from datetime import datetime


class GameLogic:
    def __init__(self, database):
        self.db = database

        # Инициализация мира
        self.world = self.db.get_world_data()
        if not self.world or 'name' not in self.world:
            self.world = {
                'name': 'Эквестрия',
                'time': '12:00',
                'weather': 'солнечно',
                'day': 1,
                'online_players': 0
            }
            self.db.update_world_data(self.world)

        self.online_players = {}  # client_id -> player_id
        self.active_characters = {}  # client_id -> character_data
        self.character_clients = {}  # character_id -> client_id (обратная связь)
        self.game_tick = 0

        print(f"[GAME] Мир инициализирован: {self.world['name']}")
        print(f"[GAME] Время: {self.world['time']}, Погода: {self.world['weather']}")

    # ==================== ГЛАВНЫЙ МЕТОД ДОБАВЛЕН ====================
    def update_world(self):
        """Обновление состояния мира"""
        self.game_tick += 1

        # Логируем редко
        if self.game_tick % 100 == 0:
            print(f"[GAME] Tick: {self.game_tick}")

        # Обновляем время каждые 60 тиков (1 минута игрового времени)
        if self.game_tick % 60 == 0:
            update = self._update_time()
            if update:
                return update

        # Обновляем погоду каждые 300 тиков
        if self.game_tick % 300 == 0:
            update = self._update_weather()
            if update:
                return update

        # Автосохранение активных персонажей каждые 600 тиков
        if self.game_tick % 600 == 0:
            self._auto_save_characters()

        return None  # <-- ВАЖНО: возвращаем None если нечего обновлять

    def _update_time(self):
        """Обновление игрового времени"""
        current_time = self.world['time']
        hours, minutes = map(int, current_time.split(':'))

        minutes += 1
        if minutes >= 60:
            minutes = 0
            hours += 1
            if hours >= 24:
                hours = 0
                self.world['day'] += 1

        self.world['time'] = f"{hours:02d}:{minutes:02d}"
        self.db.update_world_data(self.world)

        # Рассылаем обновление времени
        return {
            'target': 'broadcast',
            'data': {
                'type': 'world_update',
                'update_type': 'time',
                'time': self.world['time'],
                'day': self.world['day'],
                'timestamp': time.time()
            }
        }

    def _update_weather(self):
        """Обновление погоды"""
        weather_types = ['солнечно', 'дождь', 'облачно', 'туман', 'снег']
        new_weather = random.choice(weather_types)

        if new_weather != self.world['weather']:
            self.world['weather'] = new_weather
            self.db.update_world_data(self.world)

            return {
                'target': 'broadcast',
                'data': {
                    'type': 'world_update',
                    'update_type': 'weather',
                    'weather': new_weather,
                    'timestamp': time.time()
                }
            }

        return None

    def _auto_save_characters(self):
        """Автосохранение активных персонажей"""
        for client_id, character in self.active_characters.items():
            self.db.update_character(character['id'], {
                'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
                'last_played': datetime.now().isoformat()
            })

    # ==================== КОНЕЦ ДОБАВЛЕННОГО КОДА ====================

    def handle_message(self, message):
        """Обработка входящих сообщений от клиентов - ОБНОВЛЕННАЯ ВЕРСИЯ"""
        msg_type = message.get('type')
        client_id = message.get('client_id')

        print(f"[GAME] Обработка сообщения от {client_id}: {msg_type}")

        # ОБНОВЛЕННЫЕ ОБРАБОТЧИКИ ДЛЯ ГРАФИЧЕСКОГО КЛИЕНТА
        if msg_type == 'auth':
            return self.handle_auth(client_id, message)
        elif msg_type == 'character_select':
            return self.handle_character_select(client_id, message)
        elif msg_type == 'join_world':
            return self.handle_join_world(client_id, message)
        elif msg_type == 'position_update':
            return self.handle_position_update(client_id, message)
        elif msg_type == 'chat_message':
            return self.handle_chat(client_id, message)
        elif msg_type == 'leave_world':
            return self.handle_leave_world(client_id, message)
        elif msg_type == 'test':
            return self.handle_ping(client_id, message)

        # Старые обработчики для совместимости
        handlers = {
            'register': self.handle_register,
            'login': self.handle_login,
            'logout': self.handle_logout,
            'create_character': self.handle_create_character,
            'select_character': self.handle_select_character,
            'delete_character': self.handle_delete_character,
            'get_characters': self.handle_get_characters,
            'character_move': self.handle_character_move,
            'character_action': self.handle_character_action,
            'update_gifct': self.handle_update_gifct,
            'get_gifct_settings': self.handle_get_gifct_settings,
            'ping': self.handle_ping,
            'get_world_info': self.handle_get_world_info,
            'save_character': self.handle_save_character,
        }

        handler = handlers.get(msg_type)
        if handler:
            return handler(client_id, message)

        print(f"[GAME] Неизвестный тип сообщения: {msg_type}")
        return self.error_response(client_id, f'Неизвестный тип сообщения: {msg_type}')

    def handle_auth(self, client_id, message):
        """Обработка упрощенной аутентификации для графического клиента"""
        print(f"[GAME] Обработка auth от {client_id}")

        username = message.get('username')
        if not username:
            return self.error_response(client_id, 'Не указано имя пользователя')

        # Используем существующего или создаем нового игрока
        existing_player = self.db.find_player_by_username(username)

        if existing_player:
            player_id = existing_player['id']
            print(f"[GAME] Использован существующий игрок: {player_id}")
        else:
            # Создаем нового игрока
            player_id, player = self.db.register_player(
                username,
                'default_password',  # Пароль по умолчанию
                f'{username}@example.com'
            )
            print(f"[GAME] Создан новый игрок: {player_id}")

        # Добавляем в онлайн игроков
        self.online_players[client_id] = player_id
        self.db.increment_online_players()

        return [{
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'auth_response',
                'success': True,
                'player_id': player_id,
                'username': username,
                'message': 'Аутентификация успешна'
            }
        }]

    def handle_character_select(self, client_id, message):
        """Обработка выбора персонажа от графического клиента"""
        print(f"[GAME] Обработка character_select от {client_id}")

        if client_id not in self.online_players:
            return self.error_response(client_id, 'Сначала пройдите аутентификацию')

        character_id = message.get('character_id')
        character_data = message.get('character_data')

        if not character_id:
            return self.error_response(client_id, 'Не указан ID персонажа')

        # Проверяем, существует ли персонаж в базе
        character = self.db.get_character(character_id)
        if not character:
            # Если персонажа нет, создаем его из полученных данных
            player_id = self.online_players[client_id]
            if character_data:
                # Используем полученные данные
                character_id, character = self.db.create_character(player_id, character_data)
                print(f"[GAME] Создан персонаж из данных клиента: {character['name']}")
            else:
                return self.error_response(client_id, 'Персонаж не найден и нет данных для создания')
        else:
            print(f"[GAME] Использован существующий персонаж: {character['name']}")

        # Сохраняем выбранного персонажа
        self.active_characters[client_id] = character.copy()
        self.character_clients[character['id']] = client_id

        # Обновляем время последней игры
        self.db.update_character(character['id'], {
            'last_played': datetime.now().isoformat()
        })

        return [{
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'character_select_response',
                'success': True,
                'character_id': character['id'],
                'character_name': character['name'],
                'message': f'Персонаж {character["name"]} выбран'
            }
        }]

    def handle_join_world(self, client_id, message):
        """Обработка входа в игровой мир от графического клиента"""
        print(f"[GAME] Обработка join_world от клиента {client_id}")

        if client_id not in self.online_players:
            return self.error_response(client_id, 'Сначала пройдите аутентификацию')

        if client_id not in self.active_characters:
            return self.error_response(client_id, 'Сначала выберите персонажа')

        character = self.active_characters[client_id]

        # Собираем информацию о других игроках
        other_players = []
        for other_client_id, other_char in self.active_characters.items():
            if other_client_id != client_id:
                other_players.append({
                    'id': other_char['id'],
                    'name': other_char['name'],
                    'position': other_char.get('position', {'x': 0, 'y': 0, 'z': 0}),
                    'stats': other_char.get('stats', {})
                })

        # Рассылаем уведомление о входе в мир
        broadcast_msg = {
            'type': 'player_joined',
            'player_id': client_id,
            'character_id': character['id'],
            'character_name': character['name'],
            'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
            'timestamp': time.time()
        }

        # Информация о мире для клиента
        world_info = {
            'name': self.world['name'],
            'time': self.world['time'],
            'weather': self.world['weather'],
            'day': self.world['day'],
            'online_players': len(self.active_characters)
        }

        return [
            {
                'target': 'broadcast',
                'data': broadcast_msg,
                'exclude_client_id': client_id
            },
            {
                'target': 'client',
                'client_id': client_id,
                'data': {
                    'type': 'world_joined',
                    'success': True,
                    'world_info': world_info,
                    'players': other_players,
                    'message': f'Добро пожаловать в {self.world["name"]}, {character["name"]}!'
                }
            }
        ]

    def handle_position_update(self, client_id, message):
        """Обработка обновления позиции от графического клиента"""
        if client_id not in self.active_characters:
            return None  # Игрок не в мире

        character = self.active_characters[client_id]
        position = message.get('position', {'x': 0, 'y': 0, 'z': 0})

        # Обновляем позицию персонажа
        character['position'] = position
        self.db.update_character(character['id'], {'position': position})

        # Рассылаем обновление другим игрокам
        broadcast_msg = {
            'type': 'position_update',
            'character_id': character['id'],
            'character_name': character['name'],
            'position': position,
            'timestamp': time.time()
        }

        return [{
            'target': 'broadcast',
            'data': broadcast_msg,
            'exclude_client_id': client_id
        }]

    def handle_leave_world(self, client_id, message):
        """Обработка выхода из мира"""
        if client_id in self.active_characters:
            character = self.active_characters[client_id]

            # Удаляем из активных
            del self.active_characters[client_id]

            # Удаляем из обратного индекса
            if character['id'] in self.character_clients:
                del self.character_clients[character['id']]

            # Рассылаем уведомление
            broadcast_msg = {
                'type': 'player_left',
                'player_id': client_id,
                'character_id': character['id'],
                'character_name': character['name'],
                'timestamp': time.time()
            }

            return [{
                'target': 'broadcast',
                'data': broadcast_msg
            }]

        return None

    def remove_player(self, client_id):
        """Удаление игрока при отключении"""
        responses = []

        if client_id in self.active_characters:
            character = self.active_characters[client_id]
            character_id = character['id']

            # Сохраняем персонажа
            self.db.update_character(character_id, {
                'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
                'last_played': datetime.now().isoformat()
            })

            # Удаляем из активных
            del self.active_characters[client_id]

            # Удаляем из обратного индекса
            if character_id in self.character_clients:
                del self.character_clients[character_id]

            # Удаляем из онлайн игроков
            if client_id in self.online_players:
                del self.online_players[client_id]
                self.db.decrement_online_players()

            # Создаем сообщение для рассылки
            broadcast_msg = {
                'type': 'player_left',
                'player_id': client_id,
                'character_id': character_id,
                'character_name': character['name'],
                'timestamp': time.time()
            }

            responses.append({
                'target': 'broadcast',
                'data': broadcast_msg
            })

        elif client_id in self.online_players:
            # Если игрок был аутентифицирован, но не в мире
            del self.online_players[client_id]
            self.db.decrement_online_players()

        return responses

    # ==================== ОСТАЛЬНЫЕ МЕТОДЫ (добавь их из старой версии) ====================

    def handle_register(self, client_id, message):
        """Обработка регистрации нового игрока"""
        username = message.get('username')
        password = message.get('password')
        email = message.get('email')

        if not username or not password:
            return self.error_response(client_id, 'Не указано имя пользователя или пароль')

        player_id, result = self.db.register_player(username, password, email)

        if player_id:
            return [{
                'target': 'client',
                'client_id': client_id,
                'data': {
                    'type': 'register_response',
                    'success': True,
                    'player_id': player_id,
                    'message': 'Регистрация успешна!'
                }
            }]
        else:
            return self.error_response(client_id, result)

    def handle_login(self, client_id, message):
        """Обработка входа в систему"""
        username = message.get('username')
        password = message.get('password')

        if not username or not password:
            return self.error_response(client_id, 'Не указаны учетные данные')

        player_id, result = self.db.authenticate_player(username, password)

        if player_id:
            self.online_players[client_id] = player_id
            self.db.increment_online_players()

            player_data = self.db.get_player(player_id)
            characters = self.db.get_player_characters(player_id)
            character_list = []
            for char in characters:
                character_list.append({
                    'id': char['id'],
                    'name': char['name'],
                    'race': char['race'],
                    'class': char['class'],
                    'level': char['level'],
                    'last_played': char.get('last_played')
                })

            return [{
                'target': 'client',
                'client_id': client_id,
                'data': {
                    'type': 'login_response',
                    'success': True,
                    'player_id': player_id,
                    'player_data': {
                        'username': player_data['username'],
                        'characters_count': len(characters),
                        'playtime': player_data.get('stats', {}).get('playtime', 0)
                    },
                    'characters': character_list,
                    'message': f'Добро пожаловать, {username}!'
                }
            }]
        else:
            return self.error_response(client_id, result)

    def handle_logout(self, client_id, message):
        """Обработка выхода из системы"""
        if client_id in self.online_players:
            player_id = self.online_players.pop(client_id)

            if client_id in self.active_characters:
                character_data = self.active_characters[client_id]
                self.db.update_character(character_data['id'], character_data)

                if character_data['id'] in self.character_clients:
                    del self.character_clients[character_data['id']]

                del self.active_characters[client_id]

                broadcast_msg = {
                    'type': 'player_left_world',
                    'character_id': character_data['id'],
                    'character_name': character_data['name'],
                    'timestamp': time.time()
                }

                broadcast_response = {
                    'target': 'broadcast',
                    'data': broadcast_msg
                }
            else:
                broadcast_response = None

            self.db.decrement_online_players()

            responses = [{
                'target': 'client',
                'client_id': client_id,
                'data': {
                    'type': 'logout_response',
                    'success': True,
                    'message': 'Вы вышли из системы'
                }
            }]

            if broadcast_response:
                responses.append(broadcast_response)

            return responses

        return None

    def handle_create_character(self, client_id, message):
        """Обработка создания нового персонажа"""
        if client_id not in self.online_players:
            return self.error_response(client_id, 'Сначала войдите в систему')

        player_id = self.online_players[client_id]
        player_characters = self.db.get_player_characters(player_id)
        if len(player_characters) >= 5:
            return self.error_response(client_id, 'Достигнут лимит персонажей (5)')

        character_data = {
            'name': message.get('name', 'Безымянный'),
            'race': message.get('race', 'человек'),
            'class': message.get('class', 'воин'),
            'strength': message.get('strength', 10),
            'agility': message.get('agility', 10),
            'intelligence': message.get('intelligence', 10),
            'vitality': message.get('vitality', 10),
            'luck': message.get('luck', 5),
            'appearance': message.get('appearance', {}),
            'gifct1': message.get('gifct1'),
            'gifct2': message.get('gifct2')
        }

        existing_char = self.db.find_character_by_name(character_data['name'])
        if existing_char:
            return self.error_response(client_id, 'Персонаж с таким именем уже существует')

        character_id, character = self.db.create_character(player_id, character_data)

        return [{
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'create_character_response',
                'success': True,
                'character_id': character_id,
                'character': character,
                'message': f'Персонаж {character["name"]} создан!'
            }
        }]

    def handle_select_character(self, client_id, message):
        """Обработка выбора персонажа для игры (старая версия)"""
        if client_id not in self.online_players:
            return self.error_response(client_id, 'Сначала войдите в систему')

        character_id = message.get('character_id')
        if not character_id:
            return self.error_response(client_id, 'Не указан ID персонажа')

        character = self.db.get_character(character_id)
        if not character:
            return self.error_response(client_id, 'Персонаж не найден')

        player_id = self.online_players[client_id]
        if character['player_id'] != player_id:
            return self.error_response(client_id, 'Это не ваш персонаж')

        self.active_characters[client_id] = character.copy()
        self.character_clients[character_id] = client_id

        self.db.update_character(character_id, {'last_played': datetime.now().isoformat()})

        other_players = []
        for other_client_id, other_char in self.active_characters.items():
            if other_client_id != client_id:
                other_players.append({
                    'character_id': other_char['id'],
                    'name': other_char['name'],
                    'position': other_char.get('position', {'x': 0, 'y': 0}),
                    'race': other_char['race'],
                    'class': other_char['class'],
                    'level': other_char['level']
                })

        broadcast_msg = {
            'type': 'player_joined_world',
            'character_id': character['id'],
            'character_name': character['name'],
            'position': character.get('position', {'x': 100, 'y': 100}),
            'timestamp': time.time()
        }

        return [
            {
                'target': 'broadcast',
                'data': broadcast_msg,
                'exclude_client_id': client_id
            },
            {
                'target': 'client',
                'client_id': client_id,
                'data': {
                    'type': 'select_character_response',
                    'success': True,
                    'character': character,
                    'world': self.world,
                    'online_players': other_players,
                    'message': f'Вы входите в мир как {character["name"]}'
                }
            }
        ]

    def handle_chat(self, client_id, message):
        """Обработка сообщений чата"""
        if client_id not in self.active_characters:
            return self.error_response(client_id, 'Сначала выберите персонажа')

        chat_message = message.get('message', '')
        character = self.active_characters[client_id]

        if not chat_message.strip():
            return None

        chat_data = {
            'type': 'chat_message',
            'character_id': character['id'],
            'character_name': character['name'],
            'message': chat_message,
            'timestamp': time.time()
        }

        return [{'target': 'broadcast', 'data': chat_data}]

    def handle_ping(self, client_id, message):
        """Обработка пинга"""
        return [{
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'pong',
                'timestamp': time.time(),
                'server_time': self.world['time'],
                'game_tick': self.game_tick
            }
        }]

    def handle_get_world_info(self, client_id, message):
        """Получение информации о мире"""
        world_info = {
            'name': self.world['name'],
            'time': self.world['time'],
            'weather': self.world['weather'],
            'day': self.world['day'],
            'online_players': len(self.active_characters)
        }

        return [{
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'world_info',
                'world': world_info,
                'server_time': time.time()
            }
        }]

    def error_response(self, client_id, message):
        """Создание ответа с ошибкой"""
        print(f"[GAME] Ошибка для {client_id}: {message}")
        return [{
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'error',
                'success': False,
                'message': message
            }
        }]

    def get_player_count(self):
        """Получение количества онлайн игроков"""
        return len(self.active_characters)

    def get_world_state(self):
        """Получение текущего состояния мира"""
        return {
            'world': self.world,
            'online_players': len(self.active_characters),
            'total_characters': self.db.get_server_stats()['total_characters'],
            'game_tick': self.game_tick
        }

    # Другие методы оставь без изменений...