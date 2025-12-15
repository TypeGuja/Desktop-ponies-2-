import tkinter as tk
from tkinter import ttk, font, messagebox
import subprocess
import sys
import threading
import time
import json
from pathlib import Path
from datetime import datetime
import os


# ========== КОНСТАНТЫ ДИЗАЙНА ==========
class Colors:
    """Цветовые схемы - только черная, серая и белая"""

    # Черная тема (по умолчанию)
    BLACK = {
        'DARK_BG': '#0a0a14',  # Темно-синий фон
        'DARKER_BG': '#05050a',  # Еще темнее фон
        'CARD_BG': '#151522',  # Фон карточек/кнопок
        'TEXT_MAIN': '#ffffff',  # Основной текст (белый)
        'ACCENT': '#00d4ff',  # Акцентный цвет (голубой)
        'BTN_CLIENT': ['#00ff88', '#00cc66'],  # Зеленый
        'BTN_SERVER': ['#00d4ff', '#0099cc'],  # Голубой
        'BTN_ALL': ['#ff6b9d', '#ff4757'],  # Розовый/красный
        'BTN_CLIENT_OFFLINE': ['#8888aa', '#666688'],  # Серо-синий
        'BTN_SETTINGS': ['#9d4edd', '#7a36b3'],  # Фиолетовый
        'WINDOW_BG': '#0a0a14',  # Фон окна
        'TITLE_BAR': '#05050a',  # Фон заголовка
        'TITLE_TEXT': '#ffffff',  # Текст заголовка
        'ACCENT_HOVER': '#40e0ff',  # Акцент при наведении (светлее)
        'ACCENT_LIGHT': '#202840',  # Светлый акцент (без альфа-канала)
        'BORDER': '#303050'  # Цвет границ
    }

    # Серая тема
    GRAY = {
        'DARK_BG': '#1a1a1a',  # Темно-серый фон
        'DARKER_BG': '#0d0d0d',  # Еще темнее серый
        'CARD_BG': '#2d2d2d',  # Фон карточек/кнопок
        'TEXT_MAIN': '#e6e6e6',  # Основной текст (светло-серый)
        'ACCENT': '#4d4d4d',  # Акцентный цвет (серый)
        'BTN_CLIENT': ['#2ecc71', '#27ae60'],  # Зеленый (яркий)
        'BTN_SERVER': ['#3498db', '#2980b9'],  # Синий
        'BTN_ALL': ['#e74c3c', '#c0392b'],  # Красный
        'BTN_CLIENT_OFFLINE': ['#95a5a6', '#7f8c8d'],  # Серый (светлый)
        'BTN_SETTINGS': ['#9b59b6', '#8e44ad'],  # Фиолетовый
        'WINDOW_BG': '#1a1a1a',  # Фон окна
        'TITLE_BAR': '#0d0d0d',  # Фон заголовка
        'TITLE_TEXT': '#e6e6e6',  # Текст заголовка
        'ACCENT_HOVER': '#6d6d6d',  # Акцент при наведении
        'ACCENT_LIGHT': '#3a3a3a',  # Светлый акцент
        'BORDER': '#404040'  # Цвет границ
    }

    # Белая тема
    WHITE = {
        'DARK_BG': '#f0f0f0',  # Светло-серый фон
        'DARKER_BG': '#e0e0e0',  # Немного темнее фон
        'CARD_BG': '#ffffff',  # Фон карточек/кнопок (белый)
        'TEXT_MAIN': '#333333',  # Основной текст (темно-серый)
        'ACCENT': '#007acc',  # Акцентный цвет (синий)
        'BTN_CLIENT': ['#28a745', '#218838'],  # Зеленый
        'BTN_SERVER': ['#17a2b8', '#138496'],  # Голубой
        'BTN_ALL': ['#dc3545', '#c82333'],  # Красный
        'BTN_CLIENT_OFFLINE': ['#6c757d', '#5a6268'],  # Серый
        'BTN_SETTINGS': ['#6f42c1', '#5a32a3'],  # Фиолетовый
        'WINDOW_BG': '#f0f0f0',  # Фон окна
        'TITLE_BAR': '#e0e0e0',  # Фон заголовка
        'TITLE_TEXT': '#333333',  # Текст заголовка
        'ACCENT_HOVER': '#0099e6',  # Акцент при наведении
        'ACCENT_LIGHT': '#cce5ff',  # Светлый акцент (без альфа-канала)
        'BORDER': '#cccccc'  # Цвет границ
    }

    def __init__(self):
        self.current_theme = 'BLACK'
        self.themes = {
            'BLACK': self.BLACK,
            'GRAY': self.GRAY,
            'WHITE': self.WHITE
        }

    def get_current(self):
        return self.themes[self.current_theme]

    def set_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            return True
        return False


