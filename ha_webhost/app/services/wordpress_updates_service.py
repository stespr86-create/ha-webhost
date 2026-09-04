import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def check_wordpress_updates(site_dir: Path) -> dict:
    """Prüft auf verfügbare WordPress-Updates mit wp-cli."""
    try:
        # Core-Updates
        result = subprocess.run(
            ["wp", "core", "check-update", "--format=count"],
            cwd=site_dir,
            capture_output=True,
            timeout=30
        )

        has_core_update = result.stdout.decode().strip() != "0" if result.returncode == 0 else False

        # Plugin-Updates
        plugin_result = subprocess.run(
            ["wp", "plugin", "list", "--update=available", "--format=count"],
            cwd=site_dir,
            capture_output=True,
            timeout=30
        )

        plugin_updates = int(plugin_result.stdout.decode().strip() or 0) if plugin_result.returncode == 0 else 0

        # Theme-Updates
        theme_result = subprocess.run(
            ["wp", "theme", "list", "--update=available", "--format=count"],
            cwd=site_dir,
            capture_output=True,
            timeout=30
        )

        theme_updates = int(theme_result.stdout.decode().strip() or 0) if theme_result.returncode == 0 else 0

        logger.info(
            f"WordPress-Updates verfügbar: Core={has_core_update}, Plugins={plugin_updates}, Themes={theme_updates}"
        )

        return {
            "core_update_available": has_core_update,
            "plugin_updates_available": plugin_updates,
            "theme_updates_available": theme_updates,
            "total_updates": (1 if has_core_update else 0) + plugin_updates + theme_updates,
        }

    except Exception as e:
        logger.warning(f"Fehler beim Update-Check: {e}")
        return {"error": str(e)}


def install_language(site_dir: Path, locale: str = "de_DE") -> dict:
    """Installiert und aktiviert ein WordPress-Sprachpaket (z.B. "de_DE" für
    Deutsch) über wp-cli - übersetzt damit sowohl die wp-admin-Oberfläche
    als auch alle Core-Standardtexte des Frontends. Plugins/Themes mit
    eigener .mo-Datei für die gewählte Sprache werden automatisch mit
    übersetzt, wp-cli lädt deren Sprachdateien bei Bedarf separat nach
    ("wp language plugin/theme update") - hier bewusst nicht Teil dieser
    Funktion, da das nur bei bereits installierten Plugins/Themes sinnvoll
    ist und sonst nur eine leere No-Op-Warnung erzeugt."""
    try:
        result = subprocess.run(
            ["wp", "language", "core", "install", locale, "--activate", "--allow-root"],
            cwd=site_dir,
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            return {"status": "error", "error": result.stderr.decode(errors="replace").strip()}
        return {"status": "success", "locale": locale}
    except Exception as e:
        logger.error(f"Fehler bei Sprachpaket-Installation ({locale}): {e}")
        return {"status": "error", "error": str(e)}


def install_wordpress_updates(site_dir: Path, update_core: bool = True, update_plugins: bool = True, update_themes: bool = True) -> dict:
    """Installiert WordPress-Updates mit wp-cli."""
    results = {}

    try:
        if update_core:
            logger.info("Installiere WordPress-Core-Updates...")
            result = subprocess.run(
                ["wp", "core", "update"],
                cwd=site_dir,
                capture_output=True,
                timeout=120
            )
            results["core"] = "success" if result.returncode == 0 else f"failed: {result.stderr.decode()}"

        if update_plugins:
            logger.info("Installiere Plugin-Updates...")
            result = subprocess.run(
                ["wp", "plugin", "update", "--all"],
                cwd=site_dir,
                capture_output=True,
                timeout=300
            )
            results["plugins"] = "success" if result.returncode == 0 else f"failed: {result.stderr.decode()}"

        if update_themes:
            logger.info("Installiere Theme-Updates...")
            result = subprocess.run(
                ["wp", "theme", "update", "--all"],
                cwd=site_dir,
                capture_output=True,
                timeout=300
            )
            results["themes"] = "success" if result.returncode == 0 else f"failed: {result.stderr.decode()}"

        logger.info(f"Update-Installation abgeschlossen: {results}")
        return {"status": "completed", "results": results}

    except Exception as e:
        logger.error(f"Fehler beim Update-Installation: {e}")
        return {"status": "error", "error": str(e)}
