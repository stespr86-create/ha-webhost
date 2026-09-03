import io
import json
import shutil
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from core.config import (
    GALLERY_JPEG_QUALITY,
    GALLERY_MAX_DIMENSION,
    GALLERY_TEMPLATE_DIR,
    MAX_GALLERY_PHOTOS,
    MAX_GALLERY_TOTAL_BYTES,
    SITES_DIR,
)

MAX_CAPTION_LENGTH = 140

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class GalleryFull(Exception):
    pass


class InvalidImage(Exception):
    pass


def _lock_for(name: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(name, threading.Lock())


def _paths(name: str) -> tuple[Path, Path, Path]:
    site_dir = SITES_DIR / name
    uploads_dir = site_dir / "uploads"
    manifest_path = site_dir / "manifest.json"
    return site_dir, uploads_dir, manifest_path


def title_from_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-") if part)


def init_gallery(name: str) -> None:
    site_dir, uploads_dir, manifest_path = _paths(name)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        manifest_path.write_text("[]")


def write_frontend(name: str) -> None:
    """Kopiert die statischen Galerie-Vorlagendateien (index.html/style.css/
    app.js) unveraendert in das Site-Verzeichnis - sie enthalten keine
    Instanz-spezifischen Daten, die holt sich app.js zur Laufzeit selbst
    ueber GET .../api/meta (Titel wird serverseitig aus dem Site-Namen
    abgeleitet, siehe title_from_name)."""
    site_dir, _, _ = _paths(name)
    for filename in ("index.html", "style.css", "app.js"):
        shutil.copyfile(GALLERY_TEMPLATE_DIR / filename, site_dir / filename)


def _read_manifest(manifest_path: Path) -> list[dict]:
    try:
        return json.loads(manifest_path.read_text())
    except (OSError, ValueError):
        return []


def _write_manifest(manifest_path: Path, entries: list[dict]) -> None:
    manifest_path.write_text(json.dumps(entries))


def list_photos(name: str) -> list[dict]:
    """Liest das Manifest und entfernt dabei Eintraege, deren Bild-Datei
    nicht mehr existiert. Dadurch reicht es, ein Foto ueber den normalen
    Datei-Manager (uploads/<datei>) zu loeschen, um es aus der Galerie zu
    entfernen - ohne eigenen Admin-Loesch-Endpunkt."""
    site_dir, uploads_dir, manifest_path = _paths(name)
    entries = _read_manifest(manifest_path)
    kept = [e for e in entries if (uploads_dir / e["filename"]).exists()]
    if len(kept) != len(entries):
        _write_manifest(manifest_path, kept)
    kept.sort(key=lambda e: e["uploaded_at"], reverse=True)
    return kept


def zip_photos(name: str, output_path: Path) -> int:
    """Packt alle aktuell gueltigen Fotos der Galerie in ein ZIP fuer den
    "Alle herunterladen"-Knopf. Gibt die Anzahl enthaltener Fotos zurueck."""
    _, uploads_dir, _ = _paths(name)
    entries = list_photos(name)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in entries:
            file_path = uploads_dir / entry["filename"]
            if file_path.exists():
                zf.write(file_path, entry["filename"])
    return len(entries)


def add_photo(name: str, content: bytes, caption: str) -> dict:
    site_dir, uploads_dir, manifest_path = _paths(name)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    lock = _lock_for(name)
    with lock:
        entries = _read_manifest(manifest_path)
        entries = [e for e in entries if (uploads_dir / e["filename"]).exists()]

        if len(entries) >= MAX_GALLERY_PHOTOS:
            raise GalleryFull("Die Galerie ist voll (maximale Anzahl Fotos erreicht).")

        total_size = sum((uploads_dir / e["filename"]).stat().st_size for e in entries)
        if total_size >= MAX_GALLERY_TOTAL_BYTES:
            raise GalleryFull("Die Galerie ist voll (Speicherplatz-Limit erreicht).")

        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
            image = Image.open(io.BytesIO(content))
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidImage("Datei ist kein gültiges Bild.") from exc

        image.thumbnail((GALLERY_MAX_DIMENSION, GALLERY_MAX_DIMENSION))

        filename = f"{uuid.uuid4().hex}.jpg"
        image.save(uploads_dir / filename, format="JPEG", quality=GALLERY_JPEG_QUALITY)

        entry = {
            "id": uuid.uuid4().hex,
            "filename": filename,
            "caption": (caption or "").strip()[:MAX_CAPTION_LENGTH],
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        entries.append(entry)
        _write_manifest(manifest_path, entries)
        return entry
