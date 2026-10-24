# Troubleshooting

## The panel does not answer

```sh
docker compose ps
docker compose logs --tail 60
ss -ltnp | grep 8788
```

A container that restarts in a loop is usually a permission problem on
`accounts/`. Check `ls -ld accounts` and match `PUID` and `PGID` in `.env`.

## 401 Unauthorized

The client sends a key the gateway does not know.

```sh
./scripts/api-key.sh --list
./scripts/api-key.sh | wc -c
```

A length under 20 means no key. Open the panel and create one. If the client uses
a placeholder like `not-needed`, run the shim.

## 403 with code 11140

That upstream account is restricted. The gateway skips it, but if it is the only
account, every request fails. Add another account in the panel.

## 429 on everything

All accounts are cooling down. The gateway writes each reset to
`usage/limit-events.jsonl`:

```sh
tail -3 usage/limit-events.jsonl
```

Wait for the latest `reset` value, then retry. Do not hammer: repeated 429s
extend the cooldown.

## Model not found

```sh
curl -s -H "Authorization: Bearer $KEY" http://127.0.0.1:8788/v1/models | jq -r '.data[].id'
```

The model id must match exactly, including the version suffix. The upstream
catalog moves; the list endpoint is the truth.

## Tailnet listener gone after a reboot

```sh
systemctl status wb2api-tailnet
sudo bash scripts/tailnet-expose.sh
```

The unit needs `tailscaled` up first. If the tailnet address changed, rerun the
script so the unit binds the new one.

## Everything works on the server, nothing works from the laptop

```sh
curl -sS -o /dev/null -w '%{http_code}\n' http://<tailnet-ip>:8788/v1/models
```

`000` means the network path is closed: check `tailscale status` on both ends and
the listener address. `401` means the path is fine and the key is wrong.

## Panel password forgotten

```sh
python3 - <<'PY'
import json
p = "accounts/settings.json"
d = json.load(open(p))
for k in ("panel_password_hash", "panel_password_salt", "panel_password_rounds"):
    d.pop(k, None)
json.dump(d, open(p, "w"), indent=2)
print("password cleared, next panel load sets the default")
PY
docker compose restart
```

Only do this on a host you control, and change the password straight away.

## Logs you should read first

| File | Holds |
| --- | --- |
| `docker compose logs` | requests, upstream errors, account selection |
| `usage/limit-events.jsonl` | per-account rate-limit resets |
| `usage/activity_history.jsonl` | account check-ins and daily tasks |
| `accounts/settings.json` | keys, panel password hash, no plaintext password |
