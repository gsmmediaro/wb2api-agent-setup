#!/usr/bin/env bash
# Start the gateway and wait until the panel answers.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "no .env found, copying .env.example" >&2
  cp .env.example .env
fi

PORT=$(grep -E '^WB2API_PORT=' .env | cut -d= -f2)
PORT=${PORT:-8788}

echo "starting wb-proxy"
docker compose up -d

printf 'waiting for the panel on 127.0.0.1:%s' "$PORT"
for i in $(seq 1 40); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/"; then
    printf '\nready: http://127.0.0.1:%s/  (API: http://127.0.0.1:%s/v1)\n' "$PORT" "$PORT"
    exit 0
  fi
  printf '.'
  sleep 3
done

printf '\nthe panel did not answer in 120 seconds\n' >&2
docker compose logs --tail 40 >&2
exit 1
