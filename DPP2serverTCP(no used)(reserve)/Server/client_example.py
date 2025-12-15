import socket
import json
import struct
import threading
import time

class GameClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.client_id = None
        self.player_id = None
        self.character_data = None

    def connect(self):
        """Подключение к серверу"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))

            welcome = self.receive_message()
            if welcome and welcome.get('type') == 'welcome':
                self.client_id = welcome.get('client_id')
                print(f"Подключено! ID клиента: {self.client_id}")

                self.running = True
                receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
                receive_thread.start()

                return True

        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False

    def send_message(self, data):
        """Отправка сообщения"""
        try:
            data['client_id'] = self.client_id
            message = json.dumps(data).encode('utf-8')
            self.socket.sendall(struct.pack('I', len(message)) + message)
            return True
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return False

    def receive_message(self):
        """Получение одного сообщения"""
        try:
            length_data = self.socket.recv(4)
            if len(length_data) < 4:
                return None

            length = struct.unpack('I', length_data)[0]
            message_data = b''

            while len(message_data) < length:
                chunk = self.socket.recv(min(4096, length - len(message_data)))
                if not chunk:
                    break
                message_data += chunk

            if len(message_data) < length:
                return None

            return json.loads(message_data.decode('utf-8'))

        except Exception as e:
            print(f"Ошибка получения: {e}")
            return None

    def receive_loop(self):
        """Цикл приема сообщений"""
        while self.running:
            try:
                message = self.receive_message()
                if message:
                    self.handle_message(message)
                else:
                    self.running = False
                    break
            except:
                self.running = False
                break

    def handle_message(self, message):
        """Обработка входящих сообщений"""
        msg_type = message.get('type')

        if msg_type == 'login_response':
            if message.get('success'):
                self.player_id = message.get('player_id')
                print(f"Успешный вход! Player ID: {self.player_id}")
        elif msg_type == 'create_character_response':
            if message.get('success'):
                self.character_data = message.get('character_data')
                print(f"Персонаж создан: {self.character_data['name']}")
        elif msg_type == 'select_character_response':
            if message.get('success'):
                self.character_data = message.get('character_data')
                print(f"Персонаж выбран: {self.character_data['name']}")
        elif msg_type == 'character_moved':
            print(f"Персонаж {message['character_name']} переместился")
        elif msg_type == 'chat_message':
            print(f"[ЧАТ] {message['character_name']}: {message['message']}")
        elif msg_type == 'gifct_settings_updated':
            print(f"Настройки Gifct обновлены: {message['gifct_settings']}")
        else:
            print(f"[СЕРВЕР] {message}")

    # === БАЗОВЫЕ КОМАНДЫ ===
    def register(self, username, password, email=None):
        """Регистрация нового аккаунта"""
        return self.send_message({
            'type': 'register',
            'username': username,
            'password': password,
            'email': email
        })

    def login(self, username, password):
        """Вход в аккаунт"""
        return self.send_message({
            'type': 'login',
            'username': username,
            'password': password
        })

    def logout(self):
        """Выход из аккаунта"""
        return self.send_message({
            'type': 'logout'
        })

    def create_character(self, name, race='человек', char_class='воин'):
        """Создание нового персонажа"""
        return self.send_message({
            'type': 'create_character',
            'name': name,
            'race': race,
            'class': char_class,
            'strength': 12,
            'agility': 10,
            'intelligence': 8,
            'vitality': 15,
            'luck': 5,
            'gifct1': 'Огненный шар',
            'gifct2': 'Лечение'
        })

    def select_character(self, character_id):
        """Выбор персонажа для игры"""
        return self.send_message({
            'type': 'select_character',
            'character_id': character_id
        })

    def get_characters(self):
        """Получение списка персонажей"""
        return self.send_message({
            'type': 'get_characters'
        })

    def move_character(self, x, y):
        """Перемещение персонажа"""
        return self.send_message({
            'type': 'character_move',
            'position': {'x': x, 'y': y},
            'direction': 'right'
        })

    def use_gifct1(self, target='враг'):
        """Использование Gifct1"""
        return self.send_message({
            'type': 'character_action',
            'action_type': 'use_gifct1',
            'target': target
        })

    def use_gifct2(self, target='себя'):
        """Использование Gifct2"""
        return self.send_message({
            'type': 'character_action',
            'action_type': 'use_gifct2',
            'target': target
        })

    def send_chat(self, message):
        """Отправка сообщения в чат"""
        return self.send_message({
            'type': 'chat_message',
            'message': message
        })

    def update_gifct_settings(self, gifct1=None, gifct2=None):
        """Обновление настроек Gifct на сервере"""
        return self.send_message({
            'type': 'update_gifct',
            'gifct1': gifct1,
            'gifct2': gifct2
        })

    def get_gifct_settings(self):
        """Получение текущих настроек Gifct"""
        return self.send_message({
            'type': 'get_gifct_settings'
        })

    def save_character(self):
        """Сохранение данных персонажа"""
        return self.send_message({
            'type': 'save_character',
            'playtime': 3600  # например, 1 час игры
        })

    def disconnect(self):
        """Отключение от сервера"""
        self.running = False
        if self.socket:
            self.socket.close()

def main():
    """Тестирование клиента"""
    client = GameClient()

    if client.connect():
        print("Подключение успешно!")

        # Тестовый сценарий
        # 1. Регистрация
        client.register("TestPlayer", "password123", "test@example.com")
        time.sleep(1)

        # 2. Вход
        client.login("TestPlayer", "password123")
        time.sleep(1)

        # 3. Создание персонажа
        client.create_character("Рыцарь_Света", "человек", "паладин")
        time.sleep(1)

        # 4. Получение списка персонажей
        client.get_characters()
        time.sleep(1)

        # 5. Обновление настроек Gifct
        client.update_gifct_settings("Огненный шторм", "Божественное исцеление")
        time.sleep(1)

        # 6. Получение настроек Gifct
        client.get_gifct_settings()
        time.sleep(1)

        # 7. Отправка сообщения в чат
        client.send_chat("Привет всем! Это тестовое сообщение.")
        time.sleep(2)

        print("\nТестирование завершено. Ожидание сообщений... (10 секунд)")
        time.sleep(10)

        client.disconnect()
        print("Отключено")
    else:
        print("Не удалось подключиться")

if __name__ == "__main__":
    main()