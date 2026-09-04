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

// Reverse-Proxy-Erkennung - MUSS vor allem anderen stehen, insbesondere vor
// require wp-settings.php: Caddy selbst terminiert kein TLS (auto_https
// off - HTTPS wird vorgelagert beendet: Home-Assistant-Ingress bzw.
// Tailscale Funnel), $_SERVER['HTTPS'] ist deshalb hier NIE direkt gesetzt.
// Tailscale Funnel sendet zwar X-Forwarded-Host, aber KEIN
// X-Forwarded-Proto (per Caddy-Access-Log geprueft) - das uebliche Signal
// fehlt also. Ohne diesen Fix haelt WordPress' eigene is_ssl()-Funktion
// (genutzt u.a. fuer Admin-/Login-Redirects, Cookie-Sicherheits-Flags)
// JEDE Anfrage faelschlich fuer unverschluesselt, obwohl WP_HOME unten auf
// https:// gesetzt wird - das Auseinanderklaffen fuehrte zu einer
// Redirect-Schleife auf wp-login.php/wp-admin (WordPress besteht dort aktiv
// auf HTTPS, erkennt die Anfrage aber nie als sicher). Tailscale Funnel
// setzt zuverlaessig Tailscale-Funnel-Request und bedient ausschliesslich
// HTTPS - als zusaetzliches Signal nutzbar. $_SERVER['HTTPS'] wird hier
// direkt gesetzt (nicht nur eine eigene Variable), damit WordPress-Core
// selbst (nicht nur unsere eigene WP_HOME-Berechnung unten) korrekt
// erkennt, dass die Anfrage sicher ist.
if (
    ( ! empty( $_SERVER['HTTP_X_FORWARDED_PROTO'] ) && strtolower( $_SERVER['HTTP_X_FORWARDED_PROTO'] ) === 'https' )
    || ! empty( $_SERVER['HTTP_TAILSCALE_FUNNEL_REQUEST'] )
) {{
    $_SERVER['HTTPS'] = 'on';
}}

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

// WordPress-Pfade (automatisch aus HTTP_HOST + eigenem Site-Namen bestimmt).
//
// Zusaetzlich noetig: der Praefix, unter dem Home-Assistant-Ingress diese
// Anfrage weiterleitet (z.B. "/api/hassio_ingress/<token>", pro Browser-
// Session unterschiedlich). WordPress kann diesen Praefix NICHT aus
// REQUEST_URI ablesen - HAs Supervisor entfernt ihn bereits, bevor die
// Anfrage den Container erreicht (REQUEST_URI enthaelt hier nur noch
// "/sites/{site_name}/..."). HA sendet ihn stattdessen separat im Header
// X-Ingress-Path mit (siehe HA-Add-on-Doku). Ohne diesen Praefix zeigen
// alle von WordPress selbst generierten absoluten Links (u.a. der
// wp-login.php-Redirect bei fehlendem Login) am Token vorbei auf die
// nackte Home-Assistant-Domain -> 404 (live beobachtet). Der Header ist
// nur ueber den Ingress-Listener vertrauenswuerdig - ueber den
// oeffentlichen Port (Tailscale Funnel) entfernt Caddy ihn aktiv
// (siehe caddy_service.STRIP_INGRESS_PATH_DIRECTIVE), er ist dort also nie
// gesetzt und wird hier entsprechend nicht verwendet.
if ( defined( 'WP_HOME' ) ) {{
    // Überschreiben ist erlaubt (z.B. in wp-cli Skripten)
}} else {{
    // $_SERVER['HTTPS'] ist jetzt zuverlaessig (siehe Fix oben) - normale
    // WordPress-Standardpruefung reicht hier.
    $protocol = ( ! empty( $_SERVER['HTTPS'] ) && $_SERVER['HTTPS'] !== 'off' ) ? 'https://' : 'http://';
    $ingress_prefix = ! empty( $_SERVER['HTTP_X_INGRESS_PATH'] ) ? $_SERVER['HTTP_X_INGRESS_PATH'] : '';
    $computed_url = $protocol . $_SERVER['HTTP_HOST'] . $ingress_prefix . '/sites/{site_name}';
    define( 'WP_HOME',    $computed_url );
    define( 'WP_SITEURL', $computed_url );
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


def wp_cli_install(
    site_dir: Path, site_url: str, blog_name: str, admin_user: str, admin_password: str, admin_email: str
) -> None:
    """Installiert WordPress ueber wp-cli ('wp core install') statt handgeschriebenem
    SQL: legt das vollstaendige Standard-Datenbankschema an (alle Kern-Tabellen,
    z.B. auch wp_comments/wp_terms/wp_term_taxonomy, die die vorherige
    Kurzfassung komplett ausgelassen hat), setzt saemtliche Standard-Optionen
    (u.a. blog_charset/html_type - deren Fehlen zu einem kaputten, leeren
    Content-Type-Header fuehrte, siehe CHANGELOG) und hasht das Admin-Passwort
    mit WordPress' eigenem phpass statt einem nicht kompatiblen eigenen
    MD5-Schema, mit dem sich vorher nicht einloggen liess."""
    logger.info(f"Fuehre 'wp core install' fuer '{site_dir.name}' aus...")

    result = subprocess.run(
        [
            "wp", "core", "install",
            f"--url={site_url}",
            f"--title={blog_name}",
            f"--admin_user={admin_user}",
            f"--admin_password={admin_password}",
            f"--admin_email={admin_email}",
            "--skip-email",
            "--allow-root",
        ],
        cwd=site_dir,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"wp core install fehlgeschlagen: {result.stderr.decode().strip()}")
    logger.info(f"WordPress-Installation fuer '{site_dir.name}' abgeschlossen.")


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


def init_wordpress_site(
    site_dir: Path,
    site_name: str,
    db_name: str,
    db_user: str,
    db_password: str,
    site_url: str = None,
    admin_password: str = None,
    admin_email: str = "admin@example.com",
    blog_name: str = "WordPress Site",
) -> None:
    """Komplette WordPress-Initialisierung: Download, Entpacken, DB, Config, Installation."""
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

    # 5. WordPress installieren (Schema + Standard-Optionen + Admin-User, siehe wp_cli_install)
    wp_cli_install(site_dir, site_url, blog_name, "admin", admin_password, admin_email)

    logger.info(f"WordPress-Site '{site_name}' erfolgreich initialisiert.")
