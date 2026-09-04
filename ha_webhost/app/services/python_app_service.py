"""Python-App-Hosting: pro Site ein eigener, überwachter Prozess statt eines
Docker-Containers - kein docker_api nötig, kein Root-äquivalenter Zugriff auf
den Host über den Docker-Socket. Trade-off (bewusst in Kauf genommen, siehe
DOCS.md Roadmap Phase 3): alle Apps teilen sich dieselbe im Container
installierte Python-Version; weniger Isolation zwischen Apps als bei
getrennten Containern - für kleine, vertrauenswürdige Apps ein sinnvoller
Kompromiss, analog zur PHP-FPM-Pool-Lösung.

Abhängigkeiten werden NICHT über ein eigenes virtualenv pro Site installiert
(das venv-Stdlib-Modul ist auf Alpine nicht zuverlässig garantiert vorhanden),
sondern per "pip install --target=<site>/.deps" isoliert installiert und zur
Laufzeit über PYTHONPATH eingebunden - braucht nur das ohnehin vorhandene
pip3, kein zusätzliches venv-Modul, kein doppelter Stdlib-Klon pro App.
"""

import logging
import os
import signal
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from core.config import PYTHON_APP_BASE_PORT, PYTHON_APP_PID_DIR

logger = logging.getLogger("webhost.python_app")


def app_port(site_id: int) -> int:
    return PYTHON_APP_BASE_PORT + site_id


def deps_dir(site_dir: Path) -> Path:
    return site_dir / ".deps"


def _pid_file(name: str) -> Path:
    return PYTHON_APP_PID_DIR / f"{name}.pid"


def _log_file(site_dir: Path) -> Path:
    return site_dir / ".app.log"


def setup_dependencies(site_dir: Path) -> None:
    """Installiert requirements.txt (falls vorhanden) isoliert in .deps/."""
    requirements = site_dir / "requirements.txt"
    if not requirements.exists():
        return

    target = deps_dir(site_dir)
    target.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["pip3", "install", "--no-cache-dir", "--target", str(target), "-r", str(requirements)],
        capture_output=True,
        timeout=600,
    )
    if result.returncode != 0:
        # Nur die letzten ~2000 Zeichen - pip-Fehlermeldungen (z.B. bei
        # fehlenden Build-Abhaengigkeiten) koennen sehr lang werden.
        raise RuntimeError(f"pip install fehlgeschlagen: {result.stderr.decode(errors='replace').strip()[-2000:]}")


def get_pid(name: str) -> Optional[int]:
    """Gibt die PID des laufenden App-Prozesses zurück, oder None (nicht
    gestartet oder bereits beendet). Wird sowohl von is_running() als auch
    vom Monitoring (services/monitoring_service.py) genutzt, um RAM/CPU des
    Prozesses ueber /proc/<pid>/... auszulesen."""
    pid_file = _pid_file(name)
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return None

    # Falls der Prozess noch ein direktes Kind dieses Backend-Prozesses ist
    # (selbes Backend-Leben wie beim Start) und bereits beendet wurde, wird
    # der Zombie-Eintrag hier eingesammelt - sonst wuerde os.kill(pid, 0)
    # faelschlich weiter "laeuft noch" melden, da ein toter, nicht
    # eingesammelter Kindprozess als Zombie in der Prozesstabelle sichtbar
    # bleibt. Nach einem Neustart des Backends selbst ist der Prozess kein
    # Kind mehr (von init uebernommen) - dann schlaegt waitpid mit
    # ChildProcessError fehl, was wir ignorieren und stattdessen per
    # kill(pid, 0) pruefen (dort gibt es das Zombie-Problem nicht, weil
    # init reapt).
    try:
        reaped_pid, _status = os.waitpid(pid, os.WNOHANG)
        if reaped_pid == pid:
            return None
    except ChildProcessError:
        pass

    try:
        os.kill(pid, 0)
        return pid
    except OSError:
        return None


def is_running(name: str) -> bool:
    return get_pid(name) is not None


def stop(name: str) -> None:
    pid_file = _pid_file(name)
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Python-App '{name}' gestoppt (PID {pid}).")
    except (OSError, ValueError):
        pass
    finally:
        pid_file.unlink(missing_ok=True)


def start(name: str, site_dir: Path, port: int) -> None:
    """Startet den App-Prozess (main.py), falls er nicht schon läuft. Die
    App muss selbst per HTTP auf 0.0.0.0:$PORT lauschen (Umgebungsvariable
    PORT - Standard-Konvention, passt zu den meisten Flask-/
    FastAPI-Quickstarts)."""
    if is_running(name):
        return

    entry = site_dir / "main.py"
    if not entry.exists():
        raise RuntimeError("main.py nicht gefunden - wird als Einstiegspunkt benötigt.")

    PYTHON_APP_PID_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PORT"] = str(port)
    deps = deps_dir(site_dir)
    if deps.exists():
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(deps) + (os.pathsep + existing if existing else "")

    with open(_log_file(site_dir), "ab") as log:
        process = subprocess.Popen(
            ["python3", str(entry)],
            cwd=site_dir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    _pid_file(name).write_text(str(process.pid))
    logger.info(f"Python-App '{name}' gestartet (PID {process.pid}, Port {port}).")


def ensure_running(sites: Iterable[tuple[str, Path, int]]) -> None:
    """Stellt sicher, dass für jede aktive Python-Site ein Prozess läuft -
    startet fehlende/abgestürzte Prozesse neu. Wird bei jedem sync_proxy()
    aufgerufen (App-Start + jedes Site-Create/Delete), analog zum
    Reload-Mechanismus von Caddy/PHP-FPM."""
    for name, site_dir, port in sites:
        if not is_running(name):
            try:
                start(name, site_dir, port)
            except Exception as exc:
                logger.error(f"Python-App '{name}' konnte nicht gestartet werden: {exc}")


def stop_orphaned(active_names: set) -> None:
    """Beendet Prozesse von Sites, die nicht mehr aktiv sind (gelöscht oder
    Status != active)."""
    if not PYTHON_APP_PID_DIR.exists():
        return
    for pid_file in PYTHON_APP_PID_DIR.glob("*.pid"):
        name = pid_file.stem
        if name not in active_names:
            stop(name)
