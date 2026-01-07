import time
import threading
import json
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)


class ServerCore:
    def __init__(self, config_file='config.json'):
        self.load_config(config_file)

        from database import Database
        from network import NetworkServer
        from game_logic import GameLogic

        self.db = Database()
        self.network = NetworkServer(
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
            'characters_created': 0
        }

        print(f"{Fore.GREEN}DPP2 Character Server Core initialized")

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
                    'server_name': 'DPP2 Character Server'
                }
            }

    def start(self):
        """Запуск сервера"""
        print(f"{Fore.YELLOW}Запуск сервера персонажей...")

        if not self.network.start():
            print(f"{Fore.RED}Не удалось запустить сетевой сервер")
            return False

        self.running = True

        self.main_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.main_thread.start()

        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        print(f"{Fore.GREEN}Сервер запущен на {self.config['server']['host']}:{self.config['server']['port']}")
        print(f"{Fore.CYAN}Нажмите Ctrl+C для остановки")

        return True

    def stop(self):
        """Остановка сервера"""
        print(f"{Fore.YELLOW}Остановка сервера...")

        self.running = False

        # Сохраняем всех активных персонажей
        print(f"{Fore.YELLOW}Сохранение данных персонажей...")
        self.game.auto_save_characters()

        # Останавливаем сеть
        self.network.stop()

        # Сохраняем данные базы
        self.db.save()

        if hasattr(self, 'main_thread'):
            self.main_thread.join(timeout=5)

        print(f"{Fore.GREEN}Сервер остановлен")

    def main_loop(self):
        """Главный цикл сервера"""
        print(f"{Fore.CYAN}Главный цикл запущен")

        tick_counter = 0
        while self.running:
            try:
                loop_start = time.time()
                tick_counter += 1

                # Логируем каждый 10й тик
                if tick_counter % 10 == 0:
                    print(f"[TICK {tick_counter}] Статус: running={self.running}")

                # 1. Обрабатываем входящие сообщения
                messages = self.network.get_messages()
                if messages:
                    print(f"[TICK {tick_counter}] Сообщений: {len(messages)}")

                self.process_messages(messages)

                # 2. Обновляем мир - ПРОВЕРИМ ЧТО ОН ВОЗВРАЩАЕТ
                world_update = self.game.update_world()
                if world_update:
                    print(f"[TICK {tick_counter}] World update: {world_update.get('data', {}).get('type', 'unknown')}")
                    self.handle_broadcast(world_update['data'])

                # 3. Обновляем статистику
                self.stats['ticks_processed'] += 1

                # 4. Выдерживаем тикрейт
                loop_time = time.time() - loop_start
                sleep_time = max(0, self.tick_interval - loop_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    print(
                        f"[TICK {tick_counter}] ⚠️ Задержка! Loop: {loop_time:.3f}s, Target: {self.tick_interval:.3f}s")

            except Exception as e:
                print(f"{Fore.RED}Ошибка в главном цикле: {e}")
                import traceback
                traceback.print_exc()

    # В методе process_messages измените обработку отключения:
    def process_messages(self, messages):
        """Обработка входящих сообщений"""
        for message in messages:
            try:
                self.stats['messages_processed'] += 1

                msg_type = message.get('type')
                client_id = message.get('client_id')

                # Системные сообщения
                if msg_type == 'client_connected':
                    print(f"{Fore.GREEN}Клиент подключен: ID={client_id}")
                    self.stats['players_connected'] += 1
                    continue

                elif msg_type == 'client_disconnected':
                    print(f"{Fore.YELLOW}Клиент отключен: ID={client_id}")

                    # ИСПРАВЛЕНО: handle возвращает список или None
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
                print(f"{Fore.RED}Ошибка обработки сообщения: {e}")
                import traceback
                traceback.print_exc()

    def handle_broadcast(self, data, exclude_client_id=None):
        """Обработка широковещательных сообщений"""
        print(f"[BROADCAST] Отправка: {data.get('type', 'unknown')}")
        self.network.broadcast(data, exclude_client_id)

    def monitor_loop(self):
        """Цикл мониторинга"""
        print(f"{Fore.CYAN}Мониторинг запущен")

        last_print = time.time()

        while self.running:
            try:
                current_time = time.time()

                if current_time - last_print >= 10:
                    self.print_stats()
                    last_print = current_time

                time.sleep(1)

            except Exception as e:
                print(f"{Fore.RED}Ошибка в мониторе: {e}")

    def print_stats(self):
        """Вывод статистики сервера"""
        uptime = int(time.time() - self.stats['start_time'])
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60

        players_online = self.game.get_player_count()
        connected_clients = len(self.network.clients)

        print(f"\n{Fore.CYAN}{'=' * 50}")
        print(f"{Fore.WHITE}Статистика сервера персонажей:")
        print(f"{Fore.GREEN}Время работы: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"{Fore.GREEN}Игроков онлайн: {players_online}")
        print(f"{Fore.GREEN}Подключений: {connected_clients}")
        print(f"{Fore.GREEN}Тиков обработано: {self.stats['ticks_processed']}")
        print(f"{Fore.GREEN}Сообщений обработано: {self.stats['messages_processed']}")
        print(f"{Fore.GREEN}Всего персонажей: {self.db.get_server_stats()['total_characters']}")
        print(f"{Fore.CYAN}{'=' * 50}")

    def get_server_info(self):
        """Получение информации о сервере"""
        return {
            'status': 'running' if self.running else 'stopped',
            'config': self.config['server'],
            'stats': self.stats,
            'world': self.game.get_world_state(),
            'gifct_settings': self.db.get_gifct_settings()
        }