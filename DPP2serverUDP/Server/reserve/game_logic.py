import time
import random
from datetime import datetime
from typing import List, Dict, Any, Optional


class GameLogic:
    """Игровая логика для UDP сервера"""

    def __init__(self, database):
        self.db = database
        self._init_world()
        self._init_structures()
        self._init_timers()
        print(f"[GAME] UDP Мир инициализирован: {self.world['name']}")
        print(f"[GAME] Протокол: UDP, Порт: {self.world.get('udp_port', 5555)}")
        print(f"[GAME] Время: {self.world['time']}, Погода: {self.world['weather']}")

    def _init_world(self):
        """Инициализация мира"""
        self.world = self.db.get_world_data()
        if not self.world or 'name' not in self.world:
            self.world = {
                'name': 'Эквестрия',
                'time': '12:00',
                'weather': 'солнечно',
                'day': 1,
                'online_players': 0,
                'udp_port': 5555,
                'protocol': 'udp'
            }
            self.db.update_world_data(self.world)

    def _init_structures(self):
        """Инициализация структур данных"""
        self.online_players = {}  # client_id -> player_id
        self.active_characters = {}  # client_id -> character_data
        self.character_clients = {}  # character_id -> client_id
        self.player_positions = {}  # client_id -> position
        self.last_position_updates = {}  # client_id -> timestamp
        self.last_broadcast_updates = {}  # client_id -> timestamp для рассылки

    def _init_timers(self):
        """Инициализация таймеров"""
        self.game_tick = 0
        self.last_world_update = time.time()
        self.world_update_interval = 60

    # Обновление мира
    def update_world(self):
        """Обновление состояния мира для UDP"""
        self.game_tick += 1
        current_time = time.time()
        if current_time - self.last_world_update >= self.world_update_interval:
            self.last_world_update = current_time
            return self._perform_world_update()
        return None

    def _perform_world_update(self):
        """Выполнение обновления мира"""
        updates = []
        time_update = self._update_time()
        if time_update:
            updates.append(time_update)
        weather_update = self._update_weather()
        if weather_update:
            updates.append(weather_update)
        self._auto_save_characters()
        return updates if updates else None

    def _update_time(self):
        """Обновление игрового времени"""
        hours, minutes = map(int, self.world['time'].split(':'))
        minutes += 1
        if minutes >= 60:
            minutes = 0
            hours += 1
            if hours >= 24:
                hours = 0
                self.world['day'] += 1
        self.world['time'] = f"{hours:02d}:{minutes:02d}"
        self.db.update_world_data(self.world)
        return self._create_world_update('time', time=self.world['time'], day=self.world['day'])

    def _update_weather(self):
        """Обновление погоды"""
        weather_types = ['солнечно', 'дождь', 'облачно', 'туман', 'снег', 'гроза']
        new_weather = random.choice(weather_types)
        if new_weather != self.world['weather']:
            self.world['weather'] = new_weather
            self.db.update_world_data(self.world)
            return self._create_world_update('weather', weather=new_weather)
        return None

    def _create_world_update(self, update_type, **data):
        """Создание сообщения обновления мира"""
        return {
            'target': 'broadcast',
            'data': {
                'type': 'world_update',
                'update_type': update_type,
                'timestamp': time.time(),
                **data
            }
        }

    def _auto_save_characters(self):
        """Автосохранение активных персонажей"""
        for client_id, character in self.active_characters.items():
            self.db.update_character(character['id'], {
                'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
                'last_played': datetime.now().isoformat()
            })

    # Основной обработчик сообщений
    def handle_message(self, message):
        """Обработка входящих сообщений для UDP"""
        msg_type = message.get('type')
        client_id = message.get('client_id')

        if msg_type not in ['heartbeat', 'ping']:
            print(f"[GAME] UDP Обработка от {client_id}: {msg_type}")

        # UDP-специфичные сообщения
        if msg_type == 'client_init':
            return self._create_client_response(client_id, 'client_init_response',
                                                success=True, message='UDP клиент инициализирован')
        elif msg_type == 'client_disconnect':
            return self.remove_player(client_id)
        elif msg_type == 'heartbeat':
            return self.handle_heartbeat(client_id, message)
        elif msg_type == 'skin_update':
            return self.handle_skin_update(client_id, message)
        elif msg_type == 'request_skin':
            return self.handle_skin_request(client_id, message)

        # Основные игровые сообщения
        handlers = {
            'auth': self.handle_auth,
            'character_select': self.handle_character_select,
            'join_world': self.handle_join_world,
            'position_update': self.handle_position_update,
            'character_move': self.handle_position_update,
            'chat_message': self.handle_chat,
            'leave_world': self.handle_leave_world,
            'ping': self.handle_ping,
            'test': self.handle_ping,
            # Совместимость со старыми сообщениями
            'register': self.handle_register,
            'login': self.handle_login,
            'logout': self.handle_logout,
            'create_character': self.handle_create_character,
            'select_character': self.handle_select_character,
            'delete_character': self.handle_delete_character,
            'get_characters': self.handle_get_characters,
            'character_action': self.handle_character_action,
            'get_world_info': self.handle_get_world_info,
            'save_character': self.handle_save_character,
        }

        handler = handlers.get(msg_type)
        if handler:
            return handler(client_id, message)

        print(f"[GAME] Неизвестный тип сообщения UDP: {msg_type}")
        return self.error_response(client_id, f'Неизвестный тип сообщения: {msg_type}')

    # Обработчики сообщений
    def handle_heartbeat(self, client_id, message):
        """Обработка heartbeat сообщения"""
        if client_id in self.active_characters:
            character = self.active_characters[client_id]
            self.db.update_character(character['id'], {
                'last_activity': datetime.now().isoformat()
            })
        return self._create_client_response(client_id, 'heartbeat_response',
                                            timestamp=time.time(), server_tick=self.game_tick)

    def handle_auth(self, client_id, message):
        """Обработка аутентификации для UDP"""
        username = message.get('username')
        if not username:
            return self.error_response(client_id, 'Не указано имя пользователя')

        existing_player = self.db.find_player_by_username(username)
        if existing_player:
            player_id = existing_player['id']
            print(f"[GAME] UDP Использован существующий игрок: {player_id}")
        else:
            player_id, player = self.db.register_player(
                username, 'default_password', f'{username}@example.com'
            )
            print(f"[GAME] UDP Создан новый игрок: {player_id}")

        self.online_players[client_id] = player_id
        self.db.increment_online_players()

        return self._create_client_response(client_id, 'auth_response',
                                            success=True, player_id=player_id,
                                            username=username, message='UDP Аутентификация успешна',
                                            protocol='udp')

    def handle_character_select(self, client_id, message):
        """Обработка выбора персонажа"""
        character_id = message.get('character_id')
        character_data = message.get('character_data')

        if not character_id:
            return self.error_response(client_id, 'Не указан ID персонажа')

        # Проверяем player_id
        player_id = self.online_players.get(client_id)
        if not player_id:
            return self.error_response(client_id, 'Не аутентифицирован')

        # Получаем или создаем персонажа
        character = self.db.get_character(character_id)
        if not character:
            if not character_data:
                return self.error_response(client_id, 'Нет данных персонажа')

            # Создаем нового персонажа
            character_id, character = self.db.create_character(player_id, character_data)

        # Ответ клиенту
        return self._create_client_response(client_id, 'character_select_response',
                                            success=True,
                                            character_id=character_id,
                                            character_data={
                                                'id': character['id'],
                                                'name': character['name'],
                                                'race': character['race'],
                                                'class': character['class'],
                                                'level': character['level'],
                                                'position': character.get('position', {'x': 0, 'y': 0, 'z': 0})
                                            },
                                            message='Персонаж выбран')

    def handle_skin_update(self, client_id, message):
        """Обработка обновления скина персонажа"""
        if client_id not in self.active_characters:
            return self.error_response(client_id, 'Не в мире')

        character = self.active_characters[client_id]
        skin_data = message.get('skin_data', {})

        # Обновляем данные скина у персонажа
        if 'current_skin' not in character:
            character['current_skin'] = {}
        character['current_skin'].update(skin_data)

        # Сохраняем в БД
        self.db.update_character(character['id'], {
            'current_skin': character['current_skin']
        })

        # Рассылаем обновление другим игрокам
        broadcast_msg = self._create_broadcast_message('skin_update',
                                                       character=character,
                                                       skin_data=skin_data)

        return [{'target': 'broadcast', 'data': broadcast_msg,
                 'exclude_client_id': client_id}]

    def handle_skin_request(self, client_id, message):
        """Обработка запроса скина игрока"""
        target_character_id = message.get('target_character_id')

        if not target_character_id:
            return self.error_response(client_id, 'Не указан ID персонажа')

        # Ищем игрока с этим character_id
        target_client_id = self.character_clients.get(target_character_id)

        if not target_client_id or target_client_id not in self.active_characters:
            return self.error_response(client_id, 'Игрок не найден')

        character = self.active_characters[target_client_id]
        skin_data = character.get('current_skin', {})

        return self._create_client_response(client_id, 'skin_info_response',
                                            character_id=target_character_id,
                                            character_name=character['name'],
                                            skin_data=skin_data)

    def handle_join_world(self, client_id, message):
        """Обработка входа в игровой мир для UDP"""
        print(f"[GAME] UDP Запрос на вход в мир от {client_id}")

        character_id = message.get('character_id')
        character_name = message.get('character_name')

        if not character_id:
            return self.error_response(client_id, 'Не указан ID персонажа')

        # Проверяем, есть ли уже активный персонаж у этого клиента
        if client_id in self.active_characters:
            return self.error_response(client_id, 'Уже в мире с другим персонажем')

        # Получаем данные персонажа из БД
        character = self.db.get_character(character_id)
        if not character:
            # Если персонажа нет в БД, создаем нового
            character_data = {
                'id': character_id,
                'name': character_name or f'Character_{character_id}',
                'race': 'human',
                'class': 'warrior',
                'level': 1,
                'health': 100,
                'max_health': 100,
                'position': {'x': 0, 'y': 0, 'z': 0}
            }

            # Если есть player_id в online_players, используем его
            player_id = self.online_players.get(client_id, f'player_{client_id}')

            character_id, character = self.db.create_character(player_id, character_data)

        # Добавляем персонажа в активные
        self.active_characters[client_id] = character
        self.character_clients[character_id] = client_id

        # Обновляем позицию
        if 'position' in message:
            character['position'] = message['position']

        self.player_positions[client_id] = character.get('position', {'x': 0, 'y': 0, 'z': 0})
        self.last_position_updates[client_id] = time.time()

        # Обновляем в БД
        self.db.update_character(character_id, {
            'last_activity': datetime.now().isoformat(),
            'in_world': True,
            'position': character.get('position', {'x': 0, 'y': 0, 'z': 0})
        })

        # После добавления персонажа в активные
        self.active_characters[client_id] = character

        # Отправляем новому клиенту скины всех текущих игроков
        responses = []

        # Скины существующих игроков
        for other_client_id, other_character in self.active_characters.items():
            if other_client_id != client_id and 'current_skin' in other_character:
                skin_info_msg = {
                    'type': 'player_skin_info',
                    'character_id': other_character['id'],
                    'character_name': other_character['name'],
                    'skin_data': other_character['current_skin'],
                    'timestamp': time.time()
                }
                responses.append({
                    'target': 'client',
                    'client_id': client_id,
                    'data': skin_info_msg
                })

        # Создаем ответ клиенту
        responses = []

        # Ответ клиенту об успешном входе
        responses.append({
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'world_joined',
                'success': True,
                'character_id': character_id,
                'character_name': character['name'],
                'world_info': {
                    'name': self.world['name'],
                    'time': self.world['time'],
                    'weather': self.world['weather'],
                    'online_players': len(self.active_characters)
                },
                'protocol': 'udp',
                'timestamp': time.time()
            }
        })

        # Рассылка другим игрокам о новом игроке
        broadcast_msg = {
            'type': 'player_joined',
            'character_id': character_id,
            'character_name': character['name'],
            'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
            'timestamp': time.time(),
            'protocol': 'udp'
        }

        responses.append({
            'target': 'broadcast',
            'data': broadcast_msg,
            'exclude_client_id': client_id
        })

        print(f"[GAME] UDP Персонаж {character['name']} вошел в мир")
        return responses

    def handle_leave_world(self, client_id, message):
        """Обработка выхода из мира"""
        if client_id not in self.active_characters:
            return self.error_response(client_id, 'Не в мире')

        character = self.active_characters[client_id]
        character_id = character['id']

        # Сохраняем данные
        self.db.update_character(character_id, {
            'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
            'last_played': datetime.now().isoformat(),
            'in_world': False
        })

        # Удаляем из активных
        del self.active_characters[client_id]

        if character_id in self.character_clients:
            del self.character_clients[character_id]

        # Очищаем связанные данные
        for dict_to_clean in [self.player_positions, self.last_position_updates, self.last_broadcast_updates]:
            dict_to_clean.pop(client_id, None)

        # Ответ клиенту
        responses = [{
            'target': 'client',
            'client_id': client_id,
            'data': {
                'type': 'world_left',
                'success': True,
                'message': 'Вышли из мира',
                'timestamp': time.time()
            }
        }]

        # Рассылка другим игрокам
        broadcast_msg = {
            'type': 'player_left',
            'character_id': character_id,
            'character_name': character['name'],
            'timestamp': time.time(),
            'protocol': 'udp'
        }

        responses.append({
            'target': 'broadcast',
            'data': broadcast_msg,
            'exclude_client_id': client_id
        })

        print(f"[GAME] UDP Персонаж {character['name']} покинул мир")
        return responses

    def handle_position_update(self, client_id, message):
        """Обработка обновления позиции для UDP"""
        if client_id not in self.active_characters:
            return None

        character = self.active_characters[client_id]
        position = self._extract_position(message)
        if not position:
            return None

        # Обновляем позицию
        character['position'] = position
        self.player_positions[client_id] = position
        self.db.update_character(character['id'], {'position': position})

        # Обновляем время
        current_time = time.time()
        self.last_position_updates[client_id] = current_time

        # Рассылка с троттлингом
        last_broadcast = self.last_broadcast_updates.get(client_id, 0)
        if current_time - last_broadcast >= 0.05:  # 20 FPS
            self.last_broadcast_updates[client_id] = current_time
            broadcast_msg = self._create_broadcast_message('position_update',
                                                           character=character,
                                                           position=position)
            return [{'target': 'broadcast', 'data': broadcast_msg,
                     'exclude_client_id': client_id}]
        return None

    def _extract_position(self, message):
        """Извлечение позиции из сообщения"""
        if 'position' in message:
            return message['position']
        elif 'x' in message and 'y' in message:
            return {'x': message.get('x', 0), 'y': message.get('y', 0),
                    'z': message.get('z', 0)}
        return None

    def _create_broadcast_message(self, msg_type, character, **extra):
        """Создание широковещательного сообщения"""
        return {
            'type': msg_type,
            'character_id': character['id'],
            'character_name': character['name'],
            'timestamp': time.time(),
            'protocol': 'udp',
            **extra
        }

    def _create_client_response(self, client_id, response_type, **data):
        """Создание ответа клиенту"""
        return [{
            'target': 'client',
            'client_id': client_id,
            'data': {'type': response_type, **data}
        }]

    # Удаление игрока
    def remove_player(self, client_id):
        """Удаление игрока при отключении"""
        responses = []

        if client_id in self.active_characters:
            character = self.active_characters[client_id]
            character_id = character['id']

            # Сохраняем данные
            self.db.update_character(character_id, {
                'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
                'last_played': datetime.now().isoformat(),
                'in_world': False
            })

            # Удаляем из всех структур
            self._cleanup_player_data(client_id, character_id)

            # Рассылка уведомления
            broadcast_msg = self._create_broadcast_message('player_left',
                                                           character=character,
                                                           reason='disconnect')
            responses.append({'target': 'broadcast', 'data': broadcast_msg})

        elif client_id in self.online_players:
            del self.online_players[client_id]
            self.db.decrement_online_players()

        return responses if responses else None

    def _cleanup_player_data(self, client_id, character_id):
        """Очистка данных игрока"""
        # Удаляем из активных
        if client_id in self.active_characters:
            del self.active_characters[client_id]

        # Удаляем из индексов
        for dict_to_clean in [self.character_clients, self.player_positions,
                              self.last_position_updates, self.last_broadcast_updates,
                              self.online_players]:
            dict_to_clean.pop(client_id, None)

        if character_id in self.character_clients:
            del self.character_clients[character_id]

    # Остальные методы (для совместимости)
    def error_response(self, client_id, message):
        """Создание ответа с ошибкой"""
        print(f"[GAME] UDP Ошибка для {client_id}: {message}")
        return self._create_client_response(client_id, 'error',
                                            success=False, message=message, protocol='udp')

    def handle_ping(self, client_id, message):
        """Обработка пинга"""
        return self._create_client_response(client_id, 'pong',
                                            timestamp=time.time(),
                                            server_time=self.world['time'],
                                            game_tick=self.game_tick,
                                            protocol='udp')

    def handle_chat(self, client_id, message):
        """Обработка чата"""
        if client_id not in self.active_characters:
            return self.error_response(client_id, 'Не в мире')

        character = self.active_characters[client_id]

        broadcast_msg = self._create_broadcast_message('chat_message',
                                                       character=character,
                                                       text=message.get('text', ''),
                                                       channel=message.get('channel', 'global'))

        return [{'target': 'broadcast', 'data': broadcast_msg}]

    # Методы для совместимости
    def handle_register(self, client_id, message):
        username = message.get('username')
        password = message.get('password')
        email = message.get('email')

        if not username or not password:
            return self.error_response(client_id, 'Не указано имя пользователя или пароль')

        player_id, result = self.db.register_player(username, password, email)

        if player_id:
            return self._create_client_response(client_id, 'register_response',
                                                success=True, player_id=player_id,
                                                message='Регистрация успешна!')
        else:
            return self.error_response(client_id, result)

    def handle_login(self, client_id, message):
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
            character_list = [{
                'id': char['id'],
                'name': char['name'],
                'race': char['race'],
                'class': char['class'],
                'level': char['level'],
                'last_played': char.get('last_played')
            } for char in characters]

            return self._create_client_response(client_id, 'login_response',
                                                success=True, player_id=player_id,
                                                player_data={
                                                    'username': player_data['username'],
                                                    'characters_count': len(characters),
                                                    'playtime': player_data.get('stats', {}).get('playtime', 0)
                                                },
                                                characters=character_list,
                                                message=f'Добро пожаловать, {username}!')
        else:
            return self.error_response(client_id, result)

    def handle_logout(self, client_id, message):
        return self.remove_player(client_id)

    def handle_create_character(self, client_id, message):
        player_id = self.online_players.get(client_id)
        if not player_id:
            return self.error_response(client_id, 'Не аутентифицирован')

        character_data = message.get('character_data', {})
        character_id, character = self.db.create_character(player_id, character_data)

        return self._create_client_response(client_id, 'character_created',
                                            success=True, character_id=character_id,
                                            character_data=character)

    def handle_select_character(self, client_id, message):
        return self.handle_character_select(client_id, message)

    def handle_delete_character(self, client_id, message):
        character_id = message.get('character_id')
        if not character_id:
            return self.error_response(client_id, 'Не указан ID персонажа')

        success = self.db.delete_character(character_id)
        if success:
            return self._create_client_response(client_id, 'character_deleted',
                                                success=True, character_id=character_id)
        else:
            return self.error_response(client_id, 'Не удалось удалить персонажа')

    def handle_get_characters(self, client_id, message):
        player_id = self.online_players.get(client_id)
        if not player_id:
            return self.error_response(client_id, 'Не аутентифицирован')

        characters = self.db.get_player_characters(player_id)
        character_list = [{
            'id': char['id'],
            'name': char['name'],
            'race': char['race'],
            'class': char['class'],
            'level': char['level'],
            'position': char.get('position', {'x': 0, 'y': 0, 'z': 0})
        } for char in characters]

        return self._create_client_response(client_id, 'characters_list',
                                            characters=character_list)

    def handle_character_action(self, client_id, message):
        # Базовая реализация для тестирования
        return self._create_client_response(client_id, 'action_response',
                                            success=True,
                                            action=message.get('action'),
                                            message='Действие выполнено')

    def handle_get_world_info(self, client_id, message):
        return self._create_client_response(client_id, 'world_info',
                                            world=self.world,
                                            online_players=len(self.active_characters))

    def handle_save_character(self, client_id, message):
        if client_id not in self.active_characters:
            return self.error_response(client_id, 'Нет активного персонажа')

        character = self.active_characters[client_id]
        self.db.update_character(character['id'], {
            'position': character.get('position', {'x': 0, 'y': 0, 'z': 0}),
            'last_played': datetime.now().isoformat()
        })

        return self._create_client_response(client_id, 'character_saved',
                                            success=True,
                                            character_id=character['id'])

    def get_player_count(self):
        """Получение количества онлайн игроков"""
        return len(self.active_characters)

    def get_world_state(self):
        """Получение текущего состояния мира"""
        return {
            'world': self.world,
            'online_players': len(self.active_characters),
            'total_characters': self.db.get_server_stats()['total_characters'],
            'game_tick': self.game_tick,
            'protocol': 'udp'
        }