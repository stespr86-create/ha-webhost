import logging
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def backup_wordpress_site(site_dir: Path, db_name: str, backup_dir: Path) -> Path:
    """Erstellt ein vollständiges Backup einer WordPress-Site (Dateien + Datenbank)."""
    site_name = site_dir.name
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"wordpress-{site_name}-{timestamp}.tar.gz"

    logger.info(f"Erstelle Backup von WordPress-Site '{site_name}'...")

    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Datenbank dumpen
        db_dump_file = backup_dir / f"{db_name}-{timestamp}.sql"
        dump_sql = subprocess.run(
            ["mysqldump", "-u", "root", db_name],
            capture_output=True,
            timeout=60
        )
        if dump_sql.returncode != 0:
            logger.warning(f"Fehler beim DB-Dump: {dump_sql.stderr.decode()}")
        else:
            db_dump_file.write_bytes(dump_sql.stdout)
            logger.info(f"DB-Dump erstellt: {db_dump_file}")

        # 2. WordPress-Dateien + DB-Dump als TAR.GZ
        with tarfile.open(backup_file, "w:gz") as tar:
            # WordPress-Dateien
            tar.add(site_dir, arcname=f"wordpress-{site_name}/")
            # DB-Dump
            if db_dump_file.exists():
                tar.add(db_dump_file, arcname=f"wordpress-{site_name}/{db_dump_file.name}")

        logger.info(f"Backup erstellt: {backup_file} ({backup_file.stat().st_size / 1024 / 1024:.1f} MB)")

        # Cleanup: alten DB-Dump löschen (DB ist jetzt im TAR)
        if db_dump_file.exists():
            db_dump_file.unlink()

        return backup_file

    except Exception as e:
        logger.error(f"Fehler beim Backup: {e}")
        if backup_file.exists():
            backup_file.unlink()
        raise


def cleanup_old_backups(backup_dir: Path, max_age_days: int = 30, max_count: int = 10) -> None:
    """Löscht alte Backups, behält aber mindestens max_count die neuesten."""
    if not backup_dir.exists():
        return

    backup_files = sorted(backup_dir.glob("wordpress-*.tar.gz"), key=lambda p: p.stat().st_mtime)

    # Nach Alter löschen (älter als max_age_days)
    cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
    for backup_file in backup_files:
        if backup_file.stat().st_mtime < cutoff:
            logger.info(f"Lösche altes Backup: {backup_file.name}")
            backup_file.unlink()

    # Nach Anzahl begrenzen (behalte nur max_count neueste)
    remaining = sorted(backup_dir.glob("wordpress-*.tar.gz"), key=lambda p: p.stat().st_mtime)
    if len(remaining) > max_count:
        to_delete = remaining[:-max_count]
        for backup_file in to_delete:
            logger.info(f"Lösche Backup (Limit überschritten): {backup_file.name}")
            backup_file.unlink()
