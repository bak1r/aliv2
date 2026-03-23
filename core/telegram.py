"""Ali v2 — Telegram Bot Daemon
Telegram uzerinden gelen mesajlari brain.think() fonksiyonuna yonlendirir,
yanitlari kullaniciya geri gonderir ve WebSocket uzerinden web UI'a bildirir.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from core.config import get_telegram_token

log = logging.getLogger("ali.telegram")

# ── Durum ────────────────────────────────────────────────────────────
_application: Optional[Application] = None
_running = False
_thread: Optional[threading.Thread] = None

# Yetkilendirilmis kullanicilar (bos ise herkese acik)
_ALLOWED_USERS: set[int] = set()

# ── Hukuk inline klavyesi ────────────────────────────────────────────
_HUKUK_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("Ceza Hukuku", callback_data="q:Ceza hukuku hakkinda bilgi ver"),
        InlineKeyboardButton("Medeni Hukuk", callback_data="q:Medeni hukuk hakkinda bilgi ver"),
    ],
    [
        InlineKeyboardButton("Is Hukuku", callback_data="q:Is hukuku hakkinda bilgi ver"),
        InlineKeyboardButton("Idare Hukuku", callback_data="q:Idare hukuku hakkinda bilgi ver"),
    ],
    [
        InlineKeyboardButton("TCK Madde Ara", callback_data="q:TCK maddeleri hakkinda bilgi ver"),
        InlineKeyboardButton("CMK Madde Ara", callback_data="q:CMK maddeleri hakkinda bilgi ver"),
    ],
    [
        InlineKeyboardButton("Dava Sureci", callback_data="q:Dava sureci nasil isler"),
        InlineKeyboardButton("Savunma Hakki", callback_data="q:Savunma hakki nedir"),
    ],
])


# ── WebSocket broadcast yardimcisi ──────────────────────────────────
async def _ws_broadcast(event_type: str, data: dict):
    """Web UI'a WebSocket uzerinden event gonder."""
    try:
        from web.server import broadcast, _clients
        if _clients:
            await broadcast(event_type, data)
    except ImportError:
        pass
    except Exception as e:
        log.debug(f"WS broadcast hatasi: {e}")


def _ws_broadcast_sync(event_type: str, data: dict):
    """Senkron koddan WS broadcast cagir."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_ws_broadcast(event_type, data))
        else:
            loop.run_until_complete(_ws_broadcast(event_type, data))
    except RuntimeError:
        # Event loop yoksa yeni bir tane olustur
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_ws_broadcast(event_type, data))
            loop.close()
        except Exception:
            pass


# ── Yetki kontrolu ──────────────────────────────────────────────────
def _is_authorized(user_id: int) -> bool:
    """Kullanici yetkili mi kontrol et."""
    if not _ALLOWED_USERS:
        return True  # Kisitlama yoksa herkese acik
    return user_id in _ALLOWED_USERS


# ── Komut handler'lari ──────────────────────────────────────────────
async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/start' komutu — karsilama mesaji."""
    user = update.effective_user
    if not _is_authorized(user.id):
        await update.message.reply_text("Yetkiniz bulunmamaktadir.")
        return

    welcome = (
        f"Merhaba {user.first_name}!\n\n"
        f"Ben Ali, avukat AI asistaniyim. Size hukuki konularda "
        f"yardimci olabilirim.\n\n"
        f"Komutlar:\n"
        f"/start - Baslangic mesaji\n"
        f"/help - Yardim\n"
        f"/hukuk - Hukuk alanlari menusu\n"
        f"/temizle - Konusma gecmisini temizle\n\n"
        f"Dogrudan mesaj yazarak soru sorabilirsiniz."
    )
    await update.message.reply_text(welcome)

    # Web UI'a bildir
    await _ws_broadcast("telegram_event", {
        "event": "start",
        "user": user.first_name,
        "user_id": user.id,
    })


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/help' komutu — yardim mesaji."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("Yetkiniz bulunmamaktadir.")
        return

    help_text = (
        "Ali v2 — Avukat AI Asistani\n\n"
        "Kullanim:\n"
        "- Dogrudan mesaj yazarak hukuki soru sorun\n"
        "- /hukuk komutuyla hukuk alanlari menusunu acin\n"
        "- /temizle ile konusma gecmisini sifirlayin\n\n"
        "Desteklenen alanlar:\n"
        "- Ceza Hukuku (TCK, CMK)\n"
        "- Medeni Hukuk\n"
        "- Is Hukuku\n"
        "- Idare Hukuku\n"
        "- Mevzuat arama\n\n"
        "Not: Yanitlar bilgi amaclidir, hukuki tavsiye niteliginde degildir."
    )
    await update.message.reply_text(help_text)


