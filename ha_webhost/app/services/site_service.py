import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from core import crypto
from core.config import SITES_DIR
from core.security import validate_site_name
from models.site import Site, SiteStatus, SourceType
from services import (
    caddy_service,
    gallery_service,
    git_service,
    php_fpm_service,
    python_app_service,
    wordpress_service,
    zip_service,
)


def list_sites(session: Session) -> list[Site]:
    return list(session.exec(select(Site)).all())


def get_site(session: Session, name: str) -> Optional[Site]:
    return session.exec(select(Site).where(Site.name == name)).first()


#: Site-Typen, deren .php-Dateien tatsaechlich ausgefuehrt werden sollen
#: (eigener PHP-FPM-Pool pro Site, siehe services/php_fpm_service.py und
#: caddy_service.SITE_BLOCK_PHP) statt nur statisch ausgeliefert zu werden.
PHP_SOURCE_TYPES = (SourceType.wordpress, SourceType.php)


def _make_writable_for_php(site_dir: Path) -> None:
    """PHP-FPM-Worker laufen als 'nobody' (siehe php_fpm_service.POOL_TEMPLATE),
    muessen aber teils selbst in ihr Site-Verzeichnis schreiben koennen - z.B.
    WordPress-Medien-Uploads ueber die eigene wp-admin-Oberflaeche, oder eigene
    kleine PHP-Tools, die Daten in einer Datei persistieren (siehe die
    "anleitung"-Demo-Site). Site-Verzeichnisse werden aber vom Backend (root)
    per ZIP-Extraktion/wp-cli angelegt und sind standardmaessig nicht fuer
    'nobody' beschreibbar. Analog zu LOGS_DIR/PHP-FPM-Socket bewusst
    pragmatisch offene Berechtigungen (kein Multi-Tenant-Hosting, ein
    vertrauenswuerdiger Nutzer/LAN). Laeuft bei jedem sync_proxy() (inkl.
    Add-on-Start) erneut, heilt also auch bereits bestehende Sites."""
    for root, _dirs, files in os.walk(site_dir):
        try:
            os.chmod(root, 0o777)
        except OSError:
            continue
        for filename in files:
            try:
                os.chmod(os.path.join(root, filename), 0o666)
            except OSError:
                continue


def sync_proxy(session: Session) -> None:
    active_sites = [s for s in list_sites(session) if s.status == SiteStatus.active]
    names = [s.name for s in active_sites]
    php_names = [s.name for s in active_sites if s.source_type in PHP_SOURCE_TYPES]
    python_sites = [s for s in active_sites if s.source_type == SourceType.python]
    python_ports = {s.name: python_app_service.app_port(s.id) for s in python_sites}

    for name in php_names:
        _make_writable_for_php(SITES_DIR / name)

    php_fpm_service.sync_pools(php_names)
    caddy_service.write_and_reload(names, php_names, python_ports)

    python_app_service.ensure_running(
        [(s.name, SITES_DIR / s.name, python_ports[s.name]) for s in python_sites]
    )
    python_app_service.stop_orphaned(set(python_ports.keys()))


def create_site_from_upload(
    session: Session, name: str, upload_bytes: bytes, source_type: SourceType = SourceType.upload
) -> Site:
    """Legt eine neue Upload- oder PHP-Site an oder ersetzt den Inhalt einer
    bestehenden (erneutes Hochladen unter demselben Namen = Redeploy). Upload
    und PHP-Upload unterscheiden sich nur darin, ob .php-Dateien ausgefuehrt
    werden (siehe PHP_SOURCE_TYPES) - Deployment-Mechanik (ZIP entpacken) ist
    identisch."""
    name = validate_site_name(name)
    site = get_site(session, name)
    if site and site.source_type != source_type:
        raise ValueError(
            f"Site '{name}' existiert bereits mit Quelle '{site.source_type.value}'."
        )

    if not site:
        site = Site(name=name, source_type=source_type, status=SiteStatus.deploying)
    else:
        site.status = SiteStatus.deploying
    session.add(site)
    session.commit()
    session.refresh(site)

    try:
        zip_service.deploy_zip_upload(upload_bytes, SITES_DIR / name)
        site.status = SiteStatus.active
        site.last_error = None
    except Exception as exc:
        site.status = SiteStatus.failed
        site.last_error = str(exc)
        raise
    finally:
        site.updated_at = datetime.now(timezone.utc)
        site.last_deploy_at = datetime.now(timezone.utc)
        session.add(site)
        session.commit()
        sync_proxy(session)

    return site


