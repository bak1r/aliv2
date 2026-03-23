const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');

const app = express();
app.use(express.json());

let isReady = false;
let lastQR = null;

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: '.wwebjs_auth' }),
    webVersionCache: {
        type: 'remote',
        remotePath: 'https://raw.githubusercontent.com/nicstephens/nicstephens.github.io/main/nicpage/nicpage1_files/',
    },
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--single-process'
        ]
    }
});

// QR kodu terminale bas
client.on('qr', (qr) => {
    lastQR = qr;
    console.log('\n📱 WhatsApp QR kodu:');
    qrcode.generate(qr, { small: true });
    console.log('\nTelefonunuzdan WhatsApp > Bağlı Cihazlar > Cihaz Bağla ile okutun.\n');
});

client.on('ready', () => {
    isReady = true;
    lastQR = null;
    console.log('✅ WhatsApp bağlantısı kuruldu!');
});

client.on('disconnected', (reason) => {
    isReady = false;
    console.log('❌ WhatsApp bağlantısı koptu:', reason);
});

client.on('auth_failure', (msg) => {
    console.log('❌ WhatsApp kimlik doğrulama hatası:', msg);
});

// Gelen mesajları dinle
client.on('message', async (msg) => {
    // Ali brain'e yönlendirmek için HTTP callback
    try {
        const fetch = (await import('node-fetch')).default;
        await fetch('http://127.0.0.1:8420/whatsapp-incoming', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from: msg.from,
                body: msg.body,
                name: msg._data.notifyName || '',
                timestamp: msg.timestamp
            })
        }).catch(() => {});
    } catch(e) {}
});

// === HTTP API ===

// Durum kontrolü
app.get('/status', (req, res) => {
    res.json({ ready: isReady, qr_pending: lastQR !== null });
});

// Mesaj gönder
app.post('/send', async (req, res) => {
    if (!isReady) return res.status(503).json({ error: 'WhatsApp bağlı değil' });
    
    const { to, message } = req.body;
    if (!to || !message) return res.status(400).json({ error: 'to ve message gerekli' });

    try {
        // Numara formatı: 905551234567@c.us
        let chatId = to;
        if (!chatId.includes('@')) {
            chatId = chatId.replace(/[^0-9]/g, '');
            if (chatId.startsWith('0')) chatId = '90' + chatId.slice(1);
            if (!chatId.startsWith('90')) chatId = '90' + chatId;
            chatId += '@c.us';
        }
        
        await client.sendMessage(chatId, message);
        res.json({ success: true, to: chatId });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// İsimle mesaj gönder (rehberden ara)
app.post('/send-by-name', async (req, res) => {
    if (!isReady) return res.status(503).json({ error: 'WhatsApp bağlı değil' });
    
    const { name, message } = req.body;
    if (!name || !message) return res.status(400).json({ error: 'name ve message gerekli' });

    try {
        const contacts = await client.getContacts();
        const found = contacts.find(c => 
            c.name && c.name.toLowerCase().includes(name.toLowerCase())
        );
        if (!found) return res.status(404).json({ error: `"${name}" rehberde bulunamadı` });
        
        const chat = await found.getChat();
        await chat.sendMessage(message);
        res.json({ success: true, to: found.name, number: found.number });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// QR durumu
app.get('/qr', (req, res) => {
    if (isReady) return res.json({ status: 'connected' });
    if (lastQR) return res.json({ status: 'qr_ready', qr: lastQR });
    res.json({ status: 'initializing' });
});

// Sunucuyu başlat
const PORT = 8421;
app.listen(PORT, '127.0.0.1', () => {
    console.log(`\n🔗 WhatsApp API: http://127.0.0.1:${PORT}`);
    console.log('📱 QR kodu bekleniyor...\n');
});

client.initialize();
