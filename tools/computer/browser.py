"""Tarayici kontrol araci — Chrome CDP uzerinden."""

from __future__ import annotations

import json
from tools.base import BaseTool


class BrowserTool(BaseTool):
    name = "tarayici"
    description = "Chrome tarayicisi kontrolu: site ac, arama yap, sayfa icerigi oku, tikla, form doldur."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: navigate | search | get_text | click | type | scroll | new_tab | list_tabs"
            },
            "url": {"type": "string", "description": "Gidilecek URL"},
            "query": {"type": "string", "description": "Arama sorgusu"},
            "text": {"type": "string", "description": "Yazilacak metin veya tiklanacak element"},
            "selector": {"type": "string", "description": "CSS secici"},
        },
        "required": ["action"],
    }

    _browser = None
    _page = None

    def run(self, action: str = "", url: str = "", query: str = "", text: str = "", selector: str = "", **kw) -> str:
        if not action:
            return "Islem belirtilmedi."

        try:
            if action == "navigate":
                return self._navigate(url)
            elif action == "search":
                return self._search(query)
            elif action == "get_text":
                return self._get_text()
            elif action == "click":
                return self._click(selector or text)
            elif action == "type":
                return self._type(selector, text)
            elif action == "scroll":
                return self._scroll(text)  # text = "up" or "down"
            elif action == "new_tab":
                return self._new_tab(url)
            elif action == "list_tabs":
                return self._list_tabs()
            else:
                return f"Bilinmeyen islem: {action}"
        except Exception as e:
            return f"Tarayici hatasi: {e}"

    def _get_browser(self):
        """Chrome CDP baglantisi kur (lazy)."""
        if self._page:
            return self._page

        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            self._browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
            contexts = self._browser.contexts
            if contexts and contexts[0].pages:
                self._page = contexts[0].pages[0]
            else:
                self._page = self._browser.new_page()
            return self._page
        except Exception as e:
            raise RuntimeError(
                f"Chrome'a baglanamadi. Chrome'u su sekilde acin: "
                f"chrome --remote-debugging-port=9222\nHata: {e}"
            )

    def _navigate(self, url: str) -> str:
        if not url:
            return "URL belirtilmedi."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        page = self._get_browser()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return f"Sayfa yuklendi: {page.title()} ({url})"

    def _search(self, query: str) -> str:
        if not query:
            return "Arama sorgusu belirtilmedi."
        url = f"https://www.google.com/search?q={query}"
        return self._navigate(url)

    def _get_text(self) -> str:
        page = self._get_browser()
        # Readability-style content extraction
        text = page.evaluate("""
            () => {
                const article = document.querySelector('article') || document.querySelector('main') || document.body;
                return article.innerText;
            }
        """)
        if len(text) > 5000:
            text = text[:5000] + "\n\n... (icerik kisaltildi)"
        return text or "Sayfa icerigi alinamadi."

    def _click(self, target: str) -> str:
        if not target:
            return "Tiklanacak element belirtilmedi."
        page = self._get_browser()
        try:
            page.click(target, timeout=5000)
            return f"Tiklandi: {target}"
        except Exception:
            # Text icerigi ile bulmaya calis
            page.get_by_text(target).first.click(timeout=5000)
            return f"Tiklandi: {target}"

    def _type(self, selector: str, text: str) -> str:
        if not text:
            return "Yazilacak metin belirtilmedi."
        page = self._get_browser()
        if selector:
            page.fill(selector, text, timeout=5000)
        else:
            page.keyboard.type(text)
        return f"Yazildi: {text[:50]}"

    def _scroll(self, direction: str) -> str:
        page = self._get_browser()
        if direction == "up":
            page.evaluate("window.scrollBy(0, -500)")
        else:
            page.evaluate("window.scrollBy(0, 500)")
        return f"Sayfa kaydirildi: {direction or 'asagi'}"

    def _new_tab(self, url: str) -> str:
        if not url:
            url = "about:blank"
        if not url.startswith(("http://", "https://", "about:")):
            url = "https://" + url

        try:
            context = self._browser.contexts[0] if self._browser else None
            if context:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                self._page = page
                return f"Yeni sekme acildi: {url}"
        except Exception as e:
            return f"Yeni sekme acilamadi: {e}"
        return "Tarayici baglantisi yok."

    def _list_tabs(self) -> str:
        if not self._browser:
            return "Tarayici baglantisi yok."
        try:
            pages = self._browser.contexts[0].pages
            tabs = [f"  [{i}] {p.title()} — {p.url}" for i, p in enumerate(pages)]
            return f"Acik sekmeler ({len(tabs)}):\n" + "\n".join(tabs)
        except Exception:
            return "Sekme listesi alinamadi."
