import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session
from starlette.background import BackgroundTask

from core.config import MAX_UPLOAD_BYTES, SITES_DIR
from core.crypto import DecryptionError
from core.db import get_session
from core.security import InvalidSiteName, PathTraversal, UnsafeArchive
from models.site import SitePublic, SiteStatus, SourceType
from services import site_service, zip_service, backup_service, health_service, monitoring_service, log_service, wordpress_updates_service, wordpress_validator, wordpress_marketplace
from services.git_service import GitError

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("", response_model=list[SitePublic])
def list_sites(session: Session = Depends(get_session)):
    return site_service.list_sites(session)


@router.get("/backup")
def backup_all_sites(session: Session = Depends(get_session)):
    """Alle aktiven Sites gebündelt als ein ZIP herunterladen (manuelles
    Backup - .git-Verzeichnisse werden ausgeschlossen, siehe zip_service)."""
    names = [s.name for s in site_service.list_sites(session) if s.status == SiteStatus.active]
    if not names:
        raise HTTPException(404, "Keine aktiven Sites zum Sichern vorhanden.")

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    output_path = Path(tmp.name)
    zip_service.zip_all_sites(names, SITES_DIR, output_path)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return FileResponse(
        output_path,
        media_type="application/zip",
        filename=f"ha-webhost-backup-{timestamp}.zip",
        background=BackgroundTask(output_path.unlink),
    )


@router.get("/{name}", response_model=SitePublic)
def get_site(name: str, session: Session = Depends(get_session)):
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    return site


