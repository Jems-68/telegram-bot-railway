import os
import asyncio
from datetime import datetime, timedelta
from collections import deque

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ContextTypes,
    CommandHandler, MessageHandler, CallbackQueryHandler,
    filters
)

# ===== Config por variables de entorno =====
TOKEN = os.environ["TOKEN"]  # requerido
CHANNEL_ID = os.getenv("CHANNEL_ID", "@infernoplacere")  # ej. @infernoplacere
DEFAULT_WAIT_MINUTES = int(os.getenv("WAIT_MINUTES", "30"))  # 30/60/90
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))  # max 100

# ===== Estado global =====
pendientes = deque()          # guarda objetos telegram.Message
wait_minutes = DEFAULT_WAIT_MINUTES
scheduler_running = False
next_fire_at = None           # datetime de próximo envío
lock = asyncio.Lock()         # para proteger el estado compartido


def kb_tiempo():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏱️ 30 min", callback_data="set_wait_30"),
        InlineKeyboardButton("⏱️ 60 min", callback_data="set_wait_60"),
        InlineKeyboardButton("⏱️ 90 min", callback_data="set_wait_90"),
    ]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Listo! Envíame archivos. Elige el tiempo de espera entre lotes:",
        reply_markup=kb_tiempo()
    )

async def show_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Tiempo actual: {wait_minutes} min. Cambiar:",
        reply_markup=kb_tiempo()
    )

async def handle_set_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global wait_minutes
    q = update.callback_query
    await q.answer()

    if q.data == "set_wait_30":
        wait_minutes = 30
    elif q.data == "set_wait_60":
        wait_minutes = 60
    elif q.data == "set_wait_90":
        wait_minutes = 90

    # Nota: NO ajustamos next_fire_at aquí. El nuevo tiempo aplica al siguiente ciclo.
    await q.edit_message_text(f"✅ Tiempo actualizado: {wait_minutes} minutos.")

async def recibir_archivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe documentos/fotos/videos/audios y los encola."""
    msg = update.message
    if not msg:
        return

    if msg.document or msg.photo or msg.video or msg.audio or msg.animation or msg.sticker:
        async with lock:
            pendientes.append(msg)

            # Si no hay scheduler activo, lo iniciamos y fijamos el primer disparo
            global scheduler_running, next_fire_at
            if not scheduler_running:
                scheduler_running = True
                next_fire_at = datetime.now() + timedelta(minutes=wait_minutes)
                asyncio.create_task(scheduler(context))

        await msg.reply_text(
            f"📦 Guardado. Se enviará en lotes de hasta {BATCH_SIZE}."
        )

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with lock:
        total = len(pendientes)
        running = scheduler_running
        nfa = next_fire_at

    if running and nfa:
        secs = int((nfa - datetime.now()).total_seconds())
        if secs < 0: secs = 0
        mins, s = divmod(secs, 60)
        eta = f"{mins}m {s}s"
    else:
        eta = "—"

    await update.message.reply_text(
        "📊 Estado del bot\n"
        f"- Canal destino: {CHANNEL_ID}\n"
        f"- Pendientes: {total}\n"
        f"- Límite por lote: {BATCH_SIZE}\n"
        f"- Tiempo entre lotes: {wait_minutes} min\n"
        f"- Próximo envío en: {eta}"
    )

async def scheduler(context: ContextTypes.DEFAULT_TYPE):
    """Ciclo que dispara envíos cada 'wait_minutes' cuando hay pendientes.
       En cada disparo ENVÍA LOS ÚLTIMOS 100 (o menos) y luego vuelve a esperar.
    """
    global scheduler_running, next_fire_at

    while True:
        async with lock:
            if not pendientes:
                # Nada que hacer: parar scheduler
                scheduler_running = False
                next_fire_at = None
                return
            fire_at = next_fire_at or (datetime.now() + timedelta(minutes=wait_minutes))

        # Dormir hasta el próximo disparo
        sleep_secs = max(0, int((fire_at - datetime.now()).total_seconds()))
        await asyncio.sleep(sleep_secs)

        # Armar lote: TOMAR LOS MÁS RECIENTES (últimos) hasta BATCH_SIZE
        async with lock:
            if not pendientes:
                # Se vació mientras dormíamos
                scheduler_running = False
                next_fire_at = None
                return

            # Tomar últimos N
            take = min(BATCH_SIZE, len(pendientes))
            # seleccionamos en orden "del más antiguo dentro del lote al más nuevo" para publicar ordenado
            lote = list(pendientes)[-take:]
            # recortar cola
            for _ in range(take):
                pendientes.pop()

        # Enviar el lote
        for m in lote:
            try:
                await m.copy(chat_id=CHANNEL_ID)
                # borrar del chat privado con el bot
                try:
                    await m.delete()
                except Exception:
                    pass
            except Exception as e:
                print(f"[WARN] Falló enviar/copy/delete: {e}")

        # Programar siguiente disparo usando el wait_minutes vigente
        async with lock:
            next_fire_at = datetime.now() + timedelta(minutes=wait_minutes)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("tiempo", show_tiempo))
    app.add_handler(CallbackQueryHandler(handle_set_tiempo))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, recibir_archivo))

    print("🤖 Bot en ejecución (polling)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
