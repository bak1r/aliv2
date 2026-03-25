#!/bin/bash
# ═══════════════════════════════════════════════
#  ALI v2 — Avukat AI Asistani
#  Cift tikla, gerisini Ali halleder.
# ═══════════════════════════════════════════════

cd "$(dirname "$0")"
clear

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   ALI v2 — Avukat AI Asistani            ║"
echo "  ║   Kurulum basliyor, lutfen bekleyin...    ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── 1. Python kontrolu ──
PYTHON=""
for p in python3.12 python3.11 python3.10 python3; do
    if command -v "$p" &>/dev/null; then
        ver=$("$p" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$p"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ⚠️  Python 3.10 veya ustu bulunamadi."
    echo ""
    echo "  Lutfen su adimi yapin:"
    echo "  1. https://www.python.org/downloads/ adresine gidin"
    echo "  2. Python 3.12 indirin ve kurun"
    echo "  3. Bu dosyaya tekrar cift tiklayin"
    echo ""
    echo "  Veya Terminal'de: brew install python@3.12"
    echo ""
    read -p "  Devam etmek icin Enter'a basin..."
    exit 1
fi

echo "  ✅ Python: $($PYTHON --version)"

# ── 2. Sanal ortam ──
if [ ! -d ".venv" ]; then
    echo "  📦 Sanal ortam olusturuluyor..."
    $PYTHON -m venv .venv
fi
echo "  ✅ Sanal ortam hazir"

# ── 3. Paketler ──
echo "  📥 Paketler kuruluyor (bu biraz surebilir)..."

# portaudio (PyAudio icin)
if command -v brew &>/dev/null; then
    brew list portaudio &>/dev/null || brew install portaudio 2>/dev/null
fi

.venv/bin/pip install -q --upgrade pip 2>/dev/null
.venv/bin/pip install -q -r requirements-base.txt 2>&1 | tail -1

# Platform-specific
if [ -f "requirements-mac.txt" ]; then
    .venv/bin/pip install -q -r requirements-mac.txt 2>/dev/null
fi

echo "  ✅ Paketler kuruldu"

# ── 4. Playwright ──
echo "  🌐 Tarayici motoru kuruluyor..."
.venv/bin/python3 -m playwright install chromium 2>/dev/null
echo "  ✅ Tarayici hazir"

# ── 5. Klasorler ──
mkdir -p data/sessions data/documents data/screenshots data/reports config
echo "  ✅ Klasorler olusturuldu"

# ── 6. Veritabani ──
.venv/bin/python3 -c "
import sys; sys.path.insert(0,'.')
try:
    from core.database import get_db
    get_db()
    print('  ✅ Veritabani hazir')
except Exception as e:
    print(f'  ⚠️  Veritabani: {e}')
" 2>/dev/null

# ── 7. API Anahtarlari (.env) ──
if [ ! -f ".env" ]; then
    echo ""
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║   API Anahtarlari Gerekli                 ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo ""
    echo "  Ali'nin calismasi icin 2 anahtar gerekli:"
    echo ""
    echo "  1. Google Gemini (sesli konusma icin):"
    echo "     https://aistudio.google.com/apikey"
    echo ""
    echo "  2. Anthropic Claude (zeka icin):"
    echo "     https://console.anthropic.com/settings/keys"
    echo ""

    read -p "  Google Gemini API Key: " gemini_key
    read -p "  Anthropic API Key: " anthropic_key
    echo ""

    echo "  ── Telegram (opsiyonel — bos birakilabilir) ──"
    echo ""
    read -p "  Telegram Bot Token: " telegram_token
    echo ""

    telegram_api_id=""
    telegram_api_hash=""
    if [ -n "$telegram_token" ]; then
        echo "  Telegram mention takibi icin API bilgileri gerekli."
        echo "  https://my.telegram.org adresinden alinabilir."
        echo "  (Bos birakirsaniz sadece bot calısır, mention takibi kapali kalir)"
        echo ""
        read -p "  Telegram API ID (opsiyonel): " telegram_api_id
        read -p "  Telegram API Hash (opsiyonel): " telegram_api_hash
        echo ""
    fi

    echo "  ── WhatsApp (opsiyonel) ──"
    echo ""
    echo "  WhatsApp entegrasyonu icin uygulama basladiktan sonra"
    echo "  Web UI'da WhatsApp QR kodu taratmaniz gerekecek."
    echo ""

    {
        echo "GOOGLE_API_KEY=$gemini_key"
        echo "ANTHROPIC_API_KEY=$anthropic_key"
        [ -n "$telegram_token" ] && echo "TELEGRAM_BOT_TOKEN=$telegram_token"
        [ -n "$telegram_api_id" ] && echo "TELEGRAM_API_ID=$telegram_api_id"
        [ -n "$telegram_api_hash" ] && echo "TELEGRAM_API_HASH=$telegram_api_hash"
    } > .env

    echo "  ✅ API anahtarlari kaydedildi"
fi

# ── 8. macOS izinleri ──
echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Onemli: macOS Izinleri                  ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  Ilk calistirmada macOS su izinleri soracak:"
echo "  • Mikrofon → IZIN VERIN (sesli komut icin)"
echo "  • Erisebilirlik → Sistem Ayarlari > Gizlilik"
echo "    > Erisebilirlik > Terminal'e izin verin"
echo ""

# ── 9. Baslat ──
echo "  ═══════════════════════════════════════════"
echo ""
echo "  ✅ Kurulum tamamlandi!"
echo ""
echo "  Ali 28 aracla hazir:"
echo "  📚 Mevzuat & Yargi Arama"
echo "  📄 Dilekce, Savunma, Itiraz Yazma"
echo "  📅 Durusma Takvimi & Muvekil Takip"
echo "  💰 Masraf & Zaman Takibi"
echo "  🏦 Icra & Ceza Hesaplama"
echo "  📂 Toplu Dosya Analizi"
echo "  💬 WhatsApp & Telegram"
echo "  🎤 Sesli Komut"
echo ""
echo "  ═══════════════════════════════════════════"
echo ""

# ── 10. Masaustune tek tikla baslat kisayolu ──
DESKTOP="$HOME/Desktop"
LAUNCHER="$DESKTOP/ALI Baslat.command"
if [ ! -f "$LAUNCHER" ]; then
    cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/bin/bash
cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
cd ~/Desktop/UnlimitedClaude 2>/dev/null || cd "$(find ~/Desktop -name "main.py" -path "*/UnlimitedClaude/*" -exec dirname {} \; 2>/dev/null | head -1)"
export ALI_ELECTRON=1
.venv/bin/python3 main.py
LAUNCHER_EOF
    chmod +x "$LAUNCHER"
    echo "  ✅ Masaustune 'ALI Baslat.command' olusturuldu"
fi

read -p "  Ali'yi simdi baslatmak ister misiniz? (E/h): " start_now

if [ "$start_now" != "h" ] && [ "$start_now" != "H" ]; then
    echo ""
    echo "  🚀 Ali baslatiliyor..."
    echo ""
    export ALI_ELECTRON=1
    .venv/bin/python3 main.py
else
    echo ""
    echo "  Daha sonra baslatmak icin masaustundeki 'ALI Baslat.command' dosyasina cift tiklayin"
    echo ""
    read -p "  Kapatmak icin Enter'a basin..."
fi
