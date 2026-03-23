# ALI v2 — Avukat AI Asistanı (Tam Yeniden Tasarım Planı)

## Mevcut Durum (Ali v1 Analizi)

Ali v1 çalışan ama sürdürülemez bir proje:
- `claude_brain.py` tek başına 141KB, 3010 satır — her şey birbirine bağlı
- 4 model routing (Haiku/Sonnet/Opus/Gemini) gereksiz karmaşıklık
- 8 turlu tool loop, prompt çakışmaları, token israfı
- Tamamen Windows'a bağımlı (comtypes, pycaw, win10toast, winreg, os.startfile)
- Hassas veriler public repo'da (audit log, konuşma cache'i, dava bilgileri)

### Ali v1'den Taşınacak Değerli Parçalar:
1. **Hukuk knowledge base** — TCK, CMK, savunma teknikleri markdown dosyaları
2. **MCP entegrasyonları** — mevzuat.surucu.dev + yargimcp.fastmcp.app client kodu
3. **Ceza hesaplama mantığı** — legal_tools.py içindeki hesaplayıcılar
4. **Legal document şablonları** — legal_doc_forge.py içindeki docx üretimi
5. **UYAP selector haritası** — config/uyap_selectors.json
6. **Gemini ses akışı** — main.py içindeki audio pipeline (temizlenecek)

### Ali v1'den ALINMAYACAK Parçalar:
- 8 aşamalı tool loop → tek düz akış olacak
- 4 model routing → Gemini ses + Claude beyin (2 model)
- 141KB claude_brain.py → modüler yapı
- Deprecated agent/ klasörü
- Windows-only bağımlılıklar (yerine cross-platform alternatifler)
- 6KB karışık prompt.txt → kısa, net, tek prompt

---

## YENİ MİMARİ