@router.post("/upload", response_model=SitePublic)
async def deploy_upload(
    name: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Nur ZIP-Dateien werden unterstützt.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Datei zu groß (max. 200 MB).")

    try:
        return site_service.create_site_from_upload(session, name, content)
    except (InvalidSiteName, PathTraversal, UnsafeArchive) as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/php-upload", response_model=SitePublic)
async def deploy_php_upload(
    name: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Wie /upload, aber .php-Dateien werden tatsächlich ausgeführt (eigener
    PHP-FPM-Pool pro Site, siehe services/php_fpm_service.py) statt nur
    statisch ausgeliefert. Kein Datenbank-Zugang out-of-the-box - eigene
    DB-Provisionierung für generische Apps ist noch nicht Teil dieses
    Add-ons (siehe DOCS.md, Roadmap Phase 4)."""
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Nur ZIP-Dateien werden unterstützt.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Datei zu groß (max. 200 MB).")

    try:
        return site_service.create_site_from_upload(session, name, content, source_type=SourceType.php)
    except (InvalidSiteName, PathTraversal, UnsafeArchive) as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/python-upload", response_model=SitePublic)
async def deploy_python_upload(
    name: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Python-App per ZIP hochladen - braucht eine main.py, die selbst per
    HTTP auf 0.0.0.0:$PORT lauscht (Umgebungsvariable PORT wird gesetzt).
    Eigener, überwachter Prozess pro Site statt Docker-Container - kein
    docker_api nötig (siehe services/python_app_service.py). Kein
    Datenbank-Zugang out-of-the-box."""
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Nur ZIP-Dateien werden unterstützt.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Datei zu groß (max. 200 MB).")

    try:
        return site_service.create_site_from_python_upload(session, name, content)
    except (InvalidSiteName, PathTraversal, UnsafeArchive) as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Python-App-Installation fehlgeschlagen: {str(exc)}") from exc


@router.post("/git", status_code=201, response_model=SitePublic)
def deploy_git(
    name: str = Form(...),
    git_url: str = Form(...),
    branch: str = Form("main"),
    token: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    try:
        return site_service.create_site_from_git(session, name, git_url, branch, token)
    except InvalidSiteName as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except GitError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/gallery", status_code=201, response_model=SitePublic)
def deploy_gallery(
    name: str = Form(...),
    link_url: Optional[str] = Form(None),
    link_label: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    try:
        return site_service.create_gallery_site(session, name, link_url, link_label)
    except InvalidSiteName as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/wordpress", status_code=201, response_model=SitePublic)
def deploy_wordpress(
    name: str = Form(...),
    blog_name: str = Form("My WordPress Site"),
    admin_email: str = Form("admin@example.com"),
    session: Session = Depends(get_session),
):
    try:
        return site_service.create_wordpress_site(session, name, blog_name, admin_email)
    except InvalidSiteName as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"WordPress-Installation fehlgeschlagen: {str(exc)}") from exc


@router.post("/{name}/redeploy", response_model=SitePublic)
def redeploy(name: str, session: Session = Depends(get_session)):
    try:
        return site_service.redeploy(session, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (GitError, DecryptionError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{name}/gallery/refresh", response_model=SitePublic)
def refresh_gallery(name: str, session: Session = Depends(get_session)):
    try:
        return site_service.refresh_gallery_frontend(session, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{name}/monitoring", response_model=dict)
def site_monitoring(name: str, session: Session = Depends(get_session)):
    """Speicherplatz-, RAM- und CPU-Nutzung einer Site. RAM/CPU gibt es nur
    fuer Site-Typen mit eigenem Prozess (Python-Apps, WordPress/PHP-Upload
    via PHP-FPM) - "running": false bei einem gerade idlen PHP-FPM-Pool
    (pm=ondemand) ist normal, kein Fehler. Bei statischen/Git-/Galerie-Sites
    gibt es "running": null, dort nur Speicherplatz."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")

    try:
        return monitoring_service.get_site_monitoring(site)
    except Exception as exc:
        raise HTTPException(422, f"Monitoring fehlgeschlagen: {str(exc)}") from exc


@router.get("/{name}/logs", response_model=dict)
def site_logs(name: str, lines: int = 200, session: Session = Depends(get_session)):
    """Letzte Log-Zeilen einer Site (Live-Log-Viewer). Nur fuer Site-Typen mit
    eigenem Prozess verfuegbar: Python-Apps (App-Ausgabe) und WordPress/
    PHP-Upload (PHP-Fehler-Log des zugehoerigen PHP-FPM-Pools). Bei
    statischen/Git-/Galerie-Sites "available": false - dort gibt es keinen
    eigenen Prozess und damit kein Anwendungs-Log."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")

    lines = max(1, min(lines, 1000))
    try:
        return log_service.read_log(name, site.source_type, lines)
    except Exception as exc:
        raise HTTPException(422, f"Logs konnten nicht gelesen werden: {str(exc)}") from exc


@router.get("/{name}/health", response_model=dict)
def health_check_wordpress(name: str, session: Session = Depends(get_session)):
    """Führt einen Health-Check einer WordPress-Site durch."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites haben Health-Checks.")

    try:
        checker = health_service.WordPressHealth(name, site.wordpress_db_name)
        checker.run_all_checks()
        return checker.to_dict()
    except Exception as exc:
        raise HTTPException(422, f"Health-Check fehlgeschlagen: {str(exc)}") from exc


@router.get("/{name}/updates/check", response_model=dict)
def check_wordpress_updates(name: str, session: Session = Depends(get_session)):
    """Prüft auf verfügbare WordPress-Updates (Core, Plugins, Themes)."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites können Updates checken.")

    try:
        site_dir = SITES_DIR / name
        updates = wordpress_updates_service.check_wordpress_updates(site_dir)
        return {"site": name, **updates}
    except Exception as exc:
        raise HTTPException(422, f"Update-Check fehlgeschlagen: {str(exc)}") from exc


@router.post("/{name}/updates/install", response_model=dict)
def install_wordpress_updates(
    name: str,
    core: bool = True,
    plugins: bool = True,
    themes: bool = True,
    session: Session = Depends(get_session)
):
    """Installiert WordPress-Updates."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites können Updates installieren.")

    try:
        site_dir = SITES_DIR / name
        result = wordpress_updates_service.install_wordpress_updates(site_dir, core, plugins, themes)
        return {"site": name, **result}
    except Exception as exc:
        raise HTTPException(422, f"Update-Installation fehlgeschlagen: {str(exc)}") from exc


@router.post("/{name}/backup", response_model=dict)
def backup_wordpress(name: str, session: Session = Depends(get_session)):
    """Erstellt ein Backup einer WordPress-Site (Dateien + Datenbank)."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites können gebackupped werden.")

    try:
        site_dir = SITES_DIR / name
        backup_dir = SITES_DIR / ".backups"
        backup_file = backup_service.backup_wordpress_site(site_dir, site.wordpress_db_name, backup_dir)

        # Cleanup old backups
        backup_service.cleanup_old_backups(backup_dir, max_age_days=30, max_count=10)

        return {
            "status": "success",
            "backup_file": backup_file.name,
            "size_mb": round(backup_file.stat().st_size / 1024 / 1024, 2)
        }
    except Exception as exc:
        raise HTTPException(422, f"Backup fehlgeschlagen: {str(exc)}") from exc


@router.get("/{name}/plugins/search", response_model=list)
def search_plugins(name: str, q: str = "", session: Session = Depends(get_session)):
    """Sucht WordPress-Plugins im Marketplace (WordPress.org)."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites haben Plugin-Marketplace.")

    if not q or len(q) < 2:
        raise HTTPException(400, "Suchbegriff zu kurz (mindestens 2 Zeichen)")

    try:
        results = wordpress_marketplace.WordPressMarketplace.search_plugins(q, limit=20)
        return results
    except Exception as exc:
        raise HTTPException(422, f"Plugin-Suche fehlgeschlagen: {str(exc)}") from exc


@router.get("/{name}/themes/search", response_model=list)
def search_themes(name: str, q: str = "", session: Session = Depends(get_session)):
    """Sucht WordPress-Themes im Marketplace (WordPress.org)."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites haben Theme-Marketplace.")

    if not q or len(q) < 2:
        raise HTTPException(400, "Suchbegriff zu kurz (mindestens 2 Zeichen)")

    try:
        results = wordpress_marketplace.WordPressMarketplace.search_themes(q, limit=20)
        return results
    except Exception as exc:
        raise HTTPException(422, f"Theme-Suche fehlgeschlagen: {str(exc)}") from exc


@router.post("/{name}/plugins/install", response_model=dict)
def install_plugin(name: str, slug: str = Form(...), activate: bool = Form(True), session: Session = Depends(get_session)):
    """Installiert ein Plugin aus dem Marketplace."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites können Plugins installieren.")

    try:
        site_dir = SITES_DIR / name
        success = wordpress_marketplace.WordPressMarketplace.install_plugin(site_dir, slug, activate)
        return {"status": "success" if success else "failed", "plugin": slug, "activated": activate}
    except Exception as exc:
        raise HTTPException(422, f"Plugin-Installation fehlgeschlagen: {str(exc)}") from exc


@router.post("/{name}/themes/install", response_model=dict)
def install_theme(name: str, slug: str = Form(...), activate: bool = Form(False), session: Session = Depends(get_session)):
    """Installiert ein Theme aus dem Marketplace."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites können Themes installieren.")

    try:
        site_dir = SITES_DIR / name
        success = wordpress_marketplace.WordPressMarketplace.install_theme(site_dir, slug, activate)
        return {"status": "success" if success else "failed", "theme": slug, "activated": activate}
    except Exception as exc:
        raise HTTPException(422, f"Theme-Installation fehlgeschlagen: {str(exc)}") from exc


@router.get("/{name}/plugins/list", response_model=list)
def list_plugins(name: str, session: Session = Depends(get_session)):
    """Listet installierte Plugins einer Site."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites haben Plugins.")

    try:
        site_dir = SITES_DIR / name
        plugins = wordpress_marketplace.WordPressMarketplace.list_installed_plugins(site_dir)
        return plugins
    except Exception as exc:
        raise HTTPException(422, f"Fehler beim Auflisten: {str(exc)}") from exc


@router.get("/{name}/themes/list", response_model=list)
def list_themes(name: str, session: Session = Depends(get_session)):
    """Listet installierte Themes einer Site."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites haben Themes.")

    try:
        site_dir = SITES_DIR / name
        themes = wordpress_marketplace.WordPressMarketplace.list_installed_themes(site_dir)
        return themes
    except Exception as exc:
        raise HTTPException(422, f"Fehler beim Auflisten: {str(exc)}") from exc


