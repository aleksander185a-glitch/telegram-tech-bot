python
import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

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
if not BOT_TOKEN or not ADMIN_CHAT_ID:
    logger.error("❌ BOT_TOKEN или ADMIN_CHAT_ID не установлены")
    exit(1)

logger.info("✅ Переменные окружения загружены")

# Хранение временных данных
user_data = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы - просим фото"""
    welcome_text = """
🛒 Покупка бытовой техники. 
🔄 Возможен Trade-in.

Присылайте фото бытовой техники, шильдика и описание неисправности - администратор свяжется с вами!

📸 Теперь отправьте фотографию:
    """
    
    await update.message.reply_text(welcome_text)
    return PHOTO

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка полученного фото"""
    user_id = update.message.from_user.id
    
    try:
        # Сохраняем фото (берем самое качественное)
        photo_file = await update.message.photo[-1].get_file()
        user_data[user_id] = {'photo': photo_file}
        
        await update.message.reply_text(
            "✅ Фото получено! Теперь опишите неисправность или укажите модель, если не отправили шильдик:\n\n"
                   )
        return DESCRIPTION
    except Exception as e:
        logger.error(f"Ошибка обработки фото: {e}")
        await update.message.reply_text("❌ Ошибка при обработке фото. Попробуйте еще раз: /start")
        return ConversationHandler.END

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания и отправка данных администратору"""
    user_id = update.message.from_user.id
    description = update.message.text
    
    if user_id not in user_data or 'photo' not in user_data[user_id]:
        await update.message.reply_text("❌ Сначала отправь фото! Напиши /start")
        return ConversationHandler.END
    
    # Сохраняем описание и информацию о пользователе
    user_data[user_id]['description'] = description
    user_data[user_id]['user_name'] = update.message.from_user.first_name
    user_data[user_id]['username'] = update.message.from_user.username or 'не указан'
    
    try:
        # Отправляем данные администратору в Telegram
        await send_to_admin(update, context, user_id)
        
        await update.message.reply_text(
            "✅ Спасибо! Ваши фото и описание отправлены администратору! 🎉\n\n"
            "Мы свяжемся с вами в ближайшее время.\n\n"
            "Если хотите отправить еще одну заявку, напишите /start"
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке. Попробуйте еще раз: /start"
        )
    
    # Очищаем данные пользователя
    if user_id in user_data:
        del user_data[user_id]
    
    return ConversationHandler.END

async def send_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Отправка данных администратору в Telegram"""
    user_info = user_data[user_id]
    
    # Текст сообщения для администратора
    message_text = f"""
🛒 НОВАЯ ЗАЯВКА НА ПОКУПКУ ТЕХНИКИ

👤 Клиент: {user_info['user_name']}
📱 Username: @{user_info['username']}
📝 Описание неисправности: 
{user_info['description']}

    """
    
    try:
        # Скачиваем фото
        photo_path = f"temp_photo_{user_id}.jpg"
        await user_info['photo'].download_to_drive(photo_path)
        
        # Отправляем фото и текст администратору
        with open(photo_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=int(ADMIN_CHAT_ID),
                photo=photo,
                caption=message_text
            )
        
        # Удаляем временный файл
        os.remove(photo_path)
        logger.info("✅ Фото успешно отправлено администратору")
        
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        # Отправляем хотя бы текст если фото не отправилось
        await context.bot.send_message(
            chat_id=int(ADMIN_CHAT_ID),
            text=message_text + "\n\n❌ Не удалось отправить фото"
        )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    user_id = update.message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    await update.message.reply_text(
        "❌ Заявка отменена.\n\n"
        "Если хотите оставить заявку на покупку техники, напишите /start"
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    help_text = """
🤖 Помощь по боту:

🛒 Покупка бытовой техники с Trade-in

/start - оставить заявку на покупку техники
/help - показать эту справку  
/cancel - отменить текущую заявку

Как это работает:
1. Отправляете фото техники
2. Описываете неисправность
3. Администратор связывается с вами
    """
    await update.message.reply_text(help_text)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")

def main():
    # Создаем приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Создаем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, handle_photo)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_command),
            CommandHandler('help', help_command)
        ]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('help', help_command))
    app.add_error_handler(error_handler)
    
    logger.info("🤖 Бот запущен и готов принимать заявки на технику!")
    
    # Запускаем бота
    app.run_polling()

if __name__ == "__main__":
    main()
