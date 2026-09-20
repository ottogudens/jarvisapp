import os
import re
import base64
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

async def try_link_account(update: Update, chat_id: str, username: str, text: str) -> bool:
    """Intenta extraer un código de 6 dígitos del texto y vincularlo.
    Retorna True si encontró código y procesó su intento, False de lo contrario."""
    match = re.search(r'\b\d{6}\b', text)
    if not match:
        return False
    
    code = match.group(0)
    await update.message.reply_text("⏳ Verificando código de vinculación...")
    try:
        resp = await client.link_account(chat_id, username, code)
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
    return True

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name

    raw_text = update.message.text or ""
    
    processed = await try_link_account(update, chat_id, username, raw_text)
    if not processed:
        await update.message.reply_text(
            "👋 ¡Hola! Bienvenido a *J.A.R.V.I.S. Assistant*.\n\n"
            "Para comenzar, vincula tu cuenta generando un código de 6 dígitos en la sección de Configuración del panel web y envíalo aquí:\n"
            "`/start 123456` o simplemente escribe el código.",
            parse_mode="Markdown"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name
    text = (update.message.text or "").strip()

    # Si el mensaje es solo un código, intentar vincular
    if len(text) <= 15: # Para no interferir con mensajes normales que accidentalmente contengan 6 números
        processed = await try_link_account(update, chat_id, username, text)
        if processed:
            return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        resp = await client.process_message(chat_id, username, text=text)
        if resp.status_code == 200:
            data = resp.json()
            respuesta = data.get("respuesta", "Sin respuesta.")
            await update.message.reply_text(respuesta, parse_mode="Markdown")
        elif resp.status_code == 401:
            await update.message.reply_text(
                "⚠️ Tu cuenta de Telegram no está vinculada.\nGenera un código de 6 dígitos en la plataforma e ingresa:\n`/start <codigo>`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ Ocurrió un error al procesar tu solicitud (HTTP {resp.status_code}).")
    except Exception as e:
        await update.message.reply_text(f"❌ Excepción conectando con el backend: {e}")

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name
    
    await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
    
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        file_bytes = await file.download_as_bytearray()
        
        audio_b64 = base64.b64encode(file_bytes).decode('utf-8')
        
        resp = await client.process_message(chat_id, username, text="", audio_b64=audio_b64)
        if resp.status_code == 200:
            data = resp.json()
            respuesta = data.get("respuesta", "Sin respuesta.")
            
            # Enviar audio de respuesta si el backend lo proveyó
            audio_response_b64 = data.get("audio_base64")
            if audio_response_b64:
                file_dat = base64.b64decode(audio_response_b64)
                await update.message.reply_voice(file_dat)
                
            await update.message.reply_text(respuesta, parse_mode="Markdown")
        elif resp.status_code == 401:
            await update.message.reply_text("⚠️ Tu cuenta no está vinculada. Usa /start <codigo>")
        else:
            await update.message.reply_text("❌ Error procesando tu nota de voz.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al procesar audio: {e}")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name
    caption = update.message.caption or "Describe esta imagen"
    
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
    
    try:
        # Descargar la foto de mayor resolución
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # En vez de descargar, podemos pasar la ruta de telegram provista por get_file
        # Para que Jarvis la analice, le pasamos la URL directa.
        file_url = file.file_path
        
        resp = await client.process_message(chat_id, username, text=caption, file_url=file_url)
        if resp.status_code == 200:
            data = resp.json()
            respuesta = data.get("respuesta", "Sin respuesta.")
            await update.message.reply_text(respuesta, parse_mode="Markdown")
        elif resp.status_code == 401:
            await update.message.reply_text("⚠️ Tu cuenta no está vinculada. Usa /start <codigo>")
        else:
            await update.message.reply_text("❌ Error procesando tu foto.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al procesar foto: {e}")

def main():
    if not BOT_TOKEN:
        print("⚠️ Error: Debe configurar la variable TELEGRAM_BOT_TOKEN.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    print("🚀 Bot de Telegram de J.A.R.V.I.S. (Async/Multimodal) iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()

