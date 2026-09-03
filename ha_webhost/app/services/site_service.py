import shutil
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from core import crypto
from core.config import SITES_DIR
from core.security import validate_site_name
from models.site import Site, SiteStatus, SourceType
from services import caddy_service, gallery_service, git_service, zip_service


def list_sites(session: Session) -> list[Site]:
    return list(session.exec(select(Site)).all())


def get_site(session: Session, name: str) -> Optional[Site]:
    return session.exec(select(Site).where(Site.name == name)).first()


def sync_proxy(session: Session) -> None:
    names = [s.name for s in list_sites(session) if s.status == SiteStatus.active]
    caddy_service.write_and_reload(names)


def create_site_from_upload(session: Session, name: str, upload_bytes: bytes) -> Site:
    """Legt eine neue Upload-Site an oder ersetzt den Inhalt einer
    bestehenden (erneutes Hochladen unter demselben Namen = Redeploy)."""
    name = validate_site_name(name)
    site = get_site(session, name)
    if site and site.source_type != SourceType.upload:
        raise ValueError(
            f"Site '{name}' existiert bereits mit Quelle '{site.source_type.value}'."
        )

    if not site:
        site = Site(name=name, source_type=SourceType.upload, status=SiteStatus.deploying)
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

    site_dir = SITES_DIR / name
    if site_dir.exists():
        shutil.rmtree(site_dir)

    session.delete(site)
    session.commit()
    sync_proxy(session)
