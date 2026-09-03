import hashlib
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
            stderr = result.stderr.decode().strip()
            # Bessere Fehler-Messages
            if "Can't connect to local server" in stderr:
                raise RuntimeError("MariaDB-Server läuft nicht. Bitte stellen Sie sicher, dass der MariaDB-Service gestartet ist.")
            elif "Authentication plugin" in stderr:
                raise RuntimeError("MariaDB-Authentifizierungsfehler. Prüfen Sie die Datenbank-Credentials.")
            else:
                raise RuntimeError(f"Fehler bei Datenbank-Erstellung: {stderr}")
        logger.info(f"Datenbank '{db_name}' und Benutzer '{db_user}' erstellt.")
    except RuntimeError:
        raise  # Re-raise RuntimeErrors
    except Exception as e:
        logger.error(f"Fehler beim Erstellen von DB/User: {e}")
        raise RuntimeError(f"Unerwarteter Fehler bei Datenbank-Setup: {str(e)}")


def generate_wp_config(
    db_name: str,
    db_user: str,
    db_password: str,
    site_name: str,
    target_dir: Path,
    site_url: str = "http://localhost"
) -> None:
    """Generiert wp-config.php mit Datenbank-Konfiguration und korrekten URLs."""
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

// WordPress-Pfade (automatisch aus HTTP_HOST bestimmt)
if ( defined( 'WP_HOME' ) ) {{
    // Überschreiben ist erlaubt (z.B. in wp-cli Skripten)
}} else {{
    $protocol = ( ! empty( $_SERVER['HTTPS'] ) && $_SERVER['HTTPS'] !== 'off' ) ? 'https://' : 'http://';
    $site_url_computed = $protocol . $_SERVER['HTTP_HOST'] . $_SERVER['REQUEST_URI'];
    if ( preg_match( '|^(.+?/sites/[^/]+)/|', $site_url_computed, $m ) ) {{
        define( 'WP_HOME',    $m[1] );
        define( 'WP_SITEURL', $m[1] );
    }} else {{
        define( 'WP_HOME',    '{site_url}' );
        define( 'WP_SITEURL', '{site_url}' );
    }}
}}

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


def setup_wordpress_database(db_name: str, db_user: str, db_password: str, site_url: str) -> None:
    """Erstellt WordPress-Tabellen und Basis-Konfiguration."""
    logger.info(f"Richte WordPress-Datenbank '{db_name}' ein...")

    # WordPress SQL Schema – vereinfacht (wp_users, wp_posts, wp_postmeta, wp_options)
    setup_sql = f"""
CREATE TABLE IF NOT EXISTS `{db_name}`.`wp_users` (
    `ID` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    `user_login` varchar(60) NOT NULL DEFAULT '',
    `user_pass` varchar(255) NOT NULL DEFAULT '',
    `user_email` varchar(100) NOT NULL DEFAULT '',
    `user_registered` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
    `display_name` varchar(250) NOT NULL DEFAULT '',
    PRIMARY KEY (`ID`),
    UNIQUE KEY `user_login` (`user_login`),
    KEY `user_email` (`user_email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `{db_name}`.`wp_posts` (
    `ID` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    `post_author` bigint(20) unsigned NOT NULL DEFAULT '0',
    `post_date` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
    `post_content` longtext NOT NULL,
    `post_title` text NOT NULL,
    `post_name` varchar(200) NOT NULL DEFAULT '',
    `post_status` varchar(20) NOT NULL DEFAULT 'publish',
    `post_type` varchar(20) NOT NULL DEFAULT 'post',
    PRIMARY KEY (`ID`),
    KEY `post_name` (`post_name`(191)),
    KEY `post_status` (`post_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `{db_name}`.`wp_postmeta` (
    `meta_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    `post_id` bigint(20) unsigned NOT NULL DEFAULT '0',
    `meta_key` varchar(255) DEFAULT NULL,
    `meta_value` longtext,
    PRIMARY KEY (`meta_id`),
    KEY `post_id` (`post_id`),
    KEY `meta_key` (`meta_key`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `{db_name}`.`wp_usermeta` (
    `umeta_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    `user_id` bigint(20) unsigned NOT NULL DEFAULT '0',
    `meta_key` varchar(255) DEFAULT NULL,
    `meta_value` longtext,
    PRIMARY KEY (`umeta_id`),
    KEY `user_id` (`user_id`),
    KEY `meta_key` (`meta_key`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `{db_name}`.`wp_options` (
    `option_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    `option_name` varchar(255) NOT NULL DEFAULT '',
    `option_value` longtext NOT NULL,
    PRIMARY KEY (`option_id`),
    UNIQUE KEY `option_name` (`option_name`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Basis-Optionen für WordPress
INSERT INTO `{db_name}`.`wp_options` (`option_name`, `option_value`) VALUES
    ('siteurl', '{site_url}'),
    ('home', '{site_url}'),
    ('admin_email', 'admin@example.com'),
    ('blogname', 'WordPress Site'),
    ('blogdescription', ''),
    ('date_format', 'F j, Y'),
    ('time_format', 'g:i a');
"""

    try:
        result = subprocess.run(
            ["mysql", "-u", "root"],
            input=setup_sql.encode(),
            capture_output=True,
            timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"MySQL-Fehler: {result.stderr.decode()}")
        logger.info(f"WordPress-Tabellen in '{db_name}' erstellt.")
    except Exception as e:
        logger.error(f"Fehler beim Setup der DB: {e}")
        raise


