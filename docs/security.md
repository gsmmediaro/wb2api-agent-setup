# Security notes

## What this setup protects

- The gateway never listens on a public interface. Loopback and the tailnet only.
- The panel needs a password. Account tokens live on the server, not on laptops.
- Clients reach the gateway over WireGuard, so a stolen laptop does not expose it.

## What it does not protect

- The upstream provider sees every prompt. Do not send secrets through it.
- Anyone with the API key can spend the accounts' quota. Treat the key like a
  password and give each client its own.
- The panel password is stored as a PBKDF2-SHA256 hash. The API keys are stored
  in clear text in `accounts/settings.json`, because the gateway must send them
  upstream. Protect the file with permissions and disk encryption.

## Key handling

```sh
mkdir -p ~/.config/wb2api
chmod 700 ~/.config/wb2api
./scripts/api-key.sh > ~/.config/wb2api/key
chmod 600 ~/.config/wb2api/key
```

Read the key from that file, never from a chat log or a shell history entry. To
keep it out of history, use a leading space with `HISTCONTROL=ignorespace`, or
read it into a variable in the same command that uses it.

## Accounts

One host owns the accounts. Copying `accounts/` to a second host makes two
processes refresh the same refresh token, and the upstream invalidates both.
To move hosts, stop the first, copy, then start the second.

Disable an account in the panel instead of deleting it, so its usage history
stays readable.

## Exposure checklist

- [ ] `ss -ltnp | grep 8788` shows loopback and the tailnet only
- [ ] panel password changed from the default
- [ ] one API key per client, named
- [ ] `accounts/`, `usage/`, `.env` gitignored and unreadable by other users
- [ ] no `?pwd=` panel URL in history, tickets or chat
- [ ] tailnet ACL limits who can reach port 8788

## Incident response

If a key leaks:

```sh
# in the panel: disable the key, then create a new one
./scripts/api-key.sh --list
```

If an account leaks, remove it upstream as well. Disabling it in the panel stops
local use but the refresh token stays valid upstream until it is revoked.
