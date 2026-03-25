#!/usr/bin/env python3
"""
Ali v2 — Avukat AI Asistani
Web UI + Sesli Asistan + Telegram Bot
Prod-ready: tool state broadcasting, cost tracking, voice engine, notifications.
"""

import sys, os, json, time, asyncio, threading, webbrowser, logging
if sys.platform == "win32":
    os.system(""); sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# ─── Logging: Konsol + Dosya ───
_log_fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_log_datefmt = "%H:%M:%S"

# Konsol handler
logging.basicConfig(level=logging.INFO, format=_log_fmt, datefmt=_log_datefmt)

# Dosya handler — data/ali.log
_log_dir = BASE_DIR / "data"
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "ali.log"
try:
    from logging.handlers import RotatingFileHandler
    _fh = RotatingFileHandler(str(_log_file), maxBytes=10*1024*1024, backupCount=3, encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(_log_fmt, datefmt=_log_datefmt))
    logging.getLogger().addHandler(_fh)
except Exception as e:
    logging.warning(f"Log dosyasi olusturulamadi: {e}")

# Gürültülü kütüphaneleri sustur
for _noisy in ("httpx", "httpcore", "urllib3", "websockets.server"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

log = logging.getLogger("ali")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI(title="Ali v2 — Avukat AI")


@app.on_event("startup")
async def _capture_main_loop():
    global _main_loop
    _main_loop = asyncio.get_running_loop()

@app.on_event("startup")
async def _start_telegram_monitor():
    """Telethon User API monitörünü başlat (opsiyonel)."""
    try:
        tg_api_id = os.environ.get("TG_API_ID", "").strip()
        tg_api_hash = os.environ.get("TG_API_HASH", "").strip()
        if not tg_api_id or not tg_api_hash:
            return  # Yapılandırılmamış — atla

        from core.telegram_monitor import TelegramMonitor
        import core as core_module

        monitor = TelegramMonitor()
        core_module._telegram_monitor_instance = monitor

        # Broadcast fonksiyonu — web UI'a gönder
        async def _tg_broadcast(event_type, data):
            msg = json.dumps({"type": event_type, **data})
            for ws in list(_ws_clients):
                try:
                    await ws.send_text(msg)
                except Exception as e:
                    log.debug(f"WS broadcast: {e}")

        monitor.set_broadcast(_tg_broadcast)

        # Sesli bildirim — mention gelince voice engine'e bildir
        async def _on_mention(sender_name, chat_name, text_preview, reason):
            if _voice_engine:
                try:
                    await _voice_engine.inject_notification(
                        f"{sender_name}, {chat_name} sohbetinde sizi {reason}: {text_preview[:50]}"
                    )
                except Exception as e:
                    log.debug(f"Voice notification hatasi: {e}")

        monitor.set_on_mention(_on_mention)

        await monitor.start()
        log.info("[TG Monitor] Telethon monitör başlatıldı")
    except ImportError:
        log.debug("telethon yuklu degil, TG Monitor atlanıyor")
    except Exception as e:
        log.warning(f"[TG Monitor] Başlatılamadı: {e}")

TEMPLATES = BASE_DIR / "web" / "templates"

# WebSocket clients
_ws_clients: set = set()

# Voice engine global ref
_voice_engine = None

# Main event loop reference (for cross-thread broadcast from voice engine)
_main_loop: asyncio.AbstractEventLoop = None


async def broadcast_to_all(event_type: str, data: dict):
    """Tum WS client'lara event gonder."""
    if not _ws_clients:
        return
    msg = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
    dead = set()
    for ws in list(_ws_clients):
        try:
            await ws.send_text(msg)
        except Exception as e:
            log.debug(f"WS broadcast: {e}")
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def _voice_broadcast(event_type: str, data: dict):
    """Voice engine icin thread-safe broadcast wrapper.
    Voice engine ayri event loop'ta calisir, bu fonksiyon main loop'a schedule eder."""
    if _main_loop and _main_loop.is_running():
        # Fire-and-forget — voice loop'u bloklama
        asyncio.run_coroutine_threadsafe(broadcast_to_all(event_type, data), _main_loop)


@app.get("/")
async def index():
    p = TEMPLATES / "index.html"
    return HTMLResponse(p.read_text(encoding="utf-8")) if p.exists() else HTMLResponse("<h1>ALI v2</h1>")


@app.get("/health")
async def health():
    from tools import get_registry
    from core.config import SETTINGS
    r = get_registry()
    return JSONResponse({
        "status": "ok",
        "tools": list(r.keys()),
        "tool_count": len(r),
        "model": SETTINGS.get("brain", {}).get("model", ""),
    })


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)

    from tools import get_registry
    from core.config import SETTINGS, get_gemini_key, get_anthropic_key, get_telegram_token
    from core.brain import think, get_cost_summary

    registry = get_registry()
    model = SETTINGS.get("brain", {}).get("model", "")

    # Telegram durumu
    tg_active = False
    try:
        from core.telegram import is_running as tg_is_running
        tg_active = tg_is_running()
    except Exception as e:
        log.debug(f"Telegram durum kontrol hatasi: {e}")
        tg_active = bool(get_telegram_token())

    # ── Initial state sync ────────────────────────────────────────
    await ws.send_text(json.dumps({"type": "state_sync", "data": {
        "tools": list(registry.keys()),
        "model": model,
        "connected": True,
        "voice_active": bool(get_gemini_key()),
        "telegram_active": tg_active,
        "db_active": False,
    }}, ensure_ascii=False))

    # Welcome note
    features = []
    if get_anthropic_key(): features.append("Claude Beyin")
    if get_gemini_key(): features.append("Ses Motoru")
    if tg_active: features.append("Telegram")
    feat_str = " + ".join(features) if features else "Temel"

    await ws.send_text(json.dumps({"type": "note", "data": {
        "text": f"Ali v2 hazir — {len(registry)} arac, {feat_str} aktif.",
        "priority": "normal"
    }}, ensure_ascii=False))

    # API durumu
    await ws.send_text(json.dumps({"type": "env_status", "data": {
        "anthropic": bool(get_anthropic_key()),
    }}, ensure_ascii=False))

    # Daemon durumu
    await ws.send_text(json.dumps({"type": "daemon_status", "data": {
        "web": "ok",
        "voice": "ok" if get_gemini_key() else "down",
        "telegram": "ok" if tg_active else "down",
    }}, ensure_ascii=False))

    # BUG 5 FIX: MCP health check — ping endpoints and update UI
    async def _check_mcp():
        import httpx
        mcp_cfg = SETTINGS.get("mcp", {})
        mevzuat_url = mcp_cfg.get("mevzuat_endpoint", "https://mevzuat.surucu.dev/mcp")
        yargi_url = mcp_cfg.get("yargi_endpoint", "https://yargimcp.fastmcp.app/mcp")
        mevzuat_ok = False
        yargi_ok = False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    r = await client.get(mevzuat_url.replace("/mcp", "/health") if "/mcp" in mevzuat_url else mevzuat_url)
                    mevzuat_ok = r.status_code < 500
                except Exception as e:
                    log.debug(f"MCP health check (mevzuat/health): {e}")
                    try:
                        r = await client.get(mevzuat_url)
                        mevzuat_ok = r.status_code < 500
                    except Exception as e2:
                        log.debug(f"MCP health check (mevzuat): {e2}")
                try:
                    r = await client.get(yargi_url.replace("/mcp", "/health") if "/mcp" in yargi_url else yargi_url)
                    yargi_ok = r.status_code < 500
                except Exception as e:
                    log.debug(f"MCP health check (yargi/health): {e}")
                    try:
                        r = await client.get(yargi_url)
                        # 405 = servis var, GET desteklemiyor ama çalışıyor
                        yargi_ok = r.status_code in (200, 405)
                    except Exception as e2:
                        log.debug(f"MCP health check (yargi): {e2}")
        except Exception as e:
            log.debug(f"MCP health check hatasi: {e}")
        # Send MCP status to UI — hDb = Mevzuat MCP, hTg = Yargi MCP in the health widget
        await ws.send_text(json.dumps({"type": "daemon_status", "data": {
            "database": "ok" if mevzuat_ok else "down",
        }}, ensure_ascii=False))
        # For Yargi MCP we update via env_status since hTg is used for Telegram daemon
        # Use a separate mcp_status event
        await ws.send_text(json.dumps({"type": "mcp_status", "data": {
            "mevzuat": "ok" if mevzuat_ok else "down",
            "yargi": "ok" if yargi_ok else "down",
        }}, ensure_ascii=False))

    asyncio.ensure_future(_check_mcp())

    # ── Message loop ──────────────────────────────────────────────
    try:
        while True:
            data = await ws.receive_text()
            if len(data) > 10240:
                continue
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", "message")

            if action == "cancel" or (action == "message" and msg.get("text", "").strip().lower() in ("dur", "iptal", "kes", "sus")):
                from core.brain import request_cancel
                request_cancel()
                await ws.send_text(json.dumps({"type": "thinking", "data": {"active": False}}, ensure_ascii=False))
                await ws.send_text(json.dumps({"type": "transcript", "data": {
                    "role": "ai", "text": "Durdurdum efendim. Başka bir şey var mı?"
                }}, ensure_ascii=False))
                continue

            if action == "message":
                text = msg.get("text", "").strip()
                if not text:
                    continue

                # BUG 2 FIX: User mesajini geri gonderme — client sendMessage() zaten gosteriyor
                # Sadece sesli giris icin voice engine kendi transcript'ini gonderir

                # Thinking basladi
                await ws.send_text(json.dumps({"type": "thinking", "data": {
                    "active": True, "text": text
                }}, ensure_ascii=False))

                try:
                    loop = asyncio.get_running_loop()
                    t0 = time.time()
                    tools_used = []

                    # Tool state callbacks
                    def on_tool_start(name, inp):
                        tools_used.append(name)
                        asyncio.run_coroutine_threadsafe(
                            ws.send_text(json.dumps({"type": "tool_state", "data": {
                                "name": name, "state": "running"
                            }}, ensure_ascii=False)),
                            loop
                        )

                    def on_tool_end(name, result_preview, elapsed):
                        asyncio.run_coroutine_threadsafe(
                            ws.send_text(json.dumps({"type": "tool_state", "data": {
                                "name": name, "state": "done"
                            }}, ensure_ascii=False)),
                            loop
                        )
                        # not_al araci kullanildiysa UI'a note event'i gonder
                        if name == "not_al" and result_preview:
                            # BUG 6 FIX: Silme islemi ise notes panelini temizle
                            if "silindi" in result_preview.lower() or "temizlendi" in result_preview.lower():
                                asyncio.run_coroutine_threadsafe(
                                    broadcast_to_all("notes_clear", {}),
                                    loop
                                )
                            asyncio.run_coroutine_threadsafe(
                                broadcast_to_all("note", {
                                    "text": result_preview,
                                    "priority": "normal",
                                    "source": "not_al",
                                }),
                                loop
                            )

                    response = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: think(
                            user_message=text,
                            on_tool_start=on_tool_start,
                            on_tool_end=on_tool_end,
                        )),
                        timeout=90.0,
                    )

                    elapsed = int((time.time() - t0) * 1000)
                    cost = get_cost_summary()

                    # Cost hesapla (Sonnet: $3/$15 per 1M tokens)
                    session_cost = (cost["input_tokens"] * 3 + cost["output_tokens"] * 15) / 1_000_000
                    today_cost = (cost["today_input"] * 3 + cost["today_output"] * 15) / 1_000_000

                    # Legal domain algila
                    from core.brain import _detect_legal_query
                    is_legal = _detect_legal_query(text)

                    # Events gonder
                    await ws.send_text(json.dumps({"type": "thinking", "data": {"active": False}}, ensure_ascii=False))
                    await ws.send_text(json.dumps({"type": "cost", "data": {
                        "today": today_cost, "total": session_cost
                    }}, ensure_ascii=False))

                    await ws.send_text(json.dumps({"type": "transcript", "data": {
                        "role": "ai",
                        "text": response,
                        "model": model,
                        "domain": "hukuk" if is_legal else "genel",
                        "tokens": cost.get("input_tokens", 0) + cost.get("output_tokens", 0),
                        "latency_ms": elapsed,
                        "tools_used": tools_used,
                    }}, ensure_ascii=False))

                except asyncio.TimeoutError:
                    await ws.send_text(json.dumps({"type": "thinking", "data": {"active": False}}, ensure_ascii=False))
                    await ws.send_text(json.dumps({"type": "transcript", "data": {
                        "role": "system", "text": "Zaman asimi (90s). Lutfen tekrar deneyin."
                    }}, ensure_ascii=False))

                except Exception as e:
                    log.error(f"Brain hatasi: {e}")
                    await ws.send_text(json.dumps({"type": "thinking", "data": {"active": False}}, ensure_ascii=False))
                    await ws.send_text(json.dumps({"type": "transcript", "data": {
                        "role": "system", "text": f"Hata: {e}"
                    }}, ensure_ascii=False))

            elif action == "request_state":
                await ws.send_text(json.dumps({"type": "state_sync", "data": {
                    "tools": list(registry.keys()), "connected": True
                }}))

            elif action == "mic_mute":
                if _voice_engine:
                    _voice_engine.mic_muted = not _voice_engine.mic_muted
                    await broadcast_to_all("mic_mute", {"muted": _voice_engine.mic_muted})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"WS hatasi: {e}")
        import traceback; traceback.print_exc()
    finally:
        _ws_clients.discard(ws)


