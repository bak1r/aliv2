"""Ali v2 — Kalici Hafiza / Ruh Sistemi
Kullaniciyi zaman icinde taniyan, kisisel baglamli asistan.
Thread-safe JSON depolama, otomatik hafiza cikarimi ve enjeksiyonu.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Optional

from core.config import DATA_DIR

# ── Ayarlar ──────────────────────────────────────────────────────────
MEMORY_FILE = DATA_DIR / "memory.json"
MAX_PER_CATEGORY = 100
MAX_CONTEXT_CHARS = 1500  # ~500 token
CATEGORIES = ("identity", "relationships", "cases", "preferences", "notes", "patterns")

# ── Thread-safe kilit ────────────────────────────────────────────────
_mem_lock = Lock()

# ── In-memory cache ──────────────────────────────────────────────────
_memory_cache: Optional[dict] = None


# ── Dosya I/O ────────────────────────────────────────────────────────
def _empty_memory() -> dict:
    """Bos hafiza yapisi."""
    return {cat: [] for cat in CATEGORIES}


def _load_memory() -> dict:
    """Hafiza dosyasini oku. Bozuksa sifirdan basla."""
    global _memory_cache
    if _memory_cache is not None:
        return _memory_cache
    try:
        if MEMORY_FILE.exists():
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            # Yapı dogrulama
            if not isinstance(data, dict):
                raise ValueError("Gecersiz hafiza formati")
            for cat in CATEGORIES:
                if cat not in data or not isinstance(data[cat], list):
                    data[cat] = []
            _memory_cache = data
            return data
    except Exception as e:
        print(f"[Hafiza] Dosya okunamadi, sifirdan basliyor: {e}")
    _memory_cache = _empty_memory()
    return _memory_cache


def _save_memory(data: dict):
    """Hafizayi diske kaydet."""
    global _memory_cache
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _memory_cache = data
    except Exception as e:
        print(f"[Hafiza] Kayit hatasi: {e}")


# ── Hafiza ekleme ────────────────────────────────────────────────────
def _add_memory(category: str, key: str, value: str, confidence: float = 0.8):
    """Bir hatira ekle veya guncelle. Thread-safe."""
    if category not in CATEGORIES:
        return

    with _mem_lock:
        data = _load_memory()
        entries = data[category]

        # Ayni key varsa guncelle
        for entry in entries:
            if entry.get("key") == key:
                entry["value"] = value
                entry["confidence"] = max(entry.get("confidence", 0), confidence)
                entry["updated"] = datetime.now().isoformat()
                entry["hits"] = entry.get("hits", 0) + 1
                _save_memory(data)
                return

        # Yeni kayit
        entries.append({
            "key": key,
            "value": value,
            "confidence": confidence,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "hits": 1,
        })

        # Kapasite asildiysa en eski ve dusuk confidence olani sil
        if len(entries) > MAX_PER_CATEGORY:
            entries.sort(key=lambda e: (e.get("confidence", 0), e.get("updated", "")))
            data[category] = entries[-MAX_PER_CATEGORY:]

        _save_memory(data)


# ── Hafiza cikarimi desenleri ────────────────────────────────────────
_IDENTITY_PATTERNS = [
    # "benim adim X", "adim X", "ben X"
    (r"(?:benim\s+)?ad[iı]m\s+(\w+)", "isim"),
    (r"ben\s+(\w+)\s+(?:bey|han[iı]m)", "isim"),
    # "ben avukatim", "meslegim avukat"
    (r"ben\s+(?:bir\s+)?(\w+(?:\s+\w+)?)\s*(?:[iı]m|y[iı]m)", "meslek"),
    (r"mesle[gğ]im\s+(\w+)", "meslek"),
    # "X yasindayim"
    (r"(\d+)\s+ya[sş][iı]nday[iı]m", "yas"),
    # "X bey/hanim", "sayin X"
    (r"(?:say[iı]n|saygideger)\s+(\w+\s*\w*)", "unvan"),
]

_RELATIONSHIP_PATTERNS = [
    # "X bey muvekkilim", "muvekkilim X"
    (r"(\w+(?:\s+\w+)?)\s+(?:bey|han[iı]m)\s+m[uü]vekkilim", "muvekkil"),
    (r"m[uü]vekkilim\s+(\w+(?:\s+\w+)?)", "muvekkil"),
    # "hakim X", "savci X"
    (r"(?:hakim|yarg[iı][cç])\s+(\w+(?:\s+\w+)?)", "hakim"),
    (r"(?:savc[iı])\s+(\w+(?:\s+\w+)?)", "savci"),
    # "X avukat", "meslektasim X"
    (r"meslekta[sş][iı]m\s+(\w+(?:\s+\w+)?)", "meslektas"),
]

_CASE_PATTERNS = [
    # "2024/123 dosya", "dosya no 2024/123"
    (r"(\d{4}/\d+)\s+(?:dosya|esas|karar)", "dosya_no"),
    (r"dosya\s+(?:no|numaras[iı])\s*:?\s*(\d{4}/\d+)", "dosya_no"),
    # "X davasi", "X dosyasini takip et"
    (r"(\w+(?:\s+\w+){0,3})\s+davas[iı]", "dava"),
    (r"(\w+(?:\s+\w+){0,3})\s+dosyas[iı]n[iı]\s+takip", "takip"),
]

_PREFERENCE_PATTERNS = [
    # "kisa cevap ver", "kisaca"
    (r"(?:k[iı]sa(?:ca)?|[oö]z(?:et)?)\s+(?:cevap|yan[iı]t)\s+ver", "uzunluk", "kisa"),
    # "resmi dilde yaz", "samimi ol"
    (r"resmi\s+dil(?:de)?\s+(?:yaz|kullan)", "uslup", "resmi"),
    (r"samimi\s+(?:ol|yaz|konuş)", "uslup", "samimi"),
    # "turkce yaz", "ingilizce cevap ver"
    (r"(t[uü]rk[cç]e|ingilizce|[iı]ngilizce)\s+(?:yaz|cevap|yan[iı]t)", "dil", None),
    # "madde madde yaz"
    (r"madde\s+madde\s+(?:yaz|s[iı]rala)", "format", "madde_madde"),
    # "emoji kullanma"
    (r"emoji\s+kullanma", "emoji", "yok"),
]

_NOTE_PATTERNS = [
    # "bunu hatirla", "not al", "aklinda tut", "unutma"
    (r"(?:bunu\s+)?(?:hat[iı]rla|akl[iı]nda\s+tut|unutma)\s*:?\s*(.+)", "hatirlatma"),
    (r"(?:su(?:nu)?|bunu)\s+not\s+(?:al|et)\s*:?\s*(.+)", "not"),
]


def extract_memories(user_message: str, ai_response: str = ""):
    """Kullanici mesajindan ve AI yanitindan hafiza cikart.
    Bu fonksiyon arka plan thread'inde calistirilmali."""
    msg = user_message.lower().strip()

    # ── Kimlik bilgileri ──
    for pattern, key in _IDENTITY_PATTERNS:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            value = m.group(1).strip().title()
            if len(value) > 1:
                _add_memory("identity", key, value, confidence=0.9)

    # ── Iliskiler ──
    for pattern, key in _RELATIONSHIP_PATTERNS:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            value = m.group(1).strip().title()
            if len(value) > 1:
                _add_memory("relationships", f"{key}:{value}", value, confidence=0.85)

    # ── Dava/dosya bilgileri ──
    for pattern, key in _CASE_PATTERNS:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            if len(value) > 1:
                _add_memory("cases", f"{key}:{value}", value, confidence=0.85)

    # ── Tercihler ──
    for item in _PREFERENCE_PATTERNS:
        pattern, key = item[0], item[1]
        default_val = item[2] if len(item) > 2 else None
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            value = default_val or m.group(1).strip().lower()
            _add_memory("preferences", key, value, confidence=0.9)

    # ── Notlar / hatirlatmalar ──
    for pattern, key in _NOTE_PATTERNS:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            value = m.group(1).strip()
            if len(value) > 3:
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                _add_memory("notes", f"{key}:{ts}", value, confidence=1.0)

    # ── Arac kullanim desenleri (AI yanitindan) ──
    if ai_response:
        # Yaygin arac isimleri tespit et
        tool_mentions = re.findall(
            r"(?:mevzuat_ara|yargi_ara|bilgi_bankasi|belge_olustur|ceza_hesapla|"
            r"sure_hesapla|dava_analiz|not_al|zaman_takip|durusma_takvimi|muvekil_takip)",
            ai_response.lower(),
        )
        for tool_name in set(tool_mentions):
            _add_memory("patterns", f"arac:{tool_name}", tool_name, confidence=0.5)


