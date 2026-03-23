"""Telegram mesaj gonderme araci — Ali v2 uzerinden Telegram'a mesaj gonderir."""

from __future__ import annotations
from tools.base import BaseTool


class TelegramBotTool(BaseTool):
    name = "telegram_mesaj"
    description = (
        "Telegram uzerinden mesaj gonderir. "
        "Belirtilen chat_id'ye metin mesaji gonderir. "
        "Bot'un calisiyor olmasi gerekir."
    )
    parameters = {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string",
                "description": "Telegram chat ID veya kullanici adi (@username)",
            },
            "text": {
                "type": "string",
                "description": "Gonderilecek mesaj metni",
            },
        },
        "required": ["chat_id", "text"],
    }

    def run(self, chat_id: str = "", text: str = "", **kw) -> str:
        if not chat_id:
            return "Hata: chat_id belirtilmedi."
        if not text:
            return "Hata: Mesaj metni bos."

        try:
            from core.telegram import is_running, send_message_sync

            if not is_running():
                return (
                    "Telegram botu calismıyor. "
                    "Lutfen once .env dosyasina TELEGRAM_BOT_TOKEN ekleyin "
                    "ve botu baslatin."
                )

            # chat_id sayisal ise int'e cevir
            try:
                resolved_id: int | str = int(chat_id)
            except ValueError:
                resolved_id = chat_id

            success = send_message_sync(resolved_id, text)
            if success:
                return f"Mesaj basariyla gonderildi (chat_id: {chat_id})."
            else:
                return "Mesaj gonderilemedi. Loglari kontrol edin."

        except ImportError:
            return "Telegram modulu yuklenemedi. python-telegram-bot paketini kontrol edin."
        except Exception as e:
            return f"Telegram hatasi: {e}"
