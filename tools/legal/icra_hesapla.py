"""Icra Takip Hesaplama Araci — Faiz, masraf, vekalet ucreti hesabi."""

from __future__ import annotations

from datetime import datetime, timedelta
from tools.base import BaseTool


# 2024-2026 yasal faiz oranlari (yillik %)
YASAL_FAIZ = {
    2024: 24.0,
    2025: 24.0,
    2026: 24.0,  # Guncellenmeli
}

# Avukatlik asgari ucret tarifesi 2026 bazi kalemleri (TL)
# Not: Gercek degerler her yil guncellenir
AAUT_2026 = {
    "icra_takip": 6_600,
    "icra_inkar_tazminati_orani": 0.20,  # %20
    "sulh_hukuk": 12_200,
    "asliye_hukuk": 17_400,
    "asliye_ticaret": 22_600,
    "is_mahkemesi": 12_200,
    "idare_mahkemesi": 17_400,
    "agir_ceza": 35_000,
    "asliye_ceza": 17_400,
}

# Icra harclari (2026 yaklasimlari)
ICRA_HARCLARI = {
    "basvurma_harci": 427.60,
    "pesin_harc_orani": 0.005,  # Binde 5
    "tahsil_harci_orani": 0.0228,  # %2.28
    "cezaevi_yapim_harci_orani": 0.02,  # %2
}


