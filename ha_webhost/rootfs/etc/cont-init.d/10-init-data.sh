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

	# Home Assistant Ingress haengt teils einen doppelten Trailing-Slash an
	# die Basis-URL an (z.B. ".../<token>//"). Auf einfaches "/" reduzieren,
	# bevor geroutet wird.
	uri replace // / 1

	handle {
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
