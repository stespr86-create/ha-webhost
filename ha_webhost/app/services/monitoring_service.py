"""Monitoring: Speicherplatz-, RAM- und CPU-Nutzung pro Site.

Liest ausschliesslich aus /proc (Linux-Pseudo-Dateisystem) - kein
Sub-Prozess-Aufruf noetig (kein "ps", kein shell_exec). Fuer Python-App-Sites
ist die PID direkt aus der eigenen PID-Datei bekannt (siehe
python_app_service.get_pid()). Fuer PHP-FPM-Sites (WordPress/PHP-Upload) gibt
es dagegen KEINE persistierte PID - php-fpm startet/beendet Worker-Prozesse
pro Pool dynamisch (pm=ondemand, siehe php_fpm_service.py). Die zugehoerigen
Worker-PIDs werden deshalb ueber den von php-fpm gesetzten Prozesstitel
gefunden ("php-fpm: pool <name>", sichtbar unter /proc/<pid>/cmdline) -
Standardverhalten von php-fpm unter Linux. Ist der Pool gerade idle
(pm=ondemand ohne aktuelle Anfrage), existiert schlicht kein Worker-Prozess -
RAM/CPU werden dann als 0 ausgewiesen (kein Fehler, sondern normaler
Leerlauf-Zustand).
"""

import os
import time
from pathlib import Path
from typing import Optional

from core.config import SITES_DIR
from models.site import Site, SourceType
from services import python_app_service

CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
# Kurzes Sampling-Fenster fuer CPU%: zwei /proc/<pid>/stat-Snapshots mit
# dieser Pause dazwischen, CPU% ergibt sich aus dem Tick-Delta darueber.
CPU_SAMPLE_INTERVAL = 0.2


def disk_usage_bytes(path: Path) -> int:
    """Rekursive Verzeichnisgroesse in Bytes - reines Python (os.walk),
    braucht kein Sub-Prozess ("du")."""
    total = 0
    if not path.exists():
        return 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for filename in filenames:
            try:
                total += (Path(dirpath) / filename).lstat().st_size
            except OSError:
                continue
    return total


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _rss_kb(pid: int) -> int:
    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _cpu_ticks(pid: int) -> Optional[int]:
    """utime+stime (Felder 14+15) aus /proc/<pid>/stat, in Clock-Ticks. Das
    comm-Feld (Feld 2) kann Leerzeichen/Klammern enthalten - der feste,
    leerzeichen-getrennte Teil beginnt deshalb erst hinter der LETZTEN
    schliessenden Klammer."""
    try:
        content = Path(f"/proc/{pid}/stat").read_text()
        after_comm = content.rsplit(")", 1)[1].split()
        utime = int(after_comm[11])
        stime = int(after_comm[12])
        return utime + stime
    except (OSError, ValueError, IndexError):
        return None


def process_metrics(pids: list[int]) -> dict:
    """RAM (Snapshot) + CPU% (kurzes Sampling-Fenster) ueber eine Menge von
    PIDs summiert (mehrere PHP-FPM-Worker eines Pools zaehlen als eine
    Site)."""
    pids = [p for p in pids if _pid_alive(p)]
    if not pids:
        return {"running": False, "ram_mb": 0.0, "cpu_percent": 0.0, "process_count": 0}

    ram_mb = round(sum(_rss_kb(p) for p in pids) / 1024, 1)

    before = {p: _cpu_ticks(p) for p in pids}
    time.sleep(CPU_SAMPLE_INTERVAL)
    after = {p: _cpu_ticks(p) for p in pids}

    tick_delta = 0
    for p in pids:
        b, a = before.get(p), after.get(p)
        if b is not None and a is not None:
            tick_delta += max(0, a - b)

    cpu_percent = round((tick_delta / CLOCK_TICKS) / CPU_SAMPLE_INTERVAL * 100, 1)

    return {"running": True, "ram_mb": ram_mb, "cpu_percent": cpu_percent, "process_count": len(pids)}


def find_php_fpm_worker_pids(pool_name: str) -> list[int]:
    """Findet aktive php-fpm-Worker-PIDs eines Pools ueber den von php-fpm
    gesetzten Prozesstitel. Kein Treffer bei aktuell idlem Pool
    (pm=ondemand) - das ist der Normalfall, kein Fehler."""
    target = f"php-fpm: pool {pool_name}"
    matches = []
    try:
        candidates = [int(p) for p in os.listdir("/proc") if p.isdigit()]
    except OSError:
        return []

    for pid in candidates:
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            continue
        text = raw.replace(b"\x00", b" ").decode(errors="replace").strip()
        if text == target or text.startswith(target + " "):
            matches.append(pid)
    return matches


def get_site_monitoring(site: Site) -> dict:
    site_dir = SITES_DIR / site.name
    result = {"disk_mb": round(disk_usage_bytes(site_dir) / 1024 / 1024, 1)}

    if site.source_type == SourceType.python:
        pid = python_app_service.get_pid(site.name)
        result.update(process_metrics([pid] if pid else []))
    elif site.source_type in (SourceType.wordpress, SourceType.php):
        result.update(process_metrics(find_php_fpm_worker_pids(site.name)))
    else:
        # Statische/Git-/Galerie-Sites haben keinen eigenen Prozess.
        result.update({"running": None, "ram_mb": 0.0, "cpu_percent": 0.0, "process_count": 0})

    return result
