import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import os
import random
import threading
import time


class GIFPlayer:
    def __init__(self, root):
        self.root = root

        # Флаг безопасного завершения
        self._shutdown_flag = threading.Event()
        self._threads_running = True

        # Определяем тип окна
        self.is_toplevel = hasattr(root, 'master') and root.master is not None

        # Настройки
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.GIF_FOLDER = os.path.join(current_dir, "MCadance_Gifct")

        # ========== ПУТИ ДЛЯ ГИФОК ==========
        self.GIF_PATHS = {
            # Stand гифки
            "stand_right": "cadance_stand_right.gif",
            "stand_left": "cadance_stand_left.gif",

            # Movement гифки
            "move_right": "cadance-flight-right.gif",
            "move_left": "cadance-flight-left.gif",

            # Sleep гифки (в подпапке sleep-aj)
            "sleep_right": "none",
            "sleep_left": "none",

            # Drag гифки (в подпапке drag-aj)
            "drag": "none"
        }

        # ========== ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ==========
        self.SLEEP_ENABLED =  False  # Если False - отключает всю функциональность сна

        self.WIDTH, self.HEIGHT = 150, 150
        self.SLEEP_WIDTH, self.SLEEP_HEIGHT = 150, 150
        self.FRAME_DURATION_MS = 100
        self.SLEEP_FRAME_DURATION_MS = 700
        self.MOVE_INTERVAL_MIN = 2
        self.MOVE_INTERVAL_MAX = 5
        self.MOVE_SPEED_PX_PER_STEP = 2
        self.MOVE_STEP_DELAY_SEC = 0.06
        self.SCREEN_MARGIN = 1
        self.BOTTOM_MARGIN = 10
        self.SLEEP_TIMEOUT = 100

        # ========== НОВЫЕ НАСТРОЙКИ ДЛЯ ВЫТАЛКИВАНИЯ ==========
        self.PUSH_ZONE_SIZE = 1  # Размер зоны выталкивания (px)
        self.PUSH_FORCE = 5  # Сила выталкивания (px)

        # Инициализация переменных
        self.frames = []
        self.frame_index = 0
        self.current_gif_path = None
        self.is_dragging = False
        self.animating = False
        self.moving = True
        self.target_x = None
        self.target_y = None
        self._drag_start_x = 100
        self._drag_start_y = 100
        self.current_direction = "right"
        self.current_state = "idle"
        self.last_activity_time = time.time()
        self.is_sleeping = False
        self._just_woke_up = False
        self._forced_sleep = False

        # Сохранение состояний
        self._saved_frames = []
        self._saved_frame_index = 0
        self._saved_gif_path = None
        self._saved_state = "idle"
        self._saved_direction = "right"
        self._saved_before_sleep_geometry = None

        # Контекстное меню - настройки цвета
        self.context_menu = None
        self.menu_bg_color = '#2d2d2d'
        self.menu_fg_color = '#ffffff'
        self.menu_active_bg = '#0078d7'
        self.menu_active_fg = '#ffffff'

        # Колбэк для возврата к главному окну
        self.return_to_main_callback = None

        # Проверяем существование папки с гифками
        self._check_gif_folder()

        # Настройка окна и интерфейса
        self._setup_window()
        self._setup_canvas()
        self._bind_events()

        # Загрузка гифки и запуск потоков
        if not self._load_stand_gif("right"):
            print("❌ Не удалось загрузить стартовую гифку, создаем fallback")
            self._create_fallback_animation()
        else:
            self.animating = True
            print("✅ Стартовая гифка загружена")

        # Запускаем потоки
        self._animation_thread = threading.Thread(target=self._safe_animate, daemon=True)
        self._move_thread = threading.Thread(target=self._safe_move_loop, daemon=True)
        self._sleep_thread = threading.Thread(target=self._safe_sleep_monitor, daemon=True)

        self._animation_thread.start()
        self._move_thread.start()
        self._sleep_thread.start()

        self._schedule_change()

    # ========== НОВЫЕ МЕТОДЫ ДЛЯ ВЫТАЛКИВАНИЯ ==========

    def _is_in_push_zone(self, x, y):
        """Проверяет, находится ли персонаж в зоне выталкивания"""
        if self._shutdown_flag.is_set():
            return False

        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            # Проверяем левую зону выталкивания
            in_left_zone = x <= self.PUSH_ZONE_SIZE

            # Проверяем правую зону выталкивания
            in_right_zone = x >= screen_w - self.WIDTH - self.PUSH_ZONE_SIZE

            # Проверяем верхнюю зону выталкивания
            in_top_zone = y <= self.PUSH_ZONE_SIZE

            # Проверяем нижнюю зону выталкивания (только для низа экрана)
            in_bottom_zone = y >= screen_h - self.HEIGHT - self.BOTTOM_MARGIN - self.PUSH_ZONE_SIZE

            return in_left_zone or in_right_zone or in_top_zone or in_bottom_zone

        except tk.TclError:
            return False

    def _get_push_direction(self, x, y):
        """Определяет направление выталкивания"""
        if self._shutdown_flag.is_set():
            return None

        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            # Определяем в какой зоне находится персонаж
            if x <= self.PUSH_ZONE_SIZE:
                return "right"  # Выталкиваем вправо из левой зоны
            elif x >= screen_w - self.WIDTH - self.PUSH_ZONE_SIZE:
                return "left"  # Выталкиваем влево из правой зоны
            elif y <= self.PUSH_ZONE_SIZE:
                return "down"  # Выталкиваем вниз из верхней зоны
            elif y >= screen_h - self.HEIGHT - self.BOTTOM_MARGIN - self.PUSH_ZONE_SIZE:
                return "up"  # Выталкиваем вверх из нижней зоны

            return None
        except tk.TclError:
            return None

    def _apply_push_force(self, x, y):
        """Применяет силу выталкивания к позиции"""
        if self._shutdown_flag.is_set():
            return x, y

        push_direction = self._get_push_direction(x, y)
        if not push_direction:
            return x, y

        new_x, new_y = x, y

        if push_direction == "right":
            new_x = self.PUSH_ZONE_SIZE + self.PUSH_FORCE
        elif push_direction == "left":
            new_x = self.root.winfo_screenwidth() - self.WIDTH - self.PUSH_ZONE_SIZE - self.PUSH_FORCE
        elif push_direction == "down":
            new_y = self.PUSH_ZONE_SIZE + self.PUSH_FORCE
        elif push_direction == "up":
            new_y = self.root.winfo_screenheight() - self.HEIGHT - self.BOTTOM_MARGIN - self.PUSH_ZONE_SIZE - self.PUSH_FORCE

        # Обеспечиваем, чтобы новые координаты были в безопасных пределах
        new_x = max(self.SCREEN_MARGIN, min(new_x, self.root.winfo_screenwidth() - self.WIDTH - self.SCREEN_MARGIN))
        new_y = max(self.SCREEN_MARGIN, min(new_y, self.root.winfo_screenheight() - self.HEIGHT - self.BOTTOM_MARGIN))

        # УБРАНО: отладочное сообщение о выталкивании
        return new_x, new_y

    def _check_and_push_from_edges(self):
        """Проверяет и выталкивает персонажа из краевых зон"""
        if self._shutdown_flag.is_set() or self.is_dragging or self.is_sleeping:
            return

        try:
            current_x = self.root.winfo_x()
            current_y = self.root.winfo_y()

            if self._is_in_push_zone(current_x, current_y):
                new_x, new_y = self._apply_push_force(current_x, current_y)
                if new_x != current_x or new_y != current_y:
                    self.root.geometry(f"+{new_x}+{new_y}")
                    # Обновляем цель движения, чтобы персонаж не пытался вернуться в зону выталкивания
                    self.target_x, self.target_y = new_x, new_y
                    # УБРАНО: отладочное сообщение о выталкивании

        except Exception as e:
            # Оставляем только сообщения об ошибках
            if not self._shutdown_flag.is_set():
                print(f"❌ Ошибка при выталкивании: {e}")

    # ========== ОБНОВЛЕННЫЕ МЕТОДЫ ДВИЖЕНИЯ ==========

    def _safe_move_loop(self):
        """Безопасная версия цикла движения"""
        while self._threads_running and not self._shutdown_flag.is_set():
            try:
                if (self.moving and not self.is_dragging and
                        self.animating and not self.is_sleeping and
                        self._threads_running and not self._shutdown_flag.is_set()):

                    if random.random() < 0.1:
                        self.root.after(0, self._fix_stuck_position)

                    # ДОБАВЛЕНО: Проверка и выталкивание из краевых зон
                    self.root.after(0, self._check_and_push_from_edges)

                    if self._just_woke_up:
                        time.sleep(1)
                    self._pick_target()
                    self._safe_move_to_target()

                if self._threads_running and not self._shutdown_flag.is_set():
                    delay = random.uniform(self.MOVE_INTERVAL_MIN, self.MOVE_INTERVAL_MAX)
                    elapsed = 0
                    while (elapsed < delay and
                           self._threads_running and
                           not self._shutdown_flag.is_set()):
                        time.sleep(0.1)
                        elapsed += 0.1
            except Exception as e:
                if self._threads_running and not self._shutdown_flag.is_set():
                    time.sleep(1)

    def _safe_move_to_target(self):
        """Безопасная версия движения к цели"""
        while (self.moving and not self.is_dragging and
               self.animating and not self.is_sleeping and
               self._threads_running and not self._shutdown_flag.is_set()):
            try:
                if self._shutdown_flag.is_set():
                    break

                current_x, current_y = self.root.winfo_x(), self.root.winfo_y()

                # ДОБАВЛЕНО: Проверка на нахождение в зоне выталкивания во время движения
                if self._is_in_push_zone(current_x, current_y):
                    # УБРАНО: отладочное сообщение
                    new_x, new_y = self._apply_push_force(current_x, current_y)
                    self.root.after(0, lambda: self._safe_set_geometry(new_x, new_y))
                    self.target_x, self.target_y = new_x, new_y
                    continue

                if (abs(current_x - self.target_x) <= self.MOVE_SPEED_PX_PER_STEP and
                        abs(current_y - self.target_y) <= self.MOVE_SPEED_PX_PER_STEP):
                    if self.current_state != "idle":
                        self._load_stand_gif(self.current_direction)
                    return

                if self._check_wall_collision(current_x, current_y):
                    print("🚧 Столкновение со стеной, выбираем новую цель")
                    new_direction = "left" if self.current_direction == "right" else "right"
                    self.current_direction = new_direction
                    self._pick_opposite_target(current_x, current_y)
                    self._load_stand_gif(new_direction)
                    continue

                new_direction = "right" if self.target_x > current_x else "left"
                if new_direction != self.current_direction or self.current_state == "idle":
                    self.current_direction = new_direction
                    self._load_direction_gif(new_direction)

                dx = 0
                dy = 0

                if current_x < self.target_x:
                    dx = min(self.MOVE_SPEED_PX_PER_STEP, self.target_x - current_x)
                elif current_x > self.target_x:
                    dx = -min(self.MOVE_SPEED_PX_PER_STEP, current_x - self.target_x)

                if current_y < self.target_y:
                    dy = min(self.MOVE_SPEED_PX_PER_STEP, self.target_y - current_y)
                elif current_y > self.target_y:
                    dy = -min(self.MOVE_SPEED_PX_PER_STEP, current_y - self.target_y)

                new_x = current_x + dx
                new_y = current_y + dy

                # ДОБАВЛЕНО: Проверка на попадание в зону выталкивания после шага
                if self._is_in_push_zone(new_x, new_y):
                    # УБРАНО: отладочное сообщение
                    self._pick_target()
                    continue

                if self._check_wall_collision(new_x, new_y):
                    print("⚠️ Шаг ведет к столкновению, выбираем новую цель")
                    self._pick_target()
                    continue

                if not self._shutdown_flag.is_set():
                    self.root.after(0, lambda: self._safe_set_geometry(new_x, new_y))

                elapsed = 0
                while (elapsed < self.MOVE_STEP_DELAY_SEC and
                       self._threads_running and
                       not self._shutdown_flag.is_set()):
                    time.sleep(0.01)
                    elapsed += 0.01

            except Exception as e:
                print(f"Ошибка в движении: {e}")
                break

    # ========== ОБНОВЛЕННЫЙ МЕТОД ПЕРЕТАСКИВАНИЯ ==========

    def _do_drag(self, event):
        """Перетаскивание - персонаж продолжает показывать текущую гифку"""
        if (self.is_dragging and not self._shutdown_flag.is_set() and
                not self._forced_sleep):

            self._record_activity()
            x = self.root.winfo_x() + (event.x - self._drag_start_x)
            y = self.root.winfo_y() + (event.y - self._drag_start_y)

            screen_h = self.root.winfo_screenheight()
            if y > screen_h - self.HEIGHT - self.BOTTOM_MARGIN:
                y = screen_h - self.HEIGHT - self.BOTTOM_MARGIN - 10

            # ДОБАВЛЕНО: Проверка и выталкивание при перетаскивании в зону выталкивания
            if self._is_in_push_zone(x, y):
                x, y = self._apply_push_force(x, y)

            self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, event):
        """Конец перетаскивания - возвращается к обычной анимации"""
        if self._shutdown_flag.is_set() or self._forced_sleep:
            return

        self._record_activity()
        self.is_dragging = False
        self.moving = True

        current_x, current_y = self.root.winfo_x(), self.root.winfo_y()
        screen_h = self.root.winfo_screenheight()

        # ДОБАВЛЕНО: Проверка и выталкивание после окончания перетаскивания
        if self._is_in_push_zone(current_x, current_y):
            new_x, new_y = self._apply_push_force(current_x, current_y)
            self.root.geometry(f"+{new_x}+{new_y}")
            current_x, current_y = new_x, new_y

        if current_y > screen_h - self.HEIGHT - self.BOTTOM_MARGIN:
            new_y = screen_h - self.HEIGHT - self.BOTTOM_MARGIN - 10
            self.root.geometry(f"+{current_x}+{new_y}")

        if self._saved_direction:
            self._load_stand_gif(self._saved_direction)
        else:
            self._load_stand_gif(self.current_direction)

    # ========== ОСТАЛЬНЫЕ МЕТОДЫ (без изменений) ==========

    def _is_gif_disabled(self, gif_key):
        """Проверяет, отключена ли гифка (значение 'none')"""
        if gif_key in self.GIF_PATHS:
            return self.GIF_PATHS[gif_key].lower() == "none"
        return False

    def _get_gif_path(self, gif_key):
        """Возвращает путь к гифке или None если она отключена"""
        if self._is_gif_disabled(gif_key):
            return None
        return os.path.join(self.GIF_FOLDER, self.GIF_PATHS[gif_key])

    def _is_sleep_enabled(self):
        """Проверяет, включена ли функциональность сна"""
        return self.SLEEP_ENABLED

    def _load_sleep_gif(self, direction):
        """Загружает sleep гифку"""
        if self._shutdown_flag.is_set() or not self._is_sleep_enabled():
            return False

        # Если sleep анимация отключена для этого направления, не загружаем её
        if self._is_gif_disabled(f"sleep_{direction}"):
            print(f"⚠️ Sleep анимация {direction} отключена")
            return False

        sleep_path = self._get_gif_path(f"sleep_{direction}")
        if sleep_path and os.path.exists(sleep_path):
            frames = self._load_gif(sleep_path, is_sleep=True)
            if frames:
                self.frames = frames
                self.frame_index = 0
                self.current_gif_path = sleep_path
                self.current_state = "sleep"
                return True
        return False

    def _go_to_sleep(self):
        """Переход в режим сна"""
        if self.is_sleeping or self._shutdown_flag.is_set() or not self._is_sleep_enabled():
            return

        print("😴 Apple Jack засыпает")
        self.is_sleeping = True
        self.moving = False
        self._just_woke_up = False

        self._saved_before_sleep_state = self.current_state
        self._saved_before_sleep_direction = self.current_direction
        self._saved_before_sleep_frames = self.frames.copy()
        self._saved_before_sleep_frame_index = self.frame_index
        self._saved_before_sleep_gif_path = self.current_gif_path
        self._saved_before_sleep_geometry = self.root.geometry()

        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        sleep_x = current_x - (self.SLEEP_WIDTH - self.WIDTH) // 2
        sleep_y = current_y - (self.SLEEP_HEIGHT - self.HEIGHT) // 2

        if not self._shutdown_flag.is_set():
            self.root.geometry(f"{self.SLEEP_WIDTH}x{self.SLEEP_HEIGHT}+{sleep_x}+{sleep_y}")
            self.canvas.config(width=self.SLEEP_WIDTH, height=self.SLEEP_HEIGHT)

        # Пытаемся загрузить sleep гифку только если она не отключена
        sleep_loaded = False
        if not self._is_gif_disabled(f"sleep_{self.current_direction}"):
            sleep_loaded = self._load_sleep_gif(self.current_direction)

        # Если sleep анимация отключена или не загрузилась, создаем fallback
        if not sleep_loaded:
            self._create_sleep_fallback()

    def _wake_up(self):
        """Пробуждение ото сна"""
        if not self.is_sleeping or self._shutdown_flag.is_set() or not self._is_sleep_enabled():
            return

        print("🌅 Apple Jack просыпается")
        self.is_sleeping = False
        self.moving = True
        self._just_woke_up = True
        self._forced_sleep = False

        if self._saved_before_sleep_geometry and not self._shutdown_flag.is_set():
            self.root.geometry(self._saved_before_sleep_geometry)
            self.canvas.config(width=self.WIDTH, height=self.HEIGHT)

        if self._saved_before_sleep_direction:
            self._force_load_stand_gif(self._saved_before_sleep_direction)
        else:
            self._force_load_stand_gif(self.current_direction)

        if not self._shutdown_flag.is_set():
            self.root.after(2000, self._reset_wake_up_flag)

    def _safe_sleep_monitor(self):
        """Безопасная версия монитора сна"""
        while self._threads_running and not self._shutdown_flag.is_set():
            try:
                # Если сон отключен, не мониторим активность
                if not self._is_sleep_enabled():
                    time.sleep(1)
                    continue

                if (not self.is_sleeping and not self.is_dragging and
                        not self._forced_sleep and self._threads_running and
                        not self._shutdown_flag.is_set()):

                    idle_time = time.time() - self.last_activity_time
                    if idle_time >= self.SLEEP_TIMEOUT:
                        self.root.after(0, self._go_to_sleep)

                if self._threads_running and not self._shutdown_flag.is_set():
                    time.sleep(1)
            except Exception as e:
                if self._threads_running and not self._shutdown_flag.is_set():
                    time.sleep(1)

    def _create_context_menu(self):
        """Создает контекстное меню"""
        if self.context_menu:
            self.context_menu.destroy()

        self.context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=self.menu_bg_color,
            fg=self.menu_fg_color,
            font=('Segoe UI', 9),
            relief='flat',
            bd=1,
            activebackground=self.menu_active_bg,
            activeforeground=self.menu_active_fg
        )

        # Показываем кнопку сна/пробуждения только если сон включен
        if self._is_sleep_enabled():
            sleep_wake_label = "💤 Sleep" if not self.is_sleeping else "🌅 Wake Up"
            self.context_menu.add_command(
                label=sleep_wake_label,
                command=self._toggle_sleep_wake,
                background=self.menu_bg_color,
                foreground=self.menu_fg_color
            )
            self.context_menu.add_separator()

        self.context_menu.add_command(
            label="📱 Return to Menu",
            command=self._return_to_main,
            background=self.menu_bg_color,
            foreground=self.menu_fg_color
        )

        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="⛔ Exit Program",
            command=self._exit_program,
            background='#ff4444',
            foreground='white'
        )

        self.context_menu.add_separator()

        state_info = f"Status: {'Sleeping' if self.is_sleeping else 'Active'}"
        if self._forced_sleep:
            state_info += " (Forced)"
        if not self._is_sleep_enabled():
            state_info += " [Sleep Disabled]"

        self.context_menu.add_command(
            label=state_info,
            state='disabled',
            background=self.menu_bg_color,
            foreground='#666666'
        )

    def _toggle_sleep_wake(self):
        """Переключает состояние сна/пробуждения"""
        # Проверяем, включена ли функциональность сна
        if not self._is_sleep_enabled():
            print("⚠️ Функциональность сна отключена")
            return

        if self.is_sleeping:
            print("🌅 Принудительное пробуждение")
            self._forced_sleep = False
            self._wake_up()
        else:
            print("💤 Принудительный переход в сон")
            self._forced_sleep = True
            self._go_to_sleep()

    def _force_load_stand_gif(self, direction):
        """Принудительно загружает stand гифку"""
        if self._shutdown_flag.is_set():
            return False

        stand_path = self._get_gif_path(f"stand_{direction}")
        if stand_path and os.path.exists(stand_path):
            frames = self._load_gif(stand_path)
            if frames:
                self.frames = frames
                self.frame_index = 0
                self.current_gif_path = stand_path
                self.current_state = "idle"
                self.current_direction = direction
                return True

        # Пробуем противоположное направление если текущее отключено
        opposite_direction = "left" if direction == "right" else "right"
        fallback_path = self._get_gif_path(f"stand_{opposite_direction}")
        if fallback_path and os.path.exists(fallback_path):
            frames = self._load_gif(fallback_path)
            if frames:
                self.frames = frames
                self.frame_index = 0
                self.current_gif_path = fallback_path
                self.current_state = "idle"
                self.current_direction = opposite_direction
                return True

        return self._load_any_gif()

    def _load_stand_gif(self, direction):
        """Загружает stand гифку"""
        if self.is_sleeping or self._shutdown_flag.is_set():
            return True

        if self._just_woke_up:
            return self._force_load_stand_gif(direction)

        stand_path = self._get_gif_path(f"stand_{direction}")
        if stand_path and os.path.exists(stand_path):
            if self.current_gif_path == stand_path and self.frames:
                return True

            frames = self._load_gif(stand_path)
            if frames:
                self.frames = frames
                self.frame_index = 0
                self.current_gif_path = stand_path
                self.current_state = "idle"
                self.current_direction = direction
                return True

        opposite_direction = "left" if direction == "right" else "right"
        fallback_path = self._get_gif_path(f"stand_{opposite_direction}")
        if fallback_path and os.path.exists(fallback_path):
            if self.current_gif_path == fallback_path and self.frames:
                return True

            frames = self._load_gif(fallback_path)
            if frames:
                self.frames = frames
                self.frame_index = 0
                self.current_gif_path = fallback_path
                self.current_state = "idle"
                self.current_direction = opposite_direction
                return True

        return self._load_any_gif()

    def _load_direction_gif(self, direction):
        """Загружает гифку движения"""
        if self.is_sleeping or self._shutdown_flag.is_set():
            return True

        if self._just_woke_up:
            return self._load_stand_gif(direction)

        # Проверяем, отключена ли анимация движения для этого направления
        if self._is_gif_disabled(f"move_{direction}"):
            print(f"⚠️ Анимация движения {direction} отключена, используем stand")
            return self._load_stand_gif(direction)

        direction_path = self._get_gif_path(f"move_{direction}")
        if direction_path and os.path.exists(direction_path):
            if self.current_gif_path == direction_path and self.frames:
                return True

            frames = self._load_gif(direction_path)
            if frames:
                self.frames = frames
                self.frame_index = 0
                self.current_gif_path = direction_path
                self.current_state = f"move_{direction}"
                self.current_direction = direction
                return True

        # Если движение отключено или файл не найден, используем stand
        return self._load_stand_gif(direction)

    def _load_drag_gif(self):
        """Загружает drag гифку"""
        if self._shutdown_flag.is_set():
            return False

        # Проверяем, отключена ли drag анимация
        if self._is_gif_disabled("drag"):
            print("⚠️ Drag анимация отключена")
            return False

        drag_path = self._get_gif_path("drag")
        if drag_path and os.path.exists(drag_path):
            frames = self._load_gif(drag_path)
            if frames:
                self.frames = frames
                self.frame_index = 0
                self.current_gif_path = drag_path
                self.current_state = "drag"
                return True
        return False

    def _start_drag(self, event):
        """Начало перетаскивания"""
        if self._shutdown_flag.is_set() or self._forced_sleep:
            return

        self._record_activity()
        self.is_dragging = True
        self.moving = False
        self._drag_start_x = event.x
        self._drag_start_y = event.y

        self._saved_frame_index = self.frame_index
        self._saved_frames = self.frames.copy()
        self._saved_gif_path = self.current_gif_path
        self._saved_state = self.current_state
        self._saved_direction = self.current_direction

        # Загружаем drag гифку только если она не отключена
        if not self._is_gif_disabled("drag"):
            self._load_drag_gif()

    def _get_safe_position(self):
        """Возвращает безопасную позицию на экране"""
        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            x = random.randint(self.SCREEN_MARGIN, screen_w - self.WIDTH - self.SCREEN_MARGIN)
            y = random.randint(self.SCREEN_MARGIN, screen_h - self.HEIGHT - self.BOTTOM_MARGIN)

            # Ограничиваем значения
            x = max(self.SCREEN_MARGIN, min(x, screen_w - self.WIDTH - self.SCREEN_MARGIN))
            y = max(self.SCREEN_MARGIN, min(y, screen_h - self.HEIGHT - self.BOTTOM_MARGIN))

            return x, y
        except:
            return 100, 100

    def _fix_stuck_position(self):
        """Исправляет застревание персонажа"""
        if self._shutdown_flag.is_set():
            return

        try:
            current_x, current_y = self.root.winfo_x(), self.root.winfo_y()

            if self._check_wall_collision(current_x, current_y) or self._is_in_push_zone(current_x, current_y):
                print("🔧 Исправляем застревание...")
                safe_x, safe_y = self._get_safe_position()
                self.root.geometry(f"+{safe_x}+{safe_y}")
                self.target_x, self.target_y = safe_x, safe_y
        except:
            pass

    def _safe_exit_procedure(self):
        """Безопасная процедура выхода"""
        print("🔒 Запуск безопасного выхода...")
        self._shutdown_flag.set()
        self._stop_all_threads()
        self._clear_canvas_completely()
        self.root.after(100, self._final_shutdown)

    def _final_shutdown(self):
        """Финальное завершение"""
        try:
            if self.return_to_main_callback:
                print("✅ Возвращаемся к главному меню")
                self.return_to_main_callback()
            else:
                print("⚠️ Колбэк не установлен, закрываем окно")
                self.root.quit()
                self.root.destroy()
        except Exception as e:
            print(f"❌ Ошибка при завершении: {e}")
            self.root.quit()

    def _check_gif_folder(self):
        """Проверяем и создаем папку с гифками если нужно"""
        print(f"🔍 Проверяем папку с гифками: {self.GIF_FOLDER}")

        if not os.path.exists(self.GIF_FOLDER):
            print(f"📁 Папка не найдена, создаем: {self.GIF_FOLDER}")
            try:
                os.makedirs(self.GIF_FOLDER, exist_ok=True)
                print("✅ Папка создана")
                sleep_folder = os.path.join(self.GIF_FOLDER, "sleep-aj")
                drag_folder = os.path.join(self.GIF_FOLDER, "drag-aj")
                os.makedirs(sleep_folder, exist_ok=True)
                os.makedirs(drag_folder, exist_ok=True)
                print("✅ Подпапки созданы")
            except Exception as e:
                print(f"❌ Ошибка создания папки: {e}")
        else:
            print("✅ Папка с гифками найдена")

    def _setup_window(self):
        """Настройка окна"""
        self.root.overrideredirect(True)
        self.root.wm_attributes("-transparentcolor", "black")
        self.root.wm_attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+100+100")
        self.root.protocol("WM_DELETE_WINDOW", self._safe_exit_procedure)

    def _setup_canvas(self):
        """Настройка canvas"""
        self.canvas = tk.Canvas(
            self.root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack()

    def _bind_events(self):
        """Привязка событий"""
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._do_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<Enter>", self._record_activity)
        self.canvas.bind("<Motion>", self._record_activity)

    def _return_to_main(self):
        """Возвращает к стартовому окну БЕЗ завершения процесса"""
        print("🔄 Возврат к стартовому окну...")
        self._safe_exit_procedure()

    def _exit_program(self):
        """Завершает всю программу"""
        print("🛑 Завершение программы через Apple Jack...")
        self._stop_all_threads()
        self._clear_canvas_completely()
        import sys
        sys.exit(0)

    def _show_context_menu(self, event):
        """Показывает контекстное меню"""
        self._create_context_menu()
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _create_fallback_animation(self):
        """Создание цветной fallback анимации"""
        try:
            print("🎨 Создаем fallback анимацию...")
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
            self.frames = []

            for i, color in enumerate(colors):
                img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                center_x, center_y = self.WIDTH // 2, self.HEIGHT // 2
                radius = min(self.WIDTH, self.HEIGHT) // 3

                draw.ellipse([
                    center_x - radius, center_y - radius,
                    center_x + radius, center_y + radius
                ], fill=color)

                draw.text((center_x - 10, center_y - 5), "AJ", fill="white")
                photo = ImageTk.PhotoImage(img)
                self.frames.append(photo)

            self.frame_index = 0
            self.animating = True
            self.current_state = "idle"
            print("✅ Fallback анимация создана успешно!")
            return True
        except Exception as e:
            print(f"❌ Ошибка создания fallback анимации: {e}")
            return False

    def _create_sleep_fallback(self):
        """Создание fallback для сна"""
        try:
            sleep_colors = ['#1a237e', '#283593', '#303f9f', '#3949ab', '#3f51b5']
            self.frames = []

            for color in sleep_colors:
                img = Image.new('RGBA', (self.SLEEP_WIDTH, self.SLEEP_HEIGHT), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                center_x, center_y = self.SLEEP_WIDTH // 2, self.SLEEP_HEIGHT // 2
                radius = min(self.SLEEP_WIDTH, self.SLEEP_HEIGHT) // 4

                draw.ellipse([
                    center_x - radius, center_y - radius,
                    center_x + radius, center_y + radius
                ], fill=color)

                draw.text((center_x - 15, center_y - 5), "Zzz", fill="white")
                photo = ImageTk.PhotoImage(img)
                self.frames.append(photo)

            self.frame_index = 0
            self.current_state = "sleep"
        except Exception as e:
            print(f"❌ Ошибка создания sleep fallback: {e}")

    def _stop_all_threads(self):
        """Останавливает все потоки более мягко"""
        print("🛑 Мягкая остановка потоков Apple Jack...")
        self._threads_running = False
        self.animating = False
        self.moving = False
        self._shutdown_flag.set()

    def _safe_animate(self):
        """Безопасная версия анимации"""
        while self._threads_running and not self._shutdown_flag.is_set():
            try:
                if (self.frames and self.animating and
                        self._threads_running and not self._shutdown_flag.is_set()):

                    if self.current_state == "sleep":
                        frame_delay = self.SLEEP_FRAME_DURATION_MS / 1000
                    else:
                        frame_delay = self.FRAME_DURATION_MS / 1000

                    if not self._shutdown_flag.is_set():
                        self.root.after(0, self._update_animation_frame)

                    elapsed = 0
                    while (elapsed < frame_delay and
                           self._threads_running and
                           not self._shutdown_flag.is_set()):
                        time.sleep(0.01)
                        elapsed += 0.01
                else:
                    if self._threads_running and not self._shutdown_flag.is_set():
                        time.sleep(0.1)
            except Exception as e:
                if self._threads_running and not self._shutdown_flag.is_set():
                    time.sleep(0.1)

    def _update_animation_frame(self):
        """Потокобезопасное обновление кадра анимации"""
        if (hasattr(self, 'canvas') and self.frames and
                not self._shutdown_flag.is_set()):
            try:
                if not hasattr(self, 'current_image_id'):
                    self.current_image_id = self.canvas.create_image(
                        0, 0, image=self.frames[self.frame_index], anchor="nw"
                    )
                else:
                    self.canvas.itemconfig(self.current_image_id, image=self.frames[self.frame_index])

                self.frame_index = (self.frame_index + 1) % len(self.frames)
            except tk.TclError:
                pass

    def _check_wall_collision(self, x, y):
        """Проверяет столкновение со стенами"""
        if self._shutdown_flag.is_set():
            return False

        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            if (x <= self.SCREEN_MARGIN or
                    x >= screen_w - self.WIDTH - self.SCREEN_MARGIN or
                    y <= self.SCREEN_MARGIN or
                    y >= screen_h - self.HEIGHT - self.BOTTOM_MARGIN):
                return True
            return False
        except tk.TclError:
            return False

    def _pick_target(self):
        """Выбирает новую цель для движения"""
        if self._shutdown_flag.is_set():
            return

        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            x_max = max(self.SCREEN_MARGIN + 1, screen_w - self.WIDTH - self.SCREEN_MARGIN)
            y_max = max(self.SCREEN_MARGIN + 1, screen_h - self.HEIGHT - self.BOTTOM_MARGIN)

            if x_max <= self.SCREEN_MARGIN or y_max <= self.SCREEN_MARGIN:
                self.target_x, self.target_y = self.root.winfo_x(), self.root.winfo_y()
                return

            for attempt in range(10):
                self.target_x = random.randint(self.SCREEN_MARGIN, x_max)
                self.target_y = random.randint(self.SCREEN_MARGIN, y_max)

                # ДОБАВЛЕНО: Проверка, что цель не в зоне выталкивания
                if (not self._check_wall_collision(self.target_x, self.target_y) and
                        not self._is_in_push_zone(self.target_x, self.target_y)):
                    return

            self.target_x = screen_w // 2 - self.WIDTH // 2
            self.target_y = screen_h // 2 - self.HEIGHT // 2

        except (tk.TclError, ValueError):
            self.target_x, self.target_y = self.root.winfo_x(), self.root.winfo_y()

    def _pick_opposite_target(self, current_x, current_y):
        """Выбирает новую цель в противоположном направлении"""
        if self._shutdown_flag.is_set():
            return

        try:
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()

            x_max = max(self.SCREEN_MARGIN + 1, screen_w - self.WIDTH - self.SCREEN_MARGIN)
            y_max = max(self.SCREEN_MARGIN + 1, screen_h - self.HEIGHT - self.BOTTOM_MARGIN)

            if x_max <= self.SCREEN_MARGIN or y_max <= self.SCREEN_MARGIN:
                self.target_x, self.target_y = current_x, current_y
                return

            if self.current_direction == "right":
                min_x = self.SCREEN_MARGIN
                max_x = max(current_x - 50, self.SCREEN_MARGIN)
            else:
                min_x = min(current_x + 50, x_max)
                max_x = x_max

            if min_x > max_x:
                min_x, max_x = max_x, min_x

            for attempt in range(10):
                self.target_x = random.randint(min_x, max_x)
                self.target_y = random.randint(self.SCREEN_MARGIN, y_max)

                # ДОБАВЛЕНО: Проверка, что цель не в зоне выталкивания
                if (not self._check_wall_collision(self.target_x, self.target_y) and
                        not self._is_in_push_zone(self.target_x, self.target_y)):
                    return

            self.target_x = screen_w // 2 - self.WIDTH // 2
            self.target_y = screen_h // 2 - self.HEIGHT // 2

        except (tk.TclError, ValueError):
            self.target_x, self.target_y = current_x, current_y

    def _safe_set_geometry(self, x, y):
        """Потокобезопасная установка геометрии"""
        if not self._shutdown_flag.is_set():
            try:
                self.root.geometry(f"+{x}+{y}")
            except tk.TclError:
                pass

    def _record_activity(self, event=None):
        """Записываем время активности"""
        if not self._forced_sleep and not self._shutdown_flag.is_set():
            self.last_activity_time = time.time()
            if self.is_sleeping:
                self._wake_up()

    def _reset_wake_up_flag(self):
        """Сбрасывает флаг пробуждения"""
        self._just_woke_up = False

    def _load_gif(self, path, is_sleep=False):
        """Загрузка GIF файла"""
        if self._shutdown_flag.is_set():
            return []

        frames = []
        try:
            with Image.open(path) as img:
                target_width = self.SLEEP_WIDTH if is_sleep else self.WIDTH
                target_height = self.SLEEP_HEIGHT if is_sleep else self.HEIGHT

                original_width, original_height = img.size
                scale_x = target_width / original_width
                scale_y = target_height / original_height
                scale = min(scale_x, scale_y)

                new_width = int(original_width * scale)
                new_height = int(original_height * scale)

                offset_x = (target_width - new_width) // 2
                offset_y = (target_height - new_height) // 2

                for i in range(img.n_frames):
                    if self._shutdown_flag.is_set():
                        break
                    img.seek(i)
                    frame = img.convert("RGBA")
                    frame = frame.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    new_frame = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
                    new_frame.paste(frame, (offset_x, offset_y), frame)

                    frames.append(ImageTk.PhotoImage(new_frame))
        except Exception as e:
            print(f"Ошибка загрузки GIF: {e}")
        return frames

    def _load_any_gif(self):
        """Пытается загрузить любую гифку из папки"""
        try:
            if not os.path.exists(self.GIF_FOLDER) or self._shutdown_flag.is_set():
                return False

            files = os.listdir(self.GIF_FOLDER)
            gif_files = [f for f in files if f.lower().endswith('.gif')]

            if gif_files:
                first_gif = os.path.join(self.GIF_FOLDER, gif_files[0])
                if self._just_woke_up:
                    return False

                if self.current_gif_path == first_gif and self.frames:
                    return True

                frames = self._load_gif(first_gif)
                if frames:
                    self.frames = frames
                    self.frame_index = 0
                    self.current_gif_path = first_gif
                    self.current_state = "idle"
                    return True
        except Exception as e:
            print(f"❌ Ошибка при поиске гифок: {e}")

        return False

    def _schedule_change(self):
        if self.animating and not self.is_sleeping and not self._shutdown_flag.is_set():
            self.root.after(2000, self._change_gif)

    def _change_gif(self):
        if (self.animating and not self.is_dragging and
                self.current_state == "idle" and not self.is_sleeping and
                not self._shutdown_flag.is_set()):

            if not self._just_woke_up:
                self._load_stand_gif(self.current_direction)
        if self.animating and not self.is_sleeping and not self._shutdown_flag.is_set():
            self._schedule_change()

    def _clear_canvas_completely(self):
        """Очищает canvas"""
        try:
            if hasattr(self, 'canvas'):
                self.canvas.delete("all")
            self.frames = []
            self.frame_index = 0
            if hasattr(self, 'current_image_id'):
                del self.current_image_id
            import gc
            gc.collect()
        except Exception as e:
            print(f"Ошибка при очистке canvas: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = GIFPlayer(root)
    root.mainloop()