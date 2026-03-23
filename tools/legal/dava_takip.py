"""Dava Takip Araci — Birlesik dava yonetimi ve dashboard."""

from __future__ import annotations

from datetime import datetime
from tools.base import BaseTool
from core.database import get_db


class DavaTakipTool(BaseTool):
    name = "dava_takip"
    description = (
        "Birlesik dava yonetim araci. Dava ekleme, detay goruntuleme, listeleme, "
        "guncelleme, arama, durum degistirme ve gunluk dashboard. "
        "Tum dava bilgilerini (durusmalar, tebligatlar, masraflar, zaman, vekaletler) tek bir yerden gosterir."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: add | detail | list | update | search | status_update | dashboard | client_file",
                "enum": ["add", "detail", "list", "update", "search", "status_update", "dashboard", "client_file"],
            },
            "dava_no": {
                "type": "string",
                "description": "Dava/esas numarasi (ornek: 2026/123)",
            },
            "muvekil": {
                "type": "string",
                "description": "Muvekil adi (add icin gerekli, search icin kullanilabilir)",
            },
            "mahkeme": {
                "type": "string",
                "description": "Mahkeme adi",
            },
            "dava_turu": {
                "type": "string",
                "description": "Dava turu: ceza | hukuk | icra | idari",
            },
            "durum": {
                "type": "string",
                "description": "Dava durumu: aktif | kapali | beklemede",
            },
            "ozet": {
                "type": "string",
                "description": "Dava ozeti veya konusu",
            },
            "notlar": {
                "type": "string",
                "description": "Ek notlar",
            },
            "query": {
                "type": "string",
                "description": "Arama terimi (search islemi icin)",
            },
            "dava_id": {
                "type": "string",
                "description": "Dava ID'si (detail, update, status_update icin)",
            },
            "client_id": {
                "type": "string",
                "description": "Muvekil ID'si veya adi (client_file icin)",
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str = "",
        dava_no: str = "",
        muvekil: str = "",
        mahkeme: str = "",
        dava_turu: str = "",
        durum: str = "",
        ozet: str = "",
        notlar: str = "",
        query: str = "",
        dava_id: str = "",
        client_id: str = "",
        **kw,
    ) -> str:
        action = action.strip().lower()
        if action == "add":
            return self._add(dava_no, muvekil, mahkeme, dava_turu, ozet, notlar)
        elif action == "detail":
            return self._detail(dava_id, dava_no)
        elif action == "list":
            return self._list(durum)
        elif action == "update":
            return self._update(dava_id, dava_no, mahkeme, dava_turu, ozet, notlar)
        elif action == "search":
            return self._search(query or dava_no or muvekil or "")
        elif action == "status_update":
            return self._status_update(dava_id, dava_no, durum)
        elif action == "dashboard":
            return self._dashboard()
        elif action == "client_file":
            return self._client_file(client_id or muvekil)
        else:
            return f"Bilinmeyen islem: {action}. Gecerli: add, detail, list, update, search, status_update, dashboard, client_file"

    def _add(self, dava_no: str, muvekil: str, mahkeme: str, dava_turu: str,
             ozet: str, notlar: str) -> str:
        if not dava_no:
            return "Dava numarasi belirtilmedi."

        db = get_db()

        # Find or create muvekil
        muvekil_id = None
        if muvekil:
            muvekil_obj = db.muvekil_bul_by_ad(muvekil.strip())
            if muvekil_obj:
                muvekil_id = muvekil_obj["id"]
            else:
                muvekil_id = db.muvekil_ekle(ad=muvekil.strip())

        new_id = db.dava_ekle(
            muvekil_id=muvekil_id,
            dava_no=dava_no.strip(),
            mahkeme=mahkeme.strip() if mahkeme else "",
            dava_turu=dava_turu.strip().lower() if dava_turu else "",
            ozet=ozet.strip() if ozet else "",
            notlar=notlar.strip() if notlar else "",
        )

        return (
            f"DAVA EKLENDI\n"
            f"{'='*50}\n"
            f"ID: {new_id}\n"
            f"Dava No: {dava_no}\n"
            f"Muvekil: {muvekil or '-'}\n"
            f"Mahkeme: {mahkeme or '-'}\n"
            f"Dava Turu: {dava_turu or '-'}\n"
            f"Durum: AKTIF\n"
            f"Ozet: {ozet or '-'}\n"
        )

    def _detail(self, dava_id: str, dava_no: str) -> str:
        db = get_db()
        detay = None

        if dava_id:
            try:
                detay = db.dava_detay(int(dava_id.strip()))
            except (ValueError, TypeError):
                pass
        if detay is None and dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                detay = db.dava_detay(dava["id"])

        if detay is None:
            return "Dava bulunamadi. dava_id veya dava_no belirtin."

        lines = [
            f"DAVA DETAY",
            f"{'='*60}",
            f"ID: {detay['id']} | Dava No: {detay['dava_no']}",
            f"Muvekil: {detay.get('muvekil_adi') or '-'} (Tel: {detay.get('muvekil_telefon') or '-'})",
            f"Mahkeme: {detay.get('mahkeme') or '-'}",
            f"Dava Turu: {detay.get('dava_turu') or '-'}",
            f"Durum: {(detay.get('durum') or 'aktif').upper()}",
            f"Ozet: {detay.get('ozet') or '-'}",
        ]

        # Durusmalar
        durusmalar = detay.get("durusmalar", [])
        if durusmalar:
            lines.append(f"\nDURUSMALAR ({len(durusmalar)}):")
            for d in durusmalar:
                tarih_display = d.get("tarih", "-")
                try:
                    dt = datetime.strptime(tarih_display, "%Y-%m-%d")
                    tarih_display = dt.strftime("%d.%m.%Y")
                except ValueError:
                    pass
                durum_d = d.get("durum", "bekliyor")
                lines.append(f"  [{d['id']}] {tarih_display} {d.get('saat','')} — {durum_d.upper()}")

        # Tebligatlar
        tebligatlar = detay.get("tebligatlar", [])
        if tebligatlar:
            lines.append(f"\nTEBLIGATLAR ({len(tebligatlar)}):")
            for t in tebligatlar:
                son_gun = t.get("son_gun", "")
                sg_display = ""
                if son_gun:
                    try:
                        sg_dt = datetime.strptime(son_gun, "%Y-%m-%d")
                        sg_display = f" | Son Gun: {sg_dt.strftime('%d.%m.%Y')}"
                    except ValueError:
                        sg_display = f" | Son Gun: {son_gun}"
                lines.append(f"  [{t['id']}] {t.get('tebligat_turu','-')} — {t.get('durum','').upper()}{sg_display}")

        # Masraflar
        toplam_masraf = detay.get("toplam_masraf", 0)
        masraflar = detay.get("masraflar", [])
        if masraflar:
            lines.append(f"\nMASRAFLAR ({len(masraflar)} kayit — Toplam: {toplam_masraf:,.2f} TL):")
            for m in masraflar[:5]:
                tarih_display = m.get("tarih", "-")
                try:
                    dt = datetime.strptime(tarih_display, "%Y-%m-%d")
                    tarih_display = dt.strftime("%d.%m.%Y")
                except ValueError:
                    pass
                lines.append(f"  [{m['id']}] {tarih_display} | {m.get('kategori','-')} | {m['tutar']:,.2f} TL")
            if len(masraflar) > 5:
                lines.append(f"  ... ve {len(masraflar)-5} kayit daha")

        # Zaman
        toplam_dk = detay.get("toplam_sure_dakika", 0)
        zaman = detay.get("zaman_kayitlari", [])
        if zaman:
            saat = toplam_dk / 60
            lines.append(f"\nZAMAN ({len(zaman)} kayit — Toplam: {toplam_dk} dk / {saat:.2f} sa)")

        # Vekaletler
        vekaletler = detay.get("vekaletler", [])
        if vekaletler:
            lines.append(f"\nVEKALETLER ({len(vekaletler)}):")
            for v in vekaletler:
                lines.append(f"  [{v['id']}] {v.get('vekalet_turu','-')} — {v.get('durum','').upper()}")

        # Notlar
        notlar = detay.get("notlar", [])
        if notlar:
            lines.append(f"\nNOTLAR ({len(notlar)}):")
            for n in notlar[:5]:
                lines.append(f"  [{n['id']}] {n.get('etiket','normal')} | {n.get('metin','')[:80]}")

        return "\n".join(lines)

    def _list(self, durum: str) -> str:
        db = get_db()
        davalar = db.dava_listele(durum=durum if durum else None)

        if not davalar:
            return "Kayitli dava bulunmuyor."

        lines = [f"DAVA LISTESI ({len(davalar)} kayit)", "=" * 55]
        for d in davalar:
            lines.append(
                f"\n[{d['id']}] {d['dava_no']} — {(d.get('durum') or 'aktif').upper()}\n"
                f"  Muvekil: {d.get('muvekil_adi') or '-'}\n"
                f"  Mahkeme: {d.get('mahkeme') or '-'}\n"
                f"  Tur: {d.get('dava_turu') or '-'}\n"
                f"  Ozet: {(d.get('ozet') or '-')[:80]}"
            )

        return "\n".join(lines)

    def _update(self, dava_id: str, dava_no: str, mahkeme: str, dava_turu: str,
                ozet: str, notlar: str) -> str:
        db = get_db()
        target_id = None

        if dava_id:
            try:
                target_id = int(dava_id.strip())
            except ValueError:
                pass
        if target_id is None and dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                target_id = dava["id"]

        if target_id is None:
            return "Dava bulunamadi. dava_id veya dava_no belirtin."

        updates = {}
        guncellenen = []
        if mahkeme:
            updates["mahkeme"] = mahkeme.strip()
            guncellenen.append("mahkeme")
        if dava_turu:
            updates["dava_turu"] = dava_turu.strip().lower()
            guncellenen.append("dava_turu")
        if ozet:
            updates["ozet"] = ozet.strip()
            guncellenen.append("ozet")
        if notlar:
            updates["notlar"] = notlar.strip()
            guncellenen.append("notlar")

        if not guncellenen:
            return "Guncellenecek alan belirtilmedi."

        db.dava_guncelle(target_id, **updates)
        return f"DAVA GUNCELLENDI [ID: {target_id}]\nGuncellenen alanlar: {', '.join(guncellenen)}"

    def _search(self, query: str) -> str:
        if not query:
            return "Arama terimi belirtilmedi."
        db = get_db()
        sonuclar = db.dava_bul(query.strip())

        if not sonuclar:
            return f"'{query}' icin sonuc bulunamadi."

        lines = [f"ARAMA SONUCLARI: '{query}' ({len(sonuclar)} sonuc)", "=" * 55]
        for d in sonuclar:
            lines.append(
                f"\n[{d['id']}] {d['dava_no']} — {(d.get('durum') or 'aktif').upper()}\n"
                f"  Muvekil: {d.get('muvekil_adi') or '-'}\n"
                f"  Mahkeme: {d.get('mahkeme') or '-'}\n"
                f"  Ozet: {(d.get('ozet') or '-')[:80]}"
            )
        return "\n".join(lines)

    def _status_update(self, dava_id: str, dava_no: str, durum: str) -> str:
        if not durum:
            return "Yeni durum belirtilmedi. Gecerli: aktif, kapali, beklemede"

        db = get_db()
        target_id = None
        if dava_id:
            try:
                target_id = int(dava_id.strip())
            except ValueError:
                pass
        if target_id is None and dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                target_id = dava["id"]

        if target_id is None:
            return "Dava bulunamadi."

        db.dava_guncelle(target_id, durum=durum.strip().lower())
        return f"Dava durumu guncellendi: {durum.strip().upper()}"

    def _dashboard(self) -> str:
        db = get_db()
        ozet = db.gunluk_ozet()

        lines = [
            f"GUNLUK OZET — {ozet['tarih']}",
            f"{'='*60}",
            f"Aktif Dava: {ozet['aktif_dava_sayisi']}",
        ]

        # Today's hearings
        durusmalar = ozet.get("bugunki_durusmalar", [])
        if durusmalar:
            lines.append(f"\nBUGUNKU DURUSMALAR ({len(durusmalar)}):")
            for d in durusmalar:
                lines.append(f"  {d.get('saat','')} | {d.get('dava_no') or '-'} | {d.get('mahkeme','')}")
        else:
            lines.append("\nBugun durusma yok.")

        # Urgent notifications
        tebligatlar = ozet.get("acil_tebligatlar", [])
        if tebligatlar:
            lines.append(f"\nACIL TEBLIGATLAR ({len(tebligatlar)}):")
            for t in tebligatlar:
                son_gun = t.get("son_gun", "")
                try:
                    sg_dt = datetime.strptime(son_gun, "%Y-%m-%d")
                    son_gun = sg_dt.strftime("%d.%m.%Y")
                except ValueError:
                    pass
                lines.append(f"  {t.get('dava_no') or '-'} | Son Gun: {son_gun} | {t.get('tebligat_turu','')}")

        # Expiring powers of attorney
        vekaletler = ozet.get("dolan_vekaletler", [])
        if vekaletler:
            lines.append(f"\nSURESI DOLAN VEKALETLER ({len(vekaletler)}):")
            for v in vekaletler:
                bitis = v.get("bitis_tarihi", "")
                try:
                    bt_dt = datetime.strptime(bitis, "%Y-%m-%d")
                    bitis = bt_dt.strftime("%d.%m.%Y")
                except ValueError:
                    pass
                lines.append(f"  {v.get('muvekil_adi') or '-'} | Bitis: {bitis}")

        # Active timer
        zamanlayici = ozet.get("aktif_zamanlayici")
        if zamanlayici:
            baslangic = datetime.fromisoformat(zamanlayici["baslangic"])
            gecen = int((datetime.now() - baslangic).total_seconds() / 60)
            lines.append(f"\nAKTIF ZAMANLAYICI: {zamanlayici.get('dava_no') or zamanlayici.get('aciklama','-')} ({gecen} dk)")

        # Recent notes
        notlar = ozet.get("son_notlar", [])
        if notlar:
            lines.append(f"\nSON NOTLAR ({len(notlar)}):")
            for n in notlar:
                zaman = n.get("created_at", "")
                try:
                    dt = datetime.fromisoformat(zaman)
                    zaman = dt.strftime("%d.%m %H:%M")
                except (ValueError, TypeError):
                    pass
                lines.append(f"  [{zaman}] {n.get('metin','')[:60]}")

        lines.append(f"\n{'='*60}")
        return "\n".join(lines)

    def _client_file(self, client_id_or_name: str) -> str:
        if not client_id_or_name:
            return "Muvekil ID'si veya adi belirtin."

        db = get_db()

        # Try as int first
        try:
            dosya = db.muvekil_dosya(int(client_id_or_name.strip()))
        except (ValueError, TypeError):
            dosya = db.muvekil_dosya(client_id_or_name.strip())

        if dosya is None:
            return "Muvekil bulunamadi."

        lines = [
            f"MUVEKIL DOSYASI",
            f"{'='*60}",
            f"ID: {dosya['id']}",
            f"Ad: {dosya['ad']}",
            f"Telefon: {dosya.get('telefon') or '-'}",
            f"E-posta: {dosya.get('email') or '-'}",
            f"TC: {dosya.get('tc_no') or '-'}",
        ]

        # Davalar
        davalar = dosya.get("davalar", [])
        if davalar:
            lines.append(f"\nDAVALAR ({len(davalar)}):")
            for d in davalar:
                lines.append(f"  [{d['id']}] {d['dava_no']} — {(d.get('durum') or 'aktif').upper()} | {d.get('mahkeme','')}")

        # Durusmalar
        durusmalar = dosya.get("durusmalar", [])
        if durusmalar:
            lines.append(f"\nDURUSMALAR ({len(durusmalar)}):")
            for d in durusmalar[:10]:
                tarih = d.get("tarih", "-")
                try:
                    dt = datetime.strptime(tarih, "%Y-%m-%d")
                    tarih = dt.strftime("%d.%m.%Y")
                except ValueError:
                    pass
                lines.append(f"  {tarih} {d.get('saat','')} | {d.get('dava_no','-')} | {d.get('durum','').upper()}")

        # Masraflar toplam
        toplam_masraf = dosya.get("toplam_masraf", 0)
        masraflar = dosya.get("masraflar", [])
        if masraflar:
            lines.append(f"\nMASRAFLAR: {len(masraflar)} kayit — TOPLAM: {toplam_masraf:,.2f} TL")

        # Vekaletler
        vekaletler = dosya.get("vekaletler", [])
        if vekaletler:
            lines.append(f"\nVEKALETLER ({len(vekaletler)}):")
            for v in vekaletler:
                lines.append(f"  [{v['id']}] {v.get('vekalet_turu','-')} — {v.get('durum','').upper()}")

        # Notlar
        notlar = dosya.get("notlar", [])
        if notlar:
            lines.append(f"\nNOTLAR ({len(notlar)}):")
            for n in notlar[:5]:
                lines.append(f"  {n.get('metin','')[:80]}")

        return "\n".join(lines)