async def _cmd_hukuk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/hukuk' komutu — inline klavye ile hukuk alanlari menusu."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("Yetkiniz bulunmamaktadir.")
        return

    await update.message.reply_text(
        "Hukuk alani secin veya dogrudan soru yazin:",
        reply_markup=_HUKUK_KEYBOARD,
    )


async def _cmd_temizle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'/temizle' komutu — konusma gecmisini temizle."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("Yetkiniz bulunmamaktadir.")
        return

    try:
        from core.brain import clear_history
        clear_history()
        await update.message.reply_text("Konusma gecmisi temizlendi.")
    except Exception as e:
        await update.message.reply_text(f"Gecmis temizlenemedi: {e}")


# ── Inline klavye callback ──────────────────────────────────────────
async def _callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline klavye butonlarina basildiginda calisir."""
    query = update.callback_query
    await query.answer()

    if not _is_authorized(query.from_user.id):
        await query.edit_message_text("Yetkiniz bulunmamaktadir.")
        return

    data = query.data
    if not data.startswith("q:"):
        return

    user_question = data[2:]
    await query.edit_message_text(f"Soru: {user_question}\n\nYanit hazirlaniyor...")

    # Web UI'a bildir
    await _ws_broadcast("telegram_event", {
        "event": "message",
        "user": query.from_user.first_name,
        "user_id": query.from_user.id,
        "text": user_question,
        "source": "inline_keyboard",
    })

    # Brain'e gonder
    response = await _process_message(user_question, query.from_user.first_name)
    await query.edit_message_text(f"Soru: {user_question}\n\n{response}")

    # Yaniti web UI'a bildir
    await _ws_broadcast("telegram_event", {
        "event": "response",
        "user": query.from_user.first_name,
        "text": response[:200],
    })


# ── Mesaj isleme ────────────────────────────────────────────────────
async def _process_message(text: str, user_name: str = "") -> str:
    """Mesaji brain.think() fonksiyonuna gonder ve yanit al."""
    try:
        from core.brain import think
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: think(user_message=text, user_name=user_name),
        )
        return response
    except Exception as e:
        log.error(f"Brain hatasi: {e}")
        return f"Uzgunun, bir hata olustu: {e}"


async def _message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Serbest metin mesajlarini isler."""
    user = update.effective_user
    if not _is_authorized(user.id):
        await update.message.reply_text("Yetkiniz bulunmamaktadir.")
        return

    text = update.message.text
    if not text or not text.strip():
        return

    log.info(f"[Telegram] {user.first_name} ({user.id}): {text[:80]}")

    # Web UI'a bildir
    await _ws_broadcast("telegram_event", {
        "event": "message",
        "user": user.first_name,
        "user_id": user.id,
        "text": text[:200],
        "source": "telegram",
    })

    # "Yaziyor..." gostergesi
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )

    # Brain'e gonder
    response = await _process_message(text, user.first_name)

    # Telegram mesaj limiti: 4096 karakter
    if len(response) > 4000:
        # Parcalara bol ve gonder
        chunks = [response[i:i + 4000] for i in range(0, len(response), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk)
    else:
        await update.message.reply_text(response)

    # Yaniti web UI'a bildir
    await _ws_broadcast("telegram_event", {
        "event": "response",
        "user": user.first_name,
        "text": response[:200],
    })


# ── Bot yonetimi ────────────────────────────────────────────────────
async def _post_init(application: Application):
    """Bot baslatildiktan sonra komutlari ayarla."""
    commands = [
        BotCommand("start", "Baslangic mesaji"),
        BotCommand("help", "Yardim"),
        BotCommand("hukuk", "Hukuk alanlari menusu"),
        BotCommand("temizle", "Konusma gecmisini temizle"),
    ]
    await application.bot.set_my_commands(commands)
    bot_info = await application.bot.get_me()
    log.info(f"[Telegram] Bot basladi: @{bot_info.username}")
    print(f"[Telegram] Bot basladi: @{bot_info.username}")


def _build_application() -> Application:
    """Telegram Application nesnesini olustur ve handler'lari ekle."""
    token = get_telegram_token()
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN .env dosyasinda tanimli degil. "
            "Lutfen .env dosyasina TELEGRAM_BOT_TOKEN=<token> ekleyin."
        )

    app = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .build()
    )

    # Handler'lari ekle (oncelik sirasina gore)
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("hukuk", _cmd_hukuk))
    app.add_handler(CommandHandler("temizle", _cmd_temizle))
    app.add_handler(CallbackQueryHandler(_callback_query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _message_handler))

    return app


