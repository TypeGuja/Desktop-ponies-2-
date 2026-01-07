import time
import threading
import json
from colorama import init, Fore, Style

init(autoreset=True)


class ServerCore:
    """Ядро UDP сервера"""

    def __init__(self, config_file='config.json'):
        self.config = self.load_config(config_file)

        from database import Database
        from network import UDPServer
        from game_logic import GameLogic

        self.db = Database()
        self.network = UDPServer(
            host=self.config['server']['host'],
            port=self.config['server']['port'],
            max_clients=self.config['server']['max_players']
        )
        self.game = GameLogic(self.db)

        self.running = False
        self.tick_interval = 1.0 / self.config['server']['tick_rate']

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
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Ошибка загрузки конфигурации: {e}")
            return self._default_config()

    def _default_config(self):
        """Конфигурация по умолчанию"""
        return {
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
        self._start_worker_threads()

        print(f"{Fore.GREEN}UDP сервер запущен на {self.config['server']['host']}:{self.config['server']['port']}")
        print(f"{Fore.CYAN}Нажмите Ctrl+C для остановки")
        return True

    def _start_worker_threads(self):
        """Запуск рабочих потоков"""
        self.main_thread = threading.Thread(target=self.main_loop, daemon=True, name="MainLoop")
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True, name="Monitor")

        self.main_thread.start()
        self.monitor_thread.start()

    def stop(self):
        """Остановка сервера"""
        print(f"{Fore.YELLOW}Остановка UDP сервера...")
        self.running = False

        self._shutdown_sequence()

        print(f"{Fore.GREEN}UDP сервер остановлен")

    def _shutdown_sequence(self):
        """Последовательность завершения работы"""
        print(f"{Fore.YELLOW}Сохранение данных персонажей...")
        self.game._auto_save_characters()

        self.network.stop()
        self.db.save()

        if hasattr(self, 'main_thread'):
            self.main_thread.join(timeout=5)

    def main_loop(self):
        """Главный цикл UDP сервера"""
        print(f"{Fore.CYAN}Главный UDP цикл запущен")

        tick_counter = 0
        while self.running:
            try:
                loop_start = time.time()
                tick_counter += 1

                self._process_tick(tick_counter)
                self._maintain_tick_rate(loop_start)

            except Exception as e:
                print(f"{Fore.RED}Ошибка в главном UDP цикле: {e}")
                import traceback
                traceback.print_exc()

    def _process_tick(self, tick_counter):
        """Обработка одного тика"""
        # Логирование
        if tick_counter % 10 == 0:
            print(f"[UDP TICK {tick_counter}] Статус: running={self.running}")

        # Обработка сообщений
        messages = self.network.get_messages()
        if messages:
            print(f"[UDP TICK {tick_counter}] Сообщений: {len(messages)}")
            self.process_messages(messages)

        # Обновление мира
        world_updates = self.game.update_world()
        if world_updates:
            self._handle_world_updates(world_updates)

        # Обновление статистики
        self.stats['ticks_processed'] += 1
        self._update_network_stats()

    def _handle_world_updates(self, updates):
        """Обработка обновлений мира"""
        if isinstance(updates, list):
            for update in updates:
                if update and 'data' in update:
                    self.handle_broadcast(update['data'])
        elif updates and 'data' in updates:
            self.handle_broadcast(updates['data'])

    def _update_network_stats(self):
        """Обновление сетевой статистики"""
        network_stats = self.network.get_stats()
        if network_stats:
            self.stats['udp_packets_received'] = network_stats.get('packets_received', 0)
            self.stats['udp_packets_sent'] = network_stats.get('packets_sent', 0)

    def _maintain_tick_rate(self, loop_start):
        """Поддержание заданного тикрейта"""
        loop_time = time.time() - loop_start
        sleep_time = max(0, self.tick_interval - loop_time)

        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            print(f"[UDP TICK] ⚠️ Задержка! Loop: {loop_time:.3f}s")

    def process_messages(self, messages):
        """Обработка входящих UDP сообщений"""
        for message in messages:
            try:
                self.stats['messages_processed'] += 1
                self._process_single_message(message)
            except Exception as e:
                print(f"{Fore.RED}Ошибка обработки UDP сообщения: {e}")
                import traceback
                traceback.print_exc()

    def _process_single_message(self, message):
        """Обработка одного сообщения"""
        msg_type = message.get('type')
        client_id = message.get('client_id')

        if msg_type == 'client_connected':
            print(f"{Fore.GREEN}UDP Клиент подключен: ID={client_id}")
            self.stats['players_connected'] += 1
            return

        elif msg_type == 'client_disconnected':
            print(f"{Fore.YELLOW}UDP Клиент отключен: ID={client_id}")
            self._handle_client_disconnect(client_id)
            return

        # Обработка игровых сообщений
        responses = self.game.handle_message(message)
        if responses:
            self._send_responses(responses)

    def _handle_client_disconnect(self, client_id):
        """Обработка отключения клиента"""
        disconnect_responses = self.game.remove_player(client_id)
        if disconnect_responses:
            for response in disconnect_responses:
                self.handle_broadcast(response['data'])

    def _send_responses(self, responses):
        """Отправка ответов"""
        for response in responses:
            if response['target'] == 'client':
                self.network.send_to_client(
                    response['client_id'],
                    response['data']
                )
            elif response['target'] == 'broadcast':
                self.handle_broadcast(response['data'], response.get('exclude_client_id'))

    def handle_broadcast(self, data, exclude_client_id=None):
        """Обработка широковещательных сообщений"""
        print(f"[UDP BROADCAST] Отправка: {data.get('type', 'unknown')}")
        self.network.broadcast(data, exclude_client_id)

    def monitor_loop(self):
        """Цикл мониторинга UDP сервера"""
        print(f"{Fore.CYAN}UDP Мониторинг запущен")

        last_print = time.time()
        while self.running:
            try:
                if time.time() - last_print >= 10:
                    self.print_stats()
                    last_print = time.time()
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

        stats_text = f"""
{Fore.CYAN}{'=' * 60}
{Fore.WHITE}Статистика UDP сервера персонажей:
{Fore.GREEN}Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}
{Fore.GREEN}Игроков онлайн: {players_online}
{Fore.GREEN}Подключений: {connected_clients}
{Fore.GREEN}Тиков обработано: {self.stats['ticks_processed']}
{Fore.GREEN}Сообщений обработано: {self.stats['messages_processed']}
{Fore.GREEN}UDP пакетов получено: {self.stats['udp_packets_received']}
{Fore.GREEN}UDP пакетов отправлено: {self.stats['udp_packets_sent']}
{Fore.GREEN}Всего персонажей: {self.db.get_server_stats()['total_characters']}
{Fore.GREEN}Протокол: UDP
{Fore.CYAN}{'=' * 60}
"""
        print(stats_text)

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