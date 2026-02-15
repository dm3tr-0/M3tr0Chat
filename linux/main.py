#!/usr/bin/env python3
"""
M3TR0 Chat - Анонимный мессенджер через Tor
Главный файл для запуска GUI версии
"""

import sys
import os
import threading
from colorama import Fore, Style, init

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tor_manager import TorManager

init()

def print_banner():
    """баннер приложения"""
    banner = f"""
    {Fore.GREEN}╔════════════════════════════════════════════════╗
    ║          {Fore.CYAN}M3TR0 Chat v0.2.0{Fore.GREEN}                     ║
    ║       {Fore.MAGENTA}Анонимный мессенджер через Tor{Fore.GREEN}           ║
    ╚════════════════════════════════════════════════╝{Style.RESET_ALL}
    """
    print(banner)

def start_gui():
    """Запускает GUI версию"""
    try:
        # Импортируем здесь чтобы не мешать консольной версии
        from gui.app import start_gui_app
        start_gui_app()
    except ImportError as e:
        print(f"{Fore.RED}[!] Ошибка импорта GUI: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Установите зависимости: pip install flask flask-socketio{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}[!] Ошибка запуска GUI: {e}{Style.RESET_ALL}")
        return False

def start_console():
    """Запускает консольную версию"""
    try:
        from console import main as console_main
        console_main()
    except ImportError:
        print(f"{Fore.YELLOW}[*] Консольная версия недоступна{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[*] Запускается минимальная версия...{Style.RESET_ALL}")
        run_minimal_version()
    except Exception as e:
        print(f"{Fore.RED}[!] Ошибка: {e}{Style.RESET_ALL}")

def run_minimal_version():
    """Запускает минимальную версию (только Tor + сервер)"""
    print(f"{Fore.CYAN}[*] Запуск минимальной версии...{Style.RESET_ALL}")
    
    try:
        # Запускаем Tor
        tor_mgr = TorManager()
        if not tor_mgr.start_tor():
            return
        
        # Создаем onion сервис
        address = tor_mgr.create_onion_service()
        if not address:
            return
        
        print(f"\n{Fore.GREEN}[+] Система запущена!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[*] Ваш постоянный адрес: http://{address}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Нажмите Ctrl+C для выхода{Style.RESET_ALL}")
        
        # Ждем завершения
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}[*] Завершение работы...{Style.RESET_ALL}")
            
    except Exception as e:
        print(f"{Fore.RED}[!] Критическая ошибка: {e}{Style.RESET_ALL}")
    finally:
        if 'tor_mgr' in locals():
            tor_mgr.stop_tor()

def main():
    """Главная функция"""
    print_banner()
    
    print(f"{Fore.CYAN}Выберите режим запуска:{Style.RESET_ALL}")
    print(f"  1. {Fore.GREEN}GUI версия (рекомендуется){Style.RESET_ALL}")
    print(f"  2. {Fore.YELLOW}Консольная версия{Style.RESET_ALL}")
    print(f"  3. {Fore.MAGENTA}Только сервер (без GUI){Style.RESET_ALL}")
    print(f"  4. {Fore.RED}Выход{Style.RESET_ALL}")
    
    try:
        choice = input(f"\n{Fore.CYAN}> {Style.RESET_ALL}").strip()
        
        if choice == "1":
            print(f"{Fore.GREEN}[*] Запуск GUI версии...{Style.RESET_ALL}")
            start_gui()
        elif choice == "2":
            print(f"{Fore.YELLOW}[*] Запуск консольной версии...{Style.RESET_ALL}")
            start_console()
        elif choice == "3":
            print(f"{Fore.MAGENTA}[*] Запуск сервера...{Style.RESET_ALL}")
            run_minimal_version()
        elif choice == "4":
            print(f"{Fore.CYAN}[*] До свидания!{Style.RESET_ALL}")
            sys.exit(0)
        else:
            print(f"{Fore.RED}[!] Неверный выбор{Style.RESET_ALL}")
            main()
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[*] Завершение работы...{Style.RESET_ALL}")
        sys.exit(0)

if __name__ == "__main__":
    main()

