import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from core.config import SITES_DIR
from core.security import PathTraversal, safe_join

router = APIRouter(prefix="/api/files", tags=["files"])


def _site_root(name: str) -> Path:
    root = SITES_DIR / name
    if not root.exists():
        raise HTTPException(404, f"Site '{name}' nicht gefunden.")
    return root


@router.get("/{name}")
def list_files(name: str, path: str = ""):
    root = _site_root(name)
    try:
        target = safe_join(root, path) if path else root
    except PathTraversal as exc:
        raise HTTPException(400, str(exc)) from exc

    if not target.exists():
        raise HTTPException(404, "Pfad nicht gefunden.")
    if not target.is_dir():
        raise HTTPException(400, "Pfad ist kein Verzeichnis.")

    entries = [
        {
            "name": item.name,
            "is_dir": item.is_dir(),
            "size": item.stat().st_size if item.is_file() else None,
        }
        for item in sorted(target.iterdir())
    ]
    return {"path": path, "entries": entries}


@router.get("/{name}/content")
def read_file(name: str, path: str):
    root = _site_root(name)
    try:
        target = safe_join(root, path)
    except PathTraversal as exc:
        raise HTTPException(400, str(exc)) from exc

    if not target.is_file():
        raise HTTPException(404, "Datei nicht gefunden.")

    try:
        return {"path": path, "content": target.read_text(encoding="utf-8")}
    except UnicodeDecodeError as exc:
        raise HTTPException(415, "Datei ist keine Textdatei.") from exc


@router.put("/{name}/content")
def write_file(name: str, path: str, body: dict):
    root = _site_root(name)
    try:
        target = safe_join(root, path)
    except PathTraversal as exc:
        raise HTTPException(400, str(exc)) from exc

    content = body.get("content")
    if content is None:
        raise HTTPException(400, "Feld 'content' fehlt.")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"status": "ok"}


@router.post("/{name}/upload")
async def upload_file(name: str, path: str = "", file: UploadFile = File(...)):
    root = _site_root(name)
    try:
        target_dir = safe_join(root, path) if path else root
        dest = safe_join(target_dir, file.filename)
    except PathTraversal as exc:
        raise HTTPException(400, str(exc)) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    return {"status": "ok"}


@router.post("/{name}/mkdir")
def make_dir(name: str, path: str):
    root = _site_root(name)
    try:
        target = safe_join(root, path)
    except PathTraversal as exc:
        raise HTTPException(400, str(exc)) from exc

    target.mkdir(parents=True, exist_ok=True)
    return {"status": "ok"}


@router.delete("/{name}")
def delete_path(name: str, path: str):
    root = _site_root(name)
    try:
        target = safe_join(root, path)
    except PathTraversal as exc:
        raise HTTPException(400, str(exc)) from exc

    if target == root:
        raise HTTPException(400, "Root-Verzeichnis der Site kann nicht gelöscht werden.")
    if not target.exists():
        raise HTTPException(404, "Pfad nicht gefunden.")

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"status": "ok"}
