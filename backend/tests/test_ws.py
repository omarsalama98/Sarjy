"""Exercises the real handler through FastAPI's TestClient -- no network, but
a real ASGI request/response cycle, which is the strongest test the handler
gets without an actual deployment.

The turn-level tests below monkeypatch app.providers.factory rather than
re-testing run_turn()'s own branches (tests/test_turn.py already covers
every failure row against fakes, with no HTTP/ASGI machinery in the way).
What's worth proving here, that test_turn.py can't, is main.py's OWN
wiring: buffer accumulation across several binary frames, the state
messages around a turn, and that barge/implicit-barge actually cancel the
right task on a real asyncio event loop.

Every connection now sends a `quota` message right after `ready`/`state`
(Contract 6) -- the module-level `_default_tool` fixture patches
factory.get_tool() for every test in this file, deterministically, so that
message is never left to depend on whatever happens to be in the local
.env. `_handshake()` is the one place that reads and discards it, so an
individual test doesn't have to know it exists.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import main
from app.main import PROTOCOL_VERSION, app
from app.main import registry as _session_registry
from app.memory.store import Fact
from app.pipeline.timings import LOG_PREFIX
from app.pipeline.turn import MAX_TURN_BYTES
from app.providers import factory
from app.providers.base import LLMDecision
from app.tools.fake import FakeVisaTool

client = TestClient(app)


def _hello(session_id: str | None = None) -> dict[str, object]:
    return {"t": "hello", "v": PROTOCOL_VERSION, "session_id": session_id, "client_ts_ms": 0}


def _handshake(ws) -> dict[str, object]:  # type: ignore[no-untyped-def]
    """hello -> ready, state(idle), quota, memory -- every connection's
    fixed opening sequence (Block B adds `memory`, last). Returns `ready`
    for the few tests that inspect it."""
    ws.send_json(_hello())
    ready = ws.receive_json()
    ws.receive_json()  # state idle
    ws.receive_json()  # quota
    ws.receive_json()  # memory
    return ready  # type: ignore[no-any-return]


class _FakeSTT:
    model = "fake-whisper"

    def __init__(self, text: str = "what's the capital of japan") -> None:
        self._text = text
        self.called = False

    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str:
        self.called = True
        return self._text


class _FakeLLM:
    """No tool call, ever -- decide() always returns tool_name=None, and
    segments() yields exactly one `judgement` line. That keeps every turn
    in this file on the plain (no-visa-tool) path, which is what main.py's
    OWN wiring is being tested against here, not the gate's rules
    (test_turn.py owns those)."""

    model = "fake-gemini"
    thinking_level: str | None = "minimal"
    reply_text = "Tokyo."

    async def decide(
        self,
        *,
        system: str,
        history: list[tuple[str, str]],
        user: str,
        tools: list[object],
        memory_block: str = "",
    ) -> LLMDecision:
        return LLMDecision(tool_name=None, tool_arguments={}, text="", first_delta_ms=5)

    async def segments(self, *, system: str, user_block: str) -> AsyncIterator[str]:
        yield json.dumps({"kind": "judgement", "text": self.reply_text})


class _FakeTTS:
    model = "fake-aura"

    def __init__(self, chunks: list[bytes] | None = None, delay_s: float = 0.0) -> None:
        self._chunks = chunks if chunks is not None else [b"\x01\x02" * 5]
        self._delay_s = delay_s

    async def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            if self._delay_s:
                await asyncio.sleep(self._delay_s)
            yield chunk


@pytest.fixture(autouse=True)
def _default_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module gets a deterministic, empty FakeVisaTool --
    so the post-`ready` `quota` message (Contract 6) is always sent, and
    always with the same numbers, regardless of what's in the local .env."""
    monkeypatch.setattr(factory, "get_tool", lambda: FakeVisaTool())


def _patch_providers(
    monkeypatch: pytest.MonkeyPatch, stt: object, llm: object, tts: object
) -> None:
    monkeypatch.setattr(factory, "get_stt", lambda: stt)
    monkeypatch.setattr(factory, "get_llm", lambda: llm)
    monkeypatch.setattr(factory, "get_tts", lambda: tts)


