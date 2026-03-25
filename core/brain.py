"""Ali v2 — Beyin (Claude API Entegrasyonu)
Tek model, tek prompt, temiz arac dongusu.
v2.1: Streaming, tool state callbacks, retry logic, context-aware routing, cost tracking.
"""

from __future__ import annotations

import time
import re
import random
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import date
from typing import Callable, Optional

import logging

import anthropic

from core.config import get_anthropic_key, SETTINGS

log = logging.getLogger("ali.brain")

# Telemetry — kritik hataları Telegram'a bildir
def _report_error(source, error, context="", severity="ERROR"):
    try:
        from core.telemetry import report
        report(source, error, context=context, severity=severity)
    except Exception:
        pass

from core.prompt import build_claude_prompt
from core.memory import extract_memories_async, get_memory_context, get_user_name
from tools import get_claude_tool_definitions, get_tool

# ── Ayarlar ──────────────────────────────────────────────────────────
_brain_cfg = SETTINGS.get("brain", {})
MODEL = _brain_cfg.get("model", "claude-sonnet-4-20250514")
MAX_TOKENS = _brain_cfg.get("max_tokens", 4096)
MAX_TOOL_ROUNDS = _brain_cfg.get("max_tool_rounds", 4)
MAX_HISTORY = _brain_cfg.get("max_history", 10)
TEMPERATURE = _brain_cfg.get("temperature", 0.3)

# Retry ayarlari
MAX_RETRIES = 3
RETRY_DELAYS = [1.0, 3.0, 8.0]  # exponential-ish backoff

# ── State ────────────────────────────────────────────────────────────
_conversation_history: deque[dict] = deque(maxlen=MAX_HISTORY)
_cancel_flag = False
_cancel_lock = Lock()

# ── Parallel tool execution ─────────────────────────────────────────
_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tool")
_TOOL_TIMEOUT = 60

# Physical input araclari ayni anda calismamali (mouse/keyboard catismasi)
_PHYSICAL_TOOLS = frozenset({"browser_control", "app_launcher", "screen_capture"})
_PHYSICAL_LOCK = Lock()

# ── Cost tracking (session + daily) ─────────────────────────────────
_cost_lock = Lock()
_session_cost = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
_daily_cost: dict[str, dict] = {}  # {"2026-03-23": {input_tokens, output_tokens, calls}}

# ── Legal keyword detection ─────────────────────────────────────────
_LEGAL_KEYWORDS = re.compile(
    r"\b(dava|kanun|madde|tck|cmk|hmk|tmk|tbk|mahkeme|savunma|mevzuat|ceza|yargi|"
    r"hukuk|sanik|mudafi|tutuklama|beraat|iddianame|temyiz|istinaf|haciz|icra|"
    r"avukat|noter|tapu|vekaletname|savcilik|karar|tebligat)\b", re.IGNORECASE
)


# ── Fast-path: aninda yanit (API cagrisi OLMADAN) ────────────────────
_TOOL_KEYWORDS = frozenset({
    "ara", "bul", "hesapla", "yaz", "oluştur", "olustur", "ekle", "kaydet",
    "sil", "not", "hatırlat", "hatırlat", "hatirla", "dosya", "belge", "dava",
    "müvekkil", "muvekkil", "duruşma", "durusma", "tebligat", "vekalet",
    "masraf", "mevzuat", "yargı", "yargi", "icra", "analiz", "takip", "süre",
    "sure", "dilekçe", "dilekce", "savunma", "itiraz", "temyiz", "rapor",
    "whatsapp", "telegram", "web", "hava", "aç", "ac", "kapat", "chrome",
    "uygulama", "indir", "gönder", "gonder", "listele", "göster", "goster",
    "oluştur", "kontrol", "hazırla", "hazirla",
})

