import socket
import threading
import json
import struct
import time
from datetime import datetime


class ClientConnection:
    def __init__(self, sock, address, client_id):
        self.socket = sock
        self.address = address
        self.id = client_id
        self.username = f"Player_{client_id}"
        self.player_id = None
        self.last_activity = time.time()
        self.authenticated = False
        self.ping = 0
        self.send_lock = threading.Lock()
        self.buffer = b""  # <--- ДОБАВЛЕНО: буфер для неполных сообщений

    def send(self, data):
        """Отправка данных клиенту - УПРОЩЕННАЯ версия"""
        with self.send_lock:
            try:
                # Просто отправляем JSON с переводом строки
                message = json.dumps(data, ensure_ascii=False) + '\n'
                self.socket.sendall(message.encode('utf-8'))
                return True
            except Exception as e:
                print(f"[NETWORK] Ошибка отправки клиенту {self.id}: {e}")
                return False

    def close(self):
        """Закрытие соединения"""
        try:
            self.socket.close()
        except:
            pass


class NetworkServer:
    def __init__(self, host='0.0.0.0', port=5555, max_clients=100):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.running = False

        self.clients = {}  # client_id -> ClientConnection
        self.client_counter = 1

        self.server_socket = None
        self.message_queue = []
        self.queue_lock = threading.Lock()

    def start(self):
        """Запуск сервера"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.max_clients)
            self.server_socket.settimeout(1.0)

            self.running = True

            # Запускаем потоки
            self.accept_thread = threading.Thread(target=self.accept_clients, daemon=True)
            self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)

            self.accept_thread.start()
            self.receive_thread.start()

            print(f"[NETWORK] Сервер запущен на {self.host}:{self.port}")
            return True

        except Exception as e:
            print(f"[NETWORK] Ошибка запуска: {e}")
            return False

    def stop(self):
        """Остановка сервера"""
        self.running = False

        # Закрываем все соединения
        for client in list(self.clients.values()):
            client.close()
        self.clients.clear()

        if self.server_socket:
            self.server_socket.close()

        print("[NETWORK] Сервер остановлен")

    def accept_clients(self):
        """Принятие новых подключений"""
        print("[NETWORK] Ожидание подключений...")

        while self.running:
            try:
                client_socket, address = self.server_socket.accept()

                if len(self.clients) >= self.max_clients:
                    client_socket.close()
                    continue

                client_id = self.client_counter
                self.client_counter += 1

                # Настройка сокета клиента
                client_socket.settimeout(1.0)  # Небольшой таймаут

                client = ClientConnection(client_socket, address, client_id)
                self.clients[client_id] = client

                print(f"[NETWORK] Новое подключение: {address} (ID: {client_id})")

                # Отправляем приветственное сообщение - ПРОСТОЙ ФОРМАТ
                welcome_msg = {
                    'type': 'welcome',
                    'client_id': client_id,
                    'message': 'Connected to DPP2 Server',
                    'timestamp': time.time()
                }
                client.send(welcome_msg)

                # Добавляем событие подключения в очередь
                self.add_to_queue({
                    'type': 'client_connected',
                    'client_id': client_id,
                    'address': address
                })

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[NETWORK] Ошибка принятия клиента: {e}")

    def receive_messages(self):
        """Прием сообщений от клиентов - УПРОЩЕННАЯ версия"""
        print("[NETWORK] Начало приема сообщений...")

        while self.running:
            clients_to_remove = []

            for client_id, client in list(self.clients.items()):
                try:
                    # Проверяем, есть ли данные
                    ready = self.check_socket_ready(client.socket)
                    if not ready:
                        continue

                    # Получаем данные
                    try:
                        data = client.socket.recv(4096)
                    except socket.timeout:
                        continue  # Таймаут - это нормально

                    if not data:
                        clients_to_remove.append(client_id)
                        continue

                    # Добавляем в буфер клиента
                    client.buffer += data

                    # Обрабатываем буфер
                    self._process_client_buffer(client_id, client)

                    # Обновляем время активности
                    client.last_activity = time.time()

                except (ConnectionResetError, ConnectionAbortedError):
                    clients_to_remove.append(client_id)
                except socket.timeout:
                    continue  # Игнорируем таймауты
                except Exception as e:
                    print(f"[NETWORK] Ошибка чтения от клиента {client_id}: {e}")
                    clients_to_remove.append(client_id)

            # Удаляем отключившихся клиентов
            for client_id in clients_to_remove:
                self.remove_client(client_id)

            time.sleep(0.01)

    # В методе _process_client_buffer добавьте отладочный вывод:

    def _process_client_buffer(self, client_id, client):
        """Обработка буфера клиента для извлечения сообщений"""
        try:
            # Преобразуем буфер в строку
            buffer_str = client.buffer.decode('utf-8', errors='ignore')

            if buffer_str:
                print(f"[NETWORK] Буфер клиента {client_id}: {repr(buffer_str)}")

            # Разделяем по символам новой строки
            lines = buffer_str.split('\n')

            # Обрабатываем каждую строку, кроме последней (которая может быть неполной)
            for line in lines[:-1]:
                if line.strip():  # Пропускаем пустые строки
                    try:
                        # Очищаем от лишних символов
                        clean_line = line.strip()

                        # Удаляем непечатаемые символы в начале строки
                        while clean_line and not clean_line[0].isprintable():
                            clean_line = clean_line[1:]

                        if not clean_line:
                            continue

                        print(f"[NETWORK] Строка от {client_id}: {repr(clean_line[:100])}")

                        # Пытаемся распарсить JSON
                        message = json.loads(clean_line)

                        # Добавляем client_id
                        message['client_id'] = client_id
                        message['timestamp'] = time.time()

                        # Добавляем в очередь
                        self.add_to_queue(message)

                        print(f"[NETWORK] Успешно распаршено от {client_id}: {message.get('type', 'unknown')}")

                    except json.JSONDecodeError as e:
                        print(f"[NETWORK] Неверный JSON от клиента {client_id}: {clean_line[:100]}...")
                        print(f"[NETWORK] Ошибка: {e}")
                    except Exception as e:
                        print(f"[NETWORK] Ошибка обработки сообщения от {client_id}: {e}")

            # Сохраняем последнюю (возможно неполную) строку в буфере
            last_line = lines[-1] if lines[-1] else ""
            client.buffer = last_line.encode('utf-8')

        except Exception as e:
            print(f"[NETWORK] Ошибка обработки буфера клиента {client_id}: {e}")
            client.buffer = b""  # Очищаем буфер при ошибке



    def check_socket_ready(self, sock):
        """Проверка готовности сокета к чтению"""
        import select
        try:
            ready, _, _ = select.select([sock], [], [], 0)
            return bool(ready)
        except:
            return False

    def add_to_queue(self, message):
        """Добавление сообщения в очередь"""
        with self.queue_lock:
            self.message_queue.append(message)

    def get_messages(self):
        """Получение всех сообщений из очереди"""
        with self.queue_lock:
            messages = self.message_queue.copy()
            self.message_queue.clear()
            return messages

    def send_to_client(self, client_id, data):
        """Отправка сообщения конкретному клиенту"""
        client = self.clients.get(client_id)
        if client:
            return client.send(data)
        return False

    def broadcast(self, data, exclude_client_id=None):
        """Широковещательная рассылка с исключением"""
        results = []
        for client_id, client in list(self.clients.items()):
            if exclude_client_id and client_id == exclude_client_id:
                continue
            success = client.send(data)
            results.append((client_id, success))
        return results

    def remove_client(self, client_id):
        """Удаление клиента"""
        client = self.clients.pop(client_id, None)
        if client:
            print(f"[NETWORK] Клиент отключен: {client.address} (ID: {client_id})")
            client.close()

            # Добавляем событие отключения в очередь
            self.add_to_queue({
                'type': 'client_disconnected',
                'client_id': client_id,
                'username': client.username
            })

    def check_timeouts(self, timeout=0):
        """Проверка таймаутов соединений"""
        current_time = time.time()
        clients_to_remove = []

        for client_id, client in self.clients.items():
            if current_time - client.last_activity > timeout:
                clients_to_remove.append(client_id)

        for client_id in clients_to_remove:
            self.remove_client(client_id)

        return len(clients_to_remove)

    def get_connected_clients(self):
        """Получение списка подключенных клиентов"""
        return [
            {
                'id': client.id,
                'username': client.username,
                'address': client.address,
                'authenticated': client.authenticated,
                'ping': client.ping
            }
            for client in self.clients.values()
        ]