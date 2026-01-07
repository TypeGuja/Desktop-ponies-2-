"""
Протокол обмена сообщениями между клиентом и сервером
"""

import json
from typing import Any, Dict
from dataclasses import dataclass, asdict
from enum import Enum


class MessageType(Enum):
    """Типы сообщений"""
    # Подключение
    CONNECT = "connect"
    WELCOME = "welcome"
    DISCONNECT = "disconnect"

    # Игровые события
    MOVEMENT = "movement"
    ACTION = "action"
    EMOTE = "emote"

    # Состояние мира
    WORLD_UPDATE = "world_update"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    PLAYER_MOVED = "player_moved"

    # Чат
    CHAT = "chat"

    # Системные
    PING = "ping"
    PONG = "pong"
    ERROR = "error"


@dataclass
class Message:
    """Базовое сообщение"""
    type: MessageType
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь"""
        data = asdict(self)
        data['type'] = self.type.value
        return data

    def to_json(self) -> str:
        """Конвертирует в JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Создает из JSON"""
        data = json.loads(json_str)
        data['type'] = MessageType(data['type'])
        return cls(**data)


@dataclass
class ConnectMessage(Message):
    """Сообщение подключения"""
    username: str
    version: str = "1.0"


@dataclass
class WelcomeMessage(Message):
    """Приветственное сообщение"""
    player_id: str
    world_size: Dict[str, int]
    your_data: Dict[str, Any]


@dataclass
class MovementMessage(Message):
    """Сообщение движения"""
    player_id: str
    dx: float
    dy: float


@dataclass
class WorldUpdateMessage(Message):
    """Обновление состояния мира"""
    players: list
    ponies: list


@dataclass
class PlayerJoinedMessage(Message):
    """Игрок присоединился"""
    player_id: str
    username: str
    x: float
    y: float
    pony_type: str


@dataclass
class PlayerMovedMessage(Message):
    """Игрок переместился"""
    player_id: str
    x: float
    y: float
    animation: str
    direction: str


@dataclass
class ChatMessage(Message):
    """Сообщение чата"""
    player_id: str
    username: str
    text: str


@dataclass
class ActionMessage(Message):
    """Сообщение действия"""
    player_id: str
    username: str
    action: str
    data: Dict[str, Any]


class Protocol:
    """Утилиты для работы с протоколом"""

    @staticmethod
    def serialize(message: Message) -> str:
        """Сериализует сообщение"""
        return message.to_json() + '|||'

    @staticmethod
    def deserialize(data: str) -> Message:
        """Десериализует сообщение"""
        # Определяем тип сообщения
        raw_data = json.loads(data)
        msg_type = MessageType(raw_data['type'])

        # Создаем соответствующий класс
        message_classes = {
            MessageType.CONNECT: ConnectMessage,
            MessageType.WELCOME: WelcomeMessage,
            MessageType.MOVEMENT: MovementMessage,
            MessageType.WORLD_UPDATE: WorldUpdateMessage,
            MessageType.PLAYER_JOINED: PlayerJoinedMessage,
            MessageType.PLAYER_MOVED: PlayerMovedMessage,
            MessageType.CHAT: ChatMessage,
            MessageType.ACTION: ActionMessage
        }

        msg_class = message_classes.get(msg_type, Message)
        return msg_class.from_json(data)

    @staticmethod
    def create_error(reason: str, code: int = 0) -> Dict[str, Any]:
        """Создает сообщение об ошибке"""
        return {
            'type': MessageType.ERROR.value,
            'code': code,
            'reason': reason,
            'timestamp': 0  # Будет установлено при отправке
        }

    @staticmethod
    def validate_message(data: Dict[str, Any]) -> bool:
        """Проверяет валидность сообщения"""
        required_fields = ['type', 'timestamp']

        for field in required_fields:
            if field not in data:
                return False

        try:
            MessageType(data['type'])
        except:
            return False

        return True