_FAST_RESPONSES = {
    "greetings": {
        "patterns": [
            "selam", "merhaba", "hey", "günaydın", "gunaydin", "iyi akşamlar",
            "iyi aksamlar", "iyi günler", "iyi gunler", "hoş geldin", "hos geldin",
            "heyy", "selamm", "merhabaa", "sa", "s.a", "selamun aleyküm",
            "selamun aleykum", "hayırlı sabahlar", "hayirli sabahlar",
        ],
        "responses": [
            "Selam efendim! Bugün nasıl yardımcı olabilirim? 😊",
            "Merhaba! Bir emriniz mi var?",
            "Hoş geldiniz efendim! Ne yapalım bugün?",
            "Selamlar efendim! Sizi dinliyorum 😊",
            "Buyurun efendim, hazırım!",
        ],
        "responses_named": [
            "Selam {name}! Bugün nasıl yardımcı olabilirim? 😊",
            "Merhaba {name}! Bir emriniz mi var?",
            "Hoş geldiniz {name}! Ne yapalım bugün?",
            "Selamlar {name}! Sizi dinliyorum 😊",
            "Buyurun {name}, hazırım!",
        ],
    },
    "how_are_you": {
        "patterns": [
            "nasılsın", "nasilsin", "iyi misin", "ne yapıyorsun", "ne yapiyorsun",
            "naber", "ne var ne yok", "nasıl gidiyor", "nasil gidiyor",
            "keyifler nasıl", "keyifler nasil", "n'aber", "nbr",
        ],
        "responses": [
            "İyiyim efendim, teşekkür ederim! Siz nasılsınız? 😊",
            "Harika, her zamanki gibi hazırım! Siz nasılsınız?",
            "Çok iyiyim efendim! Bir emriniz var mı?",
            "Gayet iyi, teşekkürler! Bugün ne yapabilirim sizin için?",
            "Bomba gibi efendim! 💪 Siz nasılsınız?",
        ],
    },
    "thanks": {
        "patterns": [
            "teşekkürler", "tesekkurler", "sağ ol", "sag ol", "eyvallah",
            "çok sağ ol", "cok sag ol", "teşekkür ederim", "tesekkur ederim",
            "süpersin", "supersin", "harikasın", "harikasin", "çok iyi",
            "cok iyi", "mükemmel", "mukemmel", "bravo", "aferin",
            "tşk", "tsk", "saol", "eyv",
        ],
        "responses": [
            "Ne demek efendim, her zaman! 😊",
            "Rica ederim, başka bir isteğiniz var mı?",
            "Ne demek, görevimiz! 🙏",
            "Her zaman efendim! Başka bir şey lazım olursa buradayım.",
            "Estağfurullah, lafı mı olur! 😊",
        ],
    },
    "goodbye": {
        "patterns": [
            "hoşça kal", "hosca kal", "görüşürüz", "gorusuruz", "bay bay",
            "bye", "bye bye", "güle güle", "gule gule", "kendine iyi bak",
            "iyi geceler", "iyi aksamlar",
        ],
        "responses": [
            "Görüşürüz efendim! İyi günler dilerim 👋",
            "Hoşça kalın efendim! Bir şey lazım olursa buradayım.",
            "İyi günler efendim! Kendinize iyi bakın 😊",
            "Görüşmek üzere! Her zaman hazırım 👋",
            "Hoşça kalın! Güzel bir gün geçirin efendim 🌟",
        ],
    },
    "confirmation": {
        "patterns": [
            "tamam", "ok", "okay", "anladım", "anladim", "peki", "olur",
            "evet", "tamamdır", "tamamdir", "kabul", "onay", "oldu",
            "güzel", "guzel", "harika", "şahane", "sahane", "uygun",
            "he", "hee", "hı hı", "hıhı",
        ],
        "responses": [
            "Tamam efendim! Başka bir şey var mı? 😊",
            "Anlaşıldı! Bir isteğiniz olursa buradayım.",
            "Tamamdır efendim! 👍",
            "Oldu! Başka bir emriniz?",
            "Harika, başka bir şey lazım olursa söyleyin 😊",
        ],
    },
    "small_talk": {
        "patterns": [
            "bugün nasıl gidiyor", "bugun nasil gidiyor", "bugün nasıl",
            "bugun nasil", "ne güzel", "ne guzel", "sıkıldım", "sikildim",
            "canım sıkılıyor", "canim sikiliyor", "çok güzel",
        ],
        "responses": [
            "Güzel gidiyor efendim! Umarım sizin de gününüz güzeldir 😊",
            "Her zamanki gibi, işimizin başındayız! Siz nasılsınız?",
            "Gayet güzel efendim! Bir emriniz var mı?",
            "İyi gidiyor, teşekkürler! Size nasıl yardımcı olabilirim?",
        ],
    },
}


