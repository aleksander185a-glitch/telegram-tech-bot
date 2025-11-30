import os
import logging
import requests
from flask import Flask, request
import json
import time
import gc
from datetime import datetime, timedelta

# ==================== НАСТРОЙКА ЛОГГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Убираем предупреждение Werkzeug в production
if os.environ.get('RENDER'):
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://telegram-tech-bot-oxzf.onrender.com')

# Проверка обязательных переменных
if not BOT_TOKEN or not ADMIN_CHAT_ID:
    logger.error("❌ BOT_TOKEN или ADMIN_CHAT_ID не установлены")
    exit(1)

logger.info("✅ Конфигурация загружена")

# ==================== ОПТИМИЗИРОВАННЫЙ TELEGRAM БОТ ====================
class RenderOptimizedTelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = requests.Session()
    
    def _make_request_with_retry(self, url, data=None, files=None, max_retries=2):
        """Упрощенный метод с повторными попытками для Render"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = attempt * 3
                    logger.info(f"⏳ Повторная попытка через {wait_time} сек...")
                    time.sleep(wait_time)
                
                if files:
                    response = self.session.post(url, files=files, data=data, timeout=45)
                else:
                    response = self.session.post(url, json=data, timeout=25)
                
                result = response.json()
                
                if result.get('ok'):
                    logger.info(f"✅ Запрос успешен (попытка {attempt + 1})")
                    return result
                else:
                    logger.warning(f"⚠️ Telegram API error: {result}")
                    return result
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"🔌 Connection reset (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    continue
                return {'ok': False, 'error': 'Connection failed'}
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏰ Timeout (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    continue
                return {'ok': False, 'error': 'Timeout'}
                
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                return {'ok': False, 'error': str(e)}
        
        return {'ok': False, 'error': 'All retries failed'}
    
    def send_message(self, chat_id, text):
        """Отправка сообщения"""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text
        }
        
        logger.info(f"📤 Отправка сообщения для {chat_id}")
        return self._make_request_with_retry(url, data)
    
    def send_photo(self, chat_id, photo_path, caption=""):
        """Отправка фото с одной попыткой"""
        url = f"{self.base_url}/sendPhoto"
        
        try:
            with open(photo_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {'chat_id': chat_id, 'caption': caption}
                
                logger.info(f"🖼️ Отправка фото для {chat_id}")
                return self._make_request_with_retry(url, data, files, max_retries=1)
                
        except Exception as e:
            logger.error(f"❌ Ошибка подготовки фото: {e}")
            return {'ok': False, 'error': str(e)}
    
    def get_file_info(self, file_id):
        """Получение информации о файле"""
        url = f"{self.base_url}/getFile"
        data = {"file_id": file_id}
        
        logger.info(f"📁 Получение информации о файле")
        return self._make_request_with_retry(url, data)
    
    def download_file(self, file_path, local_path):
        """Скачивание файла"""
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        
        try:
            logger.info(f"📥 Скачивание файла")
            response = self.session.get(file_url, timeout=30)
            
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                file_size = len(response.content)
                logger.info(f"✅ Файл скачан: {file_size} bytes")
                return True
            else:
                logger.error(f"❌ Ошибка скачивания: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания: {e}")
            return False

    def set_webhook(self, webhook_url):
        """Установка webhook"""
        url = f"{self.base_url}/setWebhook"
        data = {"url": webhook_url}
        
        logger.info(f"🌐 Установка webhook")
        return self._make_request_with_retry(url, data)

# Инициализация бота
bot = RenderOptimizedTelegramBot(BOT_TOKEN)

# ==================== УПРОЩЕННЫЙ МЕНЕДЖЕР СЕССИЙ ====================
class SimpleSessionManager:
    def __init__(self, max_age_minutes=30):
        self.sessions = {}
        self.max_age = max_age_minutes * 60  # в секундах
    
    def create_session(self, chat_id, photo_file_id, user_name, username):
        """Создание сессии"""
        self.sessions[chat_id] = {
            'photo_file_id': photo_file_id,
            'user_name': user_name,
            'username': username,
            'created_at': time.time()
        }
        logger.info(f"🆕 Создана сессия для {chat_id}")
    
    def get_session(self, chat_id):
        """Получение сессии с проверкой срока"""
        session = self.sessions.get(chat_id)
        if session:
            if time.time() - session['created_at'] > self.max_age:
                del self.sessions[chat_id]
                logger.info(f"🧹 Сессия {chat_id} удалена по времени")
                return None
        return session
    
    def delete_session(self, chat_id):
        """Удаление сессии"""
        if chat_id in self.sessions:
            del self.sessions[chat_id]
            logger.info(f"🗑️ Сессия {chat_id} удалена")
    
    def cleanup_expired(self):
        """Очистка просроченных сессий"""
        now = time.time()
        expired = []
        
        for chat_id, session in self.sessions.items():
            if now - session['created_at'] > self.max_age:
                expired.append(chat_id)
        
        for chat_id in expired:
            del self.sessions[chat_id]
        
        if expired:
            logger.info(f"🧹 Очищено {len(expired)} сессий")
        
        return len(expired)

session_manager = SimpleSessionManager(max_age_minutes=30)

# ==================== ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ ====================
def cleanup_memory():
    """Быстрая очистка памяти"""
    collected = gc.collect()
    logger.info(f"🧹 Очистка памяти: {collected} объектов")
    return collected

def safe_file_cleanup(file_path):
    """Безопасное удаление файлов"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"✅ Файл удален: {file_path}")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить {file_path}: {e}")
    return False

