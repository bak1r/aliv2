"""Muvekil Takip Araci — Muvekil bilgileri ve dava atamasi yonetimi."""

from __future__ import annotations

from datetime import datetime
from tools.base import BaseTool
from core.database import get_db


class MuvekilTakipTool(BaseTool):
    name = "muvekil_takip"
    description = (
        "Muvekil (muvekkil) bilgi yonetimi. Muvekil ekleme, listeleme, "
        "arama, guncelleme ve not ekleme islemleri."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem turu: add | list | search | update | notes",
                "enum": ["add", "list", "search", "update", "notes"],
            },
            "name": {
                "type": "string",
                "description": "Muvekil adi-soyadi",
            },
            "phone": {
                "type": "string",
                "description": "Telefon numarasi",
            },
            "email": {
                "type": "string",
                "description": "E-posta adresi",
            },
            "case_summary": {
                "type": "string",
                "description": "Dava ozeti veya konusu",
            },
            "note": {
                "type": "string",
                "description": "Eklenecek not (notes islemi icin)",
            },
            "client_id": {
                "type": "string",
                "description": "Muvekil ID'si (update ve notes islemleri icin)",
            },
            "query": {
                "type": "string",
                "description": "Arama terimi — isim veya dava icinde arar (search islemi icin)",
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str = "",
        name: str = "",
        phone: str = "",
        email: str = "",
        case_summary: str = "",
        note: str = "",
        client_id: str = "",
        query: str = "",
        **kw,
    ) -> str:
        action = action.strip().lower()

        if action == "add":
            return self._add(name, phone, email, case_summary)
        elif action == "list":
            return self._list()
        elif action == "search":
            return self._search(query or name or "")
        elif action == "update":
            return self._update(client_id, name, phone, email, case_summary)
        elif action == "notes":
            return self._add_note(client_id, name, note)
        else:
            return f"Bilinmeyen islem: {action}. Gecerli islemler: add, list, search, update, notes"

    # -----------------------------------------------------------------
    def _add(self, name: str, phone: str, email: str, case_summary: str) -> str:
        if not name:
            return "Muvekil adi belirtilmedi."

        db = get_db()
        new_id = db.muvekil_ekle(
            ad=name.strip(),
            telefon=phone.strip() if phone else "",
            email=email.strip() if email else "",
            notlar=case_summary.strip() if case_summary else "",
        )

        return (
            f"MUVEKIL EKLENDI\n"
            f"{'='*40}\n"
            f"ID: {new_id}\n"
            f"Ad Soyad: {name.strip()}\n"
            f"Telefon: {phone.strip() if phone else '-'}\n"
            f"E-posta: {email.strip() if email else '-'}\n"
            f"Dava Ozeti: {case_summary.strip() if case_summary else '-'}\n"
        )

    # -----------------------------------------------------------------
    def _list(self) -> str:
        db = get_db()
        clients = db.muvekil_listele()
        if not clients:
            return "Kayitli muvekil bulunmuyor."

        lines = [f"MUVEKIL LISTESI ({len(clients)} kayit)", "=" * 50]
        for c in clients:
            # Count notes for this client
            notlar = db.not_ara("")  # We'll count from the DB
            not_sayisi = len([n for n in (db._get_conn().execute(
                "SELECT id FROM notlar WHERE muvekil_id=?", (c["id"],)).fetchall())])
            lines.append(
                f"\n[{c['id']}] {c['ad']}\n"
                f"  Telefon: {c.get('telefon') or '-'}\n"
                f"  E-posta: {c.get('email') or '-'}\n"
                f"  Dava: {c.get('notlar') or '-'}\n"
                f"  Not sayisi: {not_sayisi}"
            )
        return "\n".join(lines)

    # -----------------------------------------------------------------
    def _search(self, query: str) -> str:
        if not query:
            return "Arama terimi belirtilmedi. name veya query parametresi gerekli."

        db = get_db()
        sonuclar = db.muvekil_bul(query.strip())

        if not sonuclar:
            return f"'{query}' icin sonuc bulunamadi."

        lines = [f"ARAMA SONUCLARI: '{query}' ({len(sonuclar)} sonuc)", "=" * 50]
        for c in sonuclar:
            lines.append(
                f"\n[{c['id']}] {c['ad']}\n"
                f"  Telefon: {c.get('telefon') or '-'}\n"
                f"  E-posta: {c.get('email') or '-'}\n"
                f"  Dava: {c.get('notlar') or '-'}"
            )
        return "\n".join(lines)

    # -----------------------------------------------------------------
    def _update(self, client_id: str, name: str, phone: str, email: str, case_summary: str) -> str:
        if not client_id and not name:
            return "Guncellenecek muvekil icin client_id veya name belirtin."

        db = get_db()

        # Find client
        target = None
        if client_id:
            try:
                target = db.muvekil_detay(int(client_id.strip()))
            except (ValueError, TypeError):
                pass
        if target is None and name:
            target = db.muvekil_bul_by_ad(name.strip())

        if target is None:
            return "Eslesen muvekil bulunamadi."

        # Build updates
        updates = {}
        guncellenen = []
        if name and name.strip() != target.get("ad"):
            updates["ad"] = name.strip()
            guncellenen.append("ad_soyad")
        if phone:
            updates["telefon"] = phone.strip()
            guncellenen.append("telefon")
        if email:
            updates["email"] = email.strip()
            guncellenen.append("email")
        if case_summary:
            updates["notlar"] = case_summary.strip()
            guncellenen.append("dava_ozeti")

        if not guncellenen:
            return "Guncellenecek alan belirtilmedi."

        db.muvekil_guncelle(target["id"], **updates)

        return (
            f"MUVEKIL GUNCELLENDI\n"
            f"{'='*40}\n"
            f"ID: {target['id']}\n"
            f"Ad Soyad: {updates.get('ad', target['ad'])}\n"
            f"Guncellenen alanlar: {', '.join(guncellenen)}\n"
        )

    # -----------------------------------------------------------------
    def _add_note(self, client_id: str, name: str, note: str) -> str:
        if not client_id and not name:
            return "Not eklenecek muvekil icin client_id veya name belirtin."
        if not note:
            return "Not metni belirtilmedi."

        db = get_db()

        # Find client
        target = None
        if client_id:
            try:
                target = db.muvekil_detay(int(client_id.strip()))
            except (ValueError, TypeError):
                pass
        if target is None and name:
            target = db.muvekil_bul_by_ad(name.strip())

        if target is None:
            return "Eslesen muvekil bulunamadi."

        not_id = db.not_ekle(
            metin=note.strip(),
            etiket="normal",
            muvekil_id=target["id"],
        )

        tarih_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        not_sayisi = len(db._get_conn().execute(
            "SELECT id FROM notlar WHERE muvekil_id=?", (target["id"],)).fetchall())

        return (
            f"NOT EKLENDI\n"
            f"{'='*40}\n"
            f"Muvekil: {target['ad']} [{target['id']}]\n"
            f"Tarih: {tarih_str}\n"
            f"Not: {note.strip()}\n"
            f"Toplam not sayisi: {not_sayisi}\n"
        )
