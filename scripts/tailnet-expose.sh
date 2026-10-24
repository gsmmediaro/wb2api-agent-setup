#!/usr/bin/env bash
# Expose the gateway on the tailnet address only, through two systemd units.
#
#   sudo bash scripts/tailnet-expose.sh
#   sudo bash scripts/tailnet-expose.sh --remove
#
# Nothing binds a public interface. The units use socat to forward from the
# Tailscale address to the loopback listener.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo" >&2
  exit 1
fi

if [ "${1:-}" = "--remove" ]; then
  systemctl disable --now wb2api-tailnet.service 2>/dev/null || true
  rm -f /etc/systemd/system/wb2api-tailnet.service
  systemctl daemon-reload
  echo "tailnet listener removed"
  exit 0
fi

if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale is not installed, install it first" >&2
  exit 1
fi

if ! command -v socat >/dev/null 2>&1; then
  echo "installing socat"
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq socat >/dev/null
fi

TS_IP=$(tailscale ip -4 | head -1)
PORT=$(grep -E '^WB2API_PORT=' .env 2>/dev/null | cut -d= -f2)
PORT=${PORT:-8788}

if [ -z "$TS_IP" ]; then
  echo "tailscale has no IPv4 address, run 'tailscale up' first" >&2
  exit 1
fi

echo "binding $TS_IP:$PORT -> 127.0.0.1:$PORT"

sed -e "s|__TS_IP__|$TS_IP|g" -e "s|__PORT__|$PORT|g" \
  deploy/wb2api-tailnet.service > /etc/systemd/system/wb2api-tailnet.service

systemctl daemon-reload
systemctl enable --now wb2api-tailnet.service

sleep 1
ss -ltnp | grep ":$PORT" || true
echo "done. reachable at http://$TS_IP:$PORT/v1 from the tailnet"