def start_telegram_bot(allowed_users: list[int] | None = None):
    """Telegram bot'u arka plan thread'inde baslat.

    Args:
        allowed_users: Yetkilendirilmis Telegram kullanici ID'leri.
                       None veya bos liste = herkese acik.
    """
    global _application, _running, _thread, _ALLOWED_USERS

    token = get_telegram_token()
    if not token:
        log.warning("[Telegram] TELEGRAM_BOT_TOKEN bulunamadi, bot baslatilmadi.")
        print("[Telegram] TELEGRAM_BOT_TOKEN bulunamadi, bot baslatilmadi.")
        return None

    if _running:
        log.warning("[Telegram] Bot zaten calisiyor.")
        return _thread

    if allowed_users:
        _ALLOWED_USERS = set(allowed_users)

    def _run_bot():
        global _application, _running
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _application = _build_application()
            _running = True
            # Manuel polling — run_polling yerine (set_wakeup_fd hatasini onler)
            loop.run_until_complete(_application.initialize())
            loop.run_until_complete(_application.start())
            loop.run_until_complete(_application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
            ))
            print("[Telegram] Bot baslatildi")
            loop.run_forever()
        except Exception as e:
            log.error(f"[Telegram] Bot hatasi: {e}")
            print(f"[Telegram] Bot hatasi: {e}")
        finally:
            _running = False
            try:
                loop.run_until_complete(_application.updater.stop())
                loop.run_until_complete(_application.stop())
                loop.run_until_complete(_application.shutdown())
            except: pass
            loop.close()

    _thread = threading.Thread(target=_run_bot, daemon=True, name="telegram-bot")
    _thread.start()
    print("[Telegram] Bot baslatiliyor...")
    return _thread


def stop_telegram_bot():
    """Telegram bot'u durdur."""
    global _application, _running
    if _application and _running:
        try:
            _application.stop_running()
            _running = False
            log.info("[Telegram] Bot durduruldu.")
            print("[Telegram] Bot durduruldu.")
        except Exception as e:
            log.error(f"[Telegram] Durdurma hatasi: {e}")


def is_running() -> bool:
    """Bot calisiyor mu?"""
    return _running


async def send_message(chat_id: int | str, text: str) -> bool:
    """Belirtilen chat'e mesaj gonder.

    Args:
        chat_id: Telegram chat ID veya kullanici adi.
        text: Gonderilecek mesaj.

    Returns:
        Basarili ise True.
    """
    if not _application or not _running:
        log.warning("[Telegram] Bot calismadigi icin mesaj gonderilemedi.")
        return False

    try:
        # Uzun mesajlari parcala
        if len(text) > 4000:
            chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
            for chunk in chunks:
                await _application.bot.send_message(chat_id=chat_id, text=chunk)
        else:
            await _application.bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        log.error(f"[Telegram] Mesaj gonderilemedi: {e}")
        return False


def send_message_sync(chat_id: int | str, text: str) -> bool:
    """Senkron koddan mesaj gonder — herhangi bir thread'den cagirilabilir."""
    if not _application or not _running:
        log.warning("[Telegram] Bot calismadigi icin mesaj gonderilemedi.")
        return False
    try:
        import httpx
        token = get_telegram_token()
        # Direkt HTTP API cagir — event loop sorunlarini bypass et
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        with httpx.Client(timeout=10) as client:
            if len(text) > 4000:
                chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
                for chunk in chunks:
                    client.post(url, json={"chat_id": chat_id, "text": chunk})
            else:
                r = client.post(url, json={"chat_id": chat_id, "text": text})
                if not r.is_success:
                    log.error(f"[Telegram] API hatasi: {r.text}")
                    return False
        return True
    except Exception as e:
        log.error(f"[Telegram] send_message_sync hatasi: {e}")
        return False
