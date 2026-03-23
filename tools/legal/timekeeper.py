"""Zaman takip araci — dava bazli faturalanabilir saat takibi."""

from __future__ import annotations

from datetime import datetime
from tools.base import BaseTool
from core.database import get_db


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0sa 0dk"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}sa {minutes}dk"


def _format_hours(seconds: float) -> str:
    return f"{seconds / 3600:.2f}"


class TimekeeperTool(BaseTool):
    """Dava bazli faturalanabilir saat takibi — avukat ofisleri icin."""

    name = "zaman_takip"
    description = (
        "Dava bazli faturalanabilir saat takibi. "
        "Zamanlayici baslatir/durdurur, kayitlari listeler ve rapor olusturur. "
        "Avukat ofisleri icin faturalama sistemi."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "stop", "list", "report"],
                "description": "Islem: start (baslat), stop (durdur), list (listele), report (rapor)",
            },
            "case_name": {
                "type": "string",
                "description": "Dava/dosya adi (start ve report icin kullanilir)",
            },
            "description": {
                "type": "string",
                "description": "Yapilan isin aciklamasi (start icin kullanilir)",
            },
        },
        "required": ["action"],
    }

    def run(self, action: str = "list", case_name: str = "", description: str = "", **kw) -> str:
        if action == "start":
            return self._start(case_name, description)
        elif action == "stop":
            return self._stop()
        elif action == "list":
            return self._list(case_name)
        elif action == "report":
            return self._report(case_name)
        else:
            return f"Bilinmeyen islem: {action}. Gecerli islemler: start, stop, list, report"

    def _start(self, case_name: str, description: str) -> str:
        if not case_name:
            return "Dava/dosya adi belirtilmedi."

        db = get_db()

        # Check for active timer
        aktif = db.zaman_aktif()
        if aktif is not None:
            return (
                f"Zaten aktif bir zamanlayici var: '{aktif.get('dava_no') or aktif.get('aciklama', '-')}' "
                f"({aktif.get('aciklama', '-')}). Once 'stop' ile durdurun."
            )

        # Find dava_id from case_name
        dava_id = None
        dava = db.dava_bul_by_no(case_name.strip())
        if dava:
            dava_id = dava["id"]

        kayit_id = db.zaman_baslat(
            dava_id=dava_id,
            aciklama=description or case_name,
        )

        start_display = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            f"Zamanlayici baslatildi:\n"
            f"  Dava: {case_name}\n"
            f"  Aciklama: {description or 'Belirtilmedi'}\n"
            f"  Baslangic: {start_display}"
        )

    def _stop(self) -> str:
        db = get_db()
        aktif = db.zaman_aktif()

        if aktif is None:
            return "Aktif zamanlayici yok. Once 'start' ile baslatin."

        result = db.zaman_durdur(aktif["id"])
        if result is None:
            return "Zamanlayici durdurulamadi."

        sure_saniye = result["sure_dakika"] * 60
        sure_saat = result["sure_dakika"] / 60

        return (
            f"Zamanlayici durduruldu:\n"
            f"  Dava: {result.get('dava_no') or result.get('aciklama', '-')}\n"
            f"  Aciklama: {result.get('aciklama', '-')}\n"
            f"  Sure: {_format_duration(sure_saniye)} ({sure_saat:.2f} saat)\n"
            f"  Tarih: {datetime.now().strftime('%Y-%m-%d')}"
        )

    def _list(self, case_name: str = "") -> str:
        db = get_db()

        dava_id = None
        if case_name:
            dava = db.dava_bul_by_no(case_name.strip())
            if dava:
                dava_id = dava["id"]

        entries = db.zaman_listele(dava_id=dava_id)
        aktif = db.zaman_aktif()

        if not entries and aktif is None:
            return "Henuz zaman kaydi yok."

        satirlar = []

        # Active timer
        if aktif is not None:
            start = datetime.fromisoformat(aktif["baslangic"])
            gecen = (datetime.now() - start).total_seconds()
            satirlar.append(
                f"  * AKTIF: {aktif.get('dava_no') or aktif.get('aciklama', '-')} — "
                f"{aktif.get('aciklama', '-')} ({_format_duration(gecen)} gecti)"
            )
            satirlar.append("")

        # Filter by case_name text if no dava_id found
        if case_name and dava_id is None:
            entries = [e for e in entries if case_name.lower() in (e.get("aciklama") or "").lower()]

        completed = [e for e in entries if e.get("bitis")]

        if completed:
            satirlar.insert(0, f"Toplam {len(completed)} kayit:")
            for i, e in enumerate(completed, 1):
                sure_dk = e.get("sure_dakika") or 0
                sure_saat = sure_dk / 60
                tarih = e.get("baslangic", "")[:10]
                dava_display = e.get("dava_no") or e.get("aciklama") or "-"
                satirlar.append(
                    f"  {i}. [{tarih}] {dava_display} — "
                    f"{e.get('aciklama', '-')} ({_format_duration(sure_dk*60)}, {sure_saat:.2f} sa)"
                )
        elif not satirlar:
            if case_name:
                return f"'{case_name}' icin kayit bulunamadi."
            return "Henuz zaman kaydi yok."

        return "\n".join(satirlar)

    def _report(self, case_name: str = "") -> str:
        db = get_db()

        dava_id = None
        if case_name:
            dava = db.dava_bul_by_no(case_name.strip())
            if dava:
                dava_id = dava["id"]

        rapor = db.zaman_raporu(dava_id=dava_id)

        if rapor["kayit_sayisi"] == 0:
            return "Rapor olusturulamadi — henuz kayit yok."

        toplam_saniye = rapor["toplam_dakika"] * 60

        satirlar = [
            "=" * 45,
            "  ZAMAN TAKIP RAPORU",
            "=" * 45,
            "",
            f"  Toplam Kayit: {rapor['kayit_sayisi']}",
            f"  Toplam Sure: {_format_duration(toplam_saniye)} ({_format_hours(toplam_saniye)} saat)",
            "",
            "  DAVA BAZLI OZET:",
            "  " + "-" * 40,
        ]

        for d in rapor["davalar"]:
            dava_display = d.get("dava_no") or "Bilinmiyor"
            sure_saniye = d["toplam_dakika"] * 60
            satirlar.append(f"    {dava_display}: {_format_duration(sure_saniye)} ({_format_hours(sure_saniye)} saat)")

        # Day-based summary
        gun_toplam: dict[str, int] = {}
        for e in rapor["kayitlar"]:
            gun = (e.get("baslangic") or "")[:10]
            if gun:
                gun_toplam[gun] = gun_toplam.get(gun, 0) + (e.get("sure_dakika") or 0)

        if gun_toplam:
            satirlar.extend([
                "",
                "  GUN BAZLI OZET:",
                "  " + "-" * 40,
            ])
            for gun in sorted(gun_toplam.keys(), reverse=True):
                sure = gun_toplam[gun] * 60
                satirlar.append(f"    {gun}: {_format_duration(sure)} ({_format_hours(sure)} saat)")

        satirlar.append("=" * 45)

        return "\n".join(satirlar)
