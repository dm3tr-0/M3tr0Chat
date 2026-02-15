// Подключение к WebSocket
const socket = io();

// Глобальные переменные
let currentChat = null;
let chats = [];
let myOnionAddress = '';

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    console.log('M3TR0 Chat инициализация...');
    
    // Загружаем сохраненные чаты из localStorage
    loadChatsFromStorage();
    
    // Настройка обработчиков
    setupEventListeners();
    setupSocketListeners();
    
    // Запрашиваем статус Tor
    socket.emit('request_tor_status');
});

function setupEventListeners() {
    // Отправка сообщения по Enter
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Закрытие модального окна при клике вне его
    window.addEventListener('click', function(event) {
        const modal = document.getElementById('newChatModal');
        if (event.target === modal) {
            closeNewChatModal();
        }
    });
}

function setupSocketListeners() {
    // Статус Tor
    socket.on('tor_status', function(data) {
        console.log('Tor статус:', data);
        const statusDot = document.getElementById('connection-status');
        const statusText = document.getElementById('status-text');
        const onionAddress = document.getElementById('my-onion-address');
        
        if (data.status === 'connected') {
            statusDot.className = 'status-dot connected';
            statusText.textContent = 'Tor подключен';
            if (data.address) {
                onionAddress.textContent = data.address;
                myOnionAddress = data.address;
            }
        } else {
            statusDot.className = 'status-dot disconnected';
            statusText.textContent = 'Tor отключен';
            onionAddress.textContent = 'Недоступно';
        }
    });

    // Получение списка чатов
    socket.on('chats_list', function(data) {
        console.log('Получен список чатов:', data);
        if (data && data.length > 0) {
            chats = data;
            updateChatsList();
            saveChatsToStorage();
        } else {
            chats = [];
            updateChatsList();
        }
    });

    // Новое сообщение
    socket.on('new_message', function(data) {
        console.log('Новое сообщение:', data);
        
        // Определяем отправителя
        const isSent = data.sender === 'Вы';
        const senderName = isSent ? 'Вы' : (data.sender || 'Неизвестно');
        
        // Ищем чат
        let chat;
        if (isSent) {
            // Исходящее - ищем по chatId
            chat = chats.find(c => c.id === data.chatId);
        } else {
            // Входящее - ищем по адресу отправителя
            chat = chats.find(c => c.address === data.sender);
            
            // Если чата нет, создаем автоматически
            if (!chat && data.sender && data.sender.includes('.onion')) {
                chat = {
                    id: data.chatId || 'chat_' + Date.now(),
                    name: data.sender.substring(0, 10) + '...',
                    address: data.sender,
                    lastMessage: data.message,
                    lastMessageTime: data.timestamp,
                    unread: 1,
                    messages: []
                };
                chats.push(chat);
            }
        }
        
        if (chat) {
            // Инициализируем массив сообщений если нужно
            if (!chat.messages) chat.messages = [];
            
            // Проверяем, нет ли уже такого сообщения
            const existingMsg = chat.messages.find(m => m.id === data.id);
            if (!existingMsg) {
                // Добавляем сообщение
                const message = {
                    id: data.id,
                    sender: senderName,
                    text: data.message,
                    timestamp: data.timestamp,
                    isSent: isSent,
                    delivered: data.delivered || false
                };
                chat.messages.push(message);
                
                // Обновляем последнее сообщение
                chat.lastMessage = data.message;
                chat.lastMessageTime = data.timestamp;
                
                // Если чат не открыт - увеличиваем счетчик
                if (!currentChat || currentChat.id !== chat.id) {
                    chat.unread = (chat.unread || 0) + 1;
                }
                
                saveChatsToStorage();
                updateChatsList();
                
                // Если чат открыт - показываем сообщение
                if (currentChat && currentChat.id === chat.id) {
                    addMessageToUI(
                        senderName,
                        data.message,
                        isSent,
                        data.timestamp,
                        data.id,
                        data.delivered
                    );
                }
            }
        }
    });

    // Подтверждение доставки
    socket.on('message_delivered', function(data) {
        console.log('Сообщение доставлено:', data);
        
        // Обновляем статус в UI
        const messageElement = document.querySelector(`[data-message-id="${data.messageId}"]`);
        if (messageElement) {
            const statusElement = messageElement.querySelector('.message-status');
            if (statusElement) {
                statusElement.innerHTML = '<i class="fas fa-check-double"></i> Доставлено';
                statusElement.style.color = '#00ff9d';
            }
        }
        
        // Обновляем статус в чате
        const chat = chats.find(c => c.id === data.chatId);
        if (chat && chat.messages) {
            const msg = chat.messages.find(m => m.id === data.messageId);
            if (msg) {
                msg.delivered = true;
                saveChatsToStorage();
            }
        }
    });

    // История сообщений для чата
    socket.on('chat_messages', function(data) {
        console.log('История сообщений:', data);
        const chat = chats.find(c => c.id === data.chatId);
        if (chat && data.messages) {
            chat.messages = data.messages;
            if (currentChat && currentChat.id === chat.id) {
                loadMessagesForChat(chat);
            }
        }
    });

    // Чат создан
    socket.on('chat_created', function(chat) {
        console.log('Чат создан:', chat);
        if (!chats.find(c => c.id === chat.id)) {
            chats.push(chat);
            updateChatsList();
            saveChatsToStorage();
            switchChat(chat.id);
            showNotification('Чат создан!', 'success');
        }
    });

    // Ошибка чата
    socket.on('chat_error', function(data) {
        showNotification(data.message, 'error');
    });

    // Ошибки системы
    socket.on('system_error', function(data) {
        showNotification(data.message, 'error');
    });
}

