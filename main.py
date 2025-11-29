import os
import logging
import telegram
from telegram import Update
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, 
                         ConversationHandler, CallbackContext)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
PHOTO, DESCRIPTION = range(2)

# Получаем переменные окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

# Проверка переменных
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен")
    exit(1)
if not ADMIN_CHAT_ID:
    logger.error("❌ ADMIN_CHAT_ID не установлен")
    exit(1)

logger.info("✅ Переменные окружения загружены")

# Хранение временных данных
user_data = {}

def start(update: Update, context: CallbackContext):
    """Начало работы - просим фото"""
    welcome_text = """
🛒 Покупка бытовой техники. 
🔄 Возможен Trade-in.

Присылайте фото и описание неисправности - администратор обязательно даст обратную связь!

📸 Теперь отправь мне фотографию техники:
    """
    
    update.message.reply_text(welcome_text)
    return PHOTO

def handle_photo(update: Update, context: CallbackContext):
    """Обработка полученного фото"""
    user_id = update.message.from_user.id
    
    try:
        # Сохраняем фото
        photo_file = update.message.photo[-1].get_file()
        user_data[user_id] = {'photo': photo_file}
        
        update.message.reply_text(
            "✅ Фото получено! Теперь опиши неисправность техники:\n\n"
            "• Какая модель?\n"
            "• Что случилось?\n"
            "• Какие симптомы?"
        )
        return DESCRIPTION
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        update.message.reply_text("❌ Ошибка при обработке фото. Попробуйте еще раз: /start")
        return ConversationHandler.END

def handle_description(update: Update, context: CallbackContext):
    """Обработка описания и отправка данных администратору"""
    user_id = update.message.from_user.id
    description = update.message.text
    
    if user_id not in user_data or 'photo' not in user_data[user_id]:
        update.message.reply_text("❌ Сначала отправь фото! Напиши /start")
        return ConversationHandler.END
    
    # Сохраняем информацию
    user_info = user_data[user_id]
    user_info['description'] = description
    user_info['user_name'] = update.message.from_user.first_name
    user_info['username'] = update.message.from_user.username or 'не указан'
    
    try:
        # Отправляем администратору
        send_to_admin(context.bot, user_info, user_id)
        
        update.message.reply_text(
            "✅ Спасибо! Ваши фото и описание отправлены администратору! 🎉\n\n"
            "Мы свяжемся с вами в ближайшее время для обратной связи."
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        update.message.reply_text("❌ Ошибка при отправке. Попробуйте еще раз: /start")
    
    # Очищаем данные
    if user_id in user_data:
        del user_data[user_id]
    
    return ConversationHandler.END

def send_to_admin(bot, user_info, user_id):
    """Отправка данных администратору"""
    message_text = f"""
🛒 НОВАЯ ЗАЯВКА НА ПОКУПКУ ТЕХНИКИ

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание неисправности: 
{user_info['description']}

Фото техники ниже 👇
    """
    
    try:
        # Скачиваем фото
        photo_path = f"temp_photo_{user_id}.jpg"
        user_info['photo'].download(photo_path)
        
        # Отправляем фото и текст
        with open(photo_path, 'rb') as photo:
            bot.send_photo(
                chat_id=int(ADMIN_CHAT_ID),
                photo=photo,
                caption=message_text
            )
        
        # Удаляем временный файл
        os.remove(photo_path)
        logger.info("✅ Фото отправлено администратору")
        
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        # Отправляем только текст
        bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text=message_text + "\n\n❌ Не удалось отправить фото"
        )

def cancel(update: Update, context: CallbackContext):
    """Отмена операции"""
    user_id = update.message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    update.message.reply_text("❌ Заявка отменена. Напишите /start чтобы начать заново.")
    return ConversationHandler.END

def help_command(update: Update, context: CallbackContext):
    """Команда помощи"""
    help_text = """
🤖 Помощь по боту:

/start - оставить заявку на покупку техники
/help - показать справку  
/cancel - отменить заявку
    """
    update.message.reply_text(help_text)

def error(update: Update, context: CallbackContext):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")

def main():
    try:
        # Создаем updater
        updater = Updater(BOT_TOKEN, use_context=True)
        
        # Получаем dispatcher
        dp = updater.dispatcher
        
        # Создаем обработчик разговора
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                PHOTO: [MessageHandler(Filters.photo, handle_photo)],
                DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, handle_description)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        dp.add_handler(conv_handler)
        dp.add_handler(CommandHandler('help', help_command))
        dp.add_error_handler(error)
        
        # Запускаем бота
        logger.info("🤖 Бот запускается...")
        updater.start_polling()
        logger.info("✅ Бот успешно запущен и готов к работе!")
        
        # Бесконечный цикл
        updater.idle()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        exit(1)

if __name__ == "__main__":
    main()
