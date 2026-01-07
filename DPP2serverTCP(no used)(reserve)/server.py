import socket
import threading
import json
import time
import sys
import subprocess
import os
from datetime import datetime
import requests


class DPP2Server:
    def __init__(self, host='0.0.0.0', port=5555, use_cloudflare=True):
        self.host = host
        self.port = port
        self.use_cloudflare = use_cloudflare
        self.server = None
        self.clients = {}
        self.rooms = {}
        self.running = False
        self.cloudflare_process = None
        self.public_url = None
        self.cloudflare_hostname = None

        self.stats = {
            'start_time': None,
            'total_connections': 0,
            'current_connections': 0,
            'messages_sent': 0,
            'rooms_created': 0
        }

    def setup_cloudflare(self):
        """Настраивает Cloudflare Tunnel"""
        if not self.use_cloudflare:
            print("⚠️ Cloudflare Tunnel отключен.")
            return True

        print("🚀 Настройка Cloudflare Tunnel...")
        print("📝 Этот метод БЕСПЛАТНЫЙ и не требует настройки роутера!")

        # Проверяем наличие cloudflared
        if not self.check_cloudflared():
            print("❌ Cloudflared не найден!")
            print("\n📥 Установите Cloudflared:")
            print("1. Скачайте с: https://github.com/cloudflare/cloudflared/releases")
            print("2. Распакуйте cloudflared.exe в папку с сервером")
            print("3. Или запустите без Cloudflare: python server_cloudflare.py --no-cloudflare")
            return False

        try:
            # Запускаем Cloudflare Tunnel
            print("🔗 Запуск Cloudflare Tunnel...")

            # Для разных ОС
            if os.name == 'nt':  # Windows
                cmd = f'cloudflared.exe tunnel --url http://{self.host}:{self.port}'
            else:  # Linux/Mac
                cmd = f'./cloudflared tunnel --url http://{self.host}:{self.port}'

            self.cloudflare_process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Читаем вывод для получения URL
            print("⏳ Ожидание получения публичного URL... (может занять до 60 секунд)")

            timeout = time.time() + 60  # 60 секунд таймаут
            url_found = False

            while time.time() < timeout and not url_found:
                line = self.cloudflare_process.stderr.readline()
                if not line and self.cloudflare_process.poll() is not None:
                    break

                if line:
                    print(f"CLOUDFLARE: {line.strip()}")

                    # Ищем URL в выводе
                    if ".trycloudflare.com" in line:
                        # Пример: https://random-string.trycloudflare.com
                        import re
                        urls = re.findall(r'https://[a-zA-Z0-9\-]+\.trycloudflare\.com', line)
                        if urls:
                            self.public_url = urls[0]
                            self.cloudflare_hostname = self.public_url.replace('https://', '')
                            url_found = True
                            break

            if not url_found:
                # Пробуем другой метод
                self.public_url = self.get_cloudflare_url_alternative()
                if self.public_url:
                    url_found = True

            if url_found:
                print("\n" + "=" * 60)
                print("🌐 CLOUDFLARE TUNNEL АКТИВИРОВАН!")
                print("=" * 60)
                print(f"📡 Публичный URL: {self.public_url}")
                print(f"📍 Хост: {self.cloudflare_hostname}")
                print(f"🔌 Порт: 443 (HTTPS)")
                print("=" * 60)
                print("\n🎮 Друзья могут подключиться по этому адресу!")
                print("📋 Скопируйте URL и отправьте друзьям")
                print("=" * 60 + "\n")
                return True
            else:
                print("❌ Не удалось получить Cloudflare URL")
                return False

        except Exception as e:
            print(f"❌ Ошибка Cloudflare Tunnel: {e}")
            return False

    def check_cloudflared(self):
        """Проверяет наличие cloudflared"""
        # Проверяем в текущей папке
        if os.name == 'nt':
            if os.path.exists('cloudflared.exe'):
                return True
        else:
            if os.path.exists('cloudflared'):
                return True

        # Проверяем в PATH
        try:
            if os.name == 'nt':
                subprocess.run(['cloudflared.exe', '--version'],
                               capture_output=True, shell=True)
            else:
                subprocess.run(['cloudflared', '--version'],
                               capture_output=True)
            return True
        except:
            return False

    def get_cloudflare_url_alternative(self):
        """Альтернативный способ получения URL"""
        try:
            # Пробуем получить через локальный API Cloudflare
            import urllib.request
            response = urllib.request.urlopen('http://localhost:45678/metrics', timeout=5)
            data = response.read().decode('utf-8')

            # Парсим метрики для поиска URL
            for line in data.split('\n'):
                if 'tunnel_hostname' in line:
                    parts = line.split('"')
                    if len(parts) > 1:
                        hostname = parts[1]
                        return f"https://{hostname}"

        except:
            pass

        return None

    def stop_cloudflare(self):
        """Останавливает Cloudflare Tunnel"""
        if self.cloudflare_process:
            try:
                self.cloudflare_process.terminate()
                self.cloudflare_process.wait(timeout=5)
                print("✅ Cloudflare Tunnel остановлен")
            except:
                try:
                    self.cloudflare_process.kill()
                except:
                    pass

    def get_local_ip(self):
        """Получает локальный IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def get_public_ip(self):
        """Получает публичный IP"""
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            if response.status_code == 200:
                return response.json()['ip']
        except:
            pass
        return "Не определен"

    def print_server_info(self):
        """Выводит информацию о сервере"""
        local_ip = self.get_local_ip()
        public_ip = self.get_public_ip()

        print("\n" + "=" * 60)
        print("🚀 DPP2 MULTIPLAYER SERVER")
        print("=" * 60)
        print(f"📍 Локальный IP: {local_ip}")
        print(f"🌐 Публичный IP: {public_ip}")
        print(f"🔌 Порт: {self.port}")

        if self.use_cloudflare and self.public_url:
            print(f"📡 Cloudflare URL: {self.public_url}")
            print("🎮 Подключение из интернета: ДА (через Cloudflare)")
        elif self.use_cloudflare:
            print("🎮 Подключение из интернета: Cloudflare запускается...")
        else:
            print("🎮 Подключение из интернета: Требуется Port Forwarding")

        print("=" * 60)
        print("📋 Способы подключения для друзей:")
        print("=" * 60)

        if self.public_url:
            print(f"1. Через Cloudflare: {self.public_url}")

        print(f"2. Через локальную сеть: {local_ip}:{self.port}")

        if public_ip != "Не определен":
            print(f"3. Через интернет (если настроен Port Forwarding): {public_ip}:{self.port}")

        print("=" * 60 + "\n")

        # Инструкция по Port Forwarding
        if not self.use_cloudflare or not self.public_url:
            print("📚 ИНСТРУКЦИЯ ПО PORT FORWARDING:")
            print("=" * 60)
            print("1. Зайдите в настройки роутера (обычно 192.168.1.1)")
            print("2. Найдите 'Port Forwarding' или 'Виртуальные серверы'")
            print("3. Добавьте правило:")
            print(f"   - Порт: {self.port} (внешний и внутренний)")
            print(f"   - IP адрес: {local_ip}")
            print("   - Протокол: TCP")
            print("4. Сохраните и перезагрузите роутер")
            print("5. Дайте друзьям ваш публичный IP: " + public_ip)
            print("=" * 60 + "\n")

        print("📡 Ожидание подключений...")
        print("🛑 Для остановки сервера нажмите Ctrl+C\n")

    # Остальные методы такие же как в предыдущем сервере
    def start(self):
        """Запускает сервер"""
        try:
            # Запускаем Cloudflare если нужно
            if self.use_cloudflare:
                cf_success = self.setup_cloudflare()
                if not cf_success:
                    print("⚠️ Продолжаем без Cloudflare...")

            # Создаем серверный сокет
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host, self.port))
            self.server.listen(10)
            self.server.settimeout(1)

            self.running = True
            self.stats['start_time'] = datetime.now()

            # Показываем информацию
            self.print_server_info()

            # Запускаем потоки
            accept_thread = threading.Thread(target=self.accept_clients, daemon=True)
            accept_thread.start()

            # Главный цикл
            self.main_loop()

        except Exception as e:
            print(f"❌ Ошибка запуска сервера: {e}")
            self.stop()

    def accept_clients(self):
        """Принимает подключения"""
        while self.running:
            try:
                client_socket, address = self.server.accept()
                client_socket.settimeout(30)

                if self.running:
                    self.handle_new_client(client_socket, address)

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️ Ошибка accept: {e}")

    def handle_new_client(self, client_socket, address):
        """Обрабатывает новое подключение"""
        self.stats['total_connections'] += 1
        self.stats['current_connections'] += 1

        client_id = f"Player_{self.stats['total_connections']}"
        print(f"🔗 Подключение #{self.stats['total_connections']} от: {address[0]}")

        # Добавляем клиента
        self.clients[client_socket] = {
            'address': address,
            'username': client_id,
            'room': 'lobby',
            'last_activity': time.time(),
            'id': client_id
        }

        # Добавляем в комнату
        if 'lobby' not in self.rooms:
            self.rooms['lobby'] = []
        self.rooms['lobby'].append(client_socket)

        # Приветствие
        welcome_msg = {
            'type': 'server_info',
            'message': f'Добро пожаловать! Вы: {client_id}',
            'server_name': 'DPP2 Server',
            'online': self.stats['current_connections'],
            'your_id': client_id,
            'public_url': self.public_url,
            'timestamp': time.time()
        }
        self.send_json(client_socket, welcome_msg)

        # Уведомляем других
        join_msg = {
            'type': 'player_joined',
            'username': client_id,
            'online': self.stats['current_connections'],
            'timestamp': time.time()
        }
        self.broadcast(join_msg, exclude=client_socket)

        # Обработчик клиента
        client_thread = threading.Thread(
            target=self.client_handler,
            args=(client_socket, address),
            daemon=True
        )
        client_thread.start()

    def client_handler(self, client_socket, address):
        """Обрабатывает клиента"""
        client_info = self.clients.get(client_socket)
        if not client_info:
            return

        try:
            while self.running and client_socket in self.clients:
                try:
                    data = client_socket.recv(4096).decode('utf-8')

                    if not data:
                        break

                    client_info['last_activity'] = time.time()

                    messages = data.split('|||')
                    for msg in messages:
                        if msg.strip():
                            self.process_message(client_socket, msg.strip())

                except socket.timeout:
                    if time.time() - client_info['last_activity'] > 60:
                        print(f"⏰ Таймаут клиента {client_info['username']}")
                        break
                    continue
                except:
                    break

        except:
            pass

        finally:
            self.disconnect_client(client_socket)

    def process_message(self, client_socket, raw_message):
        """Обрабатывает сообщение"""
        try:
            message = json.loads(raw_message)
            msg_type = message.get('type')
            client_info = self.clients[client_socket]

            if msg_type == 'chat':
                chat_msg = {
                    'type': 'chat',
                    'username': client_info['username'],
                    'message': message.get('message', ''),
                    'room': client_info['room'],
                    'timestamp': time.time()
                }
                self.send_to_room(client_info['room'], chat_msg)
                self.stats['messages_sent'] += 1

            elif msg_type == 'pony_move':
                move_msg = {
                    'type': 'pony_move',
                    'player_id': client_info['id'],
                    'username': client_info['username'],
                    'position': message.get('position', {}),
                    'animation': message.get('animation', 'idle'),
                    'timestamp': time.time()
                }
                self.send_to_room(client_info['room'], move_msg, exclude=client_socket)

            elif msg_type == 'get_players':
                room_players = []
                if client_info['room'] in self.rooms:
                    for sock in self.rooms[client_info['room']]:
                        if sock in self.clients:
                            room_players.append({
                                'id': self.clients[sock]['id'],
                                'username': self.clients[sock]['username']
                            })

                response = {
                    'type': 'players_list',
                    'players': room_players,
                    'timestamp': time.time()
                }
                self.send_json(client_socket, response)

            elif msg_type == 'ping':
                response = {'type': 'pong', 'timestamp': time.time()}
                self.send_json(client_socket, response)

        except json.JSONDecodeError:
            print(f"⚠️ Невалидный JSON: {raw_message}")
        except Exception as e:
            print(f"⚠️ Ошибка обработки: {e}")

    def send_json(self, client_socket, data):
        """Отправляет JSON"""
        try:
            json_data = json.dumps(data, ensure_ascii=False) + '|||'
            client_socket.send(json_data.encode('utf-8'))
        except:
            self.disconnect_client(client_socket)

    def send_to_room(self, room_name, message, exclude=None):
        """Отправляет в комнату"""
        if room_name in self.rooms:
            for client in self.rooms[room_name]:
                if client != exclude and client in self.clients:
                    self.send_json(client, message)

    def broadcast(self, message, exclude=None):
        """Широковещательная рассылка"""
        for client_socket in list(self.clients.keys()):
            if client_socket != exclude:
                self.send_json(client_socket, message)

    def disconnect_client(self, client_socket):
        """Отключает клиента"""
        if client_socket in self.clients:
            client_info = self.clients[client_socket]
            username = client_info['username']

            # Удаляем из комнаты
            if client_info['room'] in self.rooms:
                if client_socket in self.rooms[client_info['room']]:
                    self.rooms[client_info['room']].remove(client_socket)

            # Уведомляем
            leave_msg = {
                'type': 'player_left',
                'username': username,
                'online': self.stats['current_connections'] - 1,
                'timestamp': time.time()
            }
            self.broadcast(leave_msg, exclude=client_socket)

            # Закрываем соединение
            try:
                client_socket.close()
            except:
                pass

            # Удаляем
            del self.clients[client_socket]
            self.stats['current_connections'] -= 1

            print(f"🔌 Отключен: {username}")

    def print_stats(self):
        """Выводит статистику"""
        if self.stats['start_time']:
            uptime = datetime.now() - self.stats['start_time']
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            print("\n" + "=" * 50)
            print("📊 СТАТИСТИКА СЕРВЕРА")
            print(f"⏱️  Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}")
            print(f"👥 Онлайн: {self.stats['current_connections']}/{self.stats['total_connections']}")
            print(f"💬 Сообщений: {self.stats['messages_sent']}")

            if self.public_url:
                print(f"🌐 Cloudflare URL: {self.public_url}")

            print("=" * 50)

    def main_loop(self):
        """Главный цикл"""
        last_stats_time = time.time()

        try:
            while self.running:
                if time.time() - last_stats_time > 30:
                    self.print_stats()
                    last_stats_time = time.time()

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки...")
        finally:
            self.stop()

    def stop(self):
        """Останавливает сервер"""
        print("\n🛑 Остановка сервера...")
        self.running = False

        # Отключаем клиентов
        for client_socket in list(self.clients.keys()):
            self.disconnect_client(client_socket)

        # Останавливаем Cloudflare
        self.stop_cloudflare()

        # Закрываем сервер
        if self.server:
            try:
                self.server.close()
            except:
                pass

        # Статистика
        self.print_stats()
        print("\n✅ Сервер остановлен")

        time.sleep(2)
        sys.exit(0)


def main():
    """Точка входа"""
    print("🚀 Запуск DPP2 Server с Cloudflare поддержкой...")

    import argparse
    parser = argparse.ArgumentParser(description='DPP2 Server с интернет-доступом')
    parser.add_argument('--host', default='0.0.0.0', help='Хост сервера')
    parser.add_argument('--port', type=int, default=5555, help='Порт сервера')
    parser.add_argument('--no-cloudflare', action='store_true', help='Отключить Cloudflare')

    args = parser.parse_args()

    # Запускаем сервер
    server = DPP2Server(
        host=args.host,
        port=args.port,
        use_cloudflare=not args.no_cloudflare
    )

    server.start()


if __name__ == "__main__":
    # Проверяем requests
    try:
        import requests
    except ImportError:
        print("⚠️ Устанавливаем requests...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
            print("✅ requests установлен")
        except:
            print("❌ Не удалось установить requests")

    main()