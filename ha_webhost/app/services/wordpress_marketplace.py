"""WordPress-Plugins und Themes installieren vom WordPress.org Marketplace."""
import json
import logging
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WordPressMarketplace:
    """Verwaltet WordPress-Plugins und Themes aus dem Marketplace."""

    # WordPress.org API URLs
    PLUGIN_API = "https://api.wordpress.org/plugins/info/1.0/"
    THEME_API = "https://api.wordpress.org/themes/info/1.2/"

    @staticmethod
    def search_plugins(query: str, limit: int = 10) -> list[dict]:
        """Sucht Plugins auf WordPress.org Marketplace."""
        try:
            url = f"{WordPressMarketplace.PLUGIN_API}?action=query_plugins&search={query}&per_page={limit}"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read())
                plugins = []
                if data.get("plugins"):
                    for plugin in data["plugins"][:limit]:
                        plugins.append({
                            "slug": plugin.get("slug"),
                            "name": plugin.get("name"),
                            "version": plugin.get("version"),
                            "description": plugin.get("short_description", "").strip()[:100],
                            "rating": plugin.get("rating", 0),
                            "active_installs": plugin.get("active_installs", 0),
                        })
                return plugins
        except Exception as e:
            logger.error(f"Fehler beim Plugin-Suchen: {e}")
            return []

    @staticmethod
    def search_themes(query: str, limit: int = 10) -> list[dict]:
        """Sucht Themes auf WordPress.org Marketplace."""
        try:
            url = f"{WordPressMarketplace.THEME_API}?action=query_themes&search={query}&per_page={limit}"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read())
                themes = []
                if data.get("themes"):
                    for theme in data["themes"][:limit]:
                        themes.append({
                            "slug": theme.get("slug"),
                            "name": theme.get("name"),
                            "version": theme.get("version"),
                            "description": theme.get("description", "").strip()[:100],
                            "rating": theme.get("rating", 0),
                            "active_installs": theme.get("active_installs", 0),
                        })
                return themes
        except Exception as e:
            logger.error(f"Fehler beim Theme-Suchen: {e}")
            return []

    @staticmethod
    def install_plugin(site_dir: Path, plugin_slug: str, activate: bool = True) -> bool:
        """Installiert ein Plugin auf einer WordPress-Site."""
        try:
            logger.info(f"Installiere Plugin '{plugin_slug}'...")

            # Install
            result = subprocess.run(
                ["wp", "plugin", "install", plugin_slug, "--activate" if activate else ""],
                cwd=site_dir,
                capture_output=True,
                timeout=120
            )

            if result.returncode == 0:
                logger.info(f"Plugin '{plugin_slug}' erfolgreich installiert")
                return True
            else:
                logger.error(f"Fehler beim Installieren: {result.stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Fehler beim Plugin-Install: {e}")
            return False

    @staticmethod
    def install_theme(site_dir: Path, theme_slug: str, activate: bool = False) -> bool:
        """Installiert ein Theme auf einer WordPress-Site."""
        try:
            logger.info(f"Installiere Theme '{theme_slug}'...")

            # Install
            result = subprocess.run(
                ["wp", "theme", "install", theme_slug],
                cwd=site_dir,
                capture_output=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"Fehler beim Installieren: {result.stderr.decode()}")
                return False

            # Activate wenn gewünscht
            if activate:
                activate_result = subprocess.run(
                    ["wp", "theme", "activate", theme_slug],
                    cwd=site_dir,
                    capture_output=True,
                    timeout=30
                )
                if activate_result.returncode != 0:
                    logger.warning(f"Theme installiert aber nicht aktiviert: {activate_result.stderr.decode()}")

            logger.info(f"Theme '{theme_slug}' erfolgreich installiert")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Theme-Install: {e}")
            return False

    @staticmethod
    def list_installed_plugins(site_dir: Path) -> list[dict]:
        """Listet installierte Plugins einer Site."""
        try:
            result = subprocess.run(
                ["wp", "plugin", "list", "--format=json"],
                cwd=site_dir,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                plugins = json.loads(result.stdout)
                return plugins
            else:
                logger.warning(f"Fehler beim Auflisten: {result.stderr.decode()}")
                return []

        except Exception as e:
            logger.error(f"Fehler beim Plugin-List: {e}")
            return []

    @staticmethod
    def list_installed_themes(site_dir: Path) -> list[dict]:
        """Listet installierte Themes einer Site."""
        try:
            result = subprocess.run(
                ["wp", "theme", "list", "--format=json"],
                cwd=site_dir,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                themes = json.loads(result.stdout)
                return themes
            else:
                logger.warning(f"Fehler beim Auflisten: {result.stderr.decode()}")
                return []

        except Exception as e:
            logger.error(f"Fehler beim Theme-List: {e}")
            return []

    @staticmethod
    def uninstall_plugin(site_dir: Path, plugin_slug: str) -> bool:
        """Deaktiviert und löscht ein Plugin."""
        try:
            logger.info(f"Deinstalliere Plugin '{plugin_slug}'...")

            result = subprocess.run(
                ["wp", "plugin", "delete", plugin_slug],
                cwd=site_dir,
                capture_output=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"Plugin '{plugin_slug}' gelöscht")
                return True
            else:
                logger.error(f"Fehler beim Löschen: {result.stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Fehler beim Plugin-Delete: {e}")
            return False

    @staticmethod
    def update_all_plugins(site_dir: Path) -> bool:
        """Updated alle Plugins einer Site."""
        try:
            logger.info("Update alle Plugins...")

            result = subprocess.run(
                ["wp", "plugin", "update", "--all"],
                cwd=site_dir,
                capture_output=True,
                timeout=300
            )

            if result.returncode == 0:
                logger.info("Alle Plugins aktualisiert")
                return True
            else:
                logger.warning(f"Fehler beim Update: {result.stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Fehler beim Plugin-Update: {e}")
            return False
