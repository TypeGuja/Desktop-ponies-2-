#!/usr/bin/env python3
"""
AnimatedCharacter и CharacterSelector – анимации персонажей и меню выбора.
"""

# ----------------------------------------------------------------------
# stdlib imports
# ----------------------------------------------------------------------
import json
import os

# ----------------------------------------------------------------------
# third‑party imports
# ----------------------------------------------------------------------
import pygame
from PIL import Image, ImageSequence  # для работы с GIF‑файлами


# ----------------------------------------------------------------------
# AnimatedCharacter
# ----------------------------------------------------------------------
class AnimatedCharacter:
    """Управление анимированным персонажем (поддержка GIF)."""

    def __init__(self, character_data: dict, assets_path: str = "assets/characters"):
        self.character_data = character_data
        self.assets_path = assets_path
        self.animations: dict = {}
        self.current_animation = "idle"
        self.current_direction = "right"
        self.current_frame = 0
        self.animation_speed = 0.1
        self.last_update = pygame.time.get_ticks()
        self.loaded = False
        self.scale = 1.0

    # ------------------------------------------------------------------
    # GIF handling
    # ------------------------------------------------------------------
    def load_gif_frames(self, gif_path: str) -> tuple[list[pygame.Surface], list[int]]:
        """Загрузить все кадры из GIF‑файла."""
        try:
            frames = []
            durations = []
            with Image.open(gif_path) as img:
                for frame in ImageSequence.Iterator(img):
                    durations.append(frame.info.get("duration", 100))
                    if frame.mode != "RGBA":
                        frame = frame.convert("RGBA")
                    data = frame.tobytes()
                    surf = pygame.image.fromstring(
                        data, frame.size, "RGBA"
                    ).convert_alpha()
                    frames.append(surf)
            return frames, durations
        except Exception as exc:  # pragma: no cover
            print(f"[ERROR] Не удалось загрузить GIF {gif_path}: {exc}")
            return [], []

    # ------------------------------------------------------------------
    # Loading animation configuration
    # ------------------------------------------------------------------
    def load_animations(self) -> bool:
        """Загрузить анимации персонажа из config‑файлов или автодетектировать GIF‑файлы."""
        char_type = self.character_data.get(
            "character_type", self.character_data.get("name", "default")
        )
        folder = os.path.join(self.assets_path, char_type)

        if not os.path.isdir(folder):
            return False

        # Пытаемся открыть JSON‑конфиги
        config_files = [
            os.path.join(folder, "animations.json"),
            os.path.join(folder, f"{char_type}.json"),
        ]
        animation_cfg = {}

        for cfg_path in config_files:
            if os.path.isfile(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Вариант «name + animations» либо чистый dict
                    if "animations" in data:
                        animation_cfg = data["animations"]
                    else:
                        animation_cfg = data
                    break
                except Exception:
                    continue

        # Если конфиг не найден – автодетектируем GIF‑файлы
        if not animation_cfg:
            animation_cfg = self.auto_detect_gifs(folder)

        # Если всё‑равно ничего – создаём базовый конфиг
        if not animation_cfg:
            animation_cfg = self.create_default_config(folder)

        # Теперь формируем структуру анимаций
        for anim_name, cfg in animation_cfg.items():
            speed = cfg.get("speed", 0.1)
            self.animations[anim_name] = {
                "speed": speed,
                "loop": cfg.get("loop", True),
                "directions": cfg.get("directions", ["right"]),
                "direction_frames": {},
                "direction_durations": {},
            }

            for direction in self.animations[anim_name]["directions"]:
                # Пытаемся найти подходящий GIF
                gif_path = None
                possible = [
                    os.path.join(folder, cfg.get(f"{direction}_file", "")),
                    os.path.join(folder, f"{anim_name}_{direction}.gif"),
                    os.path.join(folder, f"{anim_name}.gif"),
                ]
                for p in possible:
                    if p and os.path.isfile(p):
                        gif_path = p
                        break

                frames, durations = ([], [])
                if gif_path:
                    frames, durations = self.load_gif_frames(gif_path)

                if not frames:
                    # placeholder
                    frames = [self.create_placeholder_frame(char_type, anim_name, direction)]
                    durations = [100]

                self.animations[anim_name]["direction_frames"][direction] = frames
                self.animations[anim_name]["direction_durations"][direction] = durations

        self.loaded = len(self.animations) > 0
        return self.loaded

    # ------------------------------------------------------------------
    # Automatic GIF detection
    # ------------------------------------------------------------------
    def auto_detect_gifs(self, character_folder: str) -> dict:
        """Собрать конфиг из найденных GIF‑файлов."""
        cfg = {}
        for filename in os.listdir(character_folder):
            if not filename.endswith(".gif"):
                continue
            name = filename[:-4]  # без расширения
            parts = name.split("_")
            if len(parts) >= 2 and parts[-1] in ("left", "right", "up", "down"):
                direction = parts[-1]
                anim_name = "_".join(parts[:-1])
                cfg.setdefault(anim_name, {"directions": [direction], f"{direction}_file": filename, "speed": 0.1, "loop": True})
                if direction not in cfg[anim_name]["directions"]:
                    cfg[anim_name]["directions"].append(direction)
            else:
                cfg.setdefault(name, {"directions": ["right"], "file": filename, "speed": 0.1, "loop": True})
        return cfg

    # ------------------------------------------------------------------
    # Default config (fallback)
    # ------------------------------------------------------------------
    def create_default_config(self, character_folder: str) -> dict:
        """Создать набор анимаций по умолчанию."""
        cfg = {}
        common = ["idle", "walk", "run", "attack", "jump"]
        dirs = ["left", "right", "up", "down"]
        for anim in common:
            found = []
            for d in dirs:
                candidates = [
                    f"{anim}_{d}.gif",
                    f"{anim}_{d}_1.gif",
                    f"{d}_{anim}.gif",
                ]
                for fname in candidates:
                    fp = os.path.join(character_folder, fname)
                    if os.path.isfile(fp):
                        found.append((d, fname))
                        break
            if found:
                cfg[anim] = {
                    "directions": [d for d, _ in found],
                    "speed": 0.1,
                    "loop": True,
                }
                for d, f in found:
                    cfg[anim][f"{d}_file"] = f
        return cfg

    # ------------------------------------------------------------------
    # Placeholder frame (когда GIF отсутствует)
    # ------------------------------------------------------------------
    def create_placeholder_frame(self, character_type: str, animation_name: str, direction: str) -> pygame.Surface:
        """Сгенерировать простую заглушку‑картинку."""
        frame = pygame.Surface((64, 64), pygame.SRCALPHA)
        colour_map = {
            "Cadance": (255, 182, 193),
            "Celestia": (255, 215, 0),
            "Luna": (138, 43, 226),
        }
        colour = colour_map.get(character_type, (150, 150, 150))
        pygame.draw.rect(frame, (*colour, 150), (0, 0, 64, 64), border_radius=10)

        # простая стрелка указывает направление
        if direction == "left":
            pts = [(20, 32), (44, 20), (44, 44)]
        elif direction == "right":
            pts = [(44, 32), (20, 20), (20, 44)]
        elif direction == "up":
            pts = [(32, 20), (20, 44), (44, 44)]
        else:  # down
            pts = [(32, 44), (20, 20), (44, 20)]
        pygame.draw.polygon(frame, (*colour, 200), pts)

        # первая буква типа
        try:
            font = pygame.font.Font(None, 12)
            txt = font.render(character_type[:3], True, (255, 255, 255))
            rect = txt.get_rect(center=(32, 32))
            frame.blit(txt, rect)
        except Exception:
            pass

        return frame

    # ------------------------------------------------------------------
    # Animation control
    # ------------------------------------------------------------------
    def set_animation(self, animation_name: str, direction: str | None = None) -> bool:
        """Сменить текущую анимацию (и, опционально, направление)."""
        if animation_name in self.animations:
            if animation_name != self.current_animation:
                self.current_animation = animation_name
                self.current_frame = 0
                self.last_update = pygame.time.get_ticks()

            if direction:
                if direction in self.animations[animation_name]["directions"]:
                    if direction != self.current_direction:
                        self.current_direction = direction
                        self.current_frame = 0
                        self.last_update = pygame.time.get_ticks()
                else:
                    # Попытка подобрать аналогичное направление (лево/право ↔ прав/лево)
                    alt = None
                    if direction in ("left", "right"):
                        alt = "right" if direction == "left" else "left"
                    else:
                        alt = "down" if direction == "up" else "up"
                    if alt in self.animations[animation_name]["directions"]:
                        self.current_direction = alt
                        self.current_frame = 0
                        self.last_update = pygame.time.get_ticks()
            return True

        # Если анимаций нет – просто запомнить значения
        if not self.animations:
            self.current_animation = animation_name
            if direction:
                self.current_direction = direction
            return True

        # Попытка подобрать близкую анимацию по частичному совпадению имени
        for name in self.animations:
            if animation_name in name or name in animation_name:
                self.current_animation = name
                self.current_frame = 0
                self.last_update = pygame.time.get_ticks()
                if direction:
                    self.set_direction(direction)
                return True

        return False

    def set_direction(self, direction: str) -> bool:
        """Сменить направление текущей анимации."""
        if self.current_animation in self.animations:
            dirs = self.animations[self.current_animation]["directions"]
            if direction in dirs:
                if direction != self.current_direction:
                    self.current_direction = direction
                    self.current_frame = 0
                    self.last_update = pygame.time.get_ticks()
                return True
            # Попытка подобрать альтернативу
            if direction in ("left", "right"):
                alt = "right" if direction == "left" else "left"
                if alt in dirs:
                    self.current_direction = alt
                    self.current_frame = 0
                    self.last_update = pygame.time.get_ticks()
                    return True
            elif direction in ("up", "down"):
                alt = "down" if direction == "up" else "up"
                if alt in dirs:
                    self.current_direction = alt
                    self.current_frame = 0
                    self.last_update = pygame.time.get_ticks()
                    return True
        return False

    # ------------------------------------------------------------------
    # Update (frame timing)
    # ------------------------------------------------------------------
    def update(self) -> None:
        """Обновить анимацию (перейти к следующему кадру)."""
        if not self.loaded:
            return

        anim = self.animations.get(self.current_animation)
        if not anim:
            return

        now = pygame.time.get_ticks()
        frames = anim["direction_frames"].get(self.current_direction, [])
        durations = anim["direction_durations"].get(self.current_direction, [])

        # При отсутствии кадров в текущем направлении переключаемся на альтернативное
        if not frames or not durations:
            if self.current_direction in ("left", "right"):
                alt = "right" if self.current_direction == "left" else "left"
            else:
                alt = "down" if self.current_direction == "up" else "up"
            frames = anim["direction_frames"].get(alt, [])
            durations = anim["direction_durations"].get(alt, [])
            if frames and durations:
                self.current_direction = alt

        if not frames or not durations:
            return

        frame_dur = durations[self.current_frame] if self.current_frame < len(durations) else 100
        if now - self.last_update > frame_dur:
            self.last_update = now
            self.current_frame += 1
            if self.current_frame >= len(frames):
                if anim["loop"]:
                    self.current_frame = 0
                else:
                    self.current_frame = len(frames) - 1
                    if self.current_animation in ("jump", "attack"):
                        self.set_animation("idle")

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def get_current_frame(self) -> pygame.Surface:
        """Вернуть текущий кадр анимации (или заглушку)."""
        if not self.loaded:
            return self.create_placeholder_frame(
                self.character_data.get("character_type", "default"),
                self.current_animation,
                self.current_direction,
            )

        anim = self.animations.get(self.current_animation)
        if not anim:
            return self.create_placeholder_frame(
                self.character_data.get("character_type", "default"),
                self.current_animation,
                self.current_direction,
            )

        frames = anim["direction_frames"].get(self.current_direction)
        if not frames:
            # fallback to opposite direction
            if self.current_direction in ("left", "right"):
                alt = "right" if self.current_direction == "left" else "left"
            else:
                alt = "down" if self.current_direction == "up" else "up"
            frames = anim["direction_frames"].get(alt, [])
            if frames:
                self.current_direction = alt

        if not frames or self.current_frame >= len(frames):
            return self.create_placeholder_frame(
                self.character_data.get("character_type", "default"),
                self.current_animation,
                self.current_direction,
            )

        return frames[self.current_frame]

    def draw(self, surface, position: tuple[int, int], scale: float = 1.0) -> None:
        """Отрисовать персонажа на экране."""
        frame = self.get_current_frame()
        if frame:
            scaled = pygame.transform.scale(
                frame,
                (int(frame.get_width() * scale), int(frame.get_height() * scale)),
            )
            surface.blit(
                scaled,
                (
                    position[0] - scaled.get_width() // 2,
                    position[1] - scaled.get_height() // 2,
                ),
            )

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def get_size(self, scale: float = 1.0) -> tuple[int, int]:
        """Размер текущего кадра (массивный кортеж)."""
        frame = self.get_current_frame()
        if frame:
            return (
                int(frame.get_width() * scale),
                int(frame.get_height() * scale),
            )
        return (0, 0)

    def get_animation_names(self) -> list[str]:
        """Список имён доступных анимаций."""
        return list(self.animations.keys())

    def get_directions_for_animation(self, animation_name: str) -> list[str]:
        """Список направлений, поддерживаемых указанной анимацией."""
        return (
            self.animations[animation_name]["directions"]
            if animation_name in self.animations
            else []
        )

    def has_animation_direction(self, animation_name: str, direction: str) -> bool:
        """Проверка, существует ли анимация в заданном направлении."""
        if animation_name not in self.animations:
            return False
        dirs = self.animations[animation_name]["directions"]
        if direction in dirs:
            return True
        # некоторые анимации используют только left/right или up/down
        if direction == "left" and "right" in dirs:
            return True
        if direction == "right" and "left" in dirs:
            return True
        if direction == "up" and "down" in dirs:
            return True
        if direction == "down" and "up" in dirs:
            return True
        return False


# ----------------------------------------------------------------------
# CharacterSelector – меню выбора персонажа
# ----------------------------------------------------------------------
class CharacterSelector:
    """Меню выбора персонажа – список с анимированными превью."""

    def __init__(self, screen_width: int, screen_height: int, assets_path: str = "assets/characters"):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.assets_path = assets_path
        self.available_characters: list[dict] = []
        self.characters: list[AnimatedCharacter] = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.items_per_page = 6
        self.item_height = 100
        self.load_characters()

    # ------------------------------------------------------------------
    # Loading characters
    # ------------------------------------------------------------------
    def load_characters(self) -> None:
        """Собрать список доступных персонажей из asset‑каталога."""
        self.available_characters.clear()
        self.characters.clear()
        self.selected_index = 0
        self.scroll_offset = 0

        order = [
            "Celestia",
            "Luna",
            "Cadance",
            "TwilightSparkle",
            "AppleJack",
            "RainbowDash",
            "Fluttershy",
            "Rarity",
            "PinkiePie",
            "Trixie",
            "SunsetShimmer",
            "StarlightGlimmer",
        ]

        loaded_chars = {}
        loaded_anims = {}

        for name in order:
            folder = os.path.join(self.assets_path, name)
            if not os.path.isdir(folder):
                continue

            has_gif = any(f.endswith(".gif") for f in os.listdir(folder))
            if not has_gif:
                continue

            data = {
                "id": name,
                "name": name.replace("_", " ").title(),
                "folder": folder,
                "character_type": name,
                "description": f"Персонаж типа {name}",
            }
            loaded_chars[name] = data
            anim = AnimatedCharacter(data, self.assets_path)
            if anim.load_animations():
                loaded_anims[name] = anim

        for name in order:
            if name in loaded_chars and name in loaded_anims:
                self.available_characters.append(loaded_chars[name])
                self.characters.append(loaded_anims[name])

        if not self.available_characters:
            self.create_demo_characters()

    # ------------------------------------------------------------------
    # Демо‑персонажи (если ничего не найдено)
    # ------------------------------------------------------------------
    def create_demo_characters(self) -> None:
        """Создать несколько простых демо‑персонажей."""
        demo = ["Cadance", "Celestia", "Luna"]
        for name in demo:
            folder = os.path.join(self.assets_path, name)
            os.makedirs(folder, exist_ok=True)

            config = {
                "idle": {
                    "directions": ["left", "right"],
                    "left_file": "idle_left.gif",
                    "right_file": "idle_right.gif",
                    "speed": 0.2,
                    "loop": True,
                },
                "walk": {
                    "directions": ["left", "right"],
                    "left_file": "walk_left.gif",
                    "right_file": "walk_right.gif",
                    "speed": 0.15,
                    "loop": True,
                },
            }
            try:
                with open(os.path.join(folder, "animations.json"), "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            except Exception as exc:  # pragma: no cover
                print(f"[ERROR] Не удалось создать конфиг: {exc}")

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------
    def next_character(self) -> bool:
        """Перейти к следующему персонажу."""
        if self.available_characters:
            self.selected_index = (self.selected_index + 1) % len(self.available_characters)
            self.ensure_selected_visible()
            return True
        return False

    def prev_character(self) -> bool:
        """Перейти к предыдущему персонажу."""
        if self.available_characters:
            self.selected_index = (self.selected_index - 1) % len(self.available_characters)
            self.ensure_selected_visible()
            return True
        return False

    def page_up(self) -> bool:
        """Перейти на страницу вверх."""
        if self.available_characters:
            new = max(0, self.selected_index - self.items_per_page)
            if new != self.selected_index:
                self.selected_index = new
                self.ensure_selected_visible()
                return True
        return False

    def page_down(self) -> bool:
        """Перейти на страницу вниз."""
        if self.available_characters:
            new = min(len(self.available_characters) - 1,
                      self.selected_index + self.items_per_page)
            if new != self.selected_index:
                self.selected_index = new
                self.ensure_selected_visible()
                return True
        return False

    def go_to_first(self) -> bool:
        """Перейти к первому персонажу."""
        if self.available_characters and self.selected_index != 0:
            self.selected_index = 0
            self.scroll_offset = 0
            return True
        return False

    def go_to_last(self) -> bool:
        """Перейти к последнему персонажу."""
        if self.available_characters:
            last = len(self.available_characters) - 1
            if self.selected_index != last:
                self.selected_index = last
                self.ensure_selected_visible()
                return True
        return False

    def ensure_selected_visible(self) -> None:
        """Корректировать scroll_offset, чтобы выбранный элемент был видим."""
        start = self.scroll_offset
        end = self.scroll_offset + self.items_per_page
        if self.selected_index < start:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= end:
            self.scroll_offset = self.selected_index - self.items_per_page + 1

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------
    def handle_keyboard(self, event) -> str | None:
        """Обработать клавиатурные события (стрелки, pageup/down, enter, esc)."""
        if not self.available_characters:
            return None

        if event.type != pygame.KEYDOWN:
            return None

        if event.key == pygame.K_UP:
            if self.prev_character():
                return "navigate"
        elif event.key == pygame.K_DOWN:
            if self.next_character():
                return "navigate"
        elif event.key == pygame.K_PAGEUP:
            if self.page_up():
                return "navigate"
        elif event.key == pygame.K_PAGEDOWN:
            if self.page_down():
                return "navigate"
        elif event.key == pygame.K_HOME:
            if self.go_to_first():
                return "navigate"
        elif event.key == pygame.K_END:
            if self.go_to_last():
                return "navigate"
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            return "select"
        elif event.key == pygame.K_ESCAPE:
            return "cancel"
        elif event.key == pygame.K_TAB:
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                if self.prev_character():
                    return "navigate"
            else:
                if self.next_character():
                    return "navigate"
        return None

    # ------------------------------------------------------------------
    # Mouse wheel handling (fixed)
    # ------------------------------------------------------------------
    def handle_mouse_wheel(self, event) -> str:
        """Обработать прокрутку колеса мыши."""
        if not self.available_characters:
            return "no_action"

        if event.y > 0:  # колесо от себя → вниз по списку
            if self.scroll_offset < max(0, len(self.available_characters) - self.items_per_page):
                self.scroll_offset += 1
                # корректируем выбранный элемент
                if self.selected_index < self.scroll_offset:
                    self.selected_index = min(len(self.available_characters) - 1, self.scroll_offset)
                elif self.selected_index >= self.scroll_offset + self.items_per_page:
                    self.selected_index = self.scroll_offset
                return "navigate"
        elif event.y < 0:  # колесо к себе → вверх по списку
            if self.scroll_offset > 0:
                self.scroll_offset -= 1
                if self.selected_index >= self.scroll_offset + self.items_per_page:
                    self.selected_index = max(0, self.scroll_offset + self.items_per_page - 1)
                elif self.selected_index < self.scroll_offset:
                    self.selected_index = self.scroll_offset
                return "navigate"
        return "no_action"

    # ------------------------------------------------------------------
    # Mouse click handling
    # ------------------------------------------------------------------
    def handle_click(self, mouse_pos: tuple[int, int]) -> str | None:
        """Обработать клики мышью (выбор персонажа, кнопки)."""
        if not self.available_characters:
            return None

        list_w = 700
        list_h = self.items_per_page * self.item_height + 20
        list_x = (self.screen_width - list_w) // 2
        list_y = 80

        list_rect = pygame.Rect(list_x, list_y, list_w, list_h)
        if not list_rect.collidepoint(mouse_pos):
            # кнопки «Confirm» / «Cancel» внизу окна
            btn_y = self.screen_height - 60
            btn_w = 160
            btn_h = 40
            spacing = 30

            confirm = pygame.Rect(
                self.screen_width // 2 - btn_w - spacing // 2,
                btn_y,
                btn_w,
                btn_h,
            )
            if confirm.collidepoint(mouse_pos):
                return "select"

            cancel = pygame.Rect(
                self.screen_width // 2 + spacing // 2,
                btn_y,
                btn_w,
                btn_h,
            )
            if cancel.collidepoint(mouse_pos):
                return "cancel"
            return None

        # Список персонажей
        start = self.scroll_offset
        end = min(self.scroll_offset + self.items_per_page, len(self.available_characters))

        for i in range(start, end):
            idx = i - self.scroll_offset
            item_rect = pygame.Rect(
                list_x + 10,
                list_y + 10 + idx * self.item_height,
                list_w - 20,
                self.item_height - 10,
            )
            if item_rect.collidepoint(mouse_pos):
                self.selected_index = i
                self.ensure_selected_visible()
                return "navigate"
        return None

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_selected_character(self) -> dict | None:
        """Вернуть словарь текущего персонажа."""
        if self.available_characters and self.selected_index < len(self.available_characters):
            return self.available_characters[self.selected_index]
        return None

    def get_selected_animated(self) -> AnimatedCharacter | None:
        """Вернуть объект AnimatedCharacter для текущего персонажа."""
        if self.characters and self.selected_index < len(self.characters):
            return self.characters[self.selected_index]
        return None

    # ------------------------------------------------------------------
    # Update (animate characters)
    # ------------------------------------------------------------------
    def update(self) -> None:
        """Обновить анимацию всех персонажей в списке."""
        for char in self.characters:
            char.update()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render(self, surface, colors: dict, fonts: dict) -> None:
        """Отрисовать интерфейс выбора персонажа."""
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        title = fonts["large"].render("SELECT YOUR CHARACTER", True, colors["white"])
        title_rect = title.get_rect(center=(self.screen_width // 2, 60))
        surface.blit(title, title_rect)

        if not self.available_characters:
            no = fonts["medium"].render("No characters available", True, colors["error"])
            no_rect = no.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
            surface.blit(no, no_rect)
            return

        list_w = 700
        list_h = self.items_per_page * self.item_height + 20
        list_x = (self.screen_width - list_w) // 2
        list_y = 80

        bg = pygame.Rect(list_x, list_y, list_w, list_h)
        pygame.draw.rect(surface, colors["dark_grey"], bg, border_radius=15)
        pygame.draw.rect(surface, colors["accent_grey"], bg, 3, border_radius=15)

        mouse = pygame.mouse.get_pos()
        start = self.scroll_offset
        end = min(self.scroll_offset + self.items_per_page, len(self.available_characters))

        for i in range(start, end):
            idx = i - self.scroll_offset
            char = self.available_characters[i]
            item = pygame.Rect(
                list_x + 10,
                list_y + 10 + idx * self.item_height,
                list_w - 20,
                self.item_height - 10,
            )
            hover = item.collidepoint(mouse)
            selected = i == self.selected_index

            if selected:
                bg_col = colors["player"]
                border = colors["white"]
                txt_col = colors["white"]
            elif hover:
                bg_col = tuple(min(c + 20, 255) for c in colors["light_grey"])
                border = colors["accent_grey"]
                txt_col = colors["white"]
            else:
                bg_col = colors["grey"]
                border = colors["accent_grey"]
                txt_col = colors["white"]

            pygame.draw.rect(surface, bg_col, item, border_radius=10)
            pygame.draw.rect(surface, border, item, 2, border_radius=10)

            avatar_x = item.x + 20
            avatar_y = item.y + self.item_height // 2
            pygame.draw.circle(surface, colors["dark_grey"], (avatar_x, avatar_y), 35)

            if i < len(self.characters):
                self.characters[i].draw(surface, (avatar_x, avatar_y), scale=1.0)

            name = fonts["small"].render(char["name"], True, txt_col)
            name_rect = name.get_rect(midleft=(avatar_x + 50, avatar_y - 15))
            surface.blit(name, name_rect)

            typ = fonts["tiny"].render(f"Type: {char['character_type']}", True,
                                      tuple(min(c + 100, 255) for c in txt_col))
            typ_rect = typ.get_rect(midleft=(avatar_x + 50, avatar_y + 10))
            surface.blit(typ, typ_rect)

            # Кнопка SELECT / SELECTED
            sel_w = 90
            sel_btn = pygame.Rect(
                item.right - sel_w - 10,
                item.centery - 12,
                sel_w,
                25,
            )
            hover_sel = sel_btn.collidepoint(mouse)
            sel_bg = colors["success"] if not selected else colors["white"]
            sel_bg = tuple(min(c + 30, 255) for c in sel_bg) if hover_sel else sel_bg

            pygame.draw.rect(surface, sel_bg, sel_btn, border_radius=6)
            pygame.draw.rect(surface, colors["white"] if hover_sel else colors["accent_grey"],
                             sel_btn, 1, border_radius=6)

            btn_text = "SELECTED" if selected else "SELECT"
            btn_col = colors["black"] if hover_sel else colors["white"]
            btn_surf = fonts["tiny"].render(btn_text, True, btn_col)
            btn_rect = btn_surf.get_rect(center=sel_btn.center)
            surface.blit(btn_surf, btn_rect)

        # Scroll bar (if needed)
        if len(self.available_characters) > self.items_per_page:
            scroll_h = list_h - 20
            handle_h = scroll_h * self.items_per_page / len(self.available_characters)
            handle_y = list_y + 10 + (self.scroll_offset / len(self.available_characters)) * (
                scroll_h - handle_h
            )
            sb_bg = pygame.Rect(list_x + list_w - 15, list_y + 10, 6, scroll_h)
            pygame.draw.rect(surface, colors["grey"], sb_bg, border_radius=3)

            sb_handle = pygame.Rect(list_x + list_w - 15, int(handle_y), 6, int(handle_h))
            pygame.draw.rect(surface, colors["accent_grey"], sb_handle, border_radius=3)

        # Counter
        cnt = fonts["small"].render(
            f"Characters: {len(self.available_characters)} | Selected: {self.selected_index + 1}",
            True,
            colors["accent_grey"],
        )
        cnt_rect = cnt.get_rect(center=(self.screen_width // 2, list_y + list_h + 20))
        surface.blit(cnt, cnt_rect)

        # Bottom buttons (Confirm / Cancel)
        btn_y = self.screen_height - 60
        btn_w = 160
        btn_h = 40
        spacing = 30

        confirm = pygame.Rect(
            self.screen_width // 2 - btn_w - spacing // 2,
            btn_y,
            btn_w,
            btn_h,
        )
        hover = confirm.collidepoint(mouse)
        bg = tuple(min(c + 30, 255) for c in colors["success"]) if hover else colors["success"]
        pygame.draw.rect(surface, bg, confirm, border_radius=8)
        pygame.draw.rect(surface, colors["white"], confirm, 2, border_radius=8)
        txt = fonts["small"].render("CONFIRM", True, colors["white"])
        surface.blit(txt, txt.get_rect(center=confirm.center))

        cancel = pygame.Rect(
            self.screen_width // 2 + spacing // 2,
            btn_y,
            btn_w,
            btn_h,
        )
        hover = cancel.collidepoint(mouse)
        bg = tuple(min(c + 30, 255) for c in colors["error"]) if hover else colors["error"]
        pygame.draw.rect(surface, bg, cancel, border_radius=8)
        pygame.draw.rect(surface, colors["white"], cancel, 2, border_radius=8)
        txt = fonts["small"].render("CANCEL", True, colors["white"])
        surface.blit(txt, txt.get_rect(center=cancel.center))

        # Controls hint
        ctrl = fonts["tiny"].render(
            "Use ↑↓ Key_Left Key_Right",
            True,
            colors["accent_grey"],
        )
        ctrl_rect = ctrl.get_rect(
            center=(self.screen_width // 2, btn_y + btn_h + 15)
        )
        surface.blit(ctrl, ctrl_rect)

    # ------------------------------------------------------------------
    # Misc utilities
    # ------------------------------------------------------------------
    def get_character_by_name(self, name: str) -> dict | None:
        """Найти персонажа по имени (case‑insensitive)."""
        for i, char in enumerate(self.available_characters):
            if char["name"].lower() == name.lower() or char["id"].lower() == name.lower():
                self.selected_index = i
                self.ensure_selected_visible()
                return char
        return None

    def reset_selection(self) -> bool:
        """Сбросить выбор к первому элементу."""
        if self.available_characters:
            self.selected_index = 0
            self.scroll_offset = 0
            return True
        return False

    def get_character_count(self) -> int:
        """Количество доступных персонажей."""
        return len(self.available_characters)

    def is_empty(self) -> bool:
        """True, если в списке нет персонажей."""
        return len(self.available_characters) == 0