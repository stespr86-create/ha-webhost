"""WordPress-Installationen validieren und testen."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_multiple_sites_isolation(site_dirs: list[Path]) -> dict:
    """Prüft ob mehrere WordPress-Sites isoliert sind (unterschiedliche DBs, configs, etc.)."""
    results = {
        "total_sites": len(site_dirs),
        "isolated": True,
        "issues": [],
        "details": []
    }

    db_names_seen = set()
    config_hashes = {}

    for site_dir in site_dirs:
        site_name = site_dir.name
        config_file = site_dir / "wp-config.php"

        if not config_file.exists():
            results["issues"].append(f"Fehler: {site_name} hat keine wp-config.php")
            results["isolated"] = False
            continue

        try:
            config_content = config_file.read_text()

            # Parse DB name aus wp-config
            import re
            db_match = re.search(r"define\(\s*'DB_NAME'\s*,\s*'([^']+)'", config_content)
            if db_match:
                db_name = db_match.group(1)

                # Prüfe auf Duplikate
                if db_name in db_names_seen:
                    results["issues"].append(f"{site_name} nutzt selbe DB wie andere Site: {db_name}")
                    results["isolated"] = False
                else:
                    db_names_seen.add(db_name)

            # Hash config für Vergleich
            config_hash = hash(config_content)
            if config_hash in config_hashes:
                results["issues"].append(f"{site_name} hat identische config wie {config_hashes[config_hash]}")
                results["isolated"] = False
            else:
                config_hashes[config_hash] = site_name

            # Check wp-config.php ist unique
            wp_settings = site_dir / "wp-settings.php"
            if wp_settings.exists():
                results["details"].append(f"✓ {site_name}: wp-settings.php gefunden")
            else:
                results["issues"].append(f"{site_name}: wp-settings.php fehlt")

        except Exception as e:
            results["issues"].append(f"Fehler beim Prüfen von {site_name}: {e}")
            results["isolated"] = False

    logger.info(f"Isolation-Check: {results['total_sites']} Sites, isolated={results['isolated']}")
    return results
