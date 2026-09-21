"""Every Block 1 client message round-trips through parse_client_message();
extra="forbid" and the discriminated union do the actual rejecting -- these
tests exist to prove that, not to re-implement it.
"""

import pytest
from pydantic import ValidationError

from app.pipeline.protocol import (
    PROTOCOL_VERSION,
    AudioEndOut,
    AudioStartOut,
    BargeIn,
    ByeIn,
    ClientTimingIn,
    ClosingOut,
    EndIn,
    ErrorOut,
    FactCardOut,
    FactOut,
    FactRowOut,
    ForgetIn,
    HelloIn,
    MemoryOut,
    PingIn,
    PlaceCardOut,
    PlacesOut,
    PongOut,
    QuotaOut,
    ReadyOut,
    ReplyOut,
    SegmentOut,
    SegmentsOut,
    SignInIn,
    SignOutIn,
    StartIn,
    StateOut,
    TranscriptOut,
    TurnFailedOut,
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


def test_start_round_trips() -> None:
    raw = '{"t":"start","turn_id":"t-1","client_ts_ms":1758300000000}'
    msg = parse_client_message(raw)
    assert isinstance(msg, StartIn)
    assert msg.turn_id == "t-1"
    assert msg.lang == "en"


def test_start_accepts_lang_ar() -> None:
    raw = '{"t":"start","turn_id":"t-1","client_ts_ms":1758300000000,"lang":"ar"}'
    msg = parse_client_message(raw)
    assert isinstance(msg, StartIn)
    assert msg.lang == "ar"


def test_end_round_trips() -> None:
    raw = '{"t":"end","turn_id":"t-1","samples":48000,"client_ts_ms":1758300003000}'
    msg = parse_client_message(raw)
    assert isinstance(msg, EndIn)
    assert msg.samples == 48000


def test_barge_round_trips() -> None:
    raw = '{"t":"barge","turn_id":"t-1"}'
    msg = parse_client_message(raw)
    assert isinstance(msg, BargeIn)
    assert msg.turn_id == "t-1"


def test_client_timing_round_trips() -> None:
    raw = (
        '{"t":"client_timing","turn_id":"t-1","endpoint_ms":580,'
        '"first_audio_ms":1830,"redemption_ms":600,"output_latency_ms":20}'
    )
    msg = parse_client_message(raw)
    assert isinstance(msg, ClientTimingIn)
    assert msg.endpoint_ms == 580
    assert msg.first_audio_ms == 1830
    assert msg.redemption_ms == 600
    assert msg.output_latency_ms == 20


def test_client_timing_allows_null_legs() -> None:
    """A barge before any audio played means neither leg completed -- the
    message is still valid, not an error, so main.py's merge still gets a
    turn_id to key off."""
    raw = (
        '{"t":"client_timing","turn_id":"t-1","endpoint_ms":null,'
        '"first_audio_ms":null,"redemption_ms":600,"output_latency_ms":null}'
    )
    msg = parse_client_message(raw)
    assert isinstance(msg, ClientTimingIn)
    assert msg.endpoint_ms is None
    assert msg.first_audio_ms is None


def test_client_timing_rejects_an_extra_field() -> None:
    raw = (
        '{"t":"client_timing","turn_id":"t-1","endpoint_ms":1,'
        '"first_audio_ms":1,"redemption_ms":600,"output_latency_ms":null,"surprise":true}'
    )
    with pytest.raises(ValidationError):
        parse_client_message(raw)


def test_unknown_t_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_client_message('{"t":"nonsense","turn_id":"x"}')


def test_start_rejects_an_extra_field() -> None:
    with pytest.raises(ValidationError):
        parse_client_message('{"t":"start","turn_id":"x","client_ts_ms":0,"surprise":true}')


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


def test_transcript_serialises_with_documented_keys() -> None:
    msg = TranscriptOut(turn_id="t-1", text="hello", seq=5, ts_ms=0)
    assert msg.model_dump() == {
        "t": "transcript",
        "turn_id": "t-1",
        "text": "hello",
        "seq": 5,
        "ts_ms": 0,
    }


def test_reply_serialises_with_documented_keys() -> None:
    msg = ReplyOut(turn_id="t-1", text="Tokyo.", seq=6, ts_ms=0)
    assert msg.model_dump() == {
        "t": "reply",
        "turn_id": "t-1",
        "text": "Tokyo.",
        "seq": 6,
        "ts_ms": 0,
    }


def test_audio_start_serialises_with_documented_keys() -> None:
    msg = AudioStartOut(turn_id="t-1", sample_rate=24000, seq=7, ts_ms=0)
    assert msg.model_dump() == {
        "t": "audio_start",
        "turn_id": "t-1",
        "sample_rate": 24000,
        "seq": 7,
        "ts_ms": 0,
    }


def test_audio_end_serialises_with_documented_keys() -> None:
    msg = AudioEndOut(turn_id="t-1", samples=72000, seq=8, ts_ms=0)
    assert msg.model_dump() == {
        "t": "audio_end",
        "turn_id": "t-1",
        "samples": 72000,
        "seq": 8,
        "ts_ms": 0,
    }


def test_turn_failed_serialises_with_documented_keys() -> None:
    msg = TurnFailedOut(turn_id="t-1", stage="stt", message="oops", seq=9, ts_ms=0)
    assert msg.model_dump() == {
        "t": "turn_failed",
        "turn_id": "t-1",
        "stage": "stt",
        "message": "oops",
        "seq": 9,
        "ts_ms": 0,
    }


def test_turn_failed_accepts_the_two_new_stages() -> None:
    """Block A adds `tool` and `gate` to TurnFailedStage."""
    for stage in ("tool", "gate"):
        msg = TurnFailedOut(turn_id="t-1", stage=stage, message="x", seq=1, ts_ms=0)  # type: ignore[arg-type]
        assert msg.stage == stage


def test_protocol_version_is_5() -> None:
    """Bumped for Block B's sign_in/sign_out/forget/memory messages -- a
    stale tab fails the handshake cleanly rather than half-understanding
    a `memory` frame."""
    assert PROTOCOL_VERSION == 5


def test_segments_serialises_with_documented_keys() -> None:
    msg = SegmentsOut(
        turn_id="t-1",
        segments=[
            SegmentOut(
                kind="sourced",
                text="You can stay up to 90 days.",
                ok=True,
                reason=None,
                attribution=None,
                field=None,
                citation="Travel Buddy",
                source_url=None,
                source_date="2026-09-20",
                layer="live",
            )
        ],
        spoken="You can stay up to 90 days.",
        hedged=False,
        seq=10,
        ts_ms=0,
    )
    dumped = msg.model_dump()
    assert dumped["t"] == "segments"
    assert dumped["hedged"] is False
    assert dumped["segments"][0]["kind"] == "sourced"
    assert dumped["segments"][0]["ok"] is True


def test_quota_serialises_with_documented_keys() -> None:
    msg = QuotaOut(total=120, spent=10, reserve=40, remaining=70, seq=11, ts_ms=0)
    assert msg.model_dump() == {
        "t": "quota",
        "total": 120,
        "spent": 10,
        "reserve": 40,
        "remaining": 70,
        "seq": 11,
        "ts_ms": 0,
    }


def test_fact_card_serialises_with_documented_keys() -> None:
    msg = FactCardOut(
        turn_id="t-1",
        passport="SA",
        passport_name="Saudi Arabia",
        destination="JP",
        destination_name="Japan",
        covered=True,
        facts=[
            FactRowOut(
                path="visa.duration", label="Maximum stay", value="90 days", kind="sourced"
            )
        ],
        layer="live",
        degraded=False,
        source_name="Travel Buddy",
        source_url=None,
        source_date="2026-09-20T14:28:07+00:00",
        retrieved="2026-09-20T09:00:00Z",
        embassy_url="https://www.embassypages.com/saudiarabia",
        seq=12,
        ts_ms=0,
    )
    dumped = msg.model_dump()
    assert dumped["t"] == "fact_card"
    assert dumped["covered"] is True
    assert dumped["facts"][0]["path"] == "visa.duration"
    assert dumped["degraded"] is False


# ---------------------------------------------------------------------------
# Block B -- sign_in/sign_out/forget (c->s) and memory (s->c).
# ---------------------------------------------------------------------------


def test_sign_in_round_trips() -> None:
    raw = '{"t":"sign_in","name":"Omar","pin":"4712"}'
    msg = parse_client_message(raw)
    assert isinstance(msg, SignInIn)
    assert msg.name == "Omar"
    assert msg.pin == "4712"


def test_sign_in_rejects_a_non_four_digit_pin() -> None:
    with pytest.raises(ValidationError):
        parse_client_message('{"t":"sign_in","name":"Omar","pin":"471"}')


def test_sign_in_rejects_an_empty_name() -> None:
    with pytest.raises(ValidationError):
        parse_client_message('{"t":"sign_in","name":"","pin":"4712"}')


def test_sign_out_round_trips() -> None:
    msg = parse_client_message('{"t":"sign_out"}')
    assert isinstance(msg, SignOutIn)


def test_forget_round_trips_with_a_key() -> None:
    msg = parse_client_message('{"t":"forget","key":"favourite_colour"}')
    assert isinstance(msg, ForgetIn)
    assert msg.key == "favourite_colour"


def test_forget_round_trips_with_null_key_meaning_everything() -> None:
    msg = parse_client_message('{"t":"forget","key":null}')
    assert isinstance(msg, ForgetIn)
    assert msg.key is None


def test_memory_serialises_with_documented_keys() -> None:
    msg = MemoryOut(
        tier="signed_in",
        name="Omar",
        facts=[
            FactOut(
                key="favourite_colour",
                label="Favourite colour",
                value="green",
                kind="open",
                learned_at="2026-09-21T14:03:11Z",
                turn_id="t-1",
                quote="my favourite colour is green",
            )
        ],
        used=1,
        capacity=12,
        persisted=True,
        degraded=False,
        message=None,
        seq=3,
        ts_ms=0,
    )
    dumped = msg.model_dump()
    assert dumped["t"] == "memory"
    assert dumped["tier"] == "signed_in"
    assert dumped["facts"][0]["quote"] == "my favourite colour is green"
    assert dumped["used"] == 1


def test_places_serialises_with_documented_keys() -> None:
    msg = PlacesOut(
        turn_id="t-1",
        places=[
            PlaceCardOut(
                name="Kyoto",
                title="Kyoto",
                description="A city in Kansai.",
                image_url="https://upload.wikimedia.org/wikipedia/commons/k.jpg",
                page_url="https://en.wikipedia.org/wiki/Kyoto",
                revision_date="2026-09-14T15:53:35Z",
                ok=True,
                reason=None,
            )
        ],
        seq=12,
        ts_ms=0,
    )
    dumped = msg.model_dump()
    assert dumped["t"] == "places"
    assert dumped["places"][0]["ok"] is True
    assert dumped["places"][0]["name"] == "Kyoto"
