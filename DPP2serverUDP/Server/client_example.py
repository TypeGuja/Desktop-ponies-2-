#!/usr/bin/env python3
"""
DPP2 UDP Test Client с поддержкой видеострима (получение screen_frame)
"""

import socket
import time
import threading
import random
import json
import base64
import cv2
import numpy as np

from DPP2serverUDP import toon


# ----------------------------------------------------------------------
#   Менеджер скинов (не менялся)
# ----------------------------------------------------------------------
class PlayerSkinManager:
    """Менеджер скинов игроков"""

    def __init__(self):
        self.skins = {}          # character_id -> skin_data
        self.players = {}        # character_id -> player_data
        self.active_effects = {}  # effect_id -> effect_data

    def update_skin(self, character_id, skin_data):
        self.skins.setdefault(character_id, {}).update(skin_data)
        return self.skins[character_id]

    def get_skin(self, character_id):
        return self.skins.get(character_id, {})

    def remove_skin(self, character_id):
        self.skins.pop(character_id, None)

    def update_player_position(self, character_id, position):
        self.players.setdefault(character_id, {})['position'] = position

    def get_player_position(self, character_id):
        return self.players.get(character_id, {}).get('position',
                                                     {'x': 0, 'y': 0, 'z': 0})

    def add_effect(self, effect_id, effect_data):
        self.active_effects[effect_id] = {
            'data': effect_data,
            'start_time': time.time(),
            'end_time': time.time() + effect_data.get('duration', 5)
        }

    def remove_expired_effects(self):
        now = time.time()
        expired = [eid for eid, d in self.active_effects.items()
                   if d['end_time'] <= now]
        for eid in expired:
            del self.active_effects[eid]
        return expired


