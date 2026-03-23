# UYAP Rehberi — Ulusal Yargi Agi Projesi

## UYAP Nedir?

UYAP (Ulusal Yargi Agi Projesi), Turkiye Cumhuriyeti Adalet Bakanligi tarafindan gelistirilen ve yonetilen elektronik yargi sistemidir. Tum yargi birimleri (mahkemeler, savciliklar, icra daireleri, noterler) bu sistem uzerinden birbirine baglidir.

UYAP sayesinde:
- Dava dosyalari elektronik ortamda tutulur
- Durusma tutanaklari, kararlar ve tebligatlar dijital olarak olusturulur
- Avukatlar ve vatandaslar islemlerini internet uzerinden yapabilir
- Harc odemeleri online gerceklestirilebilir

## Web Portalleri

### Vatandas Portali
- **URL:** https://vatandas.uyap.gov.tr
- **Erisim:** e-Devlet (turkiye.gov.tr) uzerinden giris
- **Kimlik dogrulama:** T.C. Kimlik No + e-Devlet sifresi veya e-Imza
- **Islevler:** Dava sorgulama, dosya detay goruntuleme, tebligat takibi

### Avukat Portali
- **URL:** https://avukat.uyap.gov.tr
- **Erisim:** e-Imza veya Mobil Imza zorunlu
- **Kimlik dogrulama:** Baro sicil numarasi + e-Imza/Mobil Imza
- **Islevler:** Tam kapsamli dava yonetimi, dilekce gonderme, harc odeme, dosya indirme

### e-Devlet Giris Gereksinimleri
1. Aktif e-Devlet hesabi (turkiye.gov.tr)
2. e-Imza sertifikasi (avukatlar icin zorunlu) veya Mobil Imza
3. Guncel tarayici (Chrome, Firefox, Edge onerilen)
4. Java Runtime Environment (bazi islemler icin gerekli olabilir)
5. UYAP destekli e-Imza uygulamasi (ArkSigner, E-Guven vb.)

## Ana Bolumler

### 1. Dava Sorgulama
Acik davalari cesitli kriterlere gore arama imkani saglar:
- **Dosya No ile arama:** Mahkeme adi + esas yili + esas sira no
- **T.C. Kimlik No ile arama:** Taraf oldugu tum davalar listelenir
- **Avukat baro no ile arama:** Vekaletname girilen tum dosyalar
- **Anahtar kelime ile arama:** Dava konusu, taraf adi vb.

### 2. Dosya Detay
Secilen dava dosyasinin tum detaylari:
- **Taraflar:** Davaci, davali, mudahil, vekiller
- **Durusma takvimi:** Gecmis ve gelecek durusma tarihleri
- **Evraklar:** Dilekce, bilirkisi raporu, tutanak, karar
- **Harc bilgileri:** Odenen ve bekleyen harclar
- **Tebligat durumu:** Gonderi durumu, teblig tarihi

### 3. Karar Sorgulama
Mahkeme kararlarini sorgulama ve indirme:
- **Karar metni:** Tam metin goruntuleme
- **Karar ozeti:** Hukum fikrasi
- **Kesinlesme durumu:** Istinaf/temyiz sureci
- **Karar indirme:** PDF veya UDF formatinda

### 4. Tebligat
Elektronik tebligat takip sistemi:
- **Gelen tebligatlar:** Mahkemelerden gelen bildirimler
- **Teblig tarihi:** 5 gun icerisinde acilmasi gerekir (acilmazsa 5. gun teblig edilmis sayilir)
- **Tebligat gecmisi:** Tum tebligat kayitlari
- **Onemli:** Elektronik tebligat surelerini kacirmak hak kaybina yol acar

### 5. Harc Odeme
Online harc ve masraf islemleri:
- **Yargilama harci:** Dava acma, temyiz, istinaf harclari
- **Vekalet harci:** Avukat atama harci
- **Bilirkisi ucreti:** Bilirkisi ucret yatirma
- **Odeme yontemleri:** Kredi karti, banka karti, havale/EFT

## UDF Formati (UYAP Document Format)

### UDF Nedir?
UDF (UYAP Document Format), UYAP sistemi tarafindan kullanilan ozel bir belge formatidir. Mahkeme kararlari, dilekce ornekleri ve resmi yazilar bu formatta saklanir.

