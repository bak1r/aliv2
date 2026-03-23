"""Tebligat Takip Araci — Tebligat durumu, suresi ve otomatik son gun hesabi."""

from __future__ import annotations

from datetime import datetime, timedelta
from tools.base import BaseTool
from core.database import get_db

# Tebligat turleri ve ilgili sure bilgileri
TEBLIGAT_TURLERI = {
    "normal": {"ad": "Normal Tebligat", "tebellug_suresi": 0, "aciklama": "Elden teslim / muhataba bizzat"},
    "bila": {"ad": "Bila Tebligat (iade)", "tebellug_suresi": 0, "aciklama": "Tebligat iade — yeni adres arastirmasi gerekli"},
    "21_1": {"ad": "TK m.21/1 Tebligat", "tebellug_suresi": 0, "aciklama": "Muhatap adreste yok — komsu/muhtar bildirimi"},
    "21_2": {"ad": "TK m.21/2 (Mernis) Tebligat", "tebellug_suresi": 15, "aciklama": "Mernis adresi — 15 gun sonra teblig sayilir"},
    "35": {"ad": "TK m.35 Tebligat", "tebellug_suresi": 15, "aciklama": "Bilinen son adres — 15 gun sonra teblig sayilir"},
    "ilan": {"ad": "Ilanen Tebligat", "tebellug_suresi": 15, "aciklama": "Gazete/ilan yoluyla — 15 gun sonra teblig sayilir"},
    "elektronik": {"ad": "Elektronik Tebligat (UETS)", "tebellug_suresi": 5, "aciklama": "Elektronik ortam — 5 gun icinde okunmazsa teblig sayilir"},
    "yurtdisi": {"ad": "Yurt Disi Tebligat", "tebellug_suresi": 0, "aciklama": "Diplomatik yollarla — sure degisken"},
}

# Tebligat sonrasi yasal sureler (gun)
YASAL_SURELER = {
    "odeme_emri_itiraz": 7,
    "icra_itiraz": 7,
    "istinaf": 7,
    "temyiz": 15,
    "cevap_dilekce": 14,
    "idari_dava": 60,
    "iddianame_iade": 15,
    "dava_acma": 30,
}


