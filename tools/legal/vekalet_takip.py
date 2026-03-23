"""Vekalet Takip Araci — Vekaletname, azilname ve yetki belgesi yonetimi."""

from __future__ import annotations

from datetime import datetime, timedelta
from tools.base import BaseTool
from core.database import get_db

# Vekalet turleri
VEKALET_TURLERI = {
    "genel": "Genel Vekaletname",
    "ozel": "Ozel Vekaletname (belirli is icin)",
    "dava": "Dava Vekaletnamesi",
    "icra": "Icra Takip Vekaletnamesi",
    "gayrimenkul": "Gayrimenkul Vekaletnamesi",
    "banka": "Banka Islemleri Vekaletnamesi",
    "sirket": "Sirket Temsil Vekaletnamesi",
    "noterlik": "Noterlik Islemleri Vekaletnamesi",
}

# Vekalet durumlari
DURUMLAR = {
    "aktif": "Aktif — Gecerli vekaletname",
    "suresi_dolmus": "Suresi Dolmus — Yenilenmesi gerekli",
    "azledildi": "Azledildi — Muvekil tarafindan azil",
    "istifa": "Istifa — Avukat tarafindan cekilme",
    "iptal": "Iptal Edildi",
}


class VekaletTakipTool(BaseTool):
    name = "vekalet_takip"
    description = (
        "Vekaletname, azilname ve yetki belgesi takibi. Vekalet kaydi olusturma, "
        "azil/istifa isleme, suresi dolan vekaletleri listeleme, "
        "dava bazinda vekalet durumu sorgulama."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: add | list | azil | istifa | expiring | search | update | delete | types",
                "enum": ["add", "list", "azil", "istifa", "expiring", "search", "update", "delete", "types"],
            },
            "muvekil": {
                "type": "string",
                "description": "Muvekil adi / soyadi veya unvani",
            },
            "tc_no": {
                "type": "string",
                "description": "Muvekil TC kimlik numarasi (opsiyonel)",
            },
            "vekalet_turu": {
                "type": "string",
                "description": "Vekalet turu: genel | ozel | dava | icra | gayrimenkul | banka | sirket | noterlik",
            },
            "noter": {
                "type": "string",
                "description": "Noterlik adi ve yevmiye numarasi (ornek: Istanbul 5. Noterlik, Y:12345)",
            },
            "dava_no": {
                "type": "string",
                "description": "Ilgili dava/dosya numarasi",
            },
            "vekalet_tarihi": {
                "type": "string",
                "description": "Vekaletname tarihi (GG.AA.YYYY)",
            },
            "bitis_tarihi": {
                "type": "string",
                "description": "Vekaletname bitis/gecerlilik tarihi (GG.AA.YYYY). Bos = suresiz.",
            },
            "yetki_siniri": {
                "type": "string",
                "description": "Ozel yetki sinirlari (ornek: sulh olma, feragat, kabul, hakem tayini)",
            },
            "vekalet_id": {
                "type": "string",
                "description": "Vekalet kayit ID'si (update/delete/azil/istifa icin)",
            },
            "azil_tarihi": {
                "type": "string",
                "description": "Azil veya istifa tarihi (GG.AA.YYYY)",
            },
            "aciklama": {
                "type": "string",
                "description": "Ek aciklama veya not",
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str = "",
        muvekil: str = "",
        tc_no: str = "",
        vekalet_turu: str = "dava",
        noter: str = "",
        dava_no: str = "",
        vekalet_tarihi: str = "",
        bitis_tarihi: str = "",
        yetki_siniri: str = "",
        vekalet_id: str = "",
        azil_tarihi: str = "",
        aciklama: str = "",
        **kw,
    ) -> str:
        action = action.strip().lower()
        if action == "add":
            return self._add(muvekil, tc_no, vekalet_turu, noter, dava_no,
                           vekalet_tarihi, bitis_tarihi, yetki_siniri, aciklama)
        elif action == "list":
            return self._list(muvekil, dava_no)
        elif action == "azil":
            return self._azil(vekalet_id, muvekil, azil_tarihi, aciklama)
        elif action == "istifa":
            return self._istifa(vekalet_id, muvekil, azil_tarihi, aciklama)
        elif action == "expiring":
            return self._expiring()
        elif action == "search":
            return self._search(muvekil, dava_no, tc_no)
        elif action == "update":
            return self._update(vekalet_id, bitis_tarihi, yetki_siniri, aciklama, noter)
        elif action == "delete":
            return self._delete(vekalet_id)
        elif action == "types":
            return self._types()
        else:
            return f"Bilinmeyen islem: {action}. Gecerli: add, list, azil, istifa, expiring, search, update, delete, types"

    def _add(self, muvekil: str, tc_no: str, vekalet_turu: str, noter: str,
             dava_no: str, vekalet_tarihi: str, bitis_tarihi: str,
             yetki_siniri: str, aciklama: str) -> str:
        if not muvekil:
            return "Muvekil adi belirtilmedi."

        vekalet_turu = (vekalet_turu or "dava").strip().lower()
        if vekalet_turu not in VEKALET_TURLERI:
            return f"Gecersiz vekalet turu. Gecerli: {', '.join(VEKALET_TURLERI.keys())}"

        # Parse dates
        if vekalet_tarihi:
            vt_dt = self._parse_date(vekalet_tarihi)
            if vt_dt is None:
                return f"Gecersiz vekalet tarihi: {vekalet_tarihi}"
            vekalet_tarihi_str = vt_dt.strftime("%Y-%m-%d")
            vekalet_tarihi_display = vt_dt.strftime("%d.%m.%Y")
        else:
            vekalet_tarihi_str = datetime.now().strftime("%Y-%m-%d")
            vekalet_tarihi_display = datetime.now().strftime("%d.%m.%Y")

        bitis_tarihi_str = ""
        bitis_tarihi_display = ""
        if bitis_tarihi:
            bt_dt = self._parse_date(bitis_tarihi)
            if bt_dt is None:
                return f"Gecersiz bitis tarihi: {bitis_tarihi}"
            bitis_tarihi_str = bt_dt.strftime("%Y-%m-%d")
            bitis_tarihi_display = bt_dt.strftime("%d.%m.%Y")

        db = get_db()

        # Find or create muvekil
        muvekil_obj = db.muvekil_bul_by_ad(muvekil.strip())
        muvekil_id = muvekil_obj["id"] if muvekil_obj else None

        # Find dava_id
        dava_id = None
        if dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                dava_id = dava["id"]

        # Build notlar
        notlar_parts = []
        if tc_no:
            notlar_parts.append(f"tc:{tc_no.strip()}")
        if yetki_siniri:
            notlar_parts.append(f"yetki:{yetki_siniri.strip()}")
        if aciklama:
            notlar_parts.append(aciklama.strip())

        noter_str = noter.strip() if noter else ""
        # Extract yevmiye from noter string
        yevmiye_no = ""
        if noter_str and "Y:" in noter_str:
            parts = noter_str.split("Y:")
            if len(parts) > 1:
                yevmiye_no = "Y:" + parts[1].strip()

        new_id = db.vekalet_ekle(
            muvekil_id=muvekil_id,
            dava_id=dava_id,
            vekalet_turu=vekalet_turu,
            tarih=vekalet_tarihi_str,
            bitis_tarihi=bitis_tarihi_str,
            noter=noter_str,
            yevmiye_no=yevmiye_no,
            durum="aktif",
            notlar=" | ".join(notlar_parts) if notlar_parts else "",
        )

        lines = [
            "VEKALET KAYDI OLUSTURULDU",
            "=" * 50,
            f"ID: {new_id}",
            f"Muvekil: {muvekil.strip()}",
            f"TC: {tc_no.strip() if tc_no else '-'}",
            f"Tur: {VEKALET_TURLERI[vekalet_turu]}",
            f"Noter: {noter_str or '-'}",
            f"Dava No: {dava_no.strip() if dava_no else '-'}",
            f"Vekalet Tarihi: {vekalet_tarihi_display}",
            f"Bitis Tarihi: {bitis_tarihi_display or 'Suresiz'}",
            f"Ozel Yetkiler: {yetki_siniri.strip() if yetki_siniri else 'Standart'}",
            f"Durum: AKTIF",
        ]

        return "\n".join(lines)

    def _list(self, muvekil: str, dava_no: str) -> str:
        db = get_db()

        if muvekil or dava_no:
            search_term = muvekil or dava_no or ""
            vekaletler = db.vekalet_bul(search_term)
        else:
            vekaletler = db.vekalet_listele()

        if not vekaletler:
            return "Kayitli vekalet bulunmuyor." if not (muvekil or dava_no) else "Eslesen vekalet bulunamadi."

        aktif = [v for v in vekaletler if v["durum"] == "aktif"]
        pasif = [v for v in vekaletler if v["durum"] != "aktif"]

        lines = [f"VEKALET LISTESI ({len(vekaletler)} kayit)", "=" * 55]

        if aktif:
            lines.append(f"\nAKTIF VEKALETLER ({len(aktif)}):")
            for v in aktif:
                lines.append(self._format_vekalet(v))

        if pasif:
            lines.append(f"\nPASIF VEKALETLER ({len(pasif)}):")
            for v in pasif:
                lines.append(self._format_vekalet(v))

        return "\n".join(lines)

    def _azil(self, vekalet_id: str, muvekil: str, azil_tarihi: str, aciklama: str) -> str:
        db = get_db()
        target = self._find(db, vekalet_id, muvekil)
        if target is None:
            return "Vekalet kaydi bulunamadi. vekalet_id veya muvekil belirtin."

        if target["durum"] != "aktif":
            return f"Bu vekalet zaten aktif degil. Mevcut durum: {target['durum']}"

        if azil_tarihi:
            dt = self._parse_date(azil_tarihi)
            if dt is None:
                return f"Gecersiz azil tarihi: {azil_tarihi}"
            azil_str = dt.strftime("%d.%m.%Y")
        else:
            azil_str = datetime.now().strftime("%d.%m.%Y")

        notlar = target.get("notlar", "") or ""
        if aciklama:
            notlar = (notlar + f" | AZIL: {aciklama}").strip(" |")
        notlar = (notlar + f" | azil_tarihi:{azil_str}").strip(" |")

        db.vekalet_guncelle(target["id"], durum="azledildi", notlar=notlar)

        return (
            f"AZILNAME ISLENDI\n"
            f"{'='*50}\n"
            f"Vekalet ID: {target['id']}\n"
            f"Muvekil: {target.get('muvekil_adi') or muvekil or '-'}\n"
            f"Azil Tarihi: {azil_str}\n"
            f"Durum: AZLEDILDI\n\n"
            f"HATIRLATMA:\n"
            f"- Azilname noter araciligiyla teblig edilmelidir\n"
            f"- Mahkemeye azilname sunulmalidir\n"
            f"- Dosyadaki evraklarin teslimi planlanmalidir\n"
            f"- Baro'ya bildirim yapilmalidir"
        )

    def _istifa(self, vekalet_id: str, muvekil: str, azil_tarihi: str, aciklama: str) -> str:
        db = get_db()
        target = self._find(db, vekalet_id, muvekil)
        if target is None:
            return "Vekalet kaydi bulunamadi."

        if target["durum"] != "aktif":
            return f"Bu vekalet zaten aktif degil. Mevcut durum: {target['durum']}"

        if azil_tarihi:
            dt = self._parse_date(azil_tarihi)
            if dt is None:
                return f"Gecersiz istifa tarihi: {azil_tarihi}"
            istifa_str = dt.strftime("%d.%m.%Y")
        else:
            istifa_str = datetime.now().strftime("%d.%m.%Y")

        notlar = target.get("notlar", "") or ""
        if aciklama:
            notlar = (notlar + f" | ISTIFA: {aciklama}").strip(" |")
        notlar = (notlar + f" | istifa_tarihi:{istifa_str}").strip(" |")

        db.vekalet_guncelle(target["id"], durum="istifa", notlar=notlar)

        return (
            f"ISTIFA ISLENDI\n"
            f"{'='*50}\n"
            f"Vekalet ID: {target['id']}\n"
            f"Muvekil: {target.get('muvekil_adi') or muvekil or '-'}\n"
            f"Istifa Tarihi: {istifa_str}\n"
            f"Durum: ISTIFA\n\n"
            f"HATIRLATMA:\n"
            f"- Istifa, muvekile noter araciligiyla bildirilmelidir\n"
            f"- Av.K. m.174: Istifa eden avukat 15 gun boyunca sorumlu kalmaya devam eder\n"
            f"- Dosya ve belgeler muvekile teslim edilmelidir\n"
            f"- Mahkemeye istifa dilekce sunulmalidir"
        )

    def _expiring(self) -> str:
        db = get_db()
        vekaletler = db.suresi_dolan_vekaletler(gun=30)

        if not vekaletler:
            return "Suresi dolmus veya dolmak uzere olan vekalet bulunmuyor."

        now = datetime.now()
        suresi_dolmus = []
        yakinda_bitecek = []

        for v in vekaletler:
            if not v.get("bitis_tarihi"):
                continue
            try:
                bitis = datetime.strptime(v["bitis_tarihi"], "%Y-%m-%d")
            except ValueError:
                continue

            kalan = (bitis - now).days
            if kalan < 0:
                suresi_dolmus.append((kalan, v))
                # Auto-update status
                db.vekalet_guncelle(v["id"], durum="suresi_dolmus")
            else:
                yakinda_bitecek.append((kalan, v))

        lines = ["VEKALET SURE UYARILARI", "=" * 55]

        if suresi_dolmus:
            lines.append(f"\nSURESI DOLMUS ({len(suresi_dolmus)}):")
            for kalan, v in sorted(suresi_dolmus):
                bitis_display = v.get("bitis_tarihi", "")
                try:
                    dt = datetime.strptime(bitis_display, "%Y-%m-%d")
                    bitis_display = dt.strftime("%d.%m.%Y")
                except ValueError:
                    pass
                tur_adi = VEKALET_TURLERI.get(v.get("vekalet_turu", ""), v.get("vekalet_turu", "?"))
                lines.append(
                    f"  !!! [{v['id']}] {v.get('muvekil_adi') or '-'} — {tur_adi}\n"
                    f"      Bitis: {bitis_display} ({abs(kalan)} gun gecmis)\n"
                    f"      Dava: {v.get('dava_no') or '-'}"
                )

        if yakinda_bitecek:
            lines.append(f"\nYAKINDA BITECEK ({len(yakinda_bitecek)}):")
            for kalan, v in sorted(yakinda_bitecek):
                bitis_display = v.get("bitis_tarihi", "")
                try:
                    dt = datetime.strptime(bitis_display, "%Y-%m-%d")
                    bitis_display = dt.strftime("%d.%m.%Y")
                except ValueError:
                    pass
                tur_adi = VEKALET_TURLERI.get(v.get("vekalet_turu", ""), v.get("vekalet_turu", "?"))
                lines.append(
                    f"  !! [{v['id']}] {v.get('muvekil_adi') or '-'} — {tur_adi}\n"
                    f"     Bitis: {bitis_display} ({kalan} gun kaldi)\n"
                    f"     Dava: {v.get('dava_no') or '-'}"
                )

        return "\n".join(lines)

    def _search(self, muvekil: str, dava_no: str, tc_no: str) -> str:
        db = get_db()
        search_term = muvekil or dava_no or tc_no or ""
        if not search_term:
            return "Arama terimi belirtilmedi."
        results = db.vekalet_bul(search_term)

        if not results:
            return "Eslesen vekalet bulunamadi."

        lines = [f"ARAMA SONUCLARI ({len(results)} kayit)", "=" * 50]
        for v in results:
            lines.append(self._format_vekalet(v))

        return "\n".join(lines)

    def _update(self, vekalet_id: str, bitis_tarihi: str, yetki_siniri: str, aciklama: str, noter: str) -> str:
        if not vekalet_id:
            return "Guncellenecek vekalet ID'si belirtilmedi."

        db = get_db()
        updates = {}
        guncellemeler = []

        if bitis_tarihi:
            dt = self._parse_date(bitis_tarihi)
            if dt is None:
                return f"Gecersiz tarih: {bitis_tarihi}"
            updates["bitis_tarihi"] = dt.strftime("%Y-%m-%d")
            guncellemeler.append(f"Bitis tarihi: {dt.strftime('%d.%m.%Y')}")

        if noter:
            updates["noter"] = noter.strip()
            guncellemeler.append(f"Noter: {noter}")

        # yetki_siniri and aciklama go in notlar
        if yetki_siniri or aciklama:
            # Get existing
            all_vek = db.vekalet_listele()
            target = None
            try:
                vid = int(vekalet_id.strip())
                for v in all_vek:
                    if v["id"] == vid:
                        target = v
                        break
            except ValueError:
                pass
            if target is None:
                return "Vekalet kaydi bulunamadi."
            notlar = target.get("notlar", "") or ""
            if yetki_siniri:
                notlar = (notlar + f" | yetki:{yetki_siniri.strip()}").strip(" |")
                guncellemeler.append(f"Yetki siniri: {yetki_siniri}")
            if aciklama:
                notlar = (notlar + f" | {aciklama.strip()}").strip(" |")
                guncellemeler.append(f"Aciklama: {aciklama}")
            updates["notlar"] = notlar

        if not guncellemeler:
            return "Guncellenecek alan belirtilmedi."

        try:
            db.vekalet_guncelle(int(vekalet_id.strip()), **updates)
        except ValueError:
            return "Gecersiz vekalet ID'si."

        return f"VEKALET GUNCELLENDI [{vekalet_id}]\n" + "\n".join(f"  {g}" for g in guncellemeler)

    def _delete(self, vekalet_id: str) -> str:
        if not vekalet_id:
            return "Silinecek vekalet ID'si belirtin."
        db = get_db()
        try:
            if db.vekalet_sil(int(vekalet_id.strip())):
                return "1 vekalet kaydi silindi."
        except (ValueError, TypeError):
            pass
        return "Eslesen vekalet kaydi bulunamadi."

    def _types(self) -> str:
        lines = ["VEKALET TURLERI", "=" * 50]
        for key, desc in VEKALET_TURLERI.items():
            lines.append(f"  {key:<15} {desc}")
        lines.append(f"\nDURUMLAR:")
        for key, desc in DURUMLAR.items():
            lines.append(f"  {key:<15} {desc}")
        return "\n".join(lines)

    @staticmethod
    def _format_vekalet(v: dict) -> str:
        durum_str = v["durum"].upper()
        tur_adi = VEKALET_TURLERI.get(v.get("vekalet_turu", ""), v.get("vekalet_turu", "?"))
        muvekil_adi = v.get("muvekil_adi") or "-"

        # Extract tc and yetki from notlar
        tc_no = "-"
        yetki = "Standart"
        for part in (v.get("notlar", "") or "").split("|"):
            part = part.strip()
            if part.startswith("tc:"):
                tc_no = part.split(":", 1)[1].strip()
            elif part.startswith("yetki:"):
                yetki = part.split(":", 1)[1].strip()

        tarih_display = v.get("tarih", "-")
        bitis_display = v.get("bitis_tarihi", "")
        try:
            if tarih_display:
                dt = datetime.strptime(tarih_display, "%Y-%m-%d")
                tarih_display = dt.strftime("%d.%m.%Y")
        except ValueError:
            pass
        try:
            if bitis_display:
                dt = datetime.strptime(bitis_display, "%Y-%m-%d")
                bitis_display = dt.strftime("%d.%m.%Y")
        except ValueError:
            pass

        return (
            f"\n[{v['id']}] {muvekil_adi} — {tur_adi} [{durum_str}]\n"
            f"  TC: {tc_no} | Noter: {v.get('noter') or '-'}\n"
            f"  Dava: {v.get('dava_no') or '-'}\n"
            f"  Tarih: {tarih_display} — {bitis_display or 'Suresiz'}\n"
            f"  Yetkiler: {yetki}"
        )

    @staticmethod
    def _find(db, vekalet_id: str, muvekil: str) -> dict | None:
        if vekalet_id:
            try:
                vid = int(vekalet_id.strip())
                all_vek = db.vekalet_listele()
                for v in all_vek:
                    if v["id"] == vid:
                        return v
            except (ValueError, TypeError):
                pass
        elif muvekil:
            results = db.vekalet_bul(muvekil)
            aktifler = [v for v in results if v["durum"] == "aktif"]
            if len(aktifler) == 1:
                return aktifler[0]
        return None

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
