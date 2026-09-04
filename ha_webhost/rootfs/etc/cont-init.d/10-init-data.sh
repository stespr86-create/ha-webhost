#!/usr/bin/with-contenv bashio

mkdir -p /data/sites
mkdir -p /data/mariadb
mkdir -p /data/php-fpm-pools
mkdir -p /run/php-fpm

# MariaDB beim ersten Start initialisieren
if [ ! -f /data/mariadb/initialized ]; then
    bashio::log.info "Initialisiere MariaDB zum ersten Mal..."
    mysql_install_db --user=root --datadir=/data/mariadb --skip-test-db >/dev/null 2>&1
    touch /data/mariadb/initialized
    bashio::log.info "MariaDB-Verzeichnis erstellt."
fi

if [ ! -f /data/Caddyfile ]; then
    bashio::log.info "Erzeuge initiale Caddyfile..."
    cat > /data/Caddyfile <<'EOF'
{
	admin 127.0.0.1:2019
	auto_https off
}

:8000 {
	log {
		output stdout
	}

	# Home Assistant Ingress haengt teils einen doppelten Trailing-Slash an
	# die Basis-URL an (z.B. ".../<token>//"). Auf einfaches "/" reduzieren,
	# bevor geroutet wird.
	uri replace // / 1

	# Nur ein kurzzeitiger Platzhalter bis die App startet und ueber
	# services/caddy_service.py die echte, aus der DB generierte Caddyfile
	# schreibt (inkl. php_fastcgi-Routing fuer PHP-Sites) - siehe dort.
	route {
		reverse_proxy 127.0.0.1:8001
	}
}

:8090 {
	log {
		output stdout
	}

	handle {
		respond 404
	}
}
EOF
fi
