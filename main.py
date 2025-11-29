import os
import logging
import requests
from flask import Flask, request
import json
import traceback
import gc
import time
import signal
import sys
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

# ==================== ОБРАБОТЧИКИ СИГНАЛОВ ====================
def signal_handler(sig, frame):
    """Graceful shutdown при получении сигналов"""
    logger.info("🔄 Получен сигнал завершения, чистый выход...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://telegram-tech-bot-oxzf.onrender.com')

# Проверка обязательных переменных
if not BOT_TOKEN or not ADMIN_CHAT_ID:
    logger.error("❌ BOT_TOKEN или ADMIN_CHAT_ID не установлены")
    sys.exit(1)

logger.info("✅ Конфигурация загружена")

# ==================== ОПТИМИЗИРОВАННЫЕ СТРУКТУРЫ ДАННЫХ ====================
class SessionManager:
    """Менеджер сессий с автоматической очисткой"""
    
    def __init__(self, max_age_minutes=60):
        self.sessions = {}
        self.max_age = timedelta(minutes=max_age_minutes)
    
    def create_session(self, chat_id, photo_file_id, user_name, username):
        """Создание новой сессии с временной меткой"""
        self.sessions[chat_id] = {
            'state': 'waiting_description',
            'photo_file_id': photo_file_id,
            'user_name': user_name,
            'username': username,
            'created_at': datetime.now()
        }
        logger.info(f"🆕 Создана сессия для {chat_id}")
    
    def get_session(self, chat_id):
        """Получение сессии с проверкой срока годности"""
        session = self.sessions.get(chat_id)
        if session:
            if datetime.now() - session['created_at'] > self.max_age:
                del self.sessions[chat_id]
                logger.info(f"🧹 Сессия {chat_id} удалена по истечении времени")
                return None
        return session
    
    def delete_session(self, chat_id):
        """Удаление сессии"""
        if chat_id in self.sessions:
            del self.sessions[chat_id]
            logger.info(f"🗑️ Сессия {chat_id} удалена")
    
    def cleanup_expired(self):
        """Очистка просроченных сессий"""
        now = datetime.now()
        expired = []
        
        for chat_id, session in self.sessions.items():
            if now - session['created_at'] > self.max_age:
                expired.append(chat_id)
        
        for chat_id in expired:
            del self.sessions[chat_id]
        
        if expired:
            logger.info(f"🧹 Очищено {len(expired)} просроченных сессий")
        
        return len(expired)

# Инициализация менеджера сессий
session_manager = SessionManager(max_age_minutes=30)

# ==================== ОПТИМИЗИРОВАННЫЙ TELEGRAM БОТ ====================
class OptimizedTelegramBot:
    """Оптимизированная версия бота с управлением памятью"""
    
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        # Используем одну сессию для всех запросов
        self.session = requests.Session()
        # Настраиваем таймауты
        self.session.timeout = 30
    
    def _make_request(self, url, data=None, files=None):
        """Универсальный метод для запросов с обработкой ошибок"""
        try:
            if files:
                response = self.session.post(url, files=files, data=data, timeout=30)
            else:
                response = self.session.post(url, json=data, timeout=15)
            
            result = response.json()
            return result
        except requests.exceptions.Timeout:
            logger.error("⏰ Таймаут запроса к Telegram API")
            return {'ok': False, 'error': 'timeout'}
        except Exception as e:
            logger.error(f"❌ Ошибка запроса: {e}")
            return {'ok': False, 'error': str(e)}
    
    def send_message(self, chat_id, text):
        """Отправка сообщения с оптимизацией"""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        logger.info(f"📤 Отправка сообщения для {chat_id}")
        result = self._make_request(url, data)
        
        if result.get('ok'):
            logger.info("✅ Сообщение отправлено")
        else:
            logger.error(f"❌ Ошибка отправки: {result}")
        
        return result
    
    def send_photo(self, chat_id, photo_path, caption=""):
        """Отправка фото с контролем памяти"""
        url = f"{self.base_url}/sendPhoto"
        
        try:
            # Читаем файл чанками для экономии памяти
            file_size = os.path.getsize(photo_path)
            logger.info(f"🖼️ Отправка фото ({file_size} bytes) для {chat_id}")
            
            with open(photo_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {'chat_id': chat_id, 'caption': caption}
                
                result = self._make_request(url, data, files)
                
                if result.get('ok'):
                    logger.info("✅ Фото отправлено")
                else:
                    logger.error(f"❌ Ошибка отправки фото: {result}")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото: {e}")
            return {'ok': False, 'error': str(e)}
    
    def get_file_info(self, file_id):
        """Получение информации о файле"""
        url = f"{self.base_url}/getFile"
        data = {"file_id": file_id}
        
        logger.info(f"📁 Получение информации о файле {file_id}")
        return self._make_request(url, data)
    
    def download_file(self, file_path, local_path):
        """Скачивание файла с контролем памяти"""
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        
        try:
            logger.info(f"📥 Скачивание файла: {file_path}")
            
            # Скачиваем с прогрессом для больших файлов
            response = self.session.get(file_url, stream=True, timeout=30)
            
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(local_path)
                logger.info(f"✅ Файл скачан: {local_path} ({file_size} bytes)")
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
        data = {"url": webhook_url, "drop_pending_updates": True}
        
        logger.info(f"🌐 Установка webhook: {webhook_url}")
        return self._make_request(url, data)

# Инициализация бота
bot = OptimizedTelegramBot(BOT_TOKEN)

# ==================== ФУНКЦИИ ОПТИМИЗАЦИИ ПАМЯТИ ====================
def cleanup_memory():
    """Агрессивная очистка памяти"""
    before = gc.get_count()
    gc.collect()
    after = gc.get_count()
    logger.info(f"🧹 Очистка памяти: {before} -> {after}")
    return after[0] - before[0]  # Возвращаем количество собранных объектов

def safe_file_cleanup(file_path):
    """Безопасное удаление временных файлов"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"✅ Временный файл удален: {file_path}")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить {file_path}: {e}")
    return False

# ==================== ОСНОВНАЯ ЛОГИКА ====================
def send_to_admin_optimized(user_info, user_id):
    """Оптимизированная отправка данных администратору"""
    try:
        admin_id = ADMIN_CHAT_ID
        temp_file_path = None
        
        # Сначала отправляем текстовое уведомление
        # notification_text = f"🛒 НОВАЯ ЗАЯВКА от {user_info['user_name']}"
        bot.send_message(admin_id, notification_text)
        
        # Получаем информацию о файле
        file_info = bot.get_file_info(user_info['photo_file_id'])
        
        if not file_info.get('ok'):
            logger.error(f"❌ Ошибка получения файла: {file_info}")
            full_text = f"""
🛒 НОВАЯ ЗАЯВКА

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание неисправности: 
{user_info['description']}

❌ Фото недоступно
            """
            bot.send_message(admin_id, full_text)
            return False
        
        file_path = file_info['result']['file_path']
        temp_file_path = f"temp_photo_{user_id}_{int(time.time())}.jpg"
        
        # Скачиваем файл
        if not bot.download_file(file_path, temp_file_path):
            logger.error("❌ Не удалось скачать файл")
            full_text = f"""
🛒 НОВАЯ ЗАЯВКА

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание неисправности: 
{user_info['description']}

❌ Не удалось загрузить фото
            """
            bot.send_message(admin_id, full_text)
            return False
        
        # Отправляем фото с текстом
        full_text = f"""
🛒 НОВАЯ ЗАЯВКА

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание неисправности: 
{user_info['description']}
        """
        
        photo_result = bot.send_photo(admin_id, temp_file_path, full_text)
        
        # Независимо от результата, чистим временный файл
        safe_file_cleanup(temp_file_path)
        
        if photo_result.get('ok'):
            logger.info("✅ Заявка с фото отправлена администратору")
            return True
        else:
            logger.error(f"❌ Не удалось отправить фото: {photo_result}")
            # Отправляем только текст
            bot.send_message(admin_id, full_text + "\n\n❌ Не удалось отправить фото")
            return False
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в send_to_admin: {e}")
        logger.error(traceback.format_exc())
        
        # Всегда чистим временный файл при ошибках
        if temp_file_path:
            safe_file_cleanup(temp_file_path)
        
        # Пытаемся отправить хотя бы уведомление об ошибке
        try:
            error_text = f"❌ Ошибка обработки заявки от {user_info.get('user_name', 'unknown')}"
            bot.send_message(admin_id, error_text)
        except:
            pass
        
        return False
    finally:
        # Всегда чистим память после обработки
        cleanup_memory()

def setup_webhook():
    """Настройка webhook с проверкой"""
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    logger.info(f"🌐 Настройка webhook: {webhook_url}")
    
    result = bot.set_webhook(webhook_url)
    
    if result and result.get('ok'):
        logger.info("🎉 Webhook успешно установлен!")
        bot.send_message(ADMIN_CHAT_ID, "🤖 Бот запущен и оптимизирован! ✅")
        return True
    else:
        logger.error(f"❌ Ошибка установки webhook: {result}")
        return False

# ==================== FLASK APP ====================
app = Flask(__name__)

@app.route('/')
def home():
    return """
🤖 Бот для покупки техники (ОПТИМИЗИРОВАННЫЙ)

✅ Оптимизированная работа с памятью
✅ Автоматическая очистка сессий
✅ Контроль временных файлов

Endpoints:
• / - эта страница
• /webhook - прием сообщений от Telegram
• /status - диагностика системы
• /health - проверка здоровья
• /cleanup - принудительная очистка
"""

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик webhook с оптимизацией памяти"""
    try:
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            logger.info(f"💬 Сообщение от {chat_id}: {text[:100]}...")
            
            # Очищаем старые сессии при каждом запросе (редко, но эффективно)
            if len(session_manager.sessions) > 50:  # Если много сессий
                cleaned = session_manager.cleanup_expired()
                if cleaned > 0:
                    logger.info(f"🧹 Автоочистка: {cleaned} сессий")
            
            # Обработка команды /start
            if text == '/start':
                welcome_text = """
🛒 Покупка бытовой техники. 
🔄 Возможен Trade-in.

Присылайте фото бытовой техники и описание неисправности - администратор свяжется с вами!

📸 Отправьте фотографию:
                """
                bot.send_message(chat_id, welcome_text)
                # Не создаем сессию сразу, только после фото
                logger.info(f"🔄 Пользователь {chat_id} начал диалог")
            
            # Обработка фото
            elif 'photo' in message:
                # Проверяем, есть ли активная сессия ожидания фото
                if not session_manager.get_session(chat_id):
                    # Создаем сессию при получении фото
                    photo = message['photo'][-1]
                    file_id = photo['file_id']
                    user_name = message['from'].get('first_name', 'Пользователь')
                    username = message['from'].get('username', 'не указан')
                    
                    session_manager.create_session(chat_id, file_id, user_name, username)
                    bot.send_message(chat_id, "✅ Фото получено! Теперь опишите неисправность или укажите модель с шильдика:")
                    logger.info(f"📸 Пользователь {chat_id} отправил фото")
                else:
                    bot.send_message(chat_id, "❌ Завершите текущую заявку перед отправкой нового фото")
            
            # Обработка описания (только если есть активная сессия)
            elif text and not text.startswith('/'):
                user_session = session_manager.get_session(chat_id)
                if user_session and user_session['state'] == 'waiting_description':
                    logger.info(f"📝 Пользователь {chat_id} отправил описание")
                    
                    # Обновляем данные сессии
                    user_session['description'] = text
                    
                    # Отправляем администратору
                    logger.info(f"📤 Отправка заявки администратору {ADMIN_CHAT_ID}")
                    success = send_to_admin_optimized(user_session, chat_id)
                    
                    # Подтверждаем пользователю
                    if success:
                        bot.send_message(chat_id, "✅ Спасибо! Ваша заявка с фото отправлена администратору! 🎉")
                    else:
                        bot.send_message(chat_id, "✅ Заявка отправлена! Но возникли проблемы с отправкой фото.")
                    
                    # Очищаем сессию
                    session_manager.delete_session(chat_id)
                    
                else:
                    bot.send_message(chat_id, "🤖 Используйте /start чтобы оставить заявку на технику")
            
            # Обработка команды /help
            elif text == '/help':
                help_text = """
🤖 Помощь по боту:

/start - оставить заявку на покупку техники
/help - показать справку
/status - диагностика бота
                """
                bot.send_message(chat_id, help_text)
            
            # Обработка команды /status
            elif text == '/status':
                status_info = f"""
📊 Статус бота:

Активных сессий: {len(session_manager.sessions)}
Память: {cleanup_memory()} объектов собрано
Время работы: {int(time.time() - start_time)} сек.
                """
                bot.send_message(chat_id, status_info)
        
        return 'OK'
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        logger.error(traceback.format_exc())
        # Всегда чистим память при ошибках
        cleanup_memory()
        return 'ERROR'

@app.route('/status')
def status():
    """Диагностика системы"""
    import psutil
    process = psutil.Process()
    
    status_info = {
        "status": "running",
        "active_sessions": len(session_manager.sessions),
        "memory_usage_mb": f"{process.memory_info().rss / 1024 / 1024:.1f}",
        "memory_percent": f"{process.memory_percent():.1f}%",
        "cpu_percent": f"{process.cpu_percent():.1f}%",
        "uptime_seconds": int(time.time() - start_time),
        "cleaned_sessions": session_manager.cleanup_expired()
    }
    return status_info

@app.route('/health')
def health():
    """Health check для Render"""
    return "OK"

@app.route('/cleanup')
def cleanup():
    """Принудительная очистка"""
    cleaned_sessions = session_manager.cleanup_expired()
    cleaned_memory = cleanup_memory()
    
    return f"""
🧹 Принудительная очистка выполнена:

Удалено сессий: {cleaned_sessions}
Очищено объектов памяти: {cleaned_memory}
Активных сессий: {len(session_manager.sessions)}
    """

# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================
start_time = time.time()

def main():
    logger.info("🚀 Запуск оптимизированного бота...")
    
    # Начальная очистка памяти
    cleanup_memory()
    
    # Установка webhook
    setup_webhook()
    
    # Запуск Flask
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Запуск сервера на порту {port}")
    
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
