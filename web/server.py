"""Ali v2 — FastAPI Web Server
WebSocket ile real-time state broadcasting.
"""

from __future__ import annotations

import json
import time
import asyncio
import logging
import threading
from pathlib import Path
from typing import Set

log = logging.getLogger("ali.web")

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

# Connected WebSocket clients
_clients: Set = set()

# Global app reference
_app = None


async def broadcast(event_type: str, data: dict):
    """Tum WebSocket client'lara event gonder."""
    if not _clients:
        return
    msg = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
    dead = set()
    for ws in list(_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    if dead:
        _clients.difference_update(dead)


def get_app():
    """Singleton FastAPI app dondur."""
    global _app
    if _app is not None:
        return _app

    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse

    _app = FastAPI(title="Ali v2", version="2.0.0")

    @_app.get("/")
    async def index():
        index_path = _TEMPLATES_DIR / "index.html"
        if index_path.exists():
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>ALI v2</h1><p>Web UI bulunamadi.</p>")

    @_app.get("/health")
    async def health():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from tools import get_registry
        from core.config import SETTINGS
        registry = get_registry()
        return JSONResponse({
            "status": "ok",
            "tools": list(registry.keys()),
            "tool_count": len(registry),
            "model": SETTINGS.get("brain", {}).get("model", "unknown"),
        })

    @_app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        _clients.add(ws)
        log.info(f"WebSocket baglandi. Toplam: {len(_clients)}")

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tools import get_registry
            from core.config import SETTINGS, get_anthropic_key, get_gemini_key, get_telegram_token
            from core.brain import think, get_cost_summary

            # Initial state sync
            registry = get_registry()
            tool_names = list(registry.keys())
            model = SETTINGS.get("brain", {}).get("model", "")

            # Telegram durumunu kontrol et
            _tg_active = False
            try:
                from core.telegram import is_running as tg_is_running
                _tg_active = tg_is_running()
            except ImportError:
                _tg_active = False

            await ws.send_text(json.dumps({
                "type": "state_sync",
                "data": {
                    "tools": tool_names,
                    "model": model,
                    "connected": True,
                    "voice_active": bool(get_gemini_key()),
                    "telegram_active": _tg_active or bool(get_telegram_token()),
                    "db_active": False,
                }
            }, ensure_ascii=False))

            # Welcome note
            await ws.send_text(json.dumps({
                "type": "note",
                "data": {"text": f"Ali v2 hazir. {len(tool_names)} arac yuklendi.", "priority": "normal"}
            }, ensure_ascii=False))

            # API status
            if get_anthropic_key():
                await ws.send_text(json.dumps({
                    "type": "env_status",
                    "data": {"anthropic": True}
                }, ensure_ascii=False))

            # Main message loop
            while True:
                data = await ws.receive_text()
                if len(data) > 10240:
                    continue

                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    continue

                action = msg.get("action", "message")

                if action == "message":
                    user_text = msg.get("text", "").strip()
                    if not user_text:
                        continue

                    # User message
                    await ws.send_text(json.dumps({
                        "type": "transcript",
                        "data": {"role": "user", "text": user_text}
                    }, ensure_ascii=False))

                    # Thinking
                    await ws.send_text(json.dumps({
                        "type": "thinking",
                        "data": {"active": True, "text": user_text}
                    }, ensure_ascii=False))

                    try:
                        loop = asyncio.get_running_loop()
                        t0 = time.time()

                        response = await asyncio.wait_for(
                            loop.run_in_executor(None, lambda: think(user_message=user_text)),
                            timeout=60.0,
                        )

                        elapsed = int((time.time() - t0) * 1000)
                        cost = get_cost_summary()
                        total_cost = (cost["input_tokens"] * 3 + cost["output_tokens"] * 15) / 1_000_000

                        # Thinking done
                        await ws.send_text(json.dumps({
                            "type": "thinking", "data": {"active": False}
                        }, ensure_ascii=False))

                        # Cost
                        await ws.send_text(json.dumps({
                            "type": "cost", "data": {"today": total_cost, "total": total_cost}
                        }, ensure_ascii=False))

                        # Response
                        is_legal = any(w in user_text.lower() for w in ["dava", "kanun", "madde", "tck", "cmk", "mahkeme", "savunma", "mevzuat"])
                        await ws.send_text(json.dumps({
                            "type": "transcript",
                            "data": {
                                "role": "ai",
                                "text": response,
                                "model": model,
                                "domain": "hukuk" if is_legal else "genel",
                                "tokens": cost.get("input_tokens", 0) + cost.get("output_tokens", 0),
                                "latency_ms": elapsed,
                                "tools_used": [],
                            }
                        }, ensure_ascii=False))

                    except asyncio.TimeoutError:
                        await ws.send_text(json.dumps({
                            "type": "thinking", "data": {"active": False}
                        }, ensure_ascii=False))
                        await ws.send_text(json.dumps({
                            "type": "transcript", "data": {"role": "system", "text": "Zaman asimi (60s)."}
                        }, ensure_ascii=False))

                    except Exception as e:
                        await ws.send_text(json.dumps({
                            "type": "thinking", "data": {"active": False}
                        }, ensure_ascii=False))
                        await ws.send_text(json.dumps({
                            "type": "transcript", "data": {"role": "system", "text": f"Hata: {e}"}
                        }, ensure_ascii=False))

                elif action == "request_calendar":
                    try:
                        from core.database import get_db
                        db = get_db()
                        hearings = db.yaklasan_durusmalar(gun=30)
                        notes = db.not_listele()
                        await ws.send_text(json.dumps({
                            "type": "calendar_data",
                            "data": {
                                "hearings": hearings,
                                "notes": [{"id": n.get("id"), "text": n.get("metin", ""), "tag": n.get("etiket", "normal"), "date": n.get("created_at", "")} for n in notes]
                            }
                        }, ensure_ascii=False))
                    except Exception as e:
                        log.error(f"Calendar data hatasi: {e}")
                        await ws.send_text(json.dumps({
                            "type": "calendar_data",
                            "data": {"hearings": [], "notes": []}
                        }, ensure_ascii=False))

                elif action == "request_state":
                    registry = get_registry()
                    await ws.send_text(json.dumps({
                        "type": "state_sync",
                        "data": {"tools": list(registry.keys()), "connected": True}
                    }))

        except WebSocketDisconnect:
            pass
        except Exception as e:
            log.error(f"WebSocket hatasi: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _clients.discard(ws)
            log.info(f"WebSocket ayrildi. Toplam: {len(_clients)}")

    return _app


def start_server(port: int = None):
    """Web server'i arka plan thread'inde baslat."""
    from core.config import SETTINGS
    if port is None:
        port = SETTINGS.get("web_ui_port", 8420)

    import uvicorn

    app = get_app()

    def _run():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    print(f"[Web] UI basladi: http://127.0.0.1:{port}")
    return thread
