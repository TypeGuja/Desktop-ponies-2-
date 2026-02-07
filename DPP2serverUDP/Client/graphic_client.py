#!/usr/bin/env python3
"""
DPP2 Graphic Client – клиент с камерой, плавным зумом и поддержкой
трансляции экрана сервера. При изменении зума (`+`, `-`, колесо мыши)
масштабируется и фон, полученный от сервера.
"""

# ----------------------------------------------------------------------
#   Стандартные модули
# ----------------------------------------------------------------------
import os
import sys
import time
import uuid
import math
import queue
import threading
import base64
import io
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any

# ----------------------------------------------------------------------
#   Pygame
# ----------------------------------------------------------------------
import pygame

# ----------------------------------------------------------------------
#   Pillow – работа с изображениями
# ----------------------------------------------------------------------
from PIL import Image

# ----------------------------------------------------------------------
#   Локальные модули проекта
# ----------------------------------------------------------------------
from animated_character import AnimatedCharacter, CharacterSelector

# ----------------------------------------------------------------------
#   Состояния игры
# ----------------------------------------------------------------------
class GameState(Enum):
    MENU = 1
    CONNECTING = 2
    CHARACTER_SELECT = 3
    IN_GAME = 4
    CHAT = 5
    ESC_MENU = 6
    SETTINGS_MENU = 7