@router.delete("/{name}/plugins/{slug}", status_code=204)
def uninstall_plugin(name: str, slug: str, session: Session = Depends(get_session)):
    """Deinstalliert ein Plugin."""
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    if site.source_type != SourceType.wordpress:
        raise HTTPException(400, "Nur WordPress-Sites haben Plugins.")

    try:
        site_dir = SITES_DIR / name
        success = wordpress_marketplace.WordPressMarketplace.uninstall_plugin(site_dir, slug)
        if not success:
            raise HTTPException(422, f"Plugin '{slug}' konnte nicht gelöscht werden.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f"Fehler beim Löschen: {str(exc)}") from exc


@router.get("/system/validate-wordpress", response_model=dict)
def validate_wordpress_system(session: Session = Depends(get_session)):
    """Validiert dass alle WordPress-Sites isoliert sind und sauber konfiguriert."""
    try:
        # Alle WordPress-Sites sammeln
        sites = site_service.list_sites(session)
        wp_sites = [s for s in sites if s.source_type == SourceType.wordpress]

        if not wp_sites:
            return {"status": "no_wordpress_sites", "count": 0}

        # Directories sammeln
        site_dirs = [SITES_DIR / s.name for s in wp_sites]

        # Validierung durchführen
        validation = wordpress_validator.validate_multiple_sites_isolation(site_dirs)
        return {
            "status": "validated",
            "wordpress_sites": len(wp_sites),
            **validation
        }
    except Exception as exc:
        raise HTTPException(422, f"Validierung fehlgeschlagen: {str(exc)}") from exc


@router.delete("/{name}", status_code=204)
def delete(name: str, session: Session = Depends(get_session)):
    try:
        site_service.delete_site(session, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
