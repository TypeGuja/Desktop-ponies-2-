#!/usr/bin/env python3
"""
DPP2 Main Client – запуск графического клиента.
"""

import sys


def _show_error(title: str, message: str) -> None:
    """Вывести сообщение об ошибке. Если tkinter недоступен – печатаем в консоль."""
    try:
        from tkinter import messagebox
        messagebox.showerror(title, message)
    except Exception:
        print(f"[{title}] {message}")


def main() -> None:
    """Инициализировать и запустить графический клиент."""
    print("=" * 50)
    print("DPP2 Графический Клиент – Camera Follow System")
    print("=" * 50)

    try:
        # Импортируем GUI‑модуль только после того, как проверили, что Python
        # запущен в окружении с поддержкой tkinter.
        from graphic_client import DPP2GraphicClient

        app = DPP2GraphicClient()
        app.run()
    except Exception as exc:  # pragma: no cover
        print(f"Ошибка запуска: {exc}")
        import traceback

        traceback.print_exc()
        _show_error(
            "Ошибка",
            f"Не удалось запустить клиент:\n{exc}",
        )


if __name__ == "__main__":
    main()