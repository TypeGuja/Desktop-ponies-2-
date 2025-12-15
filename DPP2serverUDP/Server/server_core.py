import time
import threading
import json
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)


class ServerCore:
    """Ядро UDP сервера"""

    def __init__(self, config_file='config.json'):
        self.load_config(config_file)

        from database import Database
        from network import UDPServer  # Импортируем UDP версию
        from game_logic import GameLogic

        self.db = Database()
        self.network = UDPServer(
            host=self.config['server']['host'],
            port=self.config['server']['port'],
            max_clients=self.config['server']['max_players']
        )
        self.game = GameLogic(self.db)

        self.running = False
        self.tick_rate = self.config['server']['tick_rate']
        self.tick_interval = 1.0 / self.tick_rate

        self.stats = {
            'start_time': time.time(),
            'ticks_processed': 0,
            'messages_processed': 0,
            'players_connected': 0,
            'characters_created': 0,
            'udp_packets_received': 0,
            'udp_packets_sent': 0
        }

        print(f"{Fore.GREEN}DPP2 UDP Character Server Core initialized")
        print(f"{Fore.CYAN}Protocol: UDP, Port: {self.config['server']['port']}")

    def load_config(self, config_file):
        """Загрузка конфигурации"""
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            print(f"{Fore.CYAN}Конфигурация загружена из {config_file}")
        except Exception as e:
            print(f"{Fore.RED}Ошибка загрузки конфигурации: {e}")
            self.config = {
                'server': {
                    'host': '0.0.0.0',
                    'port': 5555,
                    'max_players': 100,
                    'tick_rate': 60,
                    'server_name': 'DPP2 UDP Character Server',
                    'protocol': 'udp'
                }
            }

    def start(self):
        """Запуск UDP сервера"""
        print(f"{Fore.YELLOW}Запуск UDP сервера персонажей...")

        if not self.network.start():
            print(f"{Fore.RED}Не удалось запустить UDP сервер")
            return False

        self.running = True

        self.main_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.main_thread.start()

        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        print(f"{Fore.GREEN}UDP сервер запущен на {self.config['server']['host']}:{self.config['server']['port']}")
        print(f"{Fore.CYAN}Нажмите Ctrl+C для остановки")

        return True

    def stop(self):
        """Остановка сервера"""
        print(f"{Fore.YELLOW}Остановка UDP сервера...")

        self.running = False

        # Сохраняем всех активных персонажей
        print(f"{Fore.YELLOW}Сохранение данных персонажей...")
        self.game._auto_save_characters()

        # Останавливаем сеть
        self.network.stop()

        # Сохраняем данные базы
        self.db.save()

        if hasattr(self, 'main_thread'):
            self.main_thread.join(timeout=5)

        print(f"{Fore.GREEN}UDP сервер остановлен")

    def main_loop(self):
        """Главный цикл UDP сервера"""
        print(f"{Fore.CYAN}Главный UDP цикл запущен")

        tick_counter = 0
        while self.running:
            try:
                loop_start = time.time()
                tick_counter += 1

                # Логируем каждый 10й тик
                if tick_counter % 10 == 0:
                    print(f"[UDP TICK {tick_counter}] Статус: running={self.running}")

                # 1. Обрабатываем входящие сообщения
                messages = self.network.get_messages()
                if messages:
                    print(f"[UDP TICK {tick_counter}] Сообщений: {len(messages)}")

                self.process_messages(messages)

                # 2. Обновляем мир
                world_updates = self.game.update_world()
                if world_updates:
                    if isinstance(world_updates, list):
                        for update in world_updates:
                            if update and 'data' in update:
                                self.handle_broadcast(update['data'])
                    elif world_updates and 'data' in world_updates:
                        self.handle_broadcast(world_updates['data'])

                # 3. Обновляем статистику
                self.stats['ticks_processed'] += 1

                # 4. Получаем статистику сети
                network_stats = self.network.get_stats()
                if network_stats:
                    self.stats['udp_packets_received'] = network_stats.get('packets_received', 0)
                    self.stats['udp_packets_sent'] = network_stats.get('packets_sent', 0)

                # 5. Выдерживаем тикрейт
                loop_time = time.time() - loop_start
                sleep_time = max(0, self.tick_interval - loop_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    print(f"[UDP TICK {tick_counter}] ⚠️ Задержка! Loop: {loop_time:.3f}s")

            except Exception as e:
                print(f"{Fore.RED}Ошибка в главном UDP цикле: {e}")
                import traceback
                traceback.print_exc()

    def process_messages(self, messages):
        """Обработка входящих UDP сообщений"""
        for message in messages:
            try:
                self.stats['messages_processed'] += 1

                msg_type = message.get('type')
                client_id = message.get('client_id')

                # Системные сообщения
                if msg_type == 'client_connected':
                    print(f"{Fore.GREEN}UDP Клиент подключен: ID={client_id}")
                    self.stats['players_connected'] += 1
                    continue

                elif msg_type == 'client_disconnected':
                    print(f"{Fore.YELLOW}UDP Клиент отключен: ID={client_id}")

                    # Удаляем игрока
                    disconnect_responses = self.game.remove_player(client_id)
                    if disconnect_responses:
                        for response in disconnect_responses:
                            self.handle_broadcast(response['data'])
                    continue

                # Игровые сообщения
                responses = self.game.handle_message(message)

                # Отправляем ответы
                if responses:
                    for response in responses:
                        if response['target'] == 'client':
                            self.network.send_to_client(
                                response['client_id'],
                                response['data']
                            )
                        elif response['target'] == 'broadcast':
                            self.handle_broadcast(response['data'], response.get('exclude_client_id'))

            except Exception as e:
                print(f"{Fore.RED}Ошибка обработки UDP сообщения: {e}")
                import traceback
                traceback.print_exc()

    def handle_broadcast(self, data, exclude_client_id=None):
        """Обработка широковещательных сообщений для UDP"""
        print(f"[UDP BROADCAST] Отправка: {data.get('type', 'unknown')}")
        self.network.broadcast(data, exclude_client_id)

    def monitor_loop(self):
        """Цикл мониторинга UDP сервера"""
        print(f"{Fore.CYAN}UDP Мониторинг запущен")

        last_print = time.time()

        while self.running:
            try:
                current_time = time.time()

                if current_time - last_print >= 10:
                    self.print_stats()
                    last_print = current_time

                time.sleep(1)

            except Exception as e:
                print(f"{Fore.RED}Ошибка в UDP мониторе: {e}")

    def print_stats(self):
        """Вывод статистики UDP сервера"""
        uptime = int(time.time() - self.stats['start_time'])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60

        players_online = self.game.get_player_count()
        connected_clients = len(self.network.clients) if hasattr(self.network, 'clients') else 0

        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f"{Fore.WHITE}Статистика UDP сервера персонажей:")
        print(f"{Fore.GREEN}Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"{Fore.GREEN}Игроков онлайн: {players_online}")
        print(f"{Fore.GREEN}Подключений: {connected_clients}")
        print(f"{Fore.GREEN}Тиков обработано: {self.stats['ticks_processed']}")
        print(f"{Fore.GREEN}Сообщений обработано: {self.stats['messages_processed']}")
        print(f"{Fore.GREEN}UDP пакетов получено: {self.stats['udp_packets_received']}")
        print(f"{Fore.GREEN}UDP пакетов отправлено: {self.stats['udp_packets_sent']}")
        print(f"{Fore.GREEN}Всего персонажей: {self.db.get_server_stats()['total_characters']}")
        print(f"{Fore.GREEN}Протокол: UDP")
        print(f"{Fore.CYAN}{'=' * 60}")

    def get_server_info(self):
        """Получение информации о UDP сервере"""
        return {
            'status': 'running' if self.running else 'stopped',
            'config': self.config['server'],
            'stats': self.stats,
            'world': self.game.get_world_state(),
            'gifct_settings': self.db.get_gifct_settings(),
            'network_stats': self.network.get_stats() if hasattr(self.network, 'get_stats') else {},
            'protocol': 'udp'
        }