// Функции для работы с чатами
window.showNewChatModal = function() {
    document.getElementById('newChatModal').style.display = 'flex';
};

window.closeNewChatModal = function() {
    document.getElementById('newChatModal').style.display = 'none';
    document.getElementById('new-chat-address').value = '';
    document.getElementById('new-chat-name').value = '';
};

window.createNewChat = function() {
    const address = document.getElementById('new-chat-address').value.trim();
    let name = document.getElementById('new-chat-name').value.trim();
    
    if (!address.endsWith('.onion')) {
        showNotification('Адрес должен заканчиваться на .onion', 'error');
        return;
    }
    
    if (!name) {
        name = address.substring(0, 10) + '...';
    }
    
    // Отправляем на сервер через Socket.IO
    socket.emit('new_chat', {
        address: address,
        name: name
    });
    
    closeNewChatModal();
};

function addChatToList(chat) {
    const container = document.getElementById('chats-container');
    
    // Убираем заглушку "нет чатов"
    const emptyChats = container.querySelector('.empty-chats');
    if (emptyChats) emptyChats.remove();
    
    // Проверяем, не добавлен ли уже этот чат
    if (document.querySelector(`[data-chat-id="${chat.id}"]`)) return;
    
    const chatElement = document.createElement('div');
    chatElement.className = 'chat-item';
    chatElement.dataset.chatId = chat.id;
    chatElement.onclick = () => switchChat(chat.id);
    
    chatElement.innerHTML = `
        <div class="chat-avatar">
            <i class="fas fa-user"></i>
        </div>
        <div class="chat-info">
            <h4>${escapeHtml(chat.name)}</h4>
            <p class="last-message">${escapeHtml(chat.lastMessage || 'Нет сообщений')}</p>
        </div>
        <div class="chat-meta">
            <div class="chat-time">${formatTime(chat.lastMessageTime)}</div>
            ${chat.unread ? `<div class="unread-badge">${chat.unread}</div>` : ''}
        </div>
    `;
    
    container.appendChild(chatElement);
    updateChatsCount();
}

window.switchChat = function(chatId) {
    const chat = chats.find(c => c.id === chatId);
    if (!chat) return;
    
    currentChat = chat;
    
    // Показываем область чата
    document.getElementById('chat-header').style.display = 'flex';
    document.getElementById('messages-container').style.display = 'flex';
    document.getElementById('message-input-area').style.display = 'block';
    document.getElementById('no-chat-selected').style.display = 'none';
    
    // Обновляем заголовок
    document.getElementById('current-chat-name').textContent = chat.name;
    document.getElementById('chat-status').textContent = chat.address;
    
    // Загружаем сообщения
    loadMessagesForChat(chat);
    
    // Обновляем активный чат в списке
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeChat = document.querySelector(`[data-chat-id="${chatId}"]`);
    if (activeChat) activeChat.classList.add('active');
    
    // Сбрасываем счетчик непрочитанных
    chat.unread = 0;
    updateChatsList();
    
    // Запрашиваем историю сообщений с сервера
    socket.emit('get_chat_messages', { chatId: chat.id });
};

window.backToChats = function() {
    document.getElementById('chat-header').style.display = 'none';
    document.getElementById('messages-container').style.display = 'none';
    document.getElementById('message-input-area').style.display = 'none';
    document.getElementById('no-chat-selected').style.display = 'flex';
    currentChat = null;
};

