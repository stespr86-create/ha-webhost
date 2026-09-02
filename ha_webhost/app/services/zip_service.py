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