```
┌──────────────────────────────────────────────────────┐
│                    ALI v2 MASAÜSTÜ                   │
│                                                      │
│  ┌─────────┐    ┌──────────┐    ┌─────────────────┐  │
│  │   SES   │    │  BEYİN   │    │    ARAÇLAR      │  │
│  │         │    │          │    │                 │  │
│  │ Gemini  │───▶│ Claude   │───▶│ Her araç ayrı   │  │
│  │ Live    │    │ Sonnet   │    │ dosya, bağımsız  │  │
│  │ Audio   │◀───│ Tek API  │◀───│                 │  │
│  │         │    │ çağrısı  │    │ Araç bozulsa    │  │
│  └─────────┘    └──────────┘    │ diğerleri çalışır│  │
│       │              │          └────────┬────────┘  │
│       │              │                   │           │
│  ┌────▼──────────────▼───────────────────▼────────┐  │
│  │              PLATFORM KATMANI                   │  │
│  │  Windows: comtypes, winreg, os.startfile        │  │
│  │  macOS: osascript, AppKit, open komutu          │  │
│  │  (Tek interface, platform otomatik seçilir)     │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │                    UI                           │  │
│  │  CustomTkinter (cross-platform, native görünüm) │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### Dosya Yapısı:

```
ali-v2/
├── main.py                    # Giriş noktası (~200 satır)
├── setup.py                   # Otomatik kurulum (OS algılama + bağımlılık)
├── requirements-base.txt      # Ortak bağımlılıklar
├── requirements-win.txt       # Windows-only ek paketler
├── requirements-mac.txt       # macOS-only ek paketler
├── .env.example               # API key template
├── README.md                  # Kurulum + kullanım
│
├── config/
│   ├── settings.json          # Uygulama ayarları
│   ├── uyap_selectors.json    # Ali v1'den aynen taşınacak
│   └── pricing.json           # Model fiyatlandırma
│
├── core/
│   ├── brain.py               # Claude API çağrısı (~300 satır)
│   │                          #   - Tek model: claude-sonnet-4
│   │                          #   - Tek system prompt
│   │                          #   - Tool loop max 4 tur (8 değil)
│   │                          #   - Conversation history: 10 mesaj (20 değil)
│   │
│   ├── voice.py               # Gemini ses motoru (~200 satır)
│   │                          #   - Ali v1'deki audio pipeline temizlenmiş hali
│   │                          #   - Keepalive, VAD, echo cancellation
│   │                          #   - Routing: basit → direkt cevap, karmaşık → brain.py
│   │
│   ├── prompt.py              # System prompt yönetimi (~100 satır)
│   │                          #   - Tek base prompt (Türkçe, ~50 satır)
│   │                          #   - Dinamik context enjeksiyonu (case bilgisi, kullanıcı adı)
│   │                          #   - Prompt çakışması YOK — tek kaynak
│   │
│   └── memory.py              # Basitleştirilmiş hafıza (~150 satır)
│                              #   - JSON dosyaları (şifreleme opsiyonel)
│                              #   - Conversation history
│                              #   - Kullanıcı tercihleri
│                              #   - FAISS yok (gereksiz karmaşıklık)
│
├── tools/                     # Her araç bağımsız modül
│   ├── __init__.py            # Araç registry + otomatik keşif
│   ├── base.py                # BaseTool sınıfı (her araç bunu extend eder)
│   │
│   ├── legal/                 # Hukuk araçları
│   │   ├── mevzuat_search.py  # Mevzuat MCP araması
│   │   ├── yargi_search.py    # Yargı kararları MCP araması
│   │   ├── ceza_hesapla.py    # Ceza hesaplayıcı
│   │   ├── doc_generator.py   # Dilekçe/savunma üretici
│   │   ├── deadline.py        # Süre hesaplama
│   │   └── case_manager.py    # Dava dosyası yönetimi
│   │
│   ├── computer/              # Bilgisayar kontrolü
│   │   ├── app_launcher.py    # Uygulama açma (cross-platform)
│   │   ├── file_ops.py        # Dosya işlemleri (cross-platform)
│   │   ├── browser.py         # Chrome CDP kontrolü
│   │   ├── screen.py          # Ekran yakalama + analiz
│   │   └── system.py          # Ses, bildirim, ayarlar (cross-platform)
│   │
│   └── general/               # Genel araçlar
│       ├── web_search.py      # DuckDuckGo arama
│       ├── weather.py         # Hava durumu
│       ├── reminder.py        # Hatırlatıcı
│       └── message.py         # WhatsApp mesaj
│
├── platform/                  # Cross-platform soyutlama katmanı
│   ├── __init__.py            # OS algılama + doğru modülü yükleme
│   ├── base.py                # Abstract interface tanımları
│   ├── windows.py             # Windows implementasyonları
│   │                          #   comtypes, pycaw, winreg, os.startfile
│   │                          #   win10toast, pygetwindow
│   └── macos.py               # macOS implementasyonları
│                              #   osascript (AppleScript), AppKit
│                              #   subprocess + open komutu
│                              #   terminal-notifier veya native notification
│
├── ui/
│   ├── app.py                 # Ana UI penceresi (CustomTkinter)
│   ├── components/            # UI bileşenleri
│   │   ├── chat_panel.py      # Konuşma paneli
│   │   ├── tool_rack.py       # Araç durumu göstergesi
│   │   ├── status_bar.py      # Durum çubuğu
│   │   └── setup_dialog.py    # İlk kurulum (API key girişi)
│   └── theme.py               # Renk/font tanımları
│
├── knowledge/                 # Ali v1'den aynen taşınacak
│   ├── tck/                   # Türk Ceza Kanunu
│   ├── cmk/                   # Ceza Muhakemesi Kanunu
│   ├── savunma_teknikleri/    # Savunma teknikleri
│   └── uyap/                  # UYAP rehberleri
│
└── data/                      # Çalışma zamanı verileri (gitignore'da)
    ├── memory.json            # Uzun süreli hafıza
    ├── cost_history.jsonl     # Maliyet takibi
    └── sessions/              # Oturum geçmişleri
```

---

## FAZLAR

### FAZ 1: Temel Altyapı + Kurulum Sistemi (Gün 1 sabah)

**Hedef:** Projeyi sıfırdan kurmak, cross-platform setup sistemi oluşturmak.

**Yapılacaklar:**
1. Proje iskeletini oluştur (klasör yapısı)
2. `setup.py` — akıllı kurulum scripti:
   - OS algılama (Windows/macOS/Linux)
   - Python versiyon kontrolü (3.10+)
   - Doğru requirements dosyasını seçme
   - PyAudio kurulumu (macOS: brew install portaudio gerekir)
   - Playwright kurulumu
   - `.env` dosyası oluşturma (API key sorar)
   - macOS izinleri hakkında bilgilendirme (mikrofon, erişilebilirlik)
3. `requirements-base.txt` — ortak paketler
4. `requirements-win.txt` — Windows ekstra (comtypes, pycaw, win10toast, pygetwindow)
5. `requirements-mac.txt` — macOS ekstra (pyobjc-framework-Cocoa, pyobjc-framework-Quartz)
6. `.env.example` — template
7. `.gitignore` — hassas verileri koru (data/, .env, __pycache__)

**Cross-platform kurulum akışı:**
```
$ python setup.py

