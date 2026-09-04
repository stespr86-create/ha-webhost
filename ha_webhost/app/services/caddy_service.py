import logging
import subprocess
from typing import Iterable, Mapping, Optional

from core.config import (
    BACKEND_INTERNAL_PORT,
    CADDY_CONFIG_PATH,
    CADDY_PUBLIC_SITES_PORT,
    SITES_DIR,
)
from services import php_fpm_service

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

\t# "route" erzwingt, dass die handle(_path)-Bloecke unten GENAU in
\t# Schreibreihenfolge geprueft werden. Ohne "route" sortiert Caddys
\t# Caddyfile-Adapter handle/handle_path/reverse_proxy etc. selbststaendig
\t# nach einer festen Standard-Reihenfolge um - das hat hier dazu gefuehrt,
\t# dass handle_path (Site-Dateien) trotz anderer Schreibreihenfolge VOR
\t# dem API-Proxy-Block ausgewertet wurde und /sites/*/api/* faelschlich
\t# als Datei-Pfad landete (index.html statt Backend-Antwort).
\troute {

"""

INGRESS_FOOTER = """\
\t\thandle {{
\t\t\treverse_proxy 127.0.0.1:{backend_port}
\t\t}}
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

\troute {{

"""

PUBLIC_FOOTER = """\
\t\thandle {
\t\t\trespond 404
\t\t}
\t}
}
"""

SITE_BLOCK = """\
\t\thandle_path /sites/{name}/* {{
\t\t\troot * {root}
\t\t\ttry_files {{path}} /index.html
\t\t\tfile_server
\t\t}}

"""

# PHP-faehige Sites (aktuell: WordPress) - Caddys eingebautes php_fastcgi
# spricht direkt per FastCGI mit dem site-eigenen PHP-FPM-Pool (siehe
# services/php_fpm_service.py, ein Unix-Socket pro Site). Kein nginx als
# Zwischenstation mehr noetig. php_fastcgi bringt try_files/index.php-
# Fallback fuer WordPress-Permalinks bereits eingebaut mit.
SITE_BLOCK_PHP = """\
\t\thandle_path /sites/{name}/* {{
\t\t\troot * {root}
\t\t\tphp_fastcgi unix/{socket} {{
\t\t\t\theader_up X-Forwarded-Proto {{forwarded_proto}}
\t\t\t}}
\t\t\tfile_server
\t\t}}

"""

# Python-App-Sites - kein Docker-Container, sondern ein eigener, ueberwachter
# Prozess pro Site auf einem lokalen Port (siehe services/python_app_service.py).
# Kein "root"/file_server noetig: die App entscheidet selbst, was sie
# ausliefert, Caddy reicht den kompletten Request einfach durch.
SITE_BLOCK_PYTHON = """\
\t\thandle_path /sites/{name}/* {{
\t\t\treverse_proxy 127.0.0.1:{port} {{
\t\t\t\theader_up X-Forwarded-Proto {{forwarded_proto}}
\t\t\t}}
\t\t}}

"""

# Galerie-Sites brauchen einen kleinen Backend-Endpunkt fuer
# Foto-Upload/-Liste (services/gallery_service.py), auch auf dem
# OEFFENTLICHEN Port - Gaeste haben keinen HA-Login. Bewusst nur dieser
# eine, eng gefasste Pfad ("/sites/*/api/*", NICHT "/api/*"): das Backend
# kennt unter dieser Route nur die zwei Lese-/Upload-Endpunkte aus
# api/gallery.py, kein Loeschen, keine sonstige Admin-Funktion - "handle"
# (statt "handle_path") behaelt den vollen Pfad bei, damit die Route im
# Backend den Site-Namen aus der URL lesen kann. Muss VOR dem allgemeinen
# SITE_BLOCK stehen, sonst wuerde file_server versuchen, den Pfad als
# Datei auszuliefern.
API_PROXY_BLOCK = """\
\t\thandle /sites/*/api/* {{
\t\t\treverse_proxy 127.0.0.1:{backend_port}
\t\t}}

"""

# Caddy terminiert selbst kein TLS (auto_https off) und setzt bei
# reverse_proxy/php_fastcgi AUTOMATISCH X-Forwarded-Proto: http fuer das
# jeweilige Backend, weil Caddys eigener Listener aus seiner Sicht nur HTTP
# spricht - das gilt selbst dann, wenn die Anfrage tatsaechlich per HTTPS
# über Tailscale Funnel hereinkam (Funnel selbst sendet dafuer KEIN eigenes
# X-Forwarded-Proto). Live mit einer generischen PHP-Test-Site bestaetigt:
# ohne diesen Fix sieht JEDE PHP-/Python-App "X-Forwarded-Proto: http",
# obwohl der Request nachweislich per HTTPS ankam - fuehrt bei jeder App,
# die diesen Standard-Header korrekt auswertet (z.B. fuer is_ssl()-artige
# Logik), zu falschen http://-Links bzw. Redirect-Schleifen (siehe
# WordPress-Vorfall). Fix zentral hier statt in jeder einzelnen Site/App:
# {{forwarded_proto}} wird einmal pro Request berechnet (Tailscale Funnel
# erkennbar am eigenen Tailscale-Funnel-Request-Header - der ist strukturell
# nur-HTTPS) und unten in jedem PHP-/Python-Site-Block als X-Forwarded-Proto
# an das jeweilige Backend weitergereicht. Kommt die Anfrage NICHT ueber
# Funnel (z.B. HA-Ingress oder direkter LAN-Zugriff auf Port 8090), bleibt
# der von Caddy automatisch gesetzte Wert unveraendert (kein Downgrade auf
# "immer https" - waere fuer echtes Klartext-LAN falsch).
PROTO_MAP_BLOCK = """\
\t\tmap {header.Tailscale-Funnel-Request} {forwarded_proto} {
\t\t\t?1 https
\t\t\tdefault {header.X-Forwarded-Proto}
\t\t}

"""

# "/sites/<name>" OHNE abschliessenden Slash matched keinen der obigen
# handle_path-Bloecke (das Muster "/sites/{name}/*" verlangt den Slash
# zwingend) - fuehrt ohne diesen Redirect zu 404 (bzw. beim Erstaufruf zu
# "200 leer" auf dem oeffentlichen Port). Praktisch relevant: WordPress'
# eigener home_url()-Link (z.B. Seitentitel/Logo) zeigt konventionsgemaess
# OHNE Trailing-Slash - ohne diesen Redirect fuehrte das dazu, dass genau
# dieser Link auf jeder WordPress-Site kaputt war. Betrifft alle Site-Typen
# gleichermassen, nicht nur WordPress.
REDIRECT_BLOCK = """\
\t\tredir /sites/{name} /sites/{name}/ 301

"""


def render_caddyfile(
    site_names: Iterable[str],
    php_site_names: Iterable[str] = (),
    python_site_ports: Optional[Mapping[str, int]] = None,
) -> str:
    names = sorted(site_names)
    php_names = set(php_site_names)
    python_site_ports = python_site_ports or {}

    def block_for(name: str) -> str:
        root = str(SITES_DIR / name)
        if name in php_names:
            return SITE_BLOCK_PHP.format(name=name, root=root, socket=php_fpm_service.socket_path(name))
        if name in python_site_ports:
            return SITE_BLOCK_PYTHON.format(name=name, port=python_site_ports[name])
        return SITE_BLOCK.format(name=name, root=root)

    site_blocks = "".join(block_for(name) for name in names)
    redirect_blocks = "".join(REDIRECT_BLOCK.format(name=name) for name in names)
    api_proxy_block = API_PROXY_BLOCK.format(backend_port=BACKEND_INTERNAL_PORT)

    ingress_block = (
        INGRESS_HEADER + api_proxy_block + PROTO_MAP_BLOCK + redirect_blocks + site_blocks
        + INGRESS_FOOTER.format(backend_port=BACKEND_INTERNAL_PORT)
    )
    public_block = (
        PUBLIC_HEADER.format(public_port=CADDY_PUBLIC_SITES_PORT)
        + api_proxy_block + PROTO_MAP_BLOCK + redirect_blocks + site_blocks + PUBLIC_FOOTER
    )

    return GLOBAL_OPTS + ingress_block + "\n" + public_block


def write_and_reload(
    site_names: Iterable[str],
    php_site_names: Iterable[str] = (),
    python_site_ports: Optional[Mapping[str, int]] = None,
) -> None:
    """Schreibt die Caddyfile und stößt einen Reload an.

    Ein fehlgeschlagener Reload (Caddy nicht erreichbar, Binary fehlt) darf
    das Deployment selbst nicht scheitern lassen - die Site-Dateien liegen
    bereits korrekt auf der Platte, nur der Proxy hinkt dann bis zum
    nächsten erfolgreichen Reload hinterher.
    """
    CADDY_CONFIG_PATH.write_text(render_caddyfile(site_names, php_site_names, python_site_ports))

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