# ----------------------------------------------------------------------
#   Камера (следит за персонажем, умеет плавно зуммировать)
# ----------------------------------------------------------------------
class Camera:
    """Камера с поддержкой плавного перемещения и зума."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.offset = [width // 2, height // 2]          # текущий сдвиг
        self.target_offset = [width // 2, height // 2]   # цель сдвига
        self.zoom = 1.2                                 # текущий зум
        self.target_zoom = 1.2                          # цель зума
        self.follow_speed = 0.15
        self.zoom_speed = 0.1
        self.smoothing = True
        self.follow_player = True
        self.grid_size = 50

    # --------------------------------------------------------------
    #   Обновление позиции и зума
    # --------------------------------------------------------------
    def update(self, player_position: Optional[Dict] = None, delta_time: float = 1.0):
        """Плавно смещаем камеру к игроку и меняем зум."""
        if player_position and self.follow_player:
            factor = self.zoom * 100                     # коэффициент «юнит → пиксель»
            target_x = self.width // 2 - player_position["x"] * factor
            target_y = self.height // 2 - player_position["y"] * factor

            if self.smoothing:
                self.target_offset[0] += (
                    (target_x - self.target_offset[0])
                    * self.follow_speed
                    * delta_time
                    * 60
                )
                self.target_offset[1] += (
                    (target_y - self.target_offset[1])
                    * self.follow_speed
                    * delta_time
                    * 60
                )

                self.offset[0] += (
                    (self.target_offset[0] - self.offset[0])
                    * self.follow_speed
                    * delta_time
                    * 60
                )
                self.offset[1] += (
                    (self.target_offset[1] - self.offset[1])
                    * self.follow_speed
                    * delta_time
                    * 60
                )
            else:
                self.offset[0] = target_x
                self.offset[1] = target_y
                self.target_offset[0] = target_x
                self.target_offset[1] = target_y

        # плавный зум
        if abs(self.zoom - self.target_zoom) > 0.01:
            self.zoom += (
                (self.target_zoom - self.zoom)
                * self.zoom_speed
                * delta_time
                * 60
            )

    # --------------------------------------------------------------
    #   Преобразования координат
    # --------------------------------------------------------------
    def world_to_screen(self, world_pos: Dict) -> Tuple[int, int]:
        """Мировые → экранные."""
        x = int(world_pos["x"] * 100 * self.zoom + self.offset[0])
        y = int(world_pos["y"] * 100 * self.zoom + self.offset[1])
        return x, y

    def screen_to_world(self, screen_pos: Tuple[int, int]) -> Dict:
        """Экранные → мировые."""
        x = (screen_pos[0] - self.offset[0]) / (100 * self.zoom)
        y = (screen_pos[1] - self.offset[1]) / (100 * self.zoom)
        return {"x": x, "y": y}

    # --------------------------------------------------------------
    #   Управление зумом
    # --------------------------------------------------------------
    def zoom_in(self):
        self.target_zoom = min(self.target_zoom * 1.1, 3.0)

    def zoom_out(self):
        self.target_zoom = max(self.target_zoom * 0.9, 0.5)

    # --------------------------------------------------------------
    #   Сброс к начальным параметрам
    # --------------------------------------------------------------
    def reset(self):
        self.offset = [self.width // 2, self.height // 2]
        self.target_offset = [self.width // 2, self.height // 2]
        self.zoom = 1.2
        self.target_zoom = 1.2


# ----------------------------------------------------------------------
#   Плавное интерполирование движений (для других игроков)
# ----------------------------------------------------------------------
class SmoothMovement:
    """Интерполяция позиции другого игрока."""

    def __init__(self):
        self.position = {"x": 0, "y": 0, "z": 0}
        self.target_position = {"x": 0, "y": 0, "z": 0}
        self.velocity = {"x": 0, "y": 0, "z": 0}
        self.last_update = time.time()
        self.smooth_factor = 0.25
        self.max_interpolation_time = 0.5

    def update_target(self, new_position: Dict, timestamp: Optional[float] = None):
        self.target_position = new_position.copy()
        self.last_update = time.time()

        dx = new_position["x"] - self.position["x"]
        dy = new_position["y"] - self.position["y"]
        dz = new_position["z"] - self.position["z"]

        self.velocity["x"] = dx * 0.5 + self.velocity["x"] * 0.5
        self.velocity["y"] = dy * 0.5 + self.velocity["y"] * 0.5
        self.velocity["z"] = dz * 0.5 + self.velocity["z"] * 0.5

    def update(self, delta_time: float):
        """Интерполировать позицию."""
        dx = self.target_position["x"] - self.position["x"]
        dy = self.target_position["y"] - self.position["y"]
        dz = self.target_position["z"] - self.position["z"]

        dx += self.velocity["x"] * 0.1
        dy += self.velocity["y"] * 0.1
        dz += self.velocity["z"] * 0.1

        self.position["x"] += dx * self.smooth_factor * delta_time * 60
        self.position["y"] += dy * self.smooth_factor * delta_time * 60
        self.position["z"] += dz * self.smooth_factor * delta_time * 60

        if (
            abs(dx) < 0.001
            and abs(dy) < 0.001
            and abs(dz) < 0.001
        ):
            self.position = self.target_position.copy()
            self.velocity = {"x": 0, "y": 0, "z": 0}


# ----------------------------------------------------------------------
#   Данные персонажа в списке выбора
# ----------------------------------------------------------------------
@dataclass
class CharacterItem:
    id: str
    name: str
    folder: str
    animation: Any = None


# ----------------------------------------------------------------------
#   Выбор персонажа (центрированный список)
# ----------------------------------------------------------------------
class SimpleCharacterSelector:
    """Окно‑лист персонажей."""

    DEFAULT_PRIORITY = [
        "Celestia", "Luna", "Cadance", "TwilightSparkle",
        "AppleJack", "RainbowDash", "Fluttershy",
        "Rarity", "PinkiePie", "Trixie",
        "SunsetShimmer", "StarlightGlimmer",
    ]

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        *,
        list_width: int = 600,
        item_height: int = 70,
        margin: int = 10,
        scroll_speed: int = 30,
    ) -> None:
        self.screen_w = screen_width
        self.screen_h = screen_height
        self.list_width = list_width
        self.item_height = item_height
        self.margin = margin
        self.scroll_speed = scroll_speed

        self.scroll_offset = 0
        self.max_scroll = 0
        self.characters: List[CharacterItem] = []
        self.selected_index = 0
        self._current_sort = "priority"

    # ------------------------------------------------------------------
    #   Загрузка персонажей
    # ------------------------------------------------------------------
    def load_characters(self) -> None:
        from config import config

        assets_root = config.get("characters.assets_path", "assets/characters")
        if not os.path.isdir(assets_root):
            print(f"[WARN] Characters folder not found: {assets_root}")
            return

        for entry in sorted(os.listdir(assets_root)):
            folder = os.path.join(assets_root, entry)
            if not os.path.isdir(folder):
                continue

            anim_obj = AnimatedCharacter(
                {"name": entry.capitalize(), "character_type": entry},
                assets_path=assets_root,
            )
            if anim_obj.load_animations():
                anim_obj.set_animation("idle")
                animation = anim_obj
            else:
                animation = None

            self.characters.append(
                CharacterItem(
                    id=entry,
                    name=entry.capitalize(),
                    folder=folder,
                    animation=animation,
                )
            )

        self.sort_characters(self._current_sort)

        content_h = (
            len(self.characters) * (self.item_height + self.margin)
            - self.margin
        )
        self.max_scroll = max(0, content_h - self.screen_h + 200)

    # ------------------------------------------------------------------
    #   Сортировка списка
    # ------------------------------------------------------------------
    def sort_characters(self, order: str = "priority") -> None:
        order = order.lower()
        self._current_sort = order

        if order == "priority":
            prio_map = {cid: i for i, cid in enumerate(self.DEFAULT_PRIORITY)}
            self.characters.sort(
                key=lambda ch: (
                    prio_map.get(ch.id, len(self.DEFAULT_PRIORITY)),
                    ch.name.lower(),
                )
            )
        elif order == "name":
            self.characters.sort(key=lambda ch: ch.name.lower())
        elif order == "id":
            self.characters.sort(key=lambda ch: ch.id.lower())
        else:
            print(f"[WARN] Unknown sort order «{order}», fallback to priority.")
            self.sort_characters("priority")

    # ------------------------------------------------------------------
    #   Навигация
    # ------------------------------------------------------------------
    def prev_character(self):
        if not self.characters:
            return
        self.selected_index = (self.selected_index - 1) % len(self.characters)
        self._ensure_selected_visible()

    def next_character(self):
        if not self.characters:
            return
        self.selected_index = (self.selected_index + 1) % len(self.characters)
        self._ensure_selected_visible()

    # ------------------------------------------------------------------
    #   Скролл списка (исправлен порядок прокрутки)
    # ------------------------------------------------------------------
    def _scroll(self, delta: int):
        """delta > 0  → прокрутка вверх (меньше offset)"""
        if delta > 0:
            self.scroll_offset = max(0, self.scroll_offset - 1)
        elif delta < 0:
            self.scroll_offset = min(self.max_scroll, self.scroll_offset + 1)

    def handle_mouse_wheel(self, event):
        """Обрабатываем событие колёсика мыши (pygame)."""
        delta = 0
        if hasattr(event, "y"):
            delta = event.y
        elif hasattr(event, "button"):
            if event.button == 4:
                delta = 1
            elif event.button == 5:
                delta = -1

        if delta:
            self._scroll(delta)

    # ------------------------------------------------------------------
    #   Клик – выбор персонажа
    # ------------------------------------------------------------------
    def handle_click(self, pos: Tuple[int, int]) -> Optional[str]:
        for idx, char in enumerate(self.characters):
            rect = self._rect_for_index(idx)
            if rect.collidepoint(pos):
                self.selected_index = idx
                return "select"
        return None

    # ------------------------------------------------------------------
    #   Автоскролл к выбранному элементу
    # ------------------------------------------------------------------
    def _ensure_selected_visible(self):
        item_y = self._y_for_index(self.selected_index)
        item_bottom = item_y + self.item_height

        top_visible = 100 + self.scroll_offset
        bottom_visible = self.screen_h - 100 + self.scroll_offset

        if item_y < top_visible:
            self.scroll_offset = max(0, item_y - 100)
        elif item_bottom > bottom_visible:
            self.scroll_offset = min(self.max_scroll, item_bottom - self.screen_h + 100)

    # ------------------------------------------------------------------
    #   Внутренние методы позиционирования
    # ------------------------------------------------------------------
    def _rect_for_index(self, idx: int) -> pygame.Rect:
        x = (self.screen_w - self.list_width) // 2
        y = self._y_for_index(idx)
        return pygame.Rect(x, y, self.list_width, self.item_height)

    def _y_for_index(self, idx: int) -> int:
        visible_h = min(
            len(self.characters) * (self.item_height + self.margin),
            self.screen_h - 200,
        )
        start_y = (self.screen_h - visible_h) // 2
        return start_y + idx * (self.item_height + self.margin) - self.scroll_offset

    # ------------------------------------------------------------------
    #   Обновление анимаций
    # ------------------------------------------------------------------
    def update(self, delta_time: float = 1.0):
        for char in self.characters:
            if char.animation:
                char.animation.update()

    # ------------------------------------------------------------------
    #   Рендер
    # ------------------------------------------------------------------
    def render(self, screen: pygame.Surface, colors: dict, fonts: dict):
        # полупрозрачный фон
        overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        # заголовок
        title = fonts["large"].render("SELECT CHARACTER", True, colors["white"])
        screen.blit(title, (self.screen_w // 2 - title.get_width() // 2, 50))

        # фон списка
        list_x = (self.screen_w - self.list_width) // 2
        list_y = 100
        list_h = self.screen_h - 200

        list_bg = pygame.Surface((self.list_width, list_h), pygame.SRCALPHA)
        list_bg.fill((*colors["dark_grey"][:3], 180))
        screen.blit(list_bg, (list_x, list_y))
        pygame.draw.rect(
            screen,
            colors["accent_grey"],
            (list_x, list_y, self.list_width, list_h),
            2,
            border_radius=8,
        )

        # элементы списка
        for idx, char in enumerate(self.characters):
            rect = self._rect_for_index(idx)

            # не рисуем полностью невидимые элементы
            if rect.bottom < list_y or rect.top > list_y + list_h:
                continue

            # фон элемента
            if idx == self.selected_index:
                pygame.draw.rect(screen, colors["player"], rect, border_radius=6)
                pygame.draw.rect(screen, colors["white"], rect, 2, border_radius=6)
            else:
                pygame.draw.rect(screen, colors["grey"], rect, border_radius=6)
                pygame.draw.rect(screen, colors["accent_grey"], rect, 1, border_radius=6)

            # анимация слева
            if char.animation:
                char.animation.draw(
                    screen,
                    (rect.x + 20, rect.centery),
                    scale=0.8,
                )
            else:
                # заглушка – цветной круг + первая буква
                col_map = {
                    "Celestia": (255, 215, 0),
                    "Luna": (138, 43, 226),
                    "Cadance": (255, 182, 193),
                    "TwilightSparkle": (147, 112, 219),
                    "AppleJack": (255, 165, 0),
                    "RainbowDash": (0, 191, 255),
                    "Fluttershy": (255, 255, 0),
                    "Rarity": (192, 192, 192),
                    "PinkiePie": (255, 105, 180),
                }
                col = col_map.get(char.id, (150, 100, 100))
                radius = int(25 * 0.8)
                pygame.draw.circle(
                    screen, col, (rect.x + 40, rect.centery), radius
                )
                try:
                    f = pygame.font.Font(None, int(20 * 0.8))
                    txt = f.render(char.id[0].upper(), True, (255, 255, 255))
                    txt_rect = txt.get_rect(center=(rect.x + 40, rect.centery))
                    screen.blit(txt, txt_rect)
                except Exception:
                    pass

            # имя персонажа (справа)
            name_surf = fonts["medium"].render(char.name, True, colors["white"])
            screen.blit(
                name_surf,
                (rect.x + 120, rect.centery - name_surf.get_height() // 2),
            )

            # подсказка под выбранным элементом
            if idx == self.selected_index:
                hint = fonts["tiny"].render(
                    "← CLICK OR ENTER TO SELECT →", True, colors["white"]
                )
                screen.blit(
                    hint,
                    (rect.centerx - hint.get_width() // 2, rect.bottom + 10),
                )

        # индикатор количества персонажей
        count_txt = f"{self.selected_index + 1} / {len(self.characters)}"
        count_surf = fonts["medium"].render(count_txt, True, colors["white"])
        screen.blit(
            count_surf,
            (
                self.screen_w // 2 - count_surf.get_width() // 2,
                self.screen_h - 50,
            ),
        )

    # ------------------------------------------------------------------
    #   Публичные методы
    # ------------------------------------------------------------------
    def get_selected_character(self) -> Optional[dict]:
        if not self.characters:
            return None
        ch = self.characters[self.selected_index]
        return {
            "id": ch.id,
            "name": ch.name,
            "folder": ch.folder,
            "animation": ch.animation,
        }

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                return self.handle_click(event.pos)
            elif event.button in (4, 5):
                self.handle_mouse_wheel(event)
        elif event.type == pygame.MOUSEWHEEL:
            self.handle_mouse_wheel(event)
        return None


# ----------------------------------------------------------------------
#   Другой игрок (получаем данные по сети, интерполируем, анимируем)
# ----------------------------------------------------------------------
class OtherPlayer:
    """Объект, представляющий другого игрока."""

    def __init__(self, player_data: dict):
        self.id = player_data.get("id", "")
        self.name = player_data.get("name", "Player")
        self.character_type = player_data.get("character_type", "default")
        self.smooth_movement = SmoothMovement()
        self.position = player_data.get("position", {"x": 0, "y": 0, "z": 0})
        self.smooth_movement.position = self.position.copy()
        self.smooth_movement.target_position = self.position.copy()

        self.last_update_time = time.time()
        self.last_animation_update = time.time()
        self.last_direction = "right"
        self.is_active = True
        self.is_moving = False

        self.animation = None
        self.init_animation(player_data)

        print(f"[DEBUG] Created player {self.name} ({self.character_type})")

    # --------------------------------------------------------------
    #   Инициализация/перезагрузка анимации
    # --------------------------------------------------------------
    def init_animation(self, player_data: dict) -> bool:
        try:
            ctype = player_data.get("character_type", "default")
            cname = player_data.get("name", "Player")

            # Если тип «default» – пытаемся вывести его из имени
            if ctype == "default" and cname:
                low = cname.lower()
                if "celestia" in low:
                    ctype = "Celestia"
                elif "luna" in low:
                    ctype = "Luna"
                elif "cadance" in low or "cadence" in low:
                    ctype = "Cadance"
                elif "twilight" in low:
                    ctype = "TwilightSparkle"
                elif "apple" in low:
                    ctype = "AppleJack"
                elif "rainbow" in low:
                    ctype = "RainbowDash"
                elif "fluttershy" in low:
                    ctype = "Fluttershy"
                elif "rarity" in low:
                    ctype = "Rarity"
                elif "pinkie" in low:
                    ctype = "PinkiePie"
                elif "trixie" in low:
                    ctype = "Trixie"
                elif "sunsetshimmer" in low:
                    ctype = "SunsetShimmer"
                elif "starlightglimmer" in low:
                    ctype = "StarlightGlimmer"

            print(f"[DEBUG] Init animation for {cname} ({ctype})")
            char_data = {"name": cname, "character_type": ctype}
            self.animation = AnimatedCharacter(char_data)

            if self.animation.load_animations():
                self.animation.set_animation("idle")
                print(f"[DEBUG] ✓ Animation loaded for {ctype}")
                return True

            # нет анимаций → заглушка
            print(f"[DEBUG] ✗ No animation for {ctype}, using stub")
            self.animation = self.create_stub_animation(ctype)
            return False
        except Exception as e:
            print(f"[ERROR] Animation init error: {e}")
            self.animation = self.create_stub_animation("default")
            return False

    # --------------------------------------------------------------
    #   Простая заглушка (круг + первая буква)
    # --------------------------------------------------------------
    def create_stub_animation(self, char_type: str):
        class StubAnimation:
            def __init__(self, ct):
                self.char_type = ct
                self.current_animation = "idle"
                self.current_direction = "right"

            def set_animation(self, anim):
                self.current_animation = anim
                return True

            def set_direction(self, dr):
                self.current_direction = dr
                return True

            def update(self):
                pass

            def draw(self, surface, position, scale=1.0):
                color_map = {
                    "Celestia": (255, 215, 0),
                    "Luna": (138, 43, 226),
                    "Cadance": (255, 182, 193),
                    "TwilightSparkle": (147, 112, 219),
                    "AppleJack": (255, 165, 0),
                    "RainbowDash": (0, 191, 255),
                    "Fluttershy": (255, 255, 0),
                    "Rarity": (192, 192, 192),
                    "PinkiePie": (255, 105, 180),
                    "default": (200, 100, 100),
                }
                color = color_map.get(self.char_type, color_map["default"])
                radius = int(25 * scale)
                pygame.draw.circle(
                    surface, color, (int(position[0]), int(position[1])), radius
                )
                try:
                    f = pygame.font.Font(None, int(20 * scale))
                    txt = f.render(
                        self.char_type[0] if self.char_type else "?",
                        True,
                        (255, 255, 255),
                    )
                    rect = txt.get_rect(center=(int(position[0]), int(position[1])))
                    surface.blit(txt, rect)
                except Exception:
                    pass

        return StubAnimation(char_type)

    # --------------------------------------------------------------
    #   Обновление позиций от сервера
    # --------------------------------------------------------------
    def update_position(self, new_position: dict, timestamp: Optional[float] = None):
        self.position = new_position.copy()
        self.smooth_movement.update_target(new_position, timestamp)
        self.last_update_time = time.time()

    # --------------------------------------------------------------
    #   Основное обновление (интерполяция + анимация)
    # --------------------------------------------------------------
    def update(self, delta_time: float):
        if not self.is_active:
            return

        prev = self.smooth_movement.position.copy()
        self.smooth_movement.update(delta_time)
        cur = self.smooth_movement.position

        # движется ли игрок?
        dx = cur["x"] - prev["x"]
        dy = cur["y"] - prev["y"]
        distance = math.sqrt(dx * dx + dy * dy)
        self.is_moving = distance > 0.015

        now = time.time()
        if now - self.last_animation_update > 0.08:
            if self.is_moving:
                if abs(dx) > abs(dy):
                    direction = "right" if dx > 0 else "left"
                else:
                    direction = "down" if dy > 0 else "up"

                if direction != self.last_direction:
                    self.animation.set_direction(direction)
                    self.last_direction = direction

                if self.animation.current_animation != "walk":
                    self.animation.set_animation("walk")
            else:
                if self.animation.current_animation != "idle":
                    self.animation.set_animation("idle")

            self.animation.update()
            self.last_animation_update = now

    # --------------------------------------------------------------
    #   Публичный геттер позиции (для сообщений над головой)
    # --------------------------------------------------------------
    def get_position(self) -> dict:
        return self.smooth_movement.position


# ----------------------------------------------------------------------
#   Сообщения над головой (чат)
# ----------------------------------------------------------------------
class ChatMessageOverhead:
    """Текст, появляющийся над головой персонажа."""

    def __init__(self, text: str, character_name: str, duration: float = 10.0):
        self.text = text
        self.character_name = character_name
        self.start_time = time.time()
        self.duration = duration
        self.alpha = 255
        self.fade_start = duration - 2.0
        self.position = {"x": 0, "y": 0, "z": 0}
        self.target_height_offset = 40
        self.current_height_offset = 40

    def is_expired(self) -> bool:
        return time.time() - self.start_time > self.duration

    def update(self, character_position: Optional[dict] = None, delta_time: float = 1.0):
        if character_position:
            self.position = character_position.copy()

        elapsed = time.time() - self.start_time
        if elapsed > self.fade_start:
            fade = (elapsed - self.fade_start) / (self.duration - self.fade_start)
            self.alpha = int(255 * (1 - fade))

        if abs(self.current_height_offset - self.target_height_offset) > 0.1:
            self.current_height_offset += (
                self.target_height_offset - self.current_height_offset
            ) * 5.0 * delta_time

    def set_height_offset(self, offset: int):
        self.target_height_offset = offset

    def get_screen_position(self, camera: Camera) -> Optional[Tuple[int, int]]:
        if not camera:
            return None
        pos = {
            "x": self.position["x"],
            "y": self.position["y"],
            "z": self.position["z"]
            + self.current_height_offset / 100.0,
        }
        return camera.world_to_screen(pos)


# ----------------------------------------------------------------------
#   Главный графический клиент
# ----------------------------------------------------------------------
class DPP2GraphicClient:
    """Клиент с камерой, анимациями, чат‑сообщениями и UI."""

    # --------------------------------------------------------------
    #   Конструктор
    # --------------------------------------------------------------
    def __init__(self):
        pygame.init()
        pygame.font.init()

        from config import config
        self.config = config

        # окно
        self.width = self.config.get("graphics.width", 1200)
        self.height = self.config.get("graphics.height", 800)
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("DPP2 - Camera Follow System")

        # иконка окна
        try:
            pygame.display.set_icon(self.create_window_icon())
        except Exception:
            pass

        # цветовая схема
        self.current_theme = self.config.get("ui.theme", "black")
        self.load_color_scheme()

        # камера
        self.camera = Camera(self.width, self.height)
        self.camera.follow_player = self.config.get("camera.follow_player", True)
        self.camera.smoothing = self.config.get("camera.smoothing", True)
        self.camera.zoom_speed = self.config.get("camera.zoom_speed", 0.1)
        self.camera.zoom = self.config.get("camera.default_zoom", 1.2)
        self.camera.target_zoom = self.config.get("camera.default_zoom", 1.2)

        # состояние
        self.game_state = GameState.MENU
        self.running = True
        self.clock = pygame.time.Clock()
        self.fps = self.config.get("graphics.fps_limit", 60)

        # сеть
        from network_client import NetworkClient
        self.network = NetworkClient()
        self.connected = False
        self.connection_in_progress = False

        # очереди
        self.network_queue = queue.Queue()

        # игровые данные
        self.username = ""
        self.character = None
        self.other_players: Dict[str, OtherPlayer] = {}
        self.other_players_data: Dict[str, dict] = {}
        self.in_world = False
        self.world_data: dict = {}
        self.character_selected = False

        # анимация собственного персонажа
        self.player_animation: Optional[AnimatedCharacter] = None

        # UI‑селектор персонажа
        self.character_selector: Optional[SimpleCharacterSelector] = None
        self.show_character_select = False

        # клиент‑идентификатор
        self.client_id = str(uuid.uuid4())[:8]
        print(f"[SYSTEM] Generated client_id: {self.client_id}")

        # ввод
        self.keys = {
            pygame.K_w: False,
            pygame.K_a: False,
            pygame.K_s: False,
            pygame.K_d: False,
            pygame.K_SPACE: False,
            pygame.K_LSHIFT: False,
            pygame.K_UP: False,
            pygame.K_DOWN: False,
            pygame.K_LEFT: False,
            pygame.K_RIGHT: False,
            pygame.K_ESCAPE: False,
            pygame.K_F1: False,
            pygame.K_j: False,
            pygame.K_k: False,
            pygame.K_l: False,
        }

        self.fonts = self.load_fonts()

        # UI‑элементы
        self.menu_buttons = []
        self.input_fields = []
        self.chat_messages = []
        self.chat_input = ""
        self.chat_active = False
        self.active_input_field: Optional[int] = None

        # сообщения над головой
        self.overhead_messages: List[ChatMessageOverhead] = []

        # видимость UI
        self.show_esc_menu = False
        self.show_settings_menu = False
        self.side_panel_visible = True
        self.side_panel_auto_hide = self.config.get(
            "ui.side_panel_auto_hide", True
        )

        self.side_panel_width = self.config.get("ui.side_panel_width", 320)
        self.top_panel_height = self.config.get("ui.top_panel_height", 70)
        self.bottom_panel_height = self.config.get(
            "ui.bottom_panel_height", 40
        )

        # чат
        self.chat_message_lifetime = 10.0
        self.chat_message_fade_time = 3.0

        # таймеры
        self.last_update = time.time()
        self.position_update_rate = self.config.get(
            "network.udp_position_update_rate", 0.016
        )
        self.last_position_update = 0
        self.last_heartbeat = 0
        self.heartbeat_interval = self.config.get(
            "network.udp_heartbeat_interval", 1.0
        )

        # статистика
        self.stats = {
            "fps": 0,
            "players_online": 0,
            "ping": 0,
            "udp_packets_sent": 0,
            "udp_packets_received": 0,
            "connection_time": 0,
            "camera_x": 0,
            "camera_y": 0,
            "screen_frames_received": 0,
        }

        # UI‑анимация
        self.menu_animation = 0.0
        self.settings_animation = 0.0
        self.side_panel_animation = 1.0
        self.menu_animation_speed = self.config.get(
            "ui.menu_animation_speed", 0.3
        )

        # темы
        self.available_themes = self.config.get_available_themes()
        self.theme_buttons = []

        # обработка экрана сервера
        self.screen_frame_buffer = {}
        self.screen_frame_chunks = {}
        self.screen_image = None
        self.last_screen_update = 0
        self.screen_update_interval = 10

        # UI‑инициализация
        self.init_ui()

        # сетевой поток
        self.stop_network_thread = False
        self.network_thread: Optional[threading.Thread] = None

    # --------------------------------------------------------------
    #   Вспомогательные функции
    # --------------------------------------------------------------
    def load_color_scheme(self):
        scheme = self.config.get_color_scheme(self.current_theme)
        self.colors = {
            "black": tuple(scheme.get("black", [10, 10, 15])),
            "dark_grey": tuple(scheme.get("dark_grey", [30, 30, 35])),
            "grey": tuple(scheme.get("grey", [50, 50, 60])),
            "light_grey": tuple(scheme.get("light_grey", [80, 80, 90])),
            "white": tuple(scheme.get("white", [240, 240, 245])),
            "accent_grey": tuple(scheme.get("accent_grey", [120, 120, 130])),
            "success": tuple(scheme.get("success", [100, 220, 100])),
            "error": tuple(scheme.get("error", [220, 100, 100])),
            "warning": tuple(scheme.get("warning", [220, 180, 100])),
            "player": tuple(scheme.get("player", [80, 160, 240])),
            "other_player": tuple(scheme.get("other_player", [240, 100, 100])),
            "chat_overhead": tuple(scheme.get("player", [200, 230, 255])),
        }

    def create_window_icon(self) -> pygame.Surface:
        size = 32
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(surf, self.colors["dark_grey"], (0, 0, size, size))

        # буква D
        pygame.draw.rect(surf, self.colors["player"], (8, 8, 6, 16))
        pygame.draw.rect(surf, self.colors["player"], (14, 8, 6, 4))
        pygame.draw.rect(surf, self.colors["player"], (14, 20, 6, 4))
        pygame.draw.rect(surf, self.colors["player"], (20, 12, 2, 8))

        # иконка камеры
        pygame.draw.circle(surf, self.colors["white"], (24, 16), 3)
        return surf

    def load_fonts(self) -> dict:
        try:
            title = pygame.font.Font(None, 42)
            large = pygame.font.Font(None, 28)
            medium = pygame.font.Font(None, 22)
            small = pygame.font.Font(None, 18)
            tiny = pygame.font.Font(None, 14)
        except Exception:
            title = pygame.font.SysFont("Arial", 42, bold=True)
            large = pygame.font.SysFont("Arial", 28, bold=True)
            medium = pygame.font.SysFont("Arial", 22)
            small = pygame.font.SysFont("Arial", 18)
            tiny = pygame.font.SysFont("Arial", 14)

        return {
            "title": title,
            "large": large,
            "medium": medium,
            "small": small,
            "tiny": tiny,
        }

    # --------------------------------------------------------------
    #   UI‑инициализация
    # --------------------------------------------------------------
    def init_ui(self):
        side_panel_x = self.width - self.side_panel_width

        # поля ввода
        self.input_fields = [
            {
                "name": "server_host",
                "label": "SERVER ADDRESS",
                "rect": pygame.Rect(
                    side_panel_x + 25, 120, self.side_panel_width - 50, 42
                ),
                "text": self.config.get(
                    "network.default_host", "127.0.0.1"
                ),
                "active": False,
                "visible": True,
                "max_length": 50,
                "hint": "Enter server IP",
            },
            {
                "name": "server_port",
                "label": "SERVER PORT",
                "rect": pygame.Rect(
                    side_panel_x + 25, 185, self.side_panel_width - 50, 42
                ),
                "text": str(
                    self.config.get("network.default_port", 5555)
                ),
                "active": False,
                "visible": True,
                "max_length": 10,
                "hint": "Port number",
            },
            {
                "name": "username",
                "label": "USERNAME",
                "rect": pygame.Rect(
                    side_panel_x + 25, 250, self.side_panel_width - 50, 42
                ),
                "text": "",
                "active": False,
                "visible": False,
                "max_length": 20,
                "hint": "Enter your name",
            },
        ]

        # кнопки главного меню
        btn_y = 320
        btn_h = 48
        btn_sp = 65

        self.menu_buttons = [
            {
                "id": "connect",
                "text": "CONNECT TO SERVER",
                "rect": pygame.Rect(
                    side_panel_x + 25, btn_y, self.side_panel_width - 50, btn_h
                ),
                "action": self.connect_to_server,
                "enabled": True,
                "icon": "📡",
            },
            {
                "id": "login",
                "text": "LOGIN",
                "rect": pygame.Rect(
                    side_panel_x + 25,
                    btn_y + btn_sp,
                    self.side_panel_width - 50,
                    btn_h,
                ),
                "action": self.login,
                "enabled": False,
                "icon": "👤",
            },
            {
                "id": "character",
                "text": "SELECT CHARACTER",
                "rect": pygame.Rect(
                    side_panel_x + 25,
                    btn_y + btn_sp * 2,
                    self.side_panel_width - 50,
                    btn_h,
                ),
                "action": self.select_character,
                "enabled": False,
                "icon": "🎮",
            },
            {
                "id": "join_world",
                "text": "ENTER WORLD",
                "rect": pygame.Rect(
                    side_panel_x + 25,
                    btn_y + btn_sp * 3,
                    self.side_panel_width - 50,
                    btn_h,
                ),
                "action": self.join_world,
                "enabled": False,
                "icon": "🌍",
            },
            {
                "id": "test_animations",
                "text": "TEST ANIMATIONS",
                "rect": pygame.Rect(
                    side_panel_x + 25,
                    btn_y + btn_sp * 4,
                    self.side_panel_width - 50,
                    btn_h,
                ),
                "action": self.test_animations,
                "enabled": True,
                "icon": "🔧",
            },
            {
                "id": "quit",
                "text": "QUIT GAME",
                "rect": pygame.Rect(
                    side_panel_x + 25,
                    btn_y + btn_sp * 5,
                    self.side_panel_width - 50,
                    btn_h,
                ),
                "action": self.quit_game,
                "enabled": True,
                "icon": "🚪",
            },
        ]

        # ESC‑меню
        self.esc_menu_buttons = [
            {"id": "resume", "text": "RESUME GAME", "action": self.resume_game, "icon": "▶"},
            {"id": "settings", "text": "SETTINGS", "action": self.open_settings, "icon": "⚙"},
            {"id": "toggle_ui", "text": "TOGGLE UI", "action": self.toggle_ui_visibility, "icon": "👁"},
            {"id": "disconnect", "text": "DISCONNECT", "action": self.disconnect_from_server, "icon": "📡"},
            {"id": "quit_esc", "text": "QUIT TO DESKTOP", "action": self.quit_game, "icon": "🚪"},
        ]

        # кнопки тем
        self.init_theme_buttons()

    def init_theme_buttons(self):
        self.theme_buttons = []
        themes = self.config.get("color_schemes", {})

        for i, (key, data) in enumerate(themes.items()):
            self.theme_buttons.append(
                {
                    "id": f"theme_{key}",
                    "text": data.get("name", key.upper()),
                    "theme_key": key,
                    "action": lambda t=key: self.change_theme(t),
                    "icon": "🎨",
                    "selected": key == self.current_theme,
                }
            )

    # --------------------------------------------------------------
    #   Сетевой поток
    # --------------------------------------------------------------
    def start_network_thread(self):
        if self.network_thread and self.network_thread.is_alive():
            self.stop_network_thread = True
            self.network_thread.join(timeout=1.0)

        self.stop_network_thread = False
        self.network_thread = threading.Thread(
            target=self.network_loop, daemon=True
        )
        self.network_thread.start()

    def network_loop(self):
        while self.running and not self.stop_network_thread:
            try:
                if self.network.is_connected():
                    data = self.network.receive()
                    if data:
                        self.stats["udp_packets_received"] += 1
                        self.network_queue.put(data)

                now = time.time()
                if (
                    self.network.is_connected()
                    and now - self.last_heartbeat >= self.heartbeat_interval
                ):
                    self.network.send_heartbeat()
                    self.last_heartbeat = now

                time.sleep(0.001)
            except Exception as e:
                print(f"[NETWORK] UDP thread error: {e}")
                time.sleep(0.5)

    def process_network_messages(self):
        try:
            while not self.network_queue.empty():
                data = self.network_queue.get_nowait()
                self.handle_server_message(data)
        except queue.Empty:
            pass

    # --------------------------------------------------------------
    #   Основной цикл
    # --------------------------------------------------------------
    def run(self):
        while self.running:
            self.handle_events()
            self.process_network_messages()
            self.update()
            self.render()
            self.clock.tick(self.fps)
            self.stats["fps"] = int(self.clock.get_fps())
        self.cleanup()
        pygame.quit()
        sys.exit()

    def cleanup(self):
        self.stop_network_thread = True
        if self.network_thread:
            self.network_thread.join(timeout=1.0)

        if self.network and self.network.is_connected():
            self.network.disconnect()

    # --------------------------------------------------------------
    #   Обработка событий
    # --------------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event)

            elif event.type == pygame.KEYUP:
                self.handle_keyup(event)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in (4, 5):
                    self.handle_mouse_wheel(event)   # старый способ прокрутки
                else:
                    self.handle_mouse_click(event)

            elif event.type == pygame.MOUSEWHEEL:
                self.handle_mouse_wheel(event)

            elif event.type == pygame.TEXTINPUT:
                self.handle_text_input(event.text)

    # --------------------------------------------------------------
    #   Клавиатура
    # --------------------------------------------------------------
    def handle_keydown(self, event):
        if event.key in self.keys:
            self.keys[event.key] = True

        # Навигация в селекторе персонажей
        if self.show_character_select:
            if event.key == pygame.K_LEFT:
                self.character_selector.prev_character()
            elif event.key == pygame.K_RIGHT:
                self.character_selector.next_character()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.confirm_character_selection()
            elif event.key == pygame.K_ESCAPE:
                self.show_character_select = False
                self.character_selector = None
                self.add_chat_message("[SYSTEM] Character selection canceled")
            return

        # Глобальные клавиши
        if event.key == pygame.K_ESCAPE:
            if self.show_settings_menu:
                self.close_settings()
            elif self.in_world and not self.chat_active and not self.show_character_select:
                self.toggle_esc_menu()
            elif self.show_esc_menu:
                self.toggle_esc_menu()
            elif self.chat_active:
                self.chat_active = False
                self.chat_input = ""

        elif event.key == pygame.K_F1:
            self.toggle_ui_visibility()

        elif event.key == pygame.K_RETURN:
            if self.chat_active:
                self.send_chat_message()
                self.chat_active = False
                self.chat_input = ""
            elif (
                self.active_input_field is not None
                and not self.show_esc_menu
                and not self.show_settings_menu
                and not self.show_character_select
            ):
                field = self.input_fields[self.active_input_field]
                if field["name"] == "username" and field["text"].strip():
                    self.login()
            elif (
                self.in_world
                and not self.show_esc_menu
                and not self.show_settings_menu
                and not self.show_character_select
            ):
                self.chat_active = True

        elif event.key == pygame.K_BACKSPACE:
            if self.chat_active:
                self.chat_input = self.chat_input[:-1]
            elif (
                self.active_input_field is not None
                and not self.show_esc_menu
                and not self.show_settings_menu
                and not self.show_character_select
            ):
                field = self.input_fields[self.active_input_field]
                field["text"] = field["text"][:-1]

        elif event.key == pygame.K_TAB and not self.show_esc_menu \
                and not self.show_settings_menu and not self.show_character_select:
            self.switch_input_field()

        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
            self.camera.zoom_in()
        elif event.key == pygame.K_MINUS:
            self.camera.zoom_out()

        # Тестовые клавиши анимаций собственного персонажа
        elif event.key == pygame.K_j and self.in_world and self.player_animation:
            self.set_player_animation("jump")
        elif event.key == pygame.K_k and self.in_world and self.player_animation:
            self.set_player_animation("attack")
        elif event.key == pygame.K_l and self.in_world and self.player_animation:
            self.set_player_animation("sleep")

    def handle_keyup(self, event):
        if event.key in self.keys:
            self.keys[event.key] = False

    # --------------------------------------------------------------
    #   Мышь
    # --------------------------------------------------------------
    def handle_mouse_click(self, event):
        # Если открыт селектор персонажей – делегируем событие
        if self.show_character_select and self.character_selector:
            result = self.character_selector.handle_click(event.pos)
            if result == "select":
                self.confirm_character_selection()
            elif result == "cancel":
                self.show_character_select = False
                self.character_selector = None
                self.add_chat_message("[SYSTEM] Character selection canceled")
            return

        # Меню настроек / ESC‑меню
        if self.show_settings_menu:
            self.handle_settings_menu_click(event)
            return
        if self.show_esc_menu:
            self.handle_esc_menu_click(event)
            return

        # Работа с UI‑панелями
        if event.button == 1 and self.side_panel_visible:
            mx, my = pygame.mouse.get_pos()
            # Поля ввода
            for i, field in enumerate(self.input_fields):
                if field.get("visible", True) and field["rect"].collidepoint((mx, my)):
                    self.active_input_field = i
                    field["active"] = True
                    break
            else:
                self.active_input_field = None
                for f in self.input_fields:
                    f["active"] = False

            # Кнопки меню
            for btn in self.menu_buttons:
                if btn["rect"].collidepoint((mx, my)) and btn.get("enabled", True):
                    btn["action"]()
                    break

    def handle_mouse_wheel(self, event):
        """Универсальный обработчик колесика (масштабирует камеру)."""
        if self.show_character_select and self.character_selector:
            self.character_selector.handle_mouse_wheel(event)
            return

        if hasattr(event, "y"):
            if event.y > 0:
                self.camera.zoom_in()
            elif event.y < 0:
                self.camera.zoom_out()
        elif hasattr(event, "button"):
            if event.button == 4:
                self.camera.zoom_in()
            elif event.button == 5:
                self.camera.zoom_out()

    def handle_esc_menu_click(self, event):
        if event.button != 1:
            return
        mx, my = pygame.mouse.get_pos()
        menu_w, menu_h = 400, 450
        menu_x = (self.width - menu_w) // 2
        menu_y = (self.height - menu_h) // 2
        btn_h, btn_sp = 55, 8
        start_y = menu_y + 120

        for i, btn in enumerate(self.esc_menu_buttons):
            rect = pygame.Rect(
                menu_x + 50,
                start_y + i * (btn_h + btn_sp),
                menu_w - 100,
                btn_h,
            )
            if rect.collidepoint((mx, my)):
                btn["action"]()
                break

    def handle_settings_menu_click(self, event):
        if event.button != 1:
            return
        mx, my = pygame.mouse.get_pos()
        w, h = 500, 500
        menu_x = (self.width - w) // 2
        menu_y = (self.height - h) // 2

        # Кнопки тем
        theme_start_y = menu_y + 120
        for i, btn in enumerate(self.theme_buttons):
            rect = pygame.Rect(
                menu_x + 50,
                theme_start_y + i * (45 + 10),
                w - 100,
                45,
            )
            if rect.collidepoint((mx, my)):
                btn["action"]()
                break

        # Кнопка «Назад»
        back_rect = pygame.Rect(
            menu_x + 50,
            menu_y + h - 70,
            w - 100,
            50,
        )
        if back_rect.collidepoint((mx, my)):
            self.close_settings()

    def handle_text_input(self, text):
        if self.chat_active:
            if len(self.chat_input) < 100:
                self.chat_input += text
        elif (
            self.active_input_field is not None
            and not self.show_esc_menu
            and not self.show_settings_menu
            and not self.show_character_select
        ):
            field = self.input_fields[self.active_input_field]
            if (
                len(field["text"]) < field.get("max_length", 50)
                and text not in ("\t", "\r", "\n")
            ):
                field["text"] += text

    def switch_input_field(self):
        visible = [i for i, f in enumerate(self.input_fields) if f.get("visible", True)]
        if not visible:
            return
        if self.active_input_field is None:
            self.active_input_field = visible[0]
        else:
            cur = visible.index(self.active_input_field) if self.active_input_field in visible else -1
            self.active_input_field = visible[(cur + 1) % len(visible)]

        for i, f in enumerate(self.input_fields):
            f["active"] = (i == self.active_input_field)

    # --------------------------------------------------------------
    #   Обновление логики
    # --------------------------------------------------------------
    def update(self):
        now = time.time()
        delta_time = now - self.last_update
        self.last_update = now

        # анимация селектора персонажей
        if self.show_character_select and self.character_selector:
            self.character_selector.update(delta_time)

        # анимация UI‑меню
        if self.show_esc_menu:
            self.menu_animation = min(
                self.menu_animation + delta_time / self.menu_animation_speed,
                1.0,
            )
        else:
            self.menu_animation = max(
                self.menu_animation - delta_time / self.menu_animation_speed,
                0.0,
            )

        if self.show_settings_menu:
            self.settings_animation = min(
                self.settings_animation + delta_time / self.menu_animation_speed,
                1.0,
            )
        else:
            self.settings_animation = max(
                self.settings_animation - delta_time / self.menu_animation_speed,
                0.0,
            )

        # авто‑скрытие боковой панели
        if self.in_world and self.side_panel_auto_hide:
            self.side_panel_animation = max(
                self.side_panel_animation - delta_time / 0.5, 0.0
            )
            if self.side_panel_animation <= 0:
                self.side_panel_visible = False
        else:
            self.side_panel_animation = min(
                self.side_panel_animation + delta_time / 0.5, 1.0
            )

        # движение собственного персонажа
        if (
            self.in_world
            and self.character
            and not self.chat_active
            and not self.show_esc_menu
            and not self.show_settings_menu
            and not self.show_character_select
        ):
            self.update_player_position(delta_time)

        # анимация собственного персонажа
        if self.in_world and self.player_animation:
            moving = any(
                [
                    self.keys[pygame.K_w],
                    self.keys[pygame.K_s],
                    self.keys[pygame.K_a],
                    self.keys[pygame.K_d],
                ]
            )

            if moving:
                if self.keys[pygame.K_a] or self.keys[pygame.K_LEFT]:
                    self.player_animation.set_direction("left")
                elif self.keys[pygame.K_d] or self.keys[pygame.K_RIGHT]:
                    self.player_animation.set_direction("right")

                if self.keys[pygame.K_LSHIFT]:
                    self.player_animation.set_animation("run")
                else:
                    self.player_animation.set_animation("walk")
            elif self.player_animation.current_animation not in ("jump", "attack", "sleep"):
                if self.player_animation.current_animation != "idle":
                    self.player_animation.set_animation("idle")

            self.player_animation.update()

        # камера
        if self.in_world and self.character and self.camera.follow_player:
            self.camera.update(
                self.character.get("position", {"x": 0, "y": 0, "z": 0}),
                delta_time,
            )
            self.stats["camera_x"] = int(self.camera.offset[0])
            self.stats["camera_y"] = int(self.camera.offset[1])

        # другие игроки
        for pl in self.other_players.values():
            pl.update(delta_time)
            if hasattr(pl, "animation") and pl.animation and pl.is_moving:
                pl.animation.update()

        # статус соединения UI
        self.update_connection_status()
        self.stats["players_online"] = len(self.other_players) + (1 if self.character else 0)
        self.update_join_world_button()

        # чат
        self.cleanup_old_chat_messages()
        self.update_overhead_messages(delta_time)
        self.update_message_heights()

        # время первого подключения
        if self.connected and self.stats["connection_time"] == 0:
            self.stats["connection_time"] = now

        # очистка старых кадров экрана
        if now - self.last_screen_update > 30 and self.screen_image:
            self.screen_image = None
            self.screen_frame_buffer.clear()
            self.screen_frame_chunks.clear()

    # --------------------------------------------------------------
    #   Движение собственного персонажа (WASD + Space/Shift)
    # --------------------------------------------------------------
    def update_player_position(self, delta_time: float):
        if not (
            self.in_world
            and self.character
            and not self.chat_active
            and not self.show_esc_menu
            and not self.show_settings_menu
            and not self.show_character_select
        ):
            return

        dx = dy = dz = 0.0
        speed = 2.0 * delta_time

        if self.keys[pygame.K_w] or self.keys[pygame.K_UP]:
            dy -= speed
        if self.keys[pygame.K_s] or self.keys[pygame.K_DOWN]:
            dy += speed
        if self.keys[pygame.K_a] or self.keys[pygame.K_LEFT]:
            dx -= speed
        if self.keys[pygame.K_d] or self.keys[pygame.K_RIGHT]:
            dx += speed
        if self.keys[pygame.K_SPACE]:
            dz += speed
        if self.keys[pygame.K_LSHIFT]:
            dz -= speed

        if self.player_animation:
            if dx < 0:
                self.player_animation.set_direction("left")
            elif dx > 0:
                self.player_animation.set_direction("right")

        if dx != 0 or dy != 0 or dz != 0:
            pos = self.character.get("position", {"x": 0, "y": 0, "z": 0})
            pos["x"] += dx
            pos["y"] += dy
            pos["z"] += dz

            # Сохраняем локальную копию (можно вынести в отдельный менеджер)
            from character_manager import CharacterManager

            cm = CharacterManager()
            self.character["position"] = pos
            cm.save_character(self.character)

            now = time.time()
            if now - self.last_position_update >= self.position_update_rate:
                self.send_position_update(pos)
                self.last_position_update = now

    # --------------------------------------------------------------
    #   Чат
    # --------------------------------------------------------------
    def cleanup_old_chat_messages(self):
        now = time.time()
        if not self.chat_active:
            self.chat_messages = [
                m
                for m in self.chat_messages
                if now - m["timestamp"] < self.chat_message_lifetime
            ]
        max_age = self.chat_message_lifetime + self.chat_message_fade_time
        self.chat_messages = [
            m for m in self.chat_messages if now - m["timestamp"] < max_age
        ]

    def update_overhead_messages(self, delta_time: float):
        now = time.time()
        self.overhead_messages = [
            msg for msg in self.overhead_messages if not msg.is_expired()
        ]

        for msg in self.overhead_messages:
            if self.character and msg.character_name == self.character["name"]:
                msg.update(self.character.get("position"), delta_time)
                continue

            # ищем игрока по имени
            for pid, player in self.other_players.items():
                pdata = self.other_players_data.get(pid, {})
                if pdata.get("name") == msg.character_name:
                    msg.update(player.get_position(), delta_time)
                    break
            else:
                msg.update(None, delta_time)

    def update_message_heights(self):
        msgs_by_char: Dict[str, List[ChatMessageOverhead]] = {}
        for msg in self.overhead_messages:
            msgs_by_char.setdefault(msg.character_name, []).append(msg)

        for msgs in msgs_by_char.values():
            msgs.sort(key=lambda m: m.start_time, reverse=True)
            for i, msg in enumerate(msgs):
                msg.set_height_offset(40 + i * 25)

    def add_chat_message(self, text: str, is_self: bool = False):
        self.chat_messages.append(
            {"text": text, "is_self": is_self, "timestamp": time.time()}
        )

    def send_chat_message(self):
        if not self.chat_input.strip() or not self.connected:
            return

        self.add_chat_message(f"You: {self.chat_input}", is_self=True)

        if self.character:
            overhead = ChatMessageOverhead(
                text=self.chat_input,
                character_name=self.character["name"],
                duration=10.0,
            )
            overhead.update(self.character.get("position"))
            self.overhead_messages.append(overhead)
            self.update_message_heights()

        data = {
            "type": "chat_message",
            "client_id": self.client_id,
            "character_id": self.character["id"] if self.character else None,
            "character_name": self.character["name"]
            if self.character
            else self.username,
            "character_type": self.character.get(
                "character_type", "default"
            )
            if self.character
            else "default",
            "text": self.chat_input,
            "timestamp": datetime.now().isoformat(),
            "is_overhead": True,
        }
        self.stats["udp_packets_sent"] += 1
        self.network.safe_send(data)

    # --------------------------------------------------------------
    #   Обработка сообщений от сервера
    # --------------------------------------------------------------
    def handle_server_message(self, data: dict):
        """Разбор сообщения от сервера."""
        msg_type = data.get("type")
        print(f"[DEBUG] Server message: {msg_type}")

        # Экранные кадры
        if msg_type == "screen_frame":
            self.handle_screen_frame(data)
            return

        if msg_type == "welcome":
            self.add_chat_message("[SYSTEM] Connected to UDP server")
        elif msg_type == "auth_response":
            if data.get("success"):
                self.add_chat_message("[SYSTEM] Authentication successful")
                self.character_selected = False
            else:
                self.add_chat_message(
                    f"[SYSTEM] Authentication error: {data.get('message', '')}"
                )
        elif msg_type == "character_select_response":
            if data.get("success"):
                self.character_selected = True
                self.add_chat_message("[SYSTEM] Character selected on server")
            else:
                self.add_chat_message(
                    f"[SYSTEM] Character select error: {data.get('message', '')}"
                )
        elif msg_type == "position_update":
            cid = data.get("character_id")
            if self.character and cid == self.character.get("id"):
                # собственный апдейт игнорируем – он уже отправлен клиентом
                return

            pos = data.get("position", {})
            ctype = data.get("character_type", "default")
            cname = data.get("character_name", "Unknown")

            # Попытка определить тип, если сервер его не прислал
            if ctype == "default" and cname:
                low = cname.lower()
                if "celestia" in low:
                    ctype = "Celestia"
                elif "luna" in low:
                    ctype = "Luna"
                elif "cadance" in low or "cadence" in low:
                    ctype = "Cadance"
                elif "twilight" in low:
                    ctype = "TwilightSparkle"

            if cid in self.other_players:
                self.other_players[cid].update_position(pos)
                self.other_players_data[cid]["position"] = pos
                self.other_players_data[cid]["timestamp"] = time.time()

                if ctype != self.other_players_data[cid].get(
                    "character_type", "default"
                ):
                    self.other_players_data[cid]["character_type"] = ctype
                    self.other_players[cid].init_animation(self.other_players_data[cid])
            else:
                pdata = {
                    "id": cid,
                    "name": cname,
                    "character_type": ctype,
                    "position": pos,
                    "timestamp": time.time(),
                }
                self.other_players[cid] = OtherPlayer(pdata)
                self.other_players_data[cid] = pdata
                print(f"[DEBUG] New player: {cname} ({ctype})")

        elif msg_type == "player_joined":
            pid = data.get("character_id") or data.get("player_id")
            pname = data.get("character_name", "Player")
            pos = data.get("position", {"x": 0, "y": 0, "z": 0})
            ctype = data.get("character_type", "default")

            if ctype == "default" and pname:
                low = pname.lower()
                if "celestia" in low:
                    ctype = "Celestia"
                elif "luna" in low:
                    ctype = "Luna"
                elif "cadance" in low or "cadence" in low:
                    ctype = "Cadance"
                elif "twilight" in low:
                    ctype = "TwilightSparkle"

            pdata = {
                "id": pid,
                "name": pname,
                "character_type": ctype,
                "position": pos,
                "timestamp": time.time(),
            }
            self.other_players[pid] = OtherPlayer(pdata)
            self.other_players_data[pid] = pdata
            self.add_chat_message(f"[SYSTEM] {pname} joined as {ctype}")

        elif msg_type == "player_left":
            pid = data.get("character_id") or data.get("player_id")
            pname = data.get("character_name", "Player")
            if pid in self.other_players:
                del self.other_players[pid]
            if pid in self.other_players_data:
                del self.other_players_data[pid]
            self.add_chat_message(f"[SYSTEM] {pname} left")

        elif msg_type == "world_joined":
            self.in_world = True
            self.game_state = GameState.IN_GAME
            self.world_data = data.get("world_info", {})

            self.other_players.clear()
            self.other_players_data.clear()
            for player in data.get("players", []):
                pid = player.get("id")
                if not pid:
                    continue
                ctype = player.get("character_type", "default")
                pname = player.get("name", "Player")
                if ctype == "default" and pname:
                    low = pname.lower()
                    if "celestia" in low:
                        ctype = "Celestia"
                    elif "luna" in low:
                        ctype = "Luna"
                    elif "cadance" in low or "cadence" in low:
                        ctype = "Cadance"
                    elif "twilight" in low:
                        ctype = "TwilightSparkle"

                pdata = {
                    "id": pid,
                    "name": pname,
                    "character_type": ctype,
                    "position": player.get("position", {"x": 0, "y": 0, "z": 0}),
                    "timestamp": time.time(),
                }
                self.other_players[pid] = OtherPlayer(pdata)
                self.other_players_data[pid] = pdata

            self.add_chat_message("[SYSTEM] Entered game world (UDP)!")
            self.update_join_world_button()
            if self.side_panel_auto_hide:
                self.side_panel_visible = False

        # <-- исправлен тип сообщения, теперь воспримется правильно
        elif msg_type in ("world_left", "world_leave"):
            self.in_world = False
            self.add_chat_message("[SYSTEM] Left game world")
            self.update_join_world_button()
            self.side_panel_visible = True

        elif msg_type == "chat_message":
            sender = data.get("character_name", "Unknown")
            txt = data.get("text", "")
            is_overhead = data.get("is_overhead", False)

            # Не дублируем сообщения от самого персонажа
            if self.character and sender == self.character["name"]:
                return

            if not is_overhead:
                self.add_chat_message(f"{sender}: {txt}")
            else:
                # Показ над головой (короткие сообщения)
                if len(txt) <= 3:
                    self.add_chat_message(f"{sender} [overhead]: {txt}")

                overhead = ChatMessageOverhead(txt, sender, duration=10.0)
                player = self.get_player_by_name(sender)
                if player:
                    overhead.update(player.get("position"))
                self.overhead_messages.append(overhead)
                self.update_message_heights()

        elif msg_type == "error":
            self.add_chat_message(f"[ERROR] {data.get('message', 'Error')}")

    # --------------------------------------------------------------
    #   Обработка кадров экрана сервера
    # --------------------------------------------------------------
    def handle_screen_frame(self, data: dict):
        """Собирает части кадра, декодирует и хранит как pygame.Surface."""
        frame_id = data.get("frame_id")
        chunk_index = data.get("chunk_index")
        total_chunks = data.get("total_chunks")
        chunk_data = data.get("data", "")

        if frame_id not in self.screen_frame_buffer:
            self.screen_frame_buffer[frame_id] = [""] * total_chunks
            self.screen_frame_chunks[frame_id] = 0

        if 0 <= chunk_index < total_chunks:
            self.screen_frame_buffer[frame_id][chunk_index] = chunk_data
            self.screen_frame_chunks[frame_id] += 1

        if self.screen_frame_chunks[frame_id] >= total_chunks:
            try:
                b64_data = "".join(self.screen_frame_buffer[frame_id])
                img_bytes = base64.b64decode(b64_data)
                img = Image.open(io.BytesIO(img_bytes))
                img_rgb = img.convert("RGB")
                img_bytes = img_rgb.tobytes()
                self.screen_image = pygame.image.fromstring(
                    img_bytes, img_rgb.size, "RGB"
                )
                self.stats["screen_frames_received"] += 1
                self.last_screen_update = time.time()
                del self.screen_frame_buffer[frame_id]
                del self.screen_frame_chunks[frame_id]
                print(
                    f"[SCREEN] Frame {frame_id} processed ({img.size[0]}x{img.size[1]})"
                )
            except Exception as e:
                print(f"[ERROR] Screen frame processing: {e}")

    # --------------------------------------------------------------
    #   Рендер
    # --------------------------------------------------------------
    def render(self):
        self.screen.fill(self.colors["black"])

        if self.in_world:
            self.render_game_world()

        if self.side_panel_visible and self.side_panel_animation > 0:
            self.render_side_panel()

        self.render_overhead_messages()

        if self.show_character_select and self.character_selector:
            self.character_selector.render(
                self.screen, self.colors, self.fonts
            )

        if self.chat_active:
            self.render_chat_input()
        elif self.chat_messages and (self.in_world or self.connected):
            self.render_chat_history()

        self.render_top_panel()

        if self.show_esc_menu or self.menu_animation > 0:
            self.render_esc_menu()

        if self.show_settings_menu or self.settings_animation > 0:
            self.render_settings_menu()

        pygame.display.flip()

    # --------------------------------------------------------------
    #   Игровой мир
    # --------------------------------------------------------------
    def render_game_world(self):
        # Вычисляем ширину области без скрытой боковой панели
        if self.side_panel_visible and self.side_panel_animation > 0:
            game_w = self.width - int(
                self.side_panel_width * self.side_panel_animation
            )
        else:
            game_w = self.width

        # -----------------------------------------------------------------
        #   Фоновое изображение (получено от сервера) с учётом зума
        # -----------------------------------------------------------------
        if self.screen_image:
            # Черный фон, если картинка не полная
            pygame.draw.rect(
                self.screen,
                (0, 0, 0),
                (0, self.top_panel_height, game_w, self.height - self.top_panel_height),
            )
            try:
                img_w, img_h = self.screen_image.get_size()
                scale = max(self.camera.zoom, 0.01)  # защита от 0

                # кешируем масштабированное изображение, чтобы не масштабировать каждый кадр
                if (
                    not hasattr(self, "_scaled_screen_image")
                    or self._scaled_image_zoom != self.camera.zoom
                ):
                    scaled_w = max(1, int(img_w * scale))
                    scaled_h = max(1, int(img_h * scale))
                    self._scaled_screen_image = pygame.transform.smoothscale(
                        self.screen_image, (scaled_w, scaled_h)
                    )
                    self._scaled_image_zoom = self.camera.zoom

                dest_x = int(self.camera.offset[0])
                dest_y = int(self.camera.offset[1])

                clip_rect = pygame.Rect(
                    0,
                    self.top_panel_height,
                    game_w,
                    self.height - self.top_panel_height,
                )
                self.screen.set_clip(clip_rect)
                self.screen.blit(self._scaled_screen_image, (dest_x, dest_y))
                self.screen.set_clip(None)
            except Exception as e:
                print(f"[ERROR] Rendering screen background with zoom: {e}")
                pygame.draw.rect(
                    self.screen,
                    self.colors["dark_grey"],
                    (0, self.top_panel_height, game_w, self.height - self.top_panel_height),
                )
        else:
            pygame.draw.rect(
                self.screen,
                self.colors["dark_grey"],
                (0, self.top_panel_height, game_w, self.height - self.top_panel_height),
            )

        # -------------------------------------------------
        #   Сетка (видна при небольшом зуме)
        # -------------------------------------------------
        if self.camera.zoom < 2.0:
            grid_color = tuple(min(c + 10, 255) for c in self.colors["dark_grey"])
            step = int(self.camera.grid_size * self.camera.zoom)

            start_x = -self.camera.offset[0] % step
            start_y = -self.camera.offset[1] % step

            for x in range(int(start_x), game_w, step):
                pygame.draw.line(
                    self.screen, grid_color, (x, self.top_panel_height), (x, self.height), 1
                )
            for y in range(int(start_y), self.height, step):
                pygame.draw.line(
                    self.screen, grid_color, (0, y), (game_w, y), 1
                )

        # -------------------------------------------------
        #   Другие игроки
        # -------------------------------------------------
        for pid, player in self.other_players.items():
            pos = player.get_position()
            sx, sy = self.camera.world_to_screen(pos)

            if 0 <= sx <= game_w and self.top_panel_height <= sy <= self.height:
                if player.animation:
                    try:
                        player.animation.draw(
                            self.screen, (sx, sy), scale=0.6 * self.camera.zoom
                        )
                    except Exception:
                        self._draw_player_stub(pid, player, sx, sy)
                else:
                    self._draw_player_stub(pid, player, sx, sy)

                # имя над головой
                pdata = self.other_players_data.get(pid, {"name": "Unknown"})
                name_surf = self.fonts["tiny"].render(pdata["name"], True, self.colors["white"])
                name_rect = name_surf.get_rect(center=(sx, sy - 35))
                self.screen.blit(name_surf, name_rect)

        # -------------------------------------------------
        #   Собственный персонаж
        # -------------------------------------------------
        if self.character:
            ppos = self.character.get("position", {"x": 0, "y": 0, "z": 0})
            sx, sy = self.camera.world_to_screen(ppos)

            if 0 <= sx <= game_w and self.top_panel_height <= sy <= self.height:
                if self.player_animation:
                    self.player_animation.draw(
                        self.screen, (sx, sy), scale=0.7 * self.camera.zoom
                    )
                else:
                    pygame.draw.circle(
                        self.screen,
                        self.colors["player"],
                        (sx, sy),
                        int(25 * self.camera.zoom),
                    )

                name_surf = self.fonts["small"].render(self.character["name"], True, self.colors["white"])
                name_rect = name_surf.get_rect(center=(sx, sy - 40))
                self.screen.blit(name_surf, name_rect)

        # -------------------------------------------------
        #   Информация о мире
        # -------------------------------------------------
        if self.world_data:
            wname = self.world_data.get("name", "Unknown World")
            txt = self.fonts["small"].render(
                f"World: {wname}", True, self.colors["accent_grey"]
            )
            self.screen.blit(txt, (10, self.top_panel_height + 10))

            cam_txt = self.fonts["tiny"].render(
                f"Camera: {'ON' if self.camera.follow_player else 'OFF'} | "
                f"Zoom: {self.camera.zoom:.1f}x",
                True,
                self.colors["light_grey"],
            )
            self.screen.blit(cam_txt, (10, self.top_panel_height + 35))

    def _draw_player_stub(self, pid: str, player: OtherPlayer, sx: int, sy: int):
        """Заглушка, если у игрока нет анимации."""
        color_map = {
            "Celestia": (255, 215, 0),
            "Luna": (138, 43, 226),
            "Cadance": (255, 182, 193),
            "TwilightSparkle": (147, 112, 219),
            "AppleJack": (255, 165, 0),
            "RainbowDash": (0, 191, 255),
            "Fluttershy": (255, 255, 0),
            "Rarity": (192, 192, 192),
            "PinkiePie": (255, 105, 180),
            "default": self.colors["other_player"],
        }
        col = color_map.get(player.character_type, color_map["default"])
        radius = int(20 * self.camera.zoom)
        pygame.draw.circle(self.screen, col, (sx, sy), radius)

        try:
            f = pygame.font.Font(None, int(16 * self.camera.zoom))
            txt = f.render(
                player.character_type[0] if player.character_type else "?",
                True,
                (255, 255, 255),
            )
            rect = txt.get_rect(center=(sx, sy))
            self.screen.blit(txt, rect)
        except Exception:
            pass

    # --------------------------------------------------------------
    #   Сообщения над головой
    # --------------------------------------------------------------
    def render_overhead_messages(self):
        msgs_by_char: Dict[str, List[ChatMessageOverhead]] = {}
        for msg in self.overhead_messages:
            msgs_by_char.setdefault(msg.character_name, []).append(msg)

        for char_name, msgs in msgs_by_char.items():
            msgs.sort(key=lambda m: m.start_time, reverse=True)

            # позиция персонажа
            if self.character and char_name == self.character["name"]:
                pos = self.character.get("position")
            else:
                pos = None
                for pid, player in self.other_players.items():
                    pdata = self.other_players_data.get(pid, {})
                    if pdata.get("name") == char_name:
                        pos = player.get_position()
                        break
                if pos is None:
                    continue

            screen_x, screen_y = self.camera.world_to_screen(pos)

            for i, msg in enumerate(msgs):
                if not (0 <= screen_x <= self.width and 0 <= screen_y <= self.height):
                    continue

                surf = self.fonts["medium"].render(msg.text, True, (255, 255, 255))
                if msg.alpha < 255:
                    surf.set_alpha(msg.alpha)

                txt_w, txt_h = surf.get_width(), surf.get_height()
                pad = 8
                bg_w, bg_h = txt_w + pad * 2, txt_h + pad // 2 * 2

                bg_x = screen_x - bg_w // 2
                bg_y = screen_y - 35 - i * 25 - bg_h // 2

                bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
                bg_alpha = int(180 * (msg.alpha / 255))
                pygame.draw.rect(
                    bg, (0, 0, 0, bg_alpha), (0, 0, bg_w, bg_h), border_radius=6
                )
                pygame.draw.rect(
                    bg,
                    (100, 100, 100, bg_alpha),
                    (0, 0, bg_w, bg_h),
                    width=1,
                    border_radius=6,
                )

                self.screen.blit(bg, (bg_x, bg_y))
                self.screen.blit(
                    surf, (screen_x - txt_w // 2, screen_y - 35 - i * 25 - txt_h // 2)
                )

    # --------------------------------------------------------------
    #   Боковая панель
    # --------------------------------------------------------------
    def render_side_panel(self):
        factor = self.side_panel_animation
        x = self.width - int(self.side_panel_width * factor)

        panel = pygame.Surface((self.side_panel_width, self.height), pygame.SRCALPHA)
        panel.fill((*self.colors["dark_grey"][:3], int(255 * factor)))
        pygame.draw.rect(panel, self.colors["grey"], (0, 0, 2, self.height))
        self.screen.blit(panel, (x, 0))

        alpha = int(255 * factor)

        title = self.fonts["large"].render("CONTROL PANEL", True, self.colors["white"])
        title.set_alpha(alpha)
        self.screen.blit(title, (x + 25, 40))

        sub = self.fonts["tiny"].render(
            "DPP2 - CAMERA SYSTEM", True, self.colors["accent_grey"]
        )
        sub.set_alpha(alpha)
        self.screen.blit(sub, (x + 25, 75))

        if factor > 0.9:
            # поля ввода
            for field in self.input_fields:
                if not field.get("visible", True):
                    continue
                field["rect"].x = x + 25

                label = self.fonts["tiny"].render(field["label"], True, self.colors["light_grey"])
                self.screen.blit(label, (field["rect"].x, field["rect"].y - 20))

                bg = self.colors["grey"] if not field["active"] else self.colors["light_grey"]
                pygame.draw.rect(self.screen, bg, field["rect"], border_radius=6)

                border = (
                    self.colors["accent_grey"]
                    if not field["active"]
                    else self.colors["grey"]
                )
                pygame.draw.rect(self.screen, border, field["rect"], 2, border_radius=6)

                txt = field["text"] if field["text"] else field.get("hint", "")
                col = self.colors["white"] if field["text"] else self.colors["accent_grey"]
                txt_surf = self.fonts["medium"].render(txt, True, col)

                max_w = field["rect"].width - 20
                if txt_surf.get_width() > max_w:
                    txt = "…" + txt[-(max_w // 10) :]
                    txt_surf = self.fonts["medium"].render(txt, True, col)

                txt_rect = txt_surf.get_rect(
                    midleft=(
                        field["rect"].x + 15,
                        field["rect"].y + field["rect"].height // 2,
                    )
                )
                self.screen.blit(txt_surf, txt_rect)

                if field["active"] and int(time.time() * 2) % 2 == 0:
                    cur_x = txt_rect.right + 2 if field["text"] else field["rect"].x + 15
                    cur = pygame.Rect(cur_x, field["rect"].y + 10, 2, field["rect"].height - 20)
                    pygame.draw.rect(self.screen, self.colors["white"], cur)

            # кнопки меню
            mouse = pygame.mouse.get_pos()
            for button in self.menu_buttons:
                button["rect"].x = x + 25
                hover = button["rect"].collidepoint(mouse)
                enabled = button.get("enabled", True)

                if not enabled:
                    bg = self.colors["grey"]
                    txt_col = self.colors["accent_grey"]
                    border = self.colors["grey"]
                elif hover:
                    bg = tuple(min(c + 20, 255) for c in self.colors["light_grey"])
                    txt_col = self.colors["white"]
                    border = self.colors["white"]
                else:
                    bg = self.colors["light_grey"]
                    txt_col = self.colors["white"]
                    border = self.colors["accent_grey"]

                pygame.draw.rect(self.screen, bg, button["rect"], border_radius=8)
                pygame.draw.rect(self.screen, border, button["rect"], 2, border_radius=8)

                ic = self.fonts["medium"].render(button["icon"], True, txt_col)
                self.screen.blit(ic, ic.get_rect(midleft=(button["rect"].x + 20, button["rect"].centery)))

                txt = self.fonts["medium"].render(button["text"], True, txt_col)
                self.screen.blit(txt, txt.get_rect(midleft=(button["rect"].x + 60, button["rect"].centery)))

    # --------------------------------------------------------------
    #   Верхняя панель
    # --------------------------------------------------------------
    def render_top_panel(self):
        pygame.draw.rect(self.screen, self.colors["dark_grey"], (0, 0, self.width, self.top_panel_height))
        pygame.draw.line(self.screen, self.colors["grey"], (0, self.top_panel_height), (self.width, self.top_panel_height), 2)

        # статус соединения
        status = "CONNECTED" if self.connected else "DISCONNECTED"
        col = self.colors["success"] if self.connected else self.colors["error"]
        pygame.draw.circle(self.screen, col, (25, 25), 6)
        pygame.draw.circle(self.screen, self.colors["white"], (25, 25), 6, 1)
        txt = self.fonts["small"].render(status, True, col)
        self.screen.blit(txt, (45, 20))

        # пользователь / персонаж
        info_x = 200
        if self.username:
            usr = self.fonts["tiny"].render(f"USER: {self.username}", True, self.colors["light_grey"])
            self.screen.blit(usr, (info_x, 20))

        if self.character:
            ctype = self.character.get("character_type", "default")
            ch = self.fonts["tiny"].render(
                f"CHAR: {self.character['name']} ({ctype})", True, self.colors["light_grey"]
            )
            self.screen.blit(ch, (info_x, 40))

        # статистика
        stats_x = self.width - 350
        fps = self.fonts["tiny"].render(f"FPS: {self.stats['fps']}", True, self.colors["light_grey"])
        self.screen.blit(fps, (stats_x, 20))

        pl = self.fonts["tiny"].render(
            f"PLAYERS: {self.stats['players_online']}", True, self.colors["light_grey"]
        )
        self.screen.blit(pl, (stats_x, 40))

    # --------------------------------------------------------------
    #   История чата
    # --------------------------------------------------------------
    def render_chat_history(self):
        if not self.chat_messages:
            return

        max_msg = 5
        start_x = 10
        start_y = self.height - 140
        now = time.time()

        visible = []
        for msg in reversed(self.chat_messages):
            age = now - msg["timestamp"]
            if self.chat_active or age < self.chat_message_lifetime:
                visible.append(msg)
            if len(visible) >= max_msg:
                break
        visible.reverse()

        for i, data in enumerate(visible):
            txt = data["text"]
            is_self = data.get("is_self", False)
            age = now - data["timestamp"]

            if txt.startswith("[SYSTEM]"):
                if "Connected" in txt or "successful" in txt or "Entered" in txt:
                    col = self.colors["success"]
                elif "error" in txt.lower() or "[ERROR]" in txt:
                    col = self.colors["error"]
                else:
                    col = self.colors["accent_grey"]
            elif is_self:
                col = tuple(min(c + 30, 255) for c in self.colors["player"])
            else:
                col = self.colors["white"]

            alpha = 255
            if not self.chat_active and age > self.chat_message_lifetime - self.chat_message_fade_time:
                fade = (age - (self.chat_message_lifetime - self.chat_message_fade_time)) / self.chat_message_fade_time
                alpha = int(255 * (1 - fade))

            t_surf = self.fonts["tiny"].render(txt, True, col)
            if alpha < 255:
                t_surf.set_alpha(alpha)

            bg = pygame.Rect(start_x - 5, start_y + i * 22 - 3,
                             t_surf.get_width() + 10, t_surf.get_height() + 6)
            bg_surf = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
            bg_surf.fill((*self.colors["dark_grey"][:3], min(200, alpha)))
            self.screen.blit(bg_surf, bg)
            self.screen.blit(t_surf, (start_x, start_y + i * 22))

    # --------------------------------------------------------------
    #   Поле ввода чата
    # --------------------------------------------------------------
    def render_chat_input(self):
        h = 40
        y = self.height - h - 10
        w = self.width - 20

        if self.chat_messages:
            max_msg = 10
            start_x = 10
            start_y = self.height - 140 - 30
            recent = self.chat_messages[-max_msg:]

            for i, data in enumerate(recent):
                txt = data["text"]
                is_self = data.get("is_self", False)

                if txt.startswith("[SYSTEM]"):
                    if "Connected" in txt or "successful" in txt or "Entered" in txt:
                        col = self.colors["success"]
                    elif "error" in txt.lower() or "[ERROR]" in txt:
                        col = self.colors["error"]
                    else:
                        col = self.colors["accent_grey"]
                elif is_self:
                    col = tuple(min(c + 30, 255) for c in self.colors["player"])
                else:
                    col = self.colors["white"]

                ts = self.fonts["tiny"].render(txt, True, col)
                bg = pygame.Rect(start_x - 5, start_y + i * 22 - 3,
                                 ts.get_width() + 10, ts.get_height() + 6)
                bg_s = pygame.Surface((bg.width, bg.height), pygame.SRCALPHA)
                bg_s.fill((*self.colors["dark_grey"][:3], 230))
                self.screen.blit(bg_s, bg)
                self.screen.blit(ts, (start_x, start_y + i * 22))

        pygame.draw.rect(self.screen, self.colors["dark_grey"], (10, y, w, h), border_radius=6)
        pygame.draw.rect(self.screen, self.colors["accent_grey"], (10, y, w, h), 2, border_radius=6)

        label = self.fonts["small"].render("CHAT:", True, self.colors["white"])
        self.screen.blit(label, (20, y + 10))

        disp = self.chat_input if self.chat_input else "Type your message..."
        col = self.colors["white"] if self.chat_input else self.colors["accent_grey"]
        txt = self.fonts["medium"].render(disp, True, col)

        max_w = w - 100
        if txt.get_width() > max_w:
            disp = "…" + disp[-(max_w // 10) :]
            txt = self.fonts["medium"].render(disp, True, col)

        self.screen.blit(txt, (80, y + 10))

        if int(time.time() * 2) % 2 == 0:
            cur_x = 80 + txt.get_width() + 2 if self.chat_input else 80
            cur = pygame.Rect(cur_x, y + 12, 2, h - 24)
            pygame.draw.rect(self.screen, self.colors["white"], cur)

        hint = self.fonts["tiny"].render(
            "Press ENTER to send, ESC to cancel", True, self.colors["accent_grey"]
        )
        self.screen.blit(hint, (w // 2 - hint.get_width() // 2, y - 20))

    # --------------------------------------------------------------
    #   ESC‑меню
    # --------------------------------------------------------------
    def render_esc_menu(self):
        factor = self.menu_animation
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(150 * factor)))
        self.screen.blit(overlay, (0, 0))

        menu_w, menu_h = 400, 450
        menu_x = (self.width - menu_w) // 2
        menu_y = (self.height - menu_h) // 2
        btn_h, btn_sp = 55, 8
        start_y = menu_y + 120

        bg = pygame.Rect(menu_x, menu_y, menu_w, menu_h)
        pygame.draw.rect(self.screen, self.colors["dark_grey"], bg, border_radius=12)
        pygame.draw.rect(self.screen, self.colors["accent_grey"], bg, 3, border_radius=12)

        title = self.fonts["large"].render("GAME MENU", True, self.colors["white"])
        title_rect = title.get_rect(center=(menu_x + menu_w // 2, menu_y + 50))
        self.screen.blit(title, title_rect)

        sub = self.fonts["tiny"].render("Press ESC to resume", True, self.colors["accent_grey"])
        sub_rect = sub.get_rect(center=(menu_x + menu_w // 2, menu_y + 85))
        self.screen.blit(sub, sub_rect)

        mouse = pygame.mouse.get_pos()
        for i, btn in enumerate(self.esc_menu_buttons):
            rect = pygame.Rect(
                menu_x + 50,
                start_y + i * (btn_h + btn_sp),
                menu_w - 100,
                btn_h,
            )
            hover = rect.collidepoint(mouse)

            bg_col = tuple(min(c + 20, 255) for c in self.colors["light_grey"]) if hover else self.colors["light_grey"]
            border = self.colors["white"] if hover else self.colors["accent_grey"]

            pygame.draw.rect(self.screen, bg_col, rect, border_radius=8)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=8)

            ic = self.fonts["medium"].render(btn["icon"], True, self.colors["white"])
            self.screen.blit(ic, ic.get_rect(midleft=(rect.x + 20, rect.centery)))

            txt = self.fonts["medium"].render(btn["text"], True, self.colors["white"])
            self.screen.blit(txt, txt.get_rect(midleft=(rect.x + 60, rect.centery)))

    # --------------------------------------------------------------
    #   Меню настроек
    # --------------------------------------------------------------
    def render_settings_menu(self):
        factor = self.settings_animation
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(150 * factor)))
        self.screen.blit(overlay, (0, 0))

        w, h = 500, 500
        menu_x = (self.width - w) // 2
        menu_y = (self.height - h) // 2
        ay = menu_y - (1 - factor) * 50

        bg = pygame.Rect(menu_x, ay, w, h)
        pygame.draw.rect(self.screen, self.colors["dark_grey"], bg, border_radius=12)
        pygame.draw.rect(self.screen, self.colors["accent_grey"], bg, 3, border_radius=12)

        title = self.fonts["large"].render("SETTINGS", True, self.colors["white"])
        title_rect = title.get_rect(center=(menu_x + w // 2, ay + 50))
        self.screen.blit(title, title_rect)

        sub = self.fonts["tiny"].render("Color Schemes", True, self.colors["accent_grey"])
        sub_rect = sub.get_rect(center=(menu_x + w // 2, ay + 85))
        self.screen.blit(sub, sub_rect)

        mouse = pygame.mouse.get_pos()
        theme_start_y = ay + 120
        for i, btn in enumerate(self.theme_buttons):
            rect = pygame.Rect(
                menu_x + 50,
                theme_start_y + i * (45 + 10),
                w - 100,
                45,
            )
            hover = rect.collidepoint(mouse)
            selected = btn.get("selected", False)

            if selected:
                bg_col = self.colors["player"]
                border = self.colors["white"]
                txt_col = self.colors["white"]
            elif hover:
                bg_col = tuple(min(c + 20, 255) for c in self.colors["light_grey"])
                border = self.colors["white"]
                txt_col = self.colors["white"]
            else:
                bg_col = self.colors["light_grey"]
                border = self.colors["accent_grey"]
                txt_col = self.colors["white"]

            pygame.draw.rect(self.screen, bg_col, rect, border_radius=8)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=8)

            ic = self.fonts["medium"].render(btn["icon"], True, txt_col)
            self.screen.blit(ic, ic.get_rect(midleft=(rect.x + 20, rect.centery)))

            txt = self.fonts["medium"].render(btn["text"], True, txt_col)
            self.screen.blit(txt, txt.get_rect(midleft=(rect.x + 60, rect.centery)))

            if selected:
                chk = self.fonts["medium"].render("✓", True, self.colors["white"])
                self.screen.blit(chk, chk.get_rect(midright=(rect.right - 20, rect.centery)))

        # Кнопка «Назад»
        back_rect = pygame.Rect(
            menu_x + 50,
            ay + h - 70,
            w - 100,
            50,
        )
        hover = back_rect.collidepoint(mouse)
        bg_col = tuple(min(c + 20, 255) for c in self.colors["light_grey"]) if hover else self.colors["light_grey"]
        border = self.colors["white"] if hover else self.colors["accent_grey"]
        pygame.draw.rect(self.screen, bg_col, back_rect, border_radius=8)
        pygame.draw.rect(self.screen, border, back_rect, 2, border_radius=8)

        txt = self.fonts["medium"].render("BACK TO MENU", True, self.colors["white"])
        self.screen.blit(txt, txt.get_rect(center=back_rect.center))

    # --------------------------------------------------------------
    #   UI‑управление (открытие/закрытие меню, переключение UI)
    # --------------------------------------------------------------
    def toggle_esc_menu(self):
        if self.show_settings_menu:
            self.close_settings()
        else:
            self.show_esc_menu = not self.show_esc_menu
            print(f"[UI] ESC menu {'opened' if self.show_esc_menu else 'closed'}")

    def resume_game(self):
        self.show_esc_menu = False
        print("[UI] Resuming game...")

    def open_settings(self):
        self.show_settings_menu = True
        self.show_esc_menu = False
        print("[UI] Opening settings...")

    def close_settings(self):
        self.show_settings_menu = False
        print("[UI] Closing settings...")

    def toggle_ui_visibility(self):
        self.side_panel_visible = not self.side_panel_visible
        state = "shown" if self.side_panel_visible else "hidden"
        print(f"[UI] Side panel {state}")

    def change_theme(self, theme_name):
        self.current_theme = theme_name
        self.config.set("ui.theme", theme_name)
        self.config.save()
        self.load_color_scheme()
        for btn in self.theme_buttons:
            btn["selected"] = (btn["theme_key"] == theme_name)
        print(f"[UI] Theme changed to {theme_name}")

    # --------------------------------------------------------------
    #   Сетевые операции
    # --------------------------------------------------------------
    def disconnect_from_server(self):
        if self.network and self.network.is_connected():
            self.network.disconnect()
        self.connected = False
        self.in_world = False
        self.show_esc_menu = False
        self.show_settings_menu = False
        self.side_panel_visible = True
        self.add_chat_message("[SYSTEM] Disconnected from server")
        print("[NETWORK] Disconnected")

    def connect_to_server(self):
        if self.connection_in_progress:
            return

        host = next(f for f in self.input_fields if f["name"] == "server_host")["text"]
        port = next(f for f in self.input_fields if f["name"] == "server_port")["text"]

        self.connection_in_progress = True
        self.add_chat_message(f"[SYSTEM] Connecting to {host}:{port}...")

        try:
            if self.network.is_connected():
                self.network.disconnect()
                time.sleep(0.1)

            from network_client import NetworkClient

            self.network = NetworkClient(host, int(port))
            self.network.client_id = self.client_id

            if self.network.connect():
                self.connected = True
                self.add_chat_message(f"[SYSTEM] Connected to {host}:{port}")

                init = {
                    "type": "client_init",
                    "client_id": self.client_id,
                    "timestamp": datetime.now().isoformat(),
                }
                self.network.safe_send(init)

                self.start_network_thread()
                self.show_login_field()
            else:
                self.connected = False
                self.add_chat_message("[ERROR] Connection failed")
        except ValueError:
            self.add_chat_message("[ERROR] Invalid port")
        except Exception as e:
            self.add_chat_message(f"[ERROR] {e}")
        finally:
            self.connection_in_progress = False

    def show_login_field(self):
        for field in self.input_fields:
            if field["name"] == "username":
                field["visible"] = True
                field["active"] = True
                self.active_input_field = self.input_fields.index(field)
                break

    def login(self):
        username = next(f for f in self.input_fields if f["name"] == "username")["text"].strip()
        if not username:
            self.add_chat_message("[ERROR] Enter username")
            return
        if not self.connected:
            self.add_chat_message("[ERROR] Not connected")
            return

        self.username = username
        self.add_chat_message(f"[SYSTEM] Logging in as {self.username}...")

        data = {
            "type": "auth",
            "client_id": self.client_id,
            "username": self.username,
            "timestamp": datetime.now().isoformat(),
        }
        self.network.safe_send(data)

    def select_character(self):
        if not self.username:
            self.add_chat_message("[ERROR] Login first")
            return

        self.show_character_select = True
        self.character_selector = SimpleCharacterSelector(self.width, self.height)
        self.character_selector.load_characters()
        self.add_chat_message("[SYSTEM] Opening character selection...")
        print("[UI] Character selection opened")

    def confirm_character_selection(self):
        if not self.character_selector:
            return
        sel = self.character_selector.get_selected_character()
        if not sel:
            self.add_chat_message("[ERROR] No character selected")
            return

        self.show_character_select = False
        self.character_selector = None

        from character_manager import CharacterManager

        cm = CharacterManager()
        char_name = f"{self.username}_{sel['id']}"
        self.character = cm.create_default_character(char_name, self.username)
        self.character["character_type"] = sel["id"]
        self.character["assets_path"] = sel["folder"]
        cm.save_character(self.character)

        self.add_chat_message(f"[SYSTEM] Selected: {sel['name']}")

        self.player_animation = AnimatedCharacter(self.character)
        if self.player_animation.load_animations():
            self.player_animation.set_animation("idle")
            print(f"[DEBUG] Animation loaded for {sel['id']}")
        else:
            print(f"[DEBUG] No animation for {sel['id']} – using stub")

        if self.connected:
            data = {
                "type": "character_select",
                "client_id": self.client_id,
                "character_id": self.character["id"],
                "character_data": self.character,
                "character_type": sel["id"],
                "timestamp": datetime.now().isoformat(),
            }
            self.network.safe_send(data)

        self.character_selected = True
        self.game_state = GameState.IN_GAME
        self.update_join_world_button()
        self.add_chat_message("[SYSTEM] Character ready. Click 'ENTER WORLD'")

    def test_animations(self):
        """Вывести в консоль текущие анимации и перезагрузить их."""
        print("\n=== TEST ANIMATIONS ===")
        if self.character:
            print(
                f"  My character : {self.character.get('name')} (type={self.character.get('character_type')})"
            )
        else:
            print("  My character : НЕ ВЫБРАН")
        print(f"  My animation : {'Есть' if self.player_animation else 'Нет'}")
        print(f"\n  Other players: {len(self.other_players)}")
        for pid, pl in self.other_players.items():
            has_anim = hasattr(pl, "animation") and pl.animation is not None
            print(f"    {pl.name}: type={pl.character_type}, animation={'Есть' if has_anim else 'Нет'}")

        self.reload_all_animations()
        self.add_chat_message("[TEST] Animations reloaded")

    def reload_all_animations(self):
        """Перезагружаем анимации всех игроков, включая собственного."""
        print("[DEBUG] Reloading all animations")
        if self.character and self.player_animation:
            self.player_animation.load_animations()
        for pid, pl in self.other_players.items():
            pdata = self.other_players_data.get(pid, {})
            if hasattr(pl, "init_animation"):
                pl.init_animation(pdata)

    def set_player_animation(self, anim_name: str) -> bool:
        if self.player_animation:
            return self.player_animation.set_animation(anim_name)
        return False

    def join_world(self):
        if not self.character:
            self.add_chat_message("[ERROR] Select character first")
            return
        if not self.connected:
            self.add_chat_message("[ERROR] Not connected")
            return
        if self.in_world:
            self.add_chat_message("[ERROR] Already in world")
            return

        self.add_chat_message(f"[SYSTEM] Entering world with {self.character['name']}...")
        data = {
            "type": "join_world",
            "client_id": self.client_id,
            "character_id": self.character["id"],
            "character_name": self.character["name"],
            "character_type": self.character.get("character_type", "default"),
            "character_data": self.character,
            "timestamp": datetime.now().isoformat(),
        }
        self.network.safe_send(data)

    def quit_game(self):
        if self.in_world and self.connected and self.character:
            try:
                data = {
                    "type": "leave_world",
                    "client_id": self.client_id,
                    "character_id": self.character["id"],
                    "character_name": self.character["name"],
                    "timestamp": datetime.now().isoformat(),
                }
                self.network.safe_send(data)
            except Exception:
                pass
        self.running = False

    # --------------------------------------------------------------
    #   Обновление статуса UI‑кнопок
    # --------------------------------------------------------------
    def update_connection_status(self):
        self.connected = self.network.is_connected()
        for btn in self.menu_buttons:
            if btn["id"] == "login":
                btn["enabled"] = self.connected
            elif btn["id"] == "character":
                btn["enabled"] = bool(self.username)
            elif btn["id"] == "join_world":
                btn["enabled"] = (
                    self.connected
                    and self.username
                    and self.character
                    and not self.in_world
                )

    def update_join_world_button(self):
        for btn in self.menu_buttons:
            if btn["id"] == "join_world":
                btn["enabled"] = (
                    self.connected
                    and self.username
                    and self.character
                    and not self.in_world
                )
                break

    # --------------------------------------------------------------
    #   Отправка позиции персонажа на сервер
    # --------------------------------------------------------------
    def send_position_update(self, position: dict):
        if not self.connected or not self.character:
            return
        data = {
            "type": "position_update",
            "client_id": self.client_id,
            "character_id": self.character["id"],
            "character_name": self.character["name"],
            "character_type": self.character.get("character_type", "default"),
            "position": position,
            "timestamp": datetime.now().isoformat(),
        }
        self.stats["udp_packets_sent"] += 1
        self.network.safe_send(data)


# ----------------------------------------------------------------------
#   Точка входа
# ----------------------------------------------------------------------
def main():
    print("=" * 50)
    print("DPP2 Graphic Client – Camera Follow System with Screen Streaming")
    print("=" * 50)

    try:
        app = DPP2GraphicClient()
        app.run()
    except Exception as exc:
        print(f"[FATAL] Startup error: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()