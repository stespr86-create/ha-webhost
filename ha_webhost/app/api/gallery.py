import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session
from starlette.background import BackgroundTask

from core.config import MAX_GALLERY_FILE_BYTES
from core.db import get_session
from models.site import SiteStatus, SourceType
from services import gallery_service, site_service

# Bewusst getrennt von /api/sites (Admin-API, nur ueber den Ingress-Port
# erreichbar): dieser Router liegt unter /sites/<name>/api/* und wird von
# Caddy zusaetzlich auch auf dem OEFFENTLICHEN Port freigegeben (siehe
# services/caddy_service.py), da Gaeste ohne HA-Login und ohne eigenen
# Account Fotos beisteuern koennen sollen. Nur die zwei hier definierten
# Endpunkte (lesen + hochladen) sind darüber erreichbar - kein Loeschen,
# keine sonstige Admin-Funktion.
router = APIRouter(prefix="/sites", tags=["gallery-public"])


def _get_active_gallery(session: Session, name: str):
    site = site_service.get_site(session, name)
    if not site or site.source_type != SourceType.gallery or site.status != SiteStatus.active:
        raise HTTPException(404, "Galerie nicht gefunden.")
    return site


@router.get("/{name}/api/meta")
def gallery_meta(name: str, session: Session = Depends(get_session)):
    site = _get_active_gallery(session, name)
    return {
        "title": gallery_service.title_from_name(name),
        "link_url": site.gallery_link_url,
        "link_label": site.gallery_link_label,
        "photos": gallery_service.list_photos(name),
    }


@router.get("/{name}/api/download")
def gallery_download(name: str, session: Session = Depends(get_session)):
    _get_active_gallery(session, name)

    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    output_path = Path(tmp.name)
    count = gallery_service.zip_photos(name, output_path)
    if count == 0:
        output_path.unlink(missing_ok=True)
        raise HTTPException(404, "Noch keine Fotos vorhanden.")

    return FileResponse(
        output_path,
        media_type="application/zip",
        filename=f"{name}-fotos.zip",
        background=BackgroundTask(output_path.unlink),
    )


@router.post("/{name}/api/upload")
async def gallery_upload(
    name: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    session: Session = Depends(get_session),
):
    _get_active_gallery(session, name)

    content = await file.read(MAX_GALLERY_FILE_BYTES + 1)
    if len(content) > MAX_GALLERY_FILE_BYTES:
        raise HTTPException(413, f"Foto zu groß (max. {MAX_GALLERY_FILE_BYTES // (1024 * 1024)} MB).")

    try:
        return gallery_service.add_photo(name, content, caption)
    except gallery_service.GalleryFull as exc:
        raise HTTPException(400, str(exc)) from exc
    except gallery_service.InvalidImage as exc:
        raise HTTPException(400, str(exc)) from exc
