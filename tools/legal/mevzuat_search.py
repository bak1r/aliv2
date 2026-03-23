"""Mevzuat arama araci — Turk mevzuati (kanun, KHK, tuzuk, yonetmelik, teblig, CBK)."""

from __future__ import annotations
from tools.base import BaseTool
from core.mcp_client import call_mcp_tool
from core.config import SETTINGS

ENDPOINT = SETTINGS.get("mcp", {}).get("mevzuat_endpoint", "https://mevzuat.surucu.dev/mcp")

_TYPE_MAP = {
    "hepsi": "search_kanun", "kanun": "search_kanun",
    "khk": "search_khk", "tuzuk": "search_tuzuk",
    "yonetmelik": "search_kurum_yonetmelik",
    "teblig": "search_teblig", "cbk": "search_cbk",
}

_WITHIN_MAP = {
    "kanun": "search_within_kanun", "khk": "search_within_khk",
    "tuzuk": "search_within_tuzuk", "yonetmelik": "search_within_kurum_yonetmelik",
    "teblig": "search_within_teblig", "cbk": "search_within_cbk",
    "hepsi": "search_within_mevzuat",
}


class MevzuatSearchTool(BaseTool):
    name = "mevzuat_ara"
    description = "Turk mevzuatinda arama yapar: kanun, KHK, tuzuk, yonetmelik, teblig, CBK. Mevzuat.gov.tr veritabanini kullanir."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Arama sorgusu (ornek: 'dolandiricilik', 'is hukuku')"},
            "type": {"type": "string", "description": "Mevzuat turu: kanun | khk | tuzuk | yonetmelik | teblig | cbk | hepsi", "default": "hepsi"},
            "mevzuat_no": {"type": "string", "description": "Mevzuat numarasi (ornek: '5237' TCK icin)"},
            "madde": {"type": "string", "description": "Madde numarasi (ornek: '158')"},
        },
        "required": ["query"],
    }

    def run(self, query: str = "", type: str = "hepsi", mevzuat_no: str = "", madde: str = "", **kw) -> str:
        if not query:
            return "Arama sorgusu belirtilmedi."

        mtype = type.strip().lower()

        # Madde ici arama
        if madde and mevzuat_no:
            return self._search_within(mtype, query, mevzuat_no, madde)

        if madde and not mevzuat_no:
            query = f"{query} madde {madde}".strip()

        tool_name = _TYPE_MAP.get(mtype, "search_kanun")
        args = self._build_args(tool_name, query, mevzuat_no)

        print(f"[Mevzuat] {tool_name}: {query[:60]}")
        result = call_mcp_tool(ENDPOINT, tool_name, args)

        # MCP basarisizsa yerel bilgi bankasina bak
        if self._is_failed(result):
            result = self._local_fallback(query) or result

        return self._truncate(result, 5000)

    def _search_within(self, mtype: str, query: str, mevzuat_no: str, madde: str) -> str:
        tool_name = _WITHIN_MAP.get(mtype, "search_within_mevzuat")
        args = {"keyword": query, "mevzuat_no": mevzuat_no, "madde": madde}

        result = call_mcp_tool(ENDPOINT, tool_name, args)

        if "validation error" in result.lower() or "unexpected" in result.lower():
            fallback_query = f"{query} madde {madde}".strip()
            fallback_tool = _TYPE_MAP.get(mtype, "search_kanun")
            fallback_args = self._build_args(fallback_tool, fallback_query, mevzuat_no)
            result = call_mcp_tool(ENDPOINT, fallback_tool, fallback_args)

        return self._truncate(result, 3000)

    @staticmethod
    def _build_args(tool_name: str, query: str, mevzuat_no: str) -> dict:
        if tool_name == "search_mevzuat":
            args = {"keyword": query}
        else:
            args = {"aranacak_ifade": query}
        if mevzuat_no:
            args["mevzuat_no"] = mevzuat_no
        return args

    @staticmethod
    def _is_failed(result: str) -> bool:
        markers = ("hatasi", "yanitlamadi", "arac hatasi", "Sonuc bulunamadi")
        return any(m in result for m in markers)

    @staticmethod
    def _local_fallback(query: str) -> str | None:
        try:
            from tools.legal.knowledge_search import KnowledgeSearchTool
            tool = KnowledgeSearchTool()
            domain = "cmk" if "cmk" in query.lower() else "tck"
            local = tool.run(query=query, domain=domain)
            if local and len(local) > 50 and "bulunamadi" not in local.lower():
                return f"[YEREL BILGI BANKASI]\n{local}"
        except Exception:
            pass
        return None

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        cut = text.rfind('\n', 0, limit - 100)
        if cut < limit // 2:
            cut = text.rfind('. ', 0, limit - 100)
        if cut < limit // 2:
            cut = limit - 100
        return text[:cut] + "\n\n... (sonuclar kisaltildi)"
