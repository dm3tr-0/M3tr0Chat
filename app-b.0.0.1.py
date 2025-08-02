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

def get_tor_path():
    """Возвращает путь к tor.exe/tor в зависимости от ОС"""
    if sys.platform == "win32":
        return os.path.join(TOR_DIR, "tor.exe")
    else:
        return os.path.join(TOR_DIR, "tor")

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
            "snowflake 192.0.2.3:80 2B280B23E1107BB62ABFC40DDCC8824814F80A72 fingerprint=2B280B23E1107BB62ABFC40DDCC8824814F80A72 url=https://1098762253.rsc.cdn77.org/ fronts=www.cdn77.com,www.phpmyadmin.net ice=stun:stun.antisip.com:3478,stun:stun.epygi.com:3478,stun:stun.uls.co.za:3478,stun:stun.voipgate.com:3478,stun:stun.mixvoip.com:3478,stun:stun.nextcloud.com:3478,stun:stun.bethesda.net:3478,stun:stun.nextcloud.com:443 utls-imitate=hellorandomizedalpn",
            "snowflake 192.0.2.4:80 8838024498816A039FCBBAB14E6F40A0843051FA fingerprint=8838024498816A039FCBBAB14E6F40A0843051FA url=https://1098762253.rsc.cdn77.org/ fronts=www.cdn77.com,www.phpmyadmin.net ice=stun:stun.antisip.com:3478,stun:stun.epygi.com:3478,stun:stun.uls.co.za:3478,stun:stun.voipgate.com:3478,stun:stun.mixvoip.com:3478,stun:stun.nextcloud.com:3478,stun:stun.bethesda.net:3478,stun:stun.nextcloud.com:443 utls-imitate=hellorandomizedalpn",
            "obfs4 192.95.36.142:443 CDF2E852BF539B82BD10E27E9115A31734E378C2 cert=qUVQ0srL1JI/vO6V6m/24anYXiJD3QP2HgzUKQtQ7GRqqUvs7P+tG43RtAqdhLOALP7DJQ iat-mode=1",
            "obfs4 37.218.245.14:38224 D9A82D2F9C2F65A18407B1D2B764F130847F8B5D cert=bjRaMrr1BRiAW8IE9U5z27fQaYgOhX1UCmOpg2pFpoMvo6ZgQMzLsaTzzQNTlm7hNcb+Sg iat-mode=0",
            "obfs4 85.31.186.98:443 011F2599C0E9B27EE74B353155E244813763C3E5 cert=ayq0XzCwhpdysn5o0EyDUbmSOx3X/oTEbzDMvczHOdBJKlvIdHHLJGkZARtT4dcBFArPPg iat-mode=0",
            "obfs4 85.31.186.26:443 91A6354697E6B02A386312F68D82CF86824D3606 cert=PBwr+S8JTVZo6MPdHnkTwXJPILWADLqfMGoVvhZClMq/Urndyd42BwX9YFJHZnBB3H0XCw iat-mode=0",
            "obfs4 193.11.166.194:27015 2D82C2E354D531A68469ADF7F878FA6060C6BACA cert=4TLQPJrTSaDffMK7Nbao6LC7G9OW/NHkUwIdjLSS3KYf0Nv4/nQiiI8dY2TcsQx01NniOg iat-mode=0",
            "obfs4 193.11.166.194:27020 86AC7B8D430DAC4117E9F42C9EAED18133863AAF cert=0LDeJH4JzMDtkJJrFphJCiPqKx7loozKN7VNfuukMGfHO0Z8OGdzHVkhVAOfo1mUdv9cMg iat-mode=0",
            "obfs4 193.11.166.194:27025 1AE2C08904527FEA90C4C4F8C1083EA59FBC6FAF cert=ItvYZzW5tn6v3G4UnQa6Qz04Npro6e81AP70YujmK/KXwDFPTs3aHXcHp4n8Vt6w/bv8cA iat-mode=0",
            "obfs4 209.148.46.65:443 74FAD13168806246602538555B5521A0383A1875 cert=ssH+9rP8dG2NLDN2XuFw63hIO/9MNNinLmxQDpVa+7kTOa9/m+tGWT1SmSYpQ9uTBGa6Hw iat-mode=0",
            "obfs4 146.57.248.225:22 10A6CD36A537FCE513A322361547444B393989F0 cert=K1gDtDAIcUfeLqbstggjIw2rtgIKqdIhUlHp82XRqNSq/mtAjp1BIC9vHKJ2FAEpGssTPw iat-mode=0",
            "obfs4 45.145.95.6:27015 C5B7CD6946FF10C5B3E89691A7D3F2C122D2117C cert=TD7PbUO0/0k6xYHMPW3vJxICfkMZNdkRrb63Zhl5j9dW3iRGiCx0A7mPhe5T2EDzQ35+Zw iat-mode=0",
            "obfs4 51.222.13.177:80 5EDAC3B810E12B01F6FD8050D2FD3E277B289A08 cert=2uplIpLQ0q9+0qMFrK5pkaYRDOe460LL9WHBvatgkuRr/SL31wBOEupaMMJ6koRE6Ld0ew iat-mode=0",
            "meek_lite 192.0.2.20:80 url=https://1603026938.rsc.cdn77.org front=www.phpmyadmin.net utls=HelloRandomizedALPN"
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

    tor_process = launch_tor_with_config(
        config = get_tor_config(),
        tor_cmd=tor_path,  # Явный путь к Tor
        take_ownership=True,  # Убить процесс при выходе
        init_msg_handler=lambda line: print(f"{Fore.YELLOW}{str(line[line.index('%') - 2:line.index('%') + 1])}{Style.RESET_ALL}") if ("Bootstrapped" in line and "100" not in line) else None,
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
    sender = request.remote_addr
    message = request.form.get('message', '')
    
    if message:
        received_messages.append((sender, message))
        print(f"\n{Fore.BLUE}Новое сообщение{Style.RESET_ALL}")
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
            data={'message': str(onion_address)+ '\n' + str(message)},
            timeout=30,
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



def main():
    try:
        # Запускаем Tor
        tor_process = start_tor()
        print(f"{Fore.GREEN}[+] Вы вошли в сеть (PID: {tor_process.pid}){Style.RESET_ALL}")
        
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