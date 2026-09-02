#!/usr/bin/with-contenv bashio

mkdir -p /data/sites

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

	handle {
		reverse_proxy 127.0.0.1:8001
	}
}
EOF
fi
