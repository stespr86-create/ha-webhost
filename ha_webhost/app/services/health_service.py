import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class WordPressHealth:
    def __init__(self, site_name: str, db_name: str):
        self.site_name = site_name
        self.db_name = db_name
        self.is_healthy = True
        self.issues = []

    def check_database(self) -> bool:
        """Prüft ob die WordPress-Datenbank erreichbar ist."""
        try:
            result = subprocess.run(
                ["mysql", "-u", "root", "-e", f"SELECT 1 FROM `{self.db_name}`.`wp_options` LIMIT 1"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
            else:
                self.issues.append("Datenbank nicht erreichbar")
                return False
        except Exception as e:
            self.issues.append(f"DB-Check fehlgeschlagen: {e}")
            return False

    def check_wordpress_tables(self) -> bool:
        """Prüft ob alle WordPress-Tabellen vorhanden sind."""
        required_tables = ["wp_users", "wp_posts", "wp_options", "wp_postmeta", "wp_usermeta"]
        try:
            for table in required_tables:
                result = subprocess.run(
                    ["mysql", "-u", "root", "-e", f"SELECT 1 FROM `{self.db_name}`.`{table}` LIMIT 1"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    self.issues.append(f"Tabelle '{table}' fehlt oder ist leer")
                    return False
            return True
        except Exception as e:
            self.issues.append(f"Tabellen-Check fehlgeschlagen: {e}")
            return False

    def check_admin_user(self) -> bool:
        """Prüft ob Admin-User existiert."""
        try:
            result = subprocess.run(
                ["mysql", "-u", "root", "-e", f"SELECT ID FROM `{self.db_name}`.`wp_users` WHERE `user_login` = 'admin'"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0 and b"ID" in result.stdout:
                return True
            else:
                self.issues.append("Admin-User nicht gefunden")
                return False
        except Exception as e:
            self.issues.append(f"Admin-Check fehlgeschlagen: {e}")
            return False

    def run_all_checks(self) -> bool:
        """Führt alle Health-Checks aus."""
        self.is_healthy = True
        self.issues = []

        # Nacheinander prüfen
        if not self.check_database():
            self.is_healthy = False
        if not self.check_wordpress_tables():
            self.is_healthy = False
        if not self.check_admin_user():
            self.is_healthy = False

        return self.is_healthy

    def to_dict(self) -> dict:
        """Gibt Health-Status als Dict zurück."""
        return {
            "site": self.site_name,
            "healthy": self.is_healthy,
            "database": self.db_name,
            "issues": self.issues if not self.is_healthy else []
        }