class TebligatTakipTool(BaseTool):
    name = "tebligat_takip"
    description = (
        "Tebligat durumu ve suresi takibi. Tebligat kaydi olusturma, tebellug tarihi guncelleme, "
        "son gun otomatik hesaplama (teblig+yasal sure), acil/gecmis tebligatlar listesi. "
        "Desteklenen turler: normal, 21/1, 21/2 (mernis), 35, ilan, elektronik, bila, yurtdisi."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: add | update | list | urgent | calculate | types | delete",
                "enum": ["add", "update", "list", "urgent", "calculate", "types", "delete"],
            },
            "dava_no": {
                "type": "string",
                "description": "Dava/dosya numarasi",
            },
            "tebligat_turu": {
                "type": "string",
                "description": "Tebligat turu: normal | bila | 21_1 | 21_2 | 35 | ilan | elektronik | yurtdisi",
            },
            "gonderim_tarihi": {
                "type": "string",
                "description": "Tebligat gonderim tarihi (GG.AA.YYYY)",
            },
            "tebellug_tarihi": {
                "type": "string",
                "description": "Tebellug (teslim) tarihi (GG.AA.YYYY). 21/2, 35, ilan icin otomatik hesaplanabilir.",
            },
            "muhatap": {
                "type": "string",
                "description": "Tebligat muhatabi (kisi/kurum adi)",
            },
            "yasal_islem": {
                "type": "string",
                "description": "Yapilacak yasal islem (son gun hesabi icin): odeme_emri_itiraz | icra_itiraz | istinaf | temyiz | cevap_dilekce | idari_dava | iddianame_iade | dava_acma",
            },
            "aciklama": {
                "type": "string",
                "description": "Ek aciklama veya not",
            },
            "tebligat_id": {
                "type": "string",
                "description": "Tebligat kayit ID'si (update/delete icin)",
            },
            "durum": {
                "type": "string",
                "description": "Tebligat durumu: beklemede | teblig_edildi | iade | iptal",
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str = "",
        dava_no: str = "",
        tebligat_turu: str = "normal",
        gonderim_tarihi: str = "",
        tebellug_tarihi: str = "",
        muhatap: str = "",
        yasal_islem: str = "",
        aciklama: str = "",
        tebligat_id: str = "",
        durum: str = "",
        **kw,
    ) -> str:
        action = action.strip().lower()
        if action == "add":
            return self._add(dava_no, tebligat_turu, gonderim_tarihi, tebellug_tarihi, muhatap, yasal_islem, aciklama)
        elif action == "update":
            return self._update(tebligat_id, dava_no, tebellug_tarihi, durum, aciklama)
        elif action == "list":
            return self._list(dava_no)
        elif action == "urgent":
            return self._urgent()
        elif action == "calculate":
            return self._calculate(tebligat_turu, tebellug_tarihi, gonderim_tarihi, yasal_islem)
        elif action == "types":
            return self._types()
        elif action == "delete":
            return self._delete(tebligat_id)
        else:
            return f"Bilinmeyen islem: {action}. Gecerli: add, update, list, urgent, calculate, types, delete"

    def _add(self, dava_no: str, tebligat_turu: str, gonderim_tarihi: str,
             tebellug_tarihi: str, muhatap: str, yasal_islem: str, aciklama: str) -> str:
        if not dava_no:
            return "Dava numarasi belirtilmedi."

        tebligat_turu = tebligat_turu.strip().lower() if tebligat_turu else "normal"
        if tebligat_turu not in TEBLIGAT_TURLERI:
            return f"Gecersiz tebligat turu. Gecerli: {', '.join(TEBLIGAT_TURLERI.keys())}"

        tur_info = TEBLIGAT_TURLERI[tebligat_turu]

        # Gonderim tarihi
        if gonderim_tarihi:
            gonderim_dt = self._parse_date(gonderim_tarihi)
            if gonderim_dt is None:
                return f"Gecersiz gonderim tarihi: {gonderim_tarihi}"
            gonderim_str = gonderim_dt.strftime("%Y-%m-%d")
        else:
            gonderim_dt = datetime.now()
            gonderim_str = gonderim_dt.strftime("%Y-%m-%d")

        # Tebellug tarihi
        tebellug_str = ""
        tebellug_dt = None
        if tebellug_tarihi:
            tebellug_dt = self._parse_date(tebellug_tarihi)
            if tebellug_dt is None:
                return f"Gecersiz tebellug tarihi: {tebellug_tarihi}"
            tebellug_str = tebellug_dt.strftime("%Y-%m-%d")
        elif tur_info["tebellug_suresi"] > 0 and gonderim_dt:
            tebellug_dt = gonderim_dt + timedelta(days=tur_info["tebellug_suresi"])
            tebellug_str = tebellug_dt.strftime("%Y-%m-%d")

        # Son gun hesabi
        son_gun_str = ""
        yasal_gun = 0
        if tebellug_dt and yasal_islem and yasal_islem in YASAL_SURELER:
            yasal_gun = YASAL_SURELER[yasal_islem]
            son_gun = tebellug_dt + timedelta(days=yasal_gun)
            if son_gun.weekday() == 5:
                son_gun += timedelta(days=2)
            elif son_gun.weekday() == 6:
                son_gun += timedelta(days=1)
            son_gun_str = son_gun.strftime("%Y-%m-%d")

        db = get_db()
        # Find dava_id
        dava_id = None
        dava = db.dava_bul_by_no(dava_no.strip())
        if dava:
            dava_id = dava["id"]

        notlar_parts = []
        if muhatap:
            notlar_parts.append(f"muhatap:{muhatap.strip()}")
        if yasal_islem:
            notlar_parts.append(f"yasal_islem:{yasal_islem}")
        if aciklama:
            notlar_parts.append(aciklama.strip())

        new_id = db.tebligat_ekle(
            dava_id=dava_id,
            tebligat_turu=tebligat_turu,
            gonderim_tarihi=gonderim_str,
            teblig_tarihi=tebellug_str,
            yasal_sure_gun=yasal_gun if yasal_gun else None,
            son_gun=son_gun_str,
            durum="bekliyor" if not tebellug_tarihi else "teblig_edildi",
            notlar=" | ".join(notlar_parts) if notlar_parts else "",
        )

        # Format display dates
        gonderim_display = gonderim_dt.strftime("%d.%m.%Y")
        tebellug_display = tebellug_dt.strftime("%d.%m.%Y") if tebellug_dt else "Henuz teblig edilmedi"
        if tebellug_dt and not tebellug_tarihi:
            tebellug_display += " (tahmini)"

        lines = [
            f"TEBLIGAT KAYDI OLUSTURULDU",
            f"{'='*50}",
            f"ID: {new_id}",
            f"Dava No: {dava_no}",
            f"Tur: {tur_info['ad']}",
            f"Muhatap: {muhatap.strip() if muhatap else '-'}",
            f"Gonderim: {gonderim_display}",
            f"Tebellug: {tebellug_display}",
            f"Durum: {'BEKLEMEDE' if not tebellug_tarihi else 'TEBLIG_EDILDI'}",
        ]
        if son_gun_str:
            try:
                sg_dt = datetime.strptime(son_gun_str, "%Y-%m-%d")
                lines.append(f"SON GUN ({yasal_islem}): {sg_dt.strftime('%d.%m.%Y')}")
            except ValueError:
                lines.append(f"SON GUN ({yasal_islem}): {son_gun_str}")
        if aciklama:
            lines.append(f"Not: {aciklama}")

        return "\n".join(lines)

    def _update(self, tebligat_id: str, dava_no: str, tebellug_tarihi: str, durum: str, aciklama: str) -> str:
        db = get_db()
        target = None

        if tebligat_id:
            try:
                results = db.tebligat_listele()
                for t in results:
                    if t["id"] == int(tebligat_id.strip()):
                        target = t
                        break
            except (ValueError, TypeError):
                pass
        elif dava_no:
            results = db.tebligat_by_dava_no(dava_no.strip())
            bekleyenler = [t for t in results if t["durum"] == "bekliyor"]
            if bekleyenler:
                target = bekleyenler[0]

        if target is None:
            return "Tebligat kaydi bulunamadi."

        updates = {}
        guncellemeler = []

        if tebellug_tarihi:
            dt = self._parse_date(tebellug_tarihi)
            if dt is None:
                return f"Gecersiz tebellug tarihi: {tebellug_tarihi}"
            updates["teblig_tarihi"] = dt.strftime("%Y-%m-%d")
            updates["durum"] = "teblig_edildi"
            guncellemeler.append(f"Tebellug tarihi: {dt.strftime('%d.%m.%Y')}")

            # Recalculate son_gun
            notlar = target.get("notlar", "")
            yasal_islem = ""
            for part in notlar.split("|"):
                part = part.strip()
                if part.startswith("yasal_islem:"):
                    yasal_islem = part.split(":")[1].strip()
            if yasal_islem and yasal_islem in YASAL_SURELER:
                yasal_gun = YASAL_SURELER[yasal_islem]
                son_gun = dt + timedelta(days=yasal_gun)
                if son_gun.weekday() == 5:
                    son_gun += timedelta(days=2)
                elif son_gun.weekday() == 6:
                    son_gun += timedelta(days=1)
                updates["son_gun"] = son_gun.strftime("%Y-%m-%d")
                guncellemeler.append(f"Son gun: {son_gun.strftime('%d.%m.%Y')}")

        if durum:
            updates["durum"] = durum.strip().lower()
            guncellemeler.append(f"Durum: {durum}")

        if aciklama:
            existing = target.get("notlar", "")
            updates["notlar"] = (existing + " | " + aciklama.strip()).strip(" |")
            guncellemeler.append(f"Aciklama: {aciklama}")

        if not guncellemeler:
            return "Guncellenecek alan belirtilmedi."

        db.tebligat_guncelle(target["id"], **updates)
        return f"TEBLIGAT GUNCELLENDI [{target['id']}]\n" + "\n".join(f"  {g}" for g in guncellemeler)

    def _list(self, dava_no: str) -> str:
        db = get_db()
        if dava_no:
            tebligatlar = db.tebligat_by_dava_no(dava_no.strip())
        else:
            tebligatlar = db.tebligat_listele()

        if not tebligatlar:
            return "Kayitli tebligat bulunmuyor." if not dava_no else "Eslesen tebligat bulunamadi."

        lines = [f"TEBLIGAT LISTESI ({len(tebligatlar)} kayit)", "=" * 55]
        for t in tebligatlar:
            tur_info = TEBLIGAT_TURLERI.get(t.get("tebligat_turu", ""), {"ad": t.get("tebligat_turu", "?")})
            tur_adi = tur_info["ad"]

            acil = ""
            if t.get("son_gun") and t["durum"] != "iptal":
                try:
                    sg = datetime.strptime(t["son_gun"], "%Y-%m-%d")
                    kalan = (sg - datetime.now()).days
                    if kalan < 0:
                        acil = " [SURE GECMIS!]"
                    elif kalan <= 3:
                        acil = f" [ACIL! {kalan} gun]"
                except ValueError:
                    pass

            # Extract muhatap from notlar
            muhatap = "-"
            notlar = t.get("notlar", "")
            for part in notlar.split("|"):
                part = part.strip()
                if part.startswith("muhatap:"):
                    muhatap = part.split(":", 1)[1].strip()

            gonderim_display = t.get("gonderim_tarihi", "-")
            teblig_display = t.get("teblig_tarihi", "-") or "-"
            son_gun_display = t.get("son_gun", "-") or "-"

            # Format dates for display
            for field in [("gonderim_tarihi", "gonderim_display"), ("teblig_tarihi", "teblig_display"), ("son_gun", "son_gun_display")]:
                val = t.get(field[0], "")
                if val:
                    try:
                        dt = datetime.strptime(val, "%Y-%m-%d")
                        if field[0] == "gonderim_tarihi":
                            gonderim_display = dt.strftime("%d.%m.%Y")
                        elif field[0] == "teblig_tarihi":
                            teblig_display = dt.strftime("%d.%m.%Y")
                        elif field[0] == "son_gun":
                            son_gun_display = dt.strftime("%d.%m.%Y")
                    except ValueError:
                        pass

            dava_no_display = t.get("dava_no") or "-"
            lines.append(
                f"\n[{t['id']}] {tur_adi} — {t['durum'].upper()}{acil}\n"
                f"  Dava: {dava_no_display} | Muhatap: {muhatap}\n"
                f"  Gonderim: {gonderim_display} | Tebellug: {teblig_display}\n"
                f"  Son Gun: {son_gun_display}"
            )

        return "\n".join(lines)

    def _urgent(self) -> str:
        db = get_db()
        tebligatlar = db.tebligat_listele()
        if not tebligatlar:
            return "Kayitli tebligat bulunmuyor."

        now = datetime.now()
        aciller = []
        for t in tebligatlar:
            if t["durum"] in ("iptal",):
                continue
            if not t.get("son_gun"):
                if t["durum"] == "bekliyor":
                    aciller.append((999, t, "BEKLEMEDE — tebellug bekleniyor"))
                continue
            try:
                sg = datetime.strptime(t["son_gun"], "%Y-%m-%d")
                kalan = (sg - now).days
                if kalan < 0:
                    aciller.append((kalan, t, f"SURE GECMIS ({abs(kalan)} gun once)"))
                elif kalan <= 7:
                    aciller.append((kalan, t, f"{kalan} gun kaldi"))
            except ValueError:
                continue

        if not aciller:
            return "Acil tebligat bulunmuyor. Tum sureler normal."

        aciller.sort(key=lambda x: x[0])
        lines = [f"ACIL TEBLIGATLAR ({len(aciller)} adet)", "=" * 55]

        for kalan, t, durum_str in aciller:
            tur_info = TEBLIGAT_TURLERI.get(t.get("tebligat_turu", ""), {"ad": t.get("tebligat_turu", "?")})
            muhatap = "-"
            for part in (t.get("notlar", "") or "").split("|"):
                part = part.strip()
                if part.startswith("muhatap:"):
                    muhatap = part.split(":", 1)[1].strip()

            son_gun_display = t.get("son_gun", "-")
            try:
                sg_dt = datetime.strptime(son_gun_display, "%Y-%m-%d")
                son_gun_display = sg_dt.strftime("%d.%m.%Y")
            except ValueError:
                pass

            dava_no_display = t.get("dava_no") or "-"
            lines.append(
                f"\n{'!!!' if kalan < 0 else '!!'} [{t['id']}] {tur_info['ad']} — {durum_str}\n"
                f"  Dava: {dava_no_display} | Muhatap: {muhatap}\n"
                f"  Son Gun: {son_gun_display}"
            )

        return "\n".join(lines)

    def _calculate(self, tebligat_turu: str, tebellug_tarihi: str, gonderim_tarihi: str, yasal_islem: str) -> str:
        if not yasal_islem:
            return "Yasal islem turu belirtilmedi. Gecerli: " + ", ".join(YASAL_SURELER.keys())
        if yasal_islem not in YASAL_SURELER:
            return f"Gecersiz yasal islem: {yasal_islem}. Gecerli: {', '.join(YASAL_SURELER.keys())}"

        tebligat_turu = (tebligat_turu or "normal").strip().lower()
        tur_info = TEBLIGAT_TURLERI.get(tebligat_turu)
        if not tur_info:
            return f"Gecersiz tebligat turu. Gecerli: {', '.join(TEBLIGAT_TURLERI.keys())}"

        if tebellug_tarihi:
            tebellug_dt = self._parse_date(tebellug_tarihi)
            if tebellug_dt is None:
                return f"Gecersiz tebellug tarihi: {tebellug_tarihi}"
        elif gonderim_tarihi and tur_info["tebellug_suresi"] > 0:
            gonderim_dt = self._parse_date(gonderim_tarihi)
            if gonderim_dt is None:
                return f"Gecersiz gonderim tarihi: {gonderim_tarihi}"
            tebellug_dt = gonderim_dt + timedelta(days=tur_info["tebellug_suresi"])
        else:
            return "Tebellug tarihi veya gonderim tarihi belirtilmedi."

        yasal_gun = YASAL_SURELER[yasal_islem]
        son_gun = tebellug_dt + timedelta(days=yasal_gun)

        if son_gun.weekday() == 5:
            son_gun += timedelta(days=2)
        elif son_gun.weekday() == 6:
            son_gun += timedelta(days=1)

        kalan = (son_gun - datetime.now()).days

        return (
            f"TEBLIGAT SURE HESABI\n"
            f"{'='*50}\n"
            f"Tebligat Turu: {tur_info['ad']}\n"
            f"Tebellug Tarihi: {tebellug_dt.strftime('%d.%m.%Y')}\n"
            f"Yasal Islem: {yasal_islem} ({yasal_gun} gun)\n"
            f"\nSON GUN: {son_gun.strftime('%d.%m.%Y %A')}\n"
            f"Kalan: {kalan} gun {'(GECMIS!)' if kalan < 0 else '(ACIL!)' if kalan <= 3 else ''}\n"
            f"\nNOT: Resmi tatiller hesaba dahil edilmemistir."
        )

    def _types(self) -> str:
        lines = ["TEBLIGAT TURLERI", "=" * 55]
        for key, info in TEBLIGAT_TURLERI.items():
            otomatik = f" — otomatik {info['tebellug_suresi']} gun" if info["tebellug_suresi"] > 0 else ""
            lines.append(f"\n  {key}: {info['ad']}{otomatik}")
            lines.append(f"    {info['aciklama']}")
        lines.append(f"\nYASAL SURELER:")
        for key, gun in YASAL_SURELER.items():
            lines.append(f"  {key}: {gun} gun")
        return "\n".join(lines)

    def _delete(self, tebligat_id: str) -> str:
        if not tebligat_id:
            return "Silinecek tebligat ID'si belirtin."
        db = get_db()
        try:
            if db.tebligat_sil(int(tebligat_id.strip())):
                return "1 tebligat kaydi silindi."
        except (ValueError, TypeError):
            pass
        return "Eslesen tebligat kaydi bulunamadi."

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
