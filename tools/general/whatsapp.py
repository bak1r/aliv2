"""WhatsApp mesaj gonderme araci — whatsapp-web.js bridge uzerinden.

Birincil yontem: whatsapp-web.js HTTP API (localhost:8421)
Yedek yontem: pywhatkit (tarayici uzerinden)
"""

from __future__ import annotations

import sys
import time
import subprocess
import requests
from tools.base import BaseTool

_WA_API = "http://127.0.0.1:8421"


class WhatsAppTool(BaseTool):
    name = "whatsapp_mesaj"
    description = (
        "WhatsApp uzerinden mesaj gonderir. "
        "Telefon numarasi (ornek: +905551234567) veya kisi adi belirtin. "
        "WhatsApp bridge aktifse QR ile bagli kalici oturum kullanir."
    )
    parameters = {
        "type": "object",
        "properties": {
            "phone_number": {
                "type": "string",
                "description": "Alici telefon numarasi, ulke kodu dahil (ornek: +905551234567)",
            },
            "contact": {
                "type": "string",
                "description": "Alici kisi adi (rehberden aranir)",
            },
            "message": {
                "type": "string",
                "description": "Gonderilecek mesaj metni",
            },
        },
        "required": ["message"],
    }

    def _bridge_active(self) -> bool:
        try:
            r = requests.get(f"{_WA_API}/status", timeout=2)
            return r.ok and r.json().get("ready", False)
        except Exception:
            return False

    def run(self, phone_number: str = "", contact: str = "", message: str = "", **kw) -> str:
        if not message:
            return "Mesaj metni belirtilmedi."
        if not phone_number and not contact:
            return "Alici belirtilmedi. phone_number veya contact parametresi gerekli."

        # Birincil: whatsapp-web.js bridge
        if self._bridge_active():
            if contact and not phone_number:
                return self._send_via_bridge_name(contact, message)
            return self._send_via_bridge(phone_number, message)

        # Yedek: pywhatkit
        if phone_number:
            return self._send_via_pywhatkit(phone_number, message)

        return "WhatsApp bridge bagli degil. Lutfen './run.sh' ile yeniden baslatin ve QR kodu okutun."

    def _send_via_bridge(self, phone_number: str, message: str) -> str:
        """whatsapp-web.js bridge uzerinden mesaj gonderir."""
        try:
            r = requests.post(f"{_WA_API}/send", json={
                "to": phone_number, "message": message
            }, timeout=15)
            if r.ok:
                return (
                    f"✅ WhatsApp mesaji gonderildi.\n"
                    f"Alici: {phone_number}\n"
                    f"Mesaj: {message[:80]}{'...' if len(message) > 80 else ''}"
                )
            return f"WhatsApp hatasi: {r.json().get('error', 'Bilinmeyen hata')}"
        except Exception as e:
            return f"WhatsApp bridge hatasi: {e}"

    def _send_via_bridge_name(self, contact: str, message: str) -> str:
        """whatsapp-web.js bridge uzerinden isimle mesaj gonderir."""
        try:
            r = requests.post(f"{_WA_API}/send-by-name", json={
                "name": contact, "message": message
            }, timeout=15)
            if r.ok:
                data = r.json()
                return (
                    f"✅ WhatsApp mesaji gonderildi.\n"
                    f"Kisi: {data.get('to', contact)}\n"
                    f"Mesaj: {message[:80]}{'...' if len(message) > 80 else ''}"
                )
            err = r.json().get('error', 'Bilinmeyen hata')
            return f"WhatsApp hatasi: {err}"
        except Exception as e:
            return f"WhatsApp bridge hatasi: {e}"

    def _send_via_pywhatkit(self, phone_number: str, message: str) -> str:
        """pywhatkit kullanarak WhatsApp Web uzerinden mesaj gonderir."""
        # Numara formatini duzelt
        phone = phone_number.strip()
        if not phone.startswith("+"):
            # Turkiye varsayilan ulke kodu
            if phone.startswith("0"):
                phone = "+90" + phone[1:]
            else:
                phone = "+" + phone

        try:
            import pywhatkit
        except ImportError:
            return (
                "pywhatkit kutuphanesi bulunamadi. "
                "Kurulum: pip install pywhatkit"
            )

        try:
            # Aninda mesaj gonder (WhatsApp Web tarayicida acilir)
            pywhatkit.sendwhatmsg_instantly(
                phone_no=phone,
                message=message,
                wait_time=15,          # Sayfa yuklenme bekleme suresi (saniye)
                tab_close=True,        # Gonderim sonrasi sekmeyi kapat
                close_time=5,          # Kapanma oncesi bekleme (saniye)
            )
            return (
                f"WhatsApp mesaji gonderildi (pywhatkit).\n"
                f"Alici: {phone}\n"
                f"Mesaj: {message[:80]}{'...' if len(message) > 80 else ''}"
            )
        except Exception as e:
            return f"WhatsApp gonderim hatasi (pywhatkit): {e}"

    def _send_via_pyautogui(self, contact: str, message: str) -> str:
        """PyAutoGUI ile WhatsApp Desktop uygulamasi uzerinden mesaj gonderir (geriye uyumluluk)."""
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "WhatsApp"])
                time.sleep(2)

                try:
                    import pyautogui
                    pyautogui.hotkey("command", "f")
                    time.sleep(0.5)
                    try:
                        import pyperclip
                        pyperclip.copy(contact)
                        pyautogui.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
                    except ImportError:
                        pyautogui.typewrite(contact, interval=0.05)
                    time.sleep(1)
                    pyautogui.press("enter")
                    time.sleep(0.5)
                    try:
                        import pyperclip
                        pyperclip.copy(message)
                        pyautogui.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
                    except ImportError:
                        pyautogui.typewrite(message, interval=0.02)
                    pyautogui.press("enter")
                    return (
                        f"WhatsApp mesaji gonderildi (PyAutoGUI).\n"
                        f"Kisi: {contact}\n"
                        f"Mesaj: {message[:80]}{'...' if len(message) > 80 else ''}"
                    )
                except ImportError:
                    return (
                        "PyAutoGUI bulunamadi. Kisi adi ile gonderim icin "
                        "pip install pyautogui gereklidir. "
                        "Alternatif olarak phone_number parametresi ile pywhatkit kullanabilirsiniz."
                    )

            elif sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", "whatsapp://"])
                time.sleep(3)

                try:
                    import pyautogui
                    pyautogui.hotkey("ctrl", "f")
                    time.sleep(0.5)
                    try:
                        import pyperclip
                        pyperclip.copy(contact)
                        pyautogui.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
                    except ImportError:
                        pyautogui.typewrite(contact, interval=0.05)
                    time.sleep(1)
                    pyautogui.press("enter")
                    time.sleep(0.5)
                    try:
                        import pyperclip
                        pyperclip.copy(message)
                        pyautogui.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
                    except ImportError:
                        pyautogui.typewrite(message, interval=0.02)
                    pyautogui.press("enter")
                    return (
                        f"WhatsApp mesaji gonderildi (PyAutoGUI).\n"
                        f"Kisi: {contact}\n"
                        f"Mesaj: {message[:80]}{'...' if len(message) > 80 else ''}"
                    )
                except ImportError:
                    return "PyAutoGUI bulunamadi."

            return "WhatsApp gonderilemedi — desteklenmeyen platform."

        except Exception as e:
            return f"WhatsApp hatasi: {e}"
