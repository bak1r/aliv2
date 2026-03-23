"""MCP Client — Ali v1'den temizlenmis versiyon.
JSON-RPC over HTTP ile remote FastMCP endpoint'lerine baglanir.
"""

from __future__ import annotations

import json
import time
import threading
import requests

from core.config import SETTINGS

_mcp_cfg = SETTINGS.get("mcp", {})
_TIMEOUT = _mcp_cfg.get("timeout", 25)
_MAX_RETRIES = _mcp_cfg.get("max_retries", 3)
_MIN_INTERVAL = _mcp_cfg.get("min_interval", 1.0)

# Session state
_sessions: dict[str, dict] = {}
_session_lock = threading.Lock()
_last_call: dict[str, float] = {}
_REQUEST_ID = 0
_id_lock = threading.Lock()


def _next_id() -> int:
    global _REQUEST_ID
    with _id_lock:
        _REQUEST_ID += 1
        return _REQUEST_ID


def _ensure_session(endpoint: str) -> str | None:
    """MCP session baslatilmamissa baslat."""
    with _session_lock:
        session = _sessions.get(endpoint)
        if session and session.get("initialized"):
            return session.get("session_id")

    # Initialize handshake
    payload = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "ali-v2", "version": "2.0.0"},
        },
    }

    try:
        resp = requests.post(
            endpoint, json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            timeout=_TIMEOUT,
        )
        if resp.status_code in (200, 202):
            session_id = resp.headers.get("Mcp-Session-Id")
            # Send initialized notification
            requests.post(
                endpoint,
                json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                headers={"Content-Type": "application/json", **({"Mcp-Session-Id": session_id} if session_id else {})},
                timeout=10,
            )
            with _session_lock:
                _sessions[endpoint] = {"session_id": session_id, "initialized": True}
            return session_id
    except Exception as e:
        print(f"[MCP] Initialize hatasi ({endpoint}): {e}")

    with _session_lock:
        _sessions[endpoint] = {"session_id": None, "initialized": True}
    return None


def _invalidate_session(endpoint: str):
    with _session_lock:
        _sessions[endpoint] = {"session_id": None, "initialized": False}


def call_mcp_tool(endpoint: str, tool_name: str, arguments: dict) -> str:
    """
    Remote MCP aracini cagir.
    Session yonetimi, retry, SSE parsing dahil.
    """
    # Rate limiting
    now = time.time()
    last = _last_call.get(endpoint, 0)
    if now - last < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - (now - last))
    _last_call[endpoint] = time.time()

    session_id = _ensure_session(endpoint)

    payload = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    last_error = ""

    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=_TIMEOUT)

            # Session expired
            if resp.status_code == 404:
                _invalidate_session(endpoint)
                session_id = _ensure_session(endpoint)
                if session_id:
                    headers["Mcp-Session-Id"] = session_id
                resp = requests.post(endpoint, json=payload, headers=headers, timeout=_TIMEOUT)

            # Server error → retry
            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                time.sleep(2 ** attempt)
                continue

            resp.raise_for_status()

            # Update session ID
            new_sid = resp.headers.get("Mcp-Session-Id")
            if new_sid and new_sid != session_id:
                with _session_lock:
                    _sessions[endpoint] = {"session_id": new_sid, "initialized": True}

            # Parse response
            content_type = resp.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                return _parse_sse(resp.text)

            return _extract_result(resp.json())

        except requests.exceptions.Timeout:
            last_error = "zaman asimi"
            time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            last_error = "baglanti hatasi"
            time.sleep(2 ** attempt)
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response else "?"
            return f"MCP hatasi: HTTP {code}"
        except Exception as e:
            return f"MCP arac hatasi: {e}"

    return f"MCP {_MAX_RETRIES} denemeden sonra yanitlamadi ({last_error})."


def _parse_sse(text: str) -> str:
    """SSE yanitini parse et."""
    results = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
                extracted = _extract_result(data)
                if extracted and not extracted.startswith("MCP"):
                    results.append(extracted)
            except json.JSONDecodeError:
                continue
    return "\n".join(results) if results else "Sonuc alinamadi."


def _extract_result(data: dict) -> str:
    """JSON-RPC yanitindan sonucu cikar."""
    if not isinstance(data, dict):
        return "Beklenmeyen yanit."

    if "error" in data:
        err = data["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return f"MCP hatasi: {msg}"

    result = data.get("result", {})
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list):
            texts = [item.get("text", "") for item in content
                     if isinstance(item, dict) and item.get("type") == "text"]
            if texts:
                return "\n".join(texts)
        if "text" in result:
            return result["text"]

    return str(result)[:3000] if result else "Sonuc bulunamadi."
