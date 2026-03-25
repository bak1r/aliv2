"""Uygulama acma araci — cross-platform."""

from __future__ import annotations

import sys
import subprocess
import shutil
from tools.base import BaseTool


# Uygulama isim → komut eslesmesi
_MAC_APPS = {
    "chrome": "Google Chrome", "safari": "Safari", "firefox": "Firefox",
    "word": "Microsoft Word", "excel": "Microsoft Excel", "powerpoint": "Microsoft PowerPoint",
    "finder": "Finder", "terminal": "Terminal", "notes": "Notes",
    "calculator": "Calculator", "calendar": "Calendar", "mail": "Mail",
    "music": "Music", "photos": "Photos", "preview": "Preview",
    "whatsapp": "WhatsApp", "telegram": "Telegram", "discord": "Discord",
    "slack": "Slack", "zoom": "zoom.us", "teams": "Microsoft Teams",
    "vscode": "Visual Studio Code", "code": "Visual Studio Code",
}

_WIN_APPS = {
    "chrome": "chrome", "firefox": "firefox", "edge": "msedge",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "explorer": "explorer", "notepad": "notepad", "cmd": "cmd",
    "terminal": "wt", "calculator": "calc", "paint": "mspaint",
    "notes": "notepad", "calendar": "outlookcal:", "mail": "outlookmail:",
    "music": "mswindowsmusic:", "photos": "ms-photos:",
    "whatsapp": "whatsapp", "telegram": "telegram", "discord": "discord",
    "slack": "slack", "zoom": "zoom", "teams": "msteams:",
    "vscode": "code", "code": "code",
    "finder": "explorer", "safari": "msedge",
}


class AppLauncherTool(BaseTool):
    name = "uygulama_ac"
    description = "Masaustu uygulamasi acar: Chrome, Word, WhatsApp, Terminal vb."
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Uygulama adi (ornek: 'chrome', 'word', 'whatsapp')"},
        },
        "required": ["app_name"],
    }

    def run(self, app_name: str = "", **kw) -> str:
        if not app_name:
            return "Uygulama adi belirtilmedi."

        app_lower = app_name.strip().lower()

        try:
            if sys.platform == "darwin":
                return self._open_mac(app_lower, app_name)
            elif sys.platform == "win32":
                return self._open_win(app_lower, app_name)
            else:
                return f"Bu isletim sistemi desteklenmiyor: {sys.platform}"
        except Exception as e:
            return f"Uygulama acilamadi ({app_name}): {e}"

    def _open_mac(self, app_lower: str, original: str) -> str:
        # Bilinen uygulama mi?
        mac_name = _MAC_APPS.get(app_lower)
        if mac_name:
            subprocess.Popen(["open", "-a", mac_name])
            return f"{mac_name} acildi."

        # Direkt dene
        result = subprocess.run(
            ["open", "-a", original],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"{original} acildi."

        # Arama yap
        result = subprocess.run(
            ["mdfind", f"kMDItemKind == 'Application' && kMDItemDisplayName == '*{original}*'"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            app_path = result.stdout.strip().split("\n")[0]
            subprocess.Popen(["open", app_path])
            return f"{app_path} acildi."

        return f"'{original}' uygulamasi bulunamadi."

    def _open_win(self, app_lower: str, original: str) -> str:
        import os
        win_name = _WIN_APPS.get(app_lower)
        if win_name:
            # Protocol handler (ms-photos:, outlookcal: vb.)
            if win_name.endswith(":"):
                try:
                    os.startfile(win_name)
                    return f"{original} acildi."
                except Exception:
                    pass

            # PATH'te var mı?
            if shutil.which(win_name):
                subprocess.Popen(win_name, shell=True)
                return f"{win_name} acildi."

            # os.startfile ile dene
            try:
                os.startfile(win_name)
                return f"{win_name} acildi."
            except Exception:
                pass

        # Direkt os.startfile
        try:
            os.startfile(original)
            return f"{original} acildi."
        except Exception:
            pass

        # PowerShell ile dene
        try:
            subprocess.Popen(
                ["powershell", "-Command", f"Start-Process '{original}'"],
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
            return f"{original} acildi."
        except Exception:
            return f"'{original}' uygulamasi bulunamadi."
