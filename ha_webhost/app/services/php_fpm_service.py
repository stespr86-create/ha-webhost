import logging
import subprocess
from pathlib import Path
from typing import Iterable

from core.config import PHP_FPM_PID_FILE, PHP_FPM_POOL_DIR, PHP_FPM_SOCKET_DIR

logger = logging.getLogger("webhost.php_fpm")

# pm=ondemand statt dynamic/static: startet Worker-Prozesse erst bei der
# ersten Anfrage und beendet sie nach process_idle_timeout wieder - auf der
# Zielhardware (schwache Home-Assistant-Systeme, viele Sites mit wenig
# gleichzeitigem Traffic) verbraucht eine ungenutzte Site damit dauerhaft
# 0 MB RAM statt staendig laufender Leerlauf-Worker (wie bei pm=dynamic).
POOL_TEMPLATE = """\
[{name}]
user = nobody
group = nobody
listen = {socket}
listen.mode = 0666
pm = ondemand
pm.max_children = 3
pm.process_idle_timeout = 15s
pm.max_requests = 200
php_admin_value[memory_limit] = 128M
php_admin_value[upload_max_filesize] = 64M
php_admin_value[post_max_size] = 64M
"""


def socket_path(name: str) -> Path:
    return PHP_FPM_SOCKET_DIR / f"{name}.sock"


def render_pool(name: str) -> str:
    return POOL_TEMPLATE.format(name=name, socket=socket_path(name))


def sync_pools(php_site_names: Iterable[str]) -> None:
    """Schreibt fuer jede PHP-faehige Site (aktuell: WordPress) einen eigenen
    PHP-FPM-Pool und stoesst einen Reload an. Pools von geloeschten/nicht
    mehr PHP-faehigen Sites werden entfernt."""
    names = sorted(set(php_site_names))

    PHP_FPM_POOL_DIR.mkdir(parents=True, exist_ok=True)
    PHP_FPM_SOCKET_DIR.mkdir(parents=True, exist_ok=True)

    wanted_files = {f"{name}.conf" for name in names}
    for existing in PHP_FPM_POOL_DIR.glob("*.conf"):
        if existing.name not in wanted_files:
            existing.unlink()

    for name in names:
        (PHP_FPM_POOL_DIR / f"{name}.conf").write_text(render_pool(name))

    _reload()


def _reload() -> None:
    """Sendet SIGUSR2 an den PHP-FPM-Master-Prozess: liest alle Pool-Configs
    neu ein (neue/entfernte Pools), ohne laufende Requests abzubrechen.

    Wie beim Caddy-Reload (siehe caddy_service.write_and_reload) darf ein
    fehlgeschlagener Reload das Deployment nicht scheitern lassen - z.B.
    direkt nach einem frischen Containerstart, bevor php-fpm seine PID-Datei
    geschrieben hat. Die Pool-Dateien liegen dann trotzdem schon korrekt auf
    der Platte und greifen beim naechsten (auch manuell ausloesbaren) Reload.
    """
    if not PHP_FPM_PID_FILE.exists():
        logger.warning("PHP-FPM PID-Datei (%s) nicht gefunden, Reload uebersprungen.", PHP_FPM_PID_FILE)
        return

    try:
        pid = int(PHP_FPM_PID_FILE.read_text().strip())
        subprocess.run(["kill", "-USR2", str(pid)], check=False, timeout=10)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        logger.warning("PHP-FPM-Reload fehlgeschlagen: %s", exc)
