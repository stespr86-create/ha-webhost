"""Sehr einfache Key-Value-Einstellungen, persistiert als JSON in /data.

Kein eigenes DB-Modell noetig fuer eine Handvoll globaler Werte wie die
oeffentliche Basis-URL (z.B. fuer Tailscale Funnel).
"""

import json
from typing import Optional

from .config import DATA_DIR

SETTINGS_PATH = DATA_DIR / "settings.json"


def _read() -> dict:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(data))


def get_public_base_url() -> Optional[str]:
    return _read().get("public_base_url") or None


def set_public_base_url(value: Optional[str]) -> None:
    data = _read()
    value = (value or "").strip().rstrip("/")
    if value:
        data["public_base_url"] = value
    else:
        data.pop("public_base_url", None)
    _write(data)
