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
        'BTN_CLIENT': '#00ff88',  # Зеленый
        'BTN_SERVER': '#00d4ff',  # Голубой
        'BTN_ALL': '#ff6b9d',  # Розовый/красный
        'BTN_CLIENT_OFFLINE': '#8888aa',  # Серо-синий
        'BTN_SETTINGS': '#9d4edd',  # Фиолетовый
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
        'BTN_CLIENT': '#2ecc71',  # Зеленый (яркий)
        'BTN_SERVER': '#3498db',  # Синий
        'BTN_ALL': '#e74c3c',  # Красный
        'BTN_CLIENT_OFFLINE': '#95a5a6',  # Серый (светлый)
        'BTN_SETTINGS': '#9b59b6',  # Фиолетовый
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
        'BTN_CLIENT': '#28a745',  # Зеленый
        'BTN_SERVER': '#17a2b8',  # Голубой
        'BTN_ALL': '#dc3545',  # Красный
        'BTN_CLIENT_OFFLINE': '#6c757d',  # Серый
        'BTN_SETTINGS': '#6f42c1',  # Фиолетовый
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

class TransparentButton:
    """Кнопка с прозрачным фоном"""

    def __init__(self, parent, text, color, command, width=250, height=40):
        """
        parent - родительский виджет
        text - текст кнопки
        color - цвет текста из цветовой схемы
        command - функция при клике
        """
        self.parent = parent
        self.text = text
        self.color = color
        self.command = command
        self.width = width
        self.height = height
        self.parent_bg = parent.cget('bg')

        # Создаем Label вместо Button для прозрачного фона
        self.label = tk.Label(
            parent,
            text=text,
            font=('Arial', 11, 'bold'),
            bg=self.parent_bg,  # Прозрачный фон (такой же как у родителя)
            fg=color,  # Цвет текста
            cursor='hand2',
            padx=20,
            pady=10
        )

        # Биндим события
        self.label.bind('<Button-1>', self.on_click)
        self.label.bind('<Enter>', self.on_enter)
        self.label.bind('<Leave>', self.on_leave)

    def on_click(self, event):
        """При клике"""
        if self.command:
            self.command()

    def on_enter(self, event):
        """При наведении мыши"""
        # Делаем текст светлее
        if self.color.startswith('#'):
            try:
                r = int(self.color[1:3], 16)
                g = int(self.color[3:5], 16)
                b = int(self.color[5:7], 16)
                r = min(255, r + 50)
                g = min(255, g + 50)
                b = min(255, b + 50)
                self.label.config(fg=f'#{r:02x}{g:02x}{b:02x}')
            except:
                # Добавляем подчеркивание
                self.label.config(font=('Arial', 11, 'bold', 'underline'))

    def on_leave(self, event):
        """При уходе мыши"""
        # Возвращаем исходный цвет
        self.label.config(fg=self.color, font=('Arial', 11, 'bold'))

    def update_color(self, new_color, parent_bg):
        """Обновление цвета кнопки"""
        self.color = new_color
        self.parent_bg = parent_bg
        self.label.config(bg=parent_bg, fg=new_color)

    def pack(self, **kwargs):
        """Упаковка кнопки"""
        return self.label.pack(**kwargs)

    def pack_forget(self):
        """Скрытие кнопки"""
        return self.label.pack_forget()