def create_site_from_python_upload(session: Session, name: str, upload_bytes: bytes) -> Site:
    """Legt eine neue Python-App-Site an oder aktualisiert eine bestehende
    (erneutes Hochladen unter demselben Namen = Redeploy: laufender Prozess
    wird gestoppt, Dateien + Abhängigkeiten ersetzt, Prozess über
    sync_proxy()/ensure_running() neu gestartet).

    Die App braucht eine main.py im ZIP-Root, die selbst per HTTP auf
    0.0.0.0:$PORT lauscht (Umgebungsvariable PORT wird gesetzt) - passt zu
    den meisten Flask-/FastAPI-Quickstarts. Optionale requirements.txt wird
    automatisch installiert (siehe services/python_app_service.py)."""
    name = validate_site_name(name)
    site = get_site(session, name)
    if site and site.source_type != SourceType.python:
        raise ValueError(
            f"Site '{name}' existiert bereits mit Quelle '{site.source_type.value}'."
        )

    if site:
        python_app_service.stop(name)  # laufenden Prozess vor Dateiaustausch stoppen
        site.status = SiteStatus.deploying
    else:
        site = Site(name=name, source_type=SourceType.python, status=SiteStatus.deploying)
    session.add(site)
    session.commit()
    session.refresh(site)

    try:
        site_dir = SITES_DIR / name
        zip_service.deploy_zip_upload(upload_bytes, site_dir)
        if not (site_dir / "main.py").exists():
            raise RuntimeError(
                "main.py nicht gefunden - wird als Einstiegspunkt benötigt "
                "(muss auf 0.0.0.0:$PORT lauschen)."
            )
        python_app_service.setup_dependencies(site_dir)
        site.status = SiteStatus.active
        site.last_error = None
    except Exception as exc:
        site.status = SiteStatus.failed
        site.last_error = str(exc)
        raise
    finally:
        site.updated_at = datetime.now(timezone.utc)
        site.last_deploy_at = datetime.now(timezone.utc)
        session.add(site)
        session.commit()
        sync_proxy(session)

    return site


def create_site_from_git(
    session: Session, name: str, git_url: str, branch: str, token: Optional[str]
) -> Site:
    name = validate_site_name(name)
    if get_site(session, name):
        raise ValueError(f"Site '{name}' existiert bereits.")

    site = Site(
        name=name,
        source_type=SourceType.git,
        git_url=git_url,
        git_branch=branch or "main",
        git_token=crypto.encrypt(token) if token else None,
        status=SiteStatus.deploying,
    )
    session.add(site)
    session.commit()
    session.refresh(site)

    try:
        git_service.clone_or_pull(git_url, site.git_branch, token, SITES_DIR / name)
        site.status = SiteStatus.active
        site.last_error = None
    except Exception as exc:
        site.status = SiteStatus.failed
        site.last_error = str(exc)
        raise
    finally:
        site.updated_at = datetime.now(timezone.utc)
        site.last_deploy_at = datetime.now(timezone.utc)
        session.add(site)
        session.commit()
        sync_proxy(session)

    return site


def create_gallery_site(
    session: Session, name: str, link_url: Optional[str], link_label: Optional[str]
) -> Site:
    """Legt eine Foto-Galerie-Site an: Gaeste koennen ohne eigenen Account
    ueber .../api/upload Fotos beisteuern, alle sehen sie in derselben
    Galerie (siehe api/gallery.py + services/gallery_service.py)."""
    name = validate_site_name(name)
    if get_site(session, name):
        raise ValueError(f"Site '{name}' existiert bereits.")

    site = Site(
        name=name,
        source_type=SourceType.gallery,
        status=SiteStatus.active,
        gallery_link_url=link_url or None,
        gallery_link_label=link_label or None,
    )
    session.add(site)
    session.commit()
    session.refresh(site)

    gallery_service.init_gallery(name)
    gallery_service.write_frontend(name)

    site.updated_at = datetime.now(timezone.utc)
    site.last_deploy_at = datetime.now(timezone.utc)
    session.add(site)
    session.commit()
    sync_proxy(session)

    return site


