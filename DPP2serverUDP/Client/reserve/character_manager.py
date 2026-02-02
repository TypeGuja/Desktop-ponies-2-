#!/usr/bin/env python3
"""
Character Manager – хранение и изменение персонажей.
"""

import json
import os
import uuid
from datetime import datetime


class CharacterManager:
    """Управление данными персонажей."""

    def __init__(self, filename: str = "characters.json"):
        self.filename = filename

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------
    def load_characters(self, username: str) -> list[dict]:
        """Загрузить список персонажей конкретного пользователя."""
        if not os.path.isfile(self.filename):
            return []

        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(username, [])
        except Exception:
            return []

    def save_character(self, character: dict) -> bool:
        """Сохранить (добавить/обновить) персонаж."""
        username = character.get("owner")
        if not username:
            return False

        # загрузить текущие данные
        if os.path.isfile(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        else:
            data = {}

        data.setdefault(username, [])

        # поиск по id
        char_id = character.get("id")
        for i, existing in enumerate(data[username]):
            if existing.get("id") == char_id:
                data[username][i] = character
                break
        else:
            data[username].append(character)

        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def update_position(
        self,
        character_id: str,
        username: str,
        position: dict,
        character: dict | None = None,
    ) -> bool:
        """Обновить позицию персонажа."""
        if character is None or not character.get("owner"):
            return False

        if not os.path.isfile(self.filename):
            return False

        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        if username in data:
            for i, char in enumerate(data[username]):
                if char.get("id") == character_id:
                    data[username][i]["position"] = position
                    try:
                        with open(self.filename, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        return True
                    except Exception:
                        return False
        return False

    # ------------------------------------------------------------------
    # Creation / deletion
    # ------------------------------------------------------------------
    def create_default_character(
        self,
        name: str,
        username: str,
        character_type: str = "default",
    ) -> dict:
        """Создать базовый набор полей персонажа."""
        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "owner": username,
            "character_type": character_type,
            "created": datetime.now().isoformat(),
            "level": 1,
            "health": 100,
            "position": {"x": 0, "y": 0, "z": 0},
            "rotation": {"x": 0, "y": 0, "z": 0},
            "inventory": [],
            "stats": {"strength": 10, "agility": 10, "intelligence": 10},
        }

    def delete_character(self, character_id: str, username: str) -> bool:
        """Удалить персонаж из файла."""
        if not os.path.isfile(self.filename):
            return False

        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                data = json.load(f)

            if username in data:
                before = len(data[username])
                data[username] = [
                    c for c in data[username] if c.get("id") != character_id
                ]
                if len(data[username]) != before:
                    with open(self.filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    return True
        except Exception:
            pass
        return False
