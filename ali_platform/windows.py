"""Windows platform implementasyonu."""

import os
import sys
import subprocess
from pathlib import Path
from ali_platform.base import PlatformBase


class WindowsPlatform(PlatformBase):

    def open_file(self, path: str) -> bool:
        try:
            os.startfile(path)
            return True
        except Exception:
            return False

    def open_folder(self, path: str) -> bool:
        try:
            os.startfile(path)
            return True
        except Exception:
            return False

    def get_volume(self) -> int:
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
            )
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            level = volume.GetMasterVolumeLevelScalar()
            return int(level * 100)
        except Exception:
            return -1

    def set_volume(self, level: int) -> bool:
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            level = max(0, min(100, level))
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None
            )
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100, None)
            return True
        except Exception:
            return False

    def send_notification(self, title: str, message: str) -> bool:
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
            return True
        except Exception:
            return False

    def get_active_window(self) -> str:
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else ""
        except Exception:
            return ""

    def activate_window(self, title: str) -> bool:
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title)
            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                return True
            # Fallback: PowerShell
            ps_cmd = f'''
            $wshell = New-Object -ComObject wscript.shell
            $wshell.AppActivate("{title}")
            '''
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, timeout=5
            )
            return True
        except Exception:
            return False

    def get_default_browser(self) -> str:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
            )
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            winreg.CloseKey(key)
            browser_map = {
                "ChromeHTML": "Chrome",
                "FirefoxURL": "Firefox",
                "MSEdgeHTM": "Edge",
                "OperaStable": "Opera",
                "BraveHTML": "Brave",
            }
            return browser_map.get(prog_id, prog_id)
        except Exception:
            return "Chrome"

    def sleep_display(self) -> bool:
        try:
            import ctypes
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
            return True
        except Exception:
            return False

    def shutdown(self) -> bool:
        try:
            subprocess.run(["shutdown", "/s", "/t", "5"], timeout=5)
            return True
        except Exception:
            return False

    def get_downloads_dir(self) -> str:
        return str(Path.home() / "Downloads")

    def get_desktop_dir(self) -> str:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            )
            desktop, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            return os.path.expandvars(desktop)
        except Exception:
            return str(Path.home() / "Desktop")