class IcraHesaplaTool(BaseTool):
    name = "icra_hesapla"
    description = (
        "Icra takip hesaplamasi: asil alacak uzerinden yasal/ticari faiz, "
        "icra harclari, vekalet ucreti, icra inkar tazminati ve toplam alacak hesabi. "
        "Ilamlı veya ilamsiz icra takipleri icin kullanilabilir."
    )
    parameters = {
        "type": "object",
        "properties": {
            "asil_alacak": {
                "type": "number",
                "description": "Asil alacak tutari (TL)",
            },
            "faiz_baslangic": {
                "type": "string",
                "description": "Faiz baslangic tarihi (GG.AA.YYYY veya YYYY-MM-DD)",
            },
            "faiz_bitis": {
                "type": "string",
                "description": "Faiz bitis tarihi (bos = bugun)",
            },
            "faiz_turu": {
                "type": "string",
                "description": "Faiz turu: yasal | ticari | ozel",
                "enum": ["yasal", "ticari", "ozel"],
            },
            "ozel_faiz_orani": {
                "type": "number",
                "description": "Ozel faiz orani (yillik %, sadece faiz_turu=ozel ise)",
            },
            "takip_turu": {
                "type": "string",
                "description": "Takip turu: ilamsiz | ilamli",
                "enum": ["ilamsiz", "ilamli"],
            },
            "mahkeme_turu": {
                "type": "string",
                "description": "Mahkeme turu (vekalet ucreti icin): icra_takip | sulh_hukuk | asliye_hukuk | asliye_ticaret | is_mahkemesi",
            },
            "inkar_tazminati": {
                "type": "boolean",
                "description": "Icra inkar tazminati hesaplansin mi? (ilamsiz takipte itirazin iptali halinde)",
            },
        },
        "required": ["asil_alacak"],
    }

    def run(
        self,
        asil_alacak: float = 0,
        faiz_baslangic: str = "",
        faiz_bitis: str = "",
        faiz_turu: str = "yasal",
        ozel_faiz_orani: float = 0,
        takip_turu: str = "ilamsiz",
        mahkeme_turu: str = "icra_takip",
        inkar_tazminati: bool = False,
        **kw,
    ) -> str:
        if asil_alacak <= 0:
            return "Asil alacak tutari belirtilmedi veya gecersiz."

        adimlar = []
        toplam = asil_alacak
        adimlar.append(f"Asil Alacak: {asil_alacak:,.2f} TL")

        # --- Faiz Hesabi ---
        faiz_tutari = 0.0
        faiz_gun = 0
        if faiz_baslangic:
            baslangic = self._parse_date(faiz_baslangic)
            if baslangic is None:
                return f"Gecersiz faiz baslangic tarihi: {faiz_baslangic}"

            if faiz_bitis:
                bitis = self._parse_date(faiz_bitis)
                if bitis is None:
                    return f"Gecersiz faiz bitis tarihi: {faiz_bitis}"
            else:
                bitis = datetime.now()

            faiz_gun = (bitis - baslangic).days
            if faiz_gun < 0:
                return "Faiz bitis tarihi baslangic tarihinden once olamaz."

            if faiz_turu == "yasal":
                yillik_oran = YASAL_FAIZ.get(baslangic.year, 24.0)
                oran_aciklama = f"Yasal faiz (%{yillik_oran})"
            elif faiz_turu == "ticari":
                yillik_oran = YASAL_FAIZ.get(baslangic.year, 24.0) * 1.5
                oran_aciklama = f"Ticari faiz (%{yillik_oran})"
            elif faiz_turu == "ozel" and ozel_faiz_orani > 0:
                yillik_oran = ozel_faiz_orani
                oran_aciklama = f"Ozel faiz (%{yillik_oran})"
            else:
                yillik_oran = YASAL_FAIZ.get(baslangic.year, 24.0)
                oran_aciklama = f"Yasal faiz (%{yillik_oran})"

            faiz_tutari = asil_alacak * (yillik_oran / 100) * (faiz_gun / 365)
            toplam += faiz_tutari

            adimlar.append(
                f"\nFAIZ HESABI:\n"
                f"  Tur: {oran_aciklama}\n"
                f"  Donem: {baslangic.strftime('%d.%m.%Y')} - {bitis.strftime('%d.%m.%Y')} ({faiz_gun} gun)\n"
                f"  Faiz Tutari: {faiz_tutari:,.2f} TL"
            )

        # --- Icra Harclari ---
        basvurma = ICRA_HARCLARI["basvurma_harci"]
        pesin_harc = asil_alacak * ICRA_HARCLARI["pesin_harc_orani"]
        toplam_harc = basvurma + pesin_harc
        toplam += toplam_harc

        adimlar.append(
            f"\nICRA HARCLARI:\n"
            f"  Basvurma Harci: {basvurma:,.2f} TL\n"
            f"  Pesin Harc (binde 5): {pesin_harc:,.2f} TL\n"
            f"  Toplam Harc: {toplam_harc:,.2f} TL"
        )

        # --- Vekalet Ucreti ---
        mahkeme_turu = mahkeme_turu.strip().lower() if mahkeme_turu else "icra_takip"
        vekalet = AAUT_2026.get(mahkeme_turu, AAUT_2026["icra_takip"])
        toplam += vekalet

        adimlar.append(
            f"\nVEKALET UCRETI:\n"
            f"  Mahkeme Turu: {mahkeme_turu}\n"
            f"  AAUT Asgarisi: {vekalet:,.2f} TL"
        )

        # --- Icra Inkar Tazminati ---
        inkar_tutari = 0.0
        if inkar_tazminati:
            inkar_tutari = asil_alacak * AAUT_2026["icra_inkar_tazminati_orani"]
            toplam += inkar_tutari
            adimlar.append(
                f"\nICRA INKAR TAZMINATI (%20):\n"
                f"  Tutar: {inkar_tutari:,.2f} TL"
            )

        # --- Tahsil Harci (tahsil edildiginde) ---
        tahsil_harci = toplam * ICRA_HARCLARI["tahsil_harci_orani"]
        cezaevi_harci = toplam * ICRA_HARCLARI["cezaevi_yapim_harci_orani"]

        # --- Sonuc ---
        lines = [
            f"\n{'='*55}",
            "ICRA TAKIP HESAP TABLOSU",
            f"{'='*55}",
            f"Takip Turu: {'Ilamsiz' if takip_turu == 'ilamsiz' else 'Ilamli'} icra takibi",
            "",
        ]
        lines.extend(adimlar)
        lines.extend([
            f"\n{'='*55}",
            f"ARA TOPLAM (Takip Miktari): {toplam:,.2f} TL",
            f"\nTAHSIL ASAMASINDA EKLENECEK:",
            f"  Tahsil Harci (%2.28): {tahsil_harci:,.2f} TL",
            f"  Cezaevi Yapim Harci (%2): {cezaevi_harci:,.2f} TL",
            f"\nGENEL TOPLAM (tahmini): {toplam + tahsil_harci + cezaevi_harci:,.2f} TL",
            f"\n{'='*55}",
            "UYARI: Bu hesaplama tahminidir. Kesin tutarlar icin icra dairesine basvurun.",
            "Faiz oranlari ve harc miktarlari guncel mevzuata gore degisiklik gosterebilir.",
        ])

        return "\n".join(lines)

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
