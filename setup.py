#!/usr/bin/env python3
"""Ali v2 — Akilli Kurulum Scripti
OS algilar, venv olusturur, dogru paketleri kurar, API key'leri sorar.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"


def _run(cmd: list[str], desc: str, show_errors: bool = False) -> bool:
    print(f"  {desc}...", end=" ", flush=True)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print("OK")
            return True
        else:
            print("HATA")
            if show_errors and result.stderr:
                for line in result.stderr.strip().split("\n")[-5:]:
                    print(f"    {line}")
            return False
    except subprocess.TimeoutExpired:
        print("ZAMAN ASIMI")
        return False
    except FileNotFoundError:
        print("BULUNAMADI")
        return False


def check_python():
    v = sys.version_info
    print(f"  Python: {v.major}.{v.minor}.{v.micro}", end=" ")
    if v >= (3, 10):
        print("OK")
        return True
    print("YETERSIZ (3.10+ gerekli)")
    if sys.platform == "darwin":
        print("  Kurulum: brew install python@3.12")
    elif sys.platform == "win32":
        print("  Kurulum: https://python.org adresinden Python 3.12+ indirin")
    else:
        print("  Kurulum: sudo apt install python3.12 (veya distro paket yoneticisi)")
    return False


def create_venv():
    """Virtual environment olustur."""
    if VENV_DIR.exists():
        print("  Sanal ortam zaten mevcut.")
        return True

    print("  Sanal ortam olusturuluyor...", end=" ", flush=True)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("OK")
        return True
    except Exception as e:
        print(f"HATA: {e}")
        return False


def get_venv_python() -> str:
    """Venv icindeki python yolunu dondur."""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python3")


def get_venv_pip() -> list[str]:
    """Venv icindeki pip komutunu dondur."""
    return [get_venv_python(), "-m", "pip", "install", "-q"]


def install_deps():
    pip = get_venv_pip()

    # pip upgrade
    _run(pip + ["--upgrade", "pip"], "pip guncelleniyor")

    # Base dependencies
    if not _run(pip + ["-r", str(BASE_DIR / "requirements-base.txt")], "Ortak paketler", show_errors=True):
        # PyAudio hata verebilir — portaudio kontrol et
        if sys.platform == "darwin":
            print("\n  PyAudio icin portaudio gerekli olabilir.")
            if shutil.which("brew"):
                _run(["brew", "install", "portaudio"], "portaudio kuruluyor")
                # Tekrar dene
                if not _run(pip + ["-r", str(BASE_DIR / "requirements-base.txt")], "Ortak paketler (2. deneme)", show_errors=True):
                    return False
            else:
                print("  Homebrew bulunamadi: https://brew.sh")
                return False
        else:
            return False

    # Platform-specific
    if sys.platform == "win32":
        _run(pip + ["-r", str(BASE_DIR / "requirements-win.txt")], "Windows paketleri", show_errors=True)
    elif sys.platform == "darwin":
        _run(pip + ["-r", str(BASE_DIR / "requirements-mac.txt")], "macOS paketleri", show_errors=True)

    return True


def install_playwright():
    venv_python = get_venv_python()
    return _run(
        [venv_python, "-m", "playwright", "install", "chromium"],
        "Playwright (Chromium)"
    )


def setup_database():
    """SQLite veritabanini baslat."""
    db_path = BASE_DIR / "data" / "ali.db"
    if db_path.exists():
        print("  Veritabani zaten mevcut.")
        return True
    print("  Veritabani olusturuluyor...", end=" ", flush=True)
    try:
        venv_python = get_venv_python()
        result = subprocess.run(
            [venv_python, "-c", "import sys; sys.path.insert(0,'.'); from core.database import get_db; db=get_db(); print('ok')"],
            capture_output=True, text=True, cwd=str(BASE_DIR), timeout=30
        )
        if result.returncode == 0:
            print("OK")
            return True
        print(f"HATA: {result.stderr[:100]}")
        return False
    except Exception as e:
        print(f"HATA: {e}")
        return False


def setup_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        print("  .env dosyasi zaten mevcut, atlaniyor.")
        return

    print("\n  API Anahtarlari:")
    print("  (Bos birakirsaniz sonra .env dosyasina ekleyebilirsiniz)\n")

    gemini_key = input("  Google Gemini API Key: ").strip()
    anthropic_key = input("  Anthropic API Key: ").strip()

    print("\n  Opsiyonel Entegrasyonlar:")
    print("  (Bos birakirsaniz sonra ekleyebilirsiniz)\n")
    telegram_token = input("  Telegram Bot Token (opsiyonel): ").strip()

    lines = []
    lines.append(f"GOOGLE_API_KEY={gemini_key}")
    lines.append(f"ANTHROPIC_API_KEY={anthropic_key}")
    if telegram_token:
        lines.append(f"TELEGRAM_BOT_TOKEN={telegram_token}")

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("  .env dosyasi olusturuldu.")


def setup_directories():
    dirs = ["data", "data/sessions", "data/documents", "data/screenshots", "config"]
    for d in dirs:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)
    print("  Klasorler olusturuldu.")


def show_platform_notes():
    if sys.platform == "darwin":
        print("\n  macOS Notlari:")
        print("  - Ilk calistirmada mikrofon izni istenecek → Izin verin")
        print("  - Bilgisayar kontrolu icin: Sistem Ayarlari > Gizlilik")
        print("    > Erisebilirlik > Terminal/Python'a izin verin")
    elif sys.platform == "win32":
        print("\n  Windows Notlari:")
        print("  - Chrome'u remote debug ile acin (bilgisayar kontrolu icin):")
        print('    chrome.exe --remote-debugging-port=9222')


def create_run_script():
    """Kolay calistirma scripti olustur."""
    if sys.platform == "darwin" or sys.platform == "linux":
        script = BASE_DIR / "run.sh"
        script.write_text(
            '#!/bin/bash\n'
            'cd "$(dirname "$0")"\n'
            '.venv/bin/python3 main.py\n',
            encoding="utf-8"
        )
        os.chmod(str(script), 0o755)
        print("  run.sh olusturuldu.")
    elif sys.platform == "win32":
        script = BASE_DIR / "run.bat"
        script.write_text(
            '@echo off\n'
            'cd /d "%~dp0"\n'
            '.venv\\Scripts\\python.exe main.py\n',
            encoding="utf-8"
        )
        print("  run.bat olusturuldu.")


def main():
    os_name = {"win32": "Windows", "darwin": "macOS", "linux": "Linux"}.get(sys.platform, sys.platform)
    print(f"\n{'='*50}")
    print(f"  ALI v2 — Avukat AI Asistani Kurulumu")
    print(f"  Isletim Sistemi: {os_name}")
    print(f"{'='*50}\n")

    if not check_python():
        sys.exit(1)

    setup_directories()

    if not create_venv():
        print("\n  HATA: Sanal ortam olusturulamadi.")
        sys.exit(1)

    if not install_deps():
        print("\n  HATA: Paket kurulumu basarisiz.")
        sys.exit(1)

    install_playwright()
    setup_env()
    setup_database()
    create_run_script()
    show_platform_notes()

    # Yetenek özeti
    print("\n  Ali v2 Yetenekleri:")
    print("  ─────────────────────────────────────")
    print("  📚 Hukuk: Mevzuat, yargi, ceza hesaplama, belge uretimi")
    print("  📁 Dava:  Durusma takvimi, muvekil, tebligat, vekalet takibi")
    print("  💰 Buro:  Masraf, zaman takibi, icra hesaplama")
    print("  📂 Analiz: Toplu PDF/Word dosya analizi")
    print("  💬 Iletisim: WhatsApp, Telegram bot")
    print("  🎤 Ses:   Sesli komut ile kullanim")
    print("  🧠 Hafiza: Sizi taniyan, ogrenen asistan")
    print("  ─────────────────────────────────────")
    print("  Toplam: 28 arac | SQLite veritabani | Cross-platform")

    print(f"\n{'='*50}")
    print(f"  Kurulum tamamlandi!")
    if sys.platform == "win32":
        print(f"  Calistirmak icin: Kur ve Baslat.bat (veya: .venv\\Scripts\\python main.py)")
    else:
        print(f"  Calistirmak icin: ./run.sh (veya: .venv/bin/python3 main.py)")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
