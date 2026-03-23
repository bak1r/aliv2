#!/bin/bash
cd "$(dirname "$0")"

# WhatsApp bridge başlat (arka planda)
if [ -d "whatsapp-service" ] && command -v node &>/dev/null; then
    echo "[WhatsApp] Bridge başlatılıyor..."
    cd whatsapp-service && node index.js &
    WA_PID=$!
    cd ..
    echo "[WhatsApp] PID: $WA_PID — QR için terminali kontrol edin"
fi

# Ali başlat
.venv/bin/python3 main.py

# Çıkışta WhatsApp bridge'i de durdur
[ -n "$WA_PID" ] && kill $WA_PID 2>/dev/null