class ThemeDropdownMenu:
    """Выпадающее меню для выбора темы"""

    def __init__(self, parent, colors, current_theme, on_theme_change):
        self.parent = parent
        self.colors = colors
        self.current_theme = current_theme
        self.on_theme_change = on_theme_change
        self.is_open = False
        self.parent_bg = colors['WINDOW_BG']

        # Создаем основной фрейм
        self.main_frame = tk.Frame(parent, bg=self.parent_bg)

        # Кнопка для открытия/закрытия меню (Label для прозрачности)
        self.dropdown_label = tk.Label(
            self.main_frame,
            text=f"Theme: {current_theme} ▼",
            font=('Arial', 11, 'bold'),
            bg=self.parent_bg,
            fg=colors['TEXT_MAIN'],
            cursor='hand2',
            padx=15,
            pady=8,
            relief='solid',
            bd=1
        )
        self.dropdown_label.pack(fill='x')
        self.dropdown_label.bind('<Button-1>', self.toggle_menu)

        # Выпадающее меню (изначально скрыто)
        self.menu_frame = tk.Frame(self.main_frame, bg=self.parent_bg, relief='solid', bd=1)

        # Опции тем
        self.theme_options = [
            ("Black", "BLACK"),
            ("Gray", "GRAY"),
            ("White", "WHITE")
        ]

        self.create_menu_items()

    def create_menu_items(self):
        """Создает элементы меню"""
        for theme_name, theme_key in self.theme_options:
            item_label = tk.Label(
                self.menu_frame,
                text=theme_name,
                font=('Arial', 11),
                bg=self.parent_bg,
                fg=self.colors['TEXT_MAIN'],
                cursor='hand2',
                padx=15,
                pady=6,
                anchor='w'
            )
            item_label.pack(fill='x')
            item_label.bind('<Button-1>', lambda e, t=theme_key: self.select_theme(t))

            # Подсвечиваем текущую тему
            if theme_key == self.current_theme:
                item_label.config(fg=self.colors['ACCENT'])

            # Эффекты наведения
            def on_enter(e, lbl=item_label, key=theme_key):
                if key != self.current_theme:
                    lbl.config(bg=self.colors['ACCENT_LIGHT'])

            def on_leave(e, lbl=item_label, key=theme_key):
                if key == self.current_theme:
                    lbl.config(bg=self.parent_bg, fg=self.colors['ACCENT'])
                else:
                    lbl.config(bg=self.parent_bg, fg=self.colors['TEXT_MAIN'])

            item_label.bind('<Enter>', on_enter)
            item_label.bind('<Leave>', on_leave)

    def toggle_menu(self, event=None):
        """Открывает/закрывает меню"""
        if self.is_open:
            self.close_menu()
        else:
            self.open_menu()

    def open_menu(self):
        """Открывает меню"""
        self.is_open = True
        self.dropdown_label.config(text=f"Theme: {self.current_theme} ▲")
        self.menu_frame.pack(fill='x', pady=(2, 0))

    def close_menu(self):
        """Закрывает меню"""
        self.is_open = False
        self.dropdown_label.config(text=f"Theme: {self.current_theme} ▼")
        self.menu_frame.pack_forget()

    def select_theme(self, theme_key):
        """Выбор темы"""
        self.current_theme = theme_key
        self.dropdown_label.config(text=f"Theme: {theme_key} ▼")
        self.close_menu()

        # Пересоздаем элементы меню для обновления подсветки
        for widget in self.menu_frame.winfo_children():
            widget.destroy()
        self.create_menu_items()

        # Вызываем callback
        if self.on_theme_change:
            self.on_theme_change(theme_key)

    def update_colors(self, colors, parent_bg):
        """Обновление цветов меню"""
        self.colors = colors
        self.parent_bg = parent_bg
        self.main_frame.config(bg=parent_bg)
        self.dropdown_label.config(bg=parent_bg, fg=colors['TEXT_MAIN'])
        self.menu_frame.config(bg=parent_bg)

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
        self.left_container = tk.Frame(self.main_container, bg=self.current_colors['WINDOW_BG'])
        self.left_container.place(x=40, rely=1.0, anchor='sw', y=-40)

        # Создаем кнопки с прозрачным фоном
        self.client_btn = TransparentButton(
            self.left_container,
            "Client",
            self.current_colors['BTN_CLIENT'],
            self.launch_client
        )
        self.client_btn.pack(pady=8)

        self.client_offline_btn = TransparentButton(
            self.left_container,
            "Client Offline",
            self.current_colors['BTN_CLIENT_OFFLINE'],
            self.launch_client_offline
        )
        self.client_offline_btn.pack(pady=8)

        # Кнопки для разработчика
        self.server_btn = TransparentButton(
            self.left_container,
            "Server",
            self.current_colors['BTN_SERVER'],
            self.launch_server
        )

        self.all_btn = TransparentButton(
            self.left_container,
            "Start All (Server+Client)",
            self.current_colors['BTN_ALL'],
            self.launch_all
        )

        # Обновляем видимость кнопок
        self.update_hidden_buttons_visibility()

    def create_settings_button(self):
        """Создание кнопки настроек в правом нижнем углу"""
        self.settings_frame = tk.Frame(self.main_container, bg=self.current_colors['WINDOW_BG'])
        self.settings_frame.place(relx=1.0, rely=1.0, anchor='se', x=-20, y=-20)

        self.settings_btn = tk.Label(
            self.settings_frame,
            text="⚙️ Settings",
            font=self.fonts['body_bold'],
            bg=self.current_colors['WINDOW_BG'],  # Прозрачный фон
            fg=self.current_colors['BTN_SETTINGS'],  # Цвет текста
            cursor='hand2',
            padx=20,
            pady=10
        )
        self.settings_btn.pack()
        self.settings_btn.bind('<Button-1>', lambda e: self.open_settings())

    def open_settings(self):
        """Открытие окна настроек"""
        try:
            # Создаем окно настроек
            self.settings_window = tk.Toplevel(self.root)
            self.settings_window.title("Settings")
            self.settings_window.geometry("450x400")
            self.settings_window.configure(bg=self.current_colors['WINDOW_BG'])
            self.settings_window.resizable(False, False)
            self.settings_window.transient(self.root)
            self.settings_window.grab_set()

            # Центрируем окно настроек
            self.settings_window.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - self.settings_window.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - self.settings_window.winfo_height()) // 2
            self.settings_window.geometry(f"+{x}+{y}")

            # Основное содержание
            content = tk.Frame(self.settings_window, bg=self.current_colors['WINDOW_BG'])
            content.pack(fill='both', expand=True, padx=25, pady=25)

            # Режим разработчика
            dev_frame = tk.Frame(content, bg=self.current_colors['WINDOW_BG'])
            dev_frame.pack(fill='x', pady=(0, 20))

            self.dev_var = tk.BooleanVar(value=self.settings['developer_mode'])
            dev_check = tk.Checkbutton(dev_frame,
                                       text="Developer Mode",
                                       font=('Arial', 11, 'bold'),
                                       bg=self.current_colors['WINDOW_BG'],
                                       fg=self.current_colors['TEXT_MAIN'],
                                       selectcolor=self.current_colors['CARD_BG'],
                                       activebackground=self.current_colors['WINDOW_BG'],
                                       activeforeground=self.current_colors['TEXT_MAIN'],
                                       variable=self.dev_var,
                                       cursor='hand2')
            dev_check.pack(anchor='w')

            tk.Label(dev_frame,
                     text="Shows Server and Start All buttons",
                     font=('Arial', 9),
                     bg=self.current_colors['WINDOW_BG'],
                     fg=self.current_colors['TEXT_MAIN']).pack(anchor='w', padx=25, pady=(0, 5))

            # Цветовые темы
            theme_frame = tk.Frame(content, bg=self.current_colors['WINDOW_BG'])
            theme_frame.pack(fill='x', pady=(0, 20))

            tk.Label(theme_frame,
                     text="Color Theme:",
                     font=('Arial', 11, 'bold'),
                     bg=self.current_colors['WINDOW_BG'],
                     fg=self.current_colors['TEXT_MAIN']).pack(anchor='w', pady=(0, 10))

            # Создаем выпадающее меню для тем
            self.theme_dropdown = ThemeDropdownMenu(
                theme_frame,
                self.current_colors,
                self.colors.current_theme,
                lambda theme: self.on_theme_changed(theme)
            )
            self.theme_dropdown.pack(fill='x', pady=(0, 5))

            # Кнопка сохранения
            btn_frame = tk.Frame(content, bg=self.current_colors['WINDOW_BG'])
            btn_frame.pack(fill='x', pady=(30, 0))

            def apply_and_close():
                # Сохраняем настройки
                self.settings['developer_mode'] = self.dev_var.get()
                self.settings['theme'] = self.colors.current_theme
                self.save_settings()

                # Применяем изменения
                self.apply_settings_changes()

                # Закрываем окно
                self.settings_window.destroy()

            # Кнопка Apply & Save (Label для прозрачности)
            save_btn = tk.Label(
                btn_frame,
                text="Apply & Save",
                font=self.fonts['body_bold'],
                bg=self.current_colors['WINDOW_BG'],
                fg=self.current_colors['BTN_CLIENT'],
                cursor='hand2',
                padx=20,
                pady=10,
                relief='solid',
                bd=1
            )
            save_btn.pack(fill='x', pady=8)
            save_btn.bind('<Button-1>', lambda e: apply_and_close())

            # Кнопка Cancel (Label для прозрачности)
            cancel_btn = tk.Label(
                btn_frame,
                text="Cancel",
                font=self.fonts['body_bold'],
                bg=self.current_colors['WINDOW_BG'],
                fg=self.current_colors['BTN_CLIENT_OFFLINE'],
                cursor='hand2',
                padx=20,
                pady=10,
                relief='solid',
                bd=1
            )
            cancel_btn.pack(fill='x')
            cancel_btn.bind('<Button-1>', lambda e: self.settings_window.destroy())

            # Фокус на окне
            self.settings_window.focus_set()

        except Exception as e:
            print(f"Ошибка открытия настроек: {e}")
            messagebox.showerror("Error", f"Failed to open settings: {e}")

    def on_theme_changed(self, theme_name):
        """Обработка смены темы в выпадающем меню"""
        # Меняем тему в объекте Colors
        self.colors.set_theme(theme_name)

    def update_button_colors(self):
        """Обновление цветов всех кнопок"""
        # Обновляем цвета кнопок
        parent_bg = self.current_colors['WINDOW_BG']

        if hasattr(self, 'client_btn'):
            self.client_btn.update_color(self.current_colors['BTN_CLIENT'], parent_bg)
        if hasattr(self, 'client_offline_btn'):
            self.client_offline_btn.update_color(self.current_colors['BTN_CLIENT_OFFLINE'], parent_bg)
        if hasattr(self, 'server_btn'):
            self.server_btn.update_color(self.current_colors['BTN_SERVER'], parent_bg)
        if hasattr(self, 'all_btn'):
            self.all_btn.update_color(self.current_colors['BTN_ALL'], parent_bg)

        # Обновляем кнопку настроек
        if hasattr(self, 'settings_btn'):
            self.settings_btn.config(
                bg=parent_bg,
                fg=self.current_colors['BTN_SETTINGS']
            )

        # Обновляем выпадающее меню
        if hasattr(self, 'theme_dropdown'):
            self.theme_dropdown.update_colors(self.current_colors, parent_bg)

    def update_hidden_buttons_visibility(self):
        """Обновление видимости скрытых кнопок"""
        if self.settings['developer_mode']:
            if hasattr(self, 'server_btn'):
                self.server_btn.pack(pady=8)
            if hasattr(self, 'all_btn'):
                self.all_btn.pack(pady=8)
        else:
            if hasattr(self, 'server_btn'):
                self.server_btn.pack_forget()
            if hasattr(self, 'all_btn'):
                self.all_btn.pack_forget()

    def apply_settings_changes(self):
        """Применение изменений настроек"""
        # Сохраняем настройки в файл
        self.save_settings()

        # Обновляем текущие цвета
        self.current_colors = self.colors.get_current()

        # Обновляем фон главного окна
        self.root.configure(bg=self.current_colors['WINDOW_BG'])
        self.main_container.configure(bg=self.current_colors['WINDOW_BG'])
        self.left_container.configure(bg=self.current_colors['WINDOW_BG'])
        self.settings_frame.configure(bg=self.current_colors['WINDOW_BG'])

        # Обновляем цвета кнопок
        self.update_button_colors()

        # Обновляем видимость кнопок разработчика
        self.update_hidden_buttons_visibility()

        # Обновляем цвета заголовка
        for widget in self.main_container.winfo_children():
            if isinstance(widget, tk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, tk.Label):
                        child.config(
                            bg=self.current_colors['WINDOW_BG'],
                            fg=self.current_colors['TEXT_MAIN']
                        )

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
                pythonw_exe = sys.executable.replace('python.exe', 'pythonw.exe')
                if not os.path.exists(pythonw_exe):
                    pythonw_exe = sys.executable

                cmd = f'"{pythonw_exe}" "{script_path}"'

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
                process.wait()
                print(f"✅ Процесс {process_name} завершен")
            except:
                print(f"⚠️ Процесс {process_name} завершился с ошибкой")

            self.running_apps -= 1
            print(f"📊 Осталось запущенных приложений: {self.running_apps}")

            if self.running_apps == 0:
                self.root.after(0, self.show_window)

        threading.Thread(target=monitor, daemon=True).start()

    def launch_client(self):
        """Запуск клиента"""
        self.hide_window()

        def launch():
            success = self.run_python_script_simple(self.client_path, "Client")
            if not success:
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
            server_success = self.run_python_script_simple(self.server_path, "Server")
            if server_success:
                time.sleep(3)
                self.run_python_script_simple(self.client_path, "Client")
            else:
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