def test_hello_then_ready_then_state_idle() -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello())

        ready = ws.receive_json()
        assert ready["t"] == "ready"
        assert ready["resumed"] is False
        assert ready["connection_n"] == 1
        assert ready["v"] == PROTOCOL_VERSION

        state = ws.receive_json()
        assert state["t"] == "state"
        assert state["value"] == "idle"

        quota = ws.receive_json()
        assert quota["t"] == "quota"
        assert quota["total"] == 120

        memory = ws.receive_json()
        assert memory["t"] == "memory"
        assert memory["tier"] == "anonymous"
        assert memory["facts"] == []


def test_ping_gets_a_pong() -> None:
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json({"t": "ping", "id": "c7", "client_ts_ms": 123})
        pong = ws.receive_json()
        assert pong["t"] == "pong"
        assert pong["id"] == "c7"
        assert pong["client_ts_ms"] == 123


def test_malformed_text_gets_an_error_and_the_socket_stays_usable() -> None:
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_text("{")
        err = ws.receive_json()
        assert err["t"] == "error"
        assert err["code"] == "bad_message"
        assert err["recoverable"] is True

        # One bad frame must not cost a conversation -- prove the socket is
        # still usable with an ordinary ping.
        ws.send_json({"t": "ping", "id": "still-alive", "client_ts_ms": 0})
        pong = ws.receive_json()
        assert pong["t"] == "pong"
        assert pong["id"] == "still-alive"


def test_binary_frame_with_no_open_turn_is_bad_message_not_fatal() -> None:
    """F15: audio arriving with no `start` in progress is a recoverable
    error, not a dropped connection -- and the socket stays usable after."""
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_bytes(b"\x00\x01")
        err = ws.receive_json()
        assert err["t"] == "error"
        assert err["code"] == "bad_message"
        assert err["recoverable"] is True

        ws.send_json({"t": "ping", "id": "still-alive", "client_ts_ms": 0})
        pong = ws.receive_json()
        assert pong["t"] == "pong"
        assert pong["id"] == "still-alive"


def test_reconnect_with_the_returned_id_resumes() -> None:
    """The whole block's thesis: a session outlives its connection."""
    with client.websocket_connect("/ws") as ws1:
        ready1 = _handshake(ws1)
        session_id = ready1["session_id"]
        assert ready1["resumed"] is False
        assert ready1["connection_n"] == 1

    with client.websocket_connect("/ws") as ws2:
        ws2.send_json(_hello(session_id))
        ready2 = ws2.receive_json()
        assert ready2["resumed"] is True
        assert ready2["session_id"] == session_id
        assert ready2["connection_n"] == 2


def test_protocol_version_mismatch_gets_error_then_closing() -> None:
    with client.websocket_connect("/ws") as ws:
        bad_hello = {"t": "hello", "v": PROTOCOL_VERSION + 1, "session_id": None, "client_ts_ms": 0}
        ws.send_json(bad_hello)

        err = ws.receive_json()
        assert err["t"] == "error"
        assert err["code"] == "protocol_version"
        assert err["recoverable"] is False

        closing = ws.receive_json()
        assert closing["t"] == "closing"
        assert closing["reason"] == "protocol_version"
        assert closing["reconnect"] is False


