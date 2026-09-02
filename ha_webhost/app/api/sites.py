from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from core.config import MAX_UPLOAD_BYTES
from core.db import get_session
from core.security import InvalidSiteName, PathTraversal, UnsafeArchive
from services import site_service
from services.git_service import GitError

router = APIRouter(prefix="/api/sites", tags=["sites"])


@router.get("")
def list_sites(session: Session = Depends(get_session)):
    return site_service.list_sites(session)


@router.get("/{name}")
def get_site(name: str, session: Session = Depends(get_session)):
    site = site_service.get_site(session, name)
    if not site:
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    return site


@router.post("/upload", status_code=201)
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


@router.post("/git", status_code=201)
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


@router.post("/{name}/redeploy")
def redeploy(name: str, session: Session = Depends(get_session)):
    try:
        return site_service.redeploy(session, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except GitError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{name}", status_code=204)
def delete(name: str, session: Session = Depends(get_session)):
    try:
        site_service.delete_site(session, name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