def extract_memories_async(user_message: str, ai_response: str = ""):
    """Hafiza cikarimini arka plan thread'inde calistir."""
    t = Thread(
        target=extract_memories,
        args=(user_message, ai_response),
        daemon=True,
        name="memory-extract",
    )
    t.start()


# ── Hafiza enjeksiyonu ───────────────────────────────────────────────
def get_memory_context() -> str:
    """Sistem promptuna enjekte edilecek hafiza baglami olustur.
    En guncel ve yuksek guvenli hatiralari onceliklendirir.
    Maksimum ~500 token (1500 karakter) cikarir."""
    with _mem_lock:
        data = _load_memory()

    sections = []

    # ── Kimlik ──
    identity_items = sorted(
        data.get("identity", []),
        key=lambda e: (e.get("confidence", 0), e.get("updated", "")),
        reverse=True,
    )
    if identity_items:
        parts = []
        for item in identity_items[:5]:
            parts.append(f"- {item['key']}: {item['value']}")
        sections.append("KULLANICI BILGILERI:\n" + "\n".join(parts))

    # ── Tercihler ──
    pref_items = sorted(
        data.get("preferences", []),
        key=lambda e: (e.get("confidence", 0), e.get("updated", "")),
        reverse=True,
    )
    if pref_items:
        parts = []
        for item in pref_items[:5]:
            parts.append(f"- {item['key']}: {item['value']}")
        sections.append("TERCIHLER:\n" + "\n".join(parts))

    # ── Iliskiler ──
    rel_items = sorted(
        data.get("relationships", []),
        key=lambda e: e.get("updated", ""),
        reverse=True,
    )
    if rel_items:
        parts = []
        for item in rel_items[:5]:
            kind = item["key"].split(":")[0] if ":" in item["key"] else ""
            parts.append(f"- {kind}: {item['value']}")
        sections.append("ILISKILER:\n" + "\n".join(parts))

    # ── Aktif davalar ──
    case_items = sorted(
        data.get("cases", []),
        key=lambda e: e.get("updated", ""),
        reverse=True,
    )
    if case_items:
        parts = []
        for item in case_items[:5]:
            kind = item["key"].split(":")[0] if ":" in item["key"] else ""
            parts.append(f"- {kind}: {item['value']}")
        sections.append("AKTIF DAVALAR/DOSYALAR:\n" + "\n".join(parts))

    # ── Notlar ──
    note_items = sorted(
        data.get("notes", []),
        key=lambda e: e.get("updated", ""),
        reverse=True,
    )
    if note_items:
        parts = []
        for item in note_items[:3]:
            parts.append(f"- {item['value']}")
        sections.append("HATIRLATMALAR:\n" + "\n".join(parts))

    if not sections:
        return ""

    result = "\n\n".join(sections)

    # Uzunluk siniri
    if len(result) > MAX_CONTEXT_CHARS:
        result = result[:MAX_CONTEXT_CHARS].rsplit("\n", 1)[0] + "\n..."

    return result


