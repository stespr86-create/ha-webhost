import os
from pathlib import Path

# Im Add-on-Container immer /data (persistenter Storage). Für lokale
# Entwicklung außerhalb von HA per DATA_DIR-Umgebungsvariable überschreibbar.
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
SITES_DIR = DATA_DIR / "sites"
DB_PATH = DATA_DIR / "webhost.db"
CADDY_CONFIG_PATH = DATA_DIR / "Caddyfile"

BACKEND_INTERNAL_PORT = 8001
CADDY_INGRESS_PORT = 8000

# Zweiter, strikt getrennter Caddy-Listener: liefert AUSSCHLIESSLICH
# /sites/<name>/* aus, niemals Admin-UI oder /api/*. Gedacht fuer
# oeffentliche Erreichbarkeit (z.B. via Tailscale Funnel) ohne dabei
# das Admin-Panel mit zu exponieren.
CADDY_PUBLIC_SITES_PORT = 8090

# 3-32 Zeichen, nur Kleinbuchstaben/Ziffern/Bindestrich, kein Start/Ende mit '-'
SITE_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"
RESERVED_NAMES = {"api", "static", "admin", "assets", "healthz", "backup"}

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB

# Fotogalerie-Sites: oeffentlich erreichbarer Upload ohne Login (siehe
# api/gallery.py) - bewusst niedrige Limits, damit weder der Speicher der
# Zielhardware (i3-Notebook, 4GB RAM) noch /data volllaufen kann.
GALLERY_TEMPLATE_DIR = Path(__file__).parent.parent / "gallery_template"
MAX_GALLERY_FILE_BYTES = 8 * 1024 * 1024  # 8 MB pro hochgeladenem Foto
MAX_GALLERY_TOTAL_BYTES = 300 * 1024 * 1024  # 300 MB pro Galerie
MAX_GALLERY_PHOTOS = 300  # Fotos pro Galerie
GALLERY_MAX_DIMENSION = 1600  # px, laengste Kante nach Verkleinerung
GALLERY_JPEG_QUALITY = 82

SITES_DIR.mkdir(parents=True, exist_ok=True)
