#!/bin/bash
# Run from the extracted, digest-verified source directory. No runtime secrets needed.
set -Eeuo pipefail
umask 077
REVISION=${1:?Require full source commit}
[[ "$REVISION" =~ ^[a-f0-9]{40}$ ]]
test "$(id -u)" = 0
test -f /srv/echomind/bootstrap-ready
mountpoint -q /srv/echomind
mountpoint -q /etc/echomind
test "$(stat -c '%U:%G:%a' /etc/echomind)" = root:root:700
install -d -m 700 /etc/echomind/build-logs
STAGE=backend
trap 'printf "Build failed at %s; inspect restricted build log on host.\n" "$STAGE" >&2' ERR
docker build --pull --tag "echomind-backend:$REVISION" ./echomind-backend \
  > "/etc/echomind/build-logs/backend-$REVISION.log" 2>&1
STAGE=proxy
docker build --pull --tag "echomind-proxy:$REVISION" ./deploy/proxy \
  > "/etc/echomind/build-logs/proxy-$REVISION.log" 2>&1
docker image inspect --format 'Built {{.Id}} ({{.Architecture}})' \
  "echomind-backend:$REVISION" "echomind-proxy:$REVISION"
printf 'First release images built from pinned base images and locked dependencies.\n'
