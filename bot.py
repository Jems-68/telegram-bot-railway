import os
import logging
import asyncio
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
    "archivos": [],
    "contador": 0,
    "mensaje_cola": None
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
        estado["contador"] += 1

        texto = f"📥 Archivo agregado a la cola. Total en cola: {estado['contador']}"

        # Actualiza el mensaje en vez de enviar uno nuevo cada vez
        if estado["mensaje_cola"] is None:
            estado["mensaje_cola"] = await update.message.reply_text(texto)
        else:
            try:
                await estado["mensaje_cola"].edit_text(texto)
            except Exception:
                estado["mensaje_cola"] = await update.message.reply_text(texto)


# --- Enviar en lotes ---
async def enviar_lotes(context: ContextTypes.DEFAULT_TYPE):
    if not estado["archivos"]:
        return

    # Esperar 5 minutos ANTES de procesar el lote
    logging.info("⏳ Esperando 5 minutos antes de procesar el lote...")
    await asyncio.sleep(5 * 60)

    if not estado["archivos"]:
        return

    # Seleccionar hasta 95 archivos
    lote = estado["archivos"][:95]
    estado["archivos"] = estado["archivos"][95:]
    estado["contador"] = len(estado["archivos"])

    logging.info(f"🚀 Enviando lote de {len(lote)} archivos...")

    for msg in lote:
        try:
            if msg.document:
                await context.bot.send_document(chat_id=TARGET_CHAT_ID, document=msg.document.file_id)
            elif msg.photo:
                await context.bot.send_photo(chat_id=TARGET_CHAT_ID, photo=msg.photo[-1].file_id)
            elif msg.video:
                await context.bot.send_video(chat_id=TARGET_CHAT_ID, video=msg.video.file_id)

            # Eliminar el mensaje original del chat privado
            await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)

        except Exception as e:
            logging.error(f"Error al enviar archivo: {e}")

    # Actualizar mensaje de cola
    if estado["mensaje_cola"]:
        try:
            await estado["mensaje_cola"].edit_text(f"✅ Último lote enviado.\n📦 Archivos restantes en cola: {estado['contador']}")
        except Exception:
            estado["mensaje_cola"] = None

    # Programar siguiente envío
    context.job_queue.run_once(enviar_lotes, estado["tiempo"] * 60)


# --- Arranque ---
def main():
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, recibir_archivo))

    # Programar el primer envío
    application.job_queue.run_once(enviar_lotes, estado["tiempo"] * 60)

    application.run_polling()


if __name__ == "__main__":
    main()