def _start_voice_engine():
    """Ses motorunu ayri thread'de baslat."""
    global _voice_engine

    # Wait for uvicorn to start and set _main_loop
    for _ in range(30):  # Max 30 seconds
        if _main_loop is not None:
            break
        time.sleep(1)
    if _main_loop is None:
        log.error("Main event loop not available — voice broadcast disabled")

    from core.voice import VoiceEngine
    from core.brain import think

    _voice_engine = VoiceEngine(brain_fn=think)
    _voice_engine.set_broadcast(_voice_broadcast)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_voice_engine.start())
    except Exception as e:
        log.error(f"Ses motoru hatasi: {e}")
        # Broadcast voice down status to UI
        try:
            loop.run_until_complete(broadcast_to_all("daemon_status", {"voice": "down"}))
            error_msg = str(e)
            if "1008" in error_msg:
                loop.run_until_complete(broadcast_to_all("note", {
                    "text": "Sesli asistan kullanilamiyor (1008). Yazarak devam edebilirsiniz.",
                    "priority": "urgent"
                }))
        except Exception as e:
            log.debug(f"Voice cleanup broadcast hatasi: {e}")
    finally:
        try:
            loop.close()
        except Exception as e:
            log.debug(f"Voice cleanup: {e}")


def main():
    from core.config import SETTINGS, get_gemini_key, get_anthropic_key, get_telegram_token

    for d in ["data", "data/sessions", "data/documents", "data/screenshots"]:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)

    # Telemetry — başlatma bildirimi
    try:
        from core.telemetry import report_startup
        report_startup()
    except Exception as e:
        log.debug(f"Telemetry startup hatasi: {e}")

    print(f"\n{'='*55}")
    print(f"  ALI v2 — Avukat AI Asistani (Prod Ready)")
    print(f"{'='*55}\n")

    from tools import get_registry
    registry = get_registry()

    gemini_ok = bool(get_gemini_key())
    anthropic_ok = bool(get_anthropic_key())
    telegram_ok = bool(get_telegram_token())

    print(f"  [Claude]   {'AKTIF' if anthropic_ok else 'YOK — .env kontrol edin'}")
    print(f"  [Gemini]   {'AKTIF — Sesli asistan hazir' if gemini_ok else 'YOK'}")
    print(f"  [Telegram] {'AKTIF' if telegram_ok else 'YOK — .env TELEGRAM_BOT_TOKEN ekleyin'}")
    print(f"  [Araclar]  {len(registry)} adet")

    port = SETTINGS.get("web_ui_port", 8420)

    # Port meşgulse önceki processi kapat
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        if result == 0:
            log.info(f"Port {port} mesgul, onceki process kapatiliyor...")
            import subprocess
            if sys.platform == "darwin" or sys.platform == "linux":
                subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True, capture_output=True)
            elif sys.platform == "win32":
                try:
                    import psutil
                    for conn in psutil.net_connections():
                        if conn.laddr.port == port and conn.pid:
                            psutil.Process(conn.pid).kill()
                except Exception as e:
                    log.debug(f"psutil port cleanup hatasi: {e}")
                    try:
                        result = subprocess.run(f"netstat -aon | findstr :{port}", shell=True, capture_output=True, text=True)
                        for line in result.stdout.strip().split('\n'):
                            parts = line.strip().split()
                            if len(parts) >= 5 and parts[-1].isdigit() and int(parts[-1]) > 0:
                                subprocess.run(f"taskkill /PID {parts[-1]} /F", shell=True, capture_output=True)
                    except Exception as e2:
                        log.debug(f"netstat fallback hatasi: {e2}")
            import time as _time
            _time.sleep(1)
    except Exception as e:
        log.debug(f"Port kontrol hatasi: {e}")

    # Telegram bot (varsa)
    if telegram_ok:
        try:
            from core.telegram import start_telegram_bot
            start_telegram_bot()
            log.info("[Telegram] Bot baslatildi")
        except Exception as e:
            log.warning(f"[Telegram] Hata: {e}")

    # Ses motoru (varsa)
    if gemini_ok:
        voice_thread = threading.Thread(target=_start_voice_engine, daemon=True)
        voice_thread.start()
        log.info("[Ses] Motor baslatildi")

    # Tarayıcı otomatik açılmasın — kullanıcı Electron app veya kendi tarayıcısını kullanır
    # if not os.environ.get("ALI_ELECTRON"):
    #     threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    print(f"\n{'='*55}")
    print(f"  Web UI: http://127.0.0.1:{port}")
    print(f"  Kapatmak icin: Ctrl+C")
    print(f"{'='*55}\n")

    # Uvicorn
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        try:
            from core.telemetry import report_shutdown
            report_shutdown("normal")
        except Exception as e:
            log.debug(f"Telemetry shutdown hatasi: {e}")


if __name__ == "__main__":
    main()
