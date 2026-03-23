"""Hukuki Sure Hesaplama Araci — Itiraz, temyiz, istinaf sureleri."""

from __future__ import annotations

from datetime import datetime, timedelta
from tools.base import BaseTool


# Turk hukukunda onemli sureler (gun)
SURELER = {
    # Ceza hukuku
    "istinaf": {"sure": 7, "aciklama": "Istinaf basvuru suresi (CMK m.272)", "baslangic": "Karar tebliginden itibaren"},
    "temyiz": {"sure": 15, "aciklama": "Temyiz basvuru suresi (CMK m.291)", "baslangic": "Istinaf karari tebliginden itibaren"},
    "itiraz": {"sure": 7, "aciklama": "Karara itiraz suresi (CMK m.268)", "baslangic": "Karar ogrenilmesinden itibaren"},
    "tutukluluk_itiraz": {"sure": 7, "aciklama": "Tutukluluga itiraz (CMK m.104)", "baslangic": "Tutuklama kararindan itibaren"},
    "iddianame_iade": {"sure": 15, "aciklama": "Iddianame iade talebi (CMK m.174)", "baslangic": "Iddianamenin tebliginden itibaren"},

    # Hukuk
    "dava_acma": {"sure": 30, "aciklama": "Genel dava acma suresi", "baslangic": "Hakkin ogrenilmesinden itibaren"},
    "tebligat_cevap": {"sure": 14, "aciklama": "Tebligata cevap suresi", "baslangic": "Tebligat tarihinden itibaren"},

    # Idari
    "idari_dava": {"sure": 60, "aciklama": "Idari islemin iptali davasi (IYUK m.7)", "baslangic": "Islemin tebliginden itibaren"},
    "idari_itiraz": {"sure": 30, "aciklama": "Idari islem itiraz suresi", "baslangic": "Islemin tebliginden itibaren"},

    # Icra
    "icra_itiraz": {"sure": 7, "aciklama": "Icra emrine itiraz (IIK m.16)", "baslangic": "Tebligattan itibaren"},
    "odeme_emri_itiraz": {"sure": 7, "aciklama": "Odeme emrine itiraz (IIK m.62)", "baslangic": "Tebligattan itibaren"},
}


class DeadlineCalcTool(BaseTool):
    name = "sure_hesapla"
    description = (
        "Hukuki sure hesaplama: istinaf, temyiz, itiraz, dava acma, tebligat sureleri. "
        "Baslangic tarihini ve islem turunu belirtin."
    )
    parameters = {
        "type": "object",
        "properties": {
            "islem_turu": {
                "type": "string",
                "description": "Sure turu: istinaf | temyiz | itiraz | tutukluluk_itiraz | iddianame_iade | dava_acma | tebligat_cevap | idari_dava | idari_itiraz | icra_itiraz | odeme_emri_itiraz"
            },
            "baslangic_tarihi": {
                "type": "string",
                "description": "Baslangic tarihi (GG.AA.YYYY veya YYYY-MM-DD)"
            },
            "listele": {
                "type": "boolean",
                "description": "Tum sureleri listele",
                "default": False
            },
        },
        "required": [],
    }

    def run(self, islem_turu: str = "", baslangic_tarihi: str = "", listele: bool = False, **kw) -> str:
        if listele or (not islem_turu and not baslangic_tarihi):
            return self._listele()

        if not islem_turu:
            return "Islem turu belirtilmedi. Kullanilabilir turler: " + ", ".join(SURELER.keys())

        islem = islem_turu.strip().lower()
        if islem not in SURELER:
            return f"Bilinmeyen islem turu: {islem}. Kullanilabilir: {', '.join(SURELER.keys())}"

        sure_info = SURELER[islem]

        # Tarih parse
        if baslangic_tarihi:
            try:
                for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                    try:
                        baslangic = datetime.strptime(baslangic_tarihi.strip(), fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return f"Gecersiz tarih formati: {baslangic_tarihi}. Ornek: 15.03.2026"
            except Exception:
                return f"Tarih parse hatasi: {baslangic_tarihi}"
        else:
            baslangic = datetime.now()

        # Son gun hesapla
        son_gun = baslangic + timedelta(days=sure_info["sure"])

        # Hafta sonu kontrolu (resmi tatil degerlendirmesi)
        if son_gun.weekday() == 5:  # Cumartesi
            son_gun += timedelta(days=2)
        elif son_gun.weekday() == 6:  # Pazar
            son_gun += timedelta(days=1)

        kalan = (son_gun - datetime.now()).days

        return (
            f"SURE HESAPLAMA\n"
            f"{'='*40}\n"
            f"Islem: {sure_info['aciklama']}\n"
            f"Baslangic: {sure_info['baslangic']}\n"
            f"Sure: {sure_info['sure']} gun\n"
            f"\n"
            f"Baslangic Tarihi: {baslangic.strftime('%d.%m.%Y')}\n"
            f"Son Gun: {son_gun.strftime('%d.%m.%Y %A')}\n"
            f"Kalan: {kalan} gun {'(GECMIS!)' if kalan < 0 else '(ACIL!)' if kalan <= 3 else ''}\n"
            f"\n"
            f"NOT: Resmi tatiller hesaba dahil edilmemistir. Manuel kontrol edin."
        )

    def _listele(self) -> str:
        lines = ["HUKUKI SURELER TABLOSU", "=" * 50]
        for key, info in SURELER.items():
            lines.append(f"\n{key} ({info['sure']} gun)")
            lines.append(f"  {info['aciklama']}")
            lines.append(f"  Baslangic: {info['baslangic']}")
        return "\n".join(lines)
