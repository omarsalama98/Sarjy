#!/usr/bin/env python3
"""Measures the exact WebSocket death time against the real deployment.

docs/plans/blocks/01-skeleton-deploy.md, Step 6. Block 0 (day1-spikes.md S1)
bracketed the failure to (5s, 160s], sampling only at those two points. This
script pings the DEPLOYED app itself -- not a throwaway probe -- every 10s
and reports last-ok / first-fail, so rotate_after_ms is a measurement Omar
can defend with a number, not a guess.

Usage:
    uv run python scripts/ws_lifetime.py wss://<host>/ws

Runs two connections concurrently (n=2, per the plan), each for up to ~6
minutes, disabling the `websockets` library's own protocol-level ping
(`ping_interval=None`) so the only traffic on the wire is this app's own
ping/pong -- the thing actually being measured, not conflated with a second,
unrelated heartbeat mechanism (S1 already showed those behave differently).

Writes nothing to disk; the two lines this prints on failure (or completion)
are the artifact -- paste them into docs/measurements/day1-spikes.md.
"""

import asyncio
import json
import ssl
import sys
import time
import uuid

import certifi
import websockets
from websockets.exceptions import ConnectionClosed

PING_INTERVAL_S = 10
PONG_DEADLINE_S = 5
MAX_RUNTIME_S = 6 * 60

# Some local Python installs (notably python.org framework builds on macOS)
# don't wire the system trust store into the stdlib ssl module by default,
# which makes asyncio's TLS handshake fail with CERTIFICATE_VERIFY_FAILED
# even though the server's certificate is fine (curl, which uses the OS
# trust store, connects to the same URL without issue). Building the
# context from certifi's bundle sidesteps that -- it verifies against a
# real, current CA list either way.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


async def _run_one(url: str, label: str) -> None:
    t0 = time.monotonic()

    def elapsed() -> float:
        return time.monotonic() - t0

    ws = None
    try:
        ws = await websockets.connect(url, ping_interval=None, open_timeout=10, ssl=_SSL_CONTEXT)
        await ws.send(
            json.dumps({"t": "hello", "v": 1, "session_id": None, "client_ts_ms": int(time.time() * 1000)})
        )
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=PONG_DEADLINE_S))
        if ready.get("t") != "ready":
            print(f"[{label}] did not get ready as the first reply: {ready}")
            return
        # `ready` is always immediately followed by a `state` push -- drain it,
        # or every reply from here on reads one message behind what was sent.
        await asyncio.wait_for(ws.recv(), timeout=PONG_DEADLINE_S)
        print(f"[{label}] t={elapsed():.1f}s ready, session={ready.get('session_id', '?')[:8]}")

        last_ok = elapsed()
        while elapsed() < MAX_RUNTIME_S:
            await asyncio.sleep(PING_INTERVAL_S)
            ping_id = str(uuid.uuid4())[:8]
            try:
                await ws.send(json.dumps({"t": "ping", "id": ping_id, "client_ts_ms": int(time.time() * 1000)}))
                reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=PONG_DEADLINE_S))
                if reply.get("t") == "pong" and reply.get("id") == ping_id:
                    last_ok = elapsed()
                    print(f"[{label}] t={last_ok:.1f}s ok")
                else:
                    print(f"[{label}] t={elapsed():.1f}s unexpected reply: {reply}")
            except (TimeoutError, ConnectionClosed) as exc:
                first_fail = elapsed()
                print(f"[{label}] last-ok t={last_ok:.1f}s  first-fail t={first_fail:.1f}s  ({exc!r})")
                return
        print(f"[{label}] survived the full {MAX_RUNTIME_S}s -- no death observed in this window")
    except Exception as exc:
        print(f"[{label}] connect/hello failed at t={elapsed():.1f}s: {exc!r}")
    finally:
        if ws is not None:
            try:
                await asyncio.wait_for(ws.close(), timeout=5)
            except Exception:
                pass  # already dead; a close() failure here is not new information


async def main() -> None:
    if len(sys.argv) != 2:
        print("usage: ws_lifetime.py wss://<host>/ws")
        raise SystemExit(2)
    url = sys.argv[1]
    await asyncio.gather(_run_one(url, "A"), _run_one(url, "B"))


if __name__ == "__main__":
    asyncio.run(main())
