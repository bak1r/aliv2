#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# WhatsApp bridge başlat (arka planda)
if [ -d "$DIR/whatsapp-service" ] && command -v node &>/dev/null; then
    echo "[WhatsApp] Bridge başlatılıyor..."
    (cd "$DIR/whatsapp-service" && node index.js) &
    WA_PID=$!
    echo "[WhatsApp] PID: $WA_PID — QR için terminali kontrol edin"
fi

# Ali başlat
"$DIR/.venv/bin/python3" "$DIR/main.py"

# Çıkışta WhatsApp bridge'i de durdur
[ -n "$WA_PID" ] && kill $WA_PID 2>/dev/null
