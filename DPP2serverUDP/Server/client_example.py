#!/usr/bin/env python3
"""
Пример UDP клиента для тестирования DPP2 UDP сервера
"""

import socket
import json
import time
import threading
import random


class UDPTestClient:
    """Тестовый UDP клиент"""

    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.address = (host, port)

        # Создаем UDP сокет
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(2.0)

        self.client_id = None
        self.connected = False
        self.running = False

        # Данные для тестирования
        self.test_username = f"test_user_{random.randint(1000, 9999)}"
        self.character_id = None
        self.character_name = f"TestChar_{random.randint(1000, 9999)}"

        # Позиция
        self.position = {'x': 0, 'y': 0, 'z': 0}

        # Очередь сообщений
        self.messages = []

    def connect(self):
        """Подключение к UDP серверу"""
        try:
            print(f"[CLIENT] Подключение к UDP серверу {self.host}:{self.port}...")

            # Отправляем инициализационное сообщение
            init_msg = {
                'type': 'client_init',
                'timestamp': time.time(),
                'client_info': {
                    'version': '1.0',
                    'protocol': 'udp'
                }
            }

            self.send(init_msg)

            # Ждем ответ
            response = self.receive()
            if response and response.get('type') == 'welcome':
                self.client_id = response.get('client_id')
                self.connected = True
                print(f"[CLIENT] ✅ Подключено! ID клиента: {self.client_id}")
                return True

        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка подключения: {e}")

        return False

    def send(self, data):
        """Отправка данных"""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            self.socket.sendto(json_str.encode('utf-8'), self.address)
            print(f"[CLIENT] 📤 Отправлено: {data.get('type', 'unknown')}")
            return True
        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка отправки: {e}")
            return False

    def receive(self):
        """Получение данных"""
        try:
            data, addr = self.socket.recvfrom(4096)
            if data:
                message = json.loads(data.decode('utf-8'))
                print(f"[CLIENT] 📥 Получено: {message.get('type', 'unknown')}")
                self.messages.append(message)
                return message
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка приема: {e}")
        return None

    def authenticate(self):
        """Аутентификация"""
        print(f"[CLIENT] 🔐 Аутентификация как {self.test_username}...")

        auth_msg = {
            'type': 'auth',
            'username': self.test_username,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(auth_msg)

        # Ждем ответ
        for _ in range(5):
            response = self.receive()
            if response and response.get('type') == 'auth_response':
                if response.get('success'):
                    print(f"[CLIENT] ✅ Аутентификация успешна!")
                    return True
                else:
                    print(f"[CLIENT] ❌ Ошибка аутентификации: {response.get('message')}")
                    return False
            time.sleep(0.1)

        print(f"[CLIENT] ❌ Таймаут аутентификации")
        return False

    def create_character(self):
        """Создание тестового персонажа"""
        print(f"[CLIENT] 🎮 Создание персонажа {self.character_name}...")

        character_data = {
            'id': f"test_char_{random.randint(10000, 99999)}",
            'name': self.character_name,
            'owner': self.test_username,
            'position': self.position,
            'stats': {
                'strength': 10,
                'agility': 10,
                'intelligence': 10
            },
            'level': 1,
            'health': 100
        }

        char_msg = {
            'type': 'character_select',
            'character_id': character_data['id'],
            'character_data': character_data,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(char_msg)

        for _ in range(5):
            response = self.receive()
            if response and response.get('type') == 'character_select_response':
                if response.get('success'):
                    self.character_id = response.get('character_id')
                    print(f"[CLIENT] ✅ Персонаж создан! ID: {self.character_id}")
                    return True
                else:
                    print(f"[CLIENT] ❌ Ошибка создания персонажа: {response.get('message')}")
                    return False
            time.sleep(0.1)

        print(f"[CLIENT] ❌ Таймаут создания персонажа")
        return False

    def join_world(self):
        """Вход в игровой мир"""
        print(f"[CLIENT] 🌍 Вход в игровой мир...")

        join_msg = {
            'type': 'join_world',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(join_msg)

        for _ in range(5):
            response = self.receive()
            if response:
                if response.get('type') == 'world_joined' and response.get('success'):
                    print(f"[CLIENT] ✅ Вошли в мир!")
                    print(f"[CLIENT] Мир: {response.get('world_info', {}).get('name', 'Неизвестно')}")
                    print(f"[CLIENT] Игроков онлайн: {response.get('world_info', {}).get('online_players', 0)}")
                    return True
                elif response.get('type') == 'error':
                    print(f"[CLIENT] ❌ Ошибка входа в мир: {response.get('message')}")
                    return False
            time.sleep(0.1)

        print(f"[CLIENT] ❌ Таймаут входа в мир")
        return False

    def move_randomly(self):
        """Случайное движение"""
        self.position['x'] += random.uniform(-5, 5)
        self.position['y'] += random.uniform(-5, 5)

        move_msg = {
            'type': 'position_update',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'position': self.position,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(move_msg)
        print(f"[CLIENT] 🚶 Движение: x={self.position['x']:.2f}, y={self.position['y']:.2f}")

    def send_chat(self, message):
        """Отправка сообщения в чат"""
        chat_msg = {
            'type': 'chat_message',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'text': message,
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(chat_msg)
        print(f"[CLIENT] 💬 Чат: {message}")

    def heartbeat(self):
        """Отправка heartbeat"""
        hb_msg = {
            'type': 'heartbeat',
            'timestamp': time.time(),
            'client_id': self.client_id
        }

        self.send(hb_msg)
        print(f"[CLIENT] 💓 Heartbeat отправлен")

    def receive_loop(self):
        """Цикл приема сообщений"""
        while self.running:
            try:
                response = self.receive()
                if response:
                    # Обработка разных типов сообщений
                    msg_type = response.get('type')

                    if msg_type == 'position_update':
                        char_id = response.get('character_id')
                        if char_id != self.character_id:
                            pos = response.get('position', {})
                            print(f"[CLIENT] 👤 Другой игрок двигается: {response.get('character_name')} "
                                  f"x={pos.get('x', 0):.2f}, y={pos.get('y', 0):.2f}")

                    elif msg_type == 'chat_message':
                        print(f"[CLIENT] 💬 {response.get('character_name')}: {response.get('text')}")

                    elif msg_type == 'player_joined':
                        print(f"[CLIENT] 👤 {response.get('character_name')} присоединился")

                    elif msg_type == 'player_left':
                        print(f"[CLIENT] 👋 {response.get('character_name')} покинул мир")

            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Ошибка в цикле приема: {e}")

    def test_scenario(self):
        """Тестовый сценарий"""
        print(f"\n{'=' * 50}")
        print(f"🚀 Запуск тестового UDP сценария")
        print(f"{'=' * 50}\n")

        # 1. Подключение
        if not self.connect():
            return False

        # 2. Аутентификация
        if not self.authenticate():
            return False

        # 3. Создание персонажа
        if not self.create_character():
            return False

        # 4. Вход в мир
        if not self.join_world():
            return False

        print(f"\n{'=' * 50}")
        print(f"✅ Тестовый сценарий выполнен успешно!")
        print(f"{'=' * 50}\n")

        # Запускаем цикл приема в отдельном потоке
        self.running = True
        receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
        receive_thread.start()

        # Основной цикл действий
        try:
            for i in range(10):
                print(f"\n[ЦИКЛ {i + 1}/10]")

                # Движение
                self.move_randomly()

                # Heartbeat
                self.heartbeat()

                # Чат (каждый 3й цикл)
                if i % 3 == 0:
                    self.send_chat(f"Тестовое сообщение {i + 1} от {self.character_name}")

                time.sleep(2)

        except KeyboardInterrupt:
            print("\n[CLIENT] Прервано пользователем")

        finally:
            self.running = False

            # Выход из мира
            leave_msg = {
                'type': 'leave_world',
                'character_id': self.character_id,
                'character_name': self.character_name,
                'timestamp': time.time(),
                'client_id': self.client_id
            }
            self.send(leave_msg)

            # Отключение
            disconnect_msg = {
                'type': 'client_disconnect',
                'timestamp': time.time(),
                'client_id': self.client_id
            }
            self.send(disconnect_msg)

            self.socket.close()
            print("[CLIENT] 📡 Отключено")

        return True

    def simple_test(self):
        """Простой тест подключения"""
        print(f"[CLIENT] Простой тест UDP подключения...")

        if self.connect():
            print(f"[CLIENT] ✅ Подключение успешно!")

            # Отправляем ping
            ping_msg = {
                'type': 'ping',
                'timestamp': time.time(),
                'client_id': self.client_id
            }
            self.send(ping_msg)

            # Ждем ответ
            for _ in range(3):
                response = self.receive()
                if response and response.get('type') == 'pong':
                    print(f"[CLIENT] ✅ Ping-Pong успешен!")
                    self.socket.close()
                    return True
                time.sleep(0.5)

            print(f"[CLIENT] ❌ Нет ответа на ping")
            self.socket.close()
            return False

        return False


def main():
    """Главная функция тестового клиента"""
    import argparse

    parser = argparse.ArgumentParser(description='DPP2 UDP Test Client')
    parser.add_argument('--host', default='127.0.0.1', help='Адрес сервера')
    parser.add_argument('--port', type=int, default=5555, help='Порт сервера')
    parser.add_argument('--simple', action='store_true', help='Простой тест подключения')
    parser.add_argument('--username', help='Имя пользователя для теста')

    args = parser.parse_args()

    print(f"DPP2 UDP Test Client")
    print(f"Сервер: {args.host}:{args.port}")
    print(f"{'=' * 50}\n")

    client = UDPTestClient(args.host, args.port)

    if args.username:
        client.test_username = args.username

    if args.simple:
        success = client.simple_test()
    else:
        success = client.test_scenario()

    if success:
        print(f"\n{'=' * 50}")
        print(f"✅ Тест завершен успешно!")
        print(f"{'=' * 50}")
        return 0
    else:
        print(f"\n{'=' * 50}")
        print(f"❌ Тест завершен с ошибками!")
        print(f"{'=' * 50}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())