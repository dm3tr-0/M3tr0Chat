import os
import sys
import signal
import subprocess
import threading
from stem.control import Controller
from stem.process import launch_tor_with_config
from flask import Flask, request
from colorama import Fore, Style, init
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
# Инициализация colorama для цветного вывода
init()


# Конфигурация
TOR_DIR = os.path.abspath("./tor")  # Папка с Tor
TOR_DATA_DIR = os.path.abspath("./tor_data")  # Данные Tor
TOR_PORT = 9050
TOR_CTRL_PORT = 9051
LOCAL_PORT = 5000  # Порт для локального сервера
onion_address = None 
app = Flask(__name__)
received_messages = []
received_friends = []
friends = []

bridge_bin = ''

def get_tor_path():
    """Возвращает путь к tor.exe/tor в зависимости от ОС"""
    if sys.platform == "win32":
        bridge_bin = "lyrebird.exe"
        return os.path.join(TOR_DIR, "tor.exe")
    else:
        bridge_bin = "lyrebird"
        return os.path.join(TOR_DIR, "libTor.so")

def get_tor_config():
    """Возвращает конфиг с мостами"""
    return {
        "SocksPort": "9050",
        "ControlPort": "9051",
        "DataDirectory": TOR_DATA_DIR,
        "UseBridges": "1",
        #"ClientTransportPlugin": "obfs4 exec ./tor/obfs4proxy.exe",
        "ClientTransportPlugin": "snowflake,obfs4,meek_lite,obfs2,obfs3,scramblesuit,webtunnel exec ./tor/pluggable_transports/lyrebird.exe",
        "Bridge":[
            "obfs4 79.168.181.215:9443 ECE22C048DAE263C39BE32DCA7D7ECC26317A8AC cert=jo2QZLNtojsoUDr7tVnj4q4i/cTvNnD29kD7Sq2UwnZ5wyI0GGu2BhSjx8p+otsOM/u3Qw iat-mode=0",
            "obfs4 93.55.88.235:8081 13DDD2BED74D068AFF3EEE2B9D13C4E4D4667DDA cert=bez4elSLBpp58h6fml9ecJ/epgNWFFAE6YsXz41emzHE/YMCZaBsxPMtBcFA+JoxydDbag iat-mode=0"
            ],
        "ConnectionPadding": "1",
        "ReducedConnectionPadding": "0",
        "CircuitPadding": "1",
        "LearnCircuitBuildTimeout": "0",
        "NumEntryGuards": "4"
    }

def start_tor():
    """Запускает встроенный Tor"""
    if not os.path.exists(TOR_DATA_DIR):
        os.makedirs(TOR_DATA_DIR)

    tor_path = get_tor_path()
    if not os.path.exists(tor_path):
        raise FileNotFoundError(f"Tor не найден по пути: {tor_path}")
    
    def print_progress(line, percent = 1):
        if "Bootstrapped" in line:
            percent = int(line[line.index('%')-2:line.index('%')].replace('00', '100'))
        spinner = ['|', '/', '-', '\\', '|', '/', '-', '\\'][int(percent/10)%8]
            
        bar_length = 20
        filled = int(bar_length * percent / 100)
        bar = '▓' * filled + '░' * (bar_length - filled)
            
        sys.stdout.write(f"\r{Fore.YELLOW}{spinner} {bar} {line}{Style.RESET_ALL}")
        if percent != 100:
            sys.stdout.flush()
            
    tor_process = launch_tor_with_config(
        config = get_tor_config(),
        tor_cmd=tor_path,  # Явный путь к Tor
        take_ownership=True,  # Убить процесс при выходе
        init_msg_handler=lambda line: print_progress(line)
    )
    return tor_process

def create_onion_service(controller):
    """Создаёт временный .onion-адрес"""
    service = controller.create_ephemeral_hidden_service(
        ports={80: 5000},  # 80 (onion) → 5000 (локально)
        await_publication=True,
    )
    return service.service_id + ".onion"

def run_flask_app():
    """Запускает Flask сервер"""
    app.run(port=LOCAL_PORT)

