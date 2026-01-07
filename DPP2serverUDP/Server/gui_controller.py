#!/usr/bin/env python3
"""
DPP2 UDP Server GUI - Modern GUI controller with sidebar and improved themes
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, font
import threading
import queue
import json
import time
import sys
import os
from datetime import datetime
import psutil
import platform

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class ModernButton(ttk.Button):
    """Modernized button"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_theme(self, colors):
        """Set theme for button"""
        style = ttk.Style()
        style_name = f"Modern.{colors['name']}.TButton"

        style.configure(style_name,
                        background=colors['button_bg'],
                        foreground=colors['button_fg'],
                        borderwidth=1,
                        relief="raised",
                        padding=8,
                        font=('Segoe UI', 10, 'bold'))

        style.map(style_name,
                  background=[('active', colors['button_active']),
                              ('pressed', colors['button_pressed']),
                              ('disabled', colors['button_disabled'])],
                  relief=[('pressed', 'sunken'),
                          ('active', 'raised')])

        self.configure(style=style_name)


class SidebarButton(tk.Canvas):
    """Button for sidebar"""

    def __init__(self, parent, text, icon="", command=None, colors=None):
        super().__init__(parent, width=200, height=40,
                         highlightthickness=0, bg=colors['sidebar_bg'])
        self.colors = colors
        self.text = text
        self.command = command
        self.state = "normal"

        # Draw icon
        if icon:
            self.create_text(20, 20, text=icon,
                             font=('Segoe UI', 14),
                             fill=colors['sidebar_icon'])

        # Draw text
        self.text_id = self.create_text(50, 20, text=text,
                                        font=('Segoe UI', 10),
                                        fill=colors['sidebar_text'],
                                        anchor="w")

        # Bind events
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

        # Selection indicator
        self.indicator = self.create_rectangle(0, 0, 4, 40,
                                               fill=colors['accent'],
                                               state="hidden")

        self.update_colors(colors)

    def update_colors(self, colors):
        """Update colors"""
        self.colors = colors
        self.configure(bg=colors['sidebar_bg'])
        self.itemconfig(self.text_id, fill=colors['sidebar_text'])
        self.itemconfig(self.indicator, fill=colors['accent'])

        if self.state == "active":
            self.configure(bg=colors['sidebar_active'])
            self.itemconfig(self.text_id, fill=colors['sidebar_active_text'])
        elif self.state == "hover":
            self.configure(bg=colors['sidebar_hover'])

    def on_enter(self, event):
        if self.state != "active":
            self.state = "hover"
            self.configure(bg=self.colors['sidebar_hover'])

    def on_leave(self, event):
        if self.state != "active":
            self.state = "normal"
            self.configure(bg=self.colors['sidebar_bg'])

    def on_click(self, event):
        if self.command:
            self.command()

    def set_active(self, active=True):
        """Set active state"""
        if active:
            self.state = "active"
            self.configure(bg=self.colors['sidebar_active'])
            self.itemconfig(self.text_id, fill=self.colors['sidebar_active_text'])
            self.itemconfig(self.indicator, state="normal")
        else:
            self.state = "normal"
            self.configure(bg=self.colors['sidebar_bg'])
            self.itemconfig(self.text_id, fill=self.colors['sidebar_text'])
            self.itemconfig(self.indicator, state="hidden")


class ThemePreview(tk.Canvas):
    """Theme preview widget"""

    def __init__(self, parent, theme_name, theme_data, command=None, width=180, height=60):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=1, highlightbackground=theme_data['border'])
        self.theme_name = theme_name
        self.theme_data = theme_data
        self.command = command
        self.selected = False

        # Draw preview
        self.create_rectangle(0, 0, width, height, fill=theme_data['bg'], outline="")

        # Sidebar
        self.create_rectangle(0, 0, 40, height, fill=theme_data['sidebar_bg'], outline="")

        # Content
        self.create_rectangle(50, 10, 80, 20, fill=theme_data['accent'], outline="")
        self.create_rectangle(50, 30, 100, 40, fill=theme_data['bg_light'], outline="")

        # Button
        self.create_rectangle(120, 20, 170, 40, fill=theme_data['button_bg'], outline="")

        # Theme name
        self.create_text(width // 2, height - 15, text=theme_data['name'],
                         font=('Segoe UI', 9), fill=theme_data['text'])

        # Bind events
        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, event):
        if not self.selected:
            self.config(highlightbackground=self.theme_data['accent'])

    def on_leave(self, event):
        if not self.selected:
            self.config(highlightbackground=self.theme_data['border'])

    def on_click(self, event):
        if self.command:
            self.command(self.theme_name)

    def set_selected(self, selected):
        """Set selection state"""
        self.selected = selected
        if selected:
            self.config(highlightbackground=self.theme_data['accent'],
                        highlightthickness=2)
        else:
            self.config(highlightbackground=self.theme_data['border'],
                        highlightthickness=1)


