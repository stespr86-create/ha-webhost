ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
        python3 \
        py3-pip \
        caddy \
        git \
        jpeg \
        zlib \
        mariadb \
        mariadb-client \
        php82 \
        php82-fpm \
        php82-mysqli \
        php82-gd \
        php82-curl \
        php82-json \
        curl

# WordPress CLI installieren
RUN curl -o /usr/local/bin/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && \
    chmod +x /usr/local/bin/wp

# PHP-FPM auf pro-Site-Pools umstellen statt eines einzelnen geteilten
# Pools: Standard-Pool (www.conf) entfernen, Pool-Configs stattdessen aus
# /data laden (dynamisch von services/php_fpm_service.py erzeugt/verwaltet,
# analog zur Caddyfile - siehe core/config.py PHP_FPM_POOL_DIR) und eine
# feste PID-Datei setzen, damit die App per SIGUSR2 einen Reload ausloesen
# kann, ohne laufende Requests abzubrechen.
RUN rm -f /etc/php82/php-fpm.d/www.conf \
    && sed -i '/^pid = /d' /etc/php82/php-fpm.conf \
    && sed -i 's#^include=.*#include=/data/php-fpm-pools/*.conf#' /etc/php82/php-fpm.conf \
    && echo 'pid = /run/php-fpm.pid' >> /etc/php82/php-fpm.conf

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
# jpeg-dev/zlib-dev/build-base nur fuer den Pillow-Build gebraucht (falls fuer
# die Ziel-Architektur kein fertiges Wheel existiert) - direkt danach wieder
# entfernt, die Laufzeit-Libs (jpeg/zlib oben) bleiben erhalten.
RUN apk add --no-cache --virtual .build-deps \
        build-base \
        python3-dev \
        jpeg-dev \
        zlib-dev \
    && pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt \
    && apk del .build-deps

COPY app /app
COPY rootfs /

RUN chmod -R a+x /etc/services.d /etc/cont-init.d

WORKDIR /app
