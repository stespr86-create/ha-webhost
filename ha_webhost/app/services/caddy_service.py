import logging
import subprocess
from typing import Iterable

from core.config import BACKEND_INTERNAL_PORT, CADDY_CONFIG_PATH, SITES_DIR

logger = logging.getLogger("webhost.caddy")

HEADER = """\
{
\tadmin 127.0.0.1:2019
\tauto_https off
}

:8000 {
\tlog {
\t\toutput stdout
\t}

\t# Home Assistant Ingress haengt teils einen doppelten Trailing-Slash an
\t# die Basis-URL an (z.B. ".../<token>//"). Auf einfaches "/" reduzieren,
\t# bevor geroutet wird.
\turi replace // / 1

"""

SITE_BLOCK = """\
\thandle_path /sites/{name}/* {{
\t\troot * {root}
\t\ttry_files {{path}} /index.html
\t\tfile_server
\t}}

"""

FOOTER = """\
\thandle {{
\t\treverse_proxy 127.0.0.1:{backend_port}
\t}}
}}
"""


def render_caddyfile(site_names: Iterable[str]) -> str:
    blocks = "".join(
        SITE_BLOCK.format(name=name, root=str(SITES_DIR / name)) for name in sorted(site_names)
    )
    return HEADER + blocks + FOOTER.format(backend_port=BACKEND_INTERNAL_PORT)


def write_and_reload(site_names: Iterable[str]) -> None:
    """Schreibt die Caddyfile und stößt einen Reload an.

    Ein fehlgeschlagener Reload (Caddy nicht erreichbar, Binary fehlt) darf
    das Deployment selbst nicht scheitern lassen - die Site-Dateien liegen
    bereits korrekt auf der Platte, nur der Proxy hinkt dann bis zum
    nächsten erfolgreichen Reload hinterher.
    """
    CADDY_CONFIG_PATH.write_text(render_caddyfile(site_names))

    try:
        result = subprocess.run(
            ["caddy", "reload", "--config", str(CADDY_CONFIG_PATH), "--adapter", "caddyfile"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Caddy-Reload konnte nicht ausgeführt werden: %s", exc)
        return

    if result.returncode != 0:
        logger.warning("Caddy-Reload fehlgeschlagen: %s", result.stderr.strip())
