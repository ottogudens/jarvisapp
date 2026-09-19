import os
import requests

BACKEND_URL = os.getenv("JARVIS_BACKEND_URL", "http://localhost:8000")

class JarvisBackendClient:
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")

    def link_account(self, telegram_chat_id: str, telegram_username: str, link_code: str):
        url = f"{self.base_url}/v1/telegram/link-account"
        payload = {
            "telegram_chat_id": str(telegram_chat_id),
            "telegram_username": telegram_username,
            "link_code": link_code
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp

    def process_message(self, telegram_chat_id: str, telegram_username: str, text: str = "", file_url: str = None):
        url = f"{self.base_url}/v1/telegram/process-message"
        payload = {
            "telegram_chat_id": str(telegram_chat_id),
            "telegram_username": telegram_username,
            "text": text,
            "file_url": file_url
        }
        resp = requests.post(url, json=payload, timeout=60)
        return resp
