"""Ali v2 — Ses Motoru (Gemini Live Audio)
SERIAI + Ali v1 en iyi parçalarından birleştirildi.
Gemini 2.5 Flash native audio ile gerçek zamanlı Türkçe ses I/O.

Mimari:
- Gemini Live = kulak + ağız (STT + TTS tek session)
- Claude Brain = beyin (tüm düşünme, analiz, karar)
- PyAudio = mikrofon + hoparlör
- VAD = Voice Activity Detection + echo cancellation
- Barge-in = kullanıcı konuşurken kesebilir
- Proaktif bildirim = Telegram/sistem bildirimleri sesli aktarılır
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import struct
import time
from typing import Optional, Callable

from core.config import get_gemini_key, SETTINGS

log = logging.getLogger("ali.voice")

# Audio constants
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024
BARGE_IN_RMS = 4000
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

# System prompt for Gemini voice
VOICE_SYSTEM_PROMPT = """Sen Ali — avukatların sesli AI asistanı.

KİŞİLİK:
- Samimi, zeki, profesyonel. Gerçek bir iş ortağı gibi konuş.
- Kısa ve öz ama sıcak. Espri: kuru mizah, hafif.
- Bilmiyorsan uydurma — tool çağır.
- Türkçe konuş. "Efendim" ile hitap et.

TOOL KULLANIMI:
- ali_brain → HER TÜRLÜ soru, analiz, hukuki araştırma, belge oluşturma.
  Basit sohbet hariç her şey için çağır. 5-30sn sürebilir.
- open_app → uygulama aç
- open_url → URL aç
- computer_settings → ses ayarları

