"""Ali v2 — Error Recovery & Graceful Degradation
MCP kopması, API limit, bağlantı hataları için otomatik kurtarma.
"""

from __future__ import annotations

import time
import logging
from typing import Callable, Any
from functools import wraps

log = logging.getLogger("ali.recovery")


class CircuitBreaker:
    """
    Circuit breaker pattern — bir servis surekli hata verirse gecici olarak devre disi birak.

    States:
    - CLOSED: Normal calisma, istekler geciyor
    - OPEN: Servis devre disi, istekler hemen reddediliyor
    - HALF_OPEN: Test istegi gonderiliyor, basariliysa CLOSED'a don
    """

    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = 0
        self._state = "CLOSED"

    @property
    def state(self) -> str:
        if self._state == "OPEN":
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "HALF_OPEN"
        return self._state

    def record_success(self):
        self._failure_count = 0
        self._state = "CLOSED"

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            log.warning(f"[CircuitBreaker] {self.name} OPEN — {self._failure_count} ardisik hata")

    def can_execute(self) -> bool:
        return self.state != "OPEN"

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "failures": self._failure_count,
            "threshold": self.failure_threshold,
        }


# Global circuit breakers
_breakers: dict[str, CircuitBreaker] = {
    "mevzuat_mcp": CircuitBreaker("Mevzuat MCP", failure_threshold=3, recovery_timeout=120),
    "yargi_mcp": CircuitBreaker("Yargi MCP", failure_threshold=3, recovery_timeout=120),
    "anthropic_api": CircuitBreaker("Anthropic API", failure_threshold=5, recovery_timeout=30),
    "gemini_api": CircuitBreaker("Gemini API", failure_threshold=3, recovery_timeout=60),
}


def get_breaker(name: str) -> CircuitBreaker:
    """Circuit breaker al veya olustur."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]


def get_all_status() -> list[dict]:
    """Tum circuit breaker durumlarini dondur."""
    return [b.get_status() for b in _breakers.values()]


def with_circuit_breaker(breaker_name: str, fallback_fn: Callable = None):
    """Decorator: fonksiyonu circuit breaker ile sar."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            breaker = get_breaker(breaker_name)

            if not breaker.can_execute():
                log.info(f"[CircuitBreaker] {breaker_name} OPEN — fallback kullaniliyor")
                if fallback_fn:
                    return fallback_fn(*args, **kwargs)
                return f"{breaker_name} servisi gecici olarak devre disi. Lutfen birka dakika sonra tekrar deneyin."

            try:
                result = fn(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                log.warning(f"[CircuitBreaker] {breaker_name} hata: {e}")
                if fallback_fn:
                    return fallback_fn(*args, **kwargs)
                raise

        return wrapper
    return decorator


class GracefulDegradation:
    """
    Servisler calismazsa otomatik olarak daha basit alternatife gec.

    Ornek:
    - MCP calismiyor → yerel bilgi bankasina gec
    - Anthropic API limit → kisa cevap ver
    - Gemini ses koptu → sadece text modunda calis
    """

    @staticmethod
    def get_fallback_chain(service: str) -> list[str]:
        """Bir servis icin fallback zincirini dondur."""
        chains = {
            "mevzuat_mcp": ["yerel_bilgi_bankasi", "web_arama"],
            "yargi_mcp": ["yerel_bilgi_bankasi", "web_arama"],
            "anthropic_api": ["cache", "basit_yanit"],
            "gemini_ses": ["text_modu"],
            "whatsapp": ["telegram", "sms_bildirimi"],
        }
        return chains.get(service, [])

    @staticmethod
    def is_degraded(service: str) -> bool:
        """Servis degrade modda mi?"""
        breaker = _breakers.get(service)
        if breaker:
            return breaker.state != "CLOSED"
        return False

    @staticmethod
    def get_health_report() -> dict:
        """Sistem sagligi raporu."""
        report = {}
        for name, breaker in _breakers.items():
            state = breaker.state
            report[name] = {
                "status": "ok" if state == "CLOSED" else "degraded" if state == "HALF_OPEN" else "down",
                "failures": breaker._failure_count,
            }
        return report