# ----------------------------------------------------------------------
#   Тестовый UDP‑клиент
# ----------------------------------------------------------------------
class UDPTestClient:
    """Тестовый UDP‑клиент с поддержкой видеострима."""

    def __init__(self, host='127.0.0.1', port=5555, use_gui=False):
        self.host = host
        self.port = port
        self.address = (host, port)

        # UDP‑socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(2.0)

        # Состояния соединения
        self.client_id = None
        self.connected = False
        self.running = False
        self.authenticated = False
        self.in_world = False

        # Тестовые данные
        self.test_username = f"test_user_{random.randint(1000, 9999)}"
        self.character_id = None
        self.character_name = f"TestChar_{random.randint(1000, 9999)}"
        self.player_id = None

        # Позиция и текущий скин
        self.position = {'x': random.uniform(0, 100),
                         'y': random.uniform(0, 100),
                         'z': 0}
        self.rotation = 0
        self.current_skin = {
            'gif_url': f'skins/player_{random.choice(["red","blue","green","purple"])}.gif',
            'gif_name': f'player_{random.choice(["red","blue","green","purple"])}',
            'animation_speed': random.uniform(0.8, 1.2),
            'color_tint': f'#{random.randint(0,255):02x}{random.randint(0,255):02x}{random.randint(0,255):02x}',
            'scale': random.uniform(0.8, 1.2),
            'layer': 'character',
            'loop': True,
            'start_frame': 0
        }

        # Очередь входящих сообщений
        self.messages = []
        self.message_lock = threading.Lock()

        # Статистика клиента
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'connected_at': None,
            'ping': 0
        }

        # Менеджер скинов
        self.skin_manager = PlayerSkinManager()

        # Хранилище для видеокадров (screen_frame)
        self._screen_frames = {}          # frame_id -> {"chunks":{}, "total":int, "timestamp":float}
        self._screen_lock = threading.Lock()

        # GUI (по желанию)
        self.use_gui = use_gui
        self.root = None
        self.canvas = None
        self.gui_thread = None
        self.gui_ready = False

        if self.use_gui:
            self.start_gui()

    # ------------------------------------------------------------------
    #   GUI (не менялась, только вызовы функции ниже)
    # ------------------------------------------------------------------
    def start_gui(self):
        """Запуск графического интерфейса в отдельном потоке."""
        self.gui_thread = threading.Thread(target=self._gui_main, daemon=True)
        self.gui_thread.start()
        for _ in range(10):
            if self.gui_ready:
                break
            time.sleep(0.1)

    # _gui_main() – полностью прежний код (не показан ради краткости)

    # ------------------------------------------------------------------
    #   СЕТЕВОЕ ВЗАИМОДЕЙСТВИЕ
    # ------------------------------------------------------------------
    def connect(self):
        """Подключиться к серверу."""
        try:
            print(f"[CLIENT] Подключение к UDP серверу {self.host}:{self.port}...")

            init_msg = {
                'type': 'client_init',
                'timestamp': time.time(),
                'client_info': {
                    'version': '1.0',
                    'protocol': 'udp',
                    'supports_skins': True,
                    'username': self.test_username
                }
            }
            self.send(init_msg)
            self.stats['connected_at'] = time.time()

            start = time.time()
            while time.time() - start < 5:
                resp = self.receive()
                if resp and resp.get('type') == 'welcome':
                    self.client_id = resp.get('client_id')
                    self.connected = True
                    print(f"[CLIENT] ✅ Подключено! client_id = {self.client_id}")

                    if self.use_gui:
                        self.status_label.config(text="Состояние: Подключен",
                                                  fg='#ff9800')

                    if not self.running:
                        self.running = True
                        threading.Thread(target=self.receive_loop,
                                         daemon=True).start()
                    return True
                time.sleep(0.1)

            print("[CLIENT] ❌ Таймаут подключения")
            return False

        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка подключения: {e}")
            return False

    def send(self, data: dict) -> bool:
        """Отправить словарь серверу (binary → toon)."""
        try:
            packet = toon.encode(data)          # <-- бинарная сериализация
            self.socket.sendto(packet, self.address)

            self.stats['messages_sent'] += 1
            self.stats['bytes_sent'] += len(packet)
            print(f"[CLIENT] 📤 Отправлено: {data.get('type', 'unknown')}")
            return True

        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка отправки: {e}")
            return False

    def receive(self) -> dict | None:
        """Получить один пакет от сервера и десериализовать."""
        try:
            data, _ = self.socket.recvfrom(4096)
            if data:
                message = toon.decode(data)      # <-- бинарная десериализация
                with self.message_lock:
                    self.messages.append(message)

                self.stats['messages_received'] += 1
                self.stats['bytes_received'] += len(data)

                if message.get('type') == 'pong':
                    sent = message.get('ping_sent', 0)
                    if sent:
                        self.stats['ping'] = int((time.time() - sent) * 1000)

                return message

        except socket.timeout:
            pass
        except Exception as e:
            print(f"[CLIENT] ❌ Ошибка получения: {e}")
        return None

    # ------------------------------------------------------------------
    #   Высокоуровневые действия (auth, character, join, …)
    # ------------------------------------------------------------------
    def authenticate(self):
        """Аутентификация на сервере."""
        print(f"[CLIENT] 🔐 Аутентификация как {self.test_username}...")

        auth_msg = {
            'type': 'auth',
            'username': self.test_username,
            'timestamp': time.time(),
            'client_id': self.client_id
        }
        self.send(auth_msg)

        start = time.time()
        while time.time() - start < 5:
            resp = self.receive()
            if resp and resp.get('type') == 'auth_response':
                if resp.get('success'):
                    self.authenticated = True
                    self.player_id = resp.get('player_id')
                    print(f"[CLIENT] ✅ Аутентификация прошла! player_id = {self.player_id}")

                    if self.use_gui:
                        self.status_label.config(text="Состояние: Авторизован",
                                                  fg='#2196f3')
                    return True
                else:
                    print(f"[CLIENT] ❌ Ошибка аутентификации: {resp.get('message')}")
                    return False
            time.sleep(0.1)

        print("[CLIENT] ❌ Таймаут аутентификации")
        return False

    def create_character(self):
        """Создать персонажа."""
        print(f"[CLIENT] 🎮 Создание персонажа {self.character_name}...")

        char_data = {
            'id': f"test_char_{random.randint(10000, 99999)}",
            'name': self.character_name,
            'owner': self.test_username,
            'position': self.position,
            'stats': {
                'strength': random.randint(8, 15),
                'agility': random.randint(8, 15),
                'intelligence': random.randint(8, 15),
                'vitality': random.randint(8, 15),
                'luck': random.randint(1, 10)
            },
            'appearance': {
                'hair_color': f'#{random.randint(0,255):02x}{random.randint(0,255):02x}{random.randint(0,255):02x}',
                'eye_color': f'#{random.randint(0,255):02x}{random.randint(0,255):02x}{random.randint(0,255):02x}',
                'height': random.randint(160, 200),
                'body_type': random.choice(['slim', 'average', 'muscular'])
            },
            'level': 1,
            'health': 100,
            'class': random.choice(['warrior', 'mage', 'archer', 'rogue']),
            'race': random.choice(['human', 'elf', 'dwarf', 'orc'])
        }

        msg = {
            'type': 'character_select',
            'character_id': char_data['id'],
            'character_data': char_data,
            'timestamp': time.time(),
            'client_id': self.client_id
        }
        self.send(msg)

        start = time.time()
        while time.time() - start < 5:
            resp = self.receive()
            if resp and resp.get('type') == 'character_select_response':
                if resp.get('success'):
                    self.character_id = resp.get('character_id')
                    self.character_name = resp.get('character_data', {}).get(
                        'name', self.character_name)
                    print(f"[CLIENT] ✅ Персонаж создан! ID={self.character_id}")
                    return True
                else:
                    print(f"[CLIENT] ❌ Ошибка создания: {resp.get('message')}")
                    return False
            time.sleep(0.1)

        print("[CLIENT] ❌ Таймаут создания персонажа")
        return False

    def join_world(self):
        """Войти в мир."""
        print("[CLIENT] 🌍 Вход в мир...")

        join_msg = {
            'type': 'join_world',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'position': self.position,
            'timestamp': time.time(),
            'client_id': self.client_id
        }
        self.send(join_msg)

        start = time.time()
        while time.time() - start < 5:
            resp = self.receive()
            if resp:
                if resp.get('type') == 'world_joined' and resp.get('success'):
                    self.in_world = True
                    print("[CLIENT] ✅ Вышли в мир!")
                    print(f"   Мир: {resp.get('world_info', {}).get('name','')}")
                    print(f"   Онлайн: {resp.get('world_info', {}).get('online_players',0)}")

                    if self.use_gui:
                        self.status_label.config(text="Состояние: В мире",
                                                  fg='#4caf50')
                    self.send_skin_update()
                    return True
                if resp.get('type') == 'error':
                    print(f"[CLIENT] ❌ Ошибка входа: {resp.get('message')}")
                    return False
            time.sleep(0.1)

        print("[CLIENT] ❌ Таймаут входа в мир")
        return False

    # ------------------------------------------------------------------
    #   Скин‑менеджмент
    # ------------------------------------------------------------------
    def send_skin_update(self, skin_data=None):
        """Отправить текущий скин серверу."""
        if not skin_data:
            skin_data = self.current_skin

        msg = {
            'type': 'skin_update',
            'client_id': self.client_id,
            'character_id': self.character_id,
            'character_name': self.character_name,
            'skin_data': skin_data,
            'timestamp': time.time(),
            'position': self.position
        }
        return self.send(msg)

    def change_skin_color(self, color):
        """Сменить цвет скина и отправить обновление."""
        if not self.in_world:
            print("[CLIENT] ❌ Не в мире, скин менять нельзя")
            return

        new_skin = {
            'gif_url': f'skins/player_{color}.gif',
            'gif_name': f'player_{color}',
            'color_tint': self._hex_for_color(color)
        }
        self.current_skin.update(new_skin)
        self.send_skin_update(new_skin)
        print(f"[CLIENT] 🎨 Скин изменён на {color}")

    @staticmethod
    def _hex_for_color(name):
        mapping = {
            'red': '#ff4444',
            'blue': '#4444ff',
            'green': '#44ff44',
            'purple': '#aa44ff',
            'gold': '#ffaa00',
            'silver': '#cccccc'
        }
        return mapping.get(name, '#ffffff')

    # ------------------------------------------------------------------
    #   Фоновый цикл приёма
    # ------------------------------------------------------------------
    def receive_loop(self):
        """Фоновый цикл получения пакетов."""
        print("[CLIENT] 🔄 Запуск цикла приёма")
        while self.running:
            try:
                resp = self.receive()
                if resp:
                    self.process_message(resp)

                # Если в очередь «messages» попали несколько пакетов – обрабатываем их все
                with self.message_lock:
                    if self.messages:
                        for m in self.messages:
                            self.process_message(m)
                        self.messages.clear()

                # Чистим эффекты скинов
                self.skin_manager.remove_expired_effects()
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    print(f"[CLIENT] Ошибка в receive_loop: {e}")

    # ------------------------------------------------------------------
    #   Обработка входящих сообщений
    # ------------------------------------------------------------------
    def process_message(self, msg: dict):
        """Разбор сообщения от сервера."""
        typ = msg.get('type')

        if typ == 'position_update':
            self._handle_position_update(msg)
        elif typ == 'chat_message':
            self._handle_chat_message(msg)
        elif typ == 'player_joined':
            self._handle_player_joined(msg)
        elif typ == 'player_left':
            self._handle_player_left(msg)
        elif typ == 'skin_update':
            self._handle_skin_update(msg)
        elif typ == 'player_skin_info':
            self._handle_player_skin_info(msg)
        elif typ == 'effect_spawn':
            self._handle_effect_spawn(msg)
        elif typ == 'world_update':
            self._handle_world_update(msg)
        elif typ == 'error':
            print(f"[CLIENT] ❌ Ошибка сервера: {msg.get('message')}")
        elif typ == 'screen_frame':
            self._handle_screen_frame(msg)
        # типы pong/heartbeat_response уже обработаны в receive()
        else:
            print(f"[CLIENT] 📥 Получено: {typ}")

    def _handle_position_update(self, msg):
        cid = msg.get('character_id')
        if cid and cid != self.character_id:
            pos = msg.get('position', {})
            self.skin_manager.update_player_position(cid, pos)
            if cid not in self.skin_manager.players:
                self.skin_manager.players[cid] = {}
            self.skin_manager.players[cid]['name'] = msg.get('character_name')

    def _handle_chat_message(self, msg):
        name = msg.get('character_name')
        text = msg.get('text', '')
        chan = msg.get('channel', 'global')
        print(f"[CLIENT] 💬 {chan.upper()} | {name}: {text}")

    def _handle_player_joined(self, msg):
        cid = msg.get('character_id')
        name = msg.get('character_name')
        pos = msg.get('position', {})
        print(f"[CLIENT] 👤 {name} присоединился к миру")
        self.skin_manager.update_player_position(cid, pos)
        self.skin_manager.players[cid] = {'name': name, 'position': pos}
        self.request_player_skin(cid)

    def _handle_player_left(self, msg):
        cid = msg.get('character_id')
        name = msg.get('character_name')
        print(f"[CLIENT] 👋 {name} покинул мир")
        self.skin_manager.remove_skin(cid)
        self.skin_manager.players.pop(cid, None)

    def _handle_skin_update(self, msg):
        cid = msg.get('character_id')
        if cid and cid != self.character_id:
            skin = msg.get('skin_data', {})
            self.skin_manager.update_skin(cid, skin)
            print(f"[CLIENT] 🎨 Обновлён скин игрока {msg.get('character_name')}")

    def _handle_player_skin_info(self, msg):
        cid = msg.get('character_id')
        skin = msg.get('skin_data', {})
        self.skin_manager.update_skin(cid, skin)
        print(f"[CLIENT] 🎨 Получен скин игрока {msg.get('character_name')}")

    def _handle_effect_spawn(self, msg):
        data = msg.get('effect_data', {})
        char_name = msg.get('character_name')
        eff_type = data.get('gifct_name', 'unknown')
        eff_id = f"{data.get('character_id','unk')}_{int(time.time()*1000)}"
        self.skin_manager.add_effect(eff_id, data)
        print(f"[CLIENT] ✨ {char_name} использует {eff_type}")

    def _handle_world_update(self, msg):
        upd = msg.get('update_type')
        if upd == 'time':
            print(f"[CLIENT] 🕐 Время в мире: {msg.get('time')}")
        elif upd == 'weather':
            print(f"[CLIENT] 🌤️ Погода изменена: {msg.get('weather')}")

    def request_player_skin(self, character_id):
        """Запросить у сервера скин указанного персонажа."""
        req = {
            'type': 'request_skin',
            'client_id': self.client_id,
            'target_character_id': character_id,
            'timestamp': time.time()
        }
        self.send(req)

    # ------------------------------------------------------------------
    #   ОБРАБОТКА КАДРОВ ЭКРАНА (screen_frame)
    # ------------------------------------------------------------------
    def _handle_screen_frame(self, msg: dict):
        """
        Сборка кадра из кусочков, декодирование JPEG и вывод
        через OpenCV (открывается окно «Server screen»).
        """
        frame_id = msg.get('frame_id')
        idx      = msg.get('chunk_index')
        total    = msg.get('total_chunks')
        chunk    = msg.get('data')

        if None in (frame_id, idx, total, chunk):
            return

        with self._screen_lock:
            info = self._screen_frames.setdefault(frame_id, {
                'chunks': {},
                'total': total,
                'timestamp': time.time()
            })
            info['chunks'][idx] = chunk

            # Если получены все части – собираем и показываем
            if len(info['chunks']) == info['total']:
                full_b64 = ''.join(info['chunks'][i] for i in range(info['total']))
                try:
                    jpeg_bytes = base64.b64decode(full_b64)
                    np_arr = np.frombuffer(jpeg_bytes, np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        cv2.imshow('Server screen', frame)
                        cv2.waitKey(1)    # заставляем окно обновиться
                except Exception as exc:
                    print(f"[CLIENT] Ошибка отображения кадра: {exc}")

                # Очистка буфера
                del self._screen_frames[frame_id]

    # ------------------------------------------------------------------
    #   Действия игрока (движение, чат, ping, gifct)
    # ------------------------------------------------------------------
    def move_randomly(self):
        if not self.in_world:
            return
        self.position['x'] += random.uniform(-2, 2)
        self.position['y'] += random.uniform(-2, 2)
        self.rotation = random.uniform(-1, 1)

        msg = {
            'type': 'position_update',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'position': self.position,
            'rotation': self.rotation,
            'timestamp': time.time(),
            'client_id': self.client_id
        }
        self.send(msg)
        print(f"[CLIENT] 🚶 Движение: x={self.position['x']:.2f}, y={self.position['y']:.2f}")

    def send_chat(self, text):
        if not self.in_world:
            return
        msg = {
            'type': 'chat_message',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'text': text,
            'timestamp': time.time(),
            'client_id': self.client_id,
            'channel': 'global'
        }
        self.send(msg)
        print(f"[CLIENT] 💬 Чат: {text}")

    def heartbeat(self):
        if not self.connected:
            return
        hb = {
            'type': 'heartbeat',
            'timestamp': time.time(),
            'ping_sent': time.time(),
            'client_id': self.client_id
        }
        self.send(hb)

    def activate_gifct(self, gifct_id='fireball'):
        """Активировать способность (gifct)."""
        if not self.in_world:
            return
        effect = {
            'gifct_id': gifct_id,
            'gifct_name': gifct_id,
            'gif_url': f'effects/{gifct_id}.gif',
            'position': self.position.copy(),
            'duration': random.uniform(2, 5),
            'scale': random.uniform(0.5, 2.0)
        }
        msg = {
            'type': 'gifct_activation',
            'character_id': self.character_id,
            'character_name': self.character_name,
            'gifct_id': gifct_id,
            'gifct_data': effect,
            'timestamp': time.time(),
            'client_id': self.client_id
        }
        self.send(msg)
        print(f"[CLIENT] ✨ Активирован {gifct_id}")

    # ------------------------------------------------------------------
    #   Тестовые сценарии
    # ------------------------------------------------------------------
    def test_scenario(self):
        """Полный автоматический сценарий клиента."""
        print("\n" + "="*50)
        print("🚀 Запуск тестового сценария")
        print("="*50 + "\n")

        if not self.connect():          return False
        if not self.authenticate():    return False
        if not self.create_character():return False
        if not self.join_world():      return False

        print("\n" + "="*50)
        print("✅ Сценарий завершён")
        print(f"👤 {self.character_name}, скин {self.current_skin['gif_name']}")
        print("="*50 + "\n")

        if not self.use_gui:
            try:
                for i in range(30):
                    if not self.running: break
                    print(f"\n[ЦИКЛ {i+1}/30]")
                    self.move_randomly()
                    if i % 5 == 0: self.heartbeat()
                    if i % 3 == 0: self.send_chat(f"Тестовое сообщение {i+1}")
                    if i % 10 == 0 and i:
                        self.change_skin_color(random.choice(
                            ['red','blue','green','purple','gold']))
                    if i % 7 == 0 and i:
                        self.activate_gifct(random.choice(
                            ['fireball','heal','shield','lightning','ice']))
                    time.sleep(2)
            except KeyboardInterrupt:
                print("\n[CLIENT] Прервано пользователем")
            finally:
                self.cleanup()
        return True

    def simple_test(self):
        """Самый короткий ping‑test."""
        print("[CLIENT] Простой ping‑test")
        if not self.connect():
            return False
        ping = {
            'type': 'ping',
            'timestamp': time.time(),
            'ping_sent': time.time(),
            'client_id': self.client_id
        }
        self.send(ping)

        for _ in range(3):
            resp = self.receive()
            if resp and resp.get('type') == 'pong':
                print("[CLIENT] ✅ Ping‑Pong OK")
                self.cleanup()
                return True
            time.sleep(0.5)

        print("[CLIENT] ❌ Нет ответа на ping")
        self.cleanup()
        return False

    def cleanup(self):
        """Корректно завершить работу клиента."""
        self.running = False

        if self.in_world:
            self.send({
                'type': 'leave_world',
                'character_id': self.character_id,
                'character_name': self.character_name,
                'timestamp': time.time(),
                'client_id': self.client_id
            })

        if self.connected:
            self.send({
                'type': 'client_disconnect',
                'timestamp': time.time(),
                'client_id': self.client_id
            })

        try:
            self.socket.close()
        except Exception:
            pass

        # Закрываем окно видеострима, если открыто
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

        print("[CLIENT] 📡 Отключено")

    # ------------------------------------------------------------------
    #   Интерактивный режим (не менялся)
    # ------------------------------------------------------------------
    def run_interactive(self):
        """Текстовый интерактивный режим."""
        print("DPP2 UDP Test Client – интерактивный режим")
        while True:
            print("\nКоманды:")
            print(" 1 – connect")
            print(" 2 – auth")
            print(" 3 – create character")
            print(" 4 – join world")
            print(" 5 – move")
            print(" 6 – chat")
            print(" 7 – change skin")
            print(" 8 – activate gifct")
            print(" 9 – stats")
            print(" 0 – exit")
            cmd = input("Выбор: ")

            if cmd == '1':
                self.connect()
            elif cmd == '2':
                self.authenticate()
            elif cmd == '3':
                self.create_character()
            elif cmd == '4':
                self.join_world()
            elif cmd == '5':
                self.move_randomly()
            elif cmd == '6':
                txt = input("Сообщение: ")
                self.send_chat(txt)
            elif cmd == '7':
                colors = ['red','blue','green','purple','gold','silver']
                for i,c in enumerate(colors,1):
                    print(f" {i} – {c}")
                c = input("Цвет: ")
                try:
                    self.change_skin_color(colors[int(c)-1])
                except Exception:
                    print("Неверный ввод")
            elif cmd == '8':
                abilities = ['fireball','heal','shield','lightning','ice']
                for i,a in enumerate(abilities,1):
                    print(f" {i} – {a}")
                a = input("Способность: ")
                try:
                    self.activate_gifct(abilities[int(a)-1])
                except Exception:
                    print("Неверный ввод")
            elif cmd == '9':
                print(f"Отправлено: {self.stats['messages_sent']}")
                print(f"Получено:   {self.stats['messages_received']}")
                print(f"Ping:       {self.stats['ping']} ms")
                print(f"Подключено: {self.connected}")
                print(f"Авторизовано:{self.authenticated}")
                print(f"В мире:    {self.in_world}")
                print(f"Скинов у прочих: {len(self.skin_manager.skins)}")
            elif cmd == '0':
                self.cleanup()
                break
            else:
                print("Неправильная команда")


def main():
    """Точка входа клиента."""
    import argparse

    parser = argparse.ArgumentParser(
        description='DPP2 UDP Test Client с поддержкой видеострима')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5555)
    parser.add_argument('--simple', action='store_true')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--interactive', action='store_true')
    parser.add_argument('--username')
    args = parser.parse_args()

    print(f"DPP2 UDP Test Client → {args.host}:{args.port}")
    client = UDPTestClient(args.host, args.port, use_gui=args.gui)

    if args.username:
        client.test_username = args.username

    if args.simple:
        success = client.simple_test()
    elif args.interactive:
        client.run_interactive()
        success = True
    elif args.gui:
        success = True
        if client.gui_thread:
            client.gui_thread.join()
    else:
        success = client.test_scenario()

    if success:
        print("\n✅ Клиент завершил работу успешно")
        return 0
    else:
        print("\n❌ Клиент закончил работу с ошибками")
        return 1


if __name__ == "__main__":
    import sys
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
        sys.exit(0)