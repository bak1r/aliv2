# UYAP Is Akislari — Adim Adim Rehber

## 1. Dosya Numarasi ile Dava Arama

### Manuel Islem
1. https://vatandas.uyap.gov.tr adresine gidin (veya avukat portali: https://avukat.uyap.gov.tr)
2. e-Devlet veya e-Imza ile giris yapin
3. Ana menuden **"Dava Sorgulama"** bolumune girin
4. Arama formunu doldurun:
   - **Mahkeme Turu:** Ornegin "Asliye Ceza Mahkemesi"
   - **Mahkeme Adi:** Ornegin "Istanbul 5. Asliye Ceza Mahkemesi"
   - **Esas Yili:** Ornegin "2025"
   - **Esas Sira No:** Ornegin "12345"
5. **"Sorgula"** butonuna tiklayin
6. Sonuc listesinden ilgili davayi secin
7. Dosya detay sayfasi acilir

### Browser Automation Adimlari
```
Adim 1: navigate_to("https://vatandas.uyap.gov.tr/DavaSorgulama")
Adim 2: wait_for_element("#mahkemeTuru")
Adim 3: select_dropdown("#mahkemeTuru", "Asliye Ceza Mahkemesi")
Adim 4: fill_input("#mahkemeAdi", "Istanbul 5. Asliye Ceza Mahkemesi")
Adim 5: fill_input("#esasYili", "2025")
Adim 6: fill_input("#esasSiraNo", "12345")
Adim 7: click("#sorgulaBtn")
Adim 8: wait_for_element("#sonucTablosu")
Adim 9: extract_text("#sonucTablosu") → sonuclari parse et
```

### Dikkat Edilecekler
- Mahkeme adi dogru yazilmali (buyuk/kucuk harf duyarli olabilir)
- Esas yili 4 haneli olmalidir
- Bazi mahkemeler "Degisik Is" numarasi kullanir — bu durumda farkli form alani secilmeli

---

## 2. Dava Evraklarini Indirme

