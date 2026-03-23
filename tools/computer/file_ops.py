"""Dosya islemleri araci — cross-platform."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from tools.base import BaseTool


class FileOpsTool(BaseTool):
    name = "dosya_islem"
    description = "Dosya islemleri: olusturma, okuma, tasima, silme, arama, listeleme."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Islem: read | write | move | delete | search | list | info"
            },
            "path": {"type": "string", "description": "Dosya/klasor yolu"},
            "content": {"type": "string", "description": "Yazilacak icerik (write icin)"},
            "destination": {"type": "string", "description": "Hedef yol (move icin)"},
            "query": {"type": "string", "description": "Arama terimi (search icin)"},
        },
        "required": ["action", "path"],
    }

    def run(self, action: str = "", path: str = "", content: str = "", destination: str = "", query: str = "", **kw) -> str:
        if not action:
            return "Islem belirtilmedi. Kullanilabilir: read, write, move, delete, search, list, info"
        if not path:
            return "Dosya yolu belirtilmedi."

        p = Path(path).expanduser()

        try:
            if action == "read":
                return self._read(p)
            elif action == "write":
                return self._write(p, content)
            elif action == "move":
                return self._move(p, destination)
            elif action == "delete":
                return self._delete(p)
            elif action == "search":
                return self._search(p, query)
            elif action == "list":
                return self._list(p)
            elif action == "info":
                return self._info(p)
            else:
                return f"Bilinmeyen islem: {action}"
        except PermissionError:
            return f"Erisim izni yok: {p}"
        except Exception as e:
            return f"Dosya islemi hatasi: {e}"

    def _read(self, p: Path) -> str:
        if not p.exists():
            return f"Dosya bulunamadi: {p}"
        if p.is_dir():
            return self._list(p)
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 5000:
            return content[:5000] + f"\n\n... ({len(content)} karakter, ilk 5000'i gosteriliyor)"
        return content

    def _write(self, p: Path, content: str) -> str:
        if not content:
            return "Yazilacak icerik belirtilmedi."
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Dosya yazildi: {p} ({len(content)} karakter)"

    def _move(self, p: Path, destination: str) -> str:
        if not p.exists():
            return f"Kaynak bulunamadi: {p}"
        if not destination:
            return "Hedef yol belirtilmedi."
        dest = Path(destination).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))
        return f"Tasindi: {p} → {dest}"

    def _delete(self, p: Path) -> str:
        if not p.exists():
            return f"Dosya bulunamadi: {p}"
        try:
            from send2trash import send2trash
            send2trash(str(p))
            return f"Cop kutusuna taşindi: {p}"
        except ImportError:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return f"Silindi: {p}"

    def _search(self, p: Path, query: str) -> str:
        if not query:
            return "Arama terimi belirtilmedi."
        if not p.is_dir():
            p = p.parent

        results = []
        for f in p.rglob("*"):
            if query.lower() in f.name.lower():
                results.append(str(f))
            if len(results) >= 20:
                break

        if not results:
            return f"'{query}' ile eslesen dosya bulunamadi: {p}"
        return f"Bulunan dosyalar ({len(results)}):\n" + "\n".join(results)

    def _list(self, p: Path) -> str:
        if not p.exists():
            return f"Klasor bulunamadi: {p}"
        if not p.is_dir():
            return self._info(p)

        items = []
        for item in sorted(p.iterdir()):
            prefix = "[DIR]" if item.is_dir() else "[FILE]"
            size = ""
            if item.is_file():
                s = item.stat().st_size
                if s > 1_000_000:
                    size = f" ({s/1_000_000:.1f} MB)"
                elif s > 1000:
                    size = f" ({s/1000:.1f} KB)"
                else:
                    size = f" ({s} B)"
            items.append(f"  {prefix} {item.name}{size}")

        if not items:
            return f"Klasor bos: {p}"
        return f"{p}:\n" + "\n".join(items[:50])

    def _info(self, p: Path) -> str:
        if not p.exists():
            return f"Bulunamadi: {p}"
        stat = p.stat()
        return (
            f"Dosya: {p}\n"
            f"Tur: {'Klasor' if p.is_dir() else 'Dosya'}\n"
            f"Boyut: {stat.st_size:,} byte\n"
            f"Degistirme: {os.path.getmtime(p):.0f}"
        )
