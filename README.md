# wb2api on a headless host

Run [WorkBuddy2API-Hub](https://github.com/ardeyouxipianyi/workbuddy2api-hub) on a
Linux server, keep it off the public internet, and point coding agents at it.

This repo holds the operations layer only: install, keys, private exposure,
client wiring, health checks. The upstream project holds the gateway itself.

No credentials live here. Accounts, keys and usage data stay on your host in
`accounts/` and `usage/`, both gitignored.

## What you get

- An OpenAI-compatible endpoint on `127.0.0.1:8788/v1` on your server.
- The panel on `127.0.0.1:8788/` for account OAuth and key management.
- A tailnet-only listener, so laptops reach the gateway without a public port.
- A localhost shim, so every tool already pointed at `127.0.0.1:8788` keeps working.
- A pi models writer, so agents pick up the gateway with one command.

## Requirements

- A Linux host you can SSH into (Ubuntu 22.04+ tested, any distro with Docker works).
- Docker with the compose plugin, or root to install it.
- Optional: Tailscale on the host and on your laptop.
- Optional: an SSH client that can forward ports.

## Steps

Each step is one command. Run them on the server unless the step says laptop.

### 1. Install Docker

```sh
sudo bash scripts/install-host.sh
```

### 2. Start the gateway

```sh
cp .env.example .env
./scripts/up.sh
```

`up.sh` starts the container, waits for the panel, and prints the panel URL. On
first start the gateway generates an API key and writes it to
`accounts/settings.json`.

### 3. Add accounts

Account OAuth needs a browser. On the laptop:

```sh
ssh -N -L 8788:127.0.0.1:8788 <user>@<host>
```

Then open `http://127.0.0.1:8788/` on the laptop. Log in with the panel password
(default `admin`, change it at once), click add account, and finish the OAuth
flow. The token lands in `accounts/` on the server. Repeat for each account.

Verify the pool:

```sh
./scripts/health.sh
```

### 4. Read the API key

```sh
./scripts/api-key.sh
```

The script prints the key that the gateway stores in `accounts/settings.json`.
Treat it as a secret. Do not paste it into a repo, a chat, or a ticket.

### 5. Verify the API

```sh
./scripts/health.sh --chat
```

This sends one tiny completion and prints the answer, the account used, and the
latency. A 401 means the key is wrong. A 502 means the container is down. A 429
or 403 means the upstream account is cooling down or restricted.

### 6. Expose it on the tailnet only

```sh
sudo bash scripts/tailnet-expose.sh
```

The script installs two systemd units and binds `8788` to the Tailscale address
only. Nothing listens on a public interface. Check with:

```sh
ss -ltnp | grep 8788
```

You should see `127.0.0.1:8788` and one tailnet address. No `0.0.0.0`.

### 7. Point pi at it

On the laptop:

```sh
python3 scripts/wire-pi-models.py --base-url http://<tailnet-ip>:8788/v1 --api-key "$(cat ~/.config/wb2api/key)"
```

The script adds `wb2api` and one pinned variant per account group to
`~/.pi/agent/models.json`, keeping a backup first. Restart pi, then pick the
model with `/model`.

If the gateway is on the same machine, skip the tailnet hop and use
`http://127.0.0.1:8788/v1`.

### 8. Keep it running

```sh
systemctl status wb2api-tailnet
docker compose logs -f --tail 50
```

`restart: unless-stopped` in the compose file handles crashes and reboots.

## How the pieces fit

```
agent or tool
  -> 127.0.0.1:8788 (shim, adds the key)        optional, laptop only
  -> <tailnet-ip>:8788 (socat, tailnet only)
  -> 127.0.0.1:8788 (gateway, panel + API)
  -> upstream accounts in accounts/
```

The shim exists because most tools send a placeholder key or none. It rewrites
`Authorization` and `?key=` in flight and passes everything else through.

## Security rules

- Bind to loopback or the tailnet. Never to `0.0.0.0` on a public host.
- Change the panel password before you add the first account.
- Keep `accounts/`, `usage/` and `.env` out of git. The `.gitignore` does this.
- Rotate the API key if it ever leaves the host.
- One key per client, so usage stays attributable and revocation stays cheap.

## Files

| Path | Purpose |
| --- | --- |
| `docker-compose.yml` | gateway service, volumes, restart policy |
| `.env.example` | port, timezone, user mapping, optional fixed key |
| `scripts/install-host.sh` | Docker and compose plugin on Debian or Ubuntu |
| `scripts/up.sh` | start, wait for the panel, print the URL |
| `scripts/api-key.sh` | read the key from the gateway state |
| `scripts/health.sh` | pool check, optional live completion |
| `scripts/tailnet-expose.sh` | tailnet-only listeners as systemd units |
| `scripts/wb2api-shim.py` | localhost to remote gateway, injects the key |
| `scripts/wire-pi-models.py` | write pi providers for the gateway |
| `deploy/*.service` | unit files the scripts install |
| `docs/pi.md` | pi model wiring and pinned providers |
| `docs/troubleshooting.md` | the failures you will actually hit |
| `AGENTS.md` | instructions written for an agent, not a human |

## Credit and licence

The gateway is [WorkBuddy2API-Hub](https://github.com/ardeyouxipianyi/workbuddy2api-hub),
MIT, by ardeyouxipianyi. This repo is MIT too. It ships no gateway code.
