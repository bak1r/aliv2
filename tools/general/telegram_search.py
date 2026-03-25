"""Telegram arama ve okuma araclari — Telethon User API ile calışır."""

from __future__ import annotations

import asyncio
import threading
from tools.base import BaseTool


def _get_monitor():
    """Global telegram monitor instance'ını al."""
    try:
        from core import _telegram_monitor_instance
        return _telegram_monitor_instance
    except (ImportError, AttributeError):
        return None


def _run_async(coro):
    """Async fonksiyonu sync context'te çalıştır."""
    monitor = _get_monitor()
    if not monitor or not monitor._client:
        return None
    loop = monitor._client.loop
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)


class TelegramSearchTool(BaseTool):
    name = "telegram_ara"
    description = (
        "Telegram mesajlarinda arama yapar. "
        "Tum sohbetlerde veya belirli bir sohbette arama yapabilir. "
        "Telethon User API gerektirir."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Aranacak metin",
            },
            "chat_name": {
                "type": "string",
                "description": "Aranacak sohbet adi (opsiyonel — bos birakilirsa tum sohbetlerde arar)",
            },
            "limit": {
                "type": "integer",
                "description": "Maksimum sonuc sayisi (varsayilan: 20)",
            },
        },
        "required": ["query"],
    }

    def run(self, query: str = "", chat_name: str = "", limit: int = 20, **kw) -> str:
        if not query:
            return "Hata: Aranacak metin belirtilmedi."

        monitor = _get_monitor()
        if not monitor or not monitor.is_connected:
            return "Telegram User API bagli degil. TG_API_ID, TG_API_HASH, TG_PHONE ayarlayin."

        try:
            results = _run_async(monitor.search_messages(query, chat_name=chat_name or None, limit=limit))
            if not results:
                return f"'{query}' icin sonuc bulunamadi."

            lines = [f"'{query}' icin {len(results)} sonuc:\n"]
            for r in results:
                lines.append(
                    f"[{r.get('date', '?')}] {r.get('chat_name', '?')} — "
                    f"{r.get('sender_name', '?')}: {r.get('text', '')[:150]}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Arama hatasi: {e}"


class TelegramChatListTool(BaseTool):
    name = "telegram_sohbetler"
    description = (
        "Telegram sohbet listesini dondurur. "
        "Gruplar, kanallar ve bireysel sohbetleri listeler."
    )
    parameters = {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Filtre: 'all' (tumu), 'group' (gruplar), 'channel' (kanallar), 'user' (bireysel)",
            },
            "limit": {
                "type": "integer",
                "description": "Maksimum sonuc (varsayilan: 30)",
            },
        },
        "required": [],
    }

    def run(self, filter: str = "all", limit: int = 30, **kw) -> str:
        monitor = _get_monitor()
        if not monitor or not monitor.is_connected:
            return "Telegram User API bagli degil."

        try:
            chats = _run_async(monitor.list_dialogs(filter_type=filter, limit=limit))
            if not chats:
                return "Sohbet bulunamadi."

            lines = [f"{len(chats)} sohbet:\n"]
            for c in chats:
                unread = c.get("unread_count", 0)
                marker = f" ({unread} okunmamis)" if unread > 0 else ""
                lines.append(f"  [{c.get('type', '?')}] {c.get('name', '?')}{marker}")
            return "\n".join(lines)
        except Exception as e:
            return f"Sohbet listesi hatasi: {e}"


class TelegramReadMessagesTool(BaseTool):
    name = "telegram_mesaj_oku"
    description = (
        "Belirli bir Telegram sohbetindeki mesajlari okur. "
        "Sohbet adi ile arama yapar."
    )
    parameters = {
        "type": "object",
        "properties": {
            "chat_name": {
                "type": "string",
                "description": "Sohbet adi (ornek: 'Ahmet', 'Proje Grubu')",
            },
            "limit": {
                "type": "integer",
                "description": "Okunacak mesaj sayisi (varsayilan: 20)",
            },
        },
        "required": ["chat_name"],
    }

    def run(self, chat_name: str = "", limit: int = 20, **kw) -> str:
        if not chat_name:
            return "Hata: Sohbet adi belirtilmedi."

        monitor = _get_monitor()
        if not monitor or not monitor.is_connected:
            return "Telegram User API bagli degil."

        try:
            messages = _run_async(monitor.read_chat_messages(chat_name=chat_name, limit=limit))
            if not messages:
                return f"'{chat_name}' sohbetinde mesaj bulunamadi veya sohbet yok."

            lines = [f"'{chat_name}' — son {len(messages)} mesaj:\n"]
            for m in messages:
                lines.append(
                    f"[{m.get('date', '?')}] {m.get('sender_name', '?')}: "
                    f"{m.get('text', '')[:200]}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Mesaj okuma hatasi: {e}"
