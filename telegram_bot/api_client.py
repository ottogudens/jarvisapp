import os
import httpx

BACKEND_URL = os.getenv("JARVIS_BACKEND_URL", "http://localhost:8000")

class JarvisBackendClient:
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")

    async def link_account(self, telegram_chat_id: str, telegram_username: str, link_code: str):
        url = f"{self.base_url}/v1/telegram/link-account"
        payload = {
            "telegram_chat_id": str(telegram_chat_id),
            "telegram_username": telegram_username,
            "link_code": link_code
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
        return resp

    async def process_message(self, telegram_chat_id: str, telegram_username: str, text: str = "", file_url: str = None, audio_b64: str = None):
        url = f"{self.base_url}/v1/telegram/process-message"
        payload = {
            "telegram_chat_id": str(telegram_chat_id),
            "telegram_username": telegram_username,
            "text": text,
        }
        if file_url:
            payload["file_url"] = file_url
        if audio_b64:
            payload["audio_b64"] = audio_b64
            
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
        return resp
