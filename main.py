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

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, chat_id, text):
        """Отправка сообщения"""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        logger.info(f"📤 Отправка сообщения для {chat_id}")
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            logger.info(f"📨 Результат: {result.get('ok', False)}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return None
    
    def send_photo(self, chat_id, photo_file_path, caption=""):
        """Отправка фото из файла"""
        url = f"{self.base_url}/sendPhoto"
        
        try:
            with open(photo_file_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {'chat_id': chat_id, 'caption': caption}
                
                logger.info(f"📤 Отправка фото для {chat_id} из {photo_file_path}")
                
                response = requests.post(url, files=files, data=data, timeout=30)
                result = response.json()
                logger.info(f"🖼 Результат: {result.get('ok', False)}")
                return result
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото: {e}")
            return None
    
    def get_file(self, file_id):
        """Получение информации о файле"""
        url = f"{self.base_url}/getFile"
        data = {"file_id": file_id}
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('ok'):
                file_path = result['result']['file_path']
                file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                logger.info(f"✅ Файл получен: {file_path}")
                return file_path  # Возвращаем путь, а не URL
            else:
                logger.error(f"❌ Ошибка получения файла: {result}")
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return None

    def download_file(self, file_path, local_path):
        """Скачивание файла с Telegram"""
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        
        try:
            logger.info(f"📥 Скачивание: {file_url}")
            response = requests.get(file_url, timeout=30)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"✅ Файл сохранен: {local_path} ({len(response.content)} bytes)")
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
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            logger.info(f"✅ Webhook установлен: {result.get('ok', False)}")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return None

# Создаем экземпляр бота
bot = TelegramBot(BOT_TOKEN)

def send_to_admin(user_info, user_id):
    """Отправка данных администратору"""
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
        # Получаем информацию о файле
        file_path = bot.get_file(user_info['photo_file_id'])
        
        if not file_path:
            logger.error("❌ Не удалось получить информацию о файле")
            bot.send_message(admin_id, message_text + "\n\n❌ Не удалось загрузить фото")
            return False
        
        # Скачиваем файл
        local_file_path = f"temp_photo_{user_id}.jpg"
        if bot.download_file(file_path, local_file_path):
            # Отправляем фото
            result = bot.send_photo(admin_id, local_file_path, message_text)
            
            # Удаляем временный файл
            try:
                os.remove(local_file_path)
                logger.info(f"✅ Временный файл удален: {local_file_path}")
            except:
                logger.warning(f"⚠️ Не удалось удалить временный файл: {local_file_path}")
            
            if result and result.get('ok'):
                logger.info("✅ Фото успешно отправлено администратору")
                return True
            else:
                logger.error("❌ Не удалось отправить фото")
                bot.send_message(admin_id, message_text + "\n\n❌ Не удалось отправить фото")
                return False
        else:
            logger.error("❌ Не удалось скачать файл")
            bot.send_message(admin_id, message_text + "\n\n❌ Не удалось скачать фото")
            return False
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        bot.send_message(admin_id, message_text + f"\n\n❌ Ошибка: {e}")
        return False

def setup_webhook():
    """Автоматическая установка webhook"""
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    logger.info(f"🔄 Настройка webhook: {webhook_url}")
    
    result = bot.set_webhook(webhook_url)
    
    if result and result.get('ok'):
        logger.info("🎉 Webhook успешно установлен!")
        bot.send_message(ADMIN_CHAT_ID, "🤖 Бот запущен и готов к работе!")
        return True
    else:
        logger.error("❌ Не удалось установить webhook")
        return False

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
                # Берем самое качественное фото
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
                logger.info(f"📸 Пользователь {chat_id} отправил фото")
            
            # Обработка описания
            elif user_sessions.get(chat_id, {}).get('state') == 'waiting_description':
                user_data = user_sessions[chat_id]
                description = text
                
                logger.info(f"📝 Пользователь {chat_id} отправил описание")
                logger.info(f"📤 Отправка заявки администратору {ADMIN_CHAT_ID}")
                
                # Отправляем администратору
                success = send_to_admin(user_data, chat_id)
                
                # Подтверждаем пользователю
                if success:
                    bot.send_message(chat_id, "✅ Спасибо! Ваша заявка с фото отправлена администратору! 🎉")
                else:
                    bot.send_message(chat_id, "✅ Заявка отправлена! Но фото не удалось прикрепить.")
                
                # Очищаем сессию
                if chat_id in user_sessions:
                    del user_sessions[chat_id]
                logger.info(f"✅ Сессия пользователя {chat_id} завершена")
            
            # Обработка команды /help
            elif text == '/help':
                help_text = """
🤖 Помощь по боту:

/start - оставить заявку на покупку техники
/help - показать справку
                """
                bot.send_message(chat_id, help_text)
            
            # Любое другое сообщение
            elif text and not text.startswith('/'):
                if user_sessions.get(chat_id):
                    bot.send_message(chat_id, "❌ Сначала отправьте фото командой /start")
                else:
                    bot.send_message(chat_id, "🤖 Используйте /start чтобы оставить заявку")
        
        return 'OK'
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return 'ERROR'

@app.route('/set_webhook', methods=['GET'])
def set_webhook_manual():
    """Ручная установка webhook"""
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    result = bot.set_webhook(webhook_url)
    return f"Webhook: {result}"

@app.route('/test_photo', methods=['GET'])
def test_photo():
    """Тест отправки текстового сообщения"""
    test_message = "🧪 ТЕСТ: Проверка работы бота. Фото тест временно отключен."
    result = bot.send_message(ADMIN_CHAT_ID, test_message)
    return f"Тест отправлен: {result}"

@app.route('/health')
def health():
    return "OK"

def main():
    logger.info("🤖 Бот запускается...")
    
    # Автоматическая установка webhook
    setup_webhook()
    
    # Запуск Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
