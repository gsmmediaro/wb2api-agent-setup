# Wiring pi to the gateway

pi reads providers from `~/.pi/agent/models.json`. Each provider needs a base
URL, an API dialect, a key, and a model list.

## One command

```sh
python3 scripts/wire-pi-models.py \
  --base-url http://<host>:8788/v1 \
  --key-file ~/.config/wb2api/key
```

Then pick the model in pi with `/model`, or pin it for one run:

```sh
pi --model wb2api/deepseek-v4.1-flash -p "reply with exactly: ok"
```

## The entry it writes

```json
{
  "wb2api": {
    "name": "wb2api",
    "baseUrl": "http://<host>:8788/v1",
    "api": "openai-completions",
    "apiKey": "<key>",
    "compat": { "supportsDeveloperRole": false },
    "models": [
      {
        "id": "deepseek-v4.1-flash",
        "reasoning": true,
        "thinkingLevelMap": {
          "off": null, "minimal": null,
          "low": "low", "medium": "low",
          "high": "high", "xhigh": "max", "max": "max"
        }
      }
    ]
  }
}
```

`supportsDeveloperRole: false` matters. The upstream rejects the `developer`
role, so pi must send `system` instead.

The `thinkingLevelMap` exists because upstream exposes only `low`, `high` and
`max`. Mapping `medium` to `low` keeps a medium request from silently becoming
the expensive default.

## Pinned providers

Run several agents at once and they all hammer the same upstream account. The
gateway reads `X-Session-Id` and keeps that conversation on one account, so
distinct pins spread the load.

```sh
python3 scripts/wire-pi-models.py --base-url ... --pins se,pl,gs
```

This adds `wb2api-se`, `wb2api-pl`, `wb2api-gs`, each with its own header. Use
one pin per long-running agent.

## Choosing the effort level

| pi flag | upstream effort | use for |
| --- | --- | --- |
| `--thinking low` | low | mechanical edits, greps, probes |
| `--thinking medium` | low | default for workers |
| `--thinking high` | high | debugging, design |
| `--thinking xhigh` | max | rare, expensive |

Do not set `xhigh` as a default anywhere.

## When the key lives on another machine

Most tools accept a placeholder key and the shim fixes it in flight:

```sh
WB2API_UPSTREAM_HOST=<host> WB2API_KEY_FILE=~/.config/wb2api/key \
  python3 scripts/wb2api-shim.py
```

Now `http://127.0.0.1:8788/v1` works everywhere, with any key, because the shim
replaces it before the request leaves the machine.

## Context window

Long agent sessions grow until they compact. The gateway reports usage, so check
`usage/` or the panel when a run looks slow. A 150k token prompt still completes,
it just costs upstream quota.
