from __future__ import annotations

import sys


def configure_utf8_console() -> None:
    """Tránh UnicodeEncodeError khi Windows/VS Code terminal đang dùng code page cũ."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

