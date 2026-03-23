"""Ceza hesaplama araci — TCK'ya gore ceza hesabi."""

from __future__ import annotations
from tools.base import BaseTool


class CezaHesaplaTool(BaseTool):
    name = "ceza_hesapla"
    description = "TCK'ya gore ceza hesaplama: temel ceza, agirlastirici/hafifletici nedenler, tesebbus, istirak, zincirleme suc."
    parameters = {
        "type": "object",
        "properties": {
            "temel_ceza_ay": {"type": "number", "description": "Temel ceza (ay olarak)"},
            "agirlastirici_orani": {"type": "number", "description": "Agirlastirici neden orani (ornek: 0.5 = yarim arttirma)"},
            "hafifletici_orani": {"type": "number", "description": "Hafifletici neden orani (ornek: 0.33 = ucte bir indirim)"},
            "tesebbus": {"type": "boolean", "description": "Tesebbus indirimi uygulansın mi?"},
            "istirak_turu": {"type": "string", "description": "Istirak turu: azmettiren | yardim_eden | bos"},
            "zincirleme_suc_sayisi": {"type": "number", "description": "Zincirleme suc sayisi (0 = yok)"},
            "iyi_hal": {"type": "boolean", "description": "Iyi hal indirimi (1/6)"},
            "yas_grubu": {"type": "string", "description": "Yas grubu: yetiskin | 15-18 | 12-15"},
        },
        "required": ["temel_ceza_ay"],
    }

    def run(
        self,
        temel_ceza_ay: float = 0,
        agirlastirici_orani: float = 0,
        hafifletici_orani: float = 0,
        tesebbus: bool = False,
        istirak_turu: str = "",
        zincirleme_suc_sayisi: int = 0,
        iyi_hal: bool = False,
        yas_grubu: str = "yetiskin",
        **kw,
    ) -> str:
        if temel_ceza_ay <= 0:
            return "Temel ceza belirtilmedi."

        ceza = temel_ceza_ay
        adimlar = [f"Temel ceza: {self._format(ceza)}"]

        # 1. Agirlastirici nedenler
        if agirlastirici_orani > 0:
            artis = ceza * agirlastirici_orani
            ceza += artis
            adimlar.append(f"Agirlastirici ({agirlastirici_orani:.0%}): +{self._format(artis)} → {self._format(ceza)}")

        # 2. Hafifletici nedenler
        if hafifletici_orani > 0:
            indirim = ceza * hafifletici_orani
            ceza -= indirim
            adimlar.append(f"Hafifletici ({hafifletici_orani:.0%}): -{self._format(indirim)} → {self._format(ceza)}")

        # 3. Tesebbus (TCK m.35: 1/4 — 3/4 arasi indirim)
        if tesebbus:
            indirim = ceza * 0.5  # Ortalama 1/2
            ceza -= indirim
            adimlar.append(f"Tesebbus indirimi (1/2): -{self._format(indirim)} → {self._format(ceza)}")

        # 4. Istirak
        if istirak_turu == "yardim_eden":
            indirim = ceza * 0.5
            ceza -= indirim
            adimlar.append(f"Yardim eden indirimi (1/2): -{self._format(indirim)} → {self._format(ceza)}")

        # 5. Zincirleme suc (TCK m.43: 1/4 — 3/4 arasi arttirma)
        if zincirleme_suc_sayisi > 0:
            oran = min(0.75, 0.25 + (zincirleme_suc_sayisi - 1) * 0.10)
            artis = ceza * oran
            ceza += artis
            adimlar.append(f"Zincirleme suc ({zincirleme_suc_sayisi}x, {oran:.0%}): +{self._format(artis)} → {self._format(ceza)}")

        # 6. Yas indirimi
        if yas_grubu == "15-18":
            indirim = ceza * (1/3)
            ceza -= indirim
            adimlar.append(f"Yas indirimi (15-18, 1/3): -{self._format(indirim)} → {self._format(ceza)}")
        elif yas_grubu == "12-15":
            indirim = ceza * 0.5
            ceza -= indirim
            adimlar.append(f"Yas indirimi (12-15, 1/2): -{self._format(indirim)} → {self._format(ceza)}")

        # 7. Iyi hal indirimi (TCK m.62: 1/6)
        if iyi_hal:
            indirim = ceza * (1/6)
            ceza -= indirim
            adimlar.append(f"Iyi hal indirimi (1/6): -{self._format(indirim)} → {self._format(ceza)}")

        # Sonuc
        ceza = max(1, ceza)  # Minimum 1 ay
        yil = int(ceza // 12)
        ay = int(ceza % 12)
        gun = int((ceza % 1) * 30)

        sonuc = f"\n{'='*40}\nSONUC CEZA: "
        parts = []
        if yil > 0:
            parts.append(f"{yil} yil")
        if ay > 0:
            parts.append(f"{ay} ay")
        if gun > 0:
            parts.append(f"{gun} gun")
        sonuc += " ".join(parts) if parts else "1 ay"

        # Erteleme/HAGB notu
        if ceza <= 24:
            sonuc += "\n\nNOT: 2 yil ve altinda — HAGB veya erteleme mumkun olabilir."
        elif ceza <= 60:
            sonuc += "\n\nNOT: 5 yil ve altinda — erteleme mumkun olabilir."

        return "CEZA HESAPLAMA:\n" + "\n".join(adimlar) + "\n" + sonuc + "\n\nUYARI: Bu hesaplama tahminidir, kesin ceza mahkeme takdirindedir."

    @staticmethod
    def _format(ay: float) -> str:
        if ay >= 12:
            return f"{ay/12:.1f} yil ({ay:.0f} ay)"
        return f"{ay:.1f} ay"
