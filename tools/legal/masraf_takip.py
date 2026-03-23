"""Masraf Takip Araci — Dava bazli masraf ve gider yonetimi."""

from __future__ import annotations

from datetime import datetime
from tools.base import BaseTool
from core.database import get_db

# Standart masraf kategorileri
KATEGORILER = {
    "harci": "Mahkeme / icra harci",
    "bilirkisi": "Bilirkisi ucreti",
    "kesif": "Kesif masrafi",
    "tebligat": "Tebligat / posta masrafi",
    "yol": "Yol / ulasim masrafi",
    "konaklama": "Konaklama masrafi",
    "noter": "Noter masrafi",
    "vekaletname": "Vekaletname masrafi",
    "fotokopi": "Fotokopi / suret masrafi",
    "tercume": "Tercume masrafi",
    "diger": "Diger masraflar",
}


class MasrafTakipTool(BaseTool):
    name = "masraf_takip"
    description = (
        "Dava bazli masraf ve gider takibi. Masraf ekleme, listeleme, "
        "dava bazinda ozet, musteri faturasi hazirlama ve silme islemleri. "
        "Kategoriler: harci, bilirkisi, kesif, tebligat, yol, konaklama, noter, vekaletname, fotokopi, tercume, diger."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: add | list | summary | invoice | delete | categories",
                "enum": ["add", "list", "summary", "invoice", "delete", "categories"],
            },
            "dava_no": {
                "type": "string",
                "description": "Esas/dosya numarasi (ornek: 2026/123)",
            },
            "muvekil": {
                "type": "string",
                "description": "Muvekil adi",
            },
            "kategori": {
                "type": "string",
                "description": "Masraf kategorisi: harci | bilirkisi | kesif | tebligat | yol | konaklama | noter | vekaletname | fotokopi | tercume | diger",
            },
            "tutar": {
                "type": "number",
                "description": "Masraf tutari (TL)",
            },
            "aciklama": {
                "type": "string",
                "description": "Masraf aciklamasi",
            },
            "tarih": {
                "type": "string",
                "description": "Masraf tarihi (GG.AA.YYYY). Bos birakilirsa bugunun tarihi.",
            },
            "masraf_id": {
                "type": "string",
                "description": "Silinecek masraf ID'si (delete islemi icin)",
            },
        },
        "required": ["action"],
    }

    def run(
        self,
        action: str = "",
        dava_no: str = "",
        muvekil: str = "",
        kategori: str = "",
        tutar: float = 0,
        aciklama: str = "",
        tarih: str = "",
        masraf_id: str = "",
        **kw,
    ) -> str:
        action = action.strip().lower()
        if action == "add":
            return self._add(dava_no, muvekil, kategori, tutar, aciklama, tarih)
        elif action == "list":
            return self._list(dava_no, muvekil)
        elif action == "summary":
            return self._summary(dava_no, muvekil)
        elif action == "invoice":
            return self._invoice(dava_no, muvekil)
        elif action == "delete":
            return self._delete(masraf_id)
        elif action == "categories":
            return self._categories()
        else:
            return f"Bilinmeyen islem: {action}. Gecerli: add, list, summary, invoice, delete, categories"

    def _add(self, dava_no: str, muvekil: str, kategori: str, tutar: float, aciklama: str, tarih: str) -> str:
        if not dava_no:
            return "Dava/dosya numarasi belirtilmedi."
        if tutar <= 0:
            return "Tutar belirtilmedi veya gecersiz."
        if not kategori:
            kategori = "diger"
        kategori = kategori.strip().lower()
        if kategori not in KATEGORILER:
            return f"Gecersiz kategori: {kategori}. Gecerli: {', '.join(KATEGORILER.keys())}"

        tarih_iso = ""
        tarih_display = ""
        if tarih:
            for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    parsed = datetime.strptime(tarih.strip(), fmt)
                    tarih_iso = parsed.strftime("%Y-%m-%d")
                    tarih_display = parsed.strftime("%d.%m.%Y")
                    break
                except ValueError:
                    continue
            else:
                return f"Gecersiz tarih: {tarih}. Ornek: 15.03.2026"
        else:
            tarih_iso = datetime.now().strftime("%Y-%m-%d")
            tarih_display = datetime.now().strftime("%d.%m.%Y")

        db = get_db()
        # Find dava_id
        dava_id = None
        dava = db.dava_bul_by_no(dava_no.strip())
        if dava:
            dava_id = dava["id"]

        aciklama_full = aciklama.strip() if aciklama else ""
        if muvekil:
            aciklama_full = f"muvekil:{muvekil.strip()} | {aciklama_full}".strip(" |")

        new_id = db.masraf_ekle(
            dava_id=dava_id,
            tutar=tutar,
            kategori=kategori,
            aciklama=aciklama_full,
            tarih=tarih_iso,
        )

        return (
            f"MASRAF EKLENDI\n"
            f"{'='*40}\n"
            f"ID: {new_id}\n"
            f"Dava No: {dava_no}\n"
            f"Muvekil: {muvekil or '-'}\n"
            f"Kategori: {KATEGORILER[kategori]}\n"
            f"Tutar: {tutar:,.2f} TL\n"
            f"Tarih: {tarih_display}\n"
            f"Aciklama: {aciklama or '-'}"
        )

    def _list(self, dava_no: str, muvekil: str) -> str:
        db = get_db()
        if dava_no:
            masraflar = db.masraf_by_dava_no(dava_no.strip())
        else:
            masraflar = db.masraf_listele()

        if muvekil:
            masraflar = [m for m in masraflar if muvekil.lower() in (m.get("aciklama") or "").lower()]

        if not masraflar:
            return "Kayitli masraf bulunmuyor." if not dava_no else "Filtreye uyan masraf bulunamadi."

        toplam = sum(m["tutar"] for m in masraflar)

        lines = [f"MASRAF LISTESI ({len(masraflar)} kayit — Toplam: {toplam:,.2f} TL)", "=" * 55]
        for m in masraflar:
            tarih_display = m.get("tarih", "-")
            try:
                dt = datetime.strptime(tarih_display, "%Y-%m-%d")
                tarih_display = dt.strftime("%d.%m.%Y")
            except ValueError:
                pass

            kat_adi = KATEGORILER.get(m.get("kategori", ""), m.get("kategori", "Diger"))
            dava_no_display = m.get("dava_no") or "-"

            # Extract muvekil from aciklama
            muvekil_display = "-"
            aciklama_text = m.get("aciklama", "")
            for part in aciklama_text.split("|"):
                part = part.strip()
                if part.startswith("muvekil:"):
                    muvekil_display = part.split(":", 1)[1].strip()

            lines.append(
                f"\n[{m['id']}] {tarih_display} | {kat_adi}\n"
                f"  Dava: {dava_no_display} | Muvekil: {muvekil_display}\n"
                f"  Tutar: {m['tutar']:,.2f} TL\n"
                f"  Aciklama: {aciklama_text or '-'}"
            )
        return "\n".join(lines)

    def _summary(self, dava_no: str, muvekil: str) -> str:
        db = get_db()
        dava_id = None
        if dava_no:
            dava = db.dava_bul_by_no(dava_no.strip())
            if dava:
                dava_id = dava["id"]

        rapor = db.masraf_raporu(dava_id=dava_id)

        if rapor["kayit_sayisi"] == 0:
            return "Kayitli masraf bulunmuyor."

        lines = ["MASRAF OZETI", "=" * 50]
        genel_toplam = rapor["genel_toplam"]

        lines.append("\nKATEGORIYE GORE:")
        for kat in rapor["kategoriler"]:
            kat_adi = KATEGORILER.get(kat["kategori"], kat["kategori"] or "Diger")
            oran = (kat["toplam"] / genel_toplam * 100) if genel_toplam > 0 else 0
            lines.append(f"  {kat_adi}: {kat['toplam']:,.2f} TL ({oran:.1f}%)")

        if len(rapor["davalar"]) > 1:
            lines.append("\nDAVAYA GORE:")
            for d in rapor["davalar"]:
                dava_display = d.get("dava_no") or "Belirtilmedi"
                lines.append(f"  {dava_display}: {d['toplam']:,.2f} TL")

        lines.append(f"\nGENEL TOPLAM: {genel_toplam:,.2f} TL")
        lines.append(f"Kayit Sayisi: {rapor['kayit_sayisi']}")

        return "\n".join(lines)

    def _invoice(self, dava_no: str, muvekil: str) -> str:
        db = get_db()
        if dava_no:
            masraflar = db.masraf_by_dava_no(dava_no.strip())
        else:
            masraflar = db.masraf_listele()

        if muvekil:
            masraflar = [m for m in masraflar if muvekil.lower() in (m.get("aciklama") or "").lower()]

        if not masraflar:
            return "Filtreye uyan masraf bulunamadi."

        masraflar.sort(key=lambda m: m.get("tarih", ""))
        toplam = sum(m["tutar"] for m in masraflar)

        # Extract muvekil from first record
        muvekil_adi = "---"
        for part in (masraflar[0].get("aciklama", "") or "").split("|"):
            part = part.strip()
            if part.startswith("muvekil:"):
                muvekil_adi = part.split(":", 1)[1].strip()

        lines = [
            "MASRAF BEYANI / FATURA TASLAGI",
            "=" * 55,
            f"Tarih: {datetime.now().strftime('%d.%m.%Y')}",
            f"Muvekil: {muvekil_adi}",
            f"Dava No: {dava_no or 'Tum davalar'}",
            "",
            f"{'No':<4} {'Tarih':<12} {'Kategori':<25} {'Tutar':>12}",
            "-" * 55,
        ]

        for i, m in enumerate(masraflar, 1):
            tarih_display = m.get("tarih", "-")
            try:
                dt = datetime.strptime(tarih_display, "%Y-%m-%d")
                tarih_display = dt.strftime("%d.%m.%Y")
            except ValueError:
                pass
            kat_adi = KATEGORILER.get(m.get("kategori", ""), m.get("kategori", "Diger"))
            lines.append(
                f"{i:<4} {tarih_display:<12} {kat_adi:<25} {m['tutar']:>10,.2f} TL"
            )

        lines.append("-" * 55)
        lines.append(f"{'TOPLAM':>41} {toplam:>10,.2f} TL")
        lines.append("")
        lines.append("NOT: Bu belge masraf beyani amaciyla hazirlanmistir.")

        return "\n".join(lines)

    def _delete(self, masraf_id: str) -> str:
        if not masraf_id:
            return "Silinecek masraf ID'si belirtin."
        db = get_db()
        try:
            if db.masraf_sil(int(masraf_id.strip())):
                return "1 masraf kaydi silindi."
        except (ValueError, TypeError):
            pass
        return "Eslesen masraf kaydi bulunamadi."

    def _categories(self) -> str:
        lines = ["MASRAF KATEGORILERI", "=" * 40]
        for key, desc in KATEGORILER.items():
            lines.append(f"  {key:<15} {desc}")
        return "\n".join(lines)
