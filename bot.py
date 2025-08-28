import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Configuración de logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- Obtener el token de las variables de entorno ---
TOKEN = os.environ.get("BOT_TOKEN")  # ahora BOT_TOKEN
if not TOKEN:
    raise ValueError("❌ No se encontró la variable BOT_TOKEN. Configúrala en Railway.")

# --- ID o @username del canal de destino ---
TARGET_CHAT_ID = "@inferno_placere"  # cambia por el username exacto de tu canal

# --- Estado global ---
estado = {
    "tiempo": 30,  # tiempo por defecto en minutos
    "archivos": []
}

# --- Comando inicio ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("⏱ 30 min", callback_data="set_30"),
            InlineKeyboardButton("⏱ 60 min", callback_data="set_60"),
            InlineKeyboardButton("⏱ 90 min", callback_data="set_90"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Hola, el bot está activo.\n⏱ Tiempo actual: {estado['tiempo']} minutos.",
        reply_markup=reply_markup
    )

# --- Manejo de botones ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "set_30":
        estado["tiempo"] = 30
    elif query.data == "set_60":
        estado["tiempo"] = 60
    elif query.data == "set_90":
        estado["tiempo"] = 90
    await query.edit_message_text(text=f"✅ Tiempo cambiado a {estado['tiempo']} minutos.")

# --- Recepción de archivos ---
async def recibir_archivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document or update.message.photo or update.message.video:
        estado["archivos"].append(update.message)
        await update.message.reply_text("📥 Archivo recibido y en cola.")

# --- Enviar en lotes ---
async def enviar_lotes(context: ContextTypes.DEFAULT_TYPE):
    if not estado["archivos"]:
        return
    
    lote = estado["archivos"][:100]  # máximo 100
    estado["archivos"] = estado["archivos"][100:]

    for msg in lote:
        try:
            if msg.document:
                await context.bot.send_document(chat_id=TARGET_CHAT_ID, document=msg.document.file_id)
            elif msg.photo:
                await context.bot.send_photo(chat_id=TARGET_CHAT_ID, photo=msg.photo[-1].file_id)
            elif msg.video:
                await context.bot.send_video(chat_id=TARGET_CHAT_ID, video=msg.video.file_id)
            await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
        except Exception as e:
            logging.error(f"Error al enviar archivo: {e}")

    # programar el siguiente envío
    context.job_queue.run_once(enviar_lotes, estado["tiempo"] * 60)

# --- Arranque ---
def main():
    application = Application.builder().token(TOKEN).build()
    job_queue = application.job_queue


    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, recibir_archivo))

    # programar el primer envío
    application.job_queue.run_once(enviar_lotes, estado["tiempo"] * 60)

    application.run_polling()

if __name__ == "__main__":
    main()
