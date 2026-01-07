#!/usr/bin/env python3
"""
AnimatedCharacter и CharacterSelector - Классы для анимированных персонажей и меню выбора
"""

import pygame
import os
import json
from PIL import Image, ImageSequence  # Для работы с GIF


class AnimatedCharacter:
    """Класс для управления анимированным персонажем с поддержкой GIF"""

    def __init__(self, character_data, assets_path="assets/characters"):
        self.character_data = character_data
        self.assets_path = assets_path
        self.animations = {}
        self.current_animation = "idle"
        self.current_direction = "right"
        self.current_frame = 0
        self.animation_speed = 0.1
        self.last_update = pygame.time.get_ticks()
        self.loaded = False
        self.scale = 1.0

    def load_gif_frames(self, gif_path):
        """Загрузка всех кадров из GIF файла"""
        try:
            frames = []
            with Image.open(gif_path) as img:
                frame_durations = []
                for frame in ImageSequence.Iterator(img):
                    duration = frame.info.get('duration', 100)
                    frame_durations.append(duration)

                    if frame.mode != 'RGBA':
                        frame = frame.convert('RGBA')

                    data = frame.tobytes()
                    size = frame.size
                    py_surface = pygame.image.fromstring(data, size, 'RGBA')
                    frames.append(py_surface.convert_alpha())

            return frames, frame_durations
        except Exception as e:
            print(f"[ERROR] Не удалось загрузить GIF {gif_path}: {e}")
            return [], []

    def get_direction_from_movement(self, dx, dy):
        """Определение направления по движению"""
        if abs(dx) > abs(dy):
            if dx < 0:
                return "left"
            elif dx > 0:
                return "right"
            else:
                if dy < 0:
                    return "up"
                elif dy > 0:
                    return "down"
                else:
                    return self.current_direction
        else:
            if dy < 0:
                return "up"
            elif dy > 0:
                return "down"
            else:
                if dx < 0:
                    return "left"
                elif dx > 0:
                    return "right"
                else:
                    return self.current_direction

    def load_animations(self):
        """Загрузка анимаций персонажа"""
        character_name = self.character_data.get('name', 'default')
        character_type = self.character_data.get('character_type', character_name)
        character_folder = os.path.join(self.assets_path, character_type)

        if not os.path.exists(character_folder):
            return False

        config_files = [
            os.path.join(character_folder, "animations.json"),
            os.path.join(character_folder, f"{character_type}.json"),
        ]

        animation_config = {}

        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)

                    if "name" in config_data and "animations" in config_data:
                        animation_config = config_data["animations"]
                    else:
                        animation_config = config_data

                    break
                except Exception as e:
                    continue

        if not animation_config:
            animation_config = self.auto_detect_gifs(character_folder)

        if not animation_config:
            animation_config = self.create_default_config(character_folder)

        for animation_name, config in animation_config.items():
            speed = config.get("speed", 0.1)

            self.animations[animation_name] = {
                "speed": speed,
                "loop": config.get("loop", True),
                "directions": config.get("directions", ["right"]),
                "direction_frames": {},
                "direction_durations": {}
            }

            directions = self.animations[animation_name]["directions"]

            for direction in directions:
                gif_path = None
                possible_files = [
                    os.path.join(character_folder, config.get(f"{direction}_file", "")),
                    os.path.join(character_folder, f"{animation_name}_{direction}.gif"),
                    os.path.join(character_folder, f"{animation_name}.gif"),
                ]

                for file_path in possible_files:
                    if file_path and os.path.exists(file_path):
                        gif_path = file_path
                        break

                frames = []
                durations = []
                if gif_path:
                    frames, durations = self.load_gif_frames(gif_path)
                    if not durations:
                        default_duration = int(speed * 1000)
                        durations = [default_duration] * len(frames)

                if frames:
                    self.animations[animation_name]["direction_frames"][direction] = frames
                    self.animations[animation_name]["direction_durations"][direction] = durations
                else:
                    placeholder = self.create_placeholder_frame(character_type, animation_name, direction)
                    self.animations[animation_name]["direction_frames"][direction] = [placeholder]
                    self.animations[animation_name]["direction_durations"][direction] = [100]

        self.loaded = len(self.animations) > 0
        return self.loaded

    def auto_detect_gifs(self, character_folder):
        """Автоматическое определение GIF файлов в папке"""
        config = {}

        for filename in os.listdir(character_folder):
            if filename.endswith('.gif'):
                name_without_ext = filename[:-4]
                parts = name_without_ext.split('_')

                if len(parts) >= 2 and parts[-1] in ["left", "right", "up", "down"]:
                    direction = parts[-1]
                    anim_name = "_".join(parts[:-1])

                    if anim_name not in config:
                        config[anim_name] = {
                            "directions": [direction],
                            f"{direction}_file": filename,
                            "speed": 0.1,
                            "loop": True
                        }
                    else:
                        if direction not in config[anim_name]["directions"]:
                            config[anim_name]["directions"].append(direction)
                        config[anim_name][f"{direction}_file"] = filename
                else:
                    anim_name = name_without_ext
                    if anim_name not in config:
                        config[anim_name] = {
                            "directions": ["right"],
                            "file": filename,
                            "speed": 0.1,
                            "loop": True
                        }

        return config

    def create_default_config(self, character_folder):
        """Создание конфигурации по умолчанию"""
        config = {}
        common_animations = ["idle", "walk", "run", "attack", "jump"]
        directions = ["left", "right", "up", "down"]

        for anim in common_animations:
            found_files = []
            for direction in directions:
                possible_names = [
                    f"{anim}_{direction}.gif",
                    f"{anim}_{direction}_1.gif",
                    f"{direction}_{anim}.gif",
                ]

                for filename in possible_names:
                    gif_path = os.path.join(character_folder, filename)
                    if os.path.exists(gif_path):
                        found_files.append((direction, filename))
                        break

            if found_files:
                config[anim] = {
                    "directions": [d for d, _ in found_files],
                    "speed": 0.1,
                    "loop": True
                }
                for direction, filename in found_files:
                    config[anim][f"{direction}_file"] = filename

        return config

    def create_placeholder_frame(self, character_type, animation_name, direction):
        """Создание заглушки для отсутствующего GIF"""
        frame = pygame.Surface((64, 64), pygame.SRCALPHA)

        colors = {
            "Cadance": (255, 182, 193),
            "Celestia": (255, 215, 0),
            "Luna": (138, 43, 226),
        }

        color = colors.get(character_type, (150, 150, 150))
        pygame.draw.rect(frame, (*color, 150), (0, 0, 64, 64), border_radius=10)

        if direction == "left":
            pygame.draw.polygon(frame, (*color, 200), [(20, 32), (44, 20), (44, 44)])
        elif direction == "right":
            pygame.draw.polygon(frame, (*color, 200), [(44, 32), (20, 20), (20, 44)])
        elif direction == "up":
            pygame.draw.polygon(frame, (*color, 200), [(32, 20), (20, 44), (44, 44)])
        elif direction == "down":
            pygame.draw.polygon(frame, (*color, 200), [(32, 44), (20, 20), (44, 20)])

        try:
            font = pygame.font.Font(None, 12)
            text = font.render(f"{character_type[:3]}", True, (255, 255, 255))
            text_rect = text.get_rect(center=(32, 32))
            frame.blit(text, text_rect)
        except:
            pass

        return frame

    def set_animation(self, animation_name, direction=None):
        """Установка текущей анимации и направления"""
        if animation_name in self.animations:
            if animation_name != self.current_animation:
                self.current_animation = animation_name
                self.current_frame = 0
                self.last_update = pygame.time.get_ticks()

            if direction:
                if direction in self.animations[animation_name]["directions"]:
                    if self.current_direction != direction:
                        self.current_direction = direction
                        self.current_frame = 0
                        self.last_update = pygame.time.get_ticks()
                else:
                    if direction in ["left", "right"]:
                        alt_direction = "right" if direction == "left" else "left"
                        if alt_direction in self.animations[animation_name]["directions"]:
                            self.current_direction = alt_direction
                            self.current_frame = 0
                            self.last_update = pygame.time.get_ticks()
                    elif direction in ["up", "down"]:
                        alt_direction = "down" if direction == "up" else "up"
                        if alt_direction in self.animations[animation_name]["directions"]:
                            self.current_direction = alt_direction
                            self.current_frame = 0
                            self.last_update = pygame.time.get_ticks()

            return True
        elif not self.animations:
            self.current_animation = animation_name
            if direction:
                self.current_direction = direction
            return True

        for anim_name in self.animations.keys():
            if anim_name in animation_name or animation_name in anim_name:
                self.current_animation = anim_name
                self.current_frame = 0
                self.last_update = pygame.time.get_ticks()
                if direction:
                    self.set_direction(direction)
                return True

        return False

    def set_direction(self, direction):
        """Установка направления"""
        if self.current_animation in self.animations:
            if direction in self.animations[self.current_animation]["directions"]:
                if self.current_direction != direction:
                    self.current_direction = direction
                    self.current_frame = 0
                    self.last_update = pygame.time.get_ticks()
                return True
            else:
                if direction in ["left", "right"]:
                    alt_direction = "right" if direction == "left" else "left"
                    if alt_direction in self.animations[self.current_animation]["directions"]:
                        self.current_direction = alt_direction
                        self.current_frame = 0
                        self.last_update = pygame.time.get_ticks()
                        return True
                elif direction in ["up", "down"]:
                    alt_direction = "down" if direction == "up" else "up"
                    if alt_direction in self.animations[self.current_animation]["directions"]:
                        self.current_direction = alt_direction
                        self.current_frame = 0
                        self.last_update = pygame.time.get_ticks()
                        return True
        return False

    def update(self):
        """Обновление анимации"""
        if not self.loaded:
            return

        anim = self.animations.get(self.current_animation)
        if not anim:
            return

        current_time = pygame.time.get_ticks()
        frames = anim["direction_frames"].get(self.current_direction, [])
        durations = anim["direction_durations"].get(self.current_direction, [])

        if not frames or not durations:
            if self.current_direction in ["left", "right"]:
                alt_direction = "right" if self.current_direction == "left" else "left"
                frames = anim["direction_frames"].get(alt_direction, [])
                durations = anim["direction_durations"].get(alt_direction, [])
            elif self.current_direction in ["up", "down"]:
                alt_direction = "down" if self.current_direction == "up" else "up"
                frames = anim["direction_frames"].get(alt_direction, [])
                durations = anim["direction_durations"].get(alt_direction, [])

            if frames and durations:
                self.current_direction = alt_direction

        if not frames or not durations:
            return

        if self.current_frame < len(durations):
            frame_duration = durations[self.current_frame]
        else:
            frame_duration = 100

        time_since_last_update = current_time - self.last_update

        if time_since_last_update > frame_duration:
            self.last_update = current_time
            self.current_frame += 1

            if self.current_frame >= len(frames):
                if anim["loop"]:
                    self.current_frame = 0
                else:
                    self.current_frame = len(frames) - 1
                    if self.current_animation in ["jump", "attack"]:
                        self.set_animation("idle")

    def get_current_frame(self):
        """Получение текущего кадра"""
        if not self.loaded:
            return self.create_placeholder_frame(
                self.character_data.get('character_type', 'default'),
                self.current_animation,
                self.current_direction
            )

        anim = self.animations.get(self.current_animation)
        if not anim:
            return self.create_placeholder_frame(
                self.character_data.get('character_type', 'default'),
                self.current_animation,
                self.current_direction
            )

        frames = anim["direction_frames"].get(self.current_direction)

        if not frames:
            if self.current_direction in ["left", "right"]:
                alt_direction = "right" if self.current_direction == "left" else "left"
                frames = anim["direction_frames"].get(alt_direction)
                if frames:
                    self.current_direction = alt_direction
            elif self.current_direction in ["up", "down"]:
                alt_direction = "down" if self.current_direction == "up" else "up"
                frames = anim["direction_frames"].get(alt_direction)
                if frames:
                    self.current_direction = alt_direction

        if not frames or self.current_frame >= len(frames):
            return self.create_placeholder_frame(
                self.character_data.get('character_type', 'default'),
                self.current_animation,
                self.current_direction
            )

        return frames[self.current_frame]

    def draw(self, surface, position, scale=1.0):
        """Отрисовка персонажа"""
        frame = self.get_current_frame()
        if frame:
            scaled_frame = pygame.transform.scale(frame,
                                                  (int(frame.get_width() * scale),
                                                   int(frame.get_height() * scale)))
            surface.blit(scaled_frame,
                         (position[0] - scaled_frame.get_width() // 2,
                          position[1] - scaled_frame.get_height() // 2))

    def get_size(self, scale=1.0):
        """Получение размера персонажа"""
        frame = self.get_current_frame()
        if frame:
            return (int(frame.get_width() * scale),
                    int(frame.get_height() * scale))
        return (0, 0)

    def get_animation_names(self):
        """Получение списка доступных анимаций"""
        return list(self.animations.keys())

    def get_directions_for_animation(self, animation_name):
        """Получение доступных направлений для анимации"""
        if animation_name in self.animations:
            return self.animations[animation_name]["directions"]
        return []

    def has_animation_direction(self, animation_name, direction):
        """Проверка наличия анимации с определенным направлением"""
        if animation_name in self.animations:
            if direction in self.animations[animation_name]["directions"]:
                return True
            if direction == "left" and "right" in self.animations[animation_name]["directions"]:
                return True
            if direction == "right" and "left" in self.animations[animation_name]["directions"]:
                return True
            if direction == "up" and "down" in self.animations[animation_name]["directions"]:
                return True
            if direction == "down" and "up" in self.animations[animation_name]["directions"]:
                return True
        return False


class CharacterSelector:
    """Класс для меню выбора персонажа в виде списка"""

    def __init__(self, screen_width, screen_height, assets_path="assets/characters"):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.assets_path = assets_path
        self.available_characters = []
        self.selected_index = 0
        self.characters = []
        self.scroll_offset = 0
        self.items_per_page = 6
        self.item_height = 100
        self.load_characters()

    def load_characters(self):
        """Загрузка доступных персонажей"""
        self.available_characters.clear()
        self.characters.clear()
        self.selected_index = 0
        self.scroll_offset = 0

        custom_order = ["Celestia", "Luna", "Cadance", "TwilightSparkle", "AppleJack",
                        "RainbowDash", "Fluttershy", "Rarity", "PinkiePie"]

        loaded_characters = {}
        loaded_animated_chars = {}

        for char_name in custom_order:
            char_folder = os.path.join(self.assets_path, char_name)

            if not os.path.exists(char_folder):
                continue

            has_gifs = False
            if os.path.isdir(char_folder):
                for file in os.listdir(char_folder):
                    if file.endswith('.gif'):
                        has_gifs = True
                        break

            if not has_gifs:
                continue

            character_data = {
                'id': char_name,
                'name': char_name.replace('_', ' ').title(),
                'folder': char_folder,
                'character_type': char_name,
                'description': f"Персонаж типа {char_name}"
            }

            loaded_characters[char_name] = character_data
            animated_char = AnimatedCharacter(character_data, self.assets_path)
            if animated_char.load_animations():
                loaded_animated_chars[char_name] = animated_char

        for char_name in custom_order:
            if char_name in loaded_characters and char_name in loaded_animated_chars:
                self.available_characters.append(loaded_characters[char_name])
                self.characters.append(loaded_animated_chars[char_name])

        if not self.available_characters:
            self.create_demo_characters()

    def create_demo_characters(self):
        """Создание демо персонажей"""
        demo_chars = ["Cadance", "Celestia", "Luna"]

        for char_name in demo_chars:
            char_folder = os.path.join(self.assets_path, char_name)

            if not os.path.exists(char_folder):
                os.makedirs(char_folder, exist_ok=True)

            config = {
                "idle": {
                    "directions": ["left", "right"],
                    "left_file": "idle_left.gif",
                    "right_file": "idle_right.gif",
                    "speed": 0.2,
                    "loop": True
                },
                "walk": {
                    "directions": ["left", "right"],
                    "left_file": "walk_left.gif",
                    "right_file": "walk_right.gif",
                    "speed": 0.15,
                    "loop": True
                }
            }

            try:
                config_path = os.path.join(char_folder, "animations.json")
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[ERROR] Не удалось создать конфиг: {e}")

    def next_character(self):
        """Следующий персонаж"""
        if self.available_characters:
            self.selected_index = (self.selected_index + 1) % len(self.available_characters)
            self.ensure_selected_visible()
            return True
        return False

    def prev_character(self):
        """Предыдущий персонаж"""
        if self.available_characters:
            self.selected_index = (self.selected_index - 1) % len(self.available_characters)
            self.ensure_selected_visible()
            return True
        return False

    def page_up(self):
        """Страница вверх"""
        if self.available_characters:
            new_index = max(0, self.selected_index - self.items_per_page)
            if new_index != self.selected_index:
                self.selected_index = new_index
                self.ensure_selected_visible()
                return True
        return False

    def page_down(self):
        """Страница вниз"""
        if self.available_characters:
            new_index = min(len(self.available_characters) - 1,
                            self.selected_index + self.items_per_page)
            if new_index != self.selected_index:
                self.selected_index = new_index
                self.ensure_selected_visible()
                return True
        return False

    def go_to_first(self):
        """К первому"""
        if self.available_characters and self.selected_index != 0:
            self.selected_index = 0
            self.scroll_offset = 0
            return True
        return False

    def go_to_last(self):
        """К последнему"""
        if self.available_characters:
            last_index = len(self.available_characters) - 1
            if self.selected_index != last_index:
                self.selected_index = last_index
                self.ensure_selected_visible()
                return True
        return False

    def ensure_selected_visible(self):
        """Видимость выбранного персонажа"""
        visible_start = self.scroll_offset
        visible_end = self.scroll_offset + self.items_per_page

        if self.selected_index < visible_start:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= visible_end:
            self.scroll_offset = self.selected_index - self.items_per_page + 1

    def handle_keyboard(self, event):
        """Обработка клавиатуры"""
        if not self.available_characters:
            return None

        if event.type == pygame.KEYDOWN:
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
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
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

    def handle_mouse_wheel(self, event):
        """Обработка колесика мыши - ИСПРАВЛЕНО"""
        if not self.available_characters:
            return "no_action"

        # В Pygame MOUSEWHEEL:
        # event.y > 0 - прокрутка вверх (колесико от себя)
        # event.y < 0 - прокрутка вниз (колесико к себе)

        # Прокрутка по 1 персонажу за раз
        if event.y > 0:  # Колесико от себя - ВНИЗ по списку
            if self.scroll_offset < max(0, len(self.available_characters) - self.items_per_page):
                self.scroll_offset += 1
                # Также меняем выбранного, если он выходит за видимую область
                if self.selected_index < self.scroll_offset:
                    self.selected_index = min(len(self.available_characters) - 1, self.scroll_offset)
                elif self.selected_index >= self.scroll_offset + self.items_per_page:
                    self.selected_index = self.scroll_offset
                return "navigate"
        elif event.y < 0:  # Колесико к себе - ВВЕРХ по списку
            if self.scroll_offset > 0:
                self.scroll_offset -= 1
                # Также меняем выбранного, если он выходит за видимую область
                if self.selected_index >= self.scroll_offset + self.items_per_page:
                    self.selected_index = max(0, self.scroll_offset + self.items_per_page - 1)
                elif self.selected_index < self.scroll_offset:
                    self.selected_index = self.scroll_offset
                return "navigate"

        return "no_action"

    def handle_click(self, mouse_pos):
        """Обработка кликов"""
        if not self.available_characters:
            return None

        list_width = 700
        list_height = self.items_per_page * self.item_height + 20
        list_x = (self.screen_width - list_width) // 2
        list_y = 80

        list_rect = pygame.Rect(list_x, list_y, list_width, list_height)
        if not list_rect.collidepoint(mouse_pos):
            button_y = self.screen_height - 60
            button_width = 160
            button_height = 40
            button_spacing = 30

            confirm_rect = pygame.Rect(
                self.screen_width // 2 - button_width - button_spacing // 2,
                button_y,
                button_width,
                button_height
            )

            if confirm_rect.collidepoint(mouse_pos):
                return "select"

            cancel_rect = pygame.Rect(
                self.screen_width // 2 + button_spacing // 2,
                button_y,
                button_width,
                button_height
            )

            if cancel_rect.collidepoint(mouse_pos):
                return "cancel"

            return None

        visible_start = self.scroll_offset
        visible_end = min(self.scroll_offset + self.items_per_page, len(self.available_characters))

        for i in range(visible_start, visible_end):
            idx = i - self.scroll_offset

            item_rect = pygame.Rect(
                list_x + 10,
                list_y + 10 + idx * self.item_height,
                list_width - 20,
                self.item_height - 10
            )

            if item_rect.collidepoint(mouse_pos):
                self.selected_index = i
                self.ensure_selected_visible()
                return "navigate"

        return None

    def get_selected_character(self):
        """Получение выбранного персонажа"""
        if self.available_characters and self.selected_index < len(self.available_characters):
            return self.available_characters[self.selected_index]
        return None

    def get_selected_animated(self):
        """Получение анимированного объекта"""
        if self.characters and self.selected_index < len(self.characters):
            return self.characters[self.selected_index]
        return None

    def update(self):
        """Обновление анимаций"""
        for char in self.characters:
            char.update()

    def render(self, surface, colors, fonts):
        """Отрисовка меню"""
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        title = fonts['large'].render("SELECT YOUR CHARACTER", True, colors['white'])
        title_rect = title.get_rect(center=(self.screen_width // 2, 60))
        surface.blit(title, title_rect)

        if not self.available_characters:
            no_chars = fonts['medium'].render("No characters available", True, colors['error'])
            no_chars_rect = no_chars.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
            surface.blit(no_chars, no_chars_rect)
            return

        list_width = 700
        list_height = self.items_per_page * self.item_height + 20
        list_x = (self.screen_width - list_width) // 2
        list_y = 80

        list_bg = pygame.Rect(list_x, list_y, list_width, list_height)
        pygame.draw.rect(surface, colors['dark_grey'], list_bg, border_radius=15)
        pygame.draw.rect(surface, colors['accent_grey'], list_bg, 3, border_radius=15)

        visible_start = self.scroll_offset
        visible_end = min(self.scroll_offset + self.items_per_page, len(self.available_characters))
        mouse_pos = pygame.mouse.get_pos()

        for i in range(visible_start, visible_end):
            idx = i - self.scroll_offset
            char = self.available_characters[i]

            item_rect = pygame.Rect(
                list_x + 10,
                list_y + 10 + idx * self.item_height,
                list_width - 20,
                self.item_height - 10
            )

            hover = item_rect.collidepoint(mouse_pos)
            selected = (i == self.selected_index)

            if selected:
                bg_color = colors['player']
                border_color = colors['white']
                text_color = colors['white']
            elif hover:
                bg_color = tuple(min(c + 20, 255) for c in colors['light_grey'])
                border_color = colors['accent_grey']
                text_color = colors['white']
            else:
                bg_color = colors['grey']
                border_color = colors['accent_grey']
                text_color = colors['white']

            pygame.draw.rect(surface, bg_color, item_rect, border_radius=10)
            pygame.draw.rect(surface, border_color, item_rect, 2, border_radius=10)

            avatar_x = item_rect.x + 20
            avatar_y = item_rect.y + self.item_height // 2

            pygame.draw.circle(surface, colors['dark_grey'], (avatar_x, avatar_y), 35)

            if i < len(self.characters):
                animated_char = self.characters[i]
                animated_char.draw(surface, (avatar_x, avatar_y), scale=1.0)

            name_text = fonts['small'].render(char['name'], True, text_color)
            name_rect = name_text.get_rect(midleft=(avatar_x + 50, avatar_y - 15))
            surface.blit(name_text, name_rect)

            type_text = fonts['tiny'].render(f"Type: {char['character_type']}", True,
                                             tuple(min(c + 100, 255) for c in text_color))
            type_rect = type_text.get_rect(midleft=(avatar_x + 50, avatar_y + 10))
            surface.blit(type_text, type_rect)

            select_btn_width = 90
            select_btn = pygame.Rect(
                item_rect.right - select_btn_width - 10,
                item_rect.centery - 12,
                select_btn_width,
                25
            )

            select_hover = select_btn.collidepoint(mouse_pos)
            select_color = colors['success'] if not selected else colors['white']
            select_bg = tuple(min(c + 30, 255) for c in select_color) if select_hover else select_color

            pygame.draw.rect(surface, select_bg, select_btn, border_radius=6)
            pygame.draw.rect(surface, colors['white'] if select_hover else colors['accent_grey'],
                             select_btn, 1, border_radius=6)

            btn_text = "SELECTED" if selected else "SELECT"
            btn_text_color = colors['black'] if select_hover else colors['white']
            btn_text_surf = fonts['tiny'].render(btn_text, True, btn_text_color)
            btn_text_rect = btn_text_surf.get_rect(center=select_btn.center)
            surface.blit(btn_text_surf, btn_text_rect)

        if len(self.available_characters) > self.items_per_page:
            scroll_height = list_height - 20
            scroll_handle_height = scroll_height * self.items_per_page / len(self.available_characters)
            scroll_handle_y = list_y + 10 + (self.scroll_offset / len(self.available_characters)) * (
                    scroll_height - scroll_handle_height)

            scroll_bg = pygame.Rect(list_x + list_width - 15, list_y + 10, 6, scroll_height)
            pygame.draw.rect(surface, colors['grey'], scroll_bg, border_radius=3)

            scroll_handle = pygame.Rect(list_x + list_width - 15, scroll_handle_y, 6, scroll_handle_height)
            pygame.draw.rect(surface, colors['accent_grey'], scroll_handle, border_radius=3)

        counter_text = fonts['small'].render(
            f"Characters: {len(self.available_characters)} | Selected: {self.selected_index + 1}",
            True, colors['accent_grey']
        )
        counter_rect = counter_text.get_rect(center=(self.screen_width // 2, list_y + list_height + 20))
        surface.blit(counter_text, counter_rect)

        button_y = self.screen_height - 60
        button_width = 160
        button_height = 40
        button_spacing = 30

        confirm_rect = pygame.Rect(
            self.screen_width // 2 - button_width - button_spacing // 2,
            button_y,
            button_width,
            button_height
        )

        confirm_hover = confirm_rect.collidepoint(mouse_pos)
        confirm_color = tuple(min(c + 30, 255) for c in colors['success']) if confirm_hover else colors['success']

        pygame.draw.rect(surface, confirm_color, confirm_rect, border_radius=8)
        pygame.draw.rect(surface, colors['white'], confirm_rect, 2, border_radius=8)

        confirm_text = fonts['small'].render("CONFIRM", True, colors['white'])
        confirm_rect_text = confirm_text.get_rect(center=confirm_rect.center)
        surface.blit(confirm_text, confirm_rect_text)

        cancel_rect = pygame.Rect(
            self.screen_width // 2 + button_spacing // 2,
            button_y,
            button_width,
            button_height
        )

        cancel_hover = cancel_rect.collidepoint(mouse_pos)
        cancel_color = tuple(min(c + 30, 255) for c in colors['error']) if cancel_hover else colors['error']

        pygame.draw.rect(surface, cancel_color, cancel_rect, border_radius=8)
        pygame.draw.rect(surface, colors['white'], cancel_rect, 2, border_radius=8)

        cancel_text = fonts['small'].render("CANCEL", True, colors['white'])
        cancel_rect_text = cancel_text.get_rect(center=cancel_rect.center)
        surface.blit(cancel_text, cancel_rect_text)

        # ИСПРАВЛЕННАЯ НАДПИСЬ ПРО УПРАВЛЕНИЕ
        controls_text = fonts['tiny'].render(
            "Use ↑↓ Key_Left Key_Right",
            True, colors['accent_grey']
        )
        controls_rect = controls_text.get_rect(center=(self.screen_width // 2, button_y + button_height + 15))
        surface.blit(controls_text, controls_rect)

    def get_character_by_name(self, name):
        """Получение персонажа по имени"""
        for i, char in enumerate(self.available_characters):
            if char['name'].lower() == name.lower() or char['id'].lower() == name.lower():
                self.selected_index = i
                self.ensure_selected_visible()
                return char
        return None

    def reset_selection(self):
        """Сброс выбора"""
        if self.available_characters:
            self.selected_index = 0
            self.scroll_offset = 0
            return True
        return False

    def get_character_count(self):
        """Количество персонажей"""
        return len(self.available_characters)

    def is_empty(self):
        """Проверка на пустоту"""
        return len(self.available_characters) == 0