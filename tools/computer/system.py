"""Sistem kontrol araci — ses, bildirim, ekran, bilgi."""

from __future__ import annotations

import sys
from tools.base import BaseTool


class SystemControlTool(BaseTool):
    name = "sistem"
    description = "Sistem kontrolleri: ses seviyesi, bildirim gonderme, ekran kapatma, sistem bilgisi."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: get_volume | set_volume | notify | sleep_display | shutdown | info"
            },
            "value": {"type": "number", "description": "Deger (ses seviyesi 0-100)"},
            "title": {"type": "string", "description": "Bildirim basligi"},
            "message": {"type": "string", "description": "Bildirim mesaji"},
        },
        "required": ["action"],
    }

    def run(self, action: str = "", value: int = 0, title: str = "", message: str = "", **kw) -> str:
        try:
            # Platform katmanini import et
            if sys.platform == "win32":
                from ali_platform.windows import WindowsPlatform
                plat = WindowsPlatform()
            elif sys.platform == "darwin":
                from ali_platform.macos import MacOSPlatform
                plat = MacOSPlatform()
            else:
                return f"Desteklenmeyen OS: {sys.platform}"

            if action == "get_volume":
                vol = plat.get_volume()
                return f"Ses seviyesi: %{vol}" if vol >= 0 else "Ses seviyesi alinamadi."

            elif action == "set_volume":
                plat.set_volume(int(value))
                return f"Ses seviyesi ayarlandi: %{int(value)}"

            elif action == "notify":
                plat.send_notification(title or "Ali", message or "Bildirim")
                return "Bildirim gonderildi."

            elif action == "sleep_display":
                plat.sleep_display()
                return "Ekran uyutuldu."

            elif action == "shutdown":
                plat.shutdown()
                return "Bilgisayar kapatiliyor..."

            elif action == "info":
                return self._system_info()

            else:
                return f"Bilinmeyen islem: {action}"

        except Exception as e:
            return f"Sistem hatasi: {e}"

    def _system_info(self) -> str:
        import psutil
        import os

        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk_path = "C:\\" if sys.platform == "win32" else "/"
        disk = psutil.disk_usage(disk_path)

        return (
            f"Sistem Bilgisi:\n"
            f"  OS: {sys.platform}\n"
            f"  CPU: %{cpu}\n"
            f"  RAM: {mem.used // (1024**3)}/{mem.total // (1024**3)} GB (%{mem.percent})\n"
            f"  Disk: {disk.used // (1024**3)}/{disk.total // (1024**3)} GB (%{disk.percent})\n"
            f"  Python: {sys.version.split()[0]}"
        )
