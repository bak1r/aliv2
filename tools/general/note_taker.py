"""Not alma araci — notlari SQLite veritabanina kaydeder, listeler, arar, siler."""

from __future__ import annotations

from datetime import datetime
from tools.base import BaseTool
from core.database import get_db


def _format_note(note: dict, idx: int) -> str:
    tag_icon = {"urgent": "(!)", "reminder": "(R)", "normal": "(-)"}.get(note.get("etiket", "normal"), "(-)")
    zaman = note.get("created_at", "?")
    # Format timestamp for display
    try:
        dt = datetime.fromisoformat(zaman)
        zaman = dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        pass
    return f"  {idx}. {tag_icon} [{zaman}] {note.get('metin', '')}"


class NoteTool(BaseTool):
    """Not defteri — ekle, listele, ara, sil."""

    name = "not_al"
    description = (
        "Not defteri araci. Notlari ekler, listeler, arar veya siler. "
        "Etiket olarak urgent, normal veya reminder kullanilabilir."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "search", "delete", "clear"],
                "description": "Yapilacak islem: add (ekle), list (listele), search (ara), delete (sil), clear (tumu sil)",
            },
            "text": {
                "type": "string",
                "description": "Not metni (add icin zorunlu, search icin aranacak kelime, delete icin not numarasi)",
            },
            "tag": {
                "type": "string",
                "enum": ["urgent", "normal", "reminder"],
                "description": "Not etiketi (varsayilan: normal)",
            },
        },
        "required": ["action"],
    }

    def run(self, action: str = "list", text: str = "", tag: str = "normal", **kw) -> str:
        if action == "add":
            return self._add(text, tag)
        elif action == "list":
            return self._list()
        elif action == "search":
            return self._search(text)
        elif action == "delete":
            return self._delete(text)
        elif action == "clear":
            return self._clear()
        else:
            return f"Bilinmeyen islem: {action}. Gecerli islemler: add, list, search, delete, clear"

    def _add(self, text: str, tag: str) -> str:
        if not text:
            return "Not metni bos olamaz."
        if tag not in ("urgent", "normal", "reminder"):
            tag = "normal"

        db = get_db()
        not_id = db.not_ekle(metin=text, etiket=tag)

        tag_tr = {"urgent": "Acil", "normal": "Normal", "reminder": "Hatirlatma"}.get(tag, tag)
        return f"Not eklendi (#{not_id}, {tag_tr}): {text}"

    def _list(self) -> str:
        db = get_db()
        notes = db.not_listele()
        if not notes:
            return "Henuz hic not yok."

        satirlar = [f"Toplam {len(notes)} not:"]
        for i, note in enumerate(notes, 1):
            satirlar.append(_format_note(note, i))
        return "\n".join(satirlar)

    def _search(self, query: str) -> str:
        if not query:
            return "Arama icin bir kelime girin."

        db = get_db()
        bulunanlar = db.not_ara(query)

        if not bulunanlar:
            return f"'{query}' icin sonuc bulunamadi."

        satirlar = [f"'{query}' icin {len(bulunanlar)} sonuc:"]
        for idx, note in enumerate(bulunanlar, 1):
            satirlar.append(_format_note(note, idx))
        return "\n".join(satirlar)

    def _delete(self, text: str) -> str:
        if not text:
            return "Silinecek not numarasini belirtin."

        try:
            idx = int(text)
        except ValueError:
            return "Gecersiz not numarasi. Lutfen sayi girin."

        db = get_db()
        notes = db.not_listele()

        if idx < 1 or idx > len(notes):
            return f"Not #{idx} bulunamadi. Toplam {len(notes)} not var."

        target = notes[idx - 1]
        db.not_sil(target["id"])

        return f"Not #{idx} silindi: {target.get('metin', '')}"

    def _clear(self) -> str:
        db = get_db()
        notes = db.not_listele()
        if not notes:
            return "Zaten hic not yok."
        count = len(notes)
        db.notlari_temizle()
        return f"Tum notlar temizlendi ({count} not silindi)."