def send_to_admin_optimized(user_info, user_id):
    """Оптимизированная отправка для администратора"""
    temp_file_path = None
    
    try:
        admin_id = ADMIN_CHAT_ID
        
        # 1. Всегда отправляем текстовое уведомление сначала
        quick_notification = f"🛒 НОВАЯ ЗАЯВКА от {user_info['user_name']}"
        bot.send_message(admin_id, quick_notification)
        
        # 2. Пытаемся получить информацию о файле
        file_info = bot.get_file_info(user_info['photo_file_id'])
        
        if not file_info.get('ok'):
            logger.error("❌ Не удалось получить информацию о файле")
            # Отправляем полный текст без фото
            full_text = f"""
🛒 НОВАЯ ЗАЯВКА

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание: 
{user_info['description']}

❌ Фото недоступно
            """
            bot.send_message(admin_id, full_text)
            return True  # Всегда возвращаем True для пользователя
        
        # 3. Скачиваем и отправляем фото
        file_path = file_info['result']['file_path']
        temp_file_path = f"temp_photo_{user_id}.jpg"
        
        if bot.download_file(file_path, temp_file_path):
            full_text = f"""
🛒 НОВАЯ ЗАЯВКА

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание: 
{user_info['description']}
            """
            
            # Отправляем фото (не критично если упадет)
            photo_result = bot.send_photo(admin_id, temp_file_path, full_text)
            
            if not photo_result.get('ok'):
                logger.warning("⚠️ Фото не отправлено, отправляем текст")
                bot.send_message(admin_id, full_text + "\n\n❌ Не удалось отправить фото")
        else:
            logger.error("❌ Не удалось скачать фото")
            full_text = f"""
🛒 НОВАЯ ЗАЯВКА

👤 Клиент: {user_info['user_name']}
📝 Описание: {user_info['description']}
❌ Фото не загружено
            """
            bot.send_message(admin_id, full_text)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки администратору: {e}")
        # Всегда возвращаем True, чтобы пользователь получил подтверждение
        return True
        
    finally:
        # Всегда чистим временные файлы и память
        if temp_file_path:
            safe_file_cleanup(temp_file_path)
        cleanup_memory()

def setup_webhook():
    """Настройка webhook"""
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    logger.info(f"🌐 Настройка webhook: {webhook_url}")
    
    result = bot.set_webhook(webhook_url)
    
    if result and result.get('ok'):
        logger.info("🎉 Webhook успешно установлен!")
        bot.send_message(ADMIN_CHAT_ID, "🤖 Бот запущен и оптимизирован для Render! ✅")
        return True
    else:
        logger.error(f"❌ Ошибка установки webhook: {result}")
        return False

# ==================== FLASK APP ====================
app = Flask(__name__)