def _check_fast_path(message: str, user_name: str = "") -> Optional[str]:
    """
    Basit sohbet mesajlarini API cagrisi OLMADAN aninda yanitla.
    Tool keyword iceriyorsa None dondur (brain'e gitsin).
    Returns: yanit string veya None (fast-path uygulanmadiysa).
    """
    cleaned = message.strip().lower()

    # Turkce karakter normalizasyonu
    cleaned_normalized = (
        cleaned.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c")
    )

    # Cok kisa veya cok uzun mesajlar
    if not cleaned or len(cleaned) > 80:
        return None

    # Tool keyword kontrolu — herhangi biri varsa fast-path ATLA
    words = set(re.split(r'\s+', cleaned))
    if words & _TOOL_KEYWORDS:
        return None

    # Normalized versiyonda da kontrol
    words_normalized = set(re.split(r'\s+', cleaned_normalized))
    normalized_tool = {
        w.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c")
        for w in _TOOL_KEYWORDS
    }
    if words_normalized & normalized_tool:
        return None

    # Display name (varsa)
    display_name = ""
    if user_name:
        # "Onur" -> "Onur Bey" (eger zaten Bey/Hanim yoksa)
        display_name = user_name
        if not any(t in user_name.lower() for t in ("bey", "hanım", "hanim")):
            display_name = f"{user_name} Bey"

    # Kategorileri kontrol et
    for category, data in _FAST_RESPONSES.items():
        for pattern in data["patterns"]:
            # Tam eslesme veya mesajin icinde pattern var
            if cleaned == pattern or cleaned_normalized == pattern.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c"):
                if display_name and "responses_named" in data:
                    return random.choice(data["responses_named"]).format(name=display_name)
                return random.choice(data["responses"])

            # Pattern mesajin icinde (ama mesaj cok uzun degilse)
            if len(cleaned) < 40 and (pattern in cleaned or pattern.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c") in cleaned_normalized):
                if display_name and "responses_named" in data:
                    return random.choice(data["responses_named"]).format(name=display_name)
                return random.choice(data["responses"])

    return None


# ── Cancel control ───────────────────────────────────────────────────
def request_cancel():
    """Iptal sinyali gonder."""
    global _cancel_flag
    with _cancel_lock:
        _cancel_flag = True


def _check_cancelled() -> bool:
    with _cancel_lock:
        return _cancel_flag


def _reset_cancel():
    global _cancel_flag
    with _cancel_lock:
        _cancel_flag = False


# ── Cost tracking ────────────────────────────────────────────────────
def _track_cost(usage):
    """Token kullanimi kaydet (session + daily)."""
    if not usage:
        return
    inp = getattr(usage, "input_tokens", 0)
    out = getattr(usage, "output_tokens", 0)
    today = date.today().isoformat()

    with _cost_lock:
        _session_cost["input_tokens"] += inp
        _session_cost["output_tokens"] += out
        _session_cost["calls"] += 1

        if today not in _daily_cost:
            _daily_cost[today] = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
        _daily_cost[today]["input_tokens"] += inp
        _daily_cost[today]["output_tokens"] += out
        _daily_cost[today]["calls"] += 1


def get_cost_summary() -> dict:
    """Maliyet ozeti dondur (session + today)."""
    today = date.today().isoformat()
    with _cost_lock:
        today_cost = _daily_cost.get(today, {"input_tokens": 0, "output_tokens": 0, "calls": 0})
        return {
            "input_tokens": _session_cost["input_tokens"],
            "output_tokens": _session_cost["output_tokens"],
            "calls": _session_cost["calls"],
            "today_input": today_cost["input_tokens"],
            "today_output": today_cost["output_tokens"],
            "today_calls": today_cost["calls"],
        }


def clear_history():
    """Konusma gecmisini temizle."""
    _conversation_history.clear()


# ── Legal context detection ──────────────────────────────────────────
def _detect_legal_query(text: str) -> bool:
    """Mesajin hukuki konuda olup olmadigini tespit et."""
    return bool(_LEGAL_KEYWORDS.search(text))


def _get_legal_context_snippet(query: str) -> str:
    """Hukuki sorgular icin bilgi bankasından kisa kontext cek."""
    try:
        tool = get_tool("bilgi_bankasi")
        if tool:
            result = tool.run(query=query, domain="hepsi")
            if result and "sonuc bulunamadi" not in result.lower():
                return result[:2000]
    except Exception as e:
        log.warning(f"Bilgi bankasi hatasi: {e}")
    return ""


# ── API call with retry ─────────────────────────────────────────────
def _api_call_with_retry(client, **kwargs) -> object:
    """Claude API cagrisini retry logic ile yap."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            last_error = e
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            log.warning(f"Rate limit — {delay}s bekleniyor (deneme {attempt + 1}/{MAX_RETRIES})")
            time.sleep(delay)
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                last_error = e
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                log.warning(f"Sunucu hatasi {e.status_code} — {delay}s bekleniyor")
                time.sleep(delay)
            else:
                raise
        except anthropic.APIConnectionError as e:
            last_error = e
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            log.warning(f"Baglanti hatasi — {delay}s bekleniyor")
            time.sleep(delay)
    raise last_error


# ── Tool execution ───────────────────────────────────────────────────
def _execute_single_tool(tool_name: str, tool_input: dict) -> str:
    """Tek bir araci calistir."""
    tool = get_tool(tool_name)
    if not tool:
        return f"Bilinmeyen arac: {tool_name}"
    try:
        if tool_name in _PHYSICAL_TOOLS:
            with _PHYSICAL_LOCK:
                return tool.run(**tool_input)
        return tool.run(**tool_input)
    except Exception as e:
        return f"Arac hatasi ({tool_name}): {e}"


def _execute_tools(
    tool_calls: list[dict],
    on_tool_start: Optional[Callable] = None,
    on_tool_end: Optional[Callable] = None,
) -> list[dict]:
    """Arac cagrilarini calistir. Callback'ler ile state broadcast destegi."""
    results = []

    if len(tool_calls) == 1:
        tc = tool_calls[0]
        if on_tool_start:
            on_tool_start(tc["name"], tc["input"])
        t0 = time.time()
        result = _execute_single_tool(tc["name"], tc["input"])
        elapsed = time.time() - t0
        if on_tool_end:
            on_tool_end(tc["name"], result[:200], elapsed)
        results.append({
            "type": "tool_result",
            "tool_use_id": tc["id"],
            "content": result[:5000],
        })
        return results

    # Coklu arac — paralel calistir
    futures = {}
    start_times = {}
    for tc in tool_calls:
        if _check_cancelled():
            results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": "Iptal edildi.",
            })
            continue
        if on_tool_start:
            on_tool_start(tc["name"], tc["input"])
        start_times[tc["id"]] = time.time()
        future = _TOOL_EXECUTOR.submit(_execute_single_tool, tc["name"], tc["input"])
        futures[future] = tc

    for future in as_completed(futures, timeout=_TOOL_TIMEOUT + 5):
        tc = futures[future]
        try:
            result = future.result(timeout=_TOOL_TIMEOUT)
        except Exception as e:
            result = f"Arac zaman asimi ({tc['name']}): {e}"
        elapsed = time.time() - start_times.get(tc["id"], time.time())
        if on_tool_end:
            on_tool_end(tc["name"], result[:200], elapsed)
        results.append({
            "type": "tool_result",
            "tool_use_id": tc["id"],
            "content": result[:5000],
        })

    return results


