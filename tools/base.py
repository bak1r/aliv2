"""BaseTool — tum araclar bu sinifi extend eder."""

from __future__ import annotations
from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Her arac bu yapida olmali."""

    name: str = ""
    description: str = ""
    parameters: dict = {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def run(self, **kwargs) -> str:
        """Araci calistir, sonucu string olarak dondur."""
        ...

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"
