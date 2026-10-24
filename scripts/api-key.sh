#!/usr/bin/env bash
# Print an API key from the gateway state, or set one.
#
#   ./scripts/api-key.sh              # first enabled key
#   ./scripts/api-key.sh --name pi    # key by name
#   ./scripts/api-key.sh --list       # names, realms, models, never the keys
#
# Reads accounts/settings.json on the host that runs the gateway.
set -euo pipefail

cd "$(dirname "$0")/.."
SETTINGS=accounts/settings.json

if [ ! -f "$SETTINGS" ]; then
  echo "no $SETTINGS, start the gateway first (scripts/up.sh)" >&2
  exit 1
fi

python3 - "$SETTINGS" "$@" <<'PY'
import json, sys

path, args = sys.argv[1], sys.argv[2:]
state = json.load(open(path))
keys = state.get("api_keys") or []

if "--list" in args:
    for entry in keys:
        print("%-16s realm=%-4s enabled=%s models=%s" % (
            entry.get("name") or "?",
            entry.get("realm") or "-",
            entry.get("enabled"),
            entry.get("models") or "*",
        ))
    sys.exit(0)

want = None
if "--name" in args:
    want = args[args.index("--name") + 1]

live = [e for e in keys if e.get("enabled") and not e.get("deleted_at")]
if want:
    live = [e for e in live if (e.get("name") or "") == want]

if not live:
    sys.stderr.write("no matching enabled key\n")
    sys.exit(1)

print(live[0]["key"])
PY