# ── Ana dusunme fonksiyonu ───────────────────────────────────────────
def think(
    user_message: str,
    user_name: str = "",
    case_context: str = "",
    on_tool_start: Optional[Callable] = None,
    on_tool_end: Optional[Callable] = None,
    on_stream_chunk: Optional[Callable] = None,
) -> str:
    """
    Ana dusunme fonksiyonu.
    Callbacks:
        on_tool_start(tool_name, tool_input)  — arac basladiginda
        on_tool_end(tool_name, result_preview, elapsed_seconds) — arac bittiginde
        on_stream_chunk(text_chunk) — streaming text parcasi geldiginde
    """
    _reset_cancel()

    # ── Fast-path: basit sohbet mesajlari icin API cagrisi YAPMA ────
    mem_user = user_name or get_user_name()
    fast_response = _check_fast_path(user_message, user_name=mem_user)
    if fast_response:
        log.info(f"Fast-path: {user_message[:40]} → aninda yanit")
        _conversation_history.append({"role": "user", "content": user_message})
        _conversation_history.append({"role": "assistant", "content": fast_response})
        return fast_response

    # ── Normal path: Claude API ─────────────────────────────────────
    api_key = get_anthropic_key()
    if not api_key:
        return "Anthropic API anahtari ayarlanmamis. Lutfen .env dosyasini kontrol edin."

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = build_claude_prompt(user_name=mem_user, case_context=case_context)

    memory_ctx = get_memory_context()
    if memory_ctx:
        system_prompt += f"\n\n## HAFIZA (kullaniciyi taniyorsun)\n{memory_ctx}"

    # Context-aware: hukuki sorgu ise bilgi bankasi kontext ekle
    if _detect_legal_query(user_message):
        kb_context = _get_legal_context_snippet(user_message)
        if kb_context:
            system_prompt += f"\n\nYEREL BILGI BANKASI KONTEKSTI:\n{kb_context}"

    # Konusma gecmisine ekle
    _conversation_history.append({"role": "user", "content": user_message})

    # Araclari al
    tools = get_claude_tool_definitions()

    # Mesajlari hazirla
    messages = list(_conversation_history)

    log.info(f"Sorgu: {user_message[:80]}... | Model: {MODEL}")

    # ── Tool dongusu (max N tur) ────────────────────────────────────
    final_text = ""
    tools_used = []

    for round_num in range(MAX_TOOL_ROUNDS):
        if _check_cancelled():
            final_text = "Iptal edildi, efendim."
            break

        try:
            response = _api_call_with_retry(
                client,
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
        except anthropic.APIError as e:
            log.error(f"Claude API hatasi: {e}")
            _report_error("brain.api", e, context=f"Model: {MODEL}", severity="CRITICAL")
            final_text = f"Claude API hatasi: {e}"
            break
        except Exception as e:
            log.error(f"Beklenmeyen hata: {e}")
            _report_error("brain.think", e, context=f"Query: {user_message[:100]}", severity="ERROR")
            final_text = f"Beklenmeyen hata: {e}"
            break

        # Cost tracking
        if hasattr(response, "usage"):
            _track_cost(response.usage)

        # Yanittan text ve tool cagrilarini ayikla
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                if on_stream_chunk and block.text:
                    on_stream_chunk(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        # Tool cagrisi yoksa → son cevap
        if not tool_calls:
            final_text = "\n".join(text_parts)
            break

        # Tool cagrilarini logla
        tool_names = [tc["name"] for tc in tool_calls]
        tools_used.extend(tool_names)
        log.info(f"Tur {round_num + 1}/{MAX_TOOL_ROUNDS}: {', '.join(tool_names)}")

        # Tool cagrilarini calistir (callback'ler ile)
        tool_results = _execute_tools(tool_calls, on_tool_start, on_tool_end)

        # Mesajlara assistant yaniti + tool sonuclarini ekle
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Son turda hala tool cagrisi varsa, text'i topla
        if round_num == MAX_TOOL_ROUNDS - 1 and text_parts:
            final_text = "\n".join(text_parts)

    # Son tur tool loop'tan ciktiysa ve text yoksa, sentez yap
    if not final_text and messages:
        try:
            synth = _api_call_with_retry(
                client,
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt + "\n\nONEMLI: Arac sonuclarini ozetleyerek kullaniciya yanit ver. Yeni arac CAGIRMA.",
                messages=messages,
            )
            for block in synth.content:
                if block.type == "text":
                    final_text += block.text
                    if on_stream_chunk and block.text:
                        on_stream_chunk(block.text)

            if hasattr(synth, "usage"):
                _track_cost(synth.usage)
        except Exception as e:
            log.error(f"Synthesis hatasi: {e}")
            _report_error("brain.synthesis", e, severity="ERROR")
            final_text = "Sonuclar alindi ancak ozetlenemedi."

    # Konusma gecmisine assistant yanitini ekle
    if final_text:
        _conversation_history.append({"role": "assistant", "content": final_text})

    # Hafiza cikarimi (arka plan thread — ana akisi yavaslatmaz)
    if final_text:
        extract_memories_async(user_message, final_text)

    return final_text or "Yanit uretilemedi."
