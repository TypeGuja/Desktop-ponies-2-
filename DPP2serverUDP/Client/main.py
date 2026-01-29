#!/usr/bin/env python3
"""
DPP2 Main Client – запуск графического клиента.
"""

import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk


def main() -> None:
    """Инициализировать и запустить графический клиент."""
    print("=" * 50)
    print("DPP2 Графический Клиент – Camera Follow System")
    print("=" * 50)

    try:
        from graphic_client import DPP2GraphicClient

        app = DPP2GraphicClient()
        app.run()
    except Exception as exc:  # pragma: no cover
        print(f"Ошибка запуска: {exc}")
        import traceback

        traceback.print_exc()
        messagebox.showerror(
            "Ошибка",
            f"Не удалось запустить клиент:\n{exc}",
        )


if __name__ == "__main__":
    main()
