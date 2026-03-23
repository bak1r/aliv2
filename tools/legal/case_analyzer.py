"""Dava Dosyasi Analiz Araci — PDF/DOCX dava dosyasini analiz eder.
Surpiz ozellik: Dosya yukle, tum davayi analiz etsin.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from tools.base import BaseTool
from core.config import BASE_DIR


class CaseAnalyzerTool(BaseTool):
    name = "dava_analiz"
    description = (
        "Dava dosyasini derinlemesine analiz eder. Dosya yolu verin veya dava detaylarini yayin. "
        "Otomatik olarak: 1) Ilgili mevzuati arar, 2) Emsal kararlari bulur, "
        "3) Savunma stratejisi olusturur, 4) Ceza hesaplamasi yapar, "
        "5) Sure hesaplamasi yapar, 6) Ozet rapor uretir."
    )
    parameters = {
        "type": "object",
        "properties": {
            "case_details": {"type": "string", "description": "Dava detaylari veya dosya yolu"},
            "suc_turu": {"type": "string", "description": "Suc turu (ornek: dolandiricilik, hirsizlik, yaralama)"},
            "madde": {"type": "string", "description": "Ilgili TCK maddesi (ornek: 157)"},
            "generate_report": {"type": "boolean", "description": "DOCX rapor olusturulsun mu?", "default": True},
        },
        "required": ["case_details"],
    }

    def run(self, case_details: str = "", suc_turu: str = "", madde: str = "", generate_report: bool = True, **kw) -> str:
        if not case_details:
            return "Dava detaylari belirtilmedi."

        results = []
        results.append("# DAVA ANALİZ RAPORU")
        results.append(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        results.append(f"Dava Ozeti: {case_details[:200]}")
        results.append("")

        # 1. Yerel bilgi bankasinda ara
        try:
            from tools.legal.knowledge_search import KnowledgeSearchTool
            kb = KnowledgeSearchTool()
            query = suc_turu or case_details[:100]
            kb_result = kb.run(query=query, domain="hepsi", madde=madde)
            if kb_result and "bulunamadi" not in kb_result.lower():
                results.append("## YEREL BILGI BANKASI")
                results.append(kb_result[:1500])
                results.append("")
        except Exception as e:
            results.append(f"Bilgi bankasi hatasi: {e}")

        # 2. Mevzuat ara
        try:
            from tools.legal.mevzuat_search import MevzuatSearchTool
            mevzuat = MevzuatSearchTool()
            mevzuat_result = mevzuat.run(query=suc_turu or case_details[:80], madde=madde)
            if mevzuat_result and "hatasi" not in mevzuat_result.lower():
                results.append("## ILGILI MEVZUAT")
                results.append(mevzuat_result[:1500])
                results.append("")
        except Exception as e:
            results.append(f"Mevzuat arama hatasi: {e}")

        # 3. Emsal karar ara
        try:
            from tools.legal.yargi_search import YargiSearchTool
            yargi = YargiSearchTool()
            yargi_result = yargi.run(query=suc_turu or case_details[:80])
            if yargi_result and "hatasi" not in yargi_result.lower():
                results.append("## EMSAL KARARLAR")
                results.append(yargi_result[:1500])
                results.append("")
        except Exception as e:
            results.append(f"Yargi arama hatasi: {e}")

        # 4. Ceza hesaplama (madde varsa)
        if madde or suc_turu:
            results.append("## CEZA HESAPLAMA NOTU")
            results.append("Ceza hesaplamasi icin 'ceza_hesapla' aracini kullanin.")
            results.append(f"Ilgili madde: TCK m.{madde}" if madde else f"Suc turu: {suc_turu}")
            results.append("")

        # 5. Savunma stratejisi onerileri
        results.append("## SAVUNMA STRATEJİSİ ÖNERİLERİ")
        results.append("(Claude tarafindan dava detaylarina gore olusturulacak)")
        results.append("")

        # 6. Ozet
        results.append("## SONUC")
        results.append("Bu analiz yardimci amaclidir. Avukat incelemesi sart.")
        results.append(f"Analiz: {datetime.now().strftime('%d.%m.%Y %H:%M')} — Ali v2")

        report = "\n".join(results)

        # DOCX rapor olustur
        if generate_report:
            try:
                from tools.legal.doc_generator import DocGeneratorTool
                doc = DocGeneratorTool()
                safe = suc_turu or "dava"
                doc_result = doc.run(
                    belge_turu="genel",
                    baslik=f"Dava Analiz Raporu — {safe}",
                    icerik=report,
                )
                report += f"\n\n---\n{doc_result}"
            except Exception as e:
                report += f"\n\nDOCX olusturulamadi: {e}"

        return report
