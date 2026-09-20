"""Server-minted sessions that outlive their connection.

A connection is not a session (docs/plans/blocks/01-skeleton-deploy.md). A
session is identified by a server-minted, opaque uuid4 the client never
proposes -- a guessable id would let one browser resume another's session,
which is exactly the cross-session leakage Block 7's memory gate asserts
against.

The registry is an in-process dict in Block 1 (modal.Dict arrives in Block 7
with memory) -- which is why modal_app.py pins max_containers=1: a reconnect
landing on a second container would find no session here and silently start
a new one.

Records expire on a TTL swept lazily on each `hello`, never on the socket
closing -- Block 0 measured the server not noticing a dead client for up to
~120s after the client had already given up and reconnected twice. A closing
socket is not a reliable signal here, so it is not the signal used.
"""

import time
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket

SESSION_TTL_MS = 15 * 60 * 1000


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Session:
    """`generation` is never sent to the client -- it exists purely to make
    a superseded connection's late teardown a no-op (the late-`finally` bug:
    S1 measured the server learning about a dead connection up to ~120s
    after the client had already reconnected, twice). Every connection
    captures its own generation right after `hello`; on disconnect it may
    clear `live` only if the session's generation still matches the one it
    captured -- otherwise a ghost from an old connection could tear down a
    session a newer connection is actively using.
    """

    session_id: str
    created_at_ms: int
    last_seen_ms: int
    connection_n: int = 0
    generation: int = 0
    seq: int = 0
    live: WebSocket | None = field(default=None, repr=False, compare=False)

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def _sweep(self) -> None:
        cutoff = now_ms() - SESSION_TTL_MS
        expired = [sid for sid, s in self._sessions.items() if s.last_seen_ms < cutoff]
        for sid in expired:
            del self._sessions[sid]

    def bind(
        self, requested_id: str | None, ws: WebSocket
    ) -> tuple[Session, bool, WebSocket | None]:
        """Resolve a session for a new connection and make `ws` its live
        socket. Returns (session, resumed, superseded_ws).

        `superseded_ws` is the previous live socket if one was still marked
        live -- either an ordinary reconnect racing ahead of the old
        socket's own teardown, or two tabs sharing a session id. Either way
        the caller is responsible for notifying and closing it; this method
        only does the bookkeeping.

        An unknown or absent id mints a new session rather than adopting the
        client's guess -- the id is never trusted, only ever recognised.
        Callers read `session.generation` immediately after this returns to
        capture "my_generation"; nothing awaits in between, so it cannot go
        stale before it is captured.
        """
        self._sweep()

        session = self._sessions.get(requested_id) if requested_id else None
        resumed = session is not None
        if session is None:
            session = Session(
                session_id=str(uuid.uuid4()),
                created_at_ms=now_ms(),
                last_seen_ms=now_ms(),
            )
            self._sessions[session.session_id] = session

        superseded_ws = session.live
        session.last_seen_ms = now_ms()
        session.connection_n += 1
        session.generation += 1
        session.live = ws
        return session, resumed, superseded_ws
