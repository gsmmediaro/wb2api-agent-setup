# Instructions for an agent

You are installing WorkBuddy2API-Hub on a Linux host. Follow the steps in order.
Run every verification. Do not skip a gate. If a gate fails, stop and report the
exact command and output.

## Rules

1. Never print, echo, log or commit an API key, an account token, or a refresh token.
   To show that a secret exists, print its length or the first 4 characters.
2. Never bind the gateway to `0.0.0.0` on a host with a public interface.
3. Ask the human to do the OAuth login. It needs their browser and their account.
4. Keep `accounts/`, `usage/` and `.env` out of git.
5. Report each step as done or blocked. Do not invent progress.

## Preconditions

Confirm these before step 1. Report anything missing.

```sh
uname -srm
id -u
command -v docker || echo no-docker
command -v tailscale || echo no-tailscale
curl -fsS -o /dev/null -w '%{http_code}\n' https://ghcr.io/v2/ || echo no-egress
```

## Steps

### Step 1: install Docker

```sh
sudo bash scripts/install-host.sh
```

Gate: `docker compose version` prints a version.

### Step 2: start the gateway

```sh
cp -n .env.example .env
./scripts/up.sh
```

Gate: `up.sh` prints `ready:`. If it times out, run
`docker compose logs --tail 60` and report the last 20 lines.

### Step 3: hand OAuth to the human

Print this and wait:

```
Run on your laptop:  ssh -N -L 8788:127.0.0.1:8788 <user>@<host>
Open:                http://127.0.0.1:8788/
Panel password:      admin (change it immediately)
Add each account with the OAuth button. Tell me when the pool is non-empty.
```

Gate after they confirm:

```sh
./scripts/health.sh --pool
```

Expect at least one account with `ok`.

### Step 4: confirm the key exists without revealing it

```sh
./scripts/api-key.sh | wc -c
./scripts/api-key.sh --list
```

Gate: the length is above 20, and `--list` shows one enabled key. Never print
the key itself into the transcript.

### Step 5: verify inference

```sh
./scripts/health.sh --chat
```

Gate: `chat: ok -> ok`.

### Step 6: expose on the tailnet

```sh
sudo bash scripts/tailnet-expose.sh
ss -ltnp | grep 8788
```

Gate: two listeners, `127.0.0.1` and one tailnet address. No `0.0.0.0`.

### Step 7: wire the client

On the human's laptop, not the server:

```sh
python3 scripts/wire-pi-models.py \
  --base-url http://<tailnet-ip>:8788/v1 \
  --key-file ~/.config/wb2api/key \
  --pins se,pl
```

Gate: the script prints the backup path and the provider names. Then run
`pi -p --model wb2api/<model> "reply with exactly: vm-ok"` and expect `vm-ok`.

## Failure handling

| Symptom | Cause | Fix |
| --- | --- | --- |
| panel does not answer | container down | `docker compose logs --tail 60` |
| 401 on `/v1/models` | wrong key | `./scripts/api-key.sh --list`, rewrite the client key |
| 403 code 11140 | upstream account restricted | disable that account in the panel |
| 429 on every request | all accounts cooling | wait for the reset in `usage/limit-events.jsonl` |
| `no matching enabled key` | key deleted or disabled | create a key in the panel |
| tailnet listener missing | tailscale not up | `tailscale up`, then rerun step 6 |

## What not to do

- Do not run `docker compose down -v`. The volumes hold the accounts.
- Do not copy `accounts/` to another host. Two hosts refreshing one refresh token
  break each other.
- Do not add a public reverse proxy without authentication in front.
- Do not paste the panel URL with `?pwd=` into a chat or a ticket.
