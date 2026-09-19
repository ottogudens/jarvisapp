import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from api_client import JarvisBackendClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
client = JarvisBackendClient()

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name

    # Si se pasó un argumento de código: /start 123456
    if context.args:
        code = context.args[0]
        await update.message.reply_text("⏳ Verificando código de vinculación...")
        resp = client.link_account(chat_id, username, code)
        if resp.status_code == 200:
            data = resp.json()
            await update.message.reply_text(
                f"✅ ¡Cuenta vinculada exitosamente con *{data.get('email')}*!\n\n"
                "Ya puedes enviarme cualquier consulta, comandos de MikroTik, IoT o notas de voz.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Error al vincular la cuenta. Verifica que el código sea correcto y no haya expirado."
            )
    else:
        await update.message.reply_text(
            "👋 ¡Hola! Bienvenido a *J.A.R.V.I.S. Assistant*.\n\n"
            "Para comenzar, vincula tu cuenta generando un código en el panel web y luego envía aquí:\n"
            "`/start <codigo_6_digitos>`",
            parse_mode="Markdown"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    resp = client.process_message(chat_id, username, text=text)
    if resp.status_code == 200:
        data = resp.json()
        respuesta = data.get("respuesta", "Sin respuesta.")
        await update.message.reply_text(respuesta, parse_mode="Markdown")
    elif resp.status_code == 401:
        await update.message.reply_text(
            "⚠️ Tu cuenta de Telegram no está vinculada.\nGenera un código en la plataforma e ingresa:\n`/start <codigo>`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Ocurrió un error al procesar tu solicitud.")

def main():
    if not BOT_TOKEN:
        print("⚠️ Error: Debe configurar la variable TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))

    print("🚀 Bot de Telegram de J.A.R.V.I.S. iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()
