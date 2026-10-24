#!/usr/bin/env python3
"""Write pi providers for a wb2api gateway into ~/.pi/agent/models.json.

    python3 scripts/wire-pi-models.py --base-url http://100.x.y.z:8788/v1 --api-key sk-...
    python3 scripts/wire-pi-models.py --base-url ... --key-file ~/.config/wb2api/key --pins se,pl

Each pin becomes its own provider with an X-Session-Id header. The gateway uses
that header to keep a conversation on one upstream account, so parallel agents
spread across accounts instead of fighting for the same one.

The script keeps a timestamped backup and leaves every other provider alone.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

DEFAULT_MODELS = Path.home() / ".pi" / "agent" / "models.json"

THINKING = {
    "off": None,
    "minimal": None,
    "low": "low",
    "medium": "low",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}


def provider_entry(name: str, base_url: str, api_key: str, model: str, pin: str | None) -> dict:
    entry = {
        "name": f"wb2api [{name}]" if pin else "wb2api",
        "baseUrl": base_url,
        "api": "openai-completions",
        "apiKey": api_key,
        "compat": {"supportsDeveloperRole": False},
        "models": [
            {
                "id": model,
                "reasoning": True,
                "thinkingLevelMap": THINKING,
            }
        ],
    }
    if pin:
        entry["headers"] = {"X-Session-Id": pin}
    return entry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="gateway base URL, ends in /v1")
    ap.add_argument("--api-key", default="", help="API key, prefer --key-file")
    ap.add_argument("--key-file", default=str(Path.home() / ".config/wb2api/key"))
    ap.add_argument("--model", default="deepseek-v4.1-flash")
    ap.add_argument("--pins", default="", help="comma list of pin names, for example se,pl,gs")
    ap.add_argument("--config", default=str(DEFAULT_MODELS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = args.api_key.strip()
    if not key:
        try:
            key = Path(args.key_file).read_text().strip()
        except OSError:
            raise SystemExit(f"no --api-key and cannot read {args.key_file}")
    if not key:
        raise SystemExit("empty API key")

    config = Path(args.config)
    state = {"providers": {}}
    if config.exists():
        state = json.loads(config.read_text())

    providers = state.setdefault("providers", {})
    providers["wb2api"] = provider_entry("hub", args.base_url, key, args.model, None)

    for pin in [p.strip() for p in args.pins.split(",") if p.strip()]:
        providers[f"wb2api-{pin}"] = provider_entry(pin, args.base_url, key, args.model, f"pin-{pin}")

    if args.dry_run:
        print(json.dumps({k: providers[k] for k in providers if k.startswith("wb2api")}, indent=2))
        return

    config.parent.mkdir(parents=True, exist_ok=True)
    if config.exists():
        backup = config.with_suffix(f".json.bak-wb2api-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(config, backup)
        print(f"backup: {backup}")

    config.write_text(json.dumps(state, indent=2) + "\n")
    added = [k for k in providers if k.startswith("wb2api")]
    print(f"wrote {config}")
    print("providers:", ", ".join(sorted(added)))


if __name__ == "__main__":
    main()
