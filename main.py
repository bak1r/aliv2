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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ali")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI(title="Ali v2 — Avukat AI")

TEMPLATES = BASE_DIR / "web" / "templates"

# WebSocket clients
_ws_clients: set = set()

# Voice engine global ref
_voice_engine = None


async def broadcast_to_all(event_type: str, data: dict):
    """Tum WS client'lara event gonder."""
    if not _ws_clients:
        return
    msg = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
    dead = set()
    for ws in list(_ws_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


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
    except Exception:
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
                except Exception:
                    try:
                        r = await client.get(mevzuat_url)
                        mevzuat_ok = r.status_code < 500
                    except Exception:
                        pass
                try:
                    r = await client.get(yargi_url.replace("/mcp", "/health") if "/mcp" in yargi_url else yargi_url)
                    yargi_ok = r.status_code < 500
                except Exception:
                    try:
                        r = await client.get(yargi_url)
                        yargi_ok = r.status_code < 500
                    except Exception:
                        pass
        except Exception:
            pass
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

                # BUG 1 FIX: Fast-path for simple greetings — Claude API cagirmadan aninda yanit
                _fast = text.lower().strip()
                if _fast in ("selam", "merhaba", "hey", "naber", "nasilsin", "iyi gunler",
                             "iyi aksamlar", "gunaydin", "hosca kal", "gorusuruz",
                             "sagol", "tesekkurler", "tesekkur ederim", "eyvallah"):
                    _greetings = {
                        "selam": "Selam efendim, buyurun!",
                        "merhaba": "Merhaba efendim, nasil yardimci olabilirim?",
                        "hey": "Buyurun efendim!",
                        "naber": "Iyiyim efendim, siz nasilsiniz? Buyurun.",
                        "nasilsin": "Iyiyim efendim, tesekkurler. Sizin icin ne yapabilirim?",
                        "iyi gunler": "Size de iyi gunler efendim!",
                        "iyi aksamlar": "Iyi aksamlar efendim!",
                        "gunaydin": "Gunaydin efendim! Bugun ne yapalim?",
                        "hosca kal": "Hosca kalin efendim, iyi gunler!",
                        "gorusuruz": "Gorusuruz efendim, iyi gunler!",
                        "sagol": "Rica ederim efendim!",
                        "tesekkurler": "Rica ederim efendim, baska bir sey var mi?",
                        "tesekkur ederim": "Rica ederim efendim!",
                        "eyvallah": "Ne demek efendim!",
                    }
                    reply = _greetings.get(_fast, "Buyurun efendim!")
                    await ws.send_text(json.dumps({"type": "transcript", "data": {
                        "role": "ai", "text": reply, "model": "fast-path",
                        "domain": "genel", "tokens": 0, "latency_ms": 1,
                        "tools_used": [],
                    }}, ensure_ascii=False))
                    continue

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
    from core.voice import VoiceEngine
    from core.brain import think

    _voice_engine = VoiceEngine(brain_fn=think)
    _voice_engine.set_broadcast(broadcast_to_all)

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
        except Exception:
            pass
    finally:
        try:
            loop.close()
        except Exception:
            pass


def main():
    from core.config import SETTINGS, get_gemini_key, get_anthropic_key, get_telegram_token

    for d in ["data", "data/sessions", "data/documents", "data/screenshots"]:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)

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
                subprocess.run(f"for /f \"tokens=5\" %a in ('netstat -aon ^| findstr :{port}') do taskkill /PID %a /F", shell=True, capture_output=True)
            import time as _time
            _time.sleep(1)
    except Exception:
        pass

    # Telegram bot (varsa)
    if telegram_ok:
        try:
            from core.telegram import start_telegram_bot
            start_telegram_bot()
            print(f"  [Telegram] Bot baslatildi")
        except Exception as e:
            print(f"  [Telegram] Hata: {e}")

    # Ses motoru (varsa)
    if gemini_ok:
        voice_thread = threading.Thread(target=_start_voice_engine, daemon=True)
        voice_thread.start()
        print(f"  [Ses]      Motor baslatildi")

    # Tarayici ac
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()

    print(f"\n{'='*55}")
    print(f"  Web UI: http://127.0.0.1:{port}")
    print(f"  Kapatmak icin: Ctrl+C")
    print(f"{'='*55}\n")

    # Uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
