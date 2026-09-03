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
        nginx \
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
