"""Web arama araci — DuckDuckGo."""

from __future__ import annotations
from tools.base import BaseTool


class WebSearchTool(BaseTool):
    name = "web_ara"
    description = "Internette arama yapar (DuckDuckGo). Guncel bilgi icin kullanin."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Arama sorgusu"},
            "max_results": {"type": "number", "description": "Maksimum sonuc sayisi", "default": 5},
        },
        "required": ["query"],
    }

    def run(self, query: str = "", max_results: int = 5, **kw) -> str:
        if not query:
            return "Arama sorgusu belirtilmedi."

        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return f"'{query}' icin sonuc bulunamadi."

            output = []
            for i, r in enumerate(results, 1):
                output.append(
                    f"{i}. {r.get('title', 'Basliksiz')}\n"
                    f"   {r.get('href', '')}\n"
                    f"   {r.get('body', '')[:200]}"
                )
            return "\n\n".join(output)

        except ImportError:
            return "duckduckgo-search paketi bulunamadi."
        except Exception as e:
            return f"Arama hatasi: {e}"
