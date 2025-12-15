"""
Конфигурация игры
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class ServerConfig:
    """Конфигурация сервера"""
    host: str = "0.0.0.0"
    port: int = 5555
    max_players: int = 50
    world_width: int = 1920
    world_height: int = 1080
    tick_rate: float = 60.0
    save_interval: int = 300  # Секунды

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerConfig':
        return cls(**data)


@dataclass
class ClientConfig:
    """Конфигурация клиента"""
    server_host: str = "127.0.0.1"
    server_port: int = 5555
    username: str = "Player"
    window_width: int = 1280
    window_height: int = 720
    vsync: bool = True
    show_fps: bool = True
    chat_font_size: int = 14
    pony_scale: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClientConfig':
        return cls(**data)


@dataclass
class GameConfig:
    """Общая конфигурация игры"""
    version: str = "1.0.0"
    assets_path: str = "assets"
    ponies_path: str = "assets/ponies"
    saves_path: str = "saves"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameConfig':
        return cls(**data)


class ConfigManager:
    """Менеджер конфигурации"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)

        self.server_config: Optional[ServerConfig] = None
        self.client_config: Optional[ClientConfig] = None
        self.game_config: Optional[GameConfig] = None

        self.load_all()

    def load_all(self):
        """Загружает все конфигурации"""
        self.load_server_config()
        self.load_client_config()
        self.load_game_config()

    def load_server_config(self) -> ServerConfig:
        """Загружает конфигурацию сервера"""
        config_path = os.path.join(self.config_dir, "server.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.server_config = ServerConfig.from_dict(data)
                print(f"✅ Загружена конфигурация сервера")
            except Exception as e:
                print(f"❌ Ошибка загрузки конфигурации сервера: {e}")
                self.server_config = ServerConfig()
        else:
            self.server_config = ServerConfig()
            self.save_server_config()

        return self.server_config

    def load_client_config(self) -> ClientConfig:
        """Загружает конфигурацию клиента"""
        config_path = os.path.join(self.config_dir, "client.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.client_config = ClientConfig.from_dict(data)
                print(f"✅ Загружена конфигурация клиента")
            except Exception as e:
                print(f"❌ Ошибка загрузки конфигурации клиента: {e}")
                self.client_config = ClientConfig()
        else:
            self.client_config = ClientConfig()
            self.save_client_config()

        return self.client_config

    def load_game_config(self) -> GameConfig:
        """Загружает игровую конфигурацию"""
        config_path = os.path.join(self.config_dir, "game.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.game_config = GameConfig.from_dict(data)
                print(f"✅ Загружена игровая конфигурация")
            except Exception as e:
                print(f"❌ Ошибка загрузки игровой конфигурации: {e}")
                self.game_config = GameConfig()
        else:
            self.game_config = GameConfig()
            self.save_game_config()

        return self.game_config

    def save_server_config(self):
        """Сохраняет конфигурацию сервера"""
        if not self.server_config:
            return

        config_path = os.path.join(self.config_dir, "server.json")

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.server_config.to_dict(), f, indent=2, ensure_ascii=False)
            print("💾 Конфигурация сервера сохранена")
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации сервера: {e}")

    def save_client_config(self):
        """Сохраняет конфигурацию клиента"""
        if not self.client_config:
            return

        config_path = os.path.join(self.config_dir, "client.json")

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.client_config.to_dict(), f, indent=2, ensure_ascii=False)
            print("💾 Конфигурация клиента сохранена")
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации клиента: {e}")

    def save_game_config(self):
        """Сохраняет игровую конфигурацию"""
        if not self.game_config:
            return

        config_path = os.path.join(self.config_dir, "game.json")

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.game_config.to_dict(), f, indent=2, ensure_ascii=False)
            print("💾 Игровая конфигурация сохранена")
        except Exception as e:
            print(f"❌ Ошибка сохранения игровой конфигурации: {e}")

    def get_server(self) -> ServerConfig:
        """Возвращает конфигурацию сервера"""
        if not self.server_config:
            self.load_server_config()
        return self.server_config

    def get_client(self) -> ClientConfig:
        """Возвращает конфигурацию клиента"""
        if not self.client_config:
            self.load_client_config()
        return self.client_config

    def get_game(self) -> GameConfig:
        """Возвращает игровую конфигурацию"""
        if not self.game_config:
            self.load_game_config()
        return self.game_config

    def update_server(self, **kwargs):
        """Обновляет конфигурацию сервера"""
        if not self.server_config:
            self.server_config = ServerConfig()

        for key, value in kwargs.items():
            if hasattr(self.server_config, key):
                setattr(self.server_config, key, value)

        self.save_server_config()

    def update_client(self, **kwargs):
        """Обновляет конфигурацию клиента"""
        if not self.client_config:
            self.client_config = ClientConfig()

        for key, value in kwargs.items():
            if hasattr(self.client_config, key):
                setattr(self.client_config, key, value)

        self.save_client_config()

    def get_assets_path(self) -> str:
        """Возвращает путь к ассетам"""
        game_config = self.get_game()
        return game_config.assets_path

    def get_ponies_path(self) -> str:
        """Возвращает путь к пони"""
        game_config = self.get_game()
        return game_config.ponies_path


# Глобальный экземпляр
config_manager = ConfigManager()