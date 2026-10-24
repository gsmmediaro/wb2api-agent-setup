#!/usr/bin/env python3
"""Localhost shim: 127.0.0.1:8788 -> a remote wb2api gateway, with the key added.

Why this exists: most clients send a placeholder key, or none at all. This shim
rewrites the Authorization header and any ?key= value in flight, then pipes the
rest through untouched. Point every existing tool at the same localhost URL and
change no config.

Environment:
  WB2API_UPSTREAM_HOST  gateway host or tailnet address (default 127.0.0.1)
  WB2API_UPSTREAM_PORT  gateway port (default 8788)
  WB2API_LOCAL_PORT     local listen port (default 8788)
  WB2API_KEY_FILE       file holding the key (default ~/.config/wb2api/key)
  WB2API_API_KEY        key inline, wins over the file

The key file should be 0600. With no key the shim passes requests through
unauthenticated, which only works against a gateway that allows that.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(os.environ.get("WB2API_LOCAL_PORT", "8788"))
UPSTREAM_HOST = os.environ.get("WB2API_UPSTREAM_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.environ.get("WB2API_UPSTREAM_PORT", "8788"))
KEY_PATH = Path(os.environ.get("WB2API_KEY_FILE", Path.home() / ".config/wb2api/key"))

PLACEHOLDERS = {
    b"not-needed", b"none", b"null", b"dummy", b"x", b"changeme",
    b"placeholder", b"your-key", b"sk-xxx", b"",
}


def load_key() -> str:
    inline = os.environ.get("WB2API_API_KEY", "").strip()
    if inline:
        return inline
    try:
        return KEY_PATH.read_text().strip()
    except OSError:
        return ""


def ensure_auth(head: bytes, key: str) -> bytes:
    """Make the request carry the real key.

    - no Authorization header -> add one
    - Authorization with a placeholder token -> replace it
    - ?key=<wrong> -> replace it, matching the parameter name exactly
    A key that already matches passes through untouched.

    Also forces Connection: close. This shim rewrites one request head and then
    relays the raw stream, so a second request on a reused keep-alive
    connection would go out with the client's placeholder key and 401. Closing
    after each response costs one TCP handshake per request and keeps every
    request on the rewrite path.
    """
    lines = head.split(b"\r\n")

    parts = lines[0].split(b" ")
    if len(parts) >= 2 and b"?" in parts[1]:
        base, _, query = parts[1].partition(b"?")
        params = query.split(b"&")
        changed = False
        for i, param in enumerate(params):
            name, sep, value = param.partition(b"=")
            # "monkey=" and "apikey=" contain "key=" but are not the key param.
            if not sep or name != b"key":
                continue
            if value.lower() in PLACEHOLDERS or value.decode(errors="replace") != key:
                params[i] = name + b"=" + key.encode()
                changed = True
        if changed:
            parts[1] = base + b"?" + b"&".join(params)
            lines[0] = b" ".join(parts)

    replaced = False
    for i, line in enumerate(lines):
        if line.lower().startswith(b"authorization:"):
            value = line.split(b":", 1)[1].strip()
            token = value[7:] if value.lower().startswith(b"bearer ") else value
            if token.lower() in PLACEHOLDERS or token.decode(errors="replace") != key:
                lines[i] = f"Authorization: Bearer {key}".encode()
            replaced = True
            break
    if not replaced:
        lines.insert(1, f"Authorization: Bearer {key}".encode())

    lines = [ln for ln in lines if not ln.lower().startswith(b"connection:")]
    lines.insert(1, b"Connection: close")
    return b"\r\n".join(lines)


async def pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        head = await client_reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, ConnectionResetError, asyncio.LimitOverrunError):
        client_writer.close()
        return

    key = load_key()
    if key:
        head = ensure_auth(head, key)

    try:
        up_reader, up_writer = await asyncio.open_connection(UPSTREAM_HOST, UPSTREAM_PORT)
    except OSError as exc:
        client_writer.write(
            b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain\r\n\r\n"
            + f"shim cannot reach {UPSTREAM_HOST}:{UPSTREAM_PORT}: {exc}\n".encode()
        )
        await client_writer.drain()
        client_writer.close()
        return

    up_writer.write(head)
    await up_writer.drain()
    await asyncio.gather(
        pump(client_reader, up_writer),
        pump(up_reader, client_writer),
    )


async def main() -> None:
    server = await asyncio.start_server(handle, LISTEN_HOST, LISTEN_PORT, backlog=128)
    state = "key loaded" if load_key() else "NO KEY, requests pass through unauthenticated"
    print(f"shim {LISTEN_HOST}:{LISTEN_PORT} -> {UPSTREAM_HOST}:{UPSTREAM_PORT} ({state})")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
