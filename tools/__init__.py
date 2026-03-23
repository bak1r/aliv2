"""Arac registry — otomatik kesif sistemi.
tools/ altindaki tum BaseTool subclass'larini bulur ve kaydeder.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from tools.base import BaseTool

_registry: dict[str, BaseTool] = {}
_loaded = False


def _discover_tools():
    """tools/ altindaki tum modulleri tarar, BaseTool subclass'larini bulur."""
    global _loaded
    if _loaded:
        return

    tools_dir = Path(__file__).parent
    # Alt paketleri tara (legal/, computer/, general/)
    for pkg_info in pkgutil.walk_packages([str(tools_dir)], prefix="tools."):
        module_name = pkg_info.name
        # base.py ve __init__.py atla
        if module_name in ("tools.base", "tools"):
            continue
        try:
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type)
                        and issubclass(attr, BaseTool)
                        and attr is not BaseTool
                        and hasattr(attr, 'name')):
                    try:
                        instance = attr()
                        if instance.name:
                            _registry[instance.name] = instance
                    except Exception as e:
                        print(f"[Tools] {attr_name} olusturulamadi: {e}")
        except Exception as e:
            print(f"[Tools] {module_name} yuklenemedi: {e}")

    _loaded = True
    print(f"[Tools] {len(_registry)} arac yuklendi: {', '.join(_registry.keys())}")


def get_registry() -> dict[str, BaseTool]:
    """Tum kayitli araclari dondur."""
    _discover_tools()
    return _registry


def get_tool(name: str) -> BaseTool | None:
    """Isimle arac getir."""
    _discover_tools()
    return _registry.get(name)


def get_claude_tool_definitions() -> list[dict]:
    """Claude API icin arac tanimlarini dondur."""
    _discover_tools()
    definitions = []
    for tool in _registry.values():
        definitions.append({
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        })
    return definitions
