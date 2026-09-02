ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
        python3 \
        py3-pip \
        caddy \
        git

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY app /app
COPY rootfs /

RUN chmod -R a+x /etc/services.d /etc/cont-init.d

WORKDIR /app