class GifctConfigDialog:
    """Dialog for adding/editing Gifct configurations"""

    def __init__(self, parent, title, gifct_data=None, colors=None):
        self.parent = parent
        self.colors = colors
        self.result = None

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x600")
        self.dialog.configure(bg=colors['bg'])
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (parent.winfo_screenwidth() // 2) - (width // 2)
        y = (parent.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')

        # Content frame
        content = tk.Frame(self.dialog, bg=colors['card_bg'], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        # Gifct name
        tk.Label(content,
                 text="Gifct Name:",
                 font=('Segoe UI', 10, 'bold'),
                 bg=colors['card_bg'],
                 fg=colors['text']).pack(anchor='w', pady=(0, 5))

        self.name_var = tk.StringVar(value=gifct_data.get('name', '') if gifct_data else '')
        name_entry = tk.Entry(content,
                              textvariable=self.name_var,
                              font=('Segoe UI', 10),
                              bg=colors['bg_light'],
                              fg=colors['text'],
                              insertbackground=colors['text'])
        name_entry.pack(fill=tk.X, pady=(0, 15))

        # Gifct ID
        tk.Label(content,
                 text="Gifct ID (unique identifier):",
                 font=('Segoe UI', 10, 'bold'),
                 bg=colors['card_bg'],
                 fg=colors['text']).pack(anchor='w', pady=(0, 5))

        self.id_var = tk.StringVar(value=gifct_data.get('id', '') if gifct_data else f"gifct_{int(time.time())}")
        id_entry = tk.Entry(content,
                            textvariable=self.id_var,
                            font=('Segoe UI', 10),
                            bg=colors['bg_light'],
                            fg=colors['text'],
                            insertbackground=colors['text'])
        id_entry.pack(fill=tk.X, pady=(0, 15))

        # Description
        tk.Label(content,
                 text="Description:",
                 font=('Segoe UI', 10, 'bold'),
                 bg=colors['card_bg'],
                 fg=colors['text']).pack(anchor='w', pady=(0, 5))

        self.desc_var = tk.StringVar(value=gifct_data.get('description', '') if gifct_data else '')
        desc_entry = tk.Entry(content,
                              textvariable=self.desc_var,
                              font=('Segoe UI', 10),
                              bg=colors['bg_light'],
                              fg=colors['text'],
                              insertbackground=colors['text'])
        desc_entry.pack(fill=tk.X, pady=(0, 15))

        # Type
        tk.Label(content,
                 text="Type:",
                 font=('Segoe UI', 10, 'bold'),
                 bg=colors['card_bg'],
                 fg=colors['text']).pack(anchor='w', pady=(0, 5))

        self.type_var = tk.StringVar(value=gifct_data.get('type', 'ability') if gifct_data else 'ability')
        type_frame = tk.Frame(content, bg=colors['card_bg'])
        type_frame.pack(fill=tk.X, pady=(0, 15))

        types = ['ability', 'skill', 'item', 'buff', 'debuff', 'custom']
        for gifct_type in types:
            tk.Radiobutton(type_frame,
                           text=gifct_type.capitalize(),
                           variable=self.type_var,
                           value=gifct_type,
                           font=('Segoe UI', 9),
                           bg=colors['card_bg'],
                           fg=colors['text_secondary'],
                           activebackground=colors['card_bg'],
                           activeforeground=colors['text'],
                           selectcolor=colors['accent']).pack(side=tk.LEFT, padx=(0, 10))

        # Parameters
        tk.Label(content,
                 text="Parameters (JSON format):",
                 font=('Segoe UI', 10, 'bold'),
                 bg=colors['card_bg'],
                 fg=colors['text']).pack(anchor='w', pady=(0, 5))

        params_frame = tk.Frame(content, bg=colors['card_bg'])
        params_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.params_text = scrolledtext.ScrolledText(params_frame,
                                                     wrap=tk.WORD,
                                                     font=('Consolas', 9),
                                                     bg=colors['bg_light'],
                                                     fg=colors['text'],
                                                     insertbackground=colors['text'],
                                                     height=8)
        self.params_text.pack(fill=tk.BOTH, expand=True)

        # Load existing parameters
        if gifct_data and 'parameters' in gifct_data:
            params_str = json.dumps(gifct_data['parameters'], indent=2)
            self.params_text.insert(tk.END, params_str)
        else:
            default_params = {
                'cooldown': 10,
                'duration': 5,
                'power': 100,
                'range': 10,
                'cost': 20
            }
            self.params_text.insert(tk.END, json.dumps(default_params, indent=2))

        # Enabled by default
        self.enabled_var = tk.BooleanVar(value=gifct_data.get('enabled', True) if gifct_data else True)
        tk.Checkbutton(content,
                       text="Enabled by default",
                       variable=self.enabled_var,
                       font=('Segoe UI', 10),
                       bg=colors['card_bg'],
                       fg=colors['text_secondary'],
                       activebackground=colors['card_bg'],
                       activeforeground=colors['text'],
                       selectcolor=colors['accent']).pack(anchor='w', pady=(0, 20))

        # Buttons
        button_frame = tk.Frame(content, bg=colors['card_bg'])
        button_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(button_frame,
                  text="Save",
                  font=('Segoe UI', 10, 'bold'),
                  bg=colors['accent'],
                  fg='white',
                  activebackground=colors['accent_light'],
                  activeforeground='white',
                  relief='flat',
                  padx=20,
                  pady=8,
                  command=self.save).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(button_frame,
                  text="Cancel",
                  font=('Segoe UI', 10),
                  bg=colors['button_bg'],
                  fg=colors['button_fg'],
                  activebackground=colors['button_active'],
                  activeforeground=colors['button_fg'],
                  relief='flat',
                  padx=20,
                  pady=8,
                  command=self.cancel).pack(side=tk.LEFT)

    def save(self):
        """Save Gifct configuration"""
        try:
            # Validate parameters JSON
            params_text = self.params_text.get('1.0', tk.END).strip()
            if params_text:
                params = json.loads(params_text)
            else:
                params = {}

            self.result = {
                'name': self.name_var.get(),
                'id': self.id_var.get(),
                'description': self.desc_var.get(),
                'type': self.type_var.get(),
                'parameters': params,
                'enabled': self.enabled_var.get(),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            self.dialog.destroy()

        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Parameters must be valid JSON:\n{str(e)}")

    def cancel(self):
        """Cancel dialog"""
        self.result = None
        self.dialog.destroy()

    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result


class ServerGUI:
    def __init__(self, root, server_core_class):
        self.root = root
        self.server_core_class = server_core_class

        # Theme definitions (improved with more distinct differences)
        self.themes = {
            'black': {
                'name': 'Midnight Black',
                'bg': '#0d1117',
                'bg_light': '#161b22',
                'bg_lighter': '#21262d',
                'sidebar_bg': '#010409',
                'sidebar_active': '#1f6feb',
                'sidebar_hover': '#1f6feb',
                'sidebar_text': '#8b949e',
                'sidebar_active_text': '#ffffff',
                'sidebar_icon': '#8b949e',
                'text': '#f0f6fc',
                'text_secondary': '#8b949e',
                'accent': '#1f6feb',
                'accent_light': '#388bfd',
                'success': '#238636',
                'success_light': '#2ea043',
                'warning': '#9e6a03',
                'warning_light': '#d29922',
                'error': '#da3633',
                'error_light': '#f85149',
                'info': '#58a6ff',
                'info_light': '#79c0ff',
                'button_bg': '#21262d',
                'button_fg': '#c9d1d9',
                'button_active': '#30363d',
                'button_pressed': '#484f58',
                'button_disabled': '#6e7681',
                'border': '#30363d',
                'border_light': '#3c444d',
                'card_bg': '#161b22',
                'card_border': '#30363d'
            },
            'grey': {
                'name': 'Professional Grey',
                'bg': '#f8f9fa',
                'bg_light': '#ffffff',
                'bg_lighter': '#e9ecef',
                'sidebar_bg': '#2b2d42',
                'sidebar_active': '#ef233c',
                'sidebar_hover': '#ef233c',
                'sidebar_text': '#adb5bd',
                'sidebar_active_text': '#ffffff',
                'sidebar_icon': '#adb5bd',
                'text': '#212529',
                'text_secondary': '#6c757d',
                'accent': '#4361ee',
                'accent_light': '#4895ef',
                'success': '#4cc9f0',
                'success_light': '#38b000',
                'warning': '#f8961e',
                'warning_light': '#f9844a',
                'error': '#f72585',
                'error_light': '#7209b7',
                'info': '#4361ee',
                'info_light': '#3a0ca3',
                'button_bg': '#4361ee',
                'button_fg': '#ffffff',
                'button_active': '#3a56d4',
                'button_pressed': '#2f4ab2',
                'button_disabled': '#6c757d',
                'border': '#dee2e6',
                'border_light': '#ced4da',
                'card_bg': '#ffffff',
                'card_border': '#dee2e6'
            },
            'white': {
                'name': 'Pure White',
                'bg': '#ffffff',
                'bg_light': '#f8f9fa',
                'bg_lighter': '#e9ecef',
                'sidebar_bg': '#343a40',
                'sidebar_active': '#007bff',
                'sidebar_hover': '#007bff',
                'sidebar_text': '#adb5bd',
                'sidebar_active_text': '#ffffff',
                'sidebar_icon': '#adb5bd',
                'text': '#212529',
                'text_secondary': '#495057',
                'accent': '#007bff',
                'accent_light': '#0069d9',
                'success': '#28a745',
                'success_light': '#218838',
                'warning': '#ffc107',
                'warning_light': '#e0a800',
                'error': '#dc3545',
                'error_light': '#c82333',
                'info': '#17a2b8',
                'info_light': '#138496',
                'button_bg': '#007bff',
                'button_fg': '#ffffff',
                'button_active': '#0069d9',
                'button_pressed': '#0056b3',
                'button_disabled': '#6c757d',
                'border': '#dee2e6',
                'border_light': '#ced4da',
                'card_bg': '#ffffff',
                'card_border': '#dee2e6'
            },
            'dark_blue': {
                'name': 'Deep Blue',
                'bg': '#0a192f',
                'bg_light': '#112240',
                'bg_lighter': '#1d3a5f',
                'sidebar_bg': '#020c1b',
                'sidebar_active': '#64ffda',
                'sidebar_hover': '#64ffda',
                'sidebar_text': '#8892b0',
                'sidebar_active_text': '#ffffff',
                'sidebar_icon': '#64ffda',
                'text': '#ccd6f6',
                'text_secondary': '#8892b0',
                'accent': '#64ffda',
                'accent_light': '#52d3aa',
                'success': '#64ffda',
                'success_light': '#52d3aa',
                'warning': '#ffd166',
                'warning_light': '#ffb347',
                'error': '#ef476f',
                'error_light': '#ff6b6b',
                'info': '#118ab2',
                'info_light': '#06d6a0',
                'button_bg': '#1d3a5f',
                'button_fg': '#64ffda',
                'button_active': '#2a4a7a',
                'button_pressed': '#375a95',
                'button_disabled': '#4a6588',
                'border': '#1d3a5f',
                'border_light': '#2a4a7a',
                'card_bg': '#112240',
                'card_border': '#1d3a5f'
            }
        }

        # Current theme (default: black)
        self.current_theme = 'black'
        self.colors = self.themes[self.current_theme]

        # Window setup
        self.root.title("🎮 DPP2 UDP Server Controller")
        self.root.geometry("1600x900")
        self.root.configure(bg=self.colors['bg'])

        # Icon (if exists)
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass

        self.message_queue = queue.Queue()
        self.server = None
        self.server_running = False
        self.server_thread = None
        self.start_time = None
        self.current_section = 'dashboard'  # Current section

        self.stats = {
            'players_online': 0,
            'characters_online': 0,
            'total_characters': 0,
            'cpu_usage': 0,
            'memory_usage': 0,
            'uptime': '00:00:00',
            'connections': 0,
            'active_gifct': 'Gifct1, Gifct2',
            'udp_packets_received': 0,
            'udp_packets_sent': 0,
            'packet_loss': '0%',
            'protocol': 'UDP',
            'udp_port': 5555
        }

        self.config = self.load_config()

        # Load saved theme
        if 'theme' in self.config:
            self.current_theme = self.config['theme']
            if self.current_theme in self.themes:
                self.colors = self.themes[self.current_theme]

        # Initialize Gifct configurations
        if 'gifct_configurations' not in self.config:
            self.config['gifct_configurations'] = {}

        self.setup_styles()
        self.setup_ui()
        self.center_window()
        self.start_update_loop()

    def load_config(self):
        """Load configuration"""
        config_path = "config.json"
        default_config = {
            "server": {
                "host": "0.0.0.0",
                "port": 80,
                "max_players": 100,
                "tick_rate": 60,
                "log_level": "INFO",
                "server_name": "DPP2 UDP Character Server",
                "protocol": "udp"
            },
            "game": {
                "max_characters_per_player": 5,
                "starting_zone": "start_city",
                "auto_save_interval": 300
            },
            "database": {
                "path": "game_server_db.json"
            },
            "network": {
                "udp_port": 80,
                "max_packet_size": 1400,
                "client_timeout": 30,
                "heartbeat_interval": 1.0
            },
            "gifct_settings": {
                "gifct_enabled": {
                    "Gifct1": True,
                    "Gifct2": True
                },
                "gifct_configs": {
                    "Gifct1": "Primary Ability",
                    "Gifct2": "Secondary Ability"
                }
            },
            "gifct_configurations": {},
            "theme": "black"
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)

                for key in default_config:
                    if key not in loaded_config:
                        loaded_config[key] = default_config[key]
                    elif isinstance(default_config[key], dict):
                        for subkey in default_config[key]:
                            if subkey not in loaded_config[key]:
                                loaded_config[key][subkey] = default_config[key][subkey]

                return loaded_config
            else:
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
                return default_config

        except Exception as e:
            print(f"Config loading error: {e}")
            return default_config

    def setup_styles(self):
        """Setup styles"""
        style = ttk.Style()
        style.theme_use('clam')

        # Common styles
        style.configure('Title.TLabel',
                        font=('Segoe UI', 18, 'bold'),
                        foreground=self.colors['text'],
                        background=self.colors['bg'])

        style.configure('Subtitle.TLabel',
                        font=('Segoe UI', 14, 'bold'),
                        foreground=self.colors['accent'],
                        background=self.colors['bg'])

        style.configure('Normal.TLabel',
                        font=('Segoe UI', 10),
                        foreground=self.colors['text_secondary'],
                        background=self.colors['bg'])

        style.configure('Value.TLabel',
                        font=('Segoe UI', 11, 'bold'),
                        foreground=self.colors['text'],
                        background=self.colors['bg'])

        style.configure('Card.TFrame',
                        background=self.colors['card_bg'],
                        relief='flat',
                        borderwidth=1)

        style.configure('Card.TLabelframe',
                        background=self.colors['card_bg'],
                        foreground=self.colors['text'],
                        bordercolor=self.colors['card_border'],
                        relief='solid',
                        borderwidth=1)

        style.configure('Card.TLabelframe.Label',
                        font=('Segoe UI', 11, 'bold'),
                        foreground=self.colors['accent'],
                        background=self.colors['card_bg'])

    def center_window(self):
        """Center window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def setup_ui(self):
        """Setup main interface"""
        # Main container
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill=tk.BOTH, expand=True)

        # Top bar
        self.create_top_bar(main_container)

        # Main container (sidebar + content)
        content_container = tk.Frame(main_container, bg=self.colors['bg'])
        content_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Sidebar
        self.sidebar_frame = tk.Frame(content_container,
                                      bg=self.colors['sidebar_bg'],
                                      width=220)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        self.create_sidebar()

        # Content area
        self.content_frame = tk.Frame(content_container, bg=self.colors['bg'])
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # Initialize sections
        self.sections = {}
        self.create_sections()

        # Show dashboard by default
        self.show_section('dashboard')

        # Bottom bar
        self.create_bottom_bar(main_container)

    def create_top_bar(self, parent):
        """Create top bar"""
        top_bar = tk.Frame(parent,
                           bg=self.colors['bg_lighter'],
                           height=60)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)

        # Logo and title
        logo_frame = tk.Frame(top_bar, bg=self.colors['bg_lighter'])
        logo_frame.pack(side=tk.LEFT, padx=20, pady=10)

        tk.Label(logo_frame,
                 text="🎮 DPP2 UDP SERVER",
                 font=('Segoe UI', 16, 'bold'),
                 bg=self.colors['bg_lighter'],
                 fg=self.colors['text']).pack(side=tk.LEFT)

        # Protocol indicator
        protocol_frame = tk.Frame(top_bar, bg=self.colors['bg_lighter'])
        protocol_frame.pack(side=tk.LEFT, padx=20)

        self.protocol_indicator = tk.Canvas(protocol_frame,
                                            width=24, height=24,
                                            bg=self.colors['accent'],
                                            highlightthickness=0)
        self.protocol_indicator.pack(side=tk.LEFT)
        self.protocol_indicator.create_text(12, 12, text="U",
                                            fill='white',
                                            font=('Segoe UI', 10, 'bold'))

        tk.Label(protocol_frame,
                 text="UDP PROTOCOL",
                 font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['bg_lighter'],
                 fg=self.colors['accent']).pack(side=tk.LEFT, padx=5)

        # Server status
        status_frame = tk.Frame(top_bar, bg=self.colors['bg_lighter'])
        status_frame.pack(side=tk.RIGHT, padx=20, pady=10)

        self.status_label = tk.Label(status_frame,
                                     text="● STOPPED",
                                     font=('Segoe UI', 11, 'bold'),
                                     bg=self.colors['bg_lighter'],
                                     fg=self.colors['error'])
        self.status_label.pack(side=tk.RIGHT, padx=(10, 0))

        self.status_indicator = tk.Canvas(status_frame,
                                          width=20, height=20,
                                          bg=self.colors['error'],
                                          highlightthickness=0)
        self.status_indicator.pack(side=tk.RIGHT)
        self.status_indicator.create_oval(2, 2, 18, 18,
                                          fill=self.colors['error'],
                                          outline='white')

    def create_sidebar(self):
        """Create sidebar"""
        # Sidebar header
        sidebar_header = tk.Frame(self.sidebar_frame,
                                  bg=self.colors['sidebar_active'],
                                  height=50)
        sidebar_header.pack(fill=tk.X, side=tk.TOP)

        tk.Label(sidebar_header,
                 text="NAVIGATION",
                 font=('Segoe UI', 12, 'bold'),
                 bg=self.colors['sidebar_active'],
                 fg=self.colors['sidebar_active_text']).pack(pady=15)

        # Navigation buttons
        nav_buttons_frame = tk.Frame(self.sidebar_frame,
                                     bg=self.colors['sidebar_bg'])
        nav_buttons_frame.pack(fill=tk.X, side=tk.TOP, pady=10)

        # Create navigation buttons
        nav_items = [
            ("🏠", "Dashboard", 'dashboard'),
            ("⚙️", "Server Settings", 'server_settings'),
            ("🎨", "Appearance", 'appearance'),
            ("🌐", "Network", 'network'),
            ("🎮", "Gifct Settings", 'gifct'),
            ("📊", "Statistics", 'stats'),
            ("📋", "Logs", 'logs'),
            ("👥", "Players", 'players'),
            ("🗃️", "Database", 'database'),
            ("🛠️", "Tools", 'tools'),
            ("❓", "Help", 'help')
        ]

        self.nav_buttons = {}
        for icon, text, section in nav_items:
            btn = SidebarButton(nav_buttons_frame, text, icon,
                                command=lambda s=section: self.show_section(s),
                                colors=self.colors)
            btn.pack(fill=tk.X, side=tk.TOP, pady=1)
            self.nav_buttons[section] = btn

        # Separator
        separator = tk.Frame(self.sidebar_frame,
                             bg=self.colors['border'],
                             height=1)
        separator.pack(fill=tk.X, side=tk.TOP, pady=20)

        # Server info at bottom
        info_frame = tk.Frame(self.sidebar_frame,
                              bg=self.colors['sidebar_bg'])
        info_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)

        tk.Label(info_frame,
                 text=f"Version: 2.1",
                 font=('Segoe UI', 8),
                 bg=self.colors['sidebar_bg'],
                 fg=self.colors['sidebar_text']).pack(anchor='w')

        tk.Label(info_frame,
                 text=f"Protocol: UDP",
                 font=('Segoe UI', 8),
                 bg=self.colors['sidebar_bg'],
                 fg=self.colors['sidebar_text']).pack(anchor='w')

    def create_sections(self):
        """Create all content sections"""
        # Dashboard
        self.create_dashboard_section()

        # Server settings
        self.create_server_settings_section()

        # Appearance (new section)
        self.create_appearance_section()

        # Network settings
        self.create_network_section()

        # Gifct settings
        self.create_gifct_section()

        # Statistics
        self.create_stats_section()

        # Logs
        self.create_logs_section()

        # Players
        self.create_players_section()

        # Database
        self.create_database_section()

        # Tools
        self.create_tools_section()

        # Help
        self.create_help_section()

    def create_dashboard_section(self):
        """Create Dashboard section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['dashboard'] = frame

        # Title
        title_frame = tk.Frame(frame, bg=self.colors['bg'])
        title_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(title_frame,
                 text="Dashboard",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(side=tk.LEFT)

        # Server status and control
        control_card = tk.Frame(frame, bg=self.colors['card_bg'],
                                relief='solid', borderwidth=1)
        control_card.pack(fill=tk.X, pady=(0, 20))

        # Card header
        control_header = tk.Frame(control_card, bg=self.colors['bg_lighter'])
        control_header.pack(fill=tk.X, pady=10, padx=10)

        tk.Label(control_header,
                 text="Server Control",
                 font=('Segoe UI', 14, 'bold'),
                 bg=self.colors['bg_lighter'],
                 fg=self.colors['text']).pack(side=tk.LEFT)

        # Control buttons
        button_frame = tk.Frame(control_card, bg=self.colors['card_bg'])
        button_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        self.start_btn = tk.Button(button_frame,
                                   text="▶ Start Server",
                                   font=('Segoe UI', 11, 'bold'),
                                   bg=self.colors['success'],
                                   fg='white',
                                   activebackground=self.colors['success_light'],
                                   activeforeground='white',
                                   relief='flat',
                                   padx=20,
                                   pady=10,
                                   command=self.start_server)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = tk.Button(button_frame,
                                  text="■ Stop",
                                  font=('Segoe UI', 11, 'bold'),
                                  bg=self.colors['error'],
                                  fg='white',
                                  activebackground=self.colors['error_light'],
                                  activeforeground='white',
                                  relief='flat',
                                  padx=20,
                                  pady=10,
                                  state=tk.DISABLED,
                                  command=self.stop_server)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        self.restart_btn = tk.Button(button_frame,
                                     text="↻ Restart",
                                     font=('Segoe UI', 11, 'bold'),
                                     bg=self.colors['warning'],
                                     fg='white',
                                     activebackground=self.colors['warning_light'],
                                     activeforeground='white',
                                     relief='flat',
                                     padx=20,
                                     pady=10,
                                     state=tk.DISABLED,
                                     command=self.restart_server)
        self.restart_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Quick statistics
        stats_grid = tk.Frame(frame, bg=self.colors['bg'])
        stats_grid.pack(fill=tk.BOTH, expand=True)

        # Create stat cards
        stat_cards = [
            ("👥", "Players Online", "players_online", "0"),
            ("📊", "Characters", "total_characters", "0"),
            ("⚡", "CPU Load", "cpu_usage", "0%"),
            ("💾", "Memory", "memory_usage", "0 MB"),
            ("⏱️", "Uptime", "uptime", "00:00:00"),
            ("📡", "UDP Packets", "udp_packets_total", "0"),
            ("🎮", "Active Gifct", "active_gifct", "Gifct1, Gifct2"),
            ("🔌", "Connections", "connections", "0")
        ]

        self.stats_vars = {}
        for i, (icon, title, key, default) in enumerate(stat_cards):
            row = i // 4
            col = i % 4

            card = tk.Frame(stats_grid, bg=self.colors['card_bg'],
                            relief='solid', borderwidth=1)
            card.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

            # Icon and title
            icon_frame = tk.Frame(card, bg=self.colors['card_bg'])
            icon_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

            tk.Label(icon_frame,
                     text=icon,
                     font=('Segoe UI', 14),
                     bg=self.colors['card_bg'],
                     fg=self.colors['accent']).pack(side=tk.LEFT)

            tk.Label(icon_frame,
                     text=title,
                     font=('Segoe UI', 9),
                     bg=self.colors['card_bg'],
                     fg=self.colors['text_secondary']).pack(side=tk.LEFT, padx=5)

            # Value
            var = tk.StringVar(value=default)
            self.stats_vars[key] = var

            value_label = tk.Label(card,
                                   textvariable=var,
                                   font=('Segoe UI', 16, 'bold'),
                                   bg=self.colors['card_bg'],
                                   fg=self.colors['text'])
            value_label.pack(pady=(0, 10))

        # Configure grid weights
        for i in range(4):
            stats_grid.columnconfigure(i, weight=1)
        for i in range(2):
            stats_grid.rowconfigure(i, weight=1)

    def create_server_settings_section(self):
        """Create Server Settings section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['server_settings'] = frame

        # Title
        tk.Label(frame,
                 text="Server Settings",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

        # Main settings
        main_settings_frame = tk.LabelFrame(frame,
                                            text="Main Settings",
                                            font=('Segoe UI', 12, 'bold'),
                                            bg=self.colors['card_bg'],
                                            fg=self.colors['text'],
                                            relief='solid',
                                            borderwidth=1)
        main_settings_frame.pack(fill=tk.X, pady=(0, 20))

        settings_grid = tk.Frame(main_settings_frame, bg=self.colors['card_bg'])
        settings_grid.pack(fill=tk.X, padx=20, pady=20)

        # Settings fields
        settings = [
            ("Server Name:", "server_name", self.config['server']['server_name']),
            ("UDP Port:", "udp_port", str(self.config['server']['port'])),
            ("Max Players:", "max_players", str(self.config['server']['max_players'])),
            ("Tick Rate:", "tick_rate", str(self.config['server']['tick_rate'])),
            ("Log Level:", "log_level", self.config['server']['log_level']),
            ("Protocol:", "protocol", self.config['server']['protocol'])
        ]

        self.server_settings_vars = {}
        for i, (label, key, default) in enumerate(settings):
            row_frame = tk.Frame(settings_grid, bg=self.colors['card_bg'])
            row_frame.grid(row=i, column=0, sticky='w', pady=5)

            tk.Label(row_frame,
                     text=label,
                     font=('Segoe UI', 10),
                     bg=self.colors['card_bg'],
                     fg=self.colors['text_secondary'],
                     width=15).pack(side=tk.LEFT)

            if key == 'log_level':
                var = tk.StringVar(value=default)
                combo = ttk.Combobox(row_frame,
                                     textvariable=var,
                                     values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                     state='readonly',
                                     width=20)
                combo.pack(side=tk.LEFT, padx=5)
            else:
                var = tk.StringVar(value=default)
                entry = tk.Entry(row_frame,
                                 textvariable=var,
                                 font=('Segoe UI', 10),
                                 bg=self.colors['bg_light'],
                                 fg=self.colors['text'],
                                 insertbackground=self.colors['text'],
                                 width=22)
                entry.pack(side=tk.LEFT, padx=5)

            self.server_settings_vars[key] = var

        # Save button
        button_frame = tk.Frame(main_settings_frame, bg=self.colors['card_bg'])
        button_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Button(button_frame,
                  text="Save Settings",
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.colors['accent'],
                  fg='white',
                  activebackground=self.colors['accent_light'],
                  activeforeground='white',
                  relief='flat',
                  padx=20,
                  pady=8,
                  command=self.save_server_settings).pack()

    def create_appearance_section(self):
        """Create Appearance section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['appearance'] = frame

        tk.Label(frame,
                 text="Appearance Settings",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

        # Theme selection card
        theme_card = tk.LabelFrame(frame,
                                   text="Theme Selection",
                                   font=('Segoe UI', 12, 'bold'),
                                   bg=self.colors['card_bg'],
                                   fg=self.colors['text'],
                                   relief='solid',
                                   borderwidth=1)
        theme_card.pack(fill=tk.X, pady=(0, 20))

        content_frame = tk.Frame(theme_card, bg=self.colors['card_bg'])
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        # Description
        tk.Label(content_frame,
                 text="Select interface theme:",
                 font=('Segoe UI', 10),
                 bg=self.colors['card_bg'],
                 fg=self.colors['text_secondary']).pack(anchor='w', pady=(0, 15))

        # Theme previews
        previews_frame = tk.Frame(content_frame, bg=self.colors['card_bg'])
        previews_frame.pack(fill=tk.X, pady=(0, 20))

        self.theme_previews = {}
        for theme_name in ['black', 'grey', 'white', 'dark_blue']:
            preview = ThemePreview(previews_frame,
                                   theme_name,
                                   self.themes[theme_name],
                                   command=self.change_theme)
            preview.pack(side=tk.LEFT, padx=(0, 10))
            self.theme_previews[theme_name] = preview

        # Update current theme selection
        for theme_name, preview in self.theme_previews.items():
            preview.set_selected(theme_name == self.current_theme)

        # Color palette card
        colors_card = tk.LabelFrame(frame,
                                    text="Current Theme Color Palette",
                                    font=('Segoe UI', 12, 'bold'),
                                    bg=self.colors['card_bg'],
                                    fg=self.colors['text'],
                                    relief='solid',
                                    borderwidth=1)
        colors_card.pack(fill=tk.X, pady=(0, 20))

        colors_content = tk.Frame(colors_card, bg=self.colors['card_bg'])
        colors_content.pack(fill=tk.X, padx=20, pady=20)

        # Current theme color palette
        color_groups = [
            ("Main Colors", ['bg', 'bg_light', 'bg_lighter', 'text', 'text_secondary']),
            ("Accent Colors", ['accent', 'accent_light', 'success', 'warning', 'error', 'info']),
            ("Interface Elements", ['sidebar_bg', 'sidebar_active', 'button_bg', 'border', 'card_bg'])
        ]

        for group_name, color_keys in color_groups:
            tk.Label(colors_content,
                     text=group_name + ":",
                     font=('Segoe UI', 10, 'bold'),
                     bg=self.colors['card_bg'],
                     fg=self.colors['text']).pack(anchor='w', pady=(10, 5))

            colors_frame = tk.Frame(colors_content, bg=self.colors['card_bg'])
            colors_frame.pack(fill=tk.X, pady=(0, 10))

            for color_key in color_keys:
                if color_key in self.colors:
                    color_frame = tk.Frame(colors_frame, bg=self.colors['card_bg'])
                    color_frame.pack(side=tk.LEFT, padx=(0, 15))

                    # Color square
                    color_canvas = tk.Canvas(color_frame,
                                             width=40, height=40,
                                             bg=self.colors[color_key],
                                             highlightthickness=1,
                                             highlightbackground=self.colors['border'])
                    color_canvas.pack()

                    # Color name and HEX code
                    tk.Label(color_frame,
                             text=color_key,
                             font=('Segoe UI', 8),
                             bg=self.colors['card_bg'],
                             fg=self.colors['text_secondary']).pack()

                    tk.Label(color_frame,
                             text=self.colors[color_key],
                             font=('Segoe UI', 8),
                             bg=self.colors['card_bg'],
                             fg=self.colors['text_secondary']).pack()

        # Font settings
        font_card = tk.LabelFrame(frame,
                                  text="Font Settings",
                                  font=('Segoe UI', 12, 'bold'),
                                  bg=self.colors['card_bg'],
                                  fg=self.colors['text'],
                                  relief='solid',
                                  borderwidth=1)
        font_card.pack(fill=tk.X, pady=(0, 20))

        font_content = tk.Frame(font_card, bg=self.colors['card_bg'])
        font_content.pack(fill=tk.X, padx=20, pady=20)

        # Font size selection
        tk.Label(font_content,
                 text="Interface Font Size:",
                 font=('Segoe UI', 10),
                 bg=self.colors['card_bg'],
                 fg=self.colors['text_secondary']).pack(anchor='w', pady=(0, 5))

        font_size_frame = tk.Frame(font_content, bg=self.colors['card_bg'])
        font_size_frame.pack(fill=tk.X, pady=(0, 15))

        self.font_size_var = tk.StringVar(value="10")
        for size in ["8", "9", "10", "11", "12"]:
            tk.Radiobutton(font_size_frame,
                           text=size,
                           variable=self.font_size_var,
                           value=size,
                           font=('Segoe UI', 10),
                           bg=self.colors['card_bg'],
                           fg=self.colors['text'],
                           activebackground=self.colors['card_bg'],
                           activeforeground=self.colors['text'],
                           selectcolor=self.colors['accent']).pack(side=tk.LEFT, padx=(0, 15))

        # Control buttons
        button_frame = tk.Frame(frame, bg=self.colors['bg'])
        button_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Button(button_frame,
                  text="Reset Settings",
                  font=('Segoe UI', 10),
                  bg=self.colors['button_bg'],
                  fg=self.colors['button_fg'],
                  activebackground=self.colors['button_active'],
                  activeforeground=self.colors['button_fg'],
                  relief='flat',
                  padx=15,
                  pady=8,
                  command=self.reset_appearance_settings).pack(side=tk.LEFT, padx=(0, 10))

    def create_network_section(self):
        """Create Network section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['network'] = frame

        tk.Label(frame,
                 text="Network Settings",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

        # Network settings card
        network_card = tk.LabelFrame(frame,
                                     text="UDP Parameters",
                                     font=('Segoe UI', 12, 'bold'),
                                     bg=self.colors['card_bg'],
                                     fg=self.colors['text'],
                                     relief='solid',
                                     borderwidth=1)
        network_card.pack(fill=tk.X, pady=(0, 20))

        settings_grid = tk.Frame(network_card, bg=self.colors['card_bg'])
        settings_grid.pack(fill=tk.X, padx=20, pady=20)

        network_settings = [
            ("Max Packet Size (bytes):", "max_packet_size", str(self.config['network']['max_packet_size'])),
            ("Client Timeout (sec):", "client_timeout", str(self.config['network']['client_timeout'])),
            ("Heartbeat Interval (sec):", "heartbeat_interval", str(self.config['network']['heartbeat_interval'])),
            ("Packet Loss:", "packet_loss", "0%")
        ]

        self.network_settings_vars = {}
        for i, (label, key, default) in enumerate(network_settings):
            row_frame = tk.Frame(settings_grid, bg=self.colors['card_bg'])
            row_frame.grid(row=i, column=0, sticky='w', pady=5)

            tk.Label(row_frame,
                     text=label,
                     font=('Segoe UI', 10),
                     bg=self.colors['card_bg'],
                     fg=self.colors['text_secondary'],
                     width=25).pack(side=tk.LEFT)

            var = tk.StringVar(value=default)
            entry = tk.Entry(row_frame,
                             textvariable=var,
                             font=('Segoe UI', 10),
                             bg=self.colors['bg_light'],
                             fg=self.colors['text'],
                             insertbackground=self.colors['text'],
                             width=15)
            entry.pack(side=tk.LEFT, padx=5)

            self.network_settings_vars[key] = var

        # Network test buttons
        test_frame = tk.Frame(network_card, bg=self.colors['card_bg'])
        test_frame.pack(fill=tk.X, pady=(0, 10), padx=20)

        tk.Button(test_frame,
                  text="Test UDP Connection",
                  font=('Segoe UI', 10),
                  bg=self.colors['info'],
                  fg='white',
                  activebackground=self.colors['info_light'],
                  activeforeground='white',
                  relief='flat',
                  padx=15,
                  pady=6,
                  command=self.test_udp_connection).pack(side=tk.LEFT, padx=(0, 10))

    def create_gifct_section(self):
        """Create Gifct Settings section with ability to add new Gifct"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['gifct'] = frame

        tk.Label(frame,
                 text="Gifct Settings",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

        # Gifct management frame
        gifct_frame = tk.LabelFrame(frame,
                                    text="Gifct Management",
                                    font=('Segoe UI', 12, 'bold'),
                                    bg=self.colors['card_bg'],
                                    fg=self.colors['text'],
                                    relief='solid',
                                    borderwidth=1)
        gifct_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Create two columns: list of Gifct and configuration
        main_container = tk.Frame(gifct_frame, bg=self.colors['card_bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Left column: Gifct list
        left_column = tk.Frame(main_container, bg=self.colors['card_bg'], width=300)
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        left_column.pack_propagate(False)

        # Gifct list header
        list_header = tk.Frame(left_column, bg=self.colors['bg_lighter'], height=40)
        list_header.pack(fill=tk.X, pady=(0, 10))
        list_header.pack_propagate(False)

        tk.Label(list_header,
                 text="Available Gifct",
                 font=('Segoe UI', 11, 'bold'),
                 bg=self.colors['bg_lighter'],
                 fg=self.colors['text']).pack(pady=10)

        # Gifct list with scrollbar
        list_container = tk.Frame(left_column, bg=self.colors['card_bg'])
        list_container.pack(fill=tk.BOTH, expand=True)

        # Create canvas with scrollbar for Gifct list
        canvas = tk.Canvas(list_container, bg=self.colors['card_bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['card_bg'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load Gifct configurations
        self.gifct_list_frame = scrollable_frame
        self.load_gifct_list()

        # Add Gifct button
        add_button_frame = tk.Frame(left_column, bg=self.colors['card_bg'])
        add_button_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(add_button_frame,
                  text="＋ Add New Gifct",
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.colors['success'],
                  fg='white',
                  activebackground=self.colors['success_light'],
                  activeforeground='white',
                  relief='flat',
                  padx=15,
                  pady=8,
                  command=self.add_gifct).pack(fill=tk.X)

        # Right column: Gifct configuration
        right_column = tk.Frame(main_container, bg=self.colors['card_bg'])
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Basic Gifct settings
        tk.Label(right_column,
                 text="Basic Gifct Settings",
                 font=('Segoe UI', 12, 'bold'),
                 bg=self.colors['card_bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 15))

        # Enable/disable Gifct
        enable_frame = tk.Frame(right_column, bg=self.colors['card_bg'])
        enable_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(enable_frame,
                 text="Active Gifct:",
                 font=('Segoe UI', 11),
                 bg=self.colors['card_bg'],
                 fg=self.colors['text']).pack(side=tk.LEFT, padx=(0, 20))

        self.gifct1_enabled_var = tk.BooleanVar(
            value=self.config['gifct_settings']['gifct_enabled'].get('Gifct1', True))
        self.gifct1_check = tk.Checkbutton(enable_frame,
                                           text="Gifct 1",
                                           font=('Segoe UI', 10),
                                           variable=self.gifct1_enabled_var,
                                           command=self.update_gifct_status,
                                           bg=self.colors['card_bg'],
                                           fg=self.colors['text'],
                                           activebackground=self.colors['card_bg'],
                                           activeforeground=self.colors['text'],
                                           selectcolor=self.colors['accent'])
        self.gifct1_check.pack(side=tk.LEFT, padx=10)

        self.gifct2_enabled_var = tk.BooleanVar(
            value=self.config['gifct_settings']['gifct_enabled'].get('Gifct2', True))
        self.gifct2_check = tk.Checkbutton(enable_frame,
                                           text="Gifct 2",
                                           font=('Segoe UI', 10),
                                           variable=self.gifct2_enabled_var,
                                           command=self.update_gifct_status,
                                           bg=self.colors['card_bg'],
                                           fg=self.colors['text'],
                                           activebackground=self.colors['card_bg'],
                                           activeforeground=self.colors['text'],
                                           selectcolor=self.colors['accent'])
        self.gifct2_check.pack(side=tk.LEFT, padx=10)

        # Gifct 1 settings
        gifct1_frame = tk.LabelFrame(right_column,
                                     text="Gifct 1 Settings",
                                     font=('Segoe UI', 10, 'bold'),
                                     bg=self.colors['bg'],
                                     fg=self.colors['text_secondary'],
                                     relief='solid',
                                     borderwidth=1)
        gifct1_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(gifct1_frame,
                 text="Name:",
                 font=('Segoe UI', 9),
                 bg=self.colors['bg'],
                 fg=self.colors['text_secondary']).pack(anchor='w', padx=10, pady=(10, 5))

        self.gifct1_name_var = tk.StringVar(
            value=self.config['gifct_settings']['gifct_configs'].get('Gifct1', 'Primary Ability'))
        tk.Entry(gifct1_frame,
                 textvariable=self.gifct1_name_var,
                 font=('Segoe UI', 10),
                 bg=self.colors['bg_light'],
                 fg=self.colors['text'],
                 insertbackground=self.colors['text']).pack(fill=tk.X, padx=10, pady=(0, 10))

        # Gifct 2 settings
        gifct2_frame = tk.LabelFrame(right_column,
                                     text="Gifct 2 Settings",
                                     font=('Segoe UI', 10, 'bold'),
                                     bg=self.colors['bg'],
                                     fg=self.colors['text_secondary'],
                                     relief='solid',
                                     borderwidth=1)
        gifct2_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(gifct2_frame,
                 text="Name:",
                 font=('Segoe UI', 9),
                 bg=self.colors['bg'],
                 fg=self.colors['text_secondary']).pack(anchor='w', padx=10, pady=(10, 5))

        self.gifct2_name_var = tk.StringVar(
            value=self.config['gifct_settings']['gifct_configs'].get('Gifct2', 'Secondary Ability'))
        tk.Entry(gifct2_frame,
                 textvariable=self.gifct2_name_var,
                 font=('Segoe UI', 10),
                 bg=self.colors['bg_light'],
                 fg=self.colors['text'],
                 insertbackground=self.colors['text']).pack(fill=tk.X, padx=10, pady=(0, 10))

        # Control buttons
        button_frame = tk.Frame(right_column, bg=self.colors['card_bg'])
        button_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(button_frame,
                  text="Save Settings",
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.colors['accent'],
                  fg='white',
                  activebackground=self.colors['accent_light'],
                  activeforeground='white',
                  relief='flat',
                  padx=20,
                  pady=8,
                  command=self.save_gifct_settings).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(button_frame,
                  text="Reset to Default",
                  font=('Segoe UI', 10),
                  bg=self.colors['button_bg'],
                  fg=self.colors['button_fg'],
                  activebackground=self.colors['button_active'],
                  activeforeground=self.colors['button_fg'],
                  relief='flat',
                  padx=15,
                  pady=8,
                  command=self.reset_gifct_settings).pack(side=tk.LEFT)

    def load_gifct_list(self):
        """Load and display Gifct configurations list"""
        # Clear existing list
        for widget in self.gifct_list_frame.winfo_children():
            widget.destroy()

        # Get Gifct configurations
        gifct_configs = self.config.get('gifct_configurations', {})

        if not gifct_configs:
            # Show empty message
            tk.Label(self.gifct_list_frame,
                     text="No Gifct configurations found.\nClick 'Add New Gifct' to create one.",
                     font=('Segoe UI', 10),
                     bg=self.colors['card_bg'],
                     fg=self.colors['text_secondary'],
                     justify=tk.CENTER).pack(pady=20)
            return

        # Display each Gifct
        for gifct_id, gifct_data in gifct_configs.items():
            self.create_gifct_list_item(gifct_id, gifct_data)

    def create_gifct_list_item(self, gifct_id, gifct_data):
        """Create a Gifct item in the list"""
        item_frame = tk.Frame(self.gifct_list_frame,
                              bg=self.colors['bg_light'],
                              relief='solid',
                              borderwidth=1)
        item_frame.pack(fill=tk.X, pady=2, padx=2)

        # Left side: Gifct info
        info_frame = tk.Frame(item_frame, bg=self.colors['bg_light'])
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=5)

        # Gifct name and type
        tk.Label(info_frame,
                 text=gifct_data.get('name', 'Unnamed Gifct'),
                 font=('Segoe UI', 10, 'bold'),
                 bg=self.colors['bg_light'],
                 fg=self.colors['text']).pack(anchor='w')

        type_frame = tk.Frame(info_frame, bg=self.colors['bg_light'])
        type_frame.pack(anchor='w', pady=(2, 0))

        # Type badge
        type_color = {
            'ability': self.colors['info'],
            'skill': self.colors['accent'],
            'item': self.colors['success'],
            'buff': self.colors['warning'],
            'debuff': self.colors['error'],
            'custom': self.colors['text_secondary']
        }.get(gifct_data.get('type', 'custom'), self.colors['text_secondary'])

        type_canvas = tk.Canvas(type_frame,
                                width=8, height=8,
                                bg=type_color,
                                highlightthickness=0)
        type_canvas.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(type_frame,
                 text=gifct_data.get('type', 'custom').upper(),
                 font=('Segoe UI', 8),
                 bg=self.colors['bg_light'],
                 fg=self.colors['text_secondary']).pack(side=tk.LEFT)

        # Right side: Action buttons
        button_frame = tk.Frame(item_frame, bg=self.colors['bg_light'])
        button_frame.pack(side=tk.RIGHT, padx=(0, 5))

        # Edit button
        edit_btn = tk.Button(button_frame,
                             text="✏️",
                             font=('Segoe UI', 9),
                             bg='transparent',
                             fg=self.colors['text_secondary'],
                             activebackground=self.colors['bg_light'],
                             activeforeground=self.colors['accent'],
                             relief='flat',
                             padx=5,
                             command=lambda id=gifct_id: self.edit_gifct(id))
        edit_btn.pack(side=tk.LEFT, padx=2)

        # Delete button
        delete_btn = tk.Button(button_frame,
                               text="🗑️",
                               font=('Segoe UI', 9),
                               bg='transparent',
                               fg=self.colors['text_secondary'],
                               activebackground=self.colors['bg_light'],
                               activeforeground=self.colors['error'],
                               relief='flat',
                               padx=5,
                               command=lambda id=gifct_id: self.delete_gifct(id))
        delete_btn.pack(side=tk.LEFT, padx=2)

        # Enabled status
        enabled = gifct_data.get('enabled', True)
        status_color = self.colors['success'] if enabled else self.colors['error']
        status_text = "●" if enabled else "○"

        status_btn = tk.Button(button_frame,
                               text=status_text,
                               font=('Segoe UI', 9),
                               bg='transparent',
                               fg=status_color,
                               activebackground=self.colors['bg_light'],
                               activeforeground=status_color,
                               relief='flat',
                               padx=5,
                               command=lambda id=gifct_id: self.toggle_gifct_status(id))
        status_btn.pack(side=tk.LEFT, padx=2)

    def add_gifct(self):
        """Add new Gifct configuration"""
        dialog = GifctConfigDialog(self.root, "Add New Gifct", colors=self.colors)
        result = dialog.show()

        if result:
            # Add new Gifct to configurations
            gifct_id = result['id']
            self.config['gifct_configurations'][gifct_id] = result

            # Save configuration
            self.save_config()

            # Reload Gifct list
            self.load_gifct_list()

            self.log_message(f"Gifct '{result['name']}' added successfully", 'SUCCESS')

    def edit_gifct(self, gifct_id):
        """Edit existing Gifct configuration"""
        if gifct_id in self.config['gifct_configurations']:
            gifct_data = self.config['gifct_configurations'][gifct_id]
            dialog = GifctConfigDialog(self.root, "Edit Gifct", gifct_data, self.colors)
            result = dialog.show()

            if result:
                # Update Gifct configuration
                result['updated_at'] = datetime.now().isoformat()
                self.config['gifct_configurations'][gifct_id] = result

                # Save configuration
                self.save_config()

                # Reload Gifct list
                self.load_gifct_list()

                self.log_message(f"Gifct '{result['name']}' updated successfully", 'SUCCESS')

    def delete_gifct(self, gifct_id):
        """Delete Gifct configuration"""
        if gifct_id in self.config['gifct_configurations']:
            gifct_name = self.config['gifct_configurations'][gifct_id].get('name', gifct_id)

            if messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete Gifct '{gifct_name}'?"):
                # Remove Gifct from configurations
                del self.config['gifct_configurations'][gifct_id]

                # Save configuration
                self.save_config()

                # Reload Gifct list
                self.load_gifct_list()

                self.log_message(f"Gifct '{gifct_name}' deleted successfully", 'SUCCESS')

    def toggle_gifct_status(self, gifct_id):
        """Toggle Gifct enabled status"""
        if gifct_id in self.config['gifct_configurations']:
            current_status = self.config['gifct_configurations'][gifct_id].get('enabled', True)
            self.config['gifct_configurations'][gifct_id]['enabled'] = not current_status
            self.config['gifct_configurations'][gifct_id]['updated_at'] = datetime.now().isoformat()

            # Save configuration
            self.save_config()

            # Reload Gifct list
            self.load_gifct_list()

            gifct_name = self.config['gifct_configurations'][gifct_id].get('name', gifct_id)
            new_status = "enabled" if not current_status else "disabled"
            self.log_message(f"Gifct '{gifct_name}' {new_status}", 'GIFCT')

    def create_stats_section(self):
        """Create Statistics section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['stats'] = frame

        tk.Label(frame,
                 text="Detailed Statistics",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

    def create_logs_section(self):
        """Create Logs section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['logs'] = frame

        tk.Label(frame,
                 text="Server Logs",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

        # Log toolbar
        toolbar = tk.Frame(frame, bg=self.colors['card_bg'])
        toolbar.pack(fill=tk.X, pady=(0, 10))

        tk.Button(toolbar,
                  text="Clear",
                  font=('Segoe UI', 9),
                  bg=self.colors['button_bg'],
                  fg=self.colors['button_fg'],
                  activebackground=self.colors['button_active'],
                  activeforeground=self.colors['button_fg'],
                  relief='flat',
                  padx=12,
                  pady=5,
                  command=self.clear_logs).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(toolbar,
                  text="Export",
                  font=('Segoe UI', 9),
                  bg=self.colors['button_bg'],
                  fg=self.colors['button_fg'],
                  activebackground=self.colors['button_active'],
                  activeforeground=self.colors['button_fg'],
                  relief='flat',
                  padx=12,
                  pady=5,
                  command=self.export_logs).pack(side=tk.LEFT, padx=5)

        # Log level
        tk.Label(toolbar,
                 text="Level:",
                 font=('Segoe UI', 9),
                 bg=self.colors['card_bg'],
                 fg=self.colors['text_secondary']).pack(side=tk.LEFT, padx=(20, 5))

        self.log_level_var = tk.StringVar(value=self.config['server']['log_level'])
        log_level_combo = ttk.Combobox(toolbar,
                                       textvariable=self.log_level_var,
                                       values=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                                       state='readonly',
                                       width=12)
        log_level_combo.pack(side=tk.LEFT)
        log_level_combo.bind('<<ComboboxSelected>>', lambda e: self.update_log_level())

        # Filter
        tk.Label(toolbar,
                 text="Filter:",
                 font=('Segoe UI', 9),
                 bg=self.colors['card_bg'],
                 fg=self.colors['text_secondary']).pack(side=tk.LEFT, padx=(20, 5))

        self.log_filter_var = tk.StringVar(value="ALL")
        log_filter_combo = ttk.Combobox(toolbar,
                                        textvariable=self.log_filter_var,
                                        values=['ALL', 'UDP', 'GIFCT', 'ERROR', 'SYSTEM'],
                                        state='readonly',
                                        width=10)
        log_filter_combo.pack(side=tk.LEFT)
        log_filter_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_logs())

        # Auto-scroll
        self.auto_scroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toolbar,
                       text="Auto-scroll",
                       font=('Segoe UI', 9),
                       variable=self.auto_scroll_var,
                       bg=self.colors['card_bg'],
                       fg=self.colors['text_secondary'],
                       activebackground=self.colors['card_bg'],
                       activeforeground=self.colors['text_secondary'],
                       selectcolor=self.colors['accent']).pack(side=tk.LEFT, padx=(20, 0))

        # Search
        tk.Label(toolbar,
                 text="Search:",
                 font=('Segoe UI', 9),
                 bg=self.colors['card_bg'],
                 fg=self.colors['text_secondary']).pack(side=tk.LEFT, padx=(20, 5))

        self.search_var = tk.StringVar()
        tk.Entry(toolbar,
                 textvariable=self.search_var,
                 font=('Segoe UI', 9),
                 bg=self.colors['bg_light'],
                 fg=self.colors['text'],
                 insertbackground=self.colors['text'],
                 width=15).pack(side=tk.LEFT)

        tk.Button(toolbar,
                  text="Find",
                  font=('Segoe UI', 9),
                  bg=self.colors['button_bg'],
                  fg=self.colors['button_fg'],
                  activebackground=self.colors['button_active'],
                  activeforeground=self.colors['button_fg'],
                  relief='flat',
                  padx=10,
                  pady=5,
                  command=self.search_logs).pack(side=tk.LEFT, padx=(5, 0))

        # Log text area
        self.log_text = scrolledtext.ScrolledText(frame,
                                                  wrap=tk.WORD,
                                                  font=('Consolas', 9),
                                                  bg=self.colors['bg_lighter'],
                                                  fg=self.colors['text'],
                                                  insertbackground=self.colors['text'],
                                                  relief='solid',
                                                  borderwidth=1)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Tags for different log types
        self.log_text.tag_config('INFO', foreground=self.colors['text_secondary'])
        self.log_text.tag_config('WARNING', foreground=self.colors['warning'])
        self.log_text.tag_config('ERROR', foreground=self.colors['error'])
        self.log_text.tag_config('DEBUG', foreground=self.colors['text_secondary'])
        self.log_text.tag_config('CRITICAL', foreground=self.colors['error'])
        self.log_text.tag_config('SUCCESS', foreground=self.colors['success'])
        self.log_text.tag_config('GIFCT', foreground=self.colors['info_light'])
        self.log_text.tag_config('UDP', foreground=self.colors['info'])
        self.log_text.tag_config('SYSTEM', foreground=self.colors['accent'])

    def create_players_section(self):
        """Create Players section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['players'] = frame

        tk.Label(frame,
                 text="Player Management",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

    def create_database_section(self):
        """Create Database section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['database'] = frame

        tk.Label(frame,
                 text="Database Management",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

    def create_tools_section(self):
        """Create Tools section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['tools'] = frame

        tk.Label(frame,
                 text="Tools",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

    def create_help_section(self):
        """Create Help section"""
        frame = tk.Frame(self.content_frame, bg=self.colors['bg'])
        self.sections['help'] = frame

        tk.Label(frame,
                 text="Help",
                 font=('Segoe UI', 20, 'bold'),
                 bg=self.colors['bg'],
                 fg=self.colors['text']).pack(anchor='w', pady=(0, 20))

    def create_bottom_bar(self, parent):
        """Create bottom bar"""
        bottom_bar = tk.Frame(parent,
                              bg=self.colors['bg_lighter'],
                              height=30)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)

        # System information
        sys_info = tk.Label(bottom_bar,
                            text=f"DPP2 UDP Server v2.1 | Python {platform.python_version()} | {platform.system()}",
                            font=('Segoe UI', 8),
                            bg=self.colors['bg_lighter'],
                            fg=self.colors['text_secondary'])
        sys_info.pack(side=tk.LEFT, padx=10, pady=5)

        # Time
        self.time_label = tk.Label(bottom_bar,
                                   font=('Segoe UI', 8),
                                   bg=self.colors['bg_lighter'],
                                   fg=self.colors['text_secondary'])
        self.time_label.pack(side=tk.RIGHT, padx=10, pady=5)

        self.update_time()

    def update_time(self):
        """Update time display"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)

    def show_section(self, section_name):
        """Show selected section"""
        # Hide all sections
        for section_frame in self.sections.values():
            section_frame.pack_forget()

        # Reset all button activity
        for btn in self.nav_buttons.values():
            btn.set_active(False)

        # Show selected section
        if section_name in self.sections:
            self.sections[section_name].pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Activate button
            if section_name in self.nav_buttons:
                self.nav_buttons[section_name].set_active(True)

            self.current_section = section_name

    def change_theme(self, theme_name):
        """Change application theme"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.colors = self.themes[theme_name]

            # Update theme preview selections
            for name, preview in self.theme_previews.items():
                preview.set_selected(name == theme_name)

            # Save theme to config
            self.config['theme'] = theme_name
            self.save_config()

            # Recreate interface
            for widget in self.content_frame.winfo_children():
                widget.destroy()

            for widget in self.sidebar_frame.winfo_children():
                widget.destroy()

            for widget in self.root.winfo_children():
                if isinstance(widget, tk.Frame) and widget != self.root:
                    widget.destroy()

            self.setup_styles()
            self.setup_ui()
            self.show_section(self.current_section)

            self.log_message(f"Theme changed to {self.colors['name']}", 'SYSTEM')

    def reset_appearance_settings(self):
        """Reset appearance settings"""
        self.change_theme('black')
        self.font_size_var.set("10")
        self.log_message("Appearance settings reset", 'SYSTEM')

    def save_server_settings(self):
        """Save server settings"""
        try:
            self.config['server']['server_name'] = self.server_settings_vars['server_name'].get()
            self.config['server']['port'] = int(self.server_settings_vars['udp_port'].get())
            self.config['server']['max_players'] = int(self.server_settings_vars['max_players'].get())
            self.config['server']['tick_rate'] = int(self.server_settings_vars['tick_rate'].get())
            self.config['server']['log_level'] = self.server_settings_vars['log_level'].get()

            self.save_config()
            self.log_message("Server settings saved", 'SUCCESS')

            self.stats_vars['udp_port'].set(str(self.config['server']['port']))

        except ValueError as e:
            self.log_message(f"Settings error: {e}", 'ERROR')
            messagebox.showerror("Error", f"Invalid values in settings:\n{str(e)}")
        except Exception as e:
            self.log_message(f"Save error: {e}", 'ERROR')
            messagebox.showerror("Error", f"Failed to save settings:\n{str(e)}")

    def save_gifct_settings(self):
        """Save Gifct settings"""
        try:
            self.config['gifct_settings']['gifct_enabled']['Gifct1'] = self.gifct1_enabled_var.get()
            self.config['gifct_settings']['gifct_enabled']['Gifct2'] = self.gifct2_enabled_var.get()
            self.config['gifct_settings']['gifct_configs']['Gifct1'] = self.gifct1_name_var.get()
            self.config['gifct_settings']['gifct_configs']['Gifct2'] = self.gifct2_name_var.get()

            self.save_config()
            self.update_gifct_status()
            self.log_message("Gifct settings saved", 'SUCCESS')

        except Exception as e:
            self.log_message(f"Gifct save error: {e}", 'ERROR')
            messagebox.showerror("Error", f"Failed to save Gifct settings:\n{str(e)}")

    def start_update_loop(self):
        self.update_ui()
        self.root.after(1000, self.start_update_loop)

    def update_ui(self):
        while not self.message_queue.empty():
            try:
                msg_type, msg = self.message_queue.get_nowait()
                self.add_log_message(msg, msg_type)
            except queue.Empty:
                break

        self.update_status_indicator()

        if self.server_running:
            self.update_stats()

    def update_status_indicator(self):
        self.status_indicator.delete("all")
        if self.server_running:
            color = self.colors['success']
            status_text = "● RUNNING"
        else:
            color = self.colors['error']
            status_text = "● STOPPED"

        self.status_indicator.create_oval(2, 2, 18, 18, fill=color, outline='white')
        self.status_label.config(text=status_text, fg=color)

    def add_log_message(self, message, msg_type='INFO'):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        filter_type = self.log_filter_var.get()
        if filter_type != 'ALL':
            if filter_type == 'UDP' and 'UDP' not in msg_type:
                return
            elif filter_type == 'GIFCT' and 'GIFCT' not in msg_type:
                return
            elif filter_type == 'ERROR' and 'ERROR' not in msg_type and 'CRITICAL' not in msg_type:
                return
            elif filter_type == 'SYSTEM' and 'UDP' in msg_type and 'GIFCT' in msg_type:
                return

        self.log_text.insert(tk.END, log_entry, msg_type)

        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)

        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 5000:
            self.log_text.delete('1.0', f'{lines - 5000}.0')

    def log_message(self, message, msg_type='INFO'):
        self.message_queue.put((msg_type, message))

    def update_gifct_status(self):
        enabled_gifct = []
        if self.gifct1_enabled_var.get():
            enabled_gifct.append("Gifct 1")
        if self.gifct2_enabled_var.get():
            enabled_gifct.append("Gifct 2")

        active_text = ", ".join(enabled_gifct) if enabled_gifct else "None active"
        self.stats_vars['active_gifct'].set(active_text)

        self.log_message(f"Gifct status updated: {active_text}", 'GIFCT')

    def reset_gifct_settings(self):
        self.gifct1_enabled_var.set(True)
        self.gifct2_enabled_var.set(True)
        self.gifct1_name_var.set("Primary Ability")
        self.gifct2_name_var.set("Secondary Ability")
        self.update_gifct_status()
        self.log_message("Gifct settings reset", 'INFO')

    def test_udp_connection(self):
        import socket
        import json

        try:
            port = int(self.server_settings_vars['udp_port'].get())

            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.settimeout(2.0)

            test_data = {'type': 'ping', 'timestamp': time.time()}

            if self.server_running:
                test_socket.sendto(json.dumps(test_data).encode(), ('127.0.0.1', port))
                self.log_message(f"Test UDP packet sent to port {port}", 'UDP')

                try:
                    data, addr = test_socket.recvfrom(1024)
                    response = json.loads(data.decode())
                    self.log_message(f"Server response: {response.get('type', 'unknown')}", 'SUCCESS')
                    messagebox.showinfo("Success", f"UDP server responding on port {port}")
                except socket.timeout:
                    self.log_message("Response timeout", 'WARNING')
                    messagebox.showwarning("Warning", f"Server not responding on port {port}")
            else:
                test_socket.bind(('127.0.0.1', 0))
                self.log_message(f"Port {port} available", 'UDP')
                messagebox.showinfo("Info", f"Port {port} is available")

            test_socket.close()

        except Exception as e:
            self.log_message(f"UDP test error: {e}", 'ERROR')
            messagebox.showerror("Error", f"Failed to test UDP:\n{str(e)}")

    def start_server(self):
        if not self.server_running:
            try:
                self.start_time = time.time()
                self.server_running = True
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self.restart_btn.config(state=tk.NORMAL)

                self.log_message("=" * 70, 'SYSTEM')
                self.log_message("🚀 STARTING DPP2 UDP SERVER", 'UDP')
                self.log_message("=" * 70, 'SYSTEM')
                self.log_message(f"🌐 Protocol: UDP", 'UDP')
                self.log_message(f"📍 Port: {self.config['server']['port']}", 'UDP')
                self.log_message(f"👥 Max Players: {self.config['server']['max_players']}", 'UDP')

                # Show active Gifct configurations
                gifct_configs = self.config.get('gifct_configurations', {})
                if gifct_configs:
                    enabled_gifct = [os.name for gid, gdata in gifct_configs.items()
                                     if gdata.get('enabled', True)]
                    if enabled_gifct:
                        self.log_message("🎮 Active Gifct Configurations:", 'GIFCT')
                        for gifct_id in enabled_gifct[:5]:  # Show first 5
                            gifct_data = gifct_configs[gifct_id]
                            self.log_message(f"  • {gifct_data.get('name', gifct_id)}", 'GIFCT')
                        if len(enabled_gifct) > 5:
                            self.log_message(f"  • ... and {len(enabled_gifct) - 5} more", 'GIFCT')

                self.log_message("✅ UDP server initialized", 'SUCCESS')

                self.server = self.server_core_class()
                self.server_thread = threading.Thread(target=self.run_server, daemon=True)
                self.server_thread.start()

                for i in range(10):
                    if hasattr(self.server, 'running') and self.server.running:
                        self.log_message("✅ UDP server started successfully", 'SUCCESS')
                        break
                    time.sleep(0.2)
                else:
                    self.log_message("❌ Failed to start server", 'ERROR')
                    self.stop_server()

            except Exception as e:
                self.log_message(f"❌ Startup error: {e}", 'ERROR')
                import traceback
                self.log_message(traceback.format_exc(), 'ERROR')
                self.stop_server()

    def run_server(self):
        try:
            if self.server and hasattr(self.server, 'start'):
                success = self.server.start()
                if success:
                    while self.server_running and hasattr(self.server, 'running') and self.server.running:
                        time.sleep(0.1)

                        if hasattr(self.server, 'get_server_info'):
                            server_info = self.server.get_server_info()
                            if server_info:
                                world_state = server_info.get('world', {})
                                self.stats['players_online'] = world_state.get('online_players', 0)
                                self.stats['total_characters'] = world_state.get('total_characters', 0)
                                self.stats['characters_online'] = self.stats['players_online']

                                network_stats = server_info.get('network_stats', {})
                                self.stats['udp_packets_received'] = network_stats.get('packets_received', 0)
                                self.stats['udp_packets_sent'] = network_stats.get('packets_sent', 0)
                                self.stats_vars['udp_packets_total'].set(
                                    str(self.stats['udp_packets_received'] + self.stats['udp_packets_sent'])
                                )

        except Exception as e:
            self.log_message(f"❌ Server thread error: {e}", 'ERROR')
        finally:
            self.server_running = False

    def stop_server(self):
        if self.server_running:
            self.log_message("🛑 Stopping server...", 'UDP')
            self.server_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.restart_btn.config(state=tk.DISABLED)

            if self.server and hasattr(self.server, 'stop'):
                try:
                    self.server.stop()
                except Exception as e:
                    self.log_message(f"Stop error: {e}", 'ERROR')

            self.log_message("✅ Server stopped", 'SUCCESS')

    def restart_server(self):
        self.log_message("🔄 Restarting server...", 'UDP')
        self.stop_server()
        self.root.after(1000, self.start_server)

    def update_stats(self):
        if self.server_running:
            if self.start_time:
                uptime = int(time.time() - self.start_time)
                hours = uptime // 3600
                minutes = (uptime % 3600) // 60
                seconds = uptime % 60
                self.stats_vars['uptime'].set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            self.stats_vars['cpu_usage'].set(f"{psutil.cpu_percent():.1f}%")

            memory = psutil.virtual_memory()
            used_mb = memory.used // (1024 * 1024)
            total_mb = memory.total // (1024 * 1024)
            self.stats_vars['memory_usage'].set(f"{used_mb}/{total_mb} MB")

            self.stats_vars['players_online'].set(str(self.stats['players_online']))
            self.stats_vars['total_characters'].set(str(self.stats['total_characters']))

            if hasattr(self.server, 'network') and hasattr(self.server.network, 'clients'):
                connections = len(self.server.network.clients)
                self.stats_vars['connections'].set(str(connections))

    def save_config(self):
        try:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)

            self.log_message("✅ Configuration saved", 'SUCCESS')
            return True

        except Exception as e:
            self.log_message(f"❌ Save error: {e}", 'ERROR')
            return False

    def update_log_level(self):
        self.config['server']['log_level'] = self.log_level_var.get()
        self.save_config()
        self.log_message(f"Log level: {self.log_level_var.get()}", 'SYSTEM')

    def filter_logs(self):
        self.clear_logs()
        self.log_message(f"Filter: {self.log_filter_var.get()}", 'SYSTEM')

    def clear_logs(self):
        self.log_text.delete('1.0', tk.END)
        self.log_message("Logs cleared", 'SYSTEM')

    def export_logs(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"udp_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get('1.0', tk.END))

                self.log_message(f"✅ Logs exported", 'SUCCESS')
                messagebox.showinfo("Success", f"Logs saved to:\n{filename}")

            except Exception as e:
                self.log_message(f"❌ Export error: {e}", 'ERROR')
                messagebox.showerror("Error", f"Export error:\n{str(e)}")

    def search_logs(self):
        search_term = self.search_var.get().lower()
        if not search_term:
            return

        self.log_text.tag_remove('highlight', '1.0', tk.END)

        start_pos = '1.0'
        found = False

        while True:
            start_pos = self.log_text.search(search_term, start_pos, stopindex=tk.END, nocase=True)
            if not start_pos:
                break

            end_pos = f"{start_pos}+{len(search_term)}c"
            self.log_text.tag_add('highlight', start_pos, end_pos)
            start_pos = end_pos
            found = True

        if found:
            self.log_text.tag_config('highlight', background=self.colors['warning'], foreground='white')
            self.log_message(f"Found: '{search_term}'", 'SYSTEM')
        else:
            self.log_message(f"Not found: '{search_term}'", 'SYSTEM')

    def on_closing(self):
        if self.server_running:
            if messagebox.askyesno("Confirm", "Server is running. Shut down?"):
                self.stop_server()
                time.sleep(1)
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """GUI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='DPP2 UDP Server GUI')
    parser.add_argument('--theme', help='Theme (black/grey/white/dark_blue)')
    parser.add_argument('--port', type=int, help='UDP server port')
    args = parser.parse_args()

    root = tk.Tk()

    from server_core import ServerCore

    app = ServerGUI(root, ServerCore)

    if args.theme and args.theme in ['black', 'grey', 'white', 'dark_blue']:
        app.change_theme(args.theme)

    if args.port:
        app.server_settings_vars['udp_port'].set(str(args.port))

    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()