@app.route('/message', methods=['POST'])
def receive_message():
    """Обрабатывает входящие сообщения"""
    sender = 'anonymous'
    message = request.form.get('message', '')
    
    if message:
        temp = message.split('\n', 1)
        sender = str(temp[0])
        try:
            message = str(temp[1])
        except Exception as ex:
            message = ''
        received_messages.append((sender, message))
        print(f"\n{Fore.BLUE}Новое сообщение от {sender} : {Style.RESET_ALL}")
        print(f"{Fore.BLUE}{message}{Style.RESET_ALL}")
        print("\nВведите адрес получателя и сообщение (или 'exit' для выхода):")
    
    return "OK"

def send_message(target_onion, message):
    """Отправляет сообщение на указанный .onion адрес"""
    try:
        # Очищаем адрес от возможных http://
        target_onion = target_onion.replace('http://', '').replace('https://', '')
        session = requests.Session()
        
        # Настройка повторных попыток
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('http://', HTTPAdapter(max_retries=retries))
        
        # Важно: используем socks5h (не socks5)
        session.proxies = {
            'http': 'socks5h://localhost:9050',
            'https': 'socks5h://localhost:9050'
        }
        
        # Формируем корректный URL
        url = f'http://{target_onion}/message'
        
        response = session.post(
            url,
            data={'message': str('http://' + str(onion_address))+ '\n' + str(message)},
            timeout=50,
            headers={'Connection': 'close'}
        )
        
        print(f"{Fore.GREEN}Сообщение отправлено на {target_onion}{Style.RESET_ALL}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Ошибка соединения: {e}{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"{Fore.RED}Критическая ошибка: {e}{Style.RESET_ALL}")
        return False
    
def message_loop():
    """Цикл для отправки сообщений"""
    while True:
        print("\nВведите адрес получателя и сообщение (или 'exit' для выхода):")
        user_input = input().strip()
        
        if user_input.lower() == 'exit':
            os._exit(0)
        
        if ' ' not in user_input:
            print("Формат: <адрес> <сообщение>")
            continue
            
        target_onion, *message_parts = user_input.split(' ', 1)
        message = message_parts[0] if message_parts else ""
        
        if not target_onion.endswith('.onion'):
            print("Адрес должен заканчиваться на .onion")
            continue
            
        send_message(target_onion, message)


@app.route('/friend', methods=['POST'])
def get_friend_request():
    """Обрабатывает входящие сообщения"""
    sender = 'anonymous'
    person = request.form.get('friend', '')
    
    if person:
        temp = person.split('\n', 1)
        sender = str(temp[0])
        try:
            person = str(temp[1])
        except Exception as ex:
            person = ''
        received_friends.append(sender)
        print(f"\n{Fore.BLUE}Новая заявка от {sender} : {Style.RESET_ALL}")
        print("\nВведите адрес получателя и сообщение (или 'exit' для выхода):")
    
    return "OK"

def send_friend_request(target_onion):
    pass


def main():
    try:
        # Запускаем Tor
        tor_process = start_tor()
        print(f"{Fore.GREEN}\n[+] Вы вошли в сеть (PID: {tor_process.pid}){Style.RESET_ALL}")
        print(f"{Fore.LIGHTMAGENTA_EX}[!] Дождитесь получения своего адреса...{Style.RESET_ALL}")
        # Запускаем Flask в отдельном потоке
        flask_thread = threading.Thread(target=run_flask_app, daemon=True)
        flask_thread.start()


        # Создаём onion-адрес
        #with Controller.from_port(port=TOR_CTRL_PORT) as controller:
        with Controller.from_port() as controller:
            controller.authenticate()
            global onion_address
            onion_address = create_onion_service(controller)
            print(f"{Fore.GREEN}[+] Ваш адрес: http://{onion_address}{Style.RESET_ALL}")

            
            # Запускаем цикл отправки сообщений
            message_loop()

    except Exception as e:
        print(f"{Fore.RED}[-] Ошибка: {e}{Style.RESET_ALL}")
    finally:
        print("[+] Завершение работы...")
if __name__ == "__main__":
    main()