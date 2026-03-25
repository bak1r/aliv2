"""Merkezi konfigürasyon yonetimi."""

from __future__ import annotations

import json
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

# .env yukle
load_dotenv(str(BASE_DIR / ".env"), override=True)


def _load_settings() -> dict:
    """settings.json oku."""
    path = CONFIG_DIR / "settings.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


SETTINGS = _load_settings()


def get_gemini_key() -> str | None:
    """Gemini API key: .env oncelikli, sonra api_keys.json."""
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if key:
        return key
    keys_file = CONFIG_DIR / "api_keys.json"
    if keys_file.exists():
        try:
            data = json.loads(keys_file.read_text(encoding="utf-8"))
            return data.get("gemini_api_key")
        except Exception:
            pass
    return None


def get_anthropic_key() -> str | None:
    """Anthropic API key: .env'den."""
    return os.environ.get("ANTHROPIC_API_KEY", "").strip() or None


def save_api_keys(gemini_key: str = "", anthropic_key: str = ""):
    """API anahtarlarini .env dosyasina kaydet."""
    env_path = BASE_DIR / ".env"
    lines = []
    if gemini_key:
        lines.append(f"GOOGLE_API_KEY={gemini_key.strip()}")
        os.environ["GOOGLE_API_KEY"] = gemini_key.strip()
    if anthropic_key:
        lines.append(f"ANTHROPIC_API_KEY={anthropic_key.strip()}")
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key.strip()

    # Mevcut .env varsa guncelle
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    if gemini_key:
        existing["GOOGLE_API_KEY"] = gemini_key.strip()
    if anthropic_key:
        existing["ANTHROPIC_API_KEY"] = anthropic_key.strip()

    env_path.write_text(
        "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
        encoding="utf-8"
    )


def get_telegram_token() -> str | None:
    """Telegram Bot API token: .env'den."""
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or None


def get_tg_api_id() -> str | None:
    """Telegram User API ID (Telethon icin)."""
    return os.environ.get("TG_API_ID", "").strip() or None


def get_tg_api_hash() -> str | None:
    """Telegram User API Hash (Telethon icin)."""
    return os.environ.get("TG_API_HASH", "").strip() or None


def get_tg_phone() -> str | None:
    """Telegram telefon numarasi (Telethon icin)."""
    return os.environ.get("TG_PHONE", "").strip() or None


def is_configured() -> bool:
    """API key'ler ayarlanmis mi?"""
    gemini = get_gemini_key()
    anthropic = get_anthropic_key()
    return bool(gemini and len(gemini) > 15 and anthropic and len(anthropic) > 15)
