#!/usr/bin/env python3
"""
Network client – простая UDP‑реализация, использующая бинарный протокол «toon».
"""

import socket
import time
from datetime import datetime

# ----------------------------------------------------------------------
#   Локальный бинарный протокол «toon» (MessagePack → pickle‑fallback)
# ----------------------------------------------------------------------
from DPP2serverUDP import toon             # <-- новый импорт


class NetworkClient:
    """Клиент UDP‑соединения, использующий протокол toon."""

    def __init__(self, host: str = "147.185.221.27", port: int = 22153):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.connected = False
        self.client_id: str | None = None

        # Параметры надёжности (имитация)
        self.packet_counter = 0
        self.last_packet_time = 0.0
        self.packet_timeout = 2.0
        self.max_packet_size = 1400

    # ------------------------------------------------------------------
    #   Подключение
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        """Инициализировать UDP‑сокет."""
        try:
            print(f"🔄 Подключение к {self.host}:{self.port} через UDP…")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(1.0)

            self.server_address = (self.host, self.port)
            self.connected = True

            print(f"✅ UDP клиент инициализирован (client_id: {self.client_id})")
            return True
        except socket.timeout:
            print("❌ Таймаут подключения")
            return False
        except Exception as exc:               # pragma: no cover
            print(f"❌ Ошибка инициализации UDP: {exc}")
            return False

    def is_connected(self) -> bool:
        """Проверить состояние соединения."""
        return self.connected and self.socket is not None

    # ------------------------------------------------------------------
    #   Отправка данных (binary → toon)
    # ------------------------------------------------------------------
    def send(self, data: dict) -> bool:
        """Отправить сообщение через UDP, сериализуя его в «toon»."""
        if not self.is_connected() or not self.socket:
            print("⚠️ Нет подключения")
            return False

        try:
            # Автоматически добавляем общие поля
            if self.client_id and "client_id" not in data:
                data["client_id"] = self.client_id
            self.packet_counter += 1
            data["packet_id"] = self.packet_counter
            data["timestamp"] = datetime.now().isoformat()

            payload = toon.encode(data)          # <-- бинарная сериализация

            if len(payload) > self.max_packet_size:
                print(f"⚠️ Пакет слишком большой ({len(payload)} байт) – урезаем")
                # Обрезать нельзя (бинарный), поэтому просто отбрасываем избыточные данные
                payload = payload[: self.max_packet_size]

            self.socket.sendto(payload, self.server_address)
            self.last_packet_time = time.time()

            typ = data.get("type", "unknown")
            print(f"📤 UDP отправлено: {typ[:20]}… (id: {self.packet_counter})")
            return True
        except socket.error as exc:
            print(f"❌ Ошибка отправки UDP: {exc}")
            return False
        except Exception as exc:               # pragma: no cover
            print(f"❌ Ошибка отправки: {exc}")
            return False

    def safe_send(self, data: dict) -> bool:
        """Отправка с несколькими попытками."""
        for attempt in range(3):
            try:
                if self.send(data):
                    return True
                print(f"⚠️ Попытка {attempt + 1} не удалась")
                time.sleep(0.1)
            except Exception as exc:           # pragma: no cover
                print(f"⚠️ Попытка {attempt + 1} вызвала ошибку: {exc}")
                time.sleep(0.1)

        print("❌ Все попытки отправки не удались")
        return False

    # ------------------------------------------------------------------
    #   Приём данных (binary → toon)
    # ------------------------------------------------------------------
    def receive(self) -> dict | None:
        """Получить и десериализовать сообщение из UDP."""
        if not self.is_connected() or not self.socket:
            return None

        try:
            data, addr = self.socket.recvfrom(4096)
            if addr != self.server_address:
                print(f"⚠️ Пакет от неизвестного адреса: {addr}")
                return None

            if not data:
                return None

            try:
                parsed = toon.decode(data)        # <-- бинарная десериализация
                if isinstance(parsed, dict):
                    typ = parsed.get("type", "unknown")
                    print(f"📥 UDP получено: {typ[:20]}…")
                    return parsed
                else:
                    print(f"⚠️ Декодировано не словарём: {type(parsed)}")
                    return None
            except Exception as exc:
                print(f"⚠️ Ошибка декодирования toon‑сообщения: {exc}")
                return None

        except socket.timeout:
            return None
        except socket.error as exc:               # pragma: no cover
            print(f"❌ Ошибка приёма UDP: {exc}")
            return None
        except Exception as exc:                  # pragma: no cover
            print(f"❌ Ошибка приёма: {exc}")
            return None

    # ------------------------------------------------------------------
    #   Heartbeat / ping
    # ------------------------------------------------------------------
    def send_heartbeat(self) -> bool:
        """Отправить heartbeat‑сообщение для поддержания соединения."""
        if not self.is_connected():
            return False

        hb = {
            "type": "heartbeat",
            "client_id": self.client_id,
            "timestamp": datetime.now().isoformat(),
            "packet_id": self.packet_counter + 1,
        }
        return self.send(hb)

    def test_connection(self) -> bool:
        """Отправить тестовый ping‑сообщение."""
        if not self.is_connected():
            return False

        ping = {
            "type": "ping",
            "client_id": self.client_id,
            "message": "ping",
            "timestamp": datetime.now().isoformat(),
        }
        print("🔍 Отправка UDP ping…")
        return self.send(ping)

    # ------------------------------------------------------------------
    #   Отключение
    # ------------------------------------------------------------------
    def disconnect(self) -> None:
        """Корректно закрыть UDP‑соединение."""
        if self.socket:
            try:
                if self.connected:
                    exit_msg = {
                        "type": "client_disconnect",
                        "client_id": self.client_id,
                        "timestamp": datetime.now().isoformat(),
                        "packet_id": self.packet_counter + 1,
                    }
                    self.send(exit_msg)
                    time.sleep(0.1)
            finally:
                self.socket.close()
        self.connected = False
        self.socket = None
        print("📡 UDP отключено")