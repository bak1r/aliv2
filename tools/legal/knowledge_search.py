"""Yerel hukuk bilgi bankasi arama araci.
knowledge/ klasorundeki TCK, CMK, savunma teknikleri, UYAP rehberlerini arar.
Internet gerektirmez — aninda, guvenilir.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from tools.base import BaseTool

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"


class KnowledgeSearchTool(BaseTool):
    name = "bilgi_bankasi"
    description = "Yerel hukuk bilgi bankasini arar: TCK, CMK, savunma teknikleri, UYAP. Internet gerektirmez."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Arama terimi"},
            "domain": {"type": "string", "description": "Alan: tck | cmk | savunma | uyap | hepsi", "default": "hepsi"},
            "madde": {"type": "string", "description": "Madde numarasi (opsiyonel)"},
        },
        "required": ["query"],
    }

    def run(self, query: str = "", domain: str = "hepsi", madde: str = "", **kw) -> str:
        if not query:
            return "Arama terimi belirtilmedi."

        domain_map = {
            "savunma": "savunma_teknikleri",
            "savunma_teknikleri": "savunma_teknikleri",
            "tck": "tck", "cmk": "cmk", "uyap": "uyap",
        }

        if domain == "hepsi":
            domains = ["tck", "cmk", "savunma_teknikleri", "uyap"]
        else:
            domains = [domain_map.get(domain, domain)]

        results = []
        for d in domains:
            d_path = KNOWLEDGE_DIR / d
            if not d_path.exists():
                continue

            files = self._find_files(d, query, madde)
            for f in files:
                section = self._extract_sections(f, query, madde)
                if section:
                    results.append(f"### {d.upper()} — {f.stem}\n{section}")

        if not results:
            available = [d.name for d in KNOWLEDGE_DIR.iterdir() if d.is_dir()] if KNOWLEDGE_DIR.exists() else []
            return f"'{query}' icin sonuc bulunamadi. Alanlar: {', '.join(available)}"

        output = f"# YEREL BILGI BANKASI — {query}\n\n" + "\n\n---\n\n".join(results)
        return output[:8000]

    def _find_files(self, domain: str, query: str, madde: str) -> list[Path]:
        domain_dir = KNOWLEDGE_DIR / domain
        query_lower = query.lower()
        scored = []

        for md_file in sorted(domain_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8").lower()
            score = sum(content.count(w) for w in query_lower.split() if len(w) >= 3)

            if madde:
                if f"m.{madde}" in content or f"madde {madde}" in content:
                    score += 50

            if score > 0:
                scored.append((md_file, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [f for f, _ in scored[:3]]

    def _extract_sections(self, file_path: Path, query: str, madde: str, max_chars: int = 3000) -> str:
        content = file_path.read_text(encoding="utf-8")
        query_words = [w for w in query.lower().split() if len(w) >= 3]

        sections = re.split(r'\n(?=## )', content)
        scored = []

        for section in sections:
            sl = section.lower()
            score = sum(sl.count(w) * 2 for w in query_words)
            if madde and (f"m.{madde}" in section or f"madde {madde}" in sl):
                score += 100
            if score > 0:
                scored.append((section.strip(), score))

        scored.sort(key=lambda x: x[1], reverse=True)

        parts, total = [], 0
        for text, _ in scored:
            if total + len(text) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    parts.append(text[:remaining] + "\n... (devami kesildi)")
                break
            parts.append(text)
            total += len(text)

        return "\n\n".join(parts) if parts else content[:max_chars]
