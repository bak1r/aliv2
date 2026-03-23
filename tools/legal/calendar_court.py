"""Durusma Takvimi Araci — Mahkeme tarihleri, durusma ve randevu yonetimi."""

from __future__ import annotations

from datetime import datetime, timedelta
from tools.base import BaseTool
from core.database import get_db


class DurusmaTakvimiTool(BaseTool):
    name = "durusma_takvimi"
    description = (
        "Mahkeme durusma takvimi yonetimi. Durusma tarihi ekleme, listeleme, "
        "yaklasan davaları goruntuleme ve silme islemleri."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem turu: add | list | upcoming | delete",
                "enum": ["add", "list", "upcoming", "delete"],
            },
            "date": {
                "type": "string",
                "description": "Tarih (GG.AA.YYYY veya YYYY-MM-DD)",
            },
            "time": {
                "type": "string",
                "description": "Saat (SS:DD, ornek: 14:30)",
            },
            "court": {
                "type": "string",
                "description": "Mahkeme adi (ornek: Istanbul 3. Agir Ceza Mahkemesi)",
            },
            "case_no": {
                "type": "string",
                "description": "Esas numarasi (ornek: 2026/123)",
            },
            "description": {
                "type": "string",
                "description": "Aciklama veya notlar",
            },
            "event_id": {
                "type": "string",
                "description": "Silinecek etkinlik ID'si (delete islemi icin)",
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str = "",
        date: str = "",
        time: str = "",
        court: str = "",
        case_no: str = "",
        description: str = "",
        event_id: str = "",
        **kw,
    ) -> str:
        action = action.strip().lower()

        if action == "add":
            return self._add(date, time, court, case_no, description)
        elif action == "list":
            return self._list()
        elif action == "upcoming":
            return self._upcoming()
        elif action == "delete":
            return self._delete(event_id, case_no)
        else:
            return f"Bilinmeyen islem: {action}. Gecerli islemler: add, list, upcoming, delete"

    # -----------------------------------------------------------------
    def _parse_date(self, date_str: str) -> datetime | None:
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    # -----------------------------------------------------------------
    def _add(self, date: str, time: str, court: str, case_no: str, description: str) -> str:
        if not date:
            return "Tarih belirtilmedi. Ornek: 25.03.2026"
        if not time:
            return "Saat belirtilmedi. Ornek: 14:30"

        parsed_date = self._parse_date(date)
        if parsed_date is None:
            return f"Gecersiz tarih formati: {date}. Ornek: 25.03.2026 veya 2026-03-25"

        try:
            hour, minute = time.strip().split(":")
            parsed_date = parsed_date.replace(hour=int(hour), minute=int(minute))
        except (ValueError, TypeError):
            return f"Gecersiz saat formati: {time}. Ornek: 14:30"

        db = get_db()
        tarih_iso = parsed_date.strftime("%Y-%m-%d")
        saat_str = parsed_date.strftime("%H:%M")

        # Try to find dava_id from case_no
        dava_id = None
        if case_no:
            dava = db.dava_bul_by_no(case_no.strip())
            if dava:
                dava_id = dava["id"]

        new_id = db.durusma_ekle(
            dava_id=dava_id,
            tarih=tarih_iso,
            saat=saat_str,
            mahkeme=court or "Belirtilmedi",
            notlar=description or "",
        )

        return (
            f"DURUSMA EKLENDI\n"
            f"{'='*40}\n"
            f"ID: {new_id}\n"
            f"Tarih: {parsed_date.strftime('%d.%m.%Y')} {saat_str}\n"
            f"Mahkeme: {court or 'Belirtilmedi'}\n"
            f"Esas No: {case_no or 'Belirtilmedi'}\n"
            f"Aciklama: {description or '-'}\n"
        )

    # -----------------------------------------------------------------
    def _list(self) -> str:
        db = get_db()
        events = db.durusma_listele()
        if not events:
            return "Takvimde kayitli durusma bulunmuyor."

        # Sort by date
        events.sort(key=lambda e: (e.get("tarih", ""), e.get("saat", "")))

        lines = [f"DURUSMA TAKVIMI ({len(events)} kayit)", "=" * 50]
        for ev in events:
            tarih_display = ev["tarih"]
            try:
                dt = datetime.strptime(ev["tarih"], "%Y-%m-%d")
                tarih_display = dt.strftime("%d.%m.%Y")
            except ValueError:
                pass
            hatirlatma = self._hatirlatma_notu(ev)
            dava_no = ev.get("dava_no") or "Belirtilmedi"
            lines.append(
                f"\n[{ev['id']}] {tarih_display} {ev.get('saat','')}{hatirlatma}\n"
                f"  Mahkeme: {ev.get('mahkeme','')}\n"
                f"  Esas No: {dava_no}\n"
                f"  Aciklama: {ev.get('notlar') or '-'}"
            )
        return "\n".join(lines)

    # -----------------------------------------------------------------
    def _upcoming(self) -> str:
        db = get_db()
        yaklasan_list = db.yaklasan_durusmalar(gun=7)

        if not yaklasan_list:
            return "Onumuzdeki 7 gun icinde durusma bulunmuyor."

        lines = [f"YAKLASAN DURUSMALAR (7 gun icinde — {len(yaklasan_list)} adet)", "=" * 50]
        now = datetime.now()
        for ev in yaklasan_list:
            try:
                ev_dt = datetime.strptime(f"{ev['tarih']} {ev.get('saat','00:00')}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            kalan = ev_dt - now
            kalan_saat = int(kalan.total_seconds() // 3600)
            kalan_gun = kalan.days

            hatirlatma = ""
            if kalan.total_seconds() <= 48 * 3600:
                hatirlatma = "  *** 48 SAAT ICINDE — HATIRLATMA ***"

            if kalan_gun > 0:
                kalan_str = f"{kalan_gun} gun {kalan_saat % 24} saat"
            else:
                kalan_str = f"{kalan_saat} saat"

            tarih_display = ev_dt.strftime("%d.%m.%Y")
            dava_no = ev.get("dava_no") or "Belirtilmedi"

            lines.append(
                f"\n[{ev['id']}] {tarih_display} {ev.get('saat','')} (kalan: {kalan_str}){hatirlatma}\n"
                f"  Mahkeme: {ev.get('mahkeme','')}\n"
                f"  Esas No: {dava_no}\n"
                f"  Aciklama: {ev.get('notlar') or '-'}"
            )
        return "\n".join(lines)

    # -----------------------------------------------------------------
    def _delete(self, event_id: str, case_no: str) -> str:
        if not event_id and not case_no:
            return "Silinecek etkinlik icin event_id veya case_no belirtin."

        db = get_db()
        silinen = 0

        if event_id:
            try:
                if db.durusma_sil(int(event_id.strip())):
                    silinen = 1
            except (ValueError, TypeError):
                pass
        elif case_no:
            durusmalar = db.durusma_bul_by_dava_no(case_no.strip())
            for d in durusmalar:
                db.durusma_sil(d["id"])
                silinen += 1

        if silinen == 0:
            return "Eslesen kayit bulunamadi."
        return f"{silinen} durusma kaydi silindi."

    # -----------------------------------------------------------------
    def _hatirlatma_notu(self, ev: dict) -> str:
        try:
            ev_dt = datetime.strptime(f"{ev['tarih']} {ev.get('saat','00:00')}", "%Y-%m-%d %H:%M")
            kalan = ev_dt - datetime.now()
            if 0 < kalan.total_seconds() <= 48 * 3600:
                return "  [!!! YAKIN]"
        except (KeyError, ValueError):
            pass
        return ""
