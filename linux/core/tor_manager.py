import os
import sys
import json
import time
import stat
import socket
import signal
import subprocess
import requests
from pathlib import Path
from stem.control import Controller
from stem.process import launch_tor_with_config
from colorama import Fore, Style, init
init(autoreset=True)

class TorManager:
    def __init__(self, config_path="./config/tor_config.json"):
        self.config = self.load_config(config_path)
        self.tor_process = None
        self.onion_address = None
        self.controller = None
        self.TOR_DIR = os.path.abspath("./tor")
        self.TOR_DATA_DIR = os.path.abspath("./tor_data")
    
    def load_config(self, path):
        """Загружает конфигурацию"""
        if not os.path.exists(path):
            return {
                "socks_port": 9050,
                "control_port": 9051,
                "data_directory": "./tor_data",
                "use_bridges": True,
                "bridges": [
                    "obfs4 79.168.181.215:9443 ECE22C048DAE263C39BE32DCA7D7ECC26317A8AC cert=jo2QZLNtojsoUDr7tVnj4q4i/cTvNnD29kD7Sq2UwnZ5wyI0GGu2BhSjx8p+otsOM/u3Qw iat-mode=0",
                    "obfs4 93.55.88.235:8081 13DDD2BED74D068AFF3EEE2B9D13C4E4D4667DDA cert=bez4elSLBpp58h6fml9ecJ/epgNWFFAE6YsXz41emzHE/YMCZaBsxPMtBcFA+JoxydDbag iat-mode=0"
                ],
                "local_port": 5001
                
            }
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_tor_path(self):
        """Возвращает путь к tor.exe"""
        if sys.platform == "win32":
            return os.path.join(self.TOR_DIR, "tor.exe")
        else:
            return os.path.join(self.TOR_DIR, "tor")

    def get_tor_config(self):
        """Конфигурация Tor"""
        return {
            "SocksPort": "9050",
            "ControlPort": "9051",
            "DataDirectory": self.TOR_DATA_DIR,
            "UseBridges": "1",
            "ClientTransportPlugin": "snowflake,obfs4,meek_lite,obfs2,obfs3,scramblesuit,webtunnel exec ./tor/pluggable_transports/lyrebird",
            "Bridge": [
                "obfs4 79.168.181.215:9443 ECE22C048DAE263C39BE32DCA7D7ECC26317A8AC cert=jo2QZLNtojsoUDr7tVnj4q4i/cTvNnD29kD7Sq2UwnZ5wyI0GGu2BhSjx8p+otsOM/u3Qw iat-mode=0",
                "obfs4 93.55.88.235:8081 13DDD2BED74D068AFF3EEE2B9D13C4E4D4667DDA cert=bez4elSLBpp58h6fml9ecJ/epgNWFFAE6YsXz41emzHE/YMCZaBsxPMtBcFA+JoxydDbag iat-mode=0"
            ],
            "ConnectionPadding": "1",
            "ReducedConnectionPadding": "0",
            "CircuitPadding": "1",
            "LearnCircuitBuildTimeout": "0",
            "NumEntryGuards": "4"
        }

    def print_progress(self, line):
        """Прогресс-бар"""
        if "Bootstrapped " in line:
            try:
                percent = int(line[line.index('%')-2:line.index('%')].replace('00', '100'))
            except:
                percent = 0
            
            spinner = ['|', '/', '-', '\\'][int(percent/10)%4]
            bar_length = 20
            filled = int(bar_length * percent / 100)
            bar = '▓' * filled + '░' * (bar_length - filled)
            
            sys.stdout.write(f"\r{Fore.YELLOW}{spinner} {bar} {line}{Style.RESET_ALL}")
            if percent != 100:
                sys.stdout.flush()

    def start_tor(self):
        """Запускает Tor"""
        print(f"{Fore.YELLOW}[*] Запуск Tor...{Style.RESET_ALL}")
        
        if not os.path.exists(self.TOR_DATA_DIR):
            os.makedirs(self.TOR_DATA_DIR)
        
        tor_path = self.get_tor_path()
        if not os.path.exists(tor_path):
            raise FileNotFoundError(f"Tor не найден по пути: {tor_path}")
        if not os.access(tor_path, os.X_OK):
            try:
                os.chmod(tor_path, stat.S_IRWXU)
            except Exception as e:
                print(f"{Fore.RED}[!] Не удалсь установить права. Попробуйте в ручную: chmod +x {tor_path}{Style.RESET_ALL}")
        try:
            self.tor_process = launch_tor_with_config(
                config=self.get_tor_config(),
                tor_cmd=tor_path,
                take_ownership=True,
                init_msg_handler=lambda line: self.print_progress(line)
            )
            
            print(f"{Fore.GREEN}\n[+] Tor успешно запущен (PID: {self.tor_process.pid}){Style.RESET_ALL}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}[!] Ошибка запуска Tor: {e}{Style.RESET_ALL}")
            return False

    def create_onion_service(self):
        """Создаёт onion-адрес (с сохранением ключа)"""
        print(f"{Fore.LIGHTMAGENTA_EX}[!] Создание onion сервиса...{Style.RESET_ALL}")
        
        try:
            self.controller = Controller.from_port()
            self.controller.authenticate()
            
            # Путь для сохранения ключа
            key_file = os.path.abspath("./tor_data/private_key")
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            
            # Проверяем, есть ли сохраненный ключ
            if os.path.exists(key_file):
                print(f"{Fore.GREEN}[+] Загружаем сохраненный ключ...{Style.RESET_ALL}")
                with open(key_file, 'r') as f:
                    key_data = f.read().strip()
                
                # Парсим ключ
                if ':' in key_data:
                    key_type, key_content = key_data.split(':', 1)
                    
                    # Создаем сервис с существующим ключом
                    service = self.controller.create_ephemeral_hidden_service(
                        {80: 5001},
                        key_type=key_type,
                        key_content=key_content,
                        await_publication=True
                    )
                    self.onion_address = f"{service.service_id}.onion"
                    print(f"{Fore.GREEN}[+] Восстановлен адрес: http://{self.onion_address}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}[!] Неверный формат ключа, создаем новый{Style.RESET_ALL}")
                    service = self.controller.create_ephemeral_hidden_service(
                        {80: 5001},
                        await_publication=True
                    )
                    self.onion_address = f"{service.service_id}.onion"
                    
                    # Сохраняем ключ
                    with open(key_file, 'w') as f:
                        f.write(f"{service.private_key_type}:{service.private_key}")
                    print(f"{Fore.GREEN}[+] Новый адрес: http://{self.onion_address}{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}[+] Ключ сохранен в {key_file}{Style.RESET_ALL}")
            else:
                # Создаем новый сервис
                print(f"{Fore.GREEN}[+] Генерируем новый адрес...{Style.RESET_ALL}")
                service = self.controller.create_ephemeral_hidden_service(
                    {80: 5001},
                    await_publication=True
                )
                self.onion_address = f"{service.service_id}.onion"
                
                # Сохраняем ключ
                with open(key_file, 'w') as f:
                    f.write(f"{service.private_key_type}:{service.private_key}")
                print(f"{Fore.GREEN}[+] Ваш адрес: http://{self.onion_address}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}[+] Ключ сохранен в {key_file}{Style.RESET_ALL}")
            
            # Сохраняем адрес в отдельный файл для удобства
            addr_file = os.path.abspath("./tor_data/onion_address.txt")
            with open(addr_file, 'w') as f:
                f.write(self.onion_address)
            
            return self.onion_address
            
        except Exception as e:
            print(f"{Fore.RED}[!] Ошибка создания onion сервиса: {e}{Style.RESET_ALL}")
            return None

    def stop_tor(self):
        """Останавливает Tor"""
        if self.tor_process:
            print(f"{Fore.YELLOW}[*] Остановка Tor...{Style.RESET_ALL}")
            try:
                if self.controller:
                    self.controller.close()
                self.tor_process.terminate()
                self.tor_process.wait(timeout=10)
                print(f"{Fore.GREEN}[+] Tor остановлен{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[!] Ошибка при остановке Tor: {e}{Style.RESET_ALL}")
                try:
                    self.tor_process.kill()
                except:

                    pass
