#!/usr/bin/env python3
"""
DPP2 Main Client - Запуск графического клиента
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os
from datetime import datetime


def main():
    """Главная функция запуска"""
    print("=" * 50)
    print("DPP2 Графический Клиент - Camera Follow System")
    print("=" * 50)

    try:
        from graphic_client import DPP2GraphicClient
        app = DPP2GraphicClient()
        app.run()
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Ошибка", f"Не удалось запустить клиент:\n{e}")


if __name__ == "__main__":
    main()