### UDF Ozellikleri
- **Dijital imzali:** Belgenin orijinalligini garanti eder
- **Salt okunur:** Icerik degistirilemez
- **e-Imza dogrulamali:** Belgeyi imzalayan hakimin/katiplerin kimligi dogrulanabilir
- **Tarih damgali:** Belgenin olusturulma tarihi ve saati kayitlidir

### UDF'yi PDF'ye Donusturme
1. **UYAP Editoru ile:** UYAP portalindeki "Belge Goruntule" butonu ile acin, "PDF Olarak Kaydet" secin
2. **UDF Viewer uygulamasi ile:** Adalet Bakanligi'nin resmi UDF goruntuleyicisini indirin
3. **Tarayici uzerinden:** Belgeyi tarayicida acip "Yazdir > PDF olarak kaydet" secin
4. **Not:** Dijital imza bilgileri PDF donusumunde kaybolabilir; resmi islemlerde UDF orijinali kullanilmalidir

## Yaygin Islemler

### Dava Arama
1. UYAP portaline giris yapin
2. Sol menuden "Dava Sorgulama" secin
3. Arama kriterlerini girin (dosya no, TC kimlik no, veya taraf adi)
4. "Sorgula" butonuna tiklayin
5. Sonuclardan ilgili davayi secin

### Belge Indirme
1. Dosya detay sayfasina gidin
2. "Evraklar" sekmesine tiklayin
3. Indirmek istediginiz belgeyi secin
4. "Indir" veya "Goruntule" butonuna tiklayin
5. Dosya UDF veya PDF formatinda indirilir

### Durusma Takvimi Kontrolu
1. Dosya detay sayfasina gidin
2. "Durusmalar" sekmesine tiklayin
3. Gelecek durusma tarihleri listelenir
4. Durusma saati, salon bilgisi ve gundemi goruntulenir

## Browser Control ile Otomasyon Ipuclari

Ali'nin `browser_control` araci ile UYAP islemleri otomatiklestirilebilir:

### Onkosullar
- Kullanici onceden e-Devlet/UYAP oturumunu acmis olmalidir
- Tarayici penceresi acik ve UYAP portalinde olmalidir
- e-Imza dongle'i takili olmalidir (avukat islemleri icin)

### Otomatiklestirilebilir Islemler
- **Dava sorgulama:** Dosya numarasi ile otomatik arama
- **Durusma tarihi kontrolu:** Belirli dosyalarin durusma tarihlerini cekme
- **Belge listesi alma:** Dosyadaki tum evraklarin listesini cikartma
- **Karar metni okuma:** Karar icerigini cekip analiz etme

### Otomatiklestirilemeyecek Islemler
- **e-Imza gerektiren islemler:** Dilekce gonderme, harc odeme (kullanici onayı gerekir)
- **Ilk giris:** e-Devlet kimlik dogrulama (guvenlik nedeniyle manuel yapilmali)
- **CAPTCHA:** Bazi sayfalarda CAPTCHA dogrulamasi gerekebilir

### Ornek Kullanim
```
browser_control ile:
1. navigate_to: "https://vatandas.uyap.gov.tr/DavaSorgulama"
2. fill_form: {"dosya_no": "2025/12345", "mahkeme": "Istanbul 5. Asliye Ceza"}
3. click: "Sorgula"
4. extract_text: "#sonuclar" → dava bilgilerini al
5. Sonuclari kullaniciya raporla
```

## Onemli Uyarilar

1. **Sure takibi kritiktir:** Tebligat surelerini kacirmak telafisi olmayan hak kayiplarina yol acar
2. **e-Imza guvenceligi:** e-Imza PIN kodunu kimseyle paylasmayiniz
3. **Oturum suresi:** UYAP oturumu belirli bir sure sonra otomatik kapanir; uzun islemlerde dikkatli olun
4. **Sistem bakim saatleri:** Genellikle gece 00:00-06:00 arasi bakim yapilabilir
5. **Yedekleme:** Indirilen belgelerin yerel yedegini alin; UYAP'tan silinmis belgelere tekrar erisilemeyebilir
6. **Tarayici uyumlulugu:** Chrome veya Edge tarayicilarin guncel surumlerini kullanin
