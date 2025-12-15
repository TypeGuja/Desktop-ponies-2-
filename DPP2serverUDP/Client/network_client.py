#!/usr/bin/env python3
"""
Network Client - UDP версия
"""

import socket
import json
import time
from datetime import datetime


class NetworkClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.client_id = None  # ID клиента, устанавливается извне
        self.server_address = None

        # Для имитации надежности
        self.packet_counter = 0
        self.last_packet_time = 0
        self.packet_timeout = 2.0
        self.max_packet_size = 1400

    def connect(self):
        """Подключение через UDP (без установки соединения)"""
        try:
            print(f"🔄 Подключение к {self.host}:{self.port} через UDP...")

            # Создаем UDP сокет
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Устанавливаем таймауты
            self.socket.settimeout(1.0)

            # Сохраняем адрес сервера
            self.server_address = (self.host, self.port)

            # Для UDP нет реального "подключения", просто пометим как готовое
            self.connected = True

            print(f"✅ UDP клиент инициализирован (client_id: {self.client_id})")
            return True

        except socket.timeout:
            print("❌ Таймаут подключения")
            return False
        except Exception as e:
            print(f"❌ Ошибка инициализации UDP: {e}")
            return False

    def send(self, data):
        """Отправка данных через UDP"""
        if not self.connected or not self.socket:
            print("⚠️ Нет подключения")
            return False

        try:
            # Добавляем client_id в каждое сообщение если он есть
            if self.client_id and 'client_id' not in data:
                data['client_id'] = self.client_id

            # Добавляем счетчик пакетов и метку времени
            self.packet_counter += 1
            data['packet_id'] = self.packet_counter
            data['timestamp'] = datetime.now().isoformat()

            # Конвертируем данные в JSON
            json_str = json.dumps(data, ensure_ascii=False)

            # Проверяем размер пакета
            if len(json_str.encode('utf-8')) > self.max_packet_size:
                print(f"⚠️ Пакет слишком большой: {len(json_str)} байт")
                json_str = json_str[:500] + '..."}'

            # Отправляем через UDP
            self.socket.sendto(json_str.encode('utf-8'), self.server_address)

            self.last_packet_time = time.time()

            print(f"📤 UDP отправлено: {data.get('type', 'unknown')[:20]}... (id: {self.packet_counter}, client_id: {self.client_id})")
            return True

        except socket.error as e:
            print(f"❌ Ошибка отправки UDP: {e}")
            return False
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False

    def receive(self):
        """Получение данных через UDP"""
        if not self.connected or not self.socket:
            return None

        try:
            # Получаем данные (максимальный размер 4096 байт)
            data, address = self.socket.recvfrom(4096)

            # Проверяем, что сообщение от сервера
            if address == self.server_address:
                # Декодируем
                decoded = data.decode('utf-8', errors='ignore').strip()

                if not decoded:
                    return None

                try:
                    parsed = json.loads(decoded)
                    print(f"📥 UDP получено: {parsed.get('type', 'unknown')[:20]}...")
                    return parsed
                except json.JSONDecodeError:
                    print(f"⚠️ Некорректный JSON в UDP: {decoded[:50]}...")
                    return None

            # Если сообщение не от нашего сервера, игнорируем
            print(f"⚠️ Получен пакет от неизвестного адреса: {address}")
            return None

        except socket.timeout:
            # Таймаут - это нормально для UDP
            return None
        except socket.error as e:
            print(f"❌ Ошибка приема UDP: {e}")
            return None
        except Exception as e:
            print(f"❌ Ошибка приема: {e}")
            return None

    def is_connected(self):
        """Проверка подключения для UDP"""
        return self.connected and self.socket is not None

    def disconnect(self):
        """Корректное отключение UDP"""
        if self.socket:
            try:
                # Пробуем отправить сообщение о выходе
                if self.connected:
                    try:
                        exit_msg = {
                            'type': 'client_disconnect',
                            'client_id': self.client_id,
                            'timestamp': datetime.now().isoformat(),
                            'packet_id': self.packet_counter + 1
                        }
                        self.send(exit_msg)
                        time.sleep(0.1)
                    except:
                        pass

                # Закрываем сокет
                self.socket.close()
            except:
                pass

        self.connected = False
        self.socket = None
        print("📡 UDP отключено")

    def safe_send(self, data):
        """Безопасная отправка с повторными попытками для UDP"""
        for attempt in range(3):
            try:
                result = self.send(data)
                if result:
                    return True
                else:
                    print(f"⚠️ Попытка {attempt + 1} не удалась")
                    time.sleep(0.1)
            except Exception as e:
                print(f"⚠️ Попытка {attempt + 1} вызвала ошибку: {e}")
                time.sleep(0.1)

        print("❌ Все попытки отправки не удались")
        return False

    def test_connection(self):
        """Тестовое сообщение для проверки соединения через UDP"""
        if not self.connected:
            return False

        try:
            test_data = {
                'type': 'ping',
                'client_id': self.client_id,
                'message': 'ping',
                'timestamp': datetime.now().isoformat()
            }

            print("🔍 Отправка UDP ping...")
            return self.send(test_data)
        except Exception as e:
            print(f"❌ Ошибка теста: {e}")
            return False

    def send_heartbeat(self):
        """Отправка heartbeat для поддержания соединения"""
        if not self.connected:
            return False

        heartbeat_data = {
            'type': 'heartbeat',
            'client_id': self.client_id,
            'timestamp': datetime.now().isoformat(),
            'packet_id': self.packet_counter + 1
        }

        return self.send(heartbeat_data)