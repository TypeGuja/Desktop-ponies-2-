#!/usr/bin/env python3
"""
DPP2 Server - Главный файл сервера с системой персонажей
"""

import sys
import os
import signal
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    print(f"\nПолучен сигнал {signum}. Останавливаем сервер...")
    if 'server' in globals():
        server.stop()
    sys.exit(0)


def run_cli():
    """Запуск в режиме командной строки"""
    from server_core import ServerCore

    print("""
    ╔══════════════════════════════════════╗
    ║   DPP2 Game Server v2.0 (Character) ║
    ║      Сервер с системой персонажей    ║
    ╚══════════════════════════════════════╝
    """)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        global server
        server = ServerCore()

        if not server.start():
            print("Не удалось запустить сервер")
            return 1

        print("\nСервер работает. Для остановки нажмите Ctrl+C\n")

        while server.running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nПолучен запрос на остановку...")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if 'server' in globals():
            server.stop()

    print("\nСервер завершил работу")
    return 0


def run_gui():
    """Запуск графического интерфейса"""
    try:
        from gui_controller import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"Ошибка импорта GUI модуля: {e}")
        print("Убедитесь, что установлены все зависимости:")
        print("pip install psutil")
        return 1
    except Exception as e:
        print(f"Ошибка запуска GUI: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='DPP2 Game Server')
    parser.add_argument('--gui', action='store_true', help='Запуск с графическим интерфейсом')
    parser.add_argument('--cli', action='store_true', help='Запуск в режиме командной строки')

    args = parser.parse_args()

    if not args.gui and not args.cli:
        print("Выберите режим запуска:")
        print("1. Графический интерфейс (GUI)")
        print("2. Командная строка (CLI)")
        print("3. Выход")

        choice = input("\nВведите номер (1-3): ").strip()

        if choice == '1':
            return run_gui()
        elif choice == '2':
            return run_cli()
        elif choice == '3':
            print("Выход...")
            return 0
        else:
            print("Неверный выбор. Запуск в режиме командной строки...")
            return run_cli()
    elif args.gui:
        return run_gui()
    else:
        return run_cli()


if __name__ == "__main__":
    sys.exit(main())