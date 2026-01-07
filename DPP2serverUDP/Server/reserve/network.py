import socket
import threading
import json
import time
import select
from datetime import datetime
from typing import Dict, Tuple, Optional, Any


class UDPClientConnection:
    """Клиентское соединение для UDP"""

    def __init__(self, address, client_id):
        self.address = address
        self.id = client_id
        self.username = f"Player_{client_id}"
        self.player_id = None
        self.last_activity = time.time()
        self.authenticated = False
        self.ping = 0
        self.packet_counter = 0
        self.last_packet_time = 0
        self.packet_loss = 0
        self.connected = True
        self.character_id = None
        self.character_data = {}
        self.in_world = False

    def update_activity(self):
        """Обновление времени последней активности"""
        self.last_activity = time.time()
        self.last_packet_time = time.time()

    def is_timed_out(self, timeout=10):
        """Проверка таймаута соединения"""
        return time.time() - self.last_activity > timeout

    def __str__(self):
        return f"UDPClient[{self.id}]: {self.address} ({self.username})"


class UDPServer:
    """UDP сервер для игры"""

    def __init__(self, host='0.0.0.0', port=5555, max_clients=100):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.running = False
        self.socket = None

        # Структуры данных
        self.clients: Dict[Tuple[str, int], UDPClientConnection] = {}
        self.clients_by_id: Dict[int, UDPClientConnection] = {}

        # Очереди
        self.incoming_queue = []
        self.outgoing_queue = []
        self.queue_lock = threading.Lock()

        # Счетчики и настройки
        self.client_counter = 1
        self.packets_received = 0
        self.packets_sent = 0
        self.packet_loss = 0
        self.packet_timeout = 2.0
        self.client_timeout = 30.0
        self.max_packet_size = 1400

        # Потоки
        self.receive_thread = None
        self.send_thread = None
        self.cleanup_thread = None

    def start(self):
        """Запуск UDP сервера"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.setblocking(False)

            self.running = True
            self._start_threads()

            print(f"[UDP SERVER] Сервер запущен на {self.host}:{self.port}")
            print(f"[UDP SERVER] Протокол: UDP, Max clients: {self.max_clients}")
            return True

        except Exception as e:
            print(f"[UDP SERVER] Ошибка запуска: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _start_threads(self):
        """Запуск рабочих потоков"""
        threads = [
            (self.receive_loop, "receive"),
            (self.send_loop, "send"),
            (self.cleanup_loop, "cleanup")
        ]

        for target, name in threads:
            thread = threading.Thread(target=target, daemon=True, name=f"UDP_{name}")
            thread.start()
            setattr(self, f"{name}_thread", thread)

    def stop(self):
        """Остановка сервера"""
        self.running = False

        # Отправляем сообщения о выходе
        disconnect_msg = {
            'type': 'server_shutdown',
            'message': 'Сервер выключается',
            'timestamp': time.time()
        }

        for client in list(self.clients.values()):
            self.send_to_address(client.address, disconnect_msg)

        if self.socket:
            self.socket.close()

        print(f"[UDP SERVER] Сервер остановлен")

    def receive_loop(self):
        """Цикл приема UDP пакетов"""
        print(f"[UDP SERVER] Цикл приема запущен")

        while self.running:
            try:
                ready_to_read, _, _ = select.select([self.socket], [], [], 0.1)
                if ready_to_read:
                    self._receive_packet()
            except Exception as e:
                if self.running:
                    print(f"[UDP SERVER] Ошибка в цикле приема: {e}")

    def _receive_packet(self):
        """Прием и обработка одного пакета"""
        try:
            data, address = self.socket.recvfrom(self.max_packet_size)
            if data:
                self.packets_received += 1
                self._process_packet_data(data, address)
        except socket.error as e:
            if self.running:
                print(f"[UDP SERVER] Ошибка приема: {e}")

    def _process_packet_data(self, data: bytes, address: Tuple[str, int]):
        """Обработка данных пакета"""
        try:
            json_str = data.decode('utf-8', errors='ignore').strip()
            if not json_str:
                return

            message = json.loads(json_str)
            message['client_address'] = address

            client = self.get_or_create_client(address)
            if client:
                client.update_activity()
                message['client_id'] = client.id

                with self.queue_lock:
                    self.incoming_queue.append(message)

                # Логирование (только для отладки)
                msg_type = message.get('type', 'unknown')
                if msg_type not in ['heartbeat', 'ping']:
                    print(f"[UDP SERVER] Получено от {client.id}: {msg_type}")

        except json.JSONDecodeError:
            print(f"[UDP SERVER] Неверный JSON от {address}")
        except Exception as e:
            print(f"[UDP SERVER] Ошибка обработки пакета: {e}")

    def send_loop(self):
        """Цикл отправки UDP пакетов"""
        print(f"[UDP SERVER] Цикл отправки запущен")

        while self.running:
            try:
                with self.queue_lock:
                    if self.outgoing_queue:
                        address, data = self.outgoing_queue.pop(0)
                        self._send_packet(address, data)
                time.sleep(0.001)
            except Exception as e:
                if self.running:
                    print(f"[UDP SERVER] Ошибка в цикле отправки: {e}")

    def _send_packet(self, address: Tuple[str, int], data: dict):
        """Отправка одного пакета"""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            packet = json_str.encode('utf-8')

            if len(packet) > self.max_packet_size:
                print(f"[UDP SERVER] Пакет слишком большой: {len(packet)} байт")
                return

            self.socket.sendto(packet, address)
            self.packets_sent += 1
        except Exception as e:
            print(f"[UDP SERVER] Ошибка отправки: {e}")

    def cleanup_loop(self):
        """Цикл очистки неактивных клиентов"""
        while self.running:
            try:
                time.sleep(5)
                self._cleanup_inactive_clients()
            except Exception as e:
                if self.running:
                    print(f"[UDP SERVER] Ошибка в цикле очистки: {e}")

    def _cleanup_inactive_clients(self):
        """Очистка неактивных клиентов"""
        current_time = time.time()
        clients_to_remove = []

        for address, client in list(self.clients.items()):
            if current_time - client.last_activity > self.client_timeout:
                clients_to_remove.append((address, client))

        for address, client in clients_to_remove:
            self.remove_client_by_address(address)
            print(f"[UDP SERVER] Клиент удален по таймауту: {client}")

    def get_or_create_client(self, address: Tuple[str, int]) -> Optional[UDPClientConnection]:
        """Получение или создание клиента"""
        if address in self.clients:
            return self.clients[address]

        if len(self.clients) >= self.max_clients:
            print(f"[UDP SERVER] Достигнут лимит клиентов")
            return None

        client_id = self.client_counter
        self.client_counter += 1

        client = UDPClientConnection(address, client_id)
        self.clients[address] = client
        self.clients_by_id[client_id] = client

        print(f"[UDP SERVER] Новый клиент: {client}")

        # Отправляем приветственное сообщение
        self.send_to_address(address, {
            'type': 'welcome',
            'client_id': client_id,
            'message': 'Connected to DPP2 UDP Server',
            'timestamp': time.time(),
            'server_info': {
                'protocol': 'udp',
                'max_clients': self.max_clients,
                'server_time': datetime.now().isoformat()
            }
        })

        # Добавляем событие подключения
        self.add_to_incoming_queue({
            'type': 'client_connected',
            'client_id': client_id,
            'address': address,
            'timestamp': time.time()
        })

        return client

    # Вспомогательные методы (без изменений)
    def send_to_address(self, address: Tuple[str, int], data: dict):
        """Отправка данных на конкретный адрес"""
        with self.queue_lock:
            self.outgoing_queue.append((address, data))

    def send_to_client(self, client_id: int, data: dict):
        """Отправка данных клиенту по ID"""
        client = self.clients_by_id.get(client_id)
        if client:
            self.send_to_address(client.address, data)
            return True
        return False

    def broadcast(self, data: dict, exclude_client_id: int = None):
        """Широковещательная рассылка"""
        for client_id, client in self.clients_by_id.items():
            if exclude_client_id and client_id == exclude_client_id:
                continue
            self.send_to_address(client.address, data)

    def get_messages(self):
        """Получение всех сообщений из очереди"""
        with self.queue_lock:
            messages = self.incoming_queue.copy()
            self.incoming_queue.clear()
            return messages

    def add_to_incoming_queue(self, message: dict):
        """Добавление сообщения во входящую очередь"""
        with self.queue_lock:
            self.incoming_queue.append(message)

    def remove_client_by_address(self, address: Tuple[str, int]):
        """Удаление клиента по адресу"""
        if address in self.clients:
            client = self.clients.pop(address)

            if client.id in self.clients_by_id:
                del self.clients_by_id[client.id]

            self.add_to_incoming_queue({
                'type': 'client_disconnected',
                'client_id': client.id,
                'address': address,
                'username': client.username,
                'timestamp': time.time()
            })

            print(f"[UDP SERVER] Клиент удален: {client}")

    def remove_client_by_id(self, client_id: int):
        """Удаление клиента по ID"""
        client = self.clients_by_id.get(client_id)
        if client:
            self.remove_client_by_address(client.address)

    def get_client_info(self, client_id: int):
        """Получение информации о клиенте"""
        client = self.clients_by_id.get(client_id)
        if client:
            return {
                'id': client.id,
                'address': client.address,
                'username': client.username,
                'authenticated': client.authenticated,
                'in_world': client.in_world,
                'character_id': client.character_id,
                'last_activity': client.last_activity,
                'ping': client.ping
            }
        return None

    def get_all_clients_info(self):
        """Получение информации обо всех клиентах"""
        return [{
            'id': client.id,
            'address': client.address,
            'username': client.username,
            'authenticated': client.authenticated,
            'in_world': client.in_world,
            'character_id': client.character_id,
            'last_activity': client.last_activity,
            'ping': client.ping
        } for client in self.clients.values()]

    def update_client_data(self, client_id: int, updates: dict):
        """Обновление данных клиента"""
        client = self.clients_by_id.get(client_id)
        if client:
            for key, value in updates.items():
                setattr(client, key, value)
            return True
        return False

    def get_stats(self):
        """Получение статистики сервера"""
        return {
            'running': self.running,
            'clients_count': len(self.clients),
            'packets_received': self.packets_received,
            'packets_sent': self.packets_sent,
            'packet_loss': self.packet_loss,
            'max_clients': self.max_clients,
            'uptime': time.time() - (getattr(self, 'start_time', time.time()))
        }