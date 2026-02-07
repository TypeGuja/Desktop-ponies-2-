#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DPP2 UDP Server Core – полностью переписан с исправлением проблемы
повторного подключения клиентов.

*   Видеостриминг отправляется раз в N сек (по умолчанию 10 сек).
*   Добавлен throttling широковещательных сообщений (`broadcast_interval`).
*   Параметры задаются в конфиге и могут менять‑ся без перезапуска кода.
*   **Критическое исправление** – корректное удаление клиента при
    получении сообщения `client_disconnect`, что позволяет клиенту
    переподключаться без «зависания» записи в `self.clients`.
"""

import time
import json
import threading
import base64
import io
import os
import signal
from datetime import datetime
from colorama import init, Fore, Style

# ----------------------------------------------------------------------
#   Внешние зависимости (mss – захват экрана, Pillow – JPEG)
# ----------------------------------------------------------------------
import mss
from PIL import Image

init(autoreset=True)


class ServerCore:
    """Основной UDP‑сервер с видеостримом."""

    # --------------------------------------------------------------
    #   Конструктор
    # --------------------------------------------------------------
    def __init__(self, config_file='config.json'):
        self.config = self.load_config(config_file)

        # импортируем локальные модули проекта
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
        self.tick_interval = 1.0 / self.config['server'].get('tick_rate', 60)

        # статистика сервера
        self.stats = {
            'start_time': time.time(),
            'ticks_processed': 0,
            'messages_processed': 0,
            'players_connected': 0,
            'characters_created': 0,
            'udp_packets_received': 0,
            'udp_packets_sent': 0,
        }

        # видеостример (поток, флаг, буфер)
        self._screen_thread   = None
        self._screen_running = threading.Event()

        # broadcast throttling
        self._last_broadcast = 0.0
        self.broadcast_interval = self.config['server'].get('broadcast_interval', 0.05)  # сек

        print(
            f"{Fore.GREEN}DPP2 UDP ServerCore initialized "
            f"on {self.config['server']['host']}:{self.config['server']['port']}"
        )

    # --------------------------------------------------------------
    #   Конфиг
    # --------------------------------------------------------------
    def load_config(self, file_name):
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Config load error: {e}")
            return self._default_config()

    def _default_config(self):
        return {
            'server': {
                'host': '0.0.0.0',
                'port': 5555,
                'max_players': 100,
                'tick_rate': 60,
                'screen_fps': 5,                # старый параметр (не используется)
                'screen_quality': 70,
                'screen_update_interval': 10,   # сек. между кадрами
                'broadcast_interval': 0.05,    # сек. между broadcast‑пакетами
            }
        }

    # --------------------------------------------------------------
    #   Запуск / остановка
    # --------------------------------------------------------------
    def start(self):
        print(f"{Fore.YELLOW}Запуск UDP‑сервера...")
        if not self.network.start():
            print(f"{Fore.RED}Не удалось запустить UDP‑сервер")
            return False

        # стартуем видеострим (если включён)
        self._start_screen_streamer()
        self.running = True
        self._start_worker_threads()

        print(
            f"{Fore.GREEN}UDP‑сервер запущен на "
            f"{self.config['server']['host']}:{self.config['server']['port']}"
        )
        print(f"{Fore.CYAN}Ctrl+C – остановка")
        return True

    def _start_worker_threads(self):
        self.main_thread = threading.Thread(
            target=self.main_loop, daemon=True, name="MainLoop"
        )
        self.monitor_thread = threading.Thread(
            target=self.monitor_loop, daemon=True, name="Monitor"
        )
        self.main_thread.start()
        self.monitor_thread.start()

    def stop(self):
        print(f"{Fore.YELLOW}Остановка UDP‑сервера...")
        self.running = False
        self._shutdown_sequence()
        print(f"{Fore.GREEN}UDP‑сервер остановлен")

    def _shutdown_sequence(self):
        # 1️⃣ остановка видеострима
        if self._screen_running.is_set():
            self._screen_running.clear()
            if self._screen_thread:
                self._screen_thread.join(timeout=2)
                print("[SERVER] ScreenStreamer stopped")

        # 2️⃣ автосохранение персонажей
        print(f"{Fore.YELLOW}Saving characters …")
        self.game._auto_save_characters()

        # 3️⃣ остановка сети + сохранение БД
        self.network.stop()
        self.db.save()

        # 4️⃣ ждём завершения основных потоков
        if hasattr(self, 'main_thread'):
            self.main_thread.join(timeout=5)

    # --------------------------------------------------------------
    #   Основной цикл
    # --------------------------------------------------------------
    def main_loop(self):
        print(f"{Fore.CYAN}Главный цикл запущен")
        counter = 0
        while self.running:
            try:
                start = time.time()
                counter += 1
                self._process_tick(counter)
                self._maintain_tick_rate(start)
            except Exception as e:
                print(f"{Fore.RED}Loop error: {e}")
                import traceback
                traceback.print_exc()

    def _process_tick(self, tick_counter):
        # логируем раз в 10 тиков
        if tick_counter % 10 == 0:
            print(f"[TICK {tick_counter}] running={self.running}")

        # ------------------------------------------------------
        #   Приём входящих UDP‑сообщений
        # ------------------------------------------------------
        msgs = self.network.get_messages()
        if msgs:
            print(f"[TICK {tick_counter}] recv {len(msgs)} msgs")
            self.process_messages(msgs)

        # ------------------------------------------------------
        #   Обновление игрового мира
        # ------------------------------------------------------
        updates = self.game.update_world()
        if updates:
            self._handle_world_updates(updates)

        # ------------------------------------------------------
        #   Статистика
        # ------------------------------------------------------
        self.stats['ticks_processed'] += 1
        self._update_network_stats()

    def _handle_world_updates(self, updates):
        """Рассылаем обновления мира (broadcast) с ограничением."""
        if isinstance(updates, list):
            for upd in updates:
                if upd and 'data' in upd:
                    self._broadcast_throttled(upd['data'])
        elif updates and 'data' in updates:
            self._broadcast_throttled(updates['data'])

    def _broadcast_throttled(self, data):
        now = time.time()
        if now - self._last_broadcast < self.broadcast_interval:
            # пропускаем, т.к. уже отправляли слишком недавно
            return
        self._last_broadcast = now
        self.network.broadcast(data)

    def _update_network_stats(self):
        net = self.network.get_stats()
        if net:
            self.stats['udp_packets_received'] = net.get('packets_received', 0)
            self.stats['udp_packets_sent'] = net.get('packets_sent', 0)

    def _maintain_tick_rate(self, loop_start):
        elapsed = time.time() - loop_start
        sleep = max(0.0, self.tick_interval - elapsed)
        if sleep > 0:
            time.sleep(sleep)
        else:
            print(f"[WARN] Tick lag: {elapsed:.3f}s")

    # --------------------------------------------------------------
    #   Обработка пакетов от клиентов
    # --------------------------------------------------------------
    def process_messages(self, messages):
        for msg in messages:
            try:
                self.stats['messages_processed'] += 1
                self._process_single_message(msg)
            except Exception as e:
                print(f"{Fore.RED}Message error: {e}")
                import traceback
                traceback.print_exc()

    def _process_single_message(self, msg):
        """Обрабатывает одно входящее сообщение."""
        typ = msg.get('type')
        client_id = msg.get('client_id')

        # --------------------------------------------------
        #   Обработка системных запросов
        # --------------------------------------------------
        if typ == 'client_connected':
            print(f"{Fore.GREEN}Client connected: {client_id}")
            self.stats['players_connected'] += 1
            return

        if typ == 'client_disconnected':
            print(f"{Fore.YELLOW}Client disconnected: {client_id}")
            self._handle_client_disconnect(client_id)
            return

        # --------------------------------------------------
        #   **НОВОЕ**: запрос от клиента на отключение
        # --------------------------------------------------
        if typ == 'client_disconnect':
            # Клиент явно запросил отключение – удаляем его из
            # сетевого списка, а дальше обработка произойдёт
            # через обычный сценарий `client_disconnected`,
            # который уже вызывается после удаления.
            print(f"{Fore.YELLOW}Client requested disconnect: {client_id}")
            if client_id is not None:
                self.network.remove_client_by_id(client_id)
            else:
                # Если client_id не передан, будем пытаться удалить
                # по адресу (можно добавить логику, но в текущем протоколе
                # client_id всегда присутствует).
                pass
            # Не вызываем _handle_client_disconnect сразу – дождёмся
            # сообщения `client_disconnected`, которое будет добавлено
            # в очередь network'ом.
            return

        # --------------------------------------------------
        #   Передаём игровую часть логике
        # --------------------------------------------------
        responses = self.game.handle_message(msg)
        if responses:
            self._send_responses(responses)

    def _handle_client_disconnect(self, client_id):
        """Обрабатывает удаление игрока из игрового мира."""
        resp = self.game.remove_player(client_id)
        if resp:
            for r in resp:
                self.handle_broadcast(r['data'],
                                      r.get('exclude_client_id'))

    def _send_responses(self, responses):
        for resp in responses:
            if resp['target'] == 'client':
                self.network.send_to_client(
                    resp['client_id'], resp['data']
                )
            elif resp['target'] == 'broadcast':
                self.handle_broadcast(
                    resp['data'], resp.get('exclude_client_id')
                )

    def handle_broadcast(self, data, exclude_client_id=None):
        print(f"[BROADCAST] {data.get('type', 'unknown')}")
        self.network.broadcast(data, exclude_client_id)

    # --------------------------------------------------------------
    #   Мониторинг (вывод статистики каждые 10 сек)
    # --------------------------------------------------------------
    def monitor_loop(self):
        print(f"{Fore.CYAN}Monitor started")
        last = time.time()
        while self.running:
            try:
                if time.time() - last >= 10:
                    self.print_stats()
                    last = time.time()
                time.sleep(1)
            except Exception as e:
                print(f"{Fore.RED}Monitor error: {e}")

    def print_stats(self):
        uptime = int(time.time() - self.stats['start_time'])
        h, m = divmod(uptime, 3600)
        m, s = divmod(m, 60)

        players = self.game.get_player_count()
        conns = len(self.network.clients) if hasattr(self.network, 'clients') else 0

        txt = f"""
{Fore.CYAN}{'='*60}
{Fore.WHITE}UDP Server stats:
{Fore.GREEN}Uptime          : {h:02d}:{m:02d}:{s:02d}
{Fore.GREEN}Players online  : {players}
{Fore.GREEN}Connections     : {conns}
{Fore.GREEN}Ticks processed : {self.stats['ticks_processed']}
{Fore.GREEN}Messages proc.  : {self.stats['messages_processed']}
{Fore.GREEN}UDP recv        : {self.stats['udp_packets_received']}
{Fore.GREEN}UDP sent        : {self.stats['udp_packets_sent']}
{Fore.GREEN}Total chars    : {self.db.get_server_stats()['total_characters']}
{Fore.CYAN}{'='*60}
"""
        print(txt)

    # --------------------------------------------------------------
    #   Видеострим (с интервалом screen_update_interval)
    # --------------------------------------------------------------
    def _start_screen_streamer(self):
        cfg_srv = self.config['server']
        interval = cfg_srv.get('screen_update_interval', 10)   # сек
        quality = cfg_srv.get('screen_quality', 70)

        if interval <= 0:
            interval = 10
            print("[SERVER] screen_update_interval <=0 → использовано 10 сек")
        self._screen_running.set()

        def stream_loop():
            with mss.mss() as sct:
                monitor_cfg = sct.monitors[1]  # главный монитор
                max_packet = self.network.max_packet_size - 200
                frame_id = 0

                while self._screen_running.is_set():
                    start = time.time()

                    # 1️⃣ захват и кодировка в JPEG
                    img_raw = sct.grab(monitor_cfg)
                    img = Image.frombytes(
                        'RGB', (img_raw.width, img_raw.height), img_raw.rgb
                    )

                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=quality)
                    jpeg = buf.getvalue()

                    # 2️⃣ optional zlib‑компрессия (закомментировано)
                    # import zlib
                    # jpeg = zlib.compress(jpeg)

                    # 3️⃣ base64 + разбивка на чанки
                    b64 = base64.b64encode(jpeg).decode('ascii')
                    chunk_sz = max_packet
                    total_chunks = (len(b64) + chunk_sz - 1) // chunk_sz

                    for idx in range(total_chunks):
                        pkt = {
                            'type': 'screen_frame',
                            'frame_id': frame_id,
                            'chunk_index': idx,
                            'total_chunks': total_chunks,
                            'data': b64[idx * chunk_sz:(idx + 1) * chunk_sz],
                        }
                        self.network.broadcast(pkt)

                    frame_id = (frame_id + 1) % (2 ** 31)

                    # 4️⃣ ожидание следующего интервала
                    elapsed = time.time() - start
                    if elapsed < interval:
                        time.sleep(interval - elapsed)

        self._screen_thread = threading.Thread(
            target=stream_loop, daemon=True, name="ScreenStreamer"
        )
        self._screen_thread.start()
        print(
            f"[SERVER] ScreenStreamer started (interval={interval}s, quality={quality})"
        )
