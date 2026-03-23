"""Hatirlatici araci."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from tools.base import BaseTool


class ReminderTool(BaseTool):
    name = "hatirlatici"
    description = "Belirli bir sure sonra hatirlatma yapar. Dakika olarak sure belirtin."
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Hatirlatma mesaji"},
            "minutes": {"type": "number", "description": "Kac dakika sonra hatirlatilsin"},
        },
        "required": ["message", "minutes"],
    }

    _reminders: list[dict] = []

    def run(self, message: str = "", minutes: float = 0, **kw) -> str:
        if not message:
            return "Hatirlatma mesaji belirtilmedi."
        if minutes <= 0:
            return "Sure belirtilmedi (dakika olarak)."

        trigger_time = datetime.now() + timedelta(minutes=minutes)

        def _remind():
            import sys
            # Platform bildirimi
            try:
                if sys.platform == "darwin":
                    from ali_platform.macos import MacOSPlatform
                    MacOSPlatform().send_notification("Ali Hatirlatici", message)
                elif sys.platform == "win32":
                    from ali_platform.windows import WindowsPlatform
                    WindowsPlatform().send_notification("Ali Hatirlatici", message)
            except Exception:
                print(f"\n[HATIRLATICI] {message}")

        timer = threading.Timer(minutes * 60, _remind)
        timer.daemon = True
        timer.start()

        self._reminders.append({
            "message": message,
            "time": trigger_time.strftime("%H:%M"),
            "timer": timer,
        })

        return f"Hatirlatici ayarlandi: '{message}' — {trigger_time.strftime('%H:%M')}'de ({minutes:.0f} dk sonra)"
