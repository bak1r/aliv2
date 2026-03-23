"""Platform interface — tum OS implementasyonlari bunu takip eder."""

from abc import ABC, abstractmethod


class PlatformBase(ABC):
    """Cross-platform islemler icin abstract base class."""

    @abstractmethod
    def open_file(self, path: str) -> bool:
        """Dosyayi varsayilan uygulamayla ac."""

    @abstractmethod
    def open_folder(self, path: str) -> bool:
        """Klasoru dosya yoneticisinde ac."""

    @abstractmethod
    def get_volume(self) -> int:
        """Sistem ses seviyesini al (0-100)."""

    @abstractmethod
    def set_volume(self, level: int) -> bool:
        """Sistem ses seviyesini ayarla (0-100)."""

    @abstractmethod
    def send_notification(self, title: str, message: str) -> bool:
        """Masaustu bildirimi gonder."""

    @abstractmethod
    def get_active_window(self) -> str:
        """Aktif pencere basligini al."""

    @abstractmethod
    def activate_window(self, title: str) -> bool:
        """Basliga gore pencereyi one getir."""

    @abstractmethod
    def get_default_browser(self) -> str:
        """Varsayilan tarayici adini al."""

    @abstractmethod
    def sleep_display(self) -> bool:
        """Ekrani uyut."""

    @abstractmethod
    def shutdown(self) -> bool:
        """Bilgisayari kapat."""

    @abstractmethod
    def get_downloads_dir(self) -> str:
        """Indirilenler klasor yolunu al."""

    @abstractmethod
    def get_desktop_dir(self) -> str:
        """Masaustu klasor yolunu al."""
