import os
import logging
import requests
from flask import Flask, request
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем переменные окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
WEBHOOK_URL = os.environ.get('RENDER_EXTERNAL_URL')  # Render автоматически устанавливает эту переменную

# Проверка переменных
if not BOT_TOKEN or not ADMIN_CHAT_ID:
    logger.error("❌ BOT_TOKEN или ADMIN_CHAT_ID не установлены")
    exit(1)

logger.info("✅ Переменные окружения загружены")

app = Flask(__name__)

# Хранение временных данных (в памяти)
user_sessions = {}

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, chat_id, text):
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return None
    
    def send_photo(self, chat_id, photo_url, caption=""):
        url = f"{self.base_url}/sendPhoto"
        data = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption
        }
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            return None
    
    def get_file(self, file_id):
        url = f"{self.base_url}/getFile"
        data = {"file_id": file_id}
        try:
            response = requests.post(url, json=data)
            result = response.json()
            if result.get('ok'):
                file_path = result['result']['file_path']
                return f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            return None
        except Exception as e:
            logger.error(f"Ошибка получения файла: {e}")
            return None

# Создаем экземпляр бота
bot = TelegramBot(BOT_TOKEN)

@app.route('/')
def home():
    return "🤖 Бот для покупки техники работает!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка входящих сообщений от Telegram"""
    try:
        update = request.get_json()
        
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
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
            
            # Обработка описания
            elif user_sessions.get(chat_id, {}).get('state') == 'waiting_description':
                user_data = user_sessions[chat_id]
                description = text
                
                # Получаем URL фото
                photo_url = bot.get_file(user_data['photo_file_id'])
                
                # Отправляем администратору
                admin_message = f"""
🛒 НОВАЯ ЗАЯВКА НА ПОКУПКУ ТЕХНИКИ

👤 Клиент: {user_data['user_name']}
📱 Username: @{user_data['username']}
📝 Описание неисправности: 
{description}
                """
                
                if photo_url:
                    bot.send_photo(ADMIN_CHAT_ID, photo_url, admin_message)
                else:
                    bot.send_message(ADMIN_CHAT_ID, admin_message + "\n\n❌ Не удалось загрузить фото")
                
                # Подтверждаем пользователю
                bot.send_message(chat_id, "✅ Спасибо! Ваша заявка отправлена администратору! 🎉")
                
                # Очищаем сессию
                del user_sessions[chat_id]
            
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
        logger.error(f"Ошибка обработки webhook: {e}")
        return 'ERROR'

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook (вызвать один раз после деплоя)"""
    if not WEBHOOK_URL:
        return "❌ WEBHOOK_URL не установлен"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    data = {
        "url": f"{WEBHOOK_URL}/webhook"
    }
    
    try:
        response = requests.post(url, json=data)
        result = response.json()
        return f"Webhook установлен: {result}"
    except Exception as e:
        return f"Ошибка установки webhook: {e}"

@app.route('/health')
def health():
    return "OK"

def main():
    logger.info("🤖 Бот запускается...")
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
    logger.info("✅ Бот запущен!")

if __name__ == "__main__":
    main()
