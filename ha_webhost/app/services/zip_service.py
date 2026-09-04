import shutil
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

from core.security import safe_extract_zip


def deploy_zip_upload(upload_bytes: bytes, target_dir: Path) -> None:
    """Schreibt hochgeladene ZIP-Bytes in eine temporäre Datei und entpackt sicher."""
    with NamedTemporaryFile(suffix=".zip", delete=True) as tmp:
        tmp.write(upload_bytes)
        tmp.flush()

        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_extract_zip(Path(tmp.name), target_dir)


def zip_directory(source_dir: Path, output_zip: Path) -> Path:
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir))
    return output_zip


#: Verzeichnisnamen, die in Site-Backups nie mitgesichert werden: bei
#: Redeploy/Update automatisch neu erzeugt (Git-Checkout bzw. pip install),
#: unnoetiger Ballast im Backup - .git zusaetzlich potenziell mit
#: Zugangsdaten im Remote-Verlauf, .deps kann je nach App sehr gross werden.
BACKUP_EXCLUDED_DIRS = {".git", ".deps"}


def zip_all_sites(site_names: list[str], sites_dir: Path, output_zip: Path) -> Path:
    """Packt alle Sites in ein gemeinsames Archiv, je Site in einem eigenen
    Ordner (siehe BACKUP_EXCLUDED_DIRS fuer ausgeschlossene Unterordner)."""
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in site_names:
            site_dir = sites_dir / name
            if not site_dir.exists():
                continue
            for path in site_dir.rglob("*"):
                if not path.is_file():
                    continue
                if BACKUP_EXCLUDED_DIRS & set(path.relative_to(site_dir).parts):
                    continue
                zf.write(path, Path(name) / path.relative_to(site_dir))
    return output_zip
