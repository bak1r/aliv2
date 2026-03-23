@echo off
chcp 65001 >nul 2>&1
title ALI v2 - Avukat AI Asistani
cd /d "%~dp0"
cls

echo.
echo   ══════════════════════════════════════════
echo     ALI v2 - Avukat AI Asistani
echo     Kurulum basliyor, lutfen bekleyin...
echo   ══════════════════════════════════════════
echo.

:: 1. Python kontrolu
set PYTHON=
for %%p in (python3.12 python3.11 python3.10 python3 python) do (
    where %%p >nul 2>&1 && (
        for /f "tokens=*" %%v in ('%%p -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2^>nul') do (
            set PYTHON=%%p
            goto :found_python
        )
    )
)

echo   ⚠️  Python 3.10 veya ustu bulunamadi.
echo.
echo   Lutfen su adimi yapin:
echo   1. https://www.python.org/downloads/ adresine gidin
echo   2. Python 3.12 indirin ve kurun
echo   3. "Add Python to PATH" secenegini isaretleyin
echo   4. Bu dosyaya tekrar cift tiklayin
echo.
pause
exit /b 1

:found_python
echo   ✅ Python bulundu: %PYTHON%

:: 2. Sanal ortam
if not exist ".venv" (
    echo   📦 Sanal ortam olusturuluyor...
    %PYTHON% -m venv .venv
)
echo   ✅ Sanal ortam hazir

:: 3. Paketler
echo   📥 Paketler kuruluyor (bu biraz surebilir)...
.venv\Scripts\pip install -q --upgrade pip 2>nul
.venv\Scripts\pip install -q -r requirements-base.txt 2>nul
if exist "requirements-win.txt" (
    .venv\Scripts\pip install -q -r requirements-win.txt 2>nul
)
echo   ✅ Paketler kuruldu

:: 4. Playwright
echo   🌐 Tarayici motoru kuruluyor...
.venv\Scripts\python -m playwright install chromium 2>nul
echo   ✅ Tarayici hazir

:: 5. Klasorler
if not exist "data\sessions" mkdir data\sessions
if not exist "data\documents" mkdir data\documents
if not exist "data\screenshots" mkdir data\screenshots
if not exist "data\reports" mkdir data\reports
if not exist "config" mkdir config
echo   ✅ Klasorler olusturuldu

:: 6. Veritabani
.venv\Scripts\python -c "import sys; sys.path.insert(0,'.'); from core.database import get_db; get_db(); print('  ✅ Veritabani hazir')" 2>nul

:: 7. API Anahtarlari
if not exist ".env" (
    echo.
    echo   ══════════════════════════════════════════
    echo     API Anahtarlari Gerekli
    echo   ══════════════════════════════════════════
    echo.
    echo   Ali'nin calismasi icin 2 anahtar gerekli:
    echo.
    echo   1. Google Gemini (sesli konusma icin):
    echo      https://aistudio.google.com/apikey
    echo.
    echo   2. Anthropic Claude (zeka icin):
    echo      https://console.anthropic.com/settings/keys
    echo.

    set /p gemini_key="  Google Gemini API Key: "
    set /p anthropic_key="  Anthropic API Key: "
    echo.
    set /p telegram_token="  Telegram Bot Token (opsiyonel): "

    (
        echo GOOGLE_API_KEY=%gemini_key%
        echo ANTHROPIC_API_KEY=%anthropic_key%
        if not "%telegram_token%"=="" echo TELEGRAM_BOT_TOKEN=%telegram_token%
    ) > .env

    echo   ✅ API anahtarlari kaydedildi
)

:: 8. Baslat
echo.
echo   ══════════════════════════════════════════
echo.
echo   ✅ Kurulum tamamlandi!
echo.
echo   Ali 28 aracla hazir:
echo   📚 Mevzuat ^& Yargi Arama
echo   📄 Dilekce, Savunma, Itiraz Yazma
echo   📅 Durusma Takvimi ^& Muvekil Takip
echo   💰 Masraf ^& Zaman Takibi
echo   🏦 Icra ^& Ceza Hesaplama
echo   📂 Toplu Dosya Analizi
echo   💬 WhatsApp ^& Telegram
echo   🎤 Sesli Komut
echo.
echo   ══════════════════════════════════════════
echo.

set /p start_now="  Ali'yi simdi baslatmak ister misiniz? (E/h): "
if /i "%start_now%"=="h" goto :end

echo.
echo   🚀 Ali baslatiliyor...
echo.
.venv\Scripts\python main.py
goto :eof

:end
echo.
echo   Daha sonra baslatmak icin bu dosyaya tekrar cift tiklayin
echo.
pause