🔍 İşletim sistemi: macOS (Darwin 25.3.0)
🐍 Python: 3.12.0 ✓

📦 Bağımlılıklar kuruluyor...
   ├── Ortak paketler... ✓
   ├── macOS paketleri... ✓
   ├── PyAudio (portaudio gerekli)...
   │   └── brew install portaudio... ✓
   └── Playwright tarayıcıları... ✓

🔑 API Anahtarları:
   ├── Google Gemini API Key: sk-... ✓
   └── Anthropic API Key: sk-... ✓

✅ Kurulum tamamlandı!
   $ python main.py
```

### FAZ 2: Platform Soyutlama Katmanı (Gün 1 öğlen)

**Hedef:** Windows ve macOS'u tek arayüzle kullanmak.

**platform/base.py — Abstract Interface:**
```python
class PlatformBase(ABC):
    @abstractmethod
    def open_file(self, path: str): ...

    @abstractmethod
    def open_folder(self, path: str): ...

    @abstractmethod
    def get_volume(self) -> int: ...

    @abstractmethod
    def set_volume(self, level: int): ...

    @abstractmethod
    def send_notification(self, title: str, message: str): ...

    @abstractmethod
    def get_active_window(self) -> str: ...

    @abstractmethod
    def list_running_apps(self) -> list: ...

    @abstractmethod
    def activate_window(self, title: str) -> bool: ...

    @abstractmethod
    def get_default_browser(self) -> str: ...

    @abstractmethod
    def shutdown(self): ...

    @abstractmethod
    def sleep_display(self): ...
```

**platform/windows.py:**
- `open_file` → `os.startfile(path)`
- `set_volume` → comtypes + pycaw
- `send_notification` → win10toast
- `get_active_window` → pygetwindow
- `activate_window` → pygetwindow + PowerShell fallback
- `get_default_browser` → winreg ProgId okuma
- `sleep_display` → ctypes.windll.user32.SendMessageW

**platform/macos.py:**
- `open_file` → `subprocess.run(["open", path])`
- `set_volume` → `osascript -e "set volume output volume X"`
- `send_notification` → `osascript -e 'display notification...'`
- `get_active_window` → AppKit NSWorkspace veya osascript
- `activate_window` → `osascript -e 'tell app "X" to activate'`
- `get_default_browser` → LaunchServices
- `sleep_display` → `pmset displaysleepnow`

**platform/__init__.py:**
```python
import sys

if sys.platform == "win32":
    from .windows import WindowsPlatform as Platform
elif sys.platform == "darwin":
    from .macos import MacOSPlatform as Platform
else:
    raise RuntimeError("Desteklenmeyen OS")