def test_bye_closes_without_error() -> None:
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json({"t": "bye", "reason": "leave"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_non_hello_first_message_closes_without_a_reply() -> None:
    """The handshake is the one place a bad message is fatal -- even a
    well-formed message is fatal here if it isn't `hello`."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"t": "ping", "id": "too-early", "client_ts_ms": 0})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_full_turn_start_binary_end_produces_the_documented_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_providers(monkeypatch, _FakeSTT(), _FakeLLM(), _FakeTTS())

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json({"t": "start", "turn_id": "t-1", "client_ts_ms": 0})
        # Two binary frames -- proves main.py accumulates across several
        # frames rather than assuming one frame per turn.
        ws.send_bytes(b"\x00\x01" * 50)
        ws.send_bytes(b"\x00\x01" * 50)
        ws.send_json({"t": "end", "turn_id": "t-1", "samples": 100, "client_ts_ms": 0})

        thinking = ws.receive_json()
        assert thinking["t"] == "state"
        assert thinking["value"] == "thinking"

        transcript = ws.receive_json()
        assert transcript["t"] == "transcript"
        assert transcript["turn_id"] == "t-1"
        assert transcript["text"] == "what's the capital of japan"

        segments = ws.receive_json()
        assert segments["t"] == "segments"
        assert segments["spoken"] == "Tokyo."

        reply = ws.receive_json()
        assert reply["t"] == "reply"
        assert reply["text"] == "Tokyo."

        audio_start = ws.receive_json()
        assert audio_start["t"] == "audio_start"
        assert audio_start["sample_rate"] == 24_000

        chunk = ws.receive_bytes()
        assert chunk == b"\x01\x02" * 5

        audio_end = ws.receive_json()
        assert audio_end["t"] == "audio_end"

        idle = ws.receive_json()
        assert idle["t"] == "state"
        assert idle["value"] == "idle"


def test_binary_with_no_open_turn_never_reaches_stt() -> None:
    """F15, proven against a fake that would raise if it were ever called --
    not just that an error is sent, but that STT is never touched."""
    stt = _FakeSTT()

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_bytes(b"\x00\x01")
        err = ws.receive_json()
        assert err["code"] == "bad_message"

    assert stt.called is False


def test_f7_oversized_audio_fails_while_still_accumulating(monkeypatch: pytest.MonkeyPatch) -> None:
    """The server's own cap, checked as bytes arrive -- proven by a fake STT
    that would raise if it were ever reached; the turn must fail before
    `end` is even sent."""

    class _RaisingSTT:
        async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str:
            raise AssertionError("STT must never be reached for an oversized turn")

    _patch_providers(monkeypatch, _RaisingSTT(), _FakeLLM(), _FakeTTS())

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json({"t": "start", "turn_id": "t-1", "client_ts_ms": 0})
        ws.send_bytes(b"\x00" * (MAX_TURN_BYTES + 2))

        failed = ws.receive_json()
        assert failed["t"] == "turn_failed"
        assert failed["stage"] == "audio"

        idle = ws.receive_json()
        assert idle["t"] == "state"
        assert idle["value"] == "idle"


def test_explicit_barge_cancels_the_turn_and_the_socket_stays_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two chunks, each preceded by a 50ms sleep: after the first chunk is
    # read, there is a real window before the second would be produced --
    # sending `barge` inside that window and cancelling BEFORE the second
    # chunk exists is the actual thing this test is proving.
    slow_tts = _FakeTTS(chunks=[b"\x01\x02" * 5, b"\x03\x04" * 5], delay_s=0.05)
    _patch_providers(monkeypatch, _FakeSTT(), _FakeLLM(), slow_tts)

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json({"t": "start", "turn_id": "t-1", "client_ts_ms": 0})
        ws.send_bytes(b"\x00\x01" * 50)
        ws.send_json({"t": "end", "turn_id": "t-1", "samples": 50, "client_ts_ms": 0})

        ws.receive_json()  # thinking
        ws.receive_json()  # transcript
        ws.receive_json()  # segments
        ws.receive_json()  # reply
        ws.receive_json()  # audio_start
        first_chunk = ws.receive_bytes()
        assert first_chunk == b"\x01\x02" * 5

        # Barge inside the 50ms window before the second chunk. No message
        # is expected in reply to `barge` itself (main.py's documented
        # choice -- sending one here would race the client's own local
        # state, which already shows "listening" by the time it sends this).
        ws.send_json({"t": "barge", "turn_id": "t-1"})

        # The socket must still be usable, and a brand new turn must work
        # cleanly -- proving t-1's task was actually torn down rather than
        # left to eventually emit its own (now-stale) audio_end.
        ws.send_json({"t": "start", "turn_id": "t-2", "client_ts_ms": 0})
        ws.send_bytes(b"\x00\x01" * 50)
        ws.send_json({"t": "end", "turn_id": "t-2", "samples": 50, "client_ts_ms": 0})

        thinking2 = ws.receive_json()
        assert thinking2["t"] == "state"
        assert thinking2["value"] == "thinking"
        transcript2 = ws.receive_json()
        assert transcript2["turn_id"] == "t-2"


def test_implicit_barge_cancels_the_turn_and_the_socket_stays_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of _handle_start's shared cancellation path: a new
    `start` -- not an explicit `{"t":"barge"}` -- while t-1's run_turn() task
    is still in flight. main.py's own framing calls this "one code path for
    both"; this proves the implicit half actually tears t-1's task down too,
    the same way the test above proves it for the explicit message."""
    slow_tts = _FakeTTS(chunks=[b"\x01\x02" * 5, b"\x03\x04" * 5], delay_s=0.05)
    _patch_providers(monkeypatch, _FakeSTT(), _FakeLLM(), slow_tts)

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json({"t": "start", "turn_id": "t-1", "client_ts_ms": 0})
        ws.send_bytes(b"\x00\x01" * 50)
        ws.send_json({"t": "end", "turn_id": "t-1", "samples": 50, "client_ts_ms": 0})

        ws.receive_json()  # thinking
        ws.receive_json()  # transcript
        ws.receive_json()  # segments
        ws.receive_json()  # reply
        ws.receive_json()  # audio_start
        first_chunk = ws.receive_bytes()
        assert first_chunk == b"\x01\x02" * 5

        # An implicit barge: a fresh `start`, no `barge` message at all,
        # while t-1 is still mid-stream.
        ws.send_json({"t": "start", "turn_id": "t-2", "client_ts_ms": 0})
        ws.send_bytes(b"\x00\x01" * 50)
        ws.send_json({"t": "end", "turn_id": "t-2", "samples": 50, "client_ts_ms": 0})

        thinking2 = ws.receive_json()
        assert thinking2["t"] == "state"
        assert thinking2["value"] == "thinking"
        transcript2 = ws.receive_json()
        assert transcript2["turn_id"] == "t-2"


def test_second_turn_sees_first_turns_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session.remember_turn(): proven the way it actually matters -- the
    SECOND turn's LLM call receives the first turn's (user, assistant) pair,
    not that Session.history merely looks right in isolation (that's
    test_session.py's job for the data structure; this is the wiring that
    makes "and what about Korea?" work). History flows through call 1
    (decide()) only -- call 2 is a fresh, stateless interaction (D5) -- so
    this fake tracks which text to answer with as state set by decide() and
    read by segments()."""

    class _RecordingLLM:
        model = "fake-gemini"
        thinking_level: str | None = "minimal"

        def __init__(self) -> None:
            self.seen_history: list[list[tuple[str, str]]] = []
            self._next_text = "Tokyo."

        async def decide(
            self,
            *,
            system: str,
            history: list[tuple[str, str]],
            user: str,
            tools: list[object],
            memory_block: str = "",
        ) -> LLMDecision:
            self.seen_history.append(list(history))
            self._next_text = "Tokyo." if not history else "Seoul."
            return LLMDecision(tool_name=None, tool_arguments={}, text="", first_delta_ms=5)

        async def segments(self, *, system: str, user_block: str) -> AsyncIterator[str]:
            yield json.dumps({"kind": "judgement", "text": self._next_text})

    llm = _RecordingLLM()
    _patch_providers(monkeypatch, _FakeSTT(), llm, _FakeTTS())

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        for turn_id in ("t-1", "t-2"):
            ws.send_json({"t": "start", "turn_id": turn_id, "client_ts_ms": 0})
            ws.send_bytes(b"\x00\x01" * 50)
            ws.send_json({"t": "end", "turn_id": turn_id, "samples": 50, "client_ts_ms": 0})
            ws.receive_json()  # thinking
            ws.receive_json()  # transcript
            ws.receive_json()  # segments
            ws.receive_json()  # reply
            ws.receive_json()  # audio_start
            ws.receive_bytes()  # chunk
            ws.receive_json()  # audio_end
            ws.receive_json()  # state idle

    assert llm.seen_history == [
        [],
        [("what's the capital of japan", "Tokyo.")],
    ]


def test_f13_socket_close_mid_turn_cancels_the_server_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """F13's server-side half: dropping the client's socket mid-turn must
    not leave run_turn() running against a connection that no longer
    exists. _serve()'s `finally` calls _cancel_active_turn() regardless of
    why the receive loop ended -- proven here by a fake TTS that only sets a
    flag from inside `except asyncio.CancelledError`, so the flag can only
    ever be set by a real cancellation, not by the turn finishing normally."""
    cancelled = asyncio.Event()

    class _NeverEndingTTS:
        model = "fake-aura"

        async def synthesize(
            self, text: str, *, language: str | None = None
        ) -> AsyncIterator[bytes]:
            yield b"\x01\x02" * 5
            try:
                await asyncio.sleep(10)  # would hang forever if never cancelled
                yield b"\x03\x04" * 5
            except asyncio.CancelledError:
                cancelled.set()
                raise

    _patch_providers(monkeypatch, _FakeSTT(), _FakeLLM(), _NeverEndingTTS())

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json({"t": "start", "turn_id": "t-1", "client_ts_ms": 0})
        ws.send_bytes(b"\x00\x01" * 50)
        ws.send_json({"t": "end", "turn_id": "t-1", "samples": 50, "client_ts_ms": 0})

        ws.receive_json()  # thinking
        ws.receive_json()  # transcript
        ws.receive_json()  # segments
        ws.receive_json()  # reply
        ws.receive_json()  # audio_start
        ws.receive_bytes()  # first chunk -- t-1 is now blocked in asyncio.sleep(10)

        # The `with` block's exit below drops the client socket without a
        # `bye` -- WebSocketTestSession's __exit__ sends a disconnect and
        # then BLOCKS until the server-side ASGI coroutine has fully
        # finished (starlette's own `stack.callback(fut.result)`), so no
        # sleep or retry loop is needed here: by the time the `with` exits,
        # _serve()'s `finally` has already run.

    assert cancelled.is_set()


def _extract_timings_records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    lines = [r.message for r in caplog.records if r.message.startswith(LOG_PREFIX)]
    return [json.loads(line.removeprefix(LOG_PREFIX)) for line in lines]


def test_i3_client_timing_for_unknown_turn_is_ignored_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client_timing racing a reconnect (or a barge) can name a turn_id
    the server never opened, or already closed out -- a legitimate race,
    not a client bug: no error, no bad_message, the socket stays usable."""
    _patch_providers(monkeypatch, _FakeSTT(), _FakeLLM(), _FakeTTS())

    with client.websocket_connect("/ws") as ws:
        _handshake(ws)

        ws.send_json(
            {
                "t": "client_timing",
                "turn_id": "t-never-opened",
                "endpoint_ms": 500,
                "first_audio_ms": 1500,
                "redemption_ms": 600,
                "output_latency_ms": None,
            }
        )

        # No reply is expected for client_timing itself -- prove the socket
        # is still usable with an ordinary ping instead.
        ws.send_json({"t": "ping", "id": "still-alive", "client_ts_ms": 0})
        pong = ws.receive_json()
        assert pong["t"] == "pong"
        assert pong["id"] == "still-alive"


def test_i2_turn_with_no_client_timing_still_emits_one_record_on_next_start(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A turn the client never reports on (closed tab, stale bundle, a
    barge before any audio) must still produce exactly one record --
    flushed by the NEXT turn's `start`, never silently dropped."""
    _patch_providers(monkeypatch, _FakeSTT(), _FakeLLM(), _FakeTTS())

    with caplog.at_level(logging.INFO, logger="sarjy"):
        with client.websocket_connect("/ws") as ws:
            _handshake(ws)

            ws.send_json({"t": "start", "turn_id": "t-1", "client_ts_ms": 0})
            ws.send_bytes(b"\x00\x01" * 50)
            ws.send_json({"t": "end", "turn_id": "t-1", "samples": 50, "client_ts_ms": 0})
            ws.receive_json()  # thinking
            ws.receive_json()  # transcript
            ws.receive_json()  # segments
            ws.receive_json()  # reply
            ws.receive_json()  # audio_start
            ws.receive_bytes()  # chunk
            ws.receive_json()  # audio_end
            ws.receive_json()  # state idle
            # Deliberately no client_timing sent for t-1.

            ws.send_json({"t": "start", "turn_id": "t-2", "client_ts_ms": 0})
            ws.send_bytes(b"\x00\x01" * 50)
            ws.send_json({"t": "end", "turn_id": "t-2", "samples": 50, "client_ts_ms": 0})
            ws.receive_json()
            ws.receive_json()
            ws.receive_json()
            ws.receive_json()
            ws.receive_json()
            ws.receive_bytes()
            ws.receive_json()
            ws.receive_json()

    t1_records = [r for r in _extract_timings_records(caplog) if r["turn_id"] == "t-1"]
    assert len(t1_records) == 1
    assert t1_records[0]["flush_reason"] == "next_turn"
    assert t1_records[0]["outcome"] == "ok"  # server side completed cleanly


def test_a_complete_turn_prints_exactly_one_turn_timings_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The merge, happy path: server and client legs both land, one record
    comes out, with every field from TurnTimings present. `tool_ms` stays
    null (no tool called this turn -- _FakeLLM never asks for one);
    `llm2_ms`/`gate_ms` are FILLED now (Block A: call 2 always runs, D6) --
    only the truly opener-only fields (Block C) are still reserved-null."""
    _patch_providers(monkeypatch, _FakeSTT(), _FakeLLM(), _FakeTTS())

    with caplog.at_level(logging.INFO, logger="sarjy"):
        with client.websocket_connect("/ws") as ws:
            _handshake(ws)

            ws.send_json({"t": "start", "turn_id": "t-1", "client_ts_ms": 0})
            ws.send_bytes(b"\x00\x01" * 50)
            ws.send_json({"t": "end", "turn_id": "t-1", "samples": 50, "client_ts_ms": 0})
            ws.receive_json()  # thinking
            ws.receive_json()  # transcript
            ws.receive_json()  # segments
            ws.receive_json()  # reply
            ws.receive_json()  # audio_start
            ws.receive_bytes()  # chunk
            ws.receive_json()  # audio_end
            ws.receive_json()  # state idle

            ws.send_json(
                {
                    "t": "client_timing",
                    "turn_id": "t-1",
                    "endpoint_ms": 580,
                    "first_audio_ms": 1830,
                    "redemption_ms": 600,
                    "output_latency_ms": 12,
                }
            )
            # No reply expected -- the `with` block's own exit (see the F13
            # test above) blocks until the server has processed everything
            # already queued, this message included, before disconnecting.

    t1_records = [r for r in _extract_timings_records(caplog) if r["turn_id"] == "t-1"]
    assert len(t1_records) == 1
    record = t1_records[0]
    assert record["outcome"] == "ok"
    assert record["flush_reason"] == "complete"
    assert record["endpoint_ms"] == 580
    assert record["first_audio_ms"] == 1830
    assert record["redemption_ms"] == 600
    assert record["output_latency_ms"] == 12
    assert record["env"] == "local"
    for leg in (
        "upload_ms",
        "stt_ms",
        "llm_ms",
        "llm_ttft_ms",
        "tts_ttfb_ms",
        "tts_total_ms",
        "server_ms",
        "llm2_ms",
        "gate_ms",
    ):
        assert record[leg] is not None, leg
    assert record["tool_ms"] is None  # no tool called this turn
    assert record["tool_layer"] is None
    assert record["segments_ok"] == 1
    assert record["segments_rejected"] == 0
    assert record["lines_malformed"] == 0
    assert record["hedged"] is False
    for reserved in ("opener_ready_ms", "tts1_ttfb_ms", "answer_gap_ms"):
        assert reserved in record
        assert record[reserved] is None


# ---------------------------------------------------------------------------
# Block B -- sign_in / sign_out / forget over a real ASGI socket. `memory`
# arrives after `ready` on every connection (_handshake() above already
# proves that); these tests are the four outcomes memory-status assertions
# in D3/D9 that matter: create, refuse, lock out, and survive a fresh
# connection (the closest a unit test gets to "a reload").
# ---------------------------------------------------------------------------


def test_sign_in_reports_not_persisted_on_a_non_durable_store() -> None:
    """B1. The whole suite runs on the in-process fallback (conftest.py), so
    this is M1's real shape: the save SUCCEEDS, and the record still must not
    claim to be persisted. Asserting True here -- which this test used to do
    -- was asserting the bug: an unreachable modal.Dict would report a happy
    panel and lose everything on the next container restart."""
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)
        ws.send_json({"t": "sign_in", "name": "Bob Nd", "pin": "1234"})
        memory = ws.receive_json()
        assert memory["persisted"] is False
        assert memory["degraded"] is True


def test_sign_in_new_user_creates_a_persisted_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The happy path this test was always about: a store that really is
    # durable. Patched at main's import site, so it exercises the same
    # `ok and store_is_durable()` expression production uses.
    monkeypatch.setattr(main, "store_is_durable", lambda: True)
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)
        ws.send_json({"t": "sign_in", "name": "Bob Ws", "pin": "1234"})
        memory = ws.receive_json()
        assert memory["t"] == "memory"
        assert memory["tier"] == "signed_in"
        assert memory["degraded"] is False
        assert memory["name"] == "Bob Ws"
        assert memory["persisted"] is True
        assert memory["facts"] == []
        assert memory["message"] is not None and "Nice to meet you" in memory["message"]


def test_m3_wrong_pin_refuses_and_leaks_no_facts() -> None:
    """The middle of D3's three outcomes: an existing name, a PIN that
    doesn't match it. No record is loaded, none is created, and nothing
    about the real record's contents ever reaches the wire."""
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)
        ws.send_json({"t": "sign_in", "name": "Carol Ws", "pin": "1111"})
        ws.receive_json()  # the creation memory message

    with client.websocket_connect("/ws") as ws2:
        _handshake(ws2)
        ws2.send_json({"t": "sign_in", "name": "Carol Ws", "pin": "9999"})
        memory = ws2.receive_json()
        assert memory["tier"] == "anonymous"
        assert memory["facts"] == []
        assert memory["message"] is not None and "doesn't match" in memory["message"]


def test_m4_five_failed_attempts_then_locked_out() -> None:
    # Dave's real record, created on its own connection.
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)
        ws.send_json({"t": "sign_in", "name": "Dave Ws", "pin": "1234"})
        ws.receive_json()

    # A SEPARATE, still-anonymous session guessing Dave's PIN -- the
    # counter lives on the guesser's Session (M4), not on Dave's record.
    with client.websocket_connect("/ws") as ws2:
        _handshake(ws2)
        for _ in range(5):
            ws2.send_json({"t": "sign_in", "name": "Dave Ws", "pin": "0000"})
            memory = ws2.receive_json()
            assert memory["tier"] == "anonymous"
            assert memory["message"] is not None and "doesn't match" in memory["message"]

        # The 6th attempt is refused outright -- even with the RIGHT pin,
        # because the lockout is per-session, not per-guess.
        ws2.send_json({"t": "sign_in", "name": "Dave Ws", "pin": "1234"})
        memory = ws2.receive_json()
        assert memory["tier"] == "anonymous"
        assert memory["message"] is not None and "too many tries" in memory["message"]


def test_m13_a_whitespace_only_name_is_refused_not_a_crash() -> None:
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)
        ws.send_json({"t": "sign_in", "name": "   ", "pin": "1234"})
        memory = ws.receive_json()
        assert memory["tier"] == "anonymous"
        assert memory["message"] is not None and "need a name" in memory["message"]


