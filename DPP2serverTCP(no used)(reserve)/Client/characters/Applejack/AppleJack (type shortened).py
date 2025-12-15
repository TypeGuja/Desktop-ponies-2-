import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import os
import random
import threading
import time

# THIS CODE DOES NOT WORK WITH SOFTWARE DPP2 AND IS A PROTOTYPE OF THE FOLLOWING

class GIFPlayer:
    def __init__(self, root):
        self.root = root
        self._shutdown_flag = threading.Event()
        self._threads_running = True

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.GIF_FOLDER = os.path.join(current_dir, "AppleJack_Gifct")

        self.GIF_PATHS = {
            "stand_right": "stand_aj_right.gif", "stand_left": "stand_aj_left.gif",
            "move_right": "trotcycle_aj_right.gif", "move_left": "trotcycle_aj_left.gif",
            "sleep_right": os.path.join("sleep-aj", "sleep_right.gif"),
            "sleep_left": os.path.join("sleep-aj", "sleep_left.gif"),
            "drag": os.path.join("drag-aj", "aj-drag-left.gif")
        }

        # Настройки
        self.SLEEP_ENABLED = True
        self.WIDTH, self.HEIGHT = 100, 150
        self.SLEEP_WIDTH, self.SLEEP_HEIGHT = 100, 100
        self.FRAME_DURATION_MS = 100
        self.SLEEP_FRAME_DURATION_MS = 700
        self.MOVE_INTERVAL_MIN, self.MOVE_INTERVAL_MAX = 2, 5
        self.MOVE_SPEED_PX_PER_STEP = 2
        self.MOVE_STEP_DELAY_SEC = 0.06
        self.SCREEN_MARGIN, self.BOTTOM_MARGIN = 10, 10
        self.SLEEP_TIMEOUT = 100
        self.PUSH_ZONE_SIZE, self.PUSH_FORCE = 5, 10

        # Состояния
        self.frames = []
        self.frame_index = 0
        self.current_gif_path = None
        self.is_dragging = self.animating = False
        self.moving = True
        self.target_x = self.target_y = None
        self._drag_start_x, self._drag_start_y = 100, 100
        self.current_direction, self.current_state = "right", "idle"
        self.is_sleeping = self._just_woke_up = self._forced_sleep = False
        self.last_activity_time = time.time()

        # Сохраненные состояния
        self._saved_frames, self._saved_frame_index = [], 0
        self._saved_gif_path, self._saved_state, self._saved_direction = None, "idle", "right"
        self._saved_before_sleep_geometry = None

        # Контекстное меню
        self.context_menu = None
        self.menu_bg_color, self.menu_fg_color = '#2d2d2d', '#ffffff'
        self.menu_active_bg, self.menu_active_fg = '#0078d7', '#ffffff'
        self.return_to_main_callback = None

        self._check_gif_folder()
        self._setup_window()
        self._setup_canvas()
        self._bind_events()

        if not self._load_stand_gif("right"):
            self._create_fallback_animation()
        else:
            self.animating = True

        # Запуск потоков
        for thread_target in [self._safe_animate, self._safe_move_loop, self._safe_sleep_monitor]:
            threading.Thread(target=thread_target, daemon=True).start()
        self._schedule_change()

    def _is_gif_disabled(self, gif_key):
        return gif_key in self.GIF_PATHS and self.GIF_PATHS[gif_key].lower() == "none"

    def _get_gif_path(self, gif_key):
        return None if self._is_gif_disabled(gif_key) else os.path.join(self.GIF_FOLDER, self.GIF_PATHS[gif_key])

    def _is_sleep_enabled(self):
        return self.SLEEP_ENABLED

    def _is_in_push_zone(self, x, y):
        if self._shutdown_flag.is_set():
            return False
        try:
            screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            return (x <= self.PUSH_ZONE_SIZE or
                    x >= screen_w - self.WIDTH - self.PUSH_ZONE_SIZE or
                    y <= self.PUSH_ZONE_SIZE or
                    y >= screen_h - self.HEIGHT - self.BOTTOM_MARGIN - self.PUSH_ZONE_SIZE)
        except tk.TclError:
            return False

    def _get_push_direction(self, x, y):
        if self._shutdown_flag.is_set():
            return None
        try:
            screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            if x <= self.PUSH_ZONE_SIZE:
                return "right"
            elif x >= screen_w - self.WIDTH - self.PUSH_ZONE_SIZE:
                return "left"
            elif y <= self.PUSH_ZONE_SIZE:
                return "down"
            elif y >= screen_h - self.HEIGHT - self.BOTTOM_MARGIN - self.PUSH_ZONE_SIZE:
                return "up"
            return None
        except tk.TclError:
            return None

    def _apply_push_force(self, x, y):
        if self._shutdown_flag.is_set():
            return x, y
        push_direction = self._get_push_direction(x, y)
        if not push_direction:
            return x, y

        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        new_x, new_y = x, y

        if push_direction == "right":
            new_x = self.PUSH_ZONE_SIZE + self.PUSH_FORCE
        elif push_direction == "left":
            new_x = screen_w - self.WIDTH - self.PUSH_ZONE_SIZE - self.PUSH_FORCE
        elif push_direction == "down":
            new_y = self.PUSH_ZONE_SIZE + self.PUSH_FORCE
        elif push_direction == "up":
            new_y = screen_h - self.HEIGHT - self.BOTTOM_MARGIN - self.PUSH_ZONE_SIZE - self.PUSH_FORCE

        new_x = max(self.SCREEN_MARGIN, min(new_x, screen_w - self.WIDTH - self.SCREEN_MARGIN))
        new_y = max(self.SCREEN_MARGIN, min(new_y, screen_h - self.HEIGHT - self.BOTTOM_MARGIN))
        return new_x, new_y

    def _check_and_push_from_edges(self):
        if self._shutdown_flag.is_set() or self.is_dragging or self.is_sleeping:
            return
        try:
            current_x, current_y = self.root.winfo_x(), self.root.winfo_y()
            if self._is_in_push_zone(current_x, current_y):
                new_x, new_y = self._apply_push_force(current_x, current_y)
                if new_x != current_x or new_y != current_y:
                    self.root.geometry(f"+{new_x}+{new_y}")
                    self.target_x, self.target_y = new_x, new_y
        except Exception:
            pass

    def _load_sleep_gif(self, direction):
        if self._shutdown_flag.is_set() or not self._is_sleep_enabled() or self._is_gif_disabled(f"sleep_{direction}"):
            return False
        sleep_path = self._get_gif_path(f"sleep_{direction}")
        if sleep_path and os.path.exists(sleep_path):
            frames = self._load_gif(sleep_path, is_sleep=True)
            if frames:
                self.frames, self.frame_index = frames, 0
                self.current_gif_path, self.current_state = sleep_path, "sleep"
                return True
        return False

    def _go_to_sleep(self):
        if self.is_sleeping or self._shutdown_flag.is_set() or not self._is_sleep_enabled():
            return
        print("😴 Apple Jack засыпает")
        self.is_sleeping, self.moving, self._just_woke_up = True, False, False

        self._saved_before_sleep_state = self.current_state
        self._saved_before_sleep_direction = self.current_direction
        self._saved_before_sleep_frames = self.frames.copy()
        self._saved_before_sleep_frame_index = self.frame_index
        self._saved_before_sleep_gif_path = self.current_gif_path
        self._saved_before_sleep_geometry = self.root.geometry()

        current_x, current_y = self.root.winfo_x(), self.root.winfo_y()
        sleep_x = current_x - (self.SLEEP_WIDTH - self.WIDTH) // 2
        sleep_y = current_y - (self.SLEEP_HEIGHT - self.HEIGHT) // 2

        if not self._shutdown_flag.is_set():
            self.root.geometry(f"{self.SLEEP_WIDTH}x{self.SLEEP_HEIGHT}+{sleep_x}+{sleep_y}")
            self.canvas.config(width=self.SLEEP_WIDTH, height=self.SLEEP_HEIGHT)

        if not self._load_sleep_gif(self.current_direction):
            self._create_sleep_fallback()

    def _wake_up(self):
        if not self.is_sleeping or self._shutdown_flag.is_set() or not self._is_sleep_enabled():
            return
        print("🌅 Apple Jack просыпается")
        self.is_sleeping, self.moving, self._just_woke_up, self._forced_sleep = False, True, True, False

        if self._saved_before_sleep_geometry and not self._shutdown_flag.is_set():
            self.root.geometry(self._saved_before_sleep_geometry)
            self.canvas.config(width=self.WIDTH, height=self.HEIGHT)

        self._force_load_stand_gif(self._saved_before_sleep_direction or self.current_direction)
        if not self._shutdown_flag.is_set():
            self.root.after(2000, self._reset_wake_up_flag)

    def _reset_wake_up_flag(self):
        self._just_woke_up = False

    def _safe_sleep_monitor(self):
        while self._threads_running and not self._shutdown_flag.is_set():
            try:
                if not self._is_sleep_enabled():
                    time.sleep(1)
                    continue
                if (not self.is_sleeping and not self.is_dragging and not self._forced_sleep and
                        self._threads_running and not self._shutdown_flag.is_set()):
                    idle_time = time.time() - self.last_activity_time
                    if idle_time >= self.SLEEP_TIMEOUT:
                        self.root.after(0, self._go_to_sleep)
                time.sleep(1)
            except Exception:
                time.sleep(1)

    def _create_context_menu(self):
        if self.context_menu:
            self.context_menu.destroy()

        self.context_menu = tk.Menu(self.root, tearoff=0, bg=self.menu_bg_color, fg=self.menu_fg_color,
                                    font=('Segoe UI', 9), relief='flat', bd=1,
                                    activebackground=self.menu_active_bg, activeforeground=self.menu_active_fg)

        if self._is_sleep_enabled():
            sleep_wake_label = "💤 Sleep" if not self.is_sleeping else "🌅 Wake Up"
            self.context_menu.add_command(label=sleep_wake_label, command=self._toggle_sleep_wake)
            self.context_menu.add_separator()

        self.context_menu.add_command(label="📱 Return to Menu", command=self._return_to_main)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="⛔ Exit Program", command=self._exit_program, background='#ff4444',
                                      foreground='white')
        self.context_menu.add_separator()

        state_info = f"Status: {'Sleeping' if self.is_sleeping else 'Active'}"
        if self._forced_sleep: state_info += " (Forced)"
        if not self._is_sleep_enabled(): state_info += " [Sleep Disabled]"
        self.context_menu.add_command(label=state_info, state='disabled', foreground='#666666')

    def _toggle_sleep_wake(self):
        if not self._is_sleep_enabled():
            return
        if self.is_sleeping:
            self._forced_sleep = False
            self._wake_up()
        else:
            self._forced_sleep = True
            self._go_to_sleep()

    def _force_load_stand_gif(self, direction):
        if self._shutdown_flag.is_set():
            return False
        for test_dir in [direction, "left" if direction == "right" else "right"]:
            stand_path = self._get_gif_path(f"stand_{test_dir}")
            if stand_path and os.path.exists(stand_path):
                frames = self._load_gif(stand_path)
                if frames:
                    self.frames, self.frame_index = frames, 0
                    self.current_gif_path, self.current_state, self.current_direction = stand_path, "idle", test_dir
                    return True
        return self._load_any_gif()

    def _load_stand_gif(self, direction):
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
                self.frames, self.frame_index = frames, 0
                self.current_gif_path, self.current_state, self.current_direction = stand_path, "idle", direction
                return True
        return self._load_stand_gif("left" if direction == "right" else "right") or self._load_any_gif()

    def _load_direction_gif(self, direction):
        if self.is_sleeping or self._shutdown_flag.is_set():
            return True
        if self._just_woke_up:
            return self._load_stand_gif(direction)
        if self._is_gif_disabled(f"move_{direction}"):
            return self._load_stand_gif(direction)
        direction_path = self._get_gif_path(f"move_{direction}")
        if direction_path and os.path.exists(direction_path):
            if self.current_gif_path == direction_path and self.frames:
                return True
            frames = self._load_gif(direction_path)
            if frames:
                self.frames, self.frame_index = frames, 0
                self.current_gif_path, self.current_state, self.current_direction = direction_path, f"move_{direction}", direction
                return True
        return self._load_stand_gif(direction)

    def _load_drag_gif(self):
        if self._shutdown_flag.is_set() or self._is_gif_disabled("drag"):
            return False
        drag_path = self._get_gif_path("drag")
        if drag_path and os.path.exists(drag_path):
            frames = self._load_gif(drag_path)
            if frames:
                self.frames, self.frame_index = frames, 0
                self.current_gif_path, self.current_state = drag_path, "drag"
                return True
        return False

    def _start_drag(self, event):
        if self._shutdown_flag.is_set() or self._forced_sleep:
            return
        self._record_activity()
        self.is_dragging, self.moving = True, False
        self._drag_start_x, self._drag_start_y = event.x, event.y

        self._saved_frame_index, self._saved_frames = self.frame_index, self.frames.copy()
        self._saved_gif_path, self._saved_state, self._saved_direction = self.current_gif_path, self.current_state, self.current_direction

        if not self._is_gif_disabled("drag"):
            self._load_drag_gif()

    def _get_safe_position(self):
        try:
            screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            x = random.randint(self.SCREEN_MARGIN, screen_w - self.WIDTH - self.SCREEN_MARGIN)
            y = random.randint(self.SCREEN_MARGIN, screen_h - self.HEIGHT - self.BOTTOM_MARGIN)
            return max(self.SCREEN_MARGIN, min(x, screen_w - self.WIDTH - self.SCREEN_MARGIN)), \
                max(self.SCREEN_MARGIN, min(y, screen_h - self.HEIGHT - self.BOTTOM_MARGIN))
        except:
            return 100, 100

    def _fix_stuck_position(self):
        if self._shutdown_flag.is_set():
            return
        try:
            current_x, current_y = self.root.winfo_x(), self.root.winfo_y()
            if self._check_wall_collision(current_x, current_y) or self._is_in_push_zone(current_x, current_y):
                safe_x, safe_y = self._get_safe_position()
                self.root.geometry(f"+{safe_x}+{safe_y}")
                self.target_x, self.target_y = safe_x, safe_y
        except:
            pass

    def _safe_exit_procedure(self):
        self._shutdown_flag.set()
        self._stop_all_threads()
        self._clear_canvas_completely()
        self.root.after(100, self._final_shutdown)

    def _final_shutdown(self):
        try:
            if self.return_to_main_callback:
                self.return_to_main_callback()
            else:
                self.root.quit()
                self.root.destroy()
        except Exception:
            self.root.quit()

    def _check_gif_folder(self):
        if not os.path.exists(self.GIF_FOLDER):
            try:
                os.makedirs(self.GIF_FOLDER, exist_ok=True)
                for subfolder in ["sleep-aj", "drag-aj"]:
                    os.makedirs(os.path.join(self.GIF_FOLDER, subfolder), exist_ok=True)
            except Exception as e:
                print(f"❌ Ошибка создания папки: {e}")

    def _setup_window(self):
        self.root.overrideredirect(True)
        self.root.wm_attributes("-transparentcolor", "black", "-topmost", True)
        self.root.configure(bg="black")
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+100+100")
        self.root.protocol("WM_DELETE_WINDOW", self._safe_exit_procedure)

    def _setup_canvas(self):
        self.canvas = tk.Canvas(self.root, width=self.WIDTH, height=self.HEIGHT, bg="black", highlightthickness=0)
        self.canvas.pack()

    def _bind_events(self):
        for event, handler in [("<ButtonPress-1>", self._start_drag), ("<B1-Motion>", self._do_drag),
                               ("<ButtonRelease-1>", self._end_drag), ("<Button-3>", self._show_context_menu),
                               ("<Enter>", self._record_activity), ("<Motion>", self._record_activity)]:
            self.canvas.bind(event, handler)

    def _return_to_main(self):
        self._safe_exit_procedure()

    def _exit_program(self):
        self._stop_all_threads()
        self._clear_canvas_completely()
        import sys
        sys.exit(0)

    def _show_context_menu(self, event):
        self._create_context_menu()
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _create_fallback_animation(self):
        try:
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
            self.frames = []
            for color in colors:
                img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                center_x, center_y = self.WIDTH // 2, self.HEIGHT // 2
                radius = min(self.WIDTH, self.HEIGHT) // 3
                draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius], fill=color)
                draw.text((center_x - 10, center_y - 5), "AJ", fill="white")
                self.frames.append(ImageTk.PhotoImage(img))
            self.frame_index, self.animating, self.current_state = 0, True, "idle"
            return True
        except Exception as e:
            print(f"❌ Ошибка создания fallback анимации: {e}")
            return False

    def _create_sleep_fallback(self):
        try:
            sleep_colors = ['#1a237e', '#283593', '#303f9f', '#3949ab', '#3f51b5']
            self.frames = []
            for color in sleep_colors:
                img = Image.new('RGBA', (self.SLEEP_WIDTH, self.SLEEP_HEIGHT), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                center_x, center_y = self.SLEEP_WIDTH // 2, self.SLEEP_HEIGHT // 2
                radius = min(self.SLEEP_WIDTH, self.SLEEP_HEIGHT) // 4
                draw.ellipse([center_x - radius, center_y - radius, center_x + radius, center_y + radius], fill=color)
                draw.text((center_x - 15, center_y - 5), "Zzz", fill="white")
                self.frames.append(ImageTk.PhotoImage(img))
            self.frame_index, self.current_state = 0, "sleep"
        except Exception as e:
            print(f"❌ Ошибка создания sleep fallback: {e}")

    def _stop_all_threads(self):
        self._threads_running = self.animating = self.moving = False
        self._shutdown_flag.set()

    def _safe_animate(self):
        while self._threads_running and not self._shutdown_flag.is_set():
            try:
                if self.frames and self.animating and not self._shutdown_flag.is_set():
                    frame_delay = self.SLEEP_FRAME_DURATION_MS / 1000 if self.current_state == "sleep" else self.FRAME_DURATION_MS / 1000
                    if not self._shutdown_flag.is_set():
                        self.root.after(0, self._update_animation_frame)
                    elapsed = 0
                    while elapsed < frame_delay and self._threads_running and not self._shutdown_flag.is_set():
                        time.sleep(0.01)
                        elapsed += 0.01
                else:
                    time.sleep(0.1)
            except Exception:
                time.sleep(0.1)

    def _update_animation_frame(self):
        if hasattr(self, 'canvas') and self.frames and not self._shutdown_flag.is_set():
            try:
                if not hasattr(self, 'current_image_id'):
                    self.current_image_id = self.canvas.create_image(0, 0, image=self.frames[self.frame_index],
                                                                     anchor="nw")
                else:
                    self.canvas.itemconfig(self.current_image_id, image=self.frames[self.frame_index])
                self.frame_index = (self.frame_index + 1) % len(self.frames)
            except tk.TclError:
                pass

    def _safe_move_loop(self):
        while self._threads_running and not self._shutdown_flag.is_set():
            try:
                if self.moving and not self.is_dragging and self.animating and not self.is_sleeping:
                    if random.random() < 0.1:
                        self.root.after(0, self._fix_stuck_position)
                    self.root.after(0, self._check_and_push_from_edges)
                    if self._just_woke_up:
                        time.sleep(1)
                    self._pick_target()
                    self._safe_move_to_target()
                delay = random.uniform(self.MOVE_INTERVAL_MIN, self.MOVE_INTERVAL_MAX)
                elapsed = 0
                while elapsed < delay and self._threads_running and not self._shutdown_flag.is_set():
                    time.sleep(0.1)
                    elapsed += 0.1
            except Exception:
                time.sleep(1)

    def _check_wall_collision(self, x, y):
        if self._shutdown_flag.is_set():
            return False
        try:
            screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            return (x <= self.SCREEN_MARGIN or x >= screen_w - self.WIDTH - self.SCREEN_MARGIN or
                    y <= self.SCREEN_MARGIN or y >= screen_h - self.HEIGHT - self.BOTTOM_MARGIN)
        except tk.TclError:
            return False

    def _pick_target(self):
        if self._shutdown_flag.is_set():
            return
        try:
            screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            x_max = max(self.SCREEN_MARGIN + 1, screen_w - self.WIDTH - self.SCREEN_MARGIN)
            y_max = max(self.SCREEN_MARGIN + 1, screen_h - self.HEIGHT - self.BOTTOM_MARGIN)

            for _ in range(10):
                self.target_x = random.randint(self.SCREEN_MARGIN, x_max)
                self.target_y = random.randint(self.SCREEN_MARGIN, y_max)
                if not self._check_wall_collision(self.target_x, self.target_y) and not self._is_in_push_zone(
                        self.target_x, self.target_y):
                    return

            self.target_x, self.target_y = screen_w // 2 - self.WIDTH // 2, screen_h // 2 - self.HEIGHT // 2
        except (tk.TclError, ValueError):
            self.target_x, self.target_y = self.root.winfo_x(), self.root.winfo_y()

    def _pick_opposite_target(self, current_x, current_y):
        if self._shutdown_flag.is_set():
            return
        try:
            screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            x_max = max(self.SCREEN_MARGIN + 1, screen_w - self.WIDTH - self.SCREEN_MARGIN)
            y_max = max(self.SCREEN_MARGIN + 1, screen_h - self.HEIGHT - self.BOTTOM_MARGIN)

            if self.current_direction == "right":
                min_x, max_x = self.SCREEN_MARGIN, max(current_x - 50, self.SCREEN_MARGIN)
            else:
                min_x, max_x = min(current_x + 50, x_max), x_max

            for _ in range(10):
                self.target_x = random.randint(min_x, max_x)
                self.target_y = random.randint(self.SCREEN_MARGIN, y_max)
                if not self._check_wall_collision(self.target_x, self.target_y) and not self._is_in_push_zone(
                        self.target_x, self.target_y):
                    return

            self.target_x, self.target_y = screen_w // 2 - self.WIDTH // 2, screen_h // 2 - self.HEIGHT // 2
        except (tk.TclError, ValueError):
            self.target_x, self.target_y = current_x, current_y

    def _safe_move_to_target(self):
        while (self.moving and not self.is_dragging and self.animating and not self.is_sleeping and
               self._threads_running and not self._shutdown_flag.is_set()):
            try:
                if self._shutdown_flag.is_set():
                    break

                current_x, current_y = self.root.winfo_x(), self.root.winfo_y()

                if self._is_in_push_zone(current_x, current_y):
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
                    new_direction = "left" if self.current_direction == "right" else "right"
                    self.current_direction = new_direction
                    self._pick_opposite_target(current_x, current_y)
                    self._load_stand_gif(new_direction)
                    continue

                new_direction = "right" if self.target_x > current_x else "left"
                if new_direction != self.current_direction or self.current_state == "idle":
                    self.current_direction = new_direction
                    self._load_direction_gif(new_direction)

                dx = min(self.MOVE_SPEED_PX_PER_STEP, self.target_x - current_x) if current_x < self.target_x else -min(
                    self.MOVE_SPEED_PX_PER_STEP, current_x - self.target_x)
                dy = min(self.MOVE_SPEED_PX_PER_STEP, self.target_y - current_y) if current_y < self.target_y else -min(
                    self.MOVE_SPEED_PX_PER_STEP, current_y - self.target_y)

                new_x, new_y = current_x + dx, current_y + dy

                if self._is_in_push_zone(new_x, new_y) or self._check_wall_collision(new_x, new_y):
                    self._pick_target()
                    continue

                if not self._shutdown_flag.is_set():
                    self.root.after(0, lambda: self._safe_set_geometry(new_x, new_y))

                elapsed = 0
                while elapsed < self.MOVE_STEP_DELAY_SEC and self._threads_running and not self._shutdown_flag.is_set():
                    time.sleep(0.01)
                    elapsed += 0.01
            except Exception:
                break

    def _safe_set_geometry(self, x, y):
        if not self._shutdown_flag.is_set():
            try:
                self.root.geometry(f"+{x}+{y}")
            except tk.TclError:
                pass

    def _do_drag(self, event):
        if self.is_dragging and not self._shutdown_flag.is_set() and not self._forced_sleep:
            self._record_activity()
            x = self.root.winfo_x() + (event.x - self._drag_start_x)
            y = self.root.winfo_y() + (event.y - self._drag_start_y)

            screen_h = self.root.winfo_screenheight()
            if y > screen_h - self.HEIGHT - self.BOTTOM_MARGIN:
                y = screen_h - self.HEIGHT - self.BOTTOM_MARGIN - 10

            if self._is_in_push_zone(x, y):
                x, y = self._apply_push_force(x, y)

            self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, event):
        if self._shutdown_flag.is_set() or self._forced_sleep:
            return
        self._record_activity()
        self.is_dragging, self.moving = False, True

        current_x, current_y = self.root.winfo_x(), self.root.winfo_y()
        screen_h = self.root.winfo_screenheight()

        if self._is_in_push_zone(current_x, current_y):
            new_x, new_y = self._apply_push_force(current_x, current_y)
            self.root.geometry(f"+{new_x}+{new_y}")
            current_x, current_y = new_x, new_y

        if current_y > screen_h - self.HEIGHT - self.BOTTOM_MARGIN:
            self.root.geometry(f"+{current_x}+{screen_h - self.HEIGHT - self.BOTTOM_MARGIN - 10}")

        self._load_stand_gif(self._saved_direction or self.current_direction)

    def _record_activity(self, event=None):
        if not self._forced_sleep and not self._shutdown_flag.is_set():
            self.last_activity_time = time.time()
            if self.is_sleeping:
                self._wake_up()

    def _load_gif(self, path, is_sleep=False):
        if self._shutdown_flag.is_set():
            return []
        frames = []
        try:
            with Image.open(path) as img:
                target_width, target_height = (self.SLEEP_WIDTH, self.SLEEP_HEIGHT) if is_sleep else (self.WIDTH,
                                                                                                      self.HEIGHT)
                original_width, original_height = img.size
                scale = min(target_width / original_width, target_height / original_height)
                new_width, new_height = int(original_width * scale), int(original_height * scale)
                offset_x, offset_y = (target_width - new_width) // 2, (target_height - new_height) // 2

                for i in range(img.n_frames):
                    if self._shutdown_flag.is_set():
                        break
                    img.seek(i)
                    frame = img.convert("RGBA").resize((new_width, new_height), Image.Resampling.LANCZOS)
                    new_frame = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
                    new_frame.paste(frame, (offset_x, offset_y), frame)
                    frames.append(ImageTk.PhotoImage(new_frame))
        except Exception as e:
            print(f"Ошибка загрузки GIF: {e}")
        return frames

    def _load_any_gif(self):
        try:
            if not os.path.exists(self.GIF_FOLDER) or self._shutdown_flag.is_set():
                return False
            gif_files = [f for f in os.listdir(self.GIF_FOLDER) if f.lower().endswith('.gif')]
            if gif_files:
                first_gif = os.path.join(self.GIF_FOLDER, gif_files[0])
                if self._just_woke_up or (self.current_gif_path == first_gif and self.frames):
                    return False if self._just_woke_up else True
                frames = self._load_gif(first_gif)
                if frames:
                    self.frames, self.frame_index = frames, 0
                    self.current_gif_path, self.current_state = first_gif, "idle"
                    return True
        except Exception as e:
            print(f"❌ Ошибка при поиске гифок: {e}")
        return False

    def _schedule_change(self):
        if self.animating and not self.is_sleeping and not self._shutdown_flag.is_set():
            self.root.after(2000, self._change_gif)

    def _change_gif(self):
        if (self.animating and not self.is_dragging and self.current_state == "idle" and
                not self.is_sleeping and not self._shutdown_flag.is_set() and not self._just_woke_up):
            self._load_stand_gif(self.current_direction)
        if self.animating and not self.is_sleeping and not self._shutdown_flag.is_set():
            self._schedule_change()

    def _clear_canvas_completely(self):
        try:
            if hasattr(self, 'canvas'):
                self.canvas.delete("all")
            self.frames, self.frame_index = [], 0
            if hasattr(self, 'current_image_id'):
                del self.current_image_id
            import gc
            gc.collect()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = GIFPlayer(root)
    root.mainloop()