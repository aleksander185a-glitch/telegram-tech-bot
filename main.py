import os
import logging
import requests
from flask import Flask, request
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://telegram-tech-bot-oxzf.onrender.com')

# Проверка переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен")
    exit(1)
if not ADMIN_CHAT_ID:
    logger.error("❌ ADMIN_CHAT_ID не установлен")
    exit(1)

logger.info("✅ Переменные окружения загружены")
logger.info(f"BOT_TOKEN: {'установлен' if BOT_TOKEN else 'НЕТ'}")
logger.info(f"ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
logger.info(f"RENDER_EXTERNAL_URL: {RENDER_EXTERNAL_URL}")

app = Flask(__name__)

# Хранение временных данных
user_sessions = {}

def create_session_with_retries():
    """Создание сессии с повторными попытками"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = create_session_with_retries()
    
    def send_message(self, chat_id, text):
        """Отправка сообщения с логированием"""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        logger.info(f"📤 Отправка сообщения для {chat_id}: {text[:50]}...")
        
        try:
            response = self.session.post(url, json=data, timeout=10)
            result = response.json()
            logger.info(f"📨 Результат отправки: {result.get('ok', False)}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            return None
    
    def send_photo(self, chat_id, photo_url, caption=""):
        """Улучшенная отправка фото через загрузку файла"""
        url = f"{self.base_url}/sendPhoto"
        
        try:
            # Скачиваем фото
            logger.info(f"📥 Скачивание фото: {photo_url}")
            response = self.session.get(photo_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ Не удалось скачать фото: {response.status_code}")
                return None
            
            photo_data = response.content
            logger.info(f"✅ Фото скачано, размер: {len(photo_data)} bytes")
            
            # Отправляем фото как файл
            files = {'photo': ('photo.jpg', photo_data, 'image/jpeg')}
            data = {
                'chat_id': chat_id,
                'caption': caption
            }
            
            logger.info(f"📤 Отправка фото для {chat_id}")
            
            upload_response = self.session.post(url, files=files, data=data, timeout=30)
            result = upload_response.json()
            logger.info(f"🖼 Результат отправки фото: {result.get('ok', False)}")
            
            if not result.get('ok'):
                logger.error(f"❌ Ошибка отправки фото: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото: {e}")
            return None
    
    def send_document(self, chat_id, file_url, caption=""):
        """Отправка файла как документа"""
        url = f"{self.base_url}/sendDocument"
        
        try:
            # Скачиваем файл
            logger.info(f"📥 Скачивание документа: {file_url}")
            response = self.session.get(file_url, timeout=30)
            if response.status_code != 200:
                logger.error(f"❌ Не удалось скачать документ: {response.status_code}")
                return None
            
            file_data = response.content
            logger.info(f"✅ Документ скачан, размер: {len(file_data)} bytes")
            
            # Отправляем как документ
            files = {'document': ('photo.jpg', file_data, 'image/jpeg')}
            data = {
                'chat_id': chat_id,
                'caption': caption
            }
            
            logger.info(f"📤 Отправка документа для {chat_id}")
            
            upload_response = self.session.post(url, files=files, data=data, timeout=30)
            result = upload_response.json()
            logger.info(f"📎 Результат отправки документа: {result.get('ok', False)}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки документа: {e}")
            return None
    
    def get_file(self, file_id):
        """Получение файла с логированием"""
        url = f"{self.base_url}/getFile"
        data = {"file_id": file_id}
        logger.info(f"📥 Получение файла: {file_id}")
        
        try:
            response = self.session.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('ok'):
                file_path = result['result']['file_path']
                file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                logger.info(f"✅ Файл получен: {file_url}")
                return file_url
            else:
                logger.error(f"❌ Ошибка получения файла: {result}")
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения файла: {e}")
            return None

    def set_webhook(self, webhook_url):
        """Установка webhook"""
        url = f"{self.base_url}/setWebhook"
        data = {
            "url": webhook_url,
            "drop_pending_updates": True
        }
        
        logger.info(f"🌐 Установка webhook: {webhook_url}")
        
        try:
            response = self.session.post(url, json=data, timeout=10)
            result = response.json()
            logger.info(f"✅ Результат установки webhook: {result.get('ok', False)}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook: {e}")
            return None

    def get_webhook_info(self):
        """Получение информации о webhook"""
        url = f"{self.base_url}/getWebhookInfo"
        
        try:
            response = self.session.get(url, timeout=10)
            result = response.json()
            logger.info(f"📊 Информация о webhook: {result.get('ok', False)}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о webhook: {e}")
            return None

# Создаем экземпляр бота
bot = TelegramBot(BOT_TOKEN)

def send_to_admin(user_info, user_id):
    """Улучшенная отправка данных администратору"""
    admin_id = ADMIN_CHAT_ID
    
    message_text = f"""
🛒 НОВАЯ ЗАЯВКА НА ПОКУПКУ ТЕХНИКИ

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание неисправности: 
{user_info['description']}

Chat ID пользователя: {user_id}
    """
    
    try:
        # Получаем URL фото
        photo_url = bot.get_file(user_info['photo_file_id'])
        
        if not photo_url:
            logger.error("❌ Не удалось получить URL фото")
            bot.send_message(admin_id, message_text + "\n\n❌ Не удалось загрузить фото")
            return False
        
        logger.info("🔄 Пробуем отправить фото...")
        
        # Пробуем отправить как фото
        result_photo = bot.send_photo(admin_id, photo_url, message_text)
        
        if result_photo and result_photo.get('ok'):
            logger.info("✅ Фото успешно отправлено администратору")
            return True
        else:
            logger.warning("⚠️ Не удалось отправить фото, пробуем как документ...")
            
            # Пробуем отправить как документ
            result_doc = bot.send_document(admin_id, photo_url, message_text)
            
            if result_doc and result_doc.get('ok'):
                logger.info("✅ Фото отправлено как документ")
                return True
            else:
                logger.error("❌ Не удалось отправить фото даже как документ")
                # Отправляем только текст
                bot.send_message(admin_id, message_text + "\n\n❌ Не удалось отправить вложение")
                return False
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка отправки: {e}")
        # Всегда отправляем текст, даже если фото не отправилось
        bot.send_message(admin_id, message_text + f"\n\n❌ Ошибка отправки вложения: {e}")
        return False

def setup_webhook():
    """Автоматическая установка webhook при запуске"""
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    logger.info(f"🔄 Настройка webhook для: {webhook_url}")
    
    # Получаем текущую информацию о webhook
    webhook_info = bot.get_webhook_info()
    
    # Устанавливаем новый webhook
    result = bot.set_webhook(webhook_url)
    
    if result and result.get('ok'):
        logger.info("🎉 Webhook успешно установлен!")
        # Отправляем уведомление администратору
        bot.send_message(
            ADMIN_CHAT_ID, 
            f"🤖 Бот запущен и настроен!\n\n"
            f"🌐 Webhook: {webhook_url}\n"
            f"✅ Статус: Активен\n"
            f"📸 Отправка фото: Улучшенная"
        )
        return True
    else:
        logger.error("❌ Не удалось установить webhook")
        return False

@app.route('/')
def home():
    return """
🤖 Бот для покупки техники работает!

Доступные endpoints:
• / - эта страница
• /webhook - прием сообщений от Telegram
• /set_webhook - установка webhook
• /webhook_info - информация о webhook
• /test_admin - тест отправки сообщения
• /test_photo - тест отправки фото
• /health - проверка здоровья
"""

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка входящих сообщений от Telegram"""
    try:
        update = request.get_json()
        logger.info(f"📨 Получено обновление от Telegram")
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            logger.info(f"💬 Сообщение от {chat_id}: {text}")
            
            # Обработка команды /start
            if text == '/start':
                welcome_text = """
🛒 Покупка бытовой техники. 
🔄 Возможен Trade-in.

Присылайте фото и описание неисправности - администратор обязательно даст обратную связь!

📸 Отправьте фотографию техники:
                """
                bot.send_message(chat_id, welcome_text)
                user_sessions[chat_id] = {'state': 'waiting_photo'}
                logger.info(f"🔄 Пользователь {chat_id} переведен в состояние waiting_photo")
            
            # Обработка фото
            elif 'photo' in message and user_sessions.get(chat_id, {}).get('state') == 'waiting_photo':
                # Берем самое качественное фото (последнее в списке)
                photo = message['photo'][-1]
                file_id = photo['file_id']
                
                # Сохраняем file_id в сессии
                user_sessions[chat_id] = {
                    'state': 'waiting_description',
                    'photo_file_id': file_id,
                    'user_name': message['from'].get('first_name', 'Пользователь'),
                    'username': message['from'].get('username', 'не указан')
                }
                
                bot.send_message(chat_id, "✅ Фото получено! Теперь опишите неисправность техники:")
                logger.info(f"📸 Пользователь {chat_id} отправил фото, переведен в состояние waiting_description")
            
            # Обработка описания
            elif user_sessions.get(chat_id, {}).get('state') == 'waiting_description':
                user_data = user_sessions[chat_id]
                description = text
                
                logger.info(f"📝 Пользователь {chat_id} отправил описание: {description}")
                logger.info(f"📤 Отправка заявки администратору {ADMIN_CHAT_ID}")
                
                # Отправляем администратору
                send_to_admin(user_data, chat_id)
                
                # Подтверждаем пользователю
                bot.send_message(chat_id, "✅ Спасибо! Ваша заявка отправлена администратору! 🎉")
                
                # Очищаем сессию
                del user_sessions[chat_id]
                logger.info(f"✅ Сессия пользователя {chat_id} завершена")
            
            # Обработка команды /help
            elif text == '/help':
                help_text = """
🤖 Помощь по боту:

/start - оставить заявку на покупку техники
/help - показать справку

Как это работает:
1. Отправляете фото техники
2. Описываете неисправность
3. Администратор связывается с вами
                """
                bot.send_message(chat_id, help_text)
            
            # Любое другое сообщение
            elif text and not text.startswith('/'):
                if user_sessions.get(chat_id):
                    bot.send_message(chat_id, "❌ Сначала отправьте фото командой /start")
                else:
                    bot.send_message(chat_id, "🤖 Используйте /start чтобы оставить заявку на технику")
        
        return 'OK'
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return 'ERROR'

@app.route('/set_webhook', methods=['GET'])
def set_webhook_manual():
    """Ручная установка webhook"""
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    result = bot.set_webhook(webhook_url)
    return f"Webhook установлен вручную: {result}"

@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    """Информация о текущем webhook"""
    info = bot.get_webhook_info()
    return f"Информация о webhook: {info}"

@app.route('/test_admin', methods=['GET'])
def test_admin():
    """Тестовая отправка сообщения администратору"""
    test_message = "🧪 ТЕСТ: Бот работает корректно! Сообщение доставляется."
    result = bot.send_message(ADMIN_CHAT_ID, test_message)
    return f"Тест отправлен: {result}"

@app.route('/test_photo', methods=['GET'])
def test_photo():
    """Тест отправки фото администратору"""
    # Используем тестовое фото (можно заменить на любое доступное фото)
    test_photo_url = "https://via.placeholder.com/400x300/0088cc/ffffff?text=Test+Photo"
    test_caption = "🧪 ТЕСТОВОЕ ФОТО: Проверка отправки изображений"
    
    result = bot.send_photo(ADMIN_CHAT_ID, test_photo_url, test_caption)
    
    if result and result.get('ok'):
        return f"✅ Тестовое фото отправлено: {result}"
    else:
        # Пробуем отправить как документ
        result_doc = bot.send_document(ADMIN_CHAT_ID, test_photo_url, test_caption)
        return f"📎 Тестовое фото отправлено как документ: {result_doc}"

@app.route('/health')
def health():
    return "OK"

def main():
    logger.info("🤖 Бот запускается...")
    
    # Автоматическая установка webhook при запуске
    if setup_webhook():
        logger.info("✅ Бот успешно запущен и настроен!")
    else:
        logger.error("❌ Бот запущен с ошибками настройки webhook")
    
    # Запуск Flask приложения
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