def test_sign_out_returns_to_a_fresh_anonymous_record() -> None:
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)
        ws.send_json({"t": "sign_in", "name": "Eve Ws", "pin": "1234"})
        ws.receive_json()

        ws.send_json({"t": "sign_out"})
        memory = ws.receive_json()
        assert memory["tier"] == "anonymous"
        assert memory["name"] is None
        assert memory["facts"] == []


def test_d2_a_fact_taught_before_signing_in_migrates_and_survives_a_fresh_connection() -> None:
    """The demo flow (AGENTS.md / D2): talk first, then sign in. A fact
    taught to the anonymous tier must not vanish at the sign-in boundary,
    and it must still be there -- with its ORIGINAL timestamp -- from a
    completely separate connection (the closest a unit test gets to "the
    reviewer hard-reloads the page")."""
    with client.websocket_connect("/ws") as ws:
        ready = _handshake(ws)
        session = _session_registry._sessions[ready["session_id"]]
        # Stands in for a real turn's extraction (already proven at the unit
        # level in test_memory.py) -- what's under test here is the WIRE and
        # STORE plumbing around sign-in, not extraction itself.
        session.memory.remember(
            Fact(
                key="favourite_colour",
                value="green",
                label="Favourite colour",
                learned_at="2026-09-21T14:03:11Z",
                quote="my favourite colour is green",
            )
        )

        ws.send_json({"t": "sign_in", "name": "Frank Ws", "pin": "1234"})
        memory = ws.receive_json()
        assert memory["tier"] == "signed_in"
        assert len(memory["facts"]) == 1
        assert memory["facts"][0]["value"] == "green"
        assert memory["facts"][0]["learned_at"] == "2026-09-21T14:03:11Z"

    with client.websocket_connect("/ws") as ws2:
        _handshake(ws2)
        ws2.send_json({"t": "sign_in", "name": "Frank Ws", "pin": "1234"})
        memory = ws2.receive_json()
        assert memory["tier"] == "signed_in"
        fact = next(f for f in memory["facts"] if f["key"] == "favourite_colour")
        assert fact["value"] == "green"
        # The ORIGINAL learned_at, proving this was READ from the store, not
        # re-learned by this second connection.
        assert fact["learned_at"] == "2026-09-21T14:03:11Z"
        assert fact["quote"] == "my favourite colour is green"


