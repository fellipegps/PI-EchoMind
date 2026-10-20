# Official Caddy release, pinned deliberately for repeatable builds.
FROM caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f

RUN addgroup -g 10001 echomind \
    && adduser -D -u 10001 -G echomind echomind \
    && setcap -r /usr/bin/caddy \
    && mkdir -p /data /config \
    && chown -R 10001:10001 /data /config
COPY Caddyfile /etc/caddy/Caddyfile
USER 10001:10001
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