# ========== НАСТРОЙКА ПУТЕЙ К ФАЙЛАМ ==========
# ========== ИЗМЕНИ ЭТИ СТРОКИ НА СВОИ ПУТИ ==========

CLIENT_FILE = r".\DPP2serverUDP\Client\main.py"  # ИЗМЕНИ НА СВОЙ ПУТЬ
CLIENT_OFFLINE_FILE = r".\DPP2.py"  # ИЗМЕНИ НА СВОЙ ПУТЬ
SERVER_FILE = r".\DPP2serverUDP\Server\main.py"  # ИЗМЕНИ НА СВОЙ ПУТЬ


# ========== КОНЕЦ НАСТРОЙКИ ПУТЕЙ ==========

class ThemeDropdownMenu:
    """Выпадающее меню для выбора темы с анимированной стрелочкой"""

    def __init__(self, parent, colors, current_theme, on_theme_change):
        self.parent = parent
        self.colors = colors
        self.current_theme = current_theme
        self.on_theme_change = on_theme_change
        self.is_open = False

        # Создаем основной фрейм с увеличенной зоной клика
        self.main_frame = tk.Frame(parent, bg=colors['WINDOW_BG'])

        # Фрейм для увеличения зоны клика
        self.click_area = tk.Frame(self.main_frame, bg=colors['WINDOW_BG'], cursor='hand2')
        self.click_area.pack(fill='x', pady=(0, 5))
        self.click_area.bind('<Button-1>', self.toggle_menu)

        # Кнопка для открытия/закрытия меню (увеличена)
        self.dropdown_button = tk.Frame(self.click_area, bg=colors['CARD_BG'], relief='flat',
                                        highlightthickness=1, highlightbackground=colors['BORDER'],
                                        cursor='hand2')
        self.dropdown_button.pack(fill='x', padx=2)
        self.dropdown_button.bind('<Button-1>', self.toggle_menu)

        # Внутренний фрейм для кнопки (увеличил паддинг)
        inner_btn = tk.Frame(self.dropdown_button, bg=colors['CARD_BG'], cursor='hand2')
        inner_btn.pack(fill='x', padx=15, pady=12)  # Увеличил паддинг
        inner_btn.bind('<Button-1>', self.toggle_menu)

        # Текст с текущей темой
        self.theme_text = tk.Label(inner_btn,
                                   text=f"Theme: {current_theme}",
                                   font=('Arial', 11, 'bold'),  # Увеличил шрифт
                                   bg=colors['CARD_BG'],
                                   fg=colors['TEXT_MAIN'],
                                   cursor='hand2')
        self.theme_text.pack(side='left')
        self.theme_text.bind('<Button-1>', self.toggle_menu)

        # Стрелочка (увеличил размер)
        self.arrow_canvas = tk.Canvas(inner_btn, width=20, height=20,
                                      bg=colors['CARD_BG'], highlightthickness=0,
                                      cursor='hand2')
        self.arrow_canvas.pack(side='right')
        self.arrow_canvas.bind('<Button-1>', self.toggle_menu)
        self.draw_arrow_down()  # Начальная позиция - вниз

        # Выпадающее меню (изначально скрыто)
        self.menu_frame = tk.Frame(self.main_frame, bg=colors['CARD_BG'], relief='flat',
                                   highlightthickness=1, highlightbackground=colors['BORDER'])

        # Опции тем
        self.theme_options = [
            ("Black", "BLACK"),
            ("Gray", "GRAY"),
            ("White", "WHITE")
        ]

        self.create_menu_items()

    def draw_arrow_down(self):
        """Рисует стрелочку вниз"""
        self.arrow_canvas.delete("all")
        self.arrow_canvas.create_polygon(5, 7, 15, 7, 10, 13,
                                         fill=self.colors['TEXT_MAIN'],
                                         outline='')

    def draw_arrow_up(self):
        """Рисует стрелочку вверх"""
        self.arrow_canvas.delete("all")
        self.arrow_canvas.create_polygon(5, 13, 15, 13, 10, 7,
                                         fill=self.colors['TEXT_MAIN'],
                                         outline='')

    def create_menu_items(self):
        """Создает элементы меню"""
        for theme_name, theme_key in self.theme_options:
            item_frame = tk.Frame(self.menu_frame, bg=self.colors['CARD_BG'], cursor='hand2')
            item_frame.pack(fill='x', padx=2, pady=1)
            item_frame.bind('<Button-1>', lambda e, t=theme_key: self.select_theme(t))

            # Создаем элемент меню (увеличил паддинг)
            item = tk.Label(item_frame,
                            text=theme_name,
                            font=('Arial', 11),  # Увеличил шрифт
                            bg=self.colors['CARD_BG'],
                            fg=self.colors['TEXT_MAIN'],
                            anchor='w',
                            padx=15,  # Увеличил паддинг
                            pady=8,  # Увеличил паддинг
                            cursor='hand2')
            item.pack(fill='x')

            # Подсвечиваем текущую тему
            if theme_key == self.current_theme:
                item.config(bg=self.colors['ACCENT'], fg='white')

            # Бинд клика
            item.bind('<Button-1>', lambda e, t=theme_key: self.select_theme(t))

            # Эффекты наведения - используем правильные цвета
            def on_enter(e, lbl=item, key=theme_key):
                if key != self.current_theme:
                    lbl.config(bg=self.colors['ACCENT_LIGHT'])

            def on_leave(e, lbl=item, key=theme_key):
                if key == self.current_theme:
                    lbl.config(bg=self.colors['ACCENT'], fg='white')
                else:
                    lbl.config(bg=self.colors['CARD_BG'], fg=self.colors['TEXT_MAIN'])

            item.bind('<Enter>', on_enter)
            item.bind('<Leave>', on_leave)
            item_frame.bind('<Enter>', on_enter)
            item_frame.bind('<Leave>', on_leave)

    def toggle_menu(self, event=None):
        """Открывает/закрывает меню"""
        if self.is_open:
            self.close_menu()
        else:
            self.open_menu()

    def open_menu(self):
        """Открывает меню"""
        self.is_open = True
        self.draw_arrow_up()
        self.menu_frame.pack(fill='x', padx=2, pady=(0, 2))

    def close_menu(self):
        """Закрывает меню"""
        self.is_open = False
        self.draw_arrow_down()
        self.menu_frame.pack_forget()

    def select_theme(self, theme_key):
        """Выбор темы"""
        self.current_theme = theme_key
        self.theme_text.config(text=f"Theme: {theme_key}")
        self.close_menu()

        # Пересоздаем элементы меню для обновления подсветки
        for widget in self.menu_frame.winfo_children():
            widget.destroy()
        self.create_menu_items()

        # Вызываем callback
        if self.on_theme_change:
            self.on_theme_change(theme_key)

    def pack(self, **kwargs):
        """Упаковка виджета"""
        return self.main_frame.pack(**kwargs)


class UltraModernLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎮 DPP2 LAUNCHER")
        self.root.geometry("800x500")
        self.root.resizable(False, False)

        # Инициализация цветов
        self.colors = Colors()
        self.current_colors = self.colors.get_current()

        # Настройки
        self.settings = {
            'developer_mode': False,
            'theme': 'BLACK'
        }
        self.load_settings()

        # Применяем цвета к окну
        self.root.configure(bg=self.current_colors['WINDOW_BG'])

        # Переменные для управления
        self.running_apps = 0  # Счетчик запущенных приложений
        self.is_hidden = False  # Флаг скрытия окна

        # Проверяем файлы
        self.check_files()

        # Настройка шрифтов
        self.setup_fonts()

        # Создание интерфейса
        self.create_interface()

        # Центрирование окна
        self.center_window()

        # Обработка закрытия
        self.root.protocol("WM_DELETE_WINDOW", self.quit_launcher)

    def check_files(self):
        """Проверка существования файлов"""
        print("\n" + "=" * 50)
        print("ПРОВЕРКА ФАЙЛОВ:")
        print("=" * 50)

        # Преобразуем в абсолютные пути
        self.client_path = os.path.abspath(CLIENT_FILE)
        self.client_offline_path = os.path.abspath(CLIENT_OFFLINE_FILE)
        self.server_path = os.path.abspath(SERVER_FILE)

        files = [
            ("КЛИЕНТ", self.client_path),
            ("ОФЛАЙН КЛИЕНТ", self.client_offline_path),
            ("СЕРВЕР", self.server_path)
        ]

        all_files_exist = True
        for name, path in files:
            if os.path.exists(path):
                print(f"✓ {name}: {path}")
            else:
                print(f"✗ {name}: {path} - НЕ НАЙДЕН!")
                all_files_exist = False

        print("=" * 50 + "\n")
        return all_files_exist

    def load_settings(self):
        """Загрузка настроек из файла"""
        try:
            settings_file = Path('launcher_settings.json')
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)

                    # Применяем тему
                    if 'theme' in loaded_settings:
                        self.colors.set_theme(loaded_settings['theme'])
                        self.current_colors = self.colors.get_current()
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")

    def save_settings(self):
        """Сохранение настроек в файл"""
        try:
            settings_file = Path('launcher_settings.json')
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def setup_fonts(self):
        """Настройка шрифтов"""
        self.fonts = {
            'body_bold': ('Arial', 12, 'bold'),
            'small': ('Arial', 9),
        }

    def create_interface(self):
        """Создание интерфейса"""
        # Главный контейнер
        self.main_container = tk.Frame(self.root, bg=self.current_colors['WINDOW_BG'])
        self.main_container.pack(fill='both', expand=True)

        # Заголовок вверху
        self.create_title()

        # Панель кнопок в левом нижнем углу
        self.create_left_button_panel()

        # Кнопка настроек в правом нижнем углу
        self.create_settings_button()

    def create_title(self):
        """Создание заголовка"""
        title_frame = tk.Frame(self.main_container, bg=self.current_colors['WINDOW_BG'])
        title_frame.pack(side='top', fill='x', pady=30)

        title = tk.Label(title_frame,
                         text="🎮 DPP2 LAUNCHER",
                         font=('Arial', 32, 'bold'),
                         bg=self.current_colors['WINDOW_BG'],
                         fg=self.current_colors['TEXT_MAIN'])
        title.pack()

        subtitle = tk.Label(title_frame,
                            text="Select an option below",
                            font=self.fonts['small'],
                            bg=self.current_colors['WINDOW_BG'],
                            fg=self.current_colors['ACCENT'])
        subtitle.pack(pady=5)

    def create_left_button_panel(self):
        """Создание панели кнопок в левом нижнем углу"""
        # Контейнер для кнопок в левом нижнем углу
        left_container = tk.Frame(self.main_container, bg=self.current_colors['WINDOW_BG'])
        left_container.place(x=40, rely=1.0, anchor='sw', y=-40)

        # Простые кнопки без анимации
        self.client_btn = tk.Button(left_container,
                                    text="Client",
                                    font=('Arial', 12, 'bold'),
                                    bg=self.current_colors['BTN_CLIENT'][0],
                                    fg='white',
                                    activebackground=self.current_colors['BTN_CLIENT'][1],
                                    activeforeground='white',
                                    borderwidth=0,
                                    cursor='hand2',
                                    width=20,
                                    height=2,
                                    command=self.launch_client)
        self.client_btn.pack(pady=8)

        self.client_offline_btn = tk.Button(left_container,
                                            text="Client Offline",
                                            font=('Arial', 12, 'bold'),
                                            bg=self.current_colors['BTN_CLIENT_OFFLINE'][0],
                                            fg='white',
                                            activebackground=self.current_colors['BTN_CLIENT_OFFLINE'][1],
                                            activeforeground='white',
                                            borderwidth=0,
                                            cursor='hand2',
                                            width=20,
                                            height=2,
                                            command=self.launch_client_offline)
        self.client_offline_btn.pack(pady=8)

        # Кнопки для разработчика
        self.server_btn = tk.Button(left_container,
                                    text="Server",
                                    font=('Arial', 12, 'bold'),
                                    bg=self.current_colors['BTN_SERVER'][0],
                                    fg='white',
                                    activebackground=self.current_colors['BTN_SERVER'][1],
                                    activeforeground='white',
                                    borderwidth=0,
                                    cursor='hand2',
                                    width=20,
                                    height=2,
                                    command=self.launch_server)

        self.all_btn = tk.Button(left_container,
                                 text="Start All (Server+Client)",
                                 font=('Arial', 12, 'bold'),
                                 bg=self.current_colors['BTN_ALL'][0],
                                 fg='white',
                                 activebackground=self.current_colors['BTN_ALL'][1],
                                 activeforeground='white',
                                 borderwidth=0,
                                 cursor='hand2',
                                 width=20,
                                 height=2,
                                 command=self.launch_all)

        # Обновляем видимость кнопок
        self.update_hidden_buttons_visibility()

    def create_settings_button(self):
        """Создание кнопки настроек в правом нижнем углу"""
        settings_frame = tk.Frame(self.main_container, bg=self.current_colors['WINDOW_BG'])
        settings_frame.place(relx=1.0, rely=1.0, anchor='se', x=-20, y=-20)

        settings_btn = tk.Button(settings_frame,
                                 text="⚙️ Settings",
                                 font=self.fonts['body_bold'],
                                 bg=self.current_colors['BTN_SETTINGS'][0],
                                 fg='white',
                                 activebackground=self.current_colors['BTN_SETTINGS'][1],
                                 activeforeground='white',
                                 borderwidth=0,
                                 cursor='hand2',
                                 padx=20,
                                 pady=10,
                                 command=self.open_settings)
        settings_btn.pack()
        settings_btn.config(cursor='hand2')

    def open_settings(self):
        """Открытие окна настроек"""
        try:
            # Создаем окно настроек
            settings_window = tk.Toplevel(self.root)
            settings_window.title("Settings")
            settings_window.geometry("450x400")  # Увеличил размер
            settings_window.configure(bg=self.current_colors['WINDOW_BG'])
            settings_window.resizable(False, False)
            settings_window.transient(self.root)
            settings_window.grab_set()

            # Центрируем окно настроек
            settings_window.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - settings_window.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - settings_window.winfo_height()) // 2
            settings_window.geometry(f"+{x}+{y}")

            # Основное содержание с увеличенными отступами
            content = tk.Frame(settings_window, bg=self.current_colors['WINDOW_BG'])
            content.pack(fill='both', expand=True, padx=25, pady=25)

            # Режим разработчика
            dev_frame = tk.Frame(content, bg=self.current_colors['WINDOW_BG'])
            dev_frame.pack(fill='x', pady=(0, 20))  # Увеличил отступ

            dev_var = tk.BooleanVar(value=self.settings['developer_mode'])
            dev_check = tk.Checkbutton(dev_frame,
                                       text="Developer Mode",
                                       font=('Arial', 11, 'bold'),  # Увеличил шрифт
                                       bg=self.current_colors['WINDOW_BG'],
                                       fg=self.current_colors['TEXT_MAIN'],
                                       selectcolor=self.current_colors['CARD_BG'],
                                       activebackground=self.current_colors['WINDOW_BG'],
                                       activeforeground=self.current_colors['TEXT_MAIN'],
                                       variable=dev_var,
                                       cursor='hand2')
            dev_check.pack(anchor='w')

            tk.Label(dev_frame,
                     text="Shows Server and Start All buttons",
                     font=('Arial', 9),
                     bg=self.current_colors['WINDOW_BG'],
                     fg=self.current_colors['TEXT_MAIN']).pack(anchor='w', padx=25, pady=(0, 5))

            # Цветовые темы - ВЫПАДАЮЩЕЕ МЕНЮ
            theme_frame = tk.Frame(content, bg=self.current_colors['WINDOW_BG'])
            theme_frame.pack(fill='x', pady=(0, 20))  # Увеличил отступ

            tk.Label(theme_frame,
                     text="Color Theme:",
                     font=('Arial', 11, 'bold'),  # Увеличил шрифт
                     bg=self.current_colors['WINDOW_BG'],
                     fg=self.current_colors['TEXT_MAIN']).pack(anchor='w', pady=(0, 10))

            # Создаем выпадающее меню для тем
            self.theme_dropdown = ThemeDropdownMenu(
                theme_frame,
                self.current_colors,
                self.colors.current_theme,
                lambda theme: self.on_theme_changed(theme, dev_var, settings_window)
            )
            self.theme_dropdown.pack(fill='x', pady=(0, 5))

            # Кнопка сохранения
            btn_frame = tk.Frame(content, bg=self.current_colors['WINDOW_BG'])
            btn_frame.pack(fill='x', pady=(30, 0))  # Увеличил отступ

            def apply_and_close():
                # Сохраняем настройки
                self.settings['developer_mode'] = dev_var.get()
                self.settings['theme'] = self.colors.current_theme
                self.save_settings()

                # Применяем изменения
                self.apply_settings_changes()

                # Закрываем окно
                settings_window.destroy()

            save_btn = tk.Button(btn_frame,
                                 text="Apply & Save",
                                 font=self.fonts['body_bold'],
                                 bg=self.current_colors['BTN_CLIENT'][0],
                                 fg='white',
                                 activebackground=self.current_colors['BTN_CLIENT'][1],
                                 activeforeground='white',
                                 borderwidth=0,
                                 cursor='hand2',
                                 command=apply_and_close)
            save_btn.pack(fill='x', pady=8)

            cancel_btn = tk.Button(btn_frame,
                                   text="Cancel",
                                   font=self.fonts['body_bold'],
                                   bg=self.current_colors['BTN_CLIENT_OFFLINE'][0],
                                   fg='white',
                                   activebackground=self.current_colors['BTN_CLIENT_OFFLINE'][1],
                                   activeforeground='white',
                                   borderwidth=0,
                                   cursor='hand2',
                                   command=settings_window.destroy)
            cancel_btn.pack(fill='x')

            # Фокус на окне
            settings_window.focus_set()

        except Exception as e:
            print(f"Ошибка открытия настроек: {e}")
            messagebox.showerror("Error", f"Failed to open settings: {e}")

    def on_theme_changed(self, theme_name, dev_var, settings_window):
        """Обработка смены темы в выпадающем меню"""
        # Меняем тему в объекте Colors
        self.colors.set_theme(theme_name)

        # Обновляем текущие цвета
        self.current_colors = self.colors.get_current()

        # Обновляем цвета окна настроек
        settings_window.configure(bg=self.current_colors['WINDOW_BG'])
        for widget in settings_window.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.configure(bg=self.current_colors['WINDOW_BG'])
                self.update_widget_colors(widget)

    def update_widget_colors(self, parent):
        """Рекурсивно обновляет цвета виджетов"""
        for widget in parent.winfo_children():
            try:
                if isinstance(widget, (tk.Frame, tk.LabelFrame)):
                    widget.configure(bg=self.current_colors['WINDOW_BG'])
                    self.update_widget_colors(widget)
                elif isinstance(widget, tk.Label):
                    widget.configure(bg=self.current_colors['WINDOW_BG'],
                                     fg=self.current_colors['TEXT_MAIN'])
                elif isinstance(widget, tk.Checkbutton):
                    widget.configure(bg=self.current_colors['WINDOW_BG'],
                                     fg=self.current_colors['TEXT_MAIN'],
                                     selectcolor=self.current_colors['CARD_BG'],
                                     activebackground=self.current_colors['WINDOW_BG'],
                                     activeforeground=self.current_colors['TEXT_MAIN'])
                elif isinstance(widget, tk.Button):
                    # Для кнопок Apply & Save и Cancel оставляем свои цвета
                    if widget.cget('text') not in ["Apply & Save", "Cancel"]:
                        widget.configure(bg=self.current_colors['CARD_BG'],
                                         fg=self.current_colors['TEXT_MAIN'])
            except:
                pass

    def update_hidden_buttons_visibility(self):
        """Обновление видимости скрытых кнопок"""
        if self.settings['developer_mode']:
            self.server_btn.pack(pady=8)
            self.all_btn.pack(pady=8)
        else:
            # Проверяем, что кнопки были созданы перед скрытием
            if hasattr(self, 'server_btn'):
                self.server_btn.pack_forget()
            if hasattr(self, 'all_btn'):
                self.all_btn.pack_forget()

    def apply_settings_changes(self):
        """Применение изменений настроек"""
        # Сохраняем настройки в файл
        self.save_settings()

        # Меняем тему
        self.colors.set_theme(self.settings['theme'])
        self.current_colors = self.colors.get_current()

        # Перезагружаем интерфейс
        self.main_container.destroy()
        self.root.configure(bg=self.current_colors['WINDOW_BG'])
        self.create_interface()

    def hide_window(self):
        """Скрыть окно лаунчера"""
        if not self.is_hidden:
            self.root.withdraw()
            self.is_hidden = True

    def show_window(self):
        """Показать окно лаунчера"""
        if self.is_hidden:
            self.root.deiconify()
            self.is_hidden = False

    def run_python_script_simple(self, script_path, script_name):
        """Простой запуск Python скрипта в отдельном процессе"""
        try:
            if not os.path.exists(script_path):
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Файл не найден:\n{script_path}"))
                return False

            # Получаем директорию
            work_dir = os.path.dirname(script_path)

            print(f"\n🚀 Запуск {script_name}:")
            print(f"📁 Файл: {script_path}")
            print(f"📂 Директория: {work_dir}")

            # Для Windows
            if os.name == 'nt':
                # Запускаем в новом процессе
                # Используем pythonw.exe для запуска без консоли
                pythonw_exe = sys.executable.replace('python.exe', 'pythonw.exe')
                if not os.path.exists(pythonw_exe):
                    pythonw_exe = sys.executable

                cmd = f'"{pythonw_exe}" "{script_path}"'

                # Запускаем процесс
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=work_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                # Для Linux/Mac
                process = subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=work_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )

            print(f"✅ {script_name} запущен (PID: {process.pid})")

            # Увеличиваем счетчик запущенных приложений
            self.running_apps += 1
            print(f"📊 Запущенных приложений: {self.running_apps}")

            # Запускаем мониторинг этого процесса
            self.monitor_process(process, script_name)

            return True

        except Exception as e:
            print(f"❌ Ошибка запуска {script_name}: {e}")
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось запустить {script_name}:\n{str(e)}"))
            return False

    def monitor_process(self, process, process_name):
        """Мониторинг процесса"""

        def monitor():
            try:
                # Ждем завершения процесса
                process.wait()
                print(f"✅ Процесс {process_name} завершен")
            except:
                print(f"⚠️ Процесс {process_name} завершился с ошибкой")

            # Уменьшаем счетчик запущенных приложений
            self.running_apps -= 1
            print(f"📊 Осталось запущенных приложений: {self.running_apps}")

            # Если все приложения закрыты - показываем лаунчер
            if self.running_apps == 0:
                self.root.after(0, self.show_window)

        # Запускаем мониторинг в отдельном потоке
        threading.Thread(target=monitor, daemon=True).start()

    def launch_client(self):
        """Запуск клиента"""
        # Скрываем окно сразу
        self.hide_window()

        # Запускаем в отдельном потоке
        def launch():
            success = self.run_python_script_simple(self.client_path, "Client")
            if not success:
                # Если не удалось, показываем окно снова
                self.root.after(0, self.show_window)

        threading.Thread(target=launch, daemon=True).start()

    def launch_client_offline(self):
        """Запуск офлайн клиента"""
        self.hide_window()

        def launch():
            success = self.run_python_script_simple(self.client_offline_path, "Client Offline")
            if not success:
                self.root.after(0, self.show_window)

        threading.Thread(target=launch, daemon=True).start()

    def launch_server(self):
        """Запуск сервера"""
        self.hide_window()

        def launch():
            success = self.run_python_script_simple(self.server_path, "Server")
            if not success:
                self.root.after(0, self.show_window)

        threading.Thread(target=launch, daemon=True).start()

    def launch_all(self):
        """Запуск всего (Server+Client)"""
        self.hide_window()

        def launch():
            # Сначала сервер
            server_success = self.run_python_script_simple(self.server_path, "Server")
            if server_success:
                # Ждем 3 секунды
                time.sleep(3)
                # Затем клиент
                self.run_python_script_simple(self.client_path, "Client")
            else:
                # Если сервер не запустился, показываем лаунчер
                self.root.after(0, self.show_window)

        threading.Thread(target=launch, daemon=True).start()

    def center_window(self):
        """Центрирование окна"""
        self.root.update_idletasks()
        width = 800
        height = 500
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def quit_launcher(self):
        """Выход из лаунчера"""
        self.root.destroy()
        sys.exit(0)

    def run(self):
        """Запуск лаунчера"""
        self.root.mainloop()


# ========== ЗАПУСК ЛАУНЧЕРА ==========
if __name__ == "__main__":
    print("=" * 50)
    print("DPP2 LAUNCHER - Запуск...")
    print("=" * 50)
    print(f"Текущая директория: {os.getcwd()}")
    print(f"Python версия: {sys.version}")

    launcher = UltraModernLauncher()
    launcher.run()