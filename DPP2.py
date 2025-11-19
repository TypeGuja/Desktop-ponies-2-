import tkinter as tk
from tkinter import ttk
import os
import subprocess
import importlib.util
import threading
import time
import json
from PIL import Image, ImageTk

# Пути к GIF-файлам для каждого пони
PONY_GIFS = {
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


# Динамический импорт всех пони из папок
def import_pony_class(pony_name):
    """Динамически импортирует класс пони по имени"""
    try:
        # Формируем имя файла и папки на основе имени пони
        if pony_name == "Apple Jack":
            folder_name = "AppleJack"
            script_name = "AppleJack.py"
            class_name = "GIFPlayer"
        else:
            # Для остальных пони: "Twilight Sparkle" -> "twilight_sparkle.py"
            folder_name = pony_name.lower().replace(" ", "_")
            script_name = f"{folder_name}.py"
            class_name = "GIFPlayer"  # Предполагаем одинаковое имя класса

        # Путь к файлу скрипта
        script_path = os.path.join(os.path.dirname(__file__), folder_name, script_name)

        if os.path.exists(script_path):
            print(f"✅ Найден файл: {script_path}")

            # Динамически импортируем модуль
            module_name = f"{folder_name}_module"
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            pony_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pony_module)

            # Возвращаем класс из модуля
            return getattr(pony_module, class_name)
        else:
            print(f"❌ Файл не найден: {script_path}")
            return None

    except Exception as e:
        print(f"❌ Ошибка импорта {pony_name}: {e}")
        return None


# Импортируем всех пони
PONY_CLASSES = {}
pony_names = [
    "Twilight Sparkle", "Rainbow Dash", "Pinkie Pie", "Apple Jack",
    "Fluttershy", "Rarity", "Cadance", "Celestia", "Luna"
]

for pony_name in pony_names:
    pony_class = import_pony_class(pony_name)
    if pony_class:
        PONY_CLASSES[pony_name] = pony_class
        print(f"✅ Успешно импортирован: {pony_name}")
    else:
        print(f"❌ Не удалось импортировать: {pony_name}")