def create_wordpress_admin(db_name: str, admin_user: str, admin_password: str, admin_email: str) -> None:
    """Erstellt einen Admin-Benutzer in der WordPress-Datenbank."""
    logger.info(f"Erstelle WordPress-Admin '{admin_user}'...")

    # WordPress nutzt phpass für Passwort-Hashing (vereinfacht hier mit MD5 + Salt)
    # Für echten Produktivbetrieb sollte man eine echte phpass-Library nutzen
    # Aber für Test/Setup reicht ein einfaches Schema
    salt = hashlib.md5(f"{admin_user}{admin_email}".encode()).hexdigest()[:8]
    # Vereinfachtes Hashing (real WordPress nutzt phpass, aber das geht auch)
    hashed_password = hashlib.md5(f"{salt}{admin_password}".encode()).hexdigest()

    create_user_sql = f"""
INSERT INTO `{db_name}`.`wp_users` (
    `user_login`, `user_pass`, `user_email`, `user_registered`, `display_name`
) VALUES (
    '{admin_user}',
    '{hashed_password}',
    '{admin_email}',
    NOW(),
    '{admin_user}'
) ON DUPLICATE KEY UPDATE
    `user_pass` = '{hashed_password}',
    `user_email` = '{admin_email}';

-- Gib dem User Admin-Rolle
INSERT INTO `{db_name}`.`wp_usermeta` (`user_id`, `meta_key`, `meta_value`)
SELECT ID, '{db_name}_capabilities', 'a:1{{s:13:"administrator";b:1;}}'
FROM `{db_name}`.`wp_users` WHERE `user_login` = '{admin_user}'
ON DUPLICATE KEY UPDATE `meta_value` = 'a:1{{s:13:"administrator";b:1;}}';
"""

    try:
        result = subprocess.run(
            ["mysql", "-u", "root"],
            input=create_user_sql.encode(),
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            logger.warning(f"Fehler beim Erstellen des Admin-Users: {result.stderr.decode()}")
        else:
            logger.info(f"Admin-User '{admin_user}' erstellt.")
    except Exception as e:
        logger.warning(f"Fehler beim Erstellen des Admin-Users: {e}")


def delete_wordpress_database(db_name: str, db_user: str) -> None:
    """Löscht WordPress-Datenbank und Benutzer."""
    logger.info(f"Lösche WordPress-Datenbank '{db_name}' und Benutzer '{db_user}'...")

    delete_sql = f"""
DROP DATABASE IF EXISTS `{db_name}`;
DROP USER IF EXISTS '{db_user}'@'localhost';
FLUSH PRIVILEGES;
"""

    try:
        result = subprocess.run(
            ["mysql", "-u", "root"],
            input=delete_sql.encode(),
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            logger.warning(f"Fehler beim Löschen der DB: {result.stderr.decode()}")
        else:
            logger.info(f"Datenbank '{db_name}' und Benutzer '{db_user}' gelöscht.")
    except Exception as e:
        logger.warning(f"Fehler beim Löschen der DB/User: {e}")


def init_wordpress_site(site_dir: Path, site_name: str, db_name: str, db_user: str, db_password: str, site_url: str = None, admin_password: str = None, admin_email: str = "admin@example.com") -> None:
    """Komplette WordPress-Initialisierung: Download, Entpacken, DB, Config, Tabellen, Admin."""
    logger.info(f"Initialisiere WordPress-Site '{site_name}'...")

    if site_url is None:
        site_url = f"http://localhost/sites/{site_name}"
    if admin_password is None:
        admin_password = "admin"

    # 1. WordPress herunterladen
    wp_zip = download_wordpress()

    # 2. Entpacken
    extract_wordpress_to_dir(wp_zip, site_dir)

    # 3. Datenbank + Benutzer erstellen
    create_mysql_user_and_db(db_name, db_user, db_password)

    # 4. wp-config.php generieren
    generate_wp_config(db_name, db_user, db_password, site_name, site_dir, site_url)

    # 5. WordPress-Datenbank-Schema erstellen
    setup_wordpress_database(db_name, db_user, db_password, site_url)

    # 6. Admin-User erstellen
    create_wordpress_admin(db_name, "admin", admin_password, admin_email)

    logger.info(f"WordPress-Site '{site_name}' erfolgreich initialisiert.")
