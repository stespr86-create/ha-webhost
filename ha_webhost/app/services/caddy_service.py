import logging
import subprocess
from typing import Iterable

from core.config import (
    BACKEND_INTERNAL_PORT,
    CADDY_CONFIG_PATH,
    CADDY_PUBLIC_SITES_PORT,
    SITES_DIR,
)

logger = logging.getLogger("webhost.caddy")

GLOBAL_OPTS = """\
{
\tadmin 127.0.0.1:2019
\tauto_https off
}

"""

INGRESS_HEADER = """\
:8000 {
\tlog {
\t\toutput stdout
\t}

\t# Home Assistant Ingress haengt teils einen doppelten Trailing-Slash an
\t# die Basis-URL an (z.B. ".../<token>//"). Auf einfaches "/" reduzieren,
\t# bevor geroutet wird.
\turi replace // / 1

"""

INGRESS_FOOTER = """\
\thandle {{
\t\treverse_proxy 127.0.0.1:{backend_port}
\t}}
}}
"""

# Oeffentlicher Listener: NUR Site-Inhalte, kein Fallback auf das Backend.
# Wichtig: Ein Caddy-Server-Block ohne jede Route antwortet NICHT
# automatisch mit 404, sondern mit "200 leer"! Deshalb hier ein
# EXPLIZITER catch-all 404-Handler statt uns auf "keine Route matcht"
# zu verlassen - Admin-UI und /api/* duerfen auf diesem Port unter
# keinen Umstaenden erreichbar sein, auch nicht durch einen Konfigfehler.
PUBLIC_HEADER = """\
:{public_port} {{
\tlog {{
\t\toutput stdout
\t}}

"""

PUBLIC_FOOTER = """\
\thandle {
\t\trespond 404
\t}
}
"""

SITE_BLOCK = """\
\thandle_path /sites/{name}/* {{
\t\troot * {root}
\t\ttry_files {{path}} /index.html
\t\tfile_server
\t}}

"""


def render_caddyfile(site_names: Iterable[str]) -> str:
    names = sorted(site_names)
    site_blocks = "".join(SITE_BLOCK.format(name=name, root=str(SITES_DIR / name)) for name in names)

    ingress_block = INGRESS_HEADER + site_blocks + INGRESS_FOOTER.format(backend_port=BACKEND_INTERNAL_PORT)
    public_block = (
        PUBLIC_HEADER.format(public_port=CADDY_PUBLIC_SITES_PORT) + site_blocks + PUBLIC_FOOTER
    )

    return GLOBAL_OPTS + ingress_block + "\n" + public_block


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
