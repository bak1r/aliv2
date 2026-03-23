"""Yargi kararlari arama araci — Turk mahkeme kararlari."""

from __future__ import annotations
from tools.base import BaseTool
from core.mcp_client import call_mcp_tool
from core.config import SETTINGS

ENDPOINT = SETTINGS.get("mcp", {}).get("yargi_endpoint", "https://yargimcp.fastmcp.app/mcp")

_SOURCE_MAP = {
    "hepsi": "search_bedesten_unified",
    "emsal": "search_emsal_detailed_decisions",
    "anayasa": "search_anayasa_unified",
    "rekabet": "search_rekabet_kurumu_decisions",
    "kvkk": "search_kvkk_decisions",
    "bddk": "search_bddk_decisions",
    "sayistay": "search_sayistay_unified",
    "kik": "search_kik_v2_decisions",
    "uyusmazlik": "search_uyusmazlik_decisions",
    "yargitay": "search_bedesten_unified",
    "danistay": "search_bedesten_unified",
}


class YargiSearchTool(BaseTool):
    name = "yargi_ara"
    description = "Turk yargi kararlarini arar: emsal, Anayasa Mahkemesi, Yargitay, Danistay, Sayistay, KVKK, Rekabet Kurumu ve daha fazlasi."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Arama sorgusu"},
            "source": {"type": "string", "description": "Kaynak: emsal | anayasa | yargitay | danistay | sayistay | rekabet | kvkk | bddk | kik | uyusmazlik | hepsi", "default": "hepsi"},
            "date_start": {"type": "string", "description": "Baslangic tarihi YYYY-MM-DD"},
            "date_end": {"type": "string", "description": "Bitis tarihi YYYY-MM-DD"},
        },
        "required": ["query"],
    }

    def run(self, query: str = "", source: str = "hepsi", date_start: str = "", date_end: str = "", **kw) -> str:
        if not query:
            return "Arama sorgusu belirtilmedi."

        source = source.strip().lower()
        tool_name = _SOURCE_MAP.get(source, "search_bedesten_unified")
        args = self._build_args(tool_name, source, query, date_start, date_end)

        print(f"[Yargi] {tool_name}: {query[:60]}")
        result = call_mcp_tool(ENDPOINT, tool_name, args)

        # MCP basarisizsa fallback
        markers = ("hatasi", "yanitlamadi", "arac hatasi", "Sonuc bulunamadi")
        if any(m in result for m in markers):
            try:
                from tools.legal.knowledge_search import KnowledgeSearchTool
                tool = KnowledgeSearchTool()
                local = tool.run(query=query, domain="hepsi")
                if local and len(local) > 50 and "bulunamadi" not in local.lower():
                    result = f"[YEREL BILGI BANKASI]\n{local}"
            except Exception:
                pass

        # Truncate
        if len(result) > 5000:
            cut = result.rfind('\n', 0, 4900)
            if cut < 3000:
                cut = 4900
            result = result[:cut] + "\n\n... (sonuclar kisaltildi)"

        return result

    @staticmethod
    def _build_args(tool_name: str, source: str, query: str, date_start: str, date_end: str) -> dict:
        if tool_name == "search_bedesten_unified":
            return {"phrase": query}

        if tool_name == "search_anayasa_unified":
            args = {"keyword": query, "decision_type": "hepsi"}
        elif tool_name == "search_sayistay_unified":
            args = {"keyword": query, "board_type": "hepsi"}
        else:
            args = {"keyword": query}

        if date_start:
            args["date_start"] = date_start
        if date_end:
            args["date_end"] = date_end
        return args
