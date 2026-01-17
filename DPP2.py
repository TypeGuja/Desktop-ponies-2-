import tkinter as tk
from tkinter import ttk
import os
import subprocess
import threading
import time
import json
from PIL import Image, ImageTk


class DynamicPonySelector:
    def __init__(self, root):
        self.root = root
        self.root.title("DPP2 - Pony Selector") # здесь надо будет доделать интерфейс + сделать возможность листать страницу колёсиком мыши
        self.root.geometry("520x500")
        self.root.minsize(300, 400)

        # Флаг для отслеживания состояния
        self.should_exit = False

        # Конфигурационный файл
        self.config_file = "theme_config.json"

        # Загружаем сохраненную тему или используем значения по умолчанию
        saved_theme = self.load_theme()

        # Текущая цветовая схема
        self.current_bg = saved_theme.get('bg_color', '#000000')
        self.current_card_bg = saved_theme.get('card_color', '#454545')
        self.current_text_color = saved_theme.get('text_color', 'white')
        self.current_theme_name = saved_theme.get('theme_name', 'black')

        # Настройки масштаба пони
        self.current_scale = saved_theme.get('pony_scale', 0.95)
        self.scale_options = [0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0,
                              1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5, 1.55, 1.6, 1.65, 1.7, 1.75, 1.8,
                              1.85, 1.9, 1.95, 2.0]

        # Настройки цвета контекстного меню
        self.menu_bg_color = saved_theme.get('menu_bg_color', '#2d2d2d')
        self.menu_fg_color = saved_theme.get('menu_fg_color', '#ffffff')
        self.menu_active_bg = saved_theme.get('menu_active_bg', '#0078d7')
        self.menu_active_fg = saved_theme.get('menu_active_fg', '#ffffff')

        # Список персонажей (имена пони)
        self.pony_names = [
            "Twilight Sparkle", "Rainbow Dash", "Pinkie Pie", "Apple Jack",
            "Fluttershy", "Rarity", "Trixie", "Starlight", "Sunset",
            "Cadance","Celestia", "Luna"
        ]

        # Карточки с GIF превью
        self.pony_gifs = {
            "Twilight Sparkle": "twilight.gif",
            "Rainbow Dash": "rainbow.gif",
            "Pinkie Pie": "pinkie.gif",
            "Apple Jack": "applejack.gif",
            "Fluttershy": "fluttershy.gif",
            "Rarity": "rarity.gif",
            "Cadance": "cadance.gif",
            "Celestia": "celestia.gif",
            "Luna": "luna.gif"
        }

        self.check_vars = {}
        self.card_width = 150
        self.card_height = 120
        self.padding = 5
        self.running_processes = {}

        # Словарь для хранения анимаций гифок
        self.gif_labels = {}
        self.gif_frames = {}

        # Переменные для управления dropdown
        self.dropdown_open = False
        self.options_window = None

        # Счетчик активных пони
        self.active_ponies_count = 0
        # Флаг для отслеживания состояния главного окна
        self.main_window_hidden = False

        # Сначала настраиваем UI с загруженной темой
        self.root.configure(bg=self.current_bg)
        self.setup_ui()
        self.root.bind('<Configure>', self.on_resize)

        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        # Запускаем монитор для проверки активных процессов
        self.monitor_thread = threading.Thread(target=self._monitor_processes, daemon=True)
        self.monitor_thread.start()

    def load_gif_frames(self, gif_path):
        """Загружает кадры GIF-файла"""
        try:
            if not os.path.exists(gif_path):
                print(f"[ERROR] GIF файл не найден: {gif_path}")
                return None

            gif = Image.open(gif_path)
            frames = []

            try:
                while True:
                    frame = gif.copy()
                    # Масштабируем кадр под размер карточки
                    frame = frame.resize((self.card_width - 10, 80), Image.Resampling.LANCZOS)
                    frames.append(ImageTk.PhotoImage(frame))
                    gif.seek(len(frames))  # Переход к следующему кадру
            except EOFError:
                pass

            return frames
        except Exception as e:
            print(f"[ERROR] Ошибка загрузки GIF {gif_path}: {e}")
            return None

    def animate_gif(self, pony_name, label, frames, frame_index=0):
        """Анимирует GIF в метке"""
        if pony_name not in self.gif_labels:
            return

        # Обновляем кадр
        if frames:
            label.configure(image=frames[frame_index])

            # Следующий кадр
            next_index = (frame_index + 1) % len(frames)

            # Запускаем следующий кадр через 100 мс
            self.root.after(100, lambda: self.animate_gif(pony_name, label, frames, next_index))

    def load_theme(self):
        """Загружает сохраненную тему из файла конфигурации"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"[INFO] Загружена сохраненная тема: {config.get('theme_name', 'default')}")
                    return config
            else:
                print("[INFO] Файл конфигурации не найден, используются значения по умолчанию")
        except Exception as e:
            print(f"[ERROR] Ошибка загрузки темы: {e}")

        # Возвращаем значения по умолчанию для черной темы
        return {
            'bg_color': '#000000',
            'card_color': '#454545',
            'text_color': 'white',
            'theme_name': 'black',
            'menu_bg_color': '#2d2d2d',
            'menu_fg_color': '#ffffff',
            'menu_active_bg': '#0078d7',
            'menu_active_fg': '#ffffff',
            'pony_scale': 1.0
        }

    def save_theme(self):
        """Сохраняет текущую тему в файл конфигурации"""
        try:
            config = {
                'bg_color': self.current_bg,
                'card_color': self.current_card_bg,
                'text_color': self.current_text_color,
                'theme_name': self.current_theme_name,
                'menu_bg_color': self.menu_bg_color,
                'menu_fg_color': self.menu_fg_color,
                'menu_active_bg': self.menu_active_bg,
                'menu_active_fg': self.menu_active_fg,
                'pony_scale': self.current_scale
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            print(f"[SUCCESS] Тема '{self.current_theme_name}' сохранена в конфигурацию")
        except Exception as e:
            print(f"[ERROR] Ошибка сохранения темы: {e}")

    def setup_ui(self):
        # Главный заголовок
        self.title_label = tk.Label(
            self.root,
            text="",
            font=('Arial', 16, 'bold'),
            fg=self.current_text_color,
            bg=self.current_bg
        )
        self.title_label.pack(pady=10)

        # Контейнер для карточек с прокруткой
        self.container = tk.Frame(self.root, bg=self.current_bg)
        self.container.pack(fill='both', expand=True, padx=10)

        # Canvas для прокрутки
        self.canvas = tk.Canvas(self.container, bg=self.current_bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.container, orient='vertical', command=self.canvas.yview)

        self.scrollable_frame = tk.Frame(self.canvas, bg=self.current_bg)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Упаковка
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Фрейм для кнопок внизу
        self.button_frame = tk.Frame(self.root, bg=self.current_bg)
        self.button_frame.pack(fill='x', padx=10, pady=10)

        # Кнопка options
        self.options_btn = tk.Button(
            self.button_frame,
            text="options",
            command=self.show_options,
            font=('Arial', 12, 'bold'),
            bg=self.current_card_bg,
            fg=self.current_text_color,
            padx=20,
            pady=5,
            relief='flat',
            bd=0,
            highlightthickness=0
        )
        self.options_btn.pack(side='left')

        # Кнопка start в правом углу
        self.select_btn = tk.Button(
            self.button_frame,
            text="start",
            command=self.launch_selected,
            font=('Arial', 12, 'bold'),
            bg=self.current_card_bg,
            fg=self.current_text_color,
            padx=30,
            pady=5,
            relief='flat',
            bd=0,
            highlightthickness=0
        )
        self.select_btn.pack(side='right')

        # Кнопка stop всех пони
        self.stop_btn = tk.Button(
            self.button_frame,
            text="stop all",
            command=self.stop_all,
            font=('Arial', 12, 'bold'),
            bg='#ff4444',
            fg='white',
            padx=20,
            pady=5,
            relief='flat',
            bd=0,
            highlightthickness=0
        )
        self.stop_btn.pack(side='right', padx=10)

        # Первоначальное размещение
        self.update_layout()

    def exit_app(self):
        """Завершает программу полностью"""
        print("[EXIT] Завершение программы...")
        self.should_exit = True
        self.stop_all()  # Сначала останавливаем всех пони
        # Очищаем GIF анимации
        self.gif_labels.clear()
        self.gif_frames.clear()
        self.root.quit()
        self.root.destroy()

    def calculate_columns(self):
        """Вычисляет количество колонок в зависимости от ширина окна"""
        container_width = self.container.winfo_width()
        if container_width < 300:
            return 2

        available_width = container_width - 20
        columns = max(2, available_width // (self.card_width + self.padding * 2))
        return min(columns, 6)

    def update_layout(self):
        """Обновляет расположение карточек"""
        # Сохраняем текущие состояния чекбоксов
        saved_states = {}
        for pony_name in self.pony_names:
            if pony_name in self.check_vars:
                saved_states[pony_name] = self.check_vars[pony_name].get()

        # Очищаем старые виджеты и анимации
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.gif_labels.clear()
        self.gif_frames.clear()

        columns = self.calculate_columns()

        for i, pony_name in enumerate(self.pony_names):
            row = i // columns
            col = i % columns
            self.create_pony_card(self.scrollable_frame, pony_name, row, col)

        # Восстанавливаем состояния чекбоксов
        for pony_name, state in saved_states.items():
            if pony_name in self.check_vars:
                self.check_vars[pony_name].set(state)

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def create_pony_card(self, parent, pony_name, row, col):
        """Создает карточку персонажа с GIF-анимацией"""
        card_frame = tk.Frame(
            parent,
            bg=self.current_card_bg,
            relief='solid',
            bd=1,
            width=self.card_width,
            height=self.card_height
        )
        card_frame.grid(row=row, column=col, padx=self.padding, pady=self.padding, sticky='nw')
        card_frame.pack_propagate(False)

        inner_frame = tk.Frame(card_frame, bg=self.current_card_bg)
        inner_frame.pack(fill='both', expand=True, padx=3, pady=3)

        # Фрейм для GIF
        gif_frame = tk.Frame(inner_frame, bg=self.current_card_bg, height=90)
        gif_frame.pack(fill='x', pady=(0, 3))
        gif_frame.pack_propagate(False)

        # Пытаемся загрузить и показать GIF
        gif_filename = self.pony_gifs.get(pony_name, "placeholder.gif")
        gif_path = os.path.join("pony_previews", gif_filename)  # Папка с превью

        # Загружаем кадры GIF
        frames = self.load_gif_frames(gif_path)

        if frames:
            # Создаем метку для GIF
            gif_label = tk.Label(
                gif_frame,
                image=frames[0],
                bg=self.current_card_bg
            )
            gif_label.pack(expand=True)

            # Сохраняем ссылки на метку и кадры
            self.gif_labels[pony_name] = gif_label
            self.gif_frames[pony_name] = frames

            # Запускаем анимацию
            self.animate_gif(pony_name, gif_label, frames)
        else:
            # Fallback: показываем placeholder если GIF не найден
            if self.current_theme_name == "white":
                gif_bg_color = '#3498db'  # Синий для белой темы
            elif self.current_theme_name == "gray":
                gif_bg_color = '#27ae60'  # Зеленый для серой темы
            else:  # black
                gif_bg_color = '#1abc9c'  # Бирюзовый для черной темы

            placeholder_label = tk.Label(
                gif_frame,
                text="[GIF]",
                bg=gif_bg_color,
                fg='white',
                font=('Arial', 7)
            )
            placeholder_label.pack(expand=True)

        # Фрейм для имени и чекбокса
        name_check_frame = tk.Frame(inner_frame, bg=self.current_card_bg, height=20)
        name_check_frame.pack(fill='x', pady=1)
        name_check_frame.pack_propagate(False)

        # Имя персонажа
        name_label = tk.Label(
            name_check_frame,
            text=pony_name,
            font=('Arial', 8, 'bold'),
            fg=self.current_text_color,
            bg=self.current_card_bg,
            anchor='w'
        )
        name_label.pack(side='left', fill='x', expand=True)

        # Чекбокс в правом углу
        if pony_name not in self.check_vars:
            self.check_vars[pony_name] = tk.BooleanVar()

        check = tk.Checkbutton(
            name_check_frame,
            variable=self.check_vars[pony_name],
            bg=self.current_card_bg,
            fg=self.current_text_color,
            selectcolor=self.current_card_bg,
            activebackground=self.current_card_bg,
            activeforeground=self.current_text_color,
            relief='flat',
            bd=0,
            highlightthickness=0
        )
        check.pack(side='right')

    def on_resize(self, event):
        """Обработчик изменения размера окна"""
        if event.widget == self.root:
            self.root.after(100, self.update_layout)

    def show_options(self):
        """Показывает окно опций с выпадающим списком тем и ползунком масштаба"""
        # Закрываем предыдущее окно опций если оно открыто
        if hasattr(self, 'options_window') and self.options_window and self.options_window.winfo_exists():
            self.options_window.destroy()

        self.options_window = tk.Toplevel(self.root)
        self.options_window.title("Options")
        self.options_window.geometry("350x320")
        self.options_window.configure(bg=self.current_bg)
        self.options_window.resizable(False, False)

        # Центрируем окно относительно главного
        self.options_window.transient(self.root)
        self.options_window.grab_set()

        # Центрирование окна
        self.options_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - self.options_window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - self.options_window.winfo_height()) // 2
        self.options_window.geometry(f"+{x}+{y}")

        # Основной контейнер
        main_frame = tk.Frame(self.options_window, bg=self.current_bg)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Раздел Color Theme
        theme_section = tk.LabelFrame(main_frame, text=" Color Theme ", font=('Arial', 11, 'bold'),
                                      fg=self.current_text_color, bg=self.current_bg, bd=1, relief='solid')
        theme_section.pack(fill='x', pady=(0, 15))

        # Фрейм для выпадающего списка
        dropdown_frame = tk.Frame(theme_section, bg=self.current_bg)
        dropdown_frame.pack(fill='x', pady=15, padx=10)

        # Создаем кастомный выпадающий список для темы
        self.create_theme_dropdown(dropdown_frame)

        # Раздел Pony Scale
        scale_section = tk.LabelFrame(main_frame, text=" Pony Scale ", font=('Arial', 11, 'bold'),
                                      fg=self.current_text_color, bg=self.current_bg, bd=1, relief='solid')
        scale_section.pack(fill='x', pady=(0, 15))

        # Фрейм для ползунка масштаба
        scale_slider_frame = tk.Frame(scale_section, bg=self.current_bg)
        scale_slider_frame.pack(fill='x', pady=15, padx=10)

        # Создаем кастомный ползунок для масштаба
        self.create_scale_slider(scale_slider_frame)

        # Кнопка применения масштаба к запущенным пони
        apply_scale_btn = tk.Button(
            main_frame,
            text="Apply Scale to Running Ponies",
            command=self.apply_scale_to_running_ponies,
            font=('Arial', 10),
            bg=self.current_card_bg,
            fg=self.current_text_color,
            padx=15,
            pady=8,
            relief='flat',
            bd=0,
            highlightthickness=0
        )
        apply_scale_btn.pack(fill='x', pady=(10, 0))

    def create_theme_dropdown(self, parent):
        """Создает кастомный выпадающий список для темы"""
        # Цвета для dropdown в зависимости от темы
        if self.current_theme_name == "white":
            dropdown_bg = '#e0e0e0'
            dropdown_fg = '#000000'
            option_bg = '#f0f0f0'
            option_hover = '#d0d0d0'
        elif self.current_theme_name == "gray":
            dropdown_bg = '#606060'
            dropdown_fg = '#ffffff'
            option_bg = '#707070'
            option_hover = '#808080'
        else:  # black
            dropdown_bg = '#333333'
            dropdown_fg = '#ffffff'
            option_bg = '#444444'
            option_hover = '#555555'

        # Основной фрейм для dropdown
        dropdown_main = tk.Frame(parent, bg=dropdown_bg, relief='solid', bd=1)
        dropdown_main.pack(fill='x')

        # Верхняя часть - выбранный элемент и стрелка
        dropdown_header = tk.Frame(dropdown_main, bg=dropdown_bg, height=30)
        dropdown_header.pack(fill='x')
        dropdown_header.pack_propagate(False)

        # Выбранный цвет - используем переменную для хранения текущей темы
        self.selected_color_var = tk.StringVar(value=self.current_theme_name)

        selected_label = tk.Label(
            dropdown_header,
            textvariable=self.selected_color_var,
            font=('Arial', 10),
            fg=dropdown_fg,
            bg=dropdown_bg,
            anchor='w'
        )
        selected_label.pack(side='left', padx=8, fill='x', expand=True)

        # Стрелка (символ ▼)
        self.arrow_label = tk.Label(
            dropdown_header,
            text="▼",
            font=('Arial', 10),
            fg=dropdown_fg,
            bg=dropdown_bg
        )
        self.arrow_label.pack(side='right', padx=8)

        # Список вариантов (изначально скрыт)
        self.options_frame = tk.Frame(dropdown_main, bg=option_bg)

        # Три темы: black, gray, white
        themes = [
            ("black", "#000000", "#454545", "white"),
            ("gray", "#808080", "#A0A0A0", "black"),
            ("white", "#FFFFFF", "#E0E0E0", "black")
        ]

        for color_name, bg_color, card_color, text_color in themes:
            color_option = tk.Frame(self.options_frame, bg=option_bg, height=30)
            color_option.pack(fill='x')
            color_option.pack_propagate(False)

            color_btn = tk.Label(
                color_option,
                text=color_name,
                font=('Arial', 10),
                fg=dropdown_fg,
                bg=option_bg,
                anchor='w',
                cursor='hand2'
            )
            color_btn.pack(fill='x', padx=8)

            # Привязываем события мыши
            color_btn.bind('<Button-1>',
                           lambda e, bg=bg_color, card=card_color, text=text_color, name=color_name:
                           self.select_theme(bg, card, text, name))

            color_btn.bind('<Enter>', lambda e, btn=color_btn: btn.configure(bg=option_hover))
            color_btn.bind('<Leave>', lambda e, btn=color_btn: btn.configure(bg=option_bg))

        # Обработчик клика по заголовку для показа/скрытия списка
        def toggle_dropdown(event):
            if self.options_frame.winfo_ismapped():
                self.options_frame.pack_forget()
                self.arrow_label.configure(text="▼")
                self.dropdown_open = False
            else:
                self.options_frame.pack(fill='x')
                self.arrow_label.configure(text="▲")
                self.dropdown_open = True

        # Привязываем обработчик ко всему заголовку
        dropdown_header.bind('<Button-1>', toggle_dropdown)
        selected_label.bind('<Button-1>', toggle_dropdown)
        self.arrow_label.bind('<Button-1>', toggle_dropdown)

    def create_scale_slider(self, parent):
        """Создает ползунок для масштаба пони с процентами"""
        # Цвета в зависимости от темы
        if self.current_theme_name == "white":
            bg_color = '#f0f0f0'
            fg_color = '#000000'
            trough_color = '#c0c0c0'
            active_color = '#0078d7'
            mark_color = '#a0a0a0'
        elif self.current_theme_name == "gray":
            bg_color = '#707070'
            fg_color = '#ffffff'
            trough_color = '#909090'
            active_color = '#0078d7'
            mark_color = '#b0b0b0'
        else:  # black
            bg_color = '#444444'
            fg_color = '#ffffff'
            trough_color = '#666666'
            active_color = '#0078d7'
            mark_color = '#888888'

        # Основной контейнер
        container = tk.Frame(parent, bg=bg_color)
        container.pack(fill='x', pady=5)

        # Метка с текущим значением
        scale_percent = int(self.current_scale * 100)
        self.scale_label = tk.Label(
            container,
            text=f"Scale: {scale_percent}%",
            font=('Arial', 10, 'bold'),
            fg=fg_color,
            bg=bg_color
        )
        self.scale_label.pack(pady=(0, 5))

        # Слайдер
        slider_frame = tk.Frame(container, bg=bg_color)
        slider_frame.pack(fill='x', pady=5)

        # Находим индекс текущего значения
        current_index = 0
        if self.current_scale in self.scale_options:
            current_index = self.scale_options.index(self.current_scale)
        else:
            # Находим ближайшее значение
            closest_val = min(self.scale_options, key=lambda x: abs(x - self.current_scale))
            current_index = self.scale_options.index(closest_val)
            self.current_scale = closest_val

        # Создаем ползунок
        self.scale_slider = tk.Scale(
            slider_frame,
            from_=0,
            to=len(self.scale_options) - 1,
            orient='horizontal',
            length=250,
            showvalue=0,
            bg=bg_color,
            fg=fg_color,
            troughcolor=trough_color,
            activebackground=active_color,
            highlightthickness=0,
            sliderrelief='flat',
            resolution=1
        )
        self.scale_slider.set(current_index)
        self.scale_slider.pack(fill='x', padx=5)

        # Обработчик движения ползунка
        def on_slider_move(val):
            try:
                index = int(float(val))
                if 0 <= index < len(self.scale_options):
                    self.current_scale = self.scale_options[index]
                    scale_percent = int(self.current_scale * 100)
                    self.scale_label.config(text=f"Scale: {scale_percent}%")
            except Exception as e:
                print(f"[ERROR] Ошибка движения ползунка: {e}")

        self.scale_slider.config(command=on_slider_move)

        # Метки под слайдером
        marks_frame = tk.Frame(container, bg=bg_color)
        marks_frame.pack(fill='x', pady=(5, 0))

        # Показываем ключевые значения в процентах
        key_values = [0.25, 0.5, 1.0, 1.5, 2.0]

        for value in key_values:
            if value in self.scale_options:
                index = self.scale_options.index(value)
                total = len(self.scale_options) - 1
                position = (index / total) * 100 if total > 0 else 0

                # Преобразуем в проценты
                percent_value = int(value * 100)

                label = tk.Label(
                    marks_frame,
                    text=f"{percent_value}%",
                    font=('Arial', 8),
                    fg=mark_color,
                    bg=bg_color
                )
                label.place(relx=position / 100, x=-10, anchor='n')

        # Автоматическое сохранение при отпускании
        def save_on_release(event):
            self.save_theme()
            scale_percent = int(self.current_scale * 100)
            print(f"[SUCCESS] Масштаб сохранен: {scale_percent}%")

        self.scale_slider.bind('<ButtonRelease-1>', save_on_release)

        return self.scale_slider

    def select_theme(self, bg_color, card_color, text_color, theme_name=None):
        """Выбирает тему из dropdown"""
        self.selected_color_var.set(theme_name)

        # Закрываем dropdown
        if self.dropdown_open:
            self.options_frame.pack_forget()
            self.arrow_label.configure(text="▼")
            self.dropdown_open = False

        self.change_theme(bg_color, card_color, text_color, theme_name)

        # Обновляем цвета меню в зависимости от темы
        if theme_name == "black":
            self.menu_bg_color = '#2d2d2d'
            self.menu_fg_color = '#ffffff'
        elif theme_name == "gray":
            self.menu_bg_color = '#606060'
            self.menu_fg_color = '#ffffff'
        else:  # white
            self.menu_bg_color = '#ffffff'
            self.menu_fg_color = '#000000'

        self.menu_active_bg = '#0078d7'
        self.menu_active_fg = '#ffffff'

        # Сохраняем выбранную тему
        self.save_theme()

    def apply_scale_to_running_ponies(self):
        """Применяет текущий масштаб ко всем запущенным пони"""
        scale_percent = int(self.current_scale * 100)
        print(f"[SCALE] Применение масштаба {scale_percent}% к запущенным пони...")

        # Заново запускаем все пони с новым масштабом
        running_ponies = list(self.running_processes.keys())

        # Останавливаем всех
        for pony_name in running_ponies:
            if pony_name in self.running_processes:
                try:
                    self.running_processes[pony_name].terminate()
                except:
                    pass

        # Запускаем заново с новым масштабом
        for pony_name in running_ponies:
            self._start_via_subprocess(pony_name)

        print("[SUCCESS] Масштаб применен к запущенным пони")

        # Закрываем окно опций
        if self.options_window and self.options_window.winfo_exists():
            self.options_window.destroy()

    def change_theme(self, bg_color, card_color, text_color, theme_name=None):
        """Меняет цветовую схему приложения"""
        self.current_bg = bg_color
        self.current_card_bg = card_color
        self.current_text_color = text_color
        if theme_name:
            self.current_theme_name = theme_name

        # Обновляем цвета главного окна
        try:
            self.root.configure(bg=bg_color)
            self.title_label.configure(bg=bg_color, fg=text_color)
            self.container.configure(bg=bg_color)
            self.canvas.configure(bg=bg_color)
            self.scrollable_frame.configure(bg=bg_color)
            self.button_frame.configure(bg=bg_color)

            # Обновляем кнопки
            self.options_btn.configure(bg=card_color, fg=text_color)
            self.select_btn.configure(bg=card_color, fg=text_color)
            self.stop_btn.configure(bg='#ff4444', fg='white')

            # Перерисовываем карточки
            self.update_layout()

            # Обновляем окно опций если оно открыто
            if hasattr(self, 'options_window') and self.options_window and self.options_window.winfo_exists():
                self.options_window.destroy()
                self.show_options()

        except Exception as e:
            print(f"[WARNING] Ошибка при смене темы: {e}")

    def launch_selected(self):
        """Запускает выбранных персонажей"""
        selected_ponies = []

        for pony_name in self.pony_names:
            if self.check_vars[pony_name].get():
                selected_ponies.append(pony_name)

        # Закрываем главное окно сразу
        if selected_ponies:
            print(f"[SUCCESS] Запуск пони: {', '.join(selected_ponies)}")
            print("[INFO] Главное окно скрыто")
            # Скрываем главное окно сразу
            self.root.withdraw()
            self.main_window_hidden = True

            # Запускаем пони параллельно
            self._launch_ponies_parallel(selected_ponies)
        else:
            print("[WARNING] Не выбрано ни одного пони")

    def _launch_ponies_parallel(self, selected_ponies):
        """Запускает пони параллельно в отдельных потоках"""
        threads = []

        for pony_name in selected_ponies:
            # Создаем отдельный поток для каждого пони
            thread = threading.Thread(
                target=self._launch_single_pony,
                args=(pony_name,),
                daemon=True
            )
            threads.append(thread)
            thread.start()

        # Не ждем завершения всех потоков
        print(f"[START] Запущено {len(threads)} потоков для пони")

    def _launch_single_pony(self, pony_name):
        """Запускает одного пони в отдельном потоке"""
        try:
            # Запускаем через subprocess
            self._start_via_subprocess(pony_name)
        except Exception as e:
            print(f"[ERROR] Ошибка запуска {pony_name} в потоке: {e}")

    def _start_via_subprocess(self, pony_name):
        """Запускает пони через subprocess с фиксом кодировки"""
        try:
            self.active_ponies_count += 1

            current_dir = os.path.dirname(os.path.abspath(__file__))
            pony_script = "./DPP2serverUDP/Client/characters/pony.py"

            if not os.path.exists(pony_script):
                print(f"[ERROR] Файл не найден: {pony_script}")
                return

            # КОМАНДА С ПРАВИЛЬНОЙ КОДИРОВКОЙ
            cmd = f'python "{pony_script}" "{pony_name}" {self.current_scale}'

            print(f"[PROCESS] Команда: {cmd}")

            # Запуск с UTF-8 кодировкой
            if os.name == 'nt':  # Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                # Важно: создаем с правильными настройками кодировки
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    startupinfo=startupinfo,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,  # Используем текстовый режим
                    encoding='utf-8',  # Указываем UTF-8
                    errors='ignore',  # Игнорируем ошибки декодирования
                    cwd=current_dir
                )
            else:  # Linux/Mac
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    cwd=current_dir
                )

            self.running_processes[pony_name] = process
            print(f"[SUCCESS] {pony_name} запущен (PID: {process.pid})")

            # Запускаем поток для чтения вывода
            threading.Thread(
                target=self._safe_read_output,
                args=(process, pony_name),
                daemon=True
            ).start()

        except Exception as e:
            print(f"[ERROR] Ошибка запуска {pony_name}: {e}")
            self.active_ponies_count -= 1

    def _safe_read_output(self, process, pony_name):
        """Безопасное чтение вывода с обработкой кодировок"""
        try:
            # Читаем stdout
            stdout_thread = threading.Thread(
                target=self._read_stream,
                args=(process.stdout, f"[{pony_name} STDOUT]"),
                daemon=True
            )

            # Читаем stderr
            stderr_thread = threading.Thread(
                target=self._read_stream,
                args=(process.stderr, f"[{pony_name} STDERR]"),
                daemon=True
            )

            stdout_thread.start()
            stderr_thread.start()

            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

        except Exception as e:
            # Игнорируем ошибки чтения
            pass

    def _read_stream(self, stream, prefix):
        """Читает поток с обработкой кодировки"""
        try:
            for line in iter(stream.readline, ''):
                if line:
                    line = line.strip()
                    if line:
                        # Пытаемся декодировать разными способами
                        try:
                            print(f"{prefix}: {line}")
                        except:
                            # Если не получается - просто выводим как есть
                            try:
                                print(f"{prefix}: [бинарные данные]")
                            except:
                                pass
        except Exception as e:
            # Игнорируем все ошибки при чтении
            pass

    def _read_process_output(self, process, pony_name):
        """Читает вывод процесса для отладки"""
        try:
            stdout, stderr = process.communicate(timeout=5)
            if stdout:
                print(f"[{pony_name} STDOUT]: {stdout}")
            if stderr:
                print(f"[{pony_name} STDERR]: {stderr}")
        except subprocess.TimeoutExpired:
            # Процесс все еще работает
            pass
        except Exception as e:
            print(f"[ERROR] Ошибка чтения вывода {pony_name}: {e}")

    def _show_main_window(self):
        """Показывает главное окно"""
        if self.main_window_hidden:
            self.root.deiconify()
            self.root.focus_force()
            self.main_window_hidden = False
            print("[INFO] Все пони закрыты, главное окно развернуто")

    def _monitor_processes(self):
        """Мониторит запущенные процессы"""
        while not self.should_exit:
            time.sleep(2)

            # Проверяем процессы
            active_processes = {}
            for pony_name, process in self.running_processes.items():
                try:
                    if process.poll() is None:
                        active_processes[pony_name] = process
                    else:
                        print(f"[INFO] {pony_name} завершил работу")
                        # Уменьшаем счетчик активных пони
                        self.active_ponies_count = max(0, self.active_ponies_count - 1)
                        print(f"[STATUS] Активных пони: {self.active_ponies_count}")
                except:
                    pass

            self.running_processes = active_processes

            # Проверяем, можно ли показать главное окно
            if (self.active_ponies_count == 0 and
                    not self.running_processes and
                    self.main_window_hidden):
                self.root.after(0, self._show_main_window)

    def stop_all(self):
        """Останавливает всех запущенных пони"""
        print("[STOP] Остановка всех пони...")

        # Останавливаем процессы
        for pony_name, process in list(self.running_processes.items()):
            try:
                process.terminate()
                print(f"[STOP] Остановлен: {pony_name}")
            except Exception as e:
                print(f"[ERROR] Ошибка остановки {pony_name}: {e}")

        self.running_processes.clear()

        # Сбрасываем счетчик активных пони
        self.active_ponies_count = 0

        # Показываем главное окно
        self._show_main_window()
        print("[STOP] Все пони остановлены")


if __name__ == "__main__":
    root = tk.Tk()
    app = DynamicPonySelector(root)
    root.mainloop()