### Manuel Islem
1. Dava dosyasi detay sayfasini acin (Adim 1'deki arama sonucundan)
2. **"Evraklar"** sekmesine tiklayin
3. Evrak listesi goruntulenir:
   - Dava dilekce
   - Savunma dilekcesi
   - Bilirkisi raporlari
   - Durusma tutanaklari
   - Ara kararlar
   - Nihai karar
4. Indirmek istediginiz evrakin yanindaki **"Indir"** ikonuna tiklayin
5. Dosya UDF formatinda indirilir
6. PDF'ye donusturmek icin UDF Viewer kullanin veya tarayicida "PDF olarak kaydet" secin

### Browser Automation Adimlari
```
Adim 1: navigate_to("{dosya_detay_url}")
Adim 2: click("#evraklarTab")
Adim 3: wait_for_element(".evrak-listesi")
Adim 4: extract_text(".evrak-listesi") → evrak listesini al
Adim 5: # Her evrak icin:
         click(".evrak-row[data-id='{evrak_id}'] .indir-btn")
Adim 6: wait_for_download() → dosya indirilir
Adim 7: Kullaniciya indirilen dosyalari raporla
```

### Toplu Indirme
- Bazi sayfalarda **"Tumunu Indir"** secenegi bulunur
- Buyuk dosyalar icin internet baglantisinin kararli olmasi onemlidir
- Indirilen UDF dosyalari `output/` klasorune kaydedilebilir

---

## 3. Durusma Tarihlerini Kontrol Etme

### Manuel Islem
1. Dava dosyasi detay sayfasini acin
2. **"Durusmalar"** sekmesine tiklayin
3. Asagidaki bilgiler listelenir:
   - **Durusma tarihi ve saati**
   - **Salon numarasi**
   - **Durusma turu:** Ilk durusma, ara durusma, karar durusmasi
   - **Durusma gundemi:** Yapilacak islemler
4. Gelecek durusmalar ust siradadir
5. Gecmis durusmalarin tutanaklari "Goruntule" butonu ile okunabilir

### Browser Automation Adimlari
```
Adim 1: navigate_to("{dosya_detay_url}")
Adim 2: click("#durusmalarTab")
Adim 3: wait_for_element(".durusma-listesi")
Adim 4: extract_text(".durusma-listesi") → tum durusma bilgilerini al
Adim 5: Parse et:
         - tarih: ".durusma-tarih"
         - saat: ".durusma-saat"
         - salon: ".durusma-salon"
         - gundem: ".durusma-gundem"
Adim 6: Takvime ekle (calendar.json)
Adim 7: Kullaniciya rapor et ve hatirlatici olustur
```

### Otomatik Takvim Entegrasyonu
Ali, durusma tarihlerini tespit ettiginde:
1. `memory/calendar.json` dosyasina kaydeder
2. Kullaniciya gelecek durusma tarihini bildirir
3. 1 gun oncesine hatirlatici olusturur

---

## 4. Elektronik Dilekce Gonderme

### Onkosullar
- **Avukat portali** uzerinden giris yapilmis olmali (https://avukat.uyap.gov.tr)
- **e-Imza** veya **Mobil Imza** zorunlu
- Dilekce PDF veya Word formatinda hazir olmali
- Harc tutari onceden hesaplanmis olmali

### Manuel Islem
1. Avukat portaline e-Imza ile giris yapin
2. Sol menuden **"Dilekce Gonder"** secin
3. **Dosya bilgilerini girin:**
   - Mahkeme adi
   - Esas numarasi
   - Dilekce turu (savunma dilekcesi, itiraz dilekcesi, beyan dilekcesi vb.)
4. **Dilekceyi yukleyin:**
   - "Dosya Sec" butonuna tiklayin
   - Hazirladiginiz dilekceyi secin (PDF/Word)
   - Ekleri varsa ayri ayri yukleyin
5. **On izleme yapin:**
   - Yuklenen belgeyi kontrol edin
   - Taraf bilgilerini dogrulayin
6. **e-Imza ile imzalayin:**
   - "Imzala ve Gonder" butonuna tiklayin
   - e-Imza PIN kodunu girin
   - Imzalama islemini onaylayin
7. **Harc odemesi (gerekiyorsa):**
   - Sistem otomatik olarak harc tutarini gosterir
   - Kredi karti veya banka karti ile odeyin
8. **Onay ekrani:**
   - Gonderim tarihi ve saati kayit altina alinir
   - Evrak numarasi verilir
   - Bu numarayi not alin

### Browser Automation Adimlari (Kismi Otomasyon)
```
Adim 1: navigate_to("https://avukat.uyap.gov.tr/DilekceGonder")
Adim 2: fill_input("#mahkemeAdi", "{mahkeme}")
Adim 3: fill_input("#esasNo", "{esas_no}")
Adim 4: select_dropdown("#dilekceTuru", "{dilekce_turu}")
Adim 5: upload_file("#dosyaSec", "{dilekce_dosya_yolu}")
Adim 6: # BURADA DURAKLA — e-Imza islemleri icin kullanici onayı gerekir
         notify_user("Dilekce yuklendi. Lutfen e-Imza ile imzalayip gonderin.")
Adim 7: # Kullanici e-Imza PIN girer ve gonderimi onaylar
Adim 8: wait_for_element(".onay-mesaji")
Adim 9: extract_text(".onay-mesaji") → gonderim onayini al
```

### Onemli Uyarilar
- **e-Imza adimi otomatiklestirilemez** — guvenlik gerekcesinle kullanici manuel yapmalidirr
- Dilekce gonderim saati resmi kayittir; mesai saati disinda da gonderilebilir
- Sure hesabinda gonderim tarihi esas alinir (saat 00:00'a kadar gonderilmis sayilir)
- Harc odenmeden dilekce isleme alinmaz

---

## 5. Dava Durumu Kontrolu

### Manuel Islem
1. Dava dosyasi detay sayfasini acin
2. **"Genel Bilgiler"** sekmesinde asagidaki bilgiler yer alir:
   - **Dava durumu:** Devam ediyor / Karar verildi / Kesinlesti / Dusuruldu
   - **Son islem:** En son yapilan islem ve tarihi
   - **Safahat:** Davanin tum asamalari kronolojik sirayla
3. **"Safahat"** sekmesine tiklayin (detayli kronoloji icin)
4. Her islem adimi icin tarih, islem turu ve aciklama goruntulenir

### Browser Automation Adimlari
```
Adim 1: navigate_to("{dosya_detay_url}")
Adim 2: wait_for_element("#genelBilgiler")
Adim 3: extract_text("#davaDurumu") → mevcut durum
Adim 4: extract_text("#sonIslem") → son islem bilgisi
Adim 5: click("#safahatTab")
Adim 6: extract_text(".safahat-listesi") → tum kronoloji
Adim 7: Parse et ve kullaniciya ozet rapor sun
```

### Durum Kodlari
| Kod | Anlami | Aciklama |
|-----|--------|----------|
| Devam Ediyor | Dava sureci aktif | Durusmalar devam ediyor |
| Karar Verildi | Ilk derece karari cikmis | Istinaf/temyiz suresi baslamis |
| Istinaf Asamasinda | BAM'a tasinmis | Bolge Adliye Mahkemesi inceliyor |
| Temyiz Asamasinda | Yargitay'a tasinmis | Yargitay inceliyor |
| Kesinlesti | Karar kesinlesmis | Infaz asamasina gecilmis |
| Dusuruldu | Dava dusurulmus | Suresinde sikayet yapilmamis vb. |
| Birlestirildi | Baska dosyayla birlesmis | Yeni dosya no'su verilir |

---

## 6. Karar Indirme

### Manuel Islem
1. Dava dosyasi detay sayfasini acin
2. **"Kararlar"** sekmesine tiklayin
3. Karar listesi goruntulenir:
   - **Ara kararlar:** Durusma sirasinda verilen kararlar
   - **Nihai karar (gerekce):** Davanin sonucunu belirleyen karar
   - **Ek kararlar:** Tavzih, duzeltme kararlari
4. Indirmek istediginiz kararin yanindaki **"Indir"** butonuna tiklayin
5. Karar UDF formatinda indirilir
6. **"PDF Olarak Indir"** secenegi varsa dogrudan PDF alinabilir
7. Karar metnini analiz icin `knowledge_search` veya `defense_analyzer` aracina aktarin

### Browser Automation Adimlari
```
Adim 1: navigate_to("{dosya_detay_url}")
Adim 2: click("#kararlarTab")
Adim 3: wait_for_element(".karar-listesi")
Adim 4: extract_text(".karar-listesi") → karar listesini al
Adim 5: # Nihai karar icin:
         click(".karar-row.nihai .indir-btn")
Adim 6: wait_for_download() → UDF dosyasi indirilir
Adim 7: # PDF'ye donustur (mumkunse)
         click(".karar-row.nihai .pdf-indir-btn")
Adim 8: Karar metnini oku ve analiz et
```

### Karar Analizi Is Akisi
Karar indirildikten sonra Ali ile analiz:
1. Karar metnini oku → `file_controller` ile dosyayi ac
2. Hukum fikrasini cikart → metin analizi
3. Uygulanan kanun maddelerini tespit et → `knowledge_search` ile karsilastir
4. Emsal deger analizi yap → `yargi_ara` ile benzer kararlari bul
5. Itiraz/istinaf noktalari belirle → `defense_analyzer` ile degerlendir
6. Rapor olustur → `legal_tools` ile PDF rapor uret

---

## Genel Browser Automation Notlari

### Oturum Yonetimi
- UYAP oturumu yaklasik **20 dakika** islem yapilmazsa kapanir
- Otomasyon sirasinda oturum suresi dolabilir — `wait_for_element` ile kontrol edin
- Oturum kapandiysa kullaniciya bildir ve yeniden giris isteyin

### Hata Yonetimi
```
Oturum Hatasi:
  → "Oturumunuz sona ermistir" mesaji alindiysa
  → Kullaniciya bildir: "UYAP oturumu kapanmis. Lutfen yeniden giris yapin."

Element Bulunamadi:
  → Sayfa yapisinde degisiklik olabilir
  → Alternatif secicleri dene (id, class, xpath)
  → Basarisizsa kullaniciya bildir

Zaman Asimi:
  → UYAP sunuculari yogun saatlerde yavas olabilir
  → Bekleme suresini artir (timeout: 30 saniye)
  → Ogleden sonra 14:00-16:00 arasi en yogun saatlerdir
```

### Guvenlik Kurallari
1. **e-Imza PIN kodunu ASLA kaydetme veya loglama** — her islemde kullanicidan iste
2. **Kisisel verileri (TC kimlik no) loglamay** — sadece islem sirasinda kullan
3. **Oturum bilgilerini saklamay** — her seferinde yeni giris yap
4. **CAPTCHA'yi otomatik cozmeye calisma** — kullaniciya yonlendir
5. **UYAP'in kullanim kosullarini ihlal etme** — asiri talep gondermekten kacin

### Performans Ipuclari
- Sorgulari mumkun oldugunca spesifik yapin (mahkeme + esas no)
- Toplu islemler arasinda 2-3 saniye bekleyin (rate limiting)
- Buyuk dosyalari indirirken baglanti kontrolu yapin
- Islem sonuclarini yerel olarak onbellekleyin (ayni sorguyu tekrarlamamak icin)
