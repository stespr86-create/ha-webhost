"""Sicherheitsfunktionen: Zip-Slip-Schutz, Path-Traversal-Schutz, Namensvalidierung."""

import re
import zipfile
from pathlib import Path

from core.config import RESERVED_NAMES, SITE_NAME_PATTERN

_ZIP_SYMLINK_MODE = 0o120000


class InvalidSiteName(ValueError):
    pass


class UnsafeArchive(ValueError):
    pass


class PathTraversal(ValueError):
    pass


def validate_site_name(name: str) -> str:
    name = name.strip().lower()
    if not re.match(SITE_NAME_PATTERN, name):
        raise InvalidSiteName(
            "Name muss 3-32 Zeichen lang sein, nur a-z, 0-9 und '-' enthalten "
            "und darf nicht mit '-' beginnen oder enden."
        )
    if name in RESERVED_NAMES:
        raise InvalidSiteName(f"'{name}' ist ein reservierter Name.")
    return name


def safe_join(base: Path, *parts: str) -> Path:
    """Hängt Pfadteile an base an und lehnt jeden Versuch ab, base zu verlassen."""
    base = base.resolve()
    target = base.joinpath(*parts).resolve()
    if target != base and base not in target.parents:
        raise PathTraversal(f"Pfad '{target}' liegt außerhalb von '{base}'.")
    return target


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Entpackt ein ZIP-Archiv und lehnt Zip-Slip, absolute Pfade und Symlinks ab."""
    dest_dir = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise UnsafeArchive(f"Unsichere Pfadangabe im Archiv: {member.filename}")

            resolved = (dest_dir / member_path).resolve()
            if dest_dir != resolved and dest_dir not in resolved.parents:
                raise UnsafeArchive(f"Zip-Slip erkannt: {member.filename}")

            is_symlink = (member.external_attr >> 16) & 0o170000 == _ZIP_SYMLINK_MODE
            if is_symlink:
                raise UnsafeArchive(f"Symlinks im Archiv sind nicht erlaubt: {member.filename}")

        zf.extractall(dest_dir)
