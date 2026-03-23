"""Platform soyutlama katmani.
OS'a gore dogru implementasyonu otomatik yukler.
"""

import sys

if sys.platform == "win32":
    from ali_platform.windows import WindowsPlatform as _PlatformClass
elif sys.platform == "darwin":
    from ali_platform.macos import MacOSPlatform as _PlatformClass
else:
    raise RuntimeError(f"Desteklenmeyen isletim sistemi: {sys.platform}")

# Tek global instance — tum uygulama bunu kullanir
platform = _PlatformClass()
