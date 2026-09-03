import io
import logging
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

WORDPRESS_DOWNLOAD_URL = "https://wordpress.org/latest.zip"
WP_VERSION_FILE = "wp-includes/version.php"


def download_wordpress() -> bytes:
    """Lädt die aktuelle WordPress-ZIP von wordpress.org herunter."""
    logger.info("Lade WordPress herunter...")
    with urllib.request.urlopen(WORDPRESS_DOWNLOAD_URL) as response:
        return response.read()


def extract_wordpress_to_dir(zip_bytes: bytes, target_dir: Path) -> None:
    """Entpackt WordPress-ZIP in target_dir. Die ZIP enthält ein 'wordpress/'-Verzeichnis,
    dessen Inhalt wir direkt in target_dir legen."""
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # WordPress-ZIP hat einen 'wordpress/'-Ordner – wir wollen den Inhalt direkt in target_dir
        for name in zf.namelist():
            if name.startswith("wordpress/"):
                arcname = name[len("wordpress/"):]  # Entferne 'wordpress/' Prefix
                if arcname:  # Ignoriere das leere Verzeichnis selbst
                    zf.extract(name, target_dir)
                    # Verschiebe die Datei auf die richtige Ebene
                    src = target_dir / name
                    dst = target_dir / arcname
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if src.is_file():
                        src.rename(dst)

        # Räume das wordpress/-Verzeichnis weg
        wordpress_dir = target_dir / "wordpress"
        if wordpress_dir.exists():
            shutil.rmtree(wordpress_dir)

    logger.info(f"WordPress extrahiert nach {target_dir}")


def create_mysql_user_and_db(db_name: str, db_user: str, db_password: str) -> None:
    """Erstellt eine neue MySQL-Datenbank und einen Benutzer über die lokale
    MariaDB-Verbindung (Socket)."""
    logger.info(f"Erstelle Datenbank '{db_name}' und Benutzer '{db_user}'...")

    # SQL-Befehle für DB + User-Erstellung
    sql_commands = f"""
CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}';
GRANT ALL PRIVILEGES ON `{db_name}`.* TO '{db_user}'@'localhost';
FLUSH PRIVILEGES;
"""

    try:
        # Über MySQL-Socket verbinden und Befehle ausführen
        result = subprocess.run(
            ["mysql", "-u", "root"],
            input=sql_commands.encode(),
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"MySQL-Fehler: {result.stderr.decode()}")
        logger.info(f"Datenbank '{db_name}' und Benutzer '{db_user}' erstellt.")
    except Exception as e:
        logger.error(f"Fehler beim Erstellen von DB/User: {e}")
        raise


def generate_wp_config(
    db_name: str,
    db_user: str,
    db_password: str,
    site_name: str,
    target_dir: Path
) -> None:
    """Generiert wp-config.php mit Datenbank-Konfiguration."""
    config_path = target_dir / "wp-config.php"

    # WordPress-Security-Keys (Demo-Werte, später könnten echte von api.wordpress.org kommen)
    auth_key = "put your unique phrase here (auth_key)"
    secure_auth_key = "put your unique phrase here (secure_auth_key)"
    logged_in_key = "put your unique phrase here (logged_in_key)"
    nonce_key = "put your unique phrase here (nonce_key)"

    wp_config_content = f"""<?php
// WordPress Konfiguration – automatisch generiert durch HA WebHost

// Datenbank-Konfiguration
define( 'DB_NAME', '{db_name}' );
define( 'DB_USER', '{db_user}' );
define( 'DB_PASSWORD', '{db_password}' );
define( 'DB_HOST', 'localhost' );
define( 'DB_CHARSET', 'utf8mb4' );
define( 'DB_COLLATE', 'utf8mb4_unicode_ci' );

// Authentifizierung
define( 'AUTH_KEY',         '{auth_key}' );
define( 'SECURE_AUTH_KEY',  '{secure_auth_key}' );
define( 'LOGGED_IN_KEY',    '{logged_in_key}' );
define( 'NONCE_KEY',        '{nonce_key}' );

// WordPress-Pfade
define( 'WP_HOME',    'http://localhost' );
define( 'WP_SITEURL', 'http://localhost' );

// Debugging
define( 'WP_DEBUG', false );

// Tabellen-Präfix
$table_prefix = 'wp_';

// Laden Sie WordPress
if ( ! defined( 'ABSPATH' ) ) {{
    define( 'ABSPATH', __DIR__ . '/' );
}}

require_once( ABSPATH . 'wp-settings.php' );
"""

    config_path.write_text(wp_config_content)
    logger.info(f"wp-config.php erstellt in {config_path}")


def init_wordpress_site(site_dir: Path, site_name: str, db_name: str, db_user: str, db_password: str) -> None:
    """Komplette WordPress-Initialisierung: Download, Entpacken, DB, Config."""
    logger.info(f"Initialisiere WordPress-Site '{site_name}'...")

    # 1. WordPress herunterladen
    wp_zip = download_wordpress()

    # 2. Entpacken
    extract_wordpress_to_dir(wp_zip, site_dir)

    # 3. Datenbank + Benutzer erstellen
    create_mysql_user_and_db(db_name, db_user, db_password)

    # 4. wp-config.php generieren
    generate_wp_config(db_name, db_user, db_password, site_name, site_dir)

    logger.info(f"WordPress-Site '{site_name}' erfolgreich initialisiert.")
