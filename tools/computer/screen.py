"""Ekran yakalama ve analiz araci."""

from __future__ import annotations

import base64
from io import BytesIO
from tools.base import BaseTool


class ScreenCaptureTool(BaseTool):
    name = "ekran_yakala"
    description = "Ekran goruntusunu yakalar ve isterseniz AI ile analiz eder."
    parameters = {
        "type": "object",
        "properties": {
            "analyze": {"type": "boolean", "description": "Goruntu analiz edilsin mi?", "default": False},
            "prompt": {"type": "string", "description": "Analiz icin soru (ornek: 'ekranda ne var?')"},
        },
        "required": [],
    }

    def run(self, analyze: bool = False, prompt: str = "", **kw) -> str:
        try:
            import mss
            from PIL import Image
        except ImportError:
            return "mss veya pillow paketi bulunamadi."

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Ana ekran
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Kucult (token tasarrufu)
            img.thumbnail((1280, 720))

            if not analyze:
                # Kaydet
                from pathlib import Path
                from datetime import datetime
                from core.config import BASE_DIR

                out_dir = BASE_DIR / "data" / "screenshots"
                out_dir.mkdir(parents=True, exist_ok=True)
                path = out_dir / f"ekran_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                img.save(str(path))
                return f"Ekran goruntusi kaydedildi: {path}"

            # Gemini Vision ile analiz
            buf = BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            try:
                from google import genai
                from core.config import get_gemini_key

                client = genai.Client(api_key=get_gemini_key())
                response = client.models.generate_content(
                    model="gemini-2.5-flash-preview-04-17",
                    contents=[
                        {"text": prompt or "Ekranda ne goruyorsun? Turkce acikla."},
                        {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                    ],
                )
                return response.text

            except Exception as e:
                return f"Ekran yakalandi ama analiz yapilamadi: {e}"

        except Exception as e:
            return f"Ekran yakalama hatasi: {e}"
