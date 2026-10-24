#!/usr/bin/env bash
# Check the gateway: panel, model list, account pool, optional live completion.
#
#   ./scripts/health.sh              # panel + /v1/models
#   ./scripts/health.sh --chat       # also send one tiny completion
#   ./scripts/health.sh --pool       # account pool summary
#
# The key comes from WB2API_KEY, or from accounts/settings.json on this host.
set -euo pipefail

cd "$(dirname "$0")/.."

PORT=${WB2API_PORT:-8788}
BASE=${WB2API_BASE:-http://127.0.0.1:$PORT}
MODEL=${WB2API_MODEL:-deepseek-v4.1-flash}

key=${WB2API_KEY:-}
if [ -z "$key" ] && [ -f accounts/settings.json ]; then
  key=$(python3 - <<'PY'
import json
try:
    state = json.load(open("accounts/settings.json"))
except Exception:
    raise SystemExit(0)
for entry in state.get("api_keys") or []:
    if entry.get("enabled") and not entry.get("deleted_at"):
        print(entry.get("key", ""))
        break
PY
)
fi

if [ -z "$key" ]; then
  echo "no API key found, set WB2API_KEY or start the gateway once" >&2
  exit 1
fi

echo "base: $BASE"

if curl -fsS -o /dev/null --max-time 5 "$BASE/"; then
  echo "panel: ok"
else
  echo "panel: FAIL" >&2
  exit 1
fi

if curl -fsS --max-time 15 -H "Authorization: Bearer $key" "$BASE/v1/models" \
   | python3 -c 'import json,sys; d=json.load(sys.stdin); print("models:", len(d.get("data", [])), "->", ", ".join(m["id"] for m in d.get("data", [])[:6]))'; then
  :
else
  echo "models: FAIL (401 means a bad key, 502 means the gateway is down)" >&2
  exit 1
fi

if [ "${1:-}" = "--pool" ] && [ -f accounts/settings.json ]; then
  python3 - <<'PY'
import json, glob, time
accs = []
for f in glob.glob("accounts/*.json"):
    if f.endswith("settings.json"):
        continue
    try:
        accs.append(json.load(open(f)))
    except Exception:
        pass
usable = [a for a in accs if a.get("enabled", True)]
print("accounts: %d total, %d enabled" % (len(accs), len(usable)))
now = time.time() * 1000
for a in usable:
    exp = a.get("expiresAt") or 0
    state = "expired" if exp and exp < now else "ok"
    print("  %-10s %-6s %s" % ((a.get("nickname") or a.get("uid", "?")[:8])[:10], a.get("realm") or "-", state))
PY
fi

if [ "${1:-}" = "--chat" ]; then
  echo "chat: sending one completion"
  curl -fsS --max-time 120 "$BASE/v1/chat/completions" \
    -H "Authorization: Bearer $key" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"reply with exactly: ok\"}],\"max_tokens\":16}" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print("chat: ok ->", d["choices"][0]["message"]["content"].strip()[:60])'
fi
