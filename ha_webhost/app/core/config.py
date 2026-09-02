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

# 3-32 Zeichen, nur Kleinbuchstaben/Ziffern/Bindestrich, kein Start/Ende mit '-'
SITE_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"
RESERVED_NAMES = {"api", "static", "admin", "assets", "healthz", "backup"}

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB

SITES_DIR.mkdir(parents=True, exist_ok=True)