platform = Platform()  # Tek global instance
```

### FAZ 3: Ses Motoru (Gün 1 öğleden sonra)

**Hedef:** Gemini ile sesli konuşma — Ali v1'den temizlenmiş versiyon.

**core/voice.py — Ali v1'den taşınacaklar:**
- Gemini 2.5 Flash native audio bağlantısı
- PyAudio 16kHz giriş / 24kHz çıkış
- VAD (ses algılama) ayarları
- Echo cancellation (_is_speaking flag)
- 60 saniye keepalive heartbeat
- Reconnect mantığı (bağlantı koptuğunda)

**Ali v1'den DEĞİŞECEKLER:**
- 7 Gemini tool → 2 tool:
  1. `quick_answer` — basit sorulara Gemini direkt cevap verir
  2. `claude_brain` — karmaşık her şey Claude'a gider
- Routing basitleştirilecek: "hukuk/dosya/araştırma/analiz" kelimeleri varsa → Claude, yoksa → Gemini direkt

### FAZ 4: Beyin (Claude Entegrasyonu) (Gün 1 akşam)

**Hedef:** Claude API çağrısı — basit, temiz, tek model.

**core/brain.py — Tamamen yeni yazım:**

**v1 vs v2 karşılaştırma:**
| Özellik | Ali v1 | Ali v2 |
|---------|--------|--------|
| Model | Haiku/Sonnet/Opus routing | Tek model: Claude Sonnet 4 |
| Tool loop | Max 8 tur | Max 4 tur |
| History | 20 mesaj deque | 10 mesaj |
| Prompt | 6KB + dinamik enjeksiyon | ~2KB sabit + minimal context |
| Dosya boyutu | 141KB, 3010 satır | ~300 satır hedef |
| Prompt kaynakları | prompt.txt + tool desc + memory + digest + workflow + gap + goals + case | Tek prompt.py |

**Neden tek model (Sonnet)?**
- Haiku/Sonnet/Opus routing = karmaşıklık + prompt çakışması
- Sonnet tek başına yeterli: hukuk analizi yapabilir, araç kullanabilir
- Opus gerçekten lazımsa ileride opsiyonel eklenebilir
- Token tasarrufu = kısa prompt + kısa history, model routing değil

**Tool kayıt sistemi:**
```python
# tools/__init__.py — otomatik araç keşfi
import importlib, pkgutil

def discover_tools():
    """tools/ altındaki tüm modülleri tarar, BaseTool subclass'larını bulur"""
    registry = {}
    for finder, name, _ in pkgutil.walk_packages(["tools"]):
        module = importlib.import_module(f"tools.{name}")
        for attr in dir(module):
            cls = getattr(module, attr)
            if isinstance(cls, type) and issubclass(cls, BaseTool) and cls != BaseTool:
                tool = cls()
                registry[tool.name] = tool
    return registry
```

```python
# tools/base.py — her araç bu yapıyı takip eder
class BaseTool:
    name: str           # "mevzuat_search"
    description: str    # Claude'a gönderilecek açıklama
    parameters: dict    # JSON Schema

    def run(self, **kwargs) -> str:
        """Aracı çalıştır, sonucu string olarak döndür"""
        raise NotImplementedError
```

**Brain akışı (basit):**
```
Kullanıcı sorusu
    ↓
