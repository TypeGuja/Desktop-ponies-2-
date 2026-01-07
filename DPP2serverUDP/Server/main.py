#!/usr/bin/env python3
"""
DPP2 UDP Server - Главный файл запуска UDP сервера
"""

import sys
import os
import signal
from colorama import init, Fore, Style

init(autoreset=True)


def main():
    """Главная функция запуска UDP сервера"""
    print(f"{Fore.CYAN}{'=' * 60}")
    print(f"{Fore.WHITE}DPP2 UDP Character Server")
    print(f"{Fore.CYAN}{'=' * 60}")

    try:
        from server_core import ServerCore

        print(f"{Fore.GREEN}Инициализация UDP сервера...")

        # Создаем сервер
        server = ServerCore()

        # Обработка сигнала завершения
        def signal_handler(sig, frame):
            print(f"\n{Fore.YELLOW}Получен сигнал завершения...")
            server.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Запускаем сервер
        if server.start():
            print(f"{Fore.GREEN}✅ UDP сервер запущен успешно!")
            print(f"{Fore.CYAN}Используйте GUI для управления или Ctrl+C для остановки")

            # Ждем завершения
            try:
                import time
                while server.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Остановка по запросу пользователя...")
                server.stop()

        else:
            print(f"{Fore.RED}❌ Не удалось запустить UDP сервер")
            return 1

    except Exception as e:
        print(f"{Fore.RED}❌ Ошибка запуска UDP сервера: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


def run_gui():
    """Запуск GUI для UDP сервера"""
    try:
        from gui_controller import main as gui_main
        print(f"{Fore.GREEN}Запуск GUI для UDP сервера...")
        gui_main()
    except ImportError as e:
        print(f"{Fore.RED}Не удалось импортировать GUI: {e}")
        print(f"{Fore.YELLOW}Запускаем консольную версию...")
        return main()
    except Exception as e:
        print(f"{Fore.RED}Ошибка запуска GUI: {e}")
        return main()


if __name__ == "__main__":
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1] == '--console':
        # Консольный режим
        sys.exit(main())
    else:
        # GUI режим по умолчанию
        sys.exit(run_gui()) #The Keeper - Bonobo