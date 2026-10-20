#!/bin/bash
# Read-only host checks. Do not print environment files or application secrets.
set -Eeuo pipefail
cloud-init status
test -f /srv/echomind/bootstrap-ready
mountpoint -q /srv/echomind
mountpoint -q /etc/echomind
findmnt --target /srv/echomind --output TARGET,SOURCE,FSTYPE,OPTIONS
findmnt --target /etc/echomind --output TARGET,SOURCE,FSTYPE,OPTIONS
test "$(stat -c '%U:%G:%a' /etc/echomind)" = root:root:700
test "$(stat -c '%U:%G:%a' /srv/echomind/private)" = root:root:700
systemctl is-active docker containerd snap.amazon-ssm-agent.amazon-ssm-agent.service
test "$(docker info --format '{{.DockerRootDir}}')" = /srv/echomind/docker
grep -qx 'root = "/srv/echomind/containerd"' /etc/containerd/config.toml
docker version --format 'Docker server {{.Server.Version}}'
COMPOSE_VERSION=$(docker compose version --short | sed 's/^v//')
dpkg --compare-versions "$COMPOSE_VERSION" ge 2.30.0
printf 'Compose %s\n' "$COMPOSE_VERSION"
aws --version
aws --version 2>&1 | grep -q '^aws-cli/2.38.0 '
SSM_VERSION=$(/snap/amazon-ssm-agent/current/amazon-ssm-agent -version | awk '{print $NF}')
dpkg --compare-versions "$SSM_VERSION" ge 3.3.2746.0
printf 'SSM Agent %s\n' "$SSM_VERSION"
systemctl is-enabled docker containerd snap.amazon-ssm-agent.amazon-ssm-agent.service
df -h / /srv/echomind
printf 'Host bootstrap and durable storage checks passed.\n'
