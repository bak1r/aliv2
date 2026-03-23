"""macOS platform implementasyonu."""

import subprocess
from pathlib import Path
from ali_platform.base import PlatformBase


class MacOSPlatform(PlatformBase):

    def open_file(self, path: str) -> bool:
        try:
            subprocess.Popen(["open", path])
            return True
        except Exception:
            return False

    def open_folder(self, path: str) -> bool:
        try:
            subprocess.Popen(["open", path])
            return True
        except Exception:
            return False

    def get_volume(self) -> int:
        try:
            result = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True, text=True, timeout=5
            )
            return int(result.stdout.strip())
        except Exception:
            return -1

    def set_volume(self, level: int) -> bool:
        try:
            level = max(0, min(100, level))
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {level}"],
                timeout=5
            )
            return True
        except Exception:
            return False

    def send_notification(self, title: str, message: str) -> bool:
        try:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script], timeout=5)
            return True
        except Exception:
            return False

    def get_active_window(self) -> str:
        try:
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                tell process frontApp
                    set windowTitle to name of front window
                end tell
                return frontApp & " - " & windowTitle
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def activate_window(self, title: str) -> bool:
        try:
            script = f'''
            tell application "{title}"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", script], timeout=5)
            return True
        except Exception:
            return False

    def get_default_browser(self) -> str:
        try:
            # LaunchServices varsayilan tarayiciyi doner
            from AppKit import NSWorkspace
            url = NSWorkspace.sharedWorkspace().URLForApplicationToOpenURL_(
                __import__("Foundation").NSURL.URLWithString_("https://example.com")
            )
            if url:
                app_name = url.lastPathComponent().replace(".app", "")
                return app_name
        except Exception:
            pass
        return "Safari"

    def sleep_display(self) -> bool:
        try:
            subprocess.run(["pmset", "displaysleepnow"], timeout=5)
            return True
        except Exception:
            return False

    def shutdown(self) -> bool:
        try:
            subprocess.run(
                ["osascript", "-e",
                 'tell app "System Events" to shut down'],
                timeout=5
            )
            return True
        except Exception:
            return False

    def get_downloads_dir(self) -> str:
        return str(Path.home() / "Downloads")

    def get_desktop_dir(self) -> str:
        return str(Path.home() / "Desktop")