KURALLAR:
- MAX 2 cümle sesli yanıt.
- Araç kullanıyorsan "bakıyorum" de, sessiz kalma.
- [SİSTEM] ile başlayan mesajlar dahili — kullanıcıya gösterme.
"""


class VoiceEngine:
    """Gemini Live tabanlı gerçek zamanlı ses motoru."""

    def __init__(self, brain_fn: Callable = None):
        """
        Args:
            brain_fn: Claude brain think() fonksiyonu
        """
        self.brain_fn = brain_fn
        self._running = False
        self._session = None
        self._is_speaking = False
        self._broadcast_fn: Optional[Callable] = None
        self._notification_queue: asyncio.Queue = None
        self._recent_notifications: list = []
        self.mic_muted = False

    def set_broadcast(self, broadcast_fn: Callable):
        """Web UI'a event broadcast fonksiyonunu bağla."""
        self._broadcast_fn = broadcast_fn

    async def inject_notification(self, text: str):
        """Dışarıdan sesli bildirim enjekte et."""
        if self._notification_queue:
            await self._notification_queue.put(text)

    async def _broadcast(self, event_type: str, data: dict):
        """Web UI'a event gönder."""
        if self._broadcast_fn:
            try:
                await self._broadcast_fn(event_type, data)
            except Exception as e:
                log.warning(f"Broadcast hatası ({event_type}): {e}")

    def is_available(self) -> bool:
        """Ses motoru çalışabilir mi?"""
        try:
            import pyaudio
            return bool(get_gemini_key())
        except ImportError:
            return False

    async def start(self):
        """Ses motorunu başlat."""
        api_key = get_gemini_key()
        if not api_key:
            log.error("Gemini API key bulunamadı")
            return

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            log.error("google-genai paketi yok")
            return

        self._running = True
        self._notification_queue = asyncio.Queue()
        client = genai.Client(api_key=api_key)

        # Tool declarations
        tools = self._build_tools()

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Orus"
                    )
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text=VOICE_SYSTEM_PROMPT)]
            ),
            tools=tools,
        )

        log.info(f"Gemini'ye bağlanılıyor... ({LIVE_MODEL})")
        await self._broadcast("daemon_status", {"voice": "ok"})

        while self._running:
            try:
                async with client.aio.live.connect(
                    model=LIVE_MODEL, config=config
                ) as session:
                    self._session = session
                    log.info("Ses bağlantısı kuruldu")
                    await self._broadcast("note", {"text": "Ses motoru aktif — konuşabilirsiniz.", "priority": "normal"})
                    await self._broadcast("speaking", {"active": False})

                    tasks = [
                        asyncio.create_task(self._listen_mic(session)),
                        asyncio.create_task(self._receive_audio(session)),
                        asyncio.create_task(self._keepalive(session)),
                        asyncio.create_task(self._notification_listener()),
                    ]

                    await asyncio.gather(*tasks)

            except Exception as e:
                log.error(f"Ses bağlantı hatası: {e}")
                await self._broadcast("note", {"text": f"Ses koptu: {e}", "priority": "urgent"})
                await asyncio.sleep(2)

    def _build_tools(self) -> list:
        """Gemini tool tanımları."""
        return [{"function_declarations": [
            {
                "name": "ali_brain",
                "description": (
                    "Ali beyni — HER TÜRLÜ düşünme gerektiren iş için çağır. "
                    "Hukuki araştırma, mevzuat arama, belge oluşturma, ceza hesaplama, "
                    "web araması, dosya işlemleri, bilgi sorgulama. "
                    "Basit sohbet (selam, teşekkür) HARİÇ her şey için çağır."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "user_request": {"type": "STRING", "description": "Kullanıcının isteği, tam olarak"}
                    },
                    "required": ["user_request"]
                }
            },
            {
                "name": "open_app",
                "description": "Uygulama aç: Chrome, Word, WhatsApp, Terminal vb.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "app_name": {"type": "STRING", "description": "Uygulama adı"}
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "open_url",
                "description": "URL'yi tarayıcıda aç.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "url": {"type": "STRING", "description": "Açılacak URL"}
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "computer_settings",
                "description": "Ses seviyesi ayarla: volume_up, volume_down, mute, unmute, get_volume",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "action": {"type": "STRING", "description": "volume_up|volume_down|mute|unmute|get_volume"},
                        "value": {"type": "STRING", "description": "Değer (opsiyonel)"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "self_shutdown",
                "description": "Ali'yi kapat.",
                "parameters": {"type": "OBJECT", "properties": {}, "required": []}
            },
        ]}]

    async def _listen_mic(self, session):
        """Mikrofondan ses al, Gemini'ye gönder."""
        try:
            import pyaudio
        except ImportError:
            log.error("PyAudio bulunamadı")
            return

        pya = pyaudio.PyAudio()
        stream = pya.open(
            format=pyaudio.paInt16, channels=1,
            rate=SEND_SAMPLE_RATE, input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        loop = asyncio.get_event_loop()
        silence = b"\x00" * CHUNK_SIZE * 2

        try:
            while self._running:
                data = await loop.run_in_executor(
                    None, lambda: stream.read(CHUNK_SIZE, exception_on_overflow=False)
                )

                if not data or len(data) < CHUNK_SIZE:
                    continue

                # Mic muted
                if self.mic_muted:
                    data = silence
                # Echo cancellation
                elif self._is_speaking:
                    rms = self._calc_rms(data)
                    if rms < BARGE_IN_RMS:
                        data = silence
                    else:
                        # Barge-in — kullanıcı konuşuyor
                        data = self._attenuate(data, 0.25)
                        await self._broadcast("audio_level", {"level": min(1.0, rms / 10000)})

                # Audio level meter
                if not self.mic_muted and not self._is_speaking:
                    rms = self._calc_rms(data)
                    if rms > 200:
                        await self._broadcast("audio_level", {"level": min(1.0, rms / 8000)})

                await session.send(
                    input={"data": base64.b64encode(data).decode(), "mime_type": "audio/pcm"},
                    end_of_turn=False,
                )
        finally:
            stream.stop_stream()
            stream.close()
            pya.terminate()

    async def _receive_audio(self, session):
        """Gemini'den ses + tool çağrıları al."""
        try:
            import pyaudio
        except ImportError:
            return

        pya = pyaudio.PyAudio()
        out_stream = pya.open(
            format=pyaudio.paInt16, channels=1,
            rate=RECEIVE_SAMPLE_RATE, output=True,
        )

        try:
            while self._running:
                turn = session.receive()
                async for response in turn:
                    # Ses verisi
                    if hasattr(response, "data") and response.data:
                        self._is_speaking = True
                        await self._broadcast("speaking", {"active": True})
                        out_stream.write(response.data)

                    # Transcript (STT)
                    if hasattr(response, "text") and response.text:
                        await self._broadcast("transcript", {
                            "role": "user", "text": response.text
                        })

                    # Tool çağrısı
                    if hasattr(response, "tool_call") and response.tool_call:
                        await self._handle_tool_call(session, response.tool_call)

                self._is_speaking = False
                await self._broadcast("speaking", {"active": False})
                await self._broadcast("audio_level", {"level": 0})
        finally:
            out_stream.stop_stream()
            out_stream.close()
            pya.terminate()

    async def _handle_tool_call(self, session, tool_call):
        """Tool çağrısını işle."""
        from google.genai import types

        for fc in tool_call.function_calls:
            log.info(f"Tool çağrısı: {fc.name} — {str(fc.args)[:80]}")
            await self._broadcast("tool_state", {"name": fc.name, "state": "running"})

            result = ""

            if fc.name == "ali_brain":
                request = fc.args.get("user_request", "")
                await self._broadcast("thinking", {"active": True, "text": request})
                await self._broadcast("transcript", {"role": "user", "text": request})

                if self.brain_fn:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, lambda: self.brain_fn(user_message=request)
                    )
                else:
                    result = "Beyin bağlantısı yok."

                await self._broadcast("thinking", {"active": False})
                await self._broadcast("transcript", {
                    "role": "ai", "text": result[:500],
                    "model": "sonnet", "domain": "hukuk"
                })

            elif fc.name == "open_app":
                app = fc.args.get("app_name", "")
                from tools.computer.app_launcher import AppLauncherTool
                result = AppLauncherTool().run(app_name=app)

            elif fc.name == "open_url":
                url = fc.args.get("url", "")
                import webbrowser
                webbrowser.open(url)
                result = f"Açıldı: {url}"

            elif fc.name == "computer_settings":
                action = fc.args.get("action", "")
                from tools.computer.system import SystemControlTool
                result = SystemControlTool().run(action=action)

            elif fc.name == "self_shutdown":
                await self._broadcast("shutdown", {"message": "Görüşürüz."})
                self._running = False
                result = "Kapatılıyor."

            await self._broadcast("tool_state", {"name": fc.name, "state": "done"})

            # Sonucu Gemini'ye gönder
            await session.send(
                input=types.LiveClientToolResponse(
                    function_responses=[
                        types.FunctionResponse(
                            name=fc.name,
                            response={"result": result[:3000]},
                        )
                    ]
                ),
                end_of_turn=True,
            )

    async def _notification_listener(self):
        """Proaktif bildirim dinleyici."""
        while self._running:
            try:
                text = await asyncio.wait_for(
                    self._notification_queue.get(), timeout=5
                )
                if self._session and not self._is_speaking:
                    log.info(f"Proaktif bildirim: {text[:80]}")
                    from datetime import datetime
                    self._recent_notifications.append({
                        "time": datetime.now().strftime("%H:%M"),
                        "text": text,
                    })
                    if len(self._recent_notifications) > 10:
                        self._recent_notifications = self._recent_notifications[-10:]

                    inject = (
                        f"[SİSTEM BİLDİRİMİ — KULLANICIYA HEMEN SESLİ BİLDİR]\n{text}\n"
                        f"Bu bildirimi kısa ve net şekilde sesli olarak ilet."
                    )
                    await self._session.send_client_content(
                        turns={"parts": [{"text": inject}]},
                        turn_complete=True,
                    )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning(f"Bildirim hatası: {e}")

    async def _keepalive(self, session):
        """Bağlantı canlı tutma."""
        silence = b"\x00" * 320
        while self._running:
            await asyncio.sleep(60)
            try:
                await session.send(
                    input={"data": base64.b64encode(silence).decode(), "mime_type": "audio/pcm"},
                    end_of_turn=False,
                )
            except Exception:
                break

    @staticmethod
    def _calc_rms(data: bytes) -> float:
        if len(data) < 2:
            return 0
        count = len(data) // 2
        shorts = struct.unpack(f"<{count}h", data[:count * 2])
        return (sum(s * s for s in shorts) / count) ** 0.5

    @staticmethod
    def _attenuate(data: bytes, factor: float) -> bytes:
        count = len(data) // 2
        shorts = struct.unpack(f"<{count}h", data[:count * 2])
        att = [max(-32768, min(32767, int(s * factor))) for s in shorts]
        return struct.pack(f"<{count}h", *att)

    def stop(self):
        self._running = False
