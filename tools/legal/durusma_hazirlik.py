"""Durusma Hazirlik Araci — Durusma oncesi kontrol listesi ve hazirlik yonetimi."""

from __future__ import annotations

from datetime import datetime
from tools.base import BaseTool
from core.database import get_db

# Standart kontrol listesi sablonlari
SABLONLAR = {
    "ceza": {
        "ad": "Ceza Davasi Durusma Hazirlik",
        "maddeler": [
            {"madde": "Iddianame / esas hakkindaki mutalaanin incelenmesi", "kategori": "belge"},
            {"madde": "Tanik listesi ve ifadelerinin gozden gecirilmesi", "kategori": "belge"},
            {"madde": "Delil listesinin kontrolu (dijital, fiziki)", "kategori": "belge"},
            {"madde": "Bilirkisi raporlarinin incelenmesi", "kategori": "belge"},
            {"madde": "Emsal kararlarin arastirilmasi", "kategori": "arastirma"},
            {"madde": "Savunma stratejisinin belirlenmesi", "kategori": "strateji"},
            {"madde": "Muvekil ile gorusme ve bilgilendirme", "kategori": "iletisim"},
            {"madde": "Tanik sorularinin hazirlanmasi", "kategori": "strateji"},
            {"madde": "Vekaletname gecerliligi kontrolu", "kategori": "belge"},
            {"madde": "Onceki durusma tutanaklarinin okunmasi", "kategori": "belge"},
            {"madde": "UYAP uzerinden dosya guncelleme kontrolu", "kategori": "sistem"},
            {"madde": "Durusma saati ve mahkeme salonu teyidi", "kategori": "lojistik"},
        ],
    },
    "hukuk": {
        "ad": "Hukuk Davasi Durusma Hazirlik",
        "maddeler": [
            {"madde": "Dilekce ve cevaplarin gozden gecirilmesi", "kategori": "belge"},
            {"madde": "Delil listesi ve eklerinin kontrolu", "kategori": "belge"},
            {"madde": "Bilirkisi raporunun incelenmesi", "kategori": "belge"},
            {"madde": "Tanik listesi ve beyanlarinin hazirlanmasi", "kategori": "belge"},
            {"madde": "Emsal karar arastirmasi", "kategori": "arastirma"},
            {"madde": "Islah dilekce taslagi (gerekiyorsa)", "kategori": "belge"},
            {"madde": "Karsi taraf beyanlarinin analizi", "kategori": "arastirma"},
            {"madde": "Muvekil ile gorusme ve bilgilendirme", "kategori": "iletisim"},
            {"madde": "Hesap raporu / uzman gorusu kontrolu", "kategori": "belge"},
            {"madde": "Vekaletname gecerliligi kontrolu", "kategori": "belge"},
            {"madde": "UYAP dosya guncelleme kontrolu", "kategori": "sistem"},
            {"madde": "Durusma saati ve salon teyidi", "kategori": "lojistik"},
        ],
    },
    "icra": {
        "ad": "Icra Durusmasi / Islemleri Hazirlik",
        "maddeler": [
            {"madde": "Icra dosyasi ve takip bilgilerinin kontrolu", "kategori": "belge"},
            {"madde": "Borclu mal varliginin arastirilmasi (tapu, trafik, banka)", "kategori": "arastirma"},
            {"madde": "Haciz / satis talep dilekceleri", "kategori": "belge"},
            {"madde": "Faiz hesabi guncellemesi", "kategori": "hesap"},
            {"madde": "Tebligat durumlarinin kontrolu", "kategori": "belge"},
            {"madde": "Odeme / itiraz surelerinin kontrolu", "kategori": "sure"},
            {"madde": "Muvekil bilgilendirme", "kategori": "iletisim"},
            {"madde": "Masraf beyani hazirlanmasi", "kategori": "hesap"},
        ],
    },
    "idari": {
        "ad": "Idari Dava Durusma Hazirlik",
        "maddeler": [
            {"madde": "Idari islem dosyasinin incelenmesi", "kategori": "belge"},
            {"madde": "Dava ve savunma dilekceleri kontrolu", "kategori": "belge"},
            {"madde": "Emsal Danistay / BIM kararlari arastirmasi", "kategori": "arastirma"},
            {"madde": "Bilirkisi raporu incelemesi", "kategori": "belge"},
            {"madde": "Yurutmenin durdurulmasi talebi degerlendirmesi", "kategori": "strateji"},
            {"madde": "Muvekil / idare ile gorusme", "kategori": "iletisim"},
            {"madde": "UYAP dosya guncelleme kontrolu", "kategori": "sistem"},
            {"madde": "Durusma saati ve salon teyidi", "kategori": "lojistik"},
        ],
    },
}