// Функции для работы с сообщениями
window.sendMessage = function() {
    if (!currentChat) {
        showNotification('Выберите чат', 'error');
        return;
    }
    
    const input = document.getElementById('message-input');
    const text = input.value.trim();
    
    if (!text) return;
    
    const messageId = 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
    const timestamp = new Date().toISOString();
    
    // Отправляем на сервер
    socket.emit('send_message', {
        messageId: messageId,
        chatId: currentChat.id,
        to: currentChat.address,
        message: text,
        sender: myOnionAddress,
        timestamp: timestamp
    });
    
    // Очищаем поле ввода
    input.value = '';
    input.focus();
};

function addMessageToUI(sender, text, isSent, timestamp, messageId, delivered = false) {
    const container = document.getElementById('messages-container');
    
    // Убираем заглушку "нет сообщений"
    const emptyMessage = document.getElementById('chat-empty');
    if (emptyMessage) emptyMessage.style.display = 'none';
    
    // Проверяем, нет ли уже такого сообщения
    if (messageId && document.querySelector(`[data-message-id="${messageId}"]`)) {
        return;
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
    if (messageId) messageDiv.dataset.messageId = messageId;
    
    const time = new Date(timestamp);
    const timeString = time.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    
    let statusHtml = '';
    if (isSent) {
        if (delivered) {
            statusHtml = '<span class="message-status"><i class="fas fa-check-double"></i> Доставлено</span>';
        } else {
            statusHtml = '<span class="message-status"><i class="fas fa-check"></i> Отправлено</span>';
        }
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-text">${escapeHtml(text)}</div>
            <div class="message-footer">
                <span class="message-time">${timeString}</span>
                ${statusHtml}
            </div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

function loadMessagesForChat(chat) {
    const container = document.getElementById('messages-container');
    container.innerHTML = '';
    
    // Показываем заглушку если нет сообщений
    const emptyMessage = document.getElementById('chat-empty');
    
    if (chat.messages && chat.messages.length > 0) {
        if (emptyMessage) emptyMessage.style.display = 'none';
        
        // Сортируем сообщения по времени
        const sortedMessages = [...chat.messages].sort((a, b) => 
            new Date(a.timestamp) - new Date(b.timestamp)
        );
        
        sortedMessages.forEach(msg => {
            addMessageToUI(
                msg.sender,
                msg.text,
                msg.isSent,
                msg.timestamp,
                msg.id,
                msg.delivered
            );
        });
    } else {
        if (emptyMessage) {
            emptyMessage.style.display = 'block';
            container.appendChild(emptyMessage);
        }
    }
}

// Утилиты
window.copyOnionAddress = function() {
    const address = document.getElementById('my-onion-address').textContent;
    if (address && address !== 'Недоступно' && address !== 'Загрузка...') {
        navigator.clipboard.writeText(address).then(() => {
            showNotification('Адрес скопирован!', 'success');
        });
    }
};

function showNotification(message, type = 'info') {
    // Удаляем старые уведомления
    const oldNotifications = document.querySelectorAll('.notification');
    oldNotifications.forEach(n => n.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'error') icon = 'exclamation-circle';
    
    notification.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function formatTime(timestamp) {
    if (!timestamp) return '';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60 * 1000) return 'только что';
    if (diff < 60 * 60 * 1000) return Math.floor(diff / (60 * 1000)) + ' мин';
    if (diff < 24 * 60 * 60 * 1000) {
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Работа с localStorage
function saveChatsToStorage() {
    try {
        localStorage.setItem('m3tr0_chats', JSON.stringify(chats));
        console.log('Чаты сохранены в localStorage');
    } catch (e) {
        console.error('Ошибка сохранения в localStorage:', e);
    }
}

function loadChatsFromStorage() {
    const saved = localStorage.getItem('m3tr0_chats');
    if (saved) {
        try {
            chats = JSON.parse(saved);
            console.log('Загружено чатов из localStorage:', chats.length);
            updateChatsList();
        } catch (e) {
            console.error('Ошибка загрузки чатов:', e);
            chats = [];
        }
    } else {
        chats = [];
    }
}

function updateChatsList() {
    const container = document.getElementById('chats-container');
    container.innerHTML = '';
    
    if (chats.length === 0) {
        container.innerHTML = `
            <div class="empty-chats">
                <i class="fas fa-comments"></i>
                <p>Нет чатов</p>
                <p>Нажмите "+ Новый чат" чтобы начать</p>
            </div>
        `;
    } else {
        chats.forEach(chat => addChatToList(chat));
    }
    
    updateChatsCount();
}

function updateChatsCount() {
    document.getElementById('chats-count').textContent = chats.length;
}

// Обработка клавиш
window.handleKeyPress = function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
};

// Добавляем стили для анимации
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

console.log('M3TR0 Chat готов!');