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
from models.site import SitePublic, SiteStatus
from services import site_service, zip_service
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


@router.delete("/{name}", status_code=204)
def delete(name: str, session: Session = Depends(get_session)):
    try:
        site_service.delete_site(session, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