class DurusmaHazirlikTool(BaseTool):
    name = "durusma_hazirlik"
    description = (
        "Durusma oncesi hazirlik kontrol listesi. Sablon olusturma (ceza, hukuk, icra, idari), "
        "madde ekleme/tamamlama, hazirlik durumu takibi ve ozel kontrol listesi yonetimi."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: create | list | check | uncheck | add_item | status | templates | delete",
                "enum": ["create", "list", "check", "uncheck", "add_item", "status", "templates", "delete"],
            },
            "sablon": {
                "type": "string",
                "description": "Sablon turu: ceza | hukuk | icra | idari (create islemi icin)",
            },
            "dava_no": {
                "type": "string",
                "description": "Dava/esas numarasi",
            },
            "durusma_tarihi": {
                "type": "string",
                "description": "Durusma tarihi (GG.AA.YYYY)",
            },
            "madde_no": {
                "type": "number",
                "description": "Kontrol listesi madde numarasi (check/uncheck icin, 1'den baslar)",
            },
            "yeni_madde": {
                "type": "string",
                "description": "Eklenecek yeni kontrol maddesi (add_item icin)",
            },
            "hazirlik_id": {
                "type": "string",
                "description": "Hazirlik listesi ID'si",
            },
            "not_": {
                "type": "string",
                "description": "Maddeye eklenecek not (check islemi ile birlikte)",
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str = "",
        sablon: str = "",
        dava_no: str = "",
        durusma_tarihi: str = "",
        madde_no: int = 0,
        yeni_madde: str = "",
        hazirlik_id: str = "",
        not_: str = "",
        **kw,
    ) -> str:
        action = action.strip().lower()
        if action == "create":
            return self._create(sablon, dava_no, durusma_tarihi)
        elif action == "list":
            return self._list(dava_no, hazirlik_id)
        elif action == "check":
            return self._toggle(hazirlik_id, dava_no, madde_no, True, not_)
        elif action == "uncheck":
            return self._toggle(hazirlik_id, dava_no, madde_no, False, "")
        elif action == "add_item":
            return self._add_item(hazirlik_id, dava_no, yeni_madde)
        elif action == "status":
            return self._status(hazirlik_id, dava_no)
        elif action == "templates":
            return self._templates()
        elif action == "delete":
            return self._delete(hazirlik_id, dava_no)
        else:
            return f"Bilinmeyen islem: {action}. Gecerli: create, list, check, uncheck, add_item, status, templates, delete"

    def _create(self, sablon: str, dava_no: str, durusma_tarihi: str) -> str:
        if not dava_no:
            return "Dava numarasi belirtilmedi."
        sablon = (sablon or "hukuk").strip().lower()
        if sablon not in SABLONLAR:
            return f"Gecersiz sablon: {sablon}. Gecerli: {', '.join(SABLONLAR.keys())}"

        db = get_db()
        sablon_data = SABLONLAR[sablon]

        # Find dava_id
        dava_id = None
        dava = db.dava_bul_by_no(dava_no.strip())
        if dava:
            dava_id = dava["id"]

        # Find or create durusma_id
        durusma_id = None
        if durusma_tarihi:
            dt = self._parse_date(durusma_tarihi)
            if dt:
                durusma_id = db.durusma_ekle(
                    dava_id=dava_id,
                    tarih=dt.strftime("%Y-%m-%d"),
                    saat="",
                    notlar=f"hazirlik:{sablon}",
                )

        # Create items
        maddeler = []
        for i, m in enumerate(sablon_data["maddeler"], 1):
            madde_id = db.hazirlik_ekle(
                dava_id=dava_id,
                durusma_id=durusma_id,
                madde=m["madde"],
                tamamlandi=0,
            )
            maddeler.append({"no": i, "madde": m["madde"], "kategori": m["kategori"], "id": madde_id})

        lines = [
            f"DURUSMA HAZIRLIK LISTESI OLUSTURULDU",
            f"{'='*50}",
            f"Dava No: {dava_no}",
            f"Sablon: {sablon_data['ad']}",
            f"Durusma Tarihi: {durusma_tarihi or 'Belirtilmedi'}",
            f"Madde Sayisi: {len(maddeler)}",
            "",
        ]
        for m in maddeler:
            lines.append(f"  [ ] {m['no']}. {m['madde']} ({m['kategori']})")

        return "\n".join(lines)

    def _list(self, dava_no: str, hazirlik_id: str) -> str:
        db = get_db()

        dava_id = None
        if dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                dava_id = dava["id"]

        maddeler = db.hazirlik_listele(dava_id=dava_id)
        if not maddeler:
            return "Kayitli hazirlik listesi bulunmuyor." if not dava_no else "Eslesen hazirlik listesi bulunamadi."

        tamamlanan = sum(1 for m in maddeler if m["tamamlandi"])
        toplam = len(maddeler)
        oran = (tamamlanan / toplam * 100) if toplam > 0 else 0

        dava_no_display = maddeler[0].get("dava_no") or dava_no or "-"
        lines = [
            f"\nDurusma Hazirlik — Dava: {dava_no_display}",
            f"  Ilerleme: {tamamlanan}/{toplam} ({oran:.0f}%)",
            f"  {'='*45}",
        ]
        for i, m in enumerate(maddeler, 1):
            check = "[x]" if m["tamamlandi"] else "[ ]"
            lines.append(f"  {check} {i}. [{m['id']}] {m['madde']}")

        return "\n".join(lines)

    def _toggle(self, hazirlik_id: str, dava_no: str, madde_no: int, durum: bool, not_: str) -> str:
        if not madde_no:
            return "Madde numarasi belirtilmedi."

        db = get_db()
        dava_id = None
        if dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                dava_id = dava["id"]

        maddeler = db.hazirlik_listele(dava_id=dava_id)
        if not maddeler:
            return "Hazirlik listesi bulunamadi. dava_no belirtin."

        madde_no = int(madde_no)
        if madde_no < 1 or madde_no > len(maddeler):
            return f"Madde {madde_no} bulunamadi."

        target = maddeler[madde_no - 1]
        db.hazirlik_guncelle(target["id"], tamamlandi=1 if durum else 0)

        # Recalculate progress
        maddeler = db.hazirlik_listele(dava_id=dava_id)
        tamamlanan = sum(1 for m in maddeler if m["tamamlandi"])
        toplam = len(maddeler)
        oran = int(tamamlanan / toplam * 100) if toplam > 0 else 0

        durum_str = "TAMAMLANDI" if durum else "GERI ALINDI"
        return (
            f"Madde {madde_no} {durum_str}: {target['madde']}\n"
            f"Ilerleme: {tamamlanan}/{toplam} ({oran}%)"
        )

    def _add_item(self, hazirlik_id: str, dava_no: str, yeni_madde: str) -> str:
        if not yeni_madde:
            return "Eklenecek madde belirtilmedi."

        db = get_db()
        dava_id = None
        if dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                dava_id = dava["id"]

        new_id = db.hazirlik_ekle(
            dava_id=dava_id,
            durusma_id=None,
            madde=yeni_madde.strip(),
            tamamlandi=0,
        )

        return f"Madde eklendi: [{new_id}] {yeni_madde}"

    def _status(self, hazirlik_id: str, dava_no: str) -> str:
        db = get_db()
        dava_id = None
        if dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                dava_id = dava["id"]

        maddeler = db.hazirlik_listele(dava_id=dava_id)
        if not maddeler:
            return "Kayitli hazirlik listesi bulunmuyor." if not dava_no else "Eslesen hazirlik listesi bulunamadi."

        tamamlanan = sum(1 for m in maddeler if m["tamamlandi"])
        toplam = len(maddeler)
        oran = (tamamlanan / toplam * 100) if toplam > 0 else 0

        eksikler = [m for m in maddeler if not m["tamamlandi"]]
        status_label = "HAZIR" if oran == 100 else "DEVAM EDIYOR" if oran > 50 else "BASLANMADI" if oran == 0 else "ERKEN ASAMADA"

        dava_no_display = maddeler[0].get("dava_no") or dava_no or "-"
        lines = [
            "DURUSMA HAZIRLIK DURUMU", "=" * 50,
            f"\nDava: {dava_no_display}",
            f"  Durum: {status_label}",
            f"  Ilerleme: {tamamlanan}/{toplam} ({oran:.0f}%)",
        ]

        if eksikler:
            lines.append(f"  Eksik Maddeler ({len(eksikler)}):")
            for i, m in enumerate(eksikler, 1):
                lines.append(f"    - [{m['id']}] {m['madde']}")

        return "\n".join(lines)

    def _templates(self) -> str:
        lines = ["DURUSMA HAZIRLIK SABLONLARI", "=" * 50]
        for key, sablon in SABLONLAR.items():
            lines.append(f"\n{key}: {sablon['ad']} ({len(sablon['maddeler'])} madde)")
            for m in sablon["maddeler"]:
                lines.append(f"  - {m['madde']} [{m['kategori']}]")
        return "\n".join(lines)

    def _delete(self, hazirlik_id: str, dava_no: str) -> str:
        if not hazirlik_id and not dava_no:
            return "Silinecek liste icin hazirlik_id veya dava_no belirtin."
        db = get_db()
        dava_id = None
        if dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                dava_id = dava["id"]

        if hazirlik_id:
            try:
                silinen = db.hazirlik_sil(madde_id=int(hazirlik_id.strip()))
            except (ValueError, TypeError):
                silinen = 0
        elif dava_id:
            silinen = db.hazirlik_sil(dava_id=dava_id)
        else:
            return "Eslesen hazirlik listesi bulunamadi."

        if silinen == 0:
            return "Eslesen hazirlik listesi bulunamadi."
        return f"{silinen} hazirlik maddesi silindi."

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
