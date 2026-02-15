"""
GUI версия M3TR0 Chat
"""

import os
import sys
import json
import threading
import time
import requests
from datetime import datetime
from flask_socketio import SocketIO, emit
from flask import Flask, render_template, jsonify, request, abort, make_response
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from colorama import Fore, Style, init
from functools import wraps

init(autoreset=True)

#путь для импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.tor_manager import TorManager


app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')
app.config['SECRET_KEY'] = 'm3tr0-chat-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Глобальные переменные
tor_manager = None
messages = []
chats = []
users_online = {}
my_onion_address = None
flask_ready = threading.Event()

PUBLIC_PATHS = ['/message']  # Только эти пути доступны извне

def is_local_request():
    """Проверяет, является ли запрос локальным"""
    
    # Проверяем Host заголовок - если это .onion, значит запрос извне
    host = request.host.split(':')[0]  # Убираем порт если есть
    if host.endswith('.onion'):
        return False
    
    # Проверяем на локальные IP
    if '127.0.0.1' in request.host:
        return True
    
    return False


def save_data():
    """Сохраняет данные"""
    try:
        os.makedirs('./data', exist_ok=True)
        data = {
            'chats': chats,
            'messages': messages,
            'timestamp': datetime.now().isoformat()
        }
        with open('./data/chat_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"{Fore.GREEN}[+] Данные сохранены{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[!] Ошибка сохранения: {e}{Style.RESET_ALL}")

def load_data():
    """Загружает данные"""
    global chats, messages
    try:
        if os.path.exists('./data/chat_data.json'):
            with open('./data/chat_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                chats = data.get('chats', [])
                messages = data.get('messages', [])
            print(f"{Fore.GREEN}[+] Данные загружены{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.YELLOW}[!] Ошибка загрузки: {e}{Style.RESET_ALL}")
        chats = []
        messages = []

def run_flask():
    """Запускает Flask"""
    print(f"{Fore.CYAN}[*] Запуск веб-сервера...{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[*] Веб-интерфейс: http://127.0.0.1:5001{Style.RESET_ALL}")
    
    load_data()
    flask_ready.set()
    
    socketio.run(
        app, 
        host='127.0.0.1', 
        port=5001, 
        debug=False, 
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )

@app.route('/')
def index():
    if is_local_request():
        """Главная страница"""
        return render_template('index.html')
    return render_template('messenger.html'), 403

@app.route('/api/status')
def get_status():
    """Статус системы"""
    return jsonify({
        'tor_running': tor_manager is not None and tor_manager.tor_process is not None,
        'onion_address': my_onion_address,
        'message_count': len(messages),
        'chat_count': len(chats),
        'users_online': len(users_online)
    })

@app.route('/message', methods=['POST'])
def receive_message():
    """Принимает входящие сообщения"""
    try:
        message_data = request.form.get('message', '')
        
        if message_data:
            # Парсим сообщение
            parts = message_data.split('\n', 1)
            sender = parts[0].strip() if len(parts) > 0 else ''
            message = parts[1].strip() if len(parts) > 1 else ''
            
            # Очищаем адрес
            sender = sender.replace('http://', '').replace('https://', '').strip()
            
            if not sender:
                sender = 'anonymous'
            
            print(f"{Fore.YELLOW}[*] Получено от {sender}: {message[:50]}{Style.RESET_ALL}")
            
            # Создаем сообщение
            incoming = {
                'id': f"incoming_{int(time.time())}_{len(messages)}",
                'sender': sender,
                'text': message,
                'timestamp': datetime.now().isoformat(),
                'isSent': False
            }
            
            messages.append(incoming)
            
            # Ищем или создаем чат
            chat = next((c for c in chats if c.get('address') == sender), None)
            
            if not chat and sender != 'anonymous':
                chat = {
                    'id': f"chat_{int(time.time())}",
                    'name': sender[:10] + '...',
                    'address': sender,
                    'lastMessage': message,
                    'lastMessageTime': incoming['timestamp'],
                    'unread': 1,
                    'messages': [incoming]
                }
                chats.append(chat)
                print(f"{Fore.GREEN}[+] Новый чат с {sender}{Style.RESET_ALL}")
            elif chat:
                if 'messages' not in chat:
                    chat['messages'] = []
                chat['messages'].append(incoming)
                chat['lastMessage'] = message
                chat['lastMessageTime'] = incoming['timestamp']
                chat['unread'] = chat.get('unread', 0) + 1
            
            if chat:
                incoming['chatId'] = chat['id']
                save_data()
                
                # Отправляем в UI
                socketio.emit('new_message', {
                    'id': incoming['id'],
                    'chatId': chat['id'],
                    'sender': sender,
                    'message': message,
                    'timestamp': incoming['timestamp'],
                    'isSent': False
                })
            
        return "OK", 200
        
    except Exception as e:
        print(f"{Fore.RED}[!] Ошибка: {e}{Style.RESET_ALL}")
        return "ERROR", 500

@socketio.on('connect')
def handle_connect():
    """Подключение клиента"""
    
    
    client_id = request.sid
    users_online[client_id] = {'connected_at': datetime.now().isoformat()}
    emit('chats_list', chats)
    print(f"{Fore.GREEN}[+] Клиент подключен: {client_id}{Style.RESET_ALL}")

@socketio.on('disconnect')
def handle_disconnect():
    """Отключение клиента"""
    client_id = request.sid
    if client_id in users_online:
        del users_online[client_id]
    print(f"{Fore.YELLOW}[-] Клиент отключен: {client_id}{Style.RESET_ALL}")

@socketio.on('request_tor_status')
def handle_tor_status():
    """Статус Tor"""
    if my_onion_address:
        emit('tor_status', {
            'status': 'connected',
            'address': my_onion_address
        })
    else:
        emit('tor_status', {'status': 'disconnected'})

@socketio.on('send_message')
def handle_send_message(data):
    """Отправка сообщения"""
    if not data:
        return
    
    message_id = data.get('messageId', f"msg_{int(time.time())}_{len(messages)}")
    target = data.get('to', '').replace('http://', '').replace('https://', '').strip()
    text = data.get('message', '')
    sender = my_onion_address or data.get('sender', '')
    chat_id = data.get('chatId')
    
    if not target or not text:
        print(f"{Fore.YELLOW}[!] Не указан адрес или сообщение{Style.RESET_ALL}")
        return
    
    print(f"{Fore.CYAN}[*] Отправка на {target}{Style.RESET_ALL}")
    
    # Создаем сообщение
    message = {
        'id': message_id,
        'chatId': chat_id,
        'sender': 'Вы',
        'text': text,
        'timestamp': data.get('timestamp', datetime.now().isoformat()),
        'isSent': True,
        'delivered': False
    }
    
    messages.append(message)
    
    # Обновляем чат
    chat = next((c for c in chats if c.get('id') == chat_id), None)
    if chat:
        if 'messages' not in chat:
            chat['messages'] = []
        chat['messages'].append(message)
        chat['lastMessage'] = text
        chat['lastMessageTime'] = message['timestamp']
    
    # Отправка
    delivered = False
    
    if target and tor_manager and tor_manager.tor_process:
        try:
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
            session.mount('http://', HTTPAdapter(max_retries=retries))
            session.proxies = {
                'http': 'socks5h://localhost:9050',
                'https': 'socks5h://localhost:9050'
            }
            
            # Формируем сообщение
            full_message = f"{sender}\n{text}"
            
            response = session.post(
                f'http://{target}/message',
                data={'message': full_message},
                timeout=50
            )
            
            if response.status_code == 200:
                delivered = True
                print(f"{Fore.GREEN}[+] Отправлено на {target}{Style.RESET_ALL}")
                
        except Exception as e:
            print(f"{Fore.RED}[!] Ошибка: {e}{Style.RESET_ALL}")
    
    message['delivered'] = delivered
    save_data()
    
    # Отправляем в UI
    socketio.emit('new_message', {
        'id': message_id,
        'chatId': chat_id,
        'sender': 'Вы',
        'message': text,
        'timestamp': message['timestamp'],
        'isSent': True,
        'delivered': delivered
    })
    
    if delivered:
        socketio.emit('message_delivered', {
            'messageId': message_id,
            'chatId': chat_id,
            'timestamp': datetime.now().isoformat()
        })

@socketio.on('new_chat')
def handle_new_chat(data):
    """Создание нового чата"""
    if not data:
        return
    
    address = data.get('address', '').replace('http://', '').replace('https://', '').strip()
    name = data.get('name', address[:10] + '...')
    
    if not address.endswith('.onion'):
        emit('chat_error', {'message': 'Адрес должен заканчиваться на .onion'})
        return
    
    if any(c.get('address') == address for c in chats):
        emit('chat_error', {'message': 'Чат уже существует'})
        return
    
    new_chat = {
        'id': f"chat_{int(time.time())}",
        'name': name,
        'address': address,
        'lastMessage': '',
        'lastMessageTime': datetime.now().isoformat(),
        'unread': 0,
        'messages': []
    }
    
    chats.append(new_chat)
    save_data()
    emit('chat_created', new_chat)
    emit('chats_list', chats)

@socketio.on('get_chat_messages')
def handle_get_chat_messages(data):
    """История сообщений чата"""
    if not data:
        return
    
    chat_id = data.get('chatId')
    chat = next((c for c in chats if c.get('id') == chat_id), None)
    if chat and 'messages' in chat:
        emit('chat_messages', {
            'chatId': chat_id,
            'messages': chat['messages']
        })



def start_gui_app():
    """Главная функция"""
    print(f"{Fore.GREEN}[*] Запуск M3TR0 Chat GUI{Style.RESET_ALL}")
    
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    
    if not flask_ready.wait(timeout=10):
        print(f"{Fore.RED}[!] Таймаут запуска Flask{Style.RESET_ALL}")
        return
    
    time.sleep(2)
    
    # Потом Tor
    global tor_manager, my_onion_address
    tor_manager = TorManager()
    
    if tor_manager.start_tor():
        time.sleep(5)
        my_onion_address = tor_manager.create_onion_service()
        
        if my_onion_address:
            print(f"{Fore.GREEN}[+] Ваш адрес: http://{my_onion_address}{Style.RESET_ALL}")
            socketio.emit('tor_status', {
                'status': 'connected',
                'address': my_onion_address
            })
    
    # Держим поток живым
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"{Fore.YELLOW}[*] Завершение...{Style.RESET_ALL}")
        if tor_manager:
            tor_manager.stop_tor()
        os._exit(0)

if __name__ == '__main__':
    start_gui_app()