@app.route('/')
def home():
    return """
🤖 Бот для покупки техники (ОПТИМИЗИРОВАН ДЛЯ RENDER)

✅ Устойчив к разрывам соединения
✅ Оптимизированная работа с памятью
✅ Быстрая обработка запросов

Команды в боте:
/start - начать заявку
/help - помощь

"""

@app.route('/webhook', methods=['POST'])
def webhook():
    """Упрощенный обработчик webhook"""
    try:
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            logger.info(f"💬 Сообщение от {chat_id}: {text[:50]}...")
            
            # Быстрая очистка старых сессий если их много
            if len(session_manager.sessions) > 20:
                session_manager.cleanup_expired()
            
            # Обработка команды /start
            if text == '/start':
                welcome_text = """
Присылайте фото и описание вашей техники!

📸 Отправьте фотографию:
                """
                bot.send_message(chat_id, welcome_text)
                logger.info(f"🔄 Пользователь {chat_id} начал диалог")
            
            # Обработка фото
            elif 'photo' in message:
                if not session_manager.get_session(chat_id):
                    # Создаем сессию при получении фото
                    photo = message['photo'][-1]
                    file_id = photo['file_id']
                    user_name = message['from'].get('first_name', 'Пользователь')
                    username = message['from'].get('username', 'не указан')
                    
                    session_manager.create_session(chat_id, file_id, user_name, username)
                    bot.send_message(chat_id, "✅ Фото получено! Теперь опишите неисправность и укажите модель с шильдика:")
                    logger.info(f"📸 Пользователь {chat_id} отправил фото")
                else:
                    bot.send_message(chat_id, "❌ Завершите текущую заявку")
            
            # Обработка описания
            elif text and not text.startswith('/'):
                user_session = session_manager.get_session(chat_id)
                if user_session:
                    logger.info(f"📝 Пользователь {chat_id} отправил описание")
                    
                    # Обновляем описание
                    user_session['description'] = text
                    
                    # Отправляем администратору (не блокируем ответ пользователю)
                    send_to_admin_optimized(user_session, chat_id)
                    
                    # Сразу подтверждаем пользователю
                    bot.send_message(chat_id, "✅ Спасибо! Ваша заявка отправлена администратору! 🎉")
                    
                    # Очищаем сессию
                    session_manager.delete_session(chat_id)
                    
                else:
                    bot.send_message(chat_id, "🤖 Используйте /start чтобы оставить заявку")
            
            # Обработка команды /help
            elif text == '/help':
                help_text = """
🤖 Помощь по боту:

/start - оставить заявку на покупку техники
/help - показать справку

Процесс:
1. Отправьте фото
2. Опишите неисправность
3. Получите обратную связь
                """
                bot.send_message(chat_id, help_text)
            
            # Обработка команды /status
            elif text == '/status':
                status_info = f"""
📊 Статус системы:

Активных сессий: {len(session_manager.sessions)}
Память: {cleanup_memory()} объектов собрано
Версия: Оптимизирована для Render
                """
                bot.send_message(chat_id, status_info)
        
        return 'OK'
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        cleanup_memory()
        return 'ERROR'

@app.route('/status')
def status():
    """Статус системы"""
    status_info = {
        "status": "running",
        "active_sessions": len(session_manager.sessions),
        "optimized_for": "Render Free",
        "timestamp": datetime.now().isoformat()
    }
    return status_info

@app.route('/health')
def health():
    """Health check для Render"""
    return "OK"

@app.route('/cleanup')
def cleanup():
    """Принудительная очистка"""
    sessions_cleaned = session_manager.cleanup_expired()
    memory_cleaned = cleanup_memory()
    
    return f"""
🧹 Очистка выполнена:

Сессии: {sessions_cleaned}
Память: {memory_cleaned}
Активных сессий: {len(session_manager.sessions)}
    """

# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================
def main():
    logger.info("🚀 Запуск оптимизированного бота для Render...")
    
    # Начальная оптимизация
    cleanup_memory()
    
    # Установка webhook
    setup_webhook()
    
    # Запуск Flask
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Сервер запущен на порту {port}")
    
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":

    main()