def get_user_name() -> str:
    """Hafizadan kullanici adini dondur (varsa)."""
    with _mem_lock:
        data = _load_memory()
    for entry in data.get("identity", []):
        if entry.get("key") == "isim":
            return entry["value"]
    return ""


# ── Yonetim fonksiyonlari ────────────────────────────────────────────
def get_all_memories() -> dict:
    """Tum hafizayi dondur (debug/UI icin)."""
    with _mem_lock:
        return _load_memory().copy()


def clear_all_memories():
    """Tum hafizayi sil."""
    with _mem_lock:
        data = _empty_memory()
        _save_memory(data)
    print("[Hafiza] Tum hafiza silindi.")


def forget(category: str, key: str) -> bool:
    """Belirli bir hatirayi sil."""
    with _mem_lock:
        data = _load_memory()
        if category not in data:
            return False
        before = len(data[category])
        data[category] = [e for e in data[category] if e.get("key") != key]
        if len(data[category]) < before:
            _save_memory(data)
            return True
    return False


def memory_stats() -> dict:
    """Hafiza istatistikleri."""
    with _mem_lock:
        data = _load_memory()
    stats = {}
    total = 0
    for cat in CATEGORIES:
        count = len(data.get(cat, []))
        stats[cat] = count
        total += count
    stats["toplam"] = total
    return stats
