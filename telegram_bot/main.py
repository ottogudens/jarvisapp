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

    # Extraer cualquier token numérico o de texto en el comando
    raw_text = update.message.text or ""
    # Quitar comillas si el usuario escribió /start "123456"
    code = None
    parts = raw_text.strip().split()
    if len(parts) > 1:
        code = parts[1].strip('"\'')

    if code:
        await update.message.reply_text("⏳ Verificando código de vinculación...")
        try:
            resp = client.link_account(chat_id, username, code)
            if resp.status_code == 200:
                data = resp.json()
                await update.message.reply_text(
                    f"✅ ¡Cuenta vinculada exitosamente con *{data.get('email')}*!\n\n"
                    "Ya puedes enviarme cualquier consulta, comandos de MikroTik, IoT o notas de voz.",
                    parse_mode="Markdown"
                )
            else:
                err_detail = "Código de vinculación inválido o expirado."
                try:
                    err_detail = resp.json().get("detail", err_detail)
                except Exception:
                    pass
                await update.message.reply_text(
                    f"❌ Error al vincular la cuenta: {err_detail}\nPor favor genera un nuevo código en la plataforma web."
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error al conectar con el servidor: {e}")
    else:
        await update.message.reply_text(
            "👋 ¡Hola! Bienvenido a *J.A.R.V.I.S. Assistant*.\n\n"
            "Para comenzar, vincula tu cuenta generando un código en la sección de Configuración del panel web y luego envía aquí:\n"
            "`/start <codigo_6_digitos>` (ejemplo: `/start 123456`)",
            parse_mode="Markdown"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name
    text = (update.message.text or "").strip()

    # Si el usuario envía directamente un código de 6 dígitos sin el /start
    clean_text = text.strip('"\'')
    if clean_text.isdigit() and len(clean_text) == 6:
        await update.message.reply_text("⏳ Verificando código de vinculación...")
        try:
            resp = client.link_account(chat_id, username, clean_text)
            if resp.status_code == 200:
                data = resp.json()
                await update.message.reply_text(
                    f"✅ ¡Cuenta vinculada exitosamente con *{data.get('email')}*!\n\n"
                    "Ya puedes enviarme cualquier consulta, comandos de MikroTik, IoT o notas de voz.",
                    parse_mode="Markdown"
                )
                return
        except Exception:
            pass

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
