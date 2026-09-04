"""Live-Log-Viewer pro Site (siehe DOCS.md Roadmap Phase 4).

Zeigt echte Log-Dateien fuer Site-Typen mit eigenem Prozess an:
- Python-Apps: stdout/stderr des App-Prozesses (siehe
  python_app_service.log_path()).
- WordPress/PHP-Upload: PHP-Fehler-Log des zugehoerigen PHP-FPM-Pools (siehe
  php_fpm_service.error_log_path() - "catch_workers_output"+"error_log" je
  Pool, damit auch Fatal Errors/Warnings landen statt nur im gemeinsamen
  Caddy-Zugriffslog zu verschwinden).
Statische/Git-/Galerie-Sites haben keinen eigenen Prozess und damit kein
Anwendungs-Log ("available": False).
"""

from pathlib import Path
from typing import Optional

from models.site import SourceType
from services import php_fpm_service, python_app_service

# Nur die letzten ~512 KB der Datei lesen, unabhaengig von ihrer tatsaechlichen
# Groesse - reicht fuer "letzte N Zeilen" bei weitem und begrenzt den
# Speicherverbrauch bei sehr geschwaetzigen/lange laufenden Apps.
MAX_READ_BYTES = 512 * 1024


def _log_path(name: str, source_type: SourceType) -> Optional[Path]:
    if source_type == SourceType.python:
        return python_app_service.log_path(name)
    if source_type in (SourceType.wordpress, SourceType.php):
        return php_fpm_service.error_log_path(name)
    return None


def read_log(name: str, source_type: SourceType, lines: int = 200) -> dict:
    path = _log_path(name, source_type)
    if path is None:
        return {"available": False, "lines": []}

    if not path.exists():
        return {"available": True, "lines": []}

    size = path.stat().st_size
    with open(path, "rb") as f:
        if size > MAX_READ_BYTES:
            f.seek(size - MAX_READ_BYTES)
        raw = f.read()

    text = raw.decode(errors="replace")
    all_lines = text.splitlines()
    return {"available": True, "lines": all_lines[-lines:]}
