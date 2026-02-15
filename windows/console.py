#!/usr/bin/env python3
"""
M3TR0 Chat - Консольная версия
"""

import os
import sys
import threading
import time
from colorama import Fore, Style, init
from flask import Flask, request

# Добавляем путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tor_manager import TorManager

init()

class ConsoleChat:
    def __init__(self):
        self.app = Flask(__name__)
        self.tor_manager = None
        self.received_messages = []
        self.received_friends = []
        self.friends = []
        
        # Настраиваем Flask маршруты
        self.setup_routes()
        
    def setup_routes(self):
        """Настраивает Flask маршруты"""
        @self.app.route('/message', methods=['POST'])
        def receive_message():
            sender = 'anonymous'
            message = request.form.get('message', '')
            
            if message:
                temp = message.split('\n', 1)
                sender = str(temp[0])
                try:
                    message = str(temp[1])
                except Exception as ex:
                    message = ''
                self.received_messages.append((sender, message))
                print(f"\n{Fore.BLUE}Новое сообщение от {sender}: {Style.RESET_ALL}")
                print(f"{Fore.BLUE}{message}{Style.RESET_ALL}")
                print("\nВведите адрес получателя и сообщение (или 'exit' для выхода):")
            
            return "OK"
        
        @self.app.route('/friend', methods=['POST'])
        def get_friend_request():
            sender = 'anonymous'
            person = request.form.get('friend', '')
            
            if person:
                temp = person.split('\n', 1)
                sender = str(temp[0])
                try:
                    person = str(temp[1])
                except Exception as ex:
                    person = ''
                self.received_friends.append(sender)
                print(f"\n{Fore.BLUE}Новая заявка от {sender}{Style.RESET_ALL}")
                print("\nВведите адрес получателя и сообщение (или 'exit' для выхода):")
            
            return "OK"
    
    def run_flask_app(self):
        """Запускает Flask сервер"""
        print(f"{Fore.CYAN}[*] Запуск сервера на порту 5000...{Style.RESET_ALL}")
        self.app.run(port=5000, debug=False, use_reloader=False)
    
    def print_banner(self):
        """Печатает баннер"""
        banner = f"""
        {Fore.GREEN}╔════════════════════════════════════════════════╗
        ║          {Fore.CYAN}M3TR0 Chat - Консольная версия{Fore.GREEN}       ║
        ║       {Fore.MAGENTA}Анонимный мессенджер через Tor{Fore.GREEN}        ║
        ╚════════════════════════════════════════════════╝{Style.RESET_ALL}
        
        {Fore.YELLOW}Команды:{Style.RESET_ALL}
        /friends          - Показать список друзей
        /messages         - Показать последние сообщения
        /clear            - Очистить экран
        /help             - Показать справку
        /exit             - Выйти из программы
        """
        print(banner)
    
    def print_help(self):
        """Печатает справку"""
        help_text = f"""
        {Fore.CYAN}Использование:{Style.RESET_ALL}
        
        {Fore.GREEN}Отправка сообщения:{Style.RESET_ALL}
        onion123.onion Привет, как дела?
        onion456.onion Это тестовое сообщение
        
        {Fore.YELLOW}Друзья:{Style.RESET_ALL}
        /friends add onion123.onion  - Добавить друга
        /friends list               - Показать список друзей
        /friends remove onion123.onion - Удалить друга
        
        {Fore.MAGENTA}Система:{Style.RESET_ALL}
        /status           - Показать статус системы
        /config           - Показать конфигурацию
        /reconnect        - Переподключиться к Tor
        """
        print(help_text)
    
    def print_status(self):
        """Показывает статус системы"""
        if self.tor_manager and self.tor_manager.tor_process:
            tor_status = f"{Fore.GREEN}✓ Запущен (PID: {self.tor_manager.tor_process.pid}){Style.RESET_ALL}"
        else:
            tor_status = f"{Fore.RED}✗ Остановлен{Style.RESET_ALL}"
        
        status = f"""
        {Fore.CYAN}Статус системы:{Style.RESET_ALL}
        
        {Fore.YELLOW}Tor:{Style.RESET_ALL} {tor_status}
        {Fore.YELLOW}Onion адрес:{Style.RESET_ALL} {getattr(self.tor_manager, 'onion_address', 'Неизвестен')}
        {Fore.YELLOW}Получено сообщений:{Style.RESET_ALL} {len(self.received_messages)}
        {Fore.YELLOW}Заявок в друзья:{Style.RESET_ALL} {len(self.received_friends)}
        {Fore.YELLOW}Друзей в списке:{Style.RESET_ALL} {len(self.friends)}
        """
        print(status)
    
    def send_message(self, target_onion, message):
        """Отправляет сообщение на onion адрес"""
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # Очищаем адрес
            target_onion = target_onion.replace('http://', '').replace('https://', '')
            
            session = requests.Session()
            
            # Настройка повторных попыток
            retries = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504]
            )
            session.mount('http://', HTTPAdapter(max_retries=retries))
            
            # Прокси через Tor
            session.proxies = {
                'http': 'socks5h://localhost:9050',
                'https': 'socks5h://localhost:9050'
            }
            
            # Формируем URL и данные
            url = f'http://{target_onion}/message'
            sender_address = self.tor_manager.onion_address if self.tor_manager else 'unknown.onion'
            data = {'message': f'http://{sender_address}\n{message}'}
            
            # Отправляем запрос
            response = session.post(
                url,
                data=data,
                timeout=30,
                headers={'Connection': 'close'}
            )
            
            if response.status_code == 200:
                print(f"{Fore.GREEN}✓ Сообщение отправлено на {target_onion}{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}✗ Ошибка отправки: {response.status_code}{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}✗ Ошибка соединения: {e}{Style.RESET_ALL}")
            return False
    
    def handle_command(self, command):
        """Обрабатывает команды"""
        parts = command.split()
        cmd = parts[0].lower() if parts else ""
        
        if cmd == "/friends":
            if len(parts) > 1:
                subcmd = parts[1].lower()
                if subcmd == "add" and len(parts) > 2:
                    friend_addr = parts[2]
                    if friend_addr.endswith('.onion'):
                        self.friends.append(friend_addr)
                        print(f"{Fore.GREEN}✓ Друг добавлен: {friend_addr}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ Неверный onion адрес{Style.RESET_ALL}")
                elif subcmd == "list":
                    if self.friends:
                        print(f"{Fore.CYAN}Список друзей:{Style.RESET_ALL}")
                        for i, friend in enumerate(self.friends, 1):
                            print(f"  {i}. {friend}")
                    else:
                        print(f"{Fore.YELLOW}Список друзей пуст{Style.RESET_ALL}")
                elif subcmd == "remove" and len(parts) > 2:
                    friend_addr = parts[2]
                    if friend_addr in self.friends:
                        self.friends.remove(friend_addr)
                        print(f"{Fore.GREEN}✓ Друг удален: {friend_addr}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ Друг не найден{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Использование: /friends [add|list|remove] [адрес]{Style.RESET_ALL}")
        
        elif cmd == "/messages":
            if self.received_messages:
                print(f"{Fore.CYAN}Последние сообщения:{Style.RESET_ALL}")
                for i, (sender, msg) in enumerate(self.received_messages[-10:], 1):
                    print(f"{Fore.YELLOW}{i}. От: {sender}{Style.RESET_ALL}")
                    print(f"   {msg}\n")
            else:
                print(f"{Fore.YELLOW}Нет полученных сообщений{Style.RESET_ALL}")
        
        elif cmd == "/status":
            self.print_status()
        
        elif cmd == "/config":
            if self.tor_manager:
                print(f"{Fore.CYAN}Конфигурация:{Style.RESET_ALL}")
                for key, value in self.tor_manager.config.items():
                    print(f"  {key}: {value}")
        
        elif cmd == "/clear":
            os.system('cls' if os.name == 'nt' else 'clear')
        
        elif cmd == "/help":
            self.print_help()
        
        elif cmd == "/reconnect":
            print(f"{Fore.YELLOW}[*] Переподключение к Tor...{Style.RESET_ALL}")
            if self.tor_manager:
                self.tor_manager.stop_tor()
                time.sleep(2)
                self.tor_manager.start_tor()
                print(f"{Fore.GREEN}✓ Tor перезапущен{Style.RESET_ALL}")
        
        else:
            print(f"{Fore.RED}Неизвестная команда. Введите /help для справки.{Style.RESET_ALL}")
    
    def message_loop(self):
        """Основной цикл отправки сообщений"""
        self.print_banner()
        
        if self.tor_manager and self.tor_manager.onion_address:
            print(f"{Fore.GREEN}[+] Ваш адрес: http://{self.tor_manager.onion_address}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}Введите адрес получателя и сообщение:{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Или введите команду (начинается с /){Style.RESET_ALL}")
        print(f"{Fore.CYAN}Пример: onion123.onion Привет! Как дела?{Style.RESET_ALL}")
        
        while True:
            try:
                user_input = input(f"\n{Fore.GREEN}m3tr0> {Style.RESET_ALL}").strip()
                
                if not user_input:
                    continue
                
                # Обработка команд
                if user_input.lower() == 'exit' or user_input.lower() == '/exit':
                    print(f"{Fore.YELLOW}[*] Завершение работы...{Style.RESET_ALL}")
                    if self.tor_manager:
                        self.tor_manager.stop_tor()
                    sys.exit(0)
                
                # Если ввод начинается с /, это команда
                elif user_input.startswith('/'):
                    self.handle_command(user_input)
                    continue
                
                # Иначе это сообщение
                if ' ' not in user_input:
                    print(f"{Fore.RED}Формат: <адрес.onion> <сообщение>{Style.RESET_ALL}")
                    continue
                
                target_onion, *message_parts = user_input.split(' ', 1)
                message = message_parts[0] if message_parts else ""
                
                if not target_onion.endswith('.onion'):
                    print(f"{Fore.RED}Адрес должен заканчиваться на .onion{Style.RESET_ALL}")
                    continue
                
                # Отправляем сообщение
                self.send_message(target_onion, message)
                
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}[*] Завершение работы...{Style.RESET_ALL}")
                if self.tor_manager:
                    self.tor_manager.stop_tor()
                sys.exit(0)
            except Exception as e:
                print(f"{Fore.RED}Ошибка: {e}{Style.RESET_ALL}")
    
    def main(self):
        """Основная функция"""
        try:
            # Запускаем Tor
            print(f"{Fore.YELLOW}[*] Запуск Tor...{Style.RESET_ALL}")
            self.tor_manager = TorManager()
            if not self.tor_manager.start_tor():
                print(f"{Fore.RED}[!] Не удалось запустить Tor{Style.RESET_ALL}")
                return
            
            # Создаем onion сервис
            address = self.tor_manager.create_onion_service()
            if not address:
                print(f"{Fore.RED}[!] Не удалось создать onion адрес{Style.RESET_ALL}")
                return
            
            # Запускаем Flask в отдельном потоке
            flask_thread = threading.Thread(target=self.run_flask_app, daemon=True)
            flask_thread.start()
            
            # Даем серверу время на запуск
            time.sleep(2)
            
            # Запускаем основной цикл
            self.message_loop()
            
        except Exception as e:
            print(f"{Fore.RED}[-] Ошибка: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
        finally:
            if self.tor_manager:
                self.tor_manager.stop_tor()

def main():
    """Точка входа"""
    chat = ConsoleChat()
    chat.main()

if __name__ == "__main__":
    main()