System prompt (prompt.py'den) + conversation history (son 10)
    ↓
Claude Sonnet API çağrısı (tüm araçlarla)
    ↓
Cevap mı? → Kullanıcıya söyle
Tool çağrısı mı? → Aracı çalıştır → Sonucu Claude'a gönder → Tekrarla (max 4 tur)
    ↓
Son cevabı Gemini'ye ver → Sesli söylesin
```

### FAZ 5: Hukuk Araçları (Gün 2 sabah)

**Hedef:** Ali v1'deki hukuk araçlarını modüler yapıya taşımak.

**tools/legal/mevzuat_search.py:**
- Ali v1'deki `actions/mevzuat_mcp.py` temizlenip taşınacak
- MCP client: `actions/mcp_client.py`'deki retry/session mantığı korunacak
- Fallback: MCP çalışmazsa knowledge/ klasöründen local arama
- Endpoint: https://mevzuat.surucu.dev/mcp

**tools/legal/yargi_search.py:**
- Ali v1'deki `actions/yargi_mcp.py` temizlenip taşınacak
- Aynı MCP client altyapısını kullanacak
- Endpoint: https://yargimcp.fastmcp.app/mcp

**tools/legal/ceza_hesapla.py:**
- Ali v1'deki `actions/legal_tools.py` → `sentencing_calculator` fonksiyonu
- Ağırlaştırıcı/hafifletici nedenler, zincirleme suç, teşebbüs, iştirak
- Bu tamamen lokal hesaplama, API gerektirmez

**tools/legal/doc_generator.py:**
- Ali v1'deki `actions/legal_doc_forge.py` temizlenecek
- python-docx ile dilekçe, savunma, itiraz, bilirkişi raporu üretimi
- Şablonlar korunacak, cross-platform dosya açma (platform katmanı ile)

**tools/legal/deadline.py:**
- Ali v1'deki `actions/legal_deadline.py` temizlenecek
- Süre hesaplama (itiraz, temyiz, vs.)

**tools/legal/case_manager.py:**
- Ali v1'deki `actions/case_context.py` + `case_manager.py` birleştirilecek
- Dava bazlı context yönetimi

**knowledge/ klasörü:**
- Ali v1'den aynen kopyalanacak
- TCK, CMK, savunma teknikleri, UYAP rehberleri
- Bu dosyalar değişmeyecek

### FAZ 6: Bilgisayar Kontrol Araçları (Gün 2 öğlen)

**Hedef:** Cross-platform bilgisayar kontrolü.

**tools/computer/app_launcher.py:**
- Platform katmanını kullanarak uygulama açma
- Windows: `os.startfile` + `pygetwindow`
- macOS: `open -a "App Name"` + `osascript`

**tools/computer/file_ops.py:**
- Dosya oluşturma, okuma, taşıma, silme, arama
- Platform bağımsız (os, shutil, pathlib)
- `send2trash` ile güvenli silme (zaten cross-platform)

**tools/computer/browser.py:**
- Playwright CDP ile Chrome kontrolü
- Ali v1'deki `actions/browser_control.py`'den sadeleştirilmiş versiyon
- Tab yönetimi, içerik okuma, navigasyon
- UYAP özel timeout'ları korunacak

**tools/computer/screen.py:**
- mss ile ekran yakalama (zaten cross-platform)
- Gemini Vision ile analiz (Ali v1'deki gibi)
- PyAutoGUI ile mouse/keyboard (zaten cross-platform)

**tools/computer/system.py:**
- Platform katmanını kullanarak:
  - Ses seviyesi kontrolü
  - Bildirim gönderme
  - Ekran kapatma
  - Sistem bilgisi

### FAZ 7: UI (Gün 2 öğleden sonra)

**Hedef:** Temiz, basit masaüstü UI.

**CustomTkinter kullanılacak (zaten cross-platform).**

**Ali v1 UI'dan DEĞİŞECEKLER:**
- 63KB ui.py → küçük bileşenlere bölünecek
- Neural brain animasyonu → sadeleştirilecek veya kaldırılacak
- 42 araçlık tool rack → kategorize, temiz grid
- API key setup dialog → korunacak

**ui/app.py — Ana pencere:**
- Sol panel: Araç durumları (aktif/pasif gösterge)
- Orta: Konuşma log'u (chat geçmişi)
- Alt: Durum çubuğu (bağlantı, maliyet, model)
- İlk açılışta: Setup dialog (API key girişi)

**ui/components/setup_dialog.py — İlk kurulum:**
```
┌─────────────────────────────────────┐
│         ALI v2 - İlk Kurulum        │
│                                     │
│  Google Gemini API Key:             │
│  ┌─────────────────────────────┐    │
│  │ ****************************│    │
│  └─────────────────────────────┘    │
│                                     │
│  Anthropic API Key:                 │
│  ┌─────────────────────────────┐    │
│  │ ****************************│    │
│  └─────────────────────────────┘    │
│                                     │
│  [Test Et]              [Kaydet]    │
└─────────────────────────────────────┘
```

### FAZ 8: Entegrasyon + Test + Paketleme (Gün 2 akşam)

**Hedef:** Her şeyi birleştirip çalışır hale getirmek.

**main.py — Giriş noktası:**
```python
1. Platform algıla + doğrula
2. Config yükle (.env + settings.json)
3. İlk çalıştırma kontrolü → Setup dialog
4. Tool registry oluştur (otomatik keşif)
5. Brain başlat (Claude bağlantısı)
6. Voice başlat (Gemini audio)
7. UI başlat (CustomTkinter)
8. Ana döngü
```

**Test stratejisi:**
- Her tool kendi test dosyasına sahip
- MCP bağlantı testi (health check)
- Platform katmanı testi (OS-specific)
- Ses testi (mikrofon erişimi)

**Paketleme (ileride):**
- pyinstaller veya py2app ile tek dosya executable
- Windows: .exe installer
- macOS: .app bundle veya .dmg

---

## CROSS-PLATFORM STRATEJİ DETAYI

### Nasıl çalışacak?

Her platform-bağımlı işlem `platform/` katmanından geçecek. Uygulama kodu ASLA doğrudan `os.startfile`, `winreg`, `comtypes` çağırmayacak.

```python
# YANLIŞ (Ali v1 böyle yapıyordu):
import os
os.startfile(path)  # Sadece Windows'ta çalışır

# DOĞRU (Ali v2 böyle yapacak):
from platform import platform
platform.open_file(path)  # Windows'ta os.startfile, macOS'ta open komutu
```

### macOS özel notlar:

1. **Mikrofon izni:** macOS ilk çalıştırmada mikrofon izni sorar. Setup scripti bunu bilgilendirecek.
2. **Erişilebilirlik izni:** PyAutoGUI (mouse/keyboard kontrolü) için Sistem Ayarları > Gizlilik > Erişilebilirlik izni gerekir. Setup scripti bunu tespit edip kullanıcıyı yönlendirecek.
3. **PyAudio:** macOS'ta `brew install portaudio` gerekir. Setup scripti kontrol edip kuracak.
4. **Bildirimler:** `osascript -e 'display notification'` veya `terminal-notifier` kullanılacak.
5. **Ses kontrolü:** `osascript -e 'set volume output volume X'` ile yapılacak.

### Windows özel notlar:

1. Ali v1'deki tüm Windows kodu `platform/windows.py`'ye taşınacak
2. Mevcut çalışan mantık korunacak, sadece yerleşim değişecek
3. Windows kullanıcıları için hiçbir fonksiyon kaybı olmayacak

---

## SETUP.PY DETAYI

```python
# Akıllı kurulum scripti pseudocode:

1. OS algıla
2. Python versiyonu kontrol (>= 3.10)
3. pip upgrade
4. requirements-base.txt kur
5. if Windows:
       requirements-win.txt kur
   elif macOS:
       portaudio kontrol (yoksa brew install)
       requirements-mac.txt kur
6. playwright install (Chrome)
7. .env dosyası var mı?
   Yoksa:
       Gemini API key sor → .env'ye yaz
       Anthropic API key sor → .env'ye yaz
8. macOS ise:
       "Mikrofon izni gerekecek" uyarısı
       "Erişilebilirlik izni gerekecek (bilgisayar kontrolü için)" uyarısı
9. knowledge/ klasörünü kontrol et
10. "Kurulum tamamlandı! python main.py ile başlat" mesajı
```

---

## TOKEN / MALİYET OPTİMİZASYONU

Ali v1 neden çok token harcıyordu:
- 6KB system prompt her çağrıda gönderiliyor
- 20 mesaj history (çoğu gereksiz)
- 8 turlu tool loop (çoğu zaman 2-3 tur yeterli)
- 42 tool tanımı her çağrıda (gereksiz olanlar dahil)
- Haiku/Sonnet/Opus routing = 3x prompt hazırlama

Ali v2 nasıl tasarruf edecek:
- ~2KB system prompt (üçte bir)
- 10 mesaj history
- Max 4 tur tool loop
- Sadece ilgili araçlar gönderilecek (hukuk sorusu → hukuk araçları)
- Tek model = tek prompt hazırlama
- Tahmini tasarruf: **%50-60 daha az token**

---

## ZAMAN ÇİZELGESİ

| Faz | İçerik | Süre |
|-----|--------|------|
| 1 | Altyapı + Setup | ~2 saat |
| 2 | Platform katmanı | ~2 saat |
| 3 | Ses motoru | ~2 saat |
| 4 | Beyin (Claude) | ~3 saat |
| 5 | Hukuk araçları | ~3 saat |
| 6 | Bilgisayar kontrol | ~2 saat |
| 7 | UI | ~3 saat |
| 8 | Entegrasyon + Test | ~3 saat |
| **TOPLAM** | | **~20 saat** |

Not: Bu süre kesintisiz çalışma varsayar. Gerçekte hatalar, debug,
API sorunları ile 2-3 gün sürebilir. Ama Ali v1'deki gibi haftalarca
sürmeyecek çünkü mimari BAŞTAN doğru kurulmuş olacak.

---

## GÜVENLİK

1. **Hassas veri ASLA repo'da olmayacak** — .gitignore kesin
2. **API key'ler sadece .env'de** — .env.example template olarak
3. **Şifreleme opsiyonel** — Ali v1'deki AES-256 mekanizma isteğe bağlı
4. **KVKK uyumu** — müşteri verileri local kalacak, dışarı gönderilmeyecek
5. **Audit trail** — güvenli, ama repo'ya commit edilmeyecek
