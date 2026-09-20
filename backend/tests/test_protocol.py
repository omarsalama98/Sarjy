"""Every Block 1 client message round-trips through parse_client_message();
extra="forbid" and the discriminated union do the actual rejecting -- these
tests exist to prove that, not to re-implement it.
"""

import pytest
from pydantic import ValidationError

from app.pipeline.protocol import (
    PROTOCOL_VERSION,
    ByeIn,
    ClosingOut,
    ErrorOut,
    HelloIn,
    PingIn,
    PongOut,
    ReadyOut,
    StateOut,
    parse_client_message,
)


def test_hello_round_trips() -> None:
    raw = '{"t":"hello","v":1,"session_id":null,"client_ts_ms":1758300000000}'
    msg = parse_client_message(raw)
    assert isinstance(msg, HelloIn)
    assert msg.v == 1
    assert msg.session_id is None
    assert msg.client_ts_ms == 1758300000000


def test_hello_round_trips_with_a_session_id() -> None:
    raw = '{"t":"hello","v":1,"session_id":"abc-123","client_ts_ms":1758300000000}'
    msg = parse_client_message(raw)
    assert isinstance(msg, HelloIn)
    assert msg.session_id == "abc-123"


def test_ping_round_trips() -> None:
    raw = '{"t":"ping","id":"c7","client_ts_ms":1758300001000}'
    msg = parse_client_message(raw)
    assert isinstance(msg, PingIn)
    assert msg.id == "c7"
    assert msg.client_ts_ms == 1758300001000


def test_bye_round_trips_for_each_reason() -> None:
    for reason in ("rotate", "leave"):
        msg = parse_client_message(f'{{"t":"bye","reason":"{reason}"}}')
        assert isinstance(msg, ByeIn)
        assert msg.reason == reason


def test_unknown_t_is_rejected() -> None:
    """start/end/barge are reserved for Block 2 -- not part of this union yet."""
    with pytest.raises(ValidationError):
        parse_client_message('{"t":"start","turn_id":"x"}')


def test_extra_field_is_rejected() -> None:
    """extra="forbid" doing the actual work, not just declared."""
    with pytest.raises(ValidationError):
        parse_client_message('{"t":"ping","id":"c7","client_ts_ms":1,"surprise":true}')


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_client_message("{")


def test_hello_version_is_not_schema_enforced() -> None:
    """`v` is a plain int at the schema layer, deliberately: app/main.py
    compares it to PROTOCOL_VERSION itself, because a mismatch gets a
    specific error+closing handshake -- not the generic "invalid first
    message -> close" path a schema-level rejection would collapse it into.
    See test_ws.py for the end-to-end version-mismatch behaviour.
    """
    raw = f'{{"t":"hello","v":{PROTOCOL_VERSION + 1},"session_id":null,"client_ts_ms":0}}'
    msg = parse_client_message(raw)
    assert isinstance(msg, HelloIn)
    assert msg.v != PROTOCOL_VERSION


def test_ready_serialises_with_documented_keys() -> None:
    msg = ReadyOut(
        v=1,
        session_id="s1",
        resumed=True,
        connection_n=3,
        rotate_after_ms=75_000,
        hard_max_ms=110_000,
        server_started_at_ms=0,
        seq=42,
        ts_ms=0,
    )
    assert msg.model_dump() == {
        "t": "ready",
        "v": 1,
        "session_id": "s1",
        "resumed": True,
        "connection_n": 3,
        "rotate_after_ms": 75_000,
        "hard_max_ms": 110_000,
        "server_started_at_ms": 0,
        "seq": 42,
        "ts_ms": 0,
    }


def test_state_serialises_with_documented_keys() -> None:
    msg = StateOut(value="idle", seq=1, ts_ms=0)
    assert msg.model_dump() == {"t": "state", "value": "idle", "seq": 1, "ts_ms": 0}


def test_pong_serialises_with_documented_keys() -> None:
    msg = PongOut(id="c7", client_ts_ms=1, seq=2, ts_ms=0)
    assert msg.model_dump() == {"t": "pong", "id": "c7", "client_ts_ms": 1, "seq": 2, "ts_ms": 0}


def test_error_serialises_with_documented_keys() -> None:
    msg = ErrorOut(code="bad_message", message="x", recoverable=True, seq=3, ts_ms=0)
    assert msg.model_dump() == {
        "t": "error",
        "code": "bad_message",
        "message": "x",
        "recoverable": True,
        "seq": 3,
        "ts_ms": 0,
    }


def test_closing_serialises_with_documented_keys() -> None:
    msg = ClosingOut(reason="rotate_ceiling", reconnect=True, seq=4, ts_ms=0)
    assert msg.model_dump() == {
        "t": "closing",
        "reason": "rotate_ceiling",
        "reconnect": True,
        "seq": 4,
        "ts_ms": 0,
    }