class DynamicPonySelector:
    def __init__(self, root):
        self.root = root
        self.root.title("DPP2")
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

        # Настройки цвета контекстного меню - загружаем из сохраненной темы
        self.menu_bg_color = saved_theme.get('menu_bg_color', '#2d2d2d')
        self.menu_fg_color = saved_theme.get('menu_fg_color', '#ffffff')
        self.menu_active_bg = saved_theme.get('menu_active_bg', '#0078d7')
        self.menu_active_fg = saved_theme.get('menu_active_fg', '#ffffff')

        # Список персонажей (теперь используем PONY_GIFS для имен файлов)
        self.ponies = [
            {"name": "Twilight Sparkle", "gif": PONY_GIFS["Twilight Sparkle"], "script": "Twilight Sparkle.py",
             "folder": "Twilight Sparkle"},
            {"name": "Rainbow Dash", "gif": PONY_GIFS["Rainbow Dash"], "script": "Rainbow Dash.py",
             "folder": "Rainbow Dash"},
            {"name": "Pinkie Pie", "gif": PONY_GIFS["Pinkie Pie"], "script": "Pinkie.py", "folder": "Pinkie Pie"},
            {"name": "Apple Jack", "gif": PONY_GIFS["Apple Jack"], "script": "AppleJack.py", "folder": "AppleJack"},
            {"name": "Fluttershy", "gif": PONY_GIFS["Fluttershy"], "script": "Fluttershy.py", "folder": "Fluttershy"},
            {"name": "Rarity", "gif": PONY_GIFS["Rarity"], "script": "Rarity.py", "folder": "rarity"},
            {"name": "Cadance", "gif": PONY_GIFS["Cadance"], "script": "MCadance.py", "folder": "MCadance"},
            {"name": "Celestia", "gif": PONY_GIFS["Celestia"], "script": "Celestia.py", "folder": "Celestia"},
            {"name": "Luna", "gif": PONY_GIFS["Luna"], "script": "Luna.py", "folder": "Luna"},
        ]

        self.check_vars = {}
        self.card_width = 150
        self.card_height = 120
        self.padding = 5
        self.running_processes = {}
        self.running_windows = {}

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
                print(f"❌ GIF файл не найден: {gif_path}")
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
            print(f"❌ Ошибка загрузки GIF {gif_path}: {e}")
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
                    print(f"✅ Загружена сохраненная тема: {config.get('theme_name', 'default')}")
                    return config
            else:
                print("ℹ️ Файл конфигурации не найден, используются значения по умолчанию")
        except Exception as e:
            print(f"❌ Ошибка загрузки темы: {e}")

        # Возвращаем значения по умолчанию для черной темы
        return {
            'bg_color': '#000000',
            'card_color': '#454545',
            'text_color': 'white',
            'theme_name': 'black',
            'menu_bg_color': '#2d2d2d',
            'menu_fg_color': '#ffffff',
            'menu_active_bg': '#0078d7',
            'menu_active_fg': '#ffffff'
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
                'menu_active_fg': self.menu_active_fg
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            print(f"✅ Тема '{self.current_theme_name}' сохранена в конфигурацию")
        except Exception as e:
            print(f"❌ Ошибка сохранения темы: {e}")

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
        print("🛑 Завершение программы...")
        self.should_exit = True
        self.stop_all()  # Сначала останавливаем всех пони
        # Очищаем GIF анимации
        self.gif_labels.clear()
        self.gif_frames.clear()
        self.root.quit()
        self.root.destroy()

    def calculate_columns(self):
        """Вычисляет количество колонок в зависимости от ширины окна"""
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
        for pony in self.ponies:
            if pony["name"] in self.check_vars:
                saved_states[pony["name"]] = self.check_vars[pony["name"]].get()

        # Очищаем старые виджеты и анимации
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.gif_labels.clear()
        self.gif_frames.clear()

        columns = self.calculate_columns()

        for i, pony in enumerate(self.ponies):
            row = i // columns
            col = i % columns
            self.create_pony_card(self.scrollable_frame, pony, row, col)

        # Восстанавливаем состояния чекбоксов
        for pony_name, state in saved_states.items():
            if pony_name in self.check_vars:
                self.check_vars[pony_name].set(state)

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def create_pony_card(self, parent, pony, row, col):
        """Создает карточку персонажа с реальной GIF-анимацией"""
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
        gif_path = os.path.join(pony["folder"], pony["gif"])

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
            self.gif_labels[pony["name"]] = gif_label
            self.gif_frames[pony["name"]] = frames

            # Запускаем анимацию
            self.animate_gif(pony["name"], gif_label, frames)
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
            text=pony["name"],
            font=('Arial', 8, 'bold'),
            fg=self.current_text_color,
            bg=self.current_card_bg,
            anchor='w'
        )
        name_label.pack(side='left', fill='x', expand=True)

        # Чекбокс в правом углу
        if pony["name"] not in self.check_vars:
            self.check_vars[pony["name"]] = tk.BooleanVar()

        check = tk.Checkbutton(
            name_check_frame,
            variable=self.check_vars[pony["name"]],
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
        """Показывает окно опций с выпадающим списком тем"""
        # Закрываем предыдущее окно опций если оно открыто
        if hasattr(self, 'options_window') and self.options_window and self.options_window.winfo_exists():
            self.options_window.destroy()

        self.options_window = tk.Toplevel(self.root)
        self.options_window.title("Options")
        self.options_window.geometry("300x250")
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

    def select_theme(self, bg_color, card_color, text_color, theme_name):
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

        self.apply_menu_colors_to_running_ponies()

    def apply_menu_colors_to_running_ponies(self):
        """Применяет новые цвета меню к уже запущенным пони"""
        for pony_name, window_info in self.running_windows.items():
            try:
                if hasattr(window_info["app"], 'menu_bg_color'):
                    window_info["app"].menu_bg_color = self.menu_bg_color
                    window_info["app"].menu_fg_color = self.menu_fg_color
                    window_info["app"].menu_active_bg = self.menu_active_bg
                    window_info["app"].menu_active_fg = self.menu_active_fg
                    print(f"✅ Обновлены цвета меню для {pony_name}")
            except Exception as e:
                print(f"❌ Ошибка обновления цветов меню для {pony_name}: {e}")

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
            print(f"⚠️ Ошибка при смене темы: {e}")

    def launch_selected(self):
        """Запускает выбранных персонажей и ЗАКРЫВАЕТ главное окно"""
        selected_ponies = []

        for pony in self.ponies:
            if self.check_vars[pony["name"]].get():
                selected_ponies.append(pony["name"])

        # ИЗМЕНЕНИЕ: Закрываем главное окно сразу
        if selected_ponies:
            print(f"✅ Запуск пони: {', '.join(selected_ponies)}")
            print("📱 Главное окно скрыто")
            # Скрываем главное окно сразу
            self.root.withdraw()
            self.main_window_hidden = True

            # Запускаем пони параллельно без задержек
            self._launch_ponies_parallel(selected_ponies)
        else:
            print("⚠️ Не выбрано ни одного пони")

    def _launch_ponies_parallel(self, selected_ponies):
        """Запускает пони параллельно в отдельных потоках"""
        threads = []

        for pony_name in selected_ponies:
            pony = next(p for p in self.ponies if p["name"] == pony_name)

            # Создаем отдельный поток для каждого пони
            thread = threading.Thread(
                target=self._launch_single_pony,
                args=(pony,),
                daemon=True
            )
            threads.append(thread)
            thread.start()

        # Не ждем завершения всех потоков - они работают независимо
        print(f"🚀 Запущено {len(threads)} потоков для пони")

    def _launch_single_pony(self, pony):
        """Запускает одного пони в отдельном потоке"""
        try:
            # Пытаемся запустить напрямую через импорт
            if pony["name"] in PONY_CLASSES and PONY_CLASSES[pony["name"]] is not None:
                self._start_pony_directly(pony)
            else:
                # Fallback: запуск через subprocess
                self._start_via_subprocess(pony)
        except Exception as e:
            print(f"❌ Ошибка запуска {pony['name']} в потоке: {e}")

    def _start_pony_directly(self, pony):
        """Запускает пони напрямую через импорт"""
        try:
            # Увеличиваем счетчик активных пони
            self.active_ponies_count += 1
            print(f"📊 Запуск {pony['name']}... Активных пони: {self.active_ponies_count}")

            # Создаем новое окно для пони
            pony_window = tk.Toplevel()
            pony_window.title(pony["name"])

            # Оптимизация для быстрого запуска
            pony_window.withdraw()  # Сначала скрываем
            pony_window.overrideredirect(False)
            pony_window.resizable(True, True)

            # Запускаем пони в этом окне
            pony_class = PONY_CLASSES[pony["name"]]
            pony_app = pony_class(pony_window)

            # СОЗДАЕМ ФУНКЦИЮ ДЛЯ ВОЗВРАТА К ГЛАВНОМУ ОКНУ
            def return_to_main_callback():
                """Колбэк для возврата к главному окну"""
                print(f"🔄 {pony['name']} возвращается к главному окну")
                # Уменьшаем счетчик активных пони
                self.active_ponies_count -= 1
                print(f"📊 Активных пони: {self.active_ponies_count}")

                # Удаляем из running_windows
                if pony["name"] in self.running_windows:
                    del self.running_windows[pony["name"]]
                # Закрываем окно пони
                pony_window.destroy()
                # Показываем главное окно только если все пони закрыты
                self._check_and_show_main_window()

            # ПЕРЕДАЕМ КОЛБЭК В ПРИЛОЖЕНИЕ ПОНИ
            pony_app.return_to_main_callback = return_to_main_callback

            # Передаем настройки цвета меню
            if hasattr(pony_app, 'menu_bg_color'):
                pony_app.menu_bg_color = self.menu_bg_color
                pony_app.menu_fg_color = self.menu_fg_color
                pony_app.menu_active_bg = self.menu_active_bg
                pony_app.menu_active_fg = self.menu_active_fg

            # Устанавливаем обработчик закрытия окна
            def on_window_close():
                """Обработчик закрытия окна"""
                print(f"🔄 Окно {pony['name']} закрывается")
                if hasattr(pony_app, '_stop_all_threads'):
                    pony_app._stop_all_threads()

                # Уменьшаем счетчик активных пони
                self.active_ponies_count -= 1
                print(f"📊 Активных пони: {self.active_ponies_count}")

                # Удаляем из running_windows
                if pony["name"] in self.running_windows:
                    del self.running_windows[pony["name"]]
                # Показываем главное окно только если все пони закрыты
                self._check_and_show_main_window()
                pony_window.destroy()

            pony_window.protocol("WM_DELETE_WINDOW", on_window_close)

            # Сохраняем ссылку на окно
            self.running_windows[pony["name"]] = {
                "window": pony_window,
                "app": pony_app
            }

            # Показываем окно сразу после создания
            pony_window.deiconify()
            print(f"✅ {pony['name']} запущен напрямую")

        except Exception as e:
            print(f"❌ Ошибка прямого запуска {pony['name']}: {e}")
            # Уменьшаем счетчик если произошла ошибка
            self.active_ponies_count -= 1
            self._start_via_subprocess(pony)

    def _start_via_subprocess(self, pony):
        """Запускает пони через subprocess"""
        try:
            # Увеличиваем счетчик активных пони
            self.active_ponies_count += 1
            print(f"📊 Запуск {pony['name']} через subprocess... Активных пони: {self.active_ponies_count}")

            if pony["name"] == "Apple Jack":
                script_path = os.path.join('AppleJack', pony["script"])
            else:
                script_path = os.path.join(pony["folder"], pony["script"])

            if os.path.exists(script_path):
                # Оптимизированные настройки для быстрого запуска
                if os.name == 'nt':  # Windows
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 1  # Показать окно нормально

                    process = subprocess.Popen(
                        ['python', script_path],
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:  # Linux/Mac
                    process = subprocess.Popen(
                        ['python', script_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                self.running_processes[pony["name"]] = process
                print(f"✅ {pony['name']} запущен через subprocess (PID: {process.pid})")
            else:
                print(f"❌ Скрипт не найден: {script_path}")
                # Уменьшаем счетчик если не удалось запустить
                self.active_ponies_count -= 1
        except Exception as e:
            print(f"❌ Ошибка запуска {pony['name']}: {e}")
            # Уменьшаем счетчик если не удалось запустить
            self.active_ponies_count -= 1

    def _check_and_show_main_window(self):
        """Проверяет условия и показывает главное окно только если все пони закрыты"""
        # Проверяем, что все пони закрыты И главное окно сейчас скрыто
        if (self.active_ponies_count == 0 and
                not self.running_processes and
                not self.running_windows and
                self.main_window_hidden):

            self.root.after(0, self._show_main_window)
        else:
            if self.active_ponies_count > 0:
                print(f"📊 Ожидание закрытия всех пони... Активных: {self.active_ponies_count}")

    def _show_main_window(self):
        """Показывает главное окно"""
        # Проверяем, что окно действительно скрыто, чтобы избежать повторных вызовов
        if self.main_window_hidden:
            self.root.deiconify()
            self.root.focus_force()
            self.main_window_hidden = False
            print("📱 Все пони закрыты, главное окно развернуто")

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
                        print(f"📱 {pony_name} завершил работу")
                        # Уменьшаем счетчик активных пони
                        self.active_ponies_count = max(0, self.active_ponies_count - 1)
                        print(f"📊 Активных пони: {self.active_ponies_count}")
                except:
                    pass

            self.running_processes = active_processes

            # Проверяем окна
            active_windows = {}
            for pony_name, window_info in self.running_windows.items():
                try:
                    if window_info["window"].winfo_exists():
                        active_windows[pony_name] = window_info
                    else:
                        print(f"📱 {pony_name} окно закрыто")
                        # Уменьшаем счетчик активных пони
                        self.active_ponies_count = max(0, self.active_ponies_count - 1)
                        print(f"📊 Активных пони: {self.active_ponies_count}")
                except:
                    pass

            self.running_windows = active_windows

            # Проверяем, можно ли показать главное окно (только если оно скрыто)
            if (self.active_ponies_count == 0 and
                    not self.running_processes and
                    not self.running_windows and
                    self.main_window_hidden):
                self.root.after(0, self._show_main_window)

    def stop_all(self):
        """Останавливает всех запущенных пони"""
        print("🛑 Остановка всех пони...")

        # Останавливаем окна
        for pony_name, window_info in list(self.running_windows.items()):
            try:
                if hasattr(window_info["app"], 'return_to_main_callback'):
                    # Используем колбэк для возврата
                    window_info["app"].return_to_main_callback()
                else:
                    window_info["window"].destroy()
                print(f"🛑 Остановлен: {pony_name}")
            except Exception as e:
                print(f"❌ Ошибка остановки {pony_name}: {e}")

        self.running_windows.clear()

        # Останавливаем процессы
        for pony_name, process in list(self.running_processes.items()):
            try:
                process.terminate()
                print(f"🛑 Остановлен: {pony_name}")
            except Exception as e:
                print(f"❌ Ошибка остановки {pony_name}: {e}")

        self.running_processes.clear()

        # Сбрасываем счетчик активных пони
        self.active_ponies_count = 0

        # Показываем главное окно
        self._show_main_window()
        print("🛑 Все пони остановлены")


if __name__ == "__main__":
    root = tk.Tk()
    app = DynamicPonySelector(root)
    root.mainloop()