"""Session identity: minting, resuming, and the generation counter that
makes a superseded connection's late teardown a no-op (S1's late-`finally`
bug -- see app/session.py's module docstring).
"""

from typing import cast

from fastapi import WebSocket

from app.session import Session, SessionRegistry


def _ws() -> WebSocket:
    """A session's `live` field is only ever compared by identity in Block 1
    -- nothing in the registry calls a WebSocket method on it. A bare object
    stands in fine; cast to satisfy the real parameter type.
    """
    return cast(WebSocket, object())


def test_cold_hello_mints_a_session() -> None:
    registry = SessionRegistry()
    session, resumed, superseded = registry.bind(None, _ws())
    assert resumed is False
    assert superseded is None
    assert session.connection_n == 1
    assert session.generation == 1
    assert session.session_id


def test_known_id_resumes_and_continues_seq_and_connection_n() -> None:
    registry = SessionRegistry()
    first, _, _ = registry.bind(None, _ws())
    first.next_seq()
    first.next_seq()  # seq is now 2, as if two messages had already gone out
    first.live = None  # the first connection's own cleanup already ran (ordinary close)

    second, resumed, superseded = registry.bind(first.session_id, _ws())

    assert second is first
    assert resumed is True
    assert superseded is None  # nothing was still live when the reconnect arrived
    assert second.connection_n == 2
    assert second.generation == 2
    assert second.seq == 2  # continues -- does not reset on reconnect


def test_unknown_id_mints_a_new_session_rather_than_trusting_it() -> None:
    registry = SessionRegistry()
    session, resumed, superseded = registry.bind("client-made-this-up", _ws())
    assert resumed is False
    assert superseded is None
    assert session.session_id != "client-made-this-up"


def test_a_still_live_connection_is_returned_as_superseded() -> None:
    registry = SessionRegistry()
    first_ws = _ws()
    session, _, _ = registry.bind(None, first_ws)
    # first_ws is still session.live -- nobody has disconnected yet, but a
    # second hello for the same id arrives anyway (two tabs, or a reconnect
    # racing ahead of the old socket's own teardown).

    _, resumed, superseded = registry.bind(session.session_id, _ws())

    assert resumed is True
    assert superseded is first_ws


def test_stale_generation_disconnect_does_not_clear_live() -> None:
    """The late-`finally` case: an old connection's cleanup runs after a
    newer one has already taken over. It must be a no-op, not a teardown."""
    registry = SessionRegistry()
    session, _, _ = registry.bind(None, _ws())
    my_generation = session.generation

    new_ws = _ws()
    registry.bind(session.session_id, new_ws)  # a reconnect bumps the generation
    assert session.generation != my_generation
    assert session.live is new_ws

    # The old (superseded) connection's `finally` block, arriving late:
    if session.generation == my_generation:
        session.live = None
    assert session.live is new_ws  # unchanged -- the whole point of the guard


def test_current_generation_disconnect_does_clear_live() -> None:
    """The positive case, for symmetry: the guard actually gates something."""
    registry = SessionRegistry()
    session, _, _ = registry.bind(None, _ws())
    my_generation = session.generation

    if session.generation == my_generation:
        session.live = None
    assert session.live is None


def test_ttl_sweep_drops_an_expired_session_and_keeps_a_fresh_one() -> None:
    registry = SessionRegistry()
    fresh, _, _ = registry.bind(None, _ws())

    # epoch: last_seen_ms=0 is long past any TTL, on purpose.
    stale = Session(session_id="stale-one", created_at_ms=0, last_seen_ms=0)
    registry._sessions[stale.session_id] = stale

    # Sweeping happens lazily on the next bind(), for an unrelated id.
    registry.bind(None, _ws())

    assert stale.session_id not in registry._sessions
    assert fresh.session_id in registry._sessions
