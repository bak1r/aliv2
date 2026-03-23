"""Hava durumu araci."""

from __future__ import annotations
import requests
from tools.base import BaseTool


class WeatherTool(BaseTool):
    name = "hava_durumu"
    description = "Hava durumu bilgisi verir. Sehir adi ile sorgulama yapar."
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "Sehir adi (ornek: 'Istanbul', 'Ankara')"},
        },
        "required": ["city"],
    }

    def run(self, city: str = "", **kw) -> str:
        if not city:
            return "Sehir adi belirtilmedi."

        try:
            # wttr.in — ucretsiz, API key gerektirmez
            resp = requests.get(
                f"https://wttr.in/{city}?format=j1",
                timeout=10,
                headers={"User-Agent": "Ali-v2"}
            )
            resp.raise_for_status()
            data = resp.json()

            current = data.get("current_condition", [{}])[0]
            temp = current.get("temp_C", "?")
            feels = current.get("FeelsLikeC", "?")
            humidity = current.get("humidity", "?")
            desc_tr = current.get("lang_tr", [{}])
            desc = desc_tr[0].get("value", current.get("weatherDesc", [{}])[0].get("value", "")) if desc_tr else ""
            wind = current.get("windspeedKmph", "?")

            return (
                f"{city} Hava Durumu:\n"
                f"  Sicaklik: {temp}°C (hissedilen: {feels}°C)\n"
                f"  Durum: {desc}\n"
                f"  Nem: %{humidity}\n"
                f"  Ruzgar: {wind} km/h"
            )

        except Exception as e:
            return f"Hava durumu alinamadi: {e}"
