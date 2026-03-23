"""WhatsApp mesaj gonderme araci — pywhatkit ile WhatsApp Web uzerinden mesaj gonderir.

Birincil yontem: pywhatkit.sendwhatmsg_instantly (telefon numarasi ile)
Yedek yontem: PyAutoGUI ile WhatsApp Desktop (kisi adi ile, geriye uyumluluk)
"""

from __future__ import annotations

import sys
import time
import subprocess
from tools.base import BaseTool


class WhatsAppTool(BaseTool):
    name = "whatsapp_mesaj"
    description = (
        "WhatsApp uzerinden mesaj gonderir. "
        "Telefon numarasi (ornek: +905551234567) veya kisi adi belirtin."
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
                "description": "Alici kisi veya grup adi (telefon numarasi yoksa PyAutoGUI ile aranir)",
            },
            "message": {
                "type": "string",
                "description": "Gonderilecek mesaj metni",
            },
        },
        "required": ["message"],
    }

    def run(self, phone_number: str = "", contact: str = "", message: str = "", **kw) -> str:
        if not message:
            return "Mesaj metni belirtilmedi."
        if not phone_number and not contact:
            return "Alici belirtilmedi. phone_number veya contact parametresi gerekli."

        # --- Birincil yontem: pywhatkit ile telefon numarasi uzerinden ---
        if phone_number:
            return self._send_via_pywhatkit(phone_number, message)

        # --- Yedek yontem: PyAutoGUI ile kisi adi uzerinden ---
        return self._send_via_pyautogui(contact, message)

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
                    pyautogui.typewrite(contact, interval=0.05)
                    time.sleep(1)
                    pyautogui.press("enter")
                    time.sleep(0.5)
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
                    pyautogui.typewrite(contact, interval=0.05)
                    time.sleep(1)
                    pyautogui.press("enter")
                    time.sleep(0.5)
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