def create_wordpress_site(
    session: Session,
    name: str,
    blog_name: str = "My WordPress Site",
    admin_email: str = "admin@example.com"
) -> Site:
    """Legt eine WordPress-Site an: lädt WordPress herunter, erstellt Datenbank
    + Benutzer, generiert wp-config.php."""
    name = validate_site_name(name)
    if get_site(session, name):
        raise ValueError(f"Site '{name}' existiert bereits.")

    # DB-Zugangsdaten generieren (Name basiert auf Site-Name)
    db_name = f"wp_{name.replace('-', '_')}"
    db_user = f"wp_{name.replace('-', '_')}"
    db_password = crypto.generate_random_password(32)
    admin_password = crypto.generate_random_password(16)

    site = Site(
        name=name,
        source_type=SourceType.wordpress,
        status=SiteStatus.deploying,
        wordpress_db_name=db_name,
        wordpress_db_user=db_user,
        wordpress_db_password=crypto.encrypt(db_password),
        wordpress_admin_user="admin",
        wordpress_admin_password=crypto.encrypt(admin_password),
        wordpress_admin_email=admin_email,
        wordpress_blog_name=blog_name,
    )
    session.add(site)
    session.commit()
    session.refresh(site)

    try:
        site_dir = SITES_DIR / name
        site_url = f"http://localhost/sites/{name}"
        wordpress_service.init_wordpress_site(
            site_dir, name, db_name, db_user, db_password,
            site_url=site_url,
            admin_password=admin_password,
            admin_email=admin_email,
            blog_name=blog_name
        )
        site.status = SiteStatus.active
        site.last_error = None
    except Exception as exc:
        site.status = SiteStatus.failed
        site.last_error = str(exc)
        raise
    finally:
        site.updated_at = datetime.now(timezone.utc)
        site.last_deploy_at = datetime.now(timezone.utc)
        session.add(site)
        session.commit()
        sync_proxy(session)

    return site


def refresh_gallery_frontend(session: Session, name: str) -> Site:
    """Kopiert index.html/style.css/app.js einer Galerie-Site neu aus der
    aktuellen Vorlage (gallery_template/) - z.B. nach einem Add-on-Update
    mit verbessertem Galerie-Design. Fasst dabei uploads/ und manifest.json
    NICHT an, bereits hochgeladene Fotos bleiben unveraendert erhalten."""
    site = get_site(session, name)
    if not site:
        raise ValueError(f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.gallery:
        raise ValueError("Nur bei Fotogalerie-Sites möglich.")

    gallery_service.write_frontend(name)

    site.updated_at = datetime.now(timezone.utc)
    session.add(site)
    session.commit()
    session.refresh(site)
    return site


def redeploy(session: Session, name: str) -> Site:
    site = get_site(session, name)
    if not site:
        raise ValueError(f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.git:
        raise ValueError("Nur per Git deployte Sites können neu deployt werden.")

    site.status = SiteStatus.deploying
    session.add(site)
    session.commit()

    try:
        token = crypto.decrypt(site.git_token) if site.git_token else None
        git_service.clone_or_pull(site.git_url, site.git_branch, token, SITES_DIR / name)
        site.status = SiteStatus.active
        site.last_error = None
    except Exception as exc:
        site.status = SiteStatus.failed
        site.last_error = str(exc)
        raise
    finally:
        site.updated_at = datetime.now(timezone.utc)
        site.last_deploy_at = datetime.now(timezone.utc)
        session.add(site)
        session.commit()

    return site


def delete_site(session: Session, name: str) -> None:
    site = get_site(session, name)
    if not site:
        raise ValueError(f"Site '{name}' nicht gefunden.")

    # WordPress-Datenbank aufräumen
    if site.source_type == SourceType.wordpress and site.wordpress_db_name and site.wordpress_db_user:
        try:
            wordpress_service.delete_wordpress_database(site.wordpress_db_name, site.wordpress_db_user)
        except Exception as e:
            # Nicht fatal – Dateien trotzdem löschen
            import logging
            logging.getLogger(__name__).error(f"Fehler beim Löschen der WordPress-DB: {e}")

    if site.source_type == SourceType.python:
        python_app_service.stop(name)

    site_dir = SITES_DIR / name
    if site_dir.exists():
        shutil.rmtree(site_dir)

    session.delete(site)
    session.commit()
    sync_proxy(session)
