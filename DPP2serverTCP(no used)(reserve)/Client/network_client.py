#!/usr/bin/env python3
"""
Network Client - Упрощенная и надежная версия
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
        self.client_id = None

    def connect(self):
        """Простое подключение без лишних проверок"""
        try:
            print(f"🔄 Подключение к {self.host}:{self.port}...")

            # Создаем сокет
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Устанавливаем таймаут
            self.socket.settimeout(5.0)

            # Подключаемся
            self.socket.connect((self.host, self.port))

            # Устанавливаем таймаут для операций
            self.socket.settimeout(1.0)

            self.connected = True
            print("✅ Успешно подключено")

            # Ждем немного чтобы сервер был готов
            time.sleep(0.1)

            return True

        except socket.timeout:
            print("❌ Таймаут подключения")
            return False
        except ConnectionRefusedError:
            print("❌ Сервер не отвечает")
            return False
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def send(self, data):
        """Отправка данных в самом простом формате"""
        if not self.connected or not self.socket:
            print("⚠️ Нет подключения")
            return False

        try:
            # Конвертируем данные в JSON
            json_str = json.dumps(data, ensure_ascii=False)

            # ДОБАВЛЯЕМ КОНЕЦ СТРОКИ - это важно!
            message = json_str + '\n'

            # Отправляем
            self.socket.sendall(message.encode('utf-8'))

            # Ждем немного перед отправкой следующего сообщения
            time.sleep(0.01)

            print(f"📤 Отправлено: {data.get('type', 'unknown')[:20]}...")
            return True

        except BrokenPipeError:
            print("❌ Соединение разорвано")
            self.connected = False
            return False
        except socket.error as e:
            print(f"❌ Ошибка сокета: {e}")
            self.connected = False
            return False
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False

    def receive(self):
        """Получение данных с обработкой ошибок"""
        if not self.connected or not self.socket:
            return None

        try:
            # Получаем данные
            data = self.socket.recv(4096)

            if not data:
                print("📭 Сервер закрыл соединение")
                self.connected = False
                return None

            # Декодируем
            decoded = data.decode('utf-8', errors='ignore').strip()

            if not decoded:
                return None

            # Разделяем по строкам
            messages = decoded.split('\n')

            for message in messages:
                if message.strip():
                    try:
                        parsed = json.loads(message.strip())
                        print(f"📥 Получено: {parsed.get('type', 'unknown')[:20]}...")
                        return parsed
                    except json.JSONDecodeError:
                        print(f"⚠️ Некорректный JSON: {message[:50]}...")
                        continue

            return None

        except socket.timeout:
            # Таймаут - это нормально, просто нет данных
            return None
        except ConnectionResetError:
            print("❌ Сервер принудительно разорвал соединение")
            self.connected = False
            return None
        except socket.error as e:
            if e.errno == 10054:  # WinError 10054
                print("❌ Соединение разорвано сервером")
            else:
                print(f"❌ Ошибка сокета: {e}")
            self.connected = False
            return None
        except Exception as e:
            print(f"❌ Ошибка приема: {e}")
            return None

    def is_connected(self):
        """Простая проверка подключения"""
        return self.connected and self.socket is not None

    def disconnect(self):
        """Корректное отключение"""
        if self.socket:
            try:
                # Пробуем отправить сообщение о выходе
                if self.connected:
                    try:
                        exit_msg = {'type': 'disconnect', 'timestamp': datetime.now().isoformat()}
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
        print("📡 Отключено")

    def safe_send(self, data):
        """Безопасная отправка с повторными попытками"""
        for attempt in range(3):
            try:
                return self.send(data)
            except Exception as e:
                print(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
                time.sleep(0.5)
                if attempt == 2:
                    print("❌ Все попытки не удались")
                    self.connected = False
        return False

    def test_connection(self):
        """Тестовое сообщение для проверки соединения"""
        if not self.connected:
            return False

        try:
            test_data = {
                'type': 'test',
                'message': 'ping',
                'timestamp': datetime.now().isoformat()
            }

            print("🔍 Отправка тестового сообщения...")
            return self.send(test_data)
        except Exception as e:
            print(f"❌ Ошибка теста: {e}")
            return False