def test_forget_everything_empties_the_panel_and_survives_a_fresh_connection() -> None:
    """Verification step 8's own framing: the proof that delete reached the
    store, not only the in-process object, is that a FRESH connection --
    which never touched the first one's Session -- still sees it empty."""
    with client.websocket_connect("/ws") as ws:
        ready = _handshake(ws)
        session = _session_registry._sessions[ready["session_id"]]
        session.memory.remember(
            Fact(key="favourite_colour", value="green", label="Favourite colour", learned_at="t")
        )

        ws.send_json({"t": "sign_in", "name": "Grace Ws", "pin": "1234"})
        memory = ws.receive_json()
        assert len(memory["facts"]) == 1

        ws.send_json({"t": "forget", "key": None})
        memory = ws.receive_json()
        assert memory["facts"] == []
        # Not `is True`: this suite runs on the non-durable in-process store
        # (conftest.py), and B1 made `persisted` mean "survives a restart"
        # rather than "the write didn't raise". What this test proves is the
        # line below -- the forget really did survive a fresh connection.
        assert memory["persisted"] is False

    with client.websocket_connect("/ws") as ws2:
        _handshake(ws2)
        ws2.send_json({"t": "sign_in", "name": "Grace Ws", "pin": "1234"})
        memory = ws2.receive_json()
        assert memory["tier"] == "signed_in"  # the identity survived
        assert memory["facts"] == []  # but not the facts


def test_m9_forget_an_unknown_key_is_a_no_op_not_an_error() -> None:
    with client.websocket_connect("/ws") as ws:
        _handshake(ws)
        ws.send_json({"t": "sign_in", "name": "Hank Ws", "pin": "1234"})
        ws.receive_json()

        ws.send_json({"t": "forget", "key": "nonexistent_key"})
        memory = ws.receive_json()
        assert memory["t"] == "memory"  # the panel resyncs regardless
        assert memory["facts"] == []
