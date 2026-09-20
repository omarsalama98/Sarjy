"""WebSocket message protocol -- the contract every later block extends.

Every message is JSON on the text channel; binary frames are audio and are
rejected until Block 2 (see main.py). Server messages always carry `seq`
(monotonic per SESSION, not per connection -- it is the visible proof a
reconnect resumed the same session) and `ts_ms` (wall clock, for display
only; Block 3's latency measurement uses monotonic clocks and must not
reuse this field).

Validation happens at exactly one boundary: `parse_client_message()`, via a
pydantic v2 discriminated union on `t` with `extra="forbid"`. Nothing else
in this app parses raw client input -- the user's speech is untrusted (see
.claude/rules/tools/grounding-gate.md); so is the user's JSON.

Reserved for later blocks -- named here so the envelope never needs a
redesign, but NOT implemented yet (docs/plans/blocks/01-skeleton-deploy.md,
"Reserved" table):
    start / end / barge   c->s, Block 2 -- client VAD drives all three
    (binary)              both, Block 2 -- 16kHz PCM16 in, 24kHz PCM out
    transcript            s->c, Block 2
    timings               s->c, Block 3
    segments              s->c, Block 4/6 -- gated, cited
    quota                 s->c, Block 5
    memory                s->c, Block 7
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

PROTOCOL_VERSION = 1


# ---------------------------------------------------------------------------
# Client -> server
# ---------------------------------------------------------------------------


class HelloIn(BaseModel):
    """First message on every connection, including reconnects.

    `session_id` is null on a cold start and the previously issued id on a
    reconnect. The server never trusts this id blindly -- an unknown one
    mints a fresh session rather than adopting the client's guess.
    """

    model_config = ConfigDict(extra="forbid")

    t: Literal["hello"]
    v: int
    session_id: str | None
    client_ts_ms: int


class PingIn(BaseModel):
    """Liveness probe. Also what the UI's manual Ping button sends -- one
    mechanism, two callers."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["ping"]
    id: str
    client_ts_ms: int


class ByeIn(BaseModel):
    """Not politeness -- capacity. Lets the server end the Modal input
    immediately instead of holding a concurrency slot for the ~2 minutes
    S1 measured before a dead socket is noticed on its own."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["bye"]
    reason: Literal["rotate", "leave"]


ClientMessage = Annotated[HelloIn | PingIn | ByeIn, Field(discriminator="t")]

_client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(raw: str | bytes) -> HelloIn | PingIn | ByeIn:
    """The one boundary function -- nothing else parses raw client input.

    Raises pydantic.ValidationError for anything invalid, including JSON
    that doesn't parse at all (pydantic-core reports that as a ValidationError
    too, so one except clause covers both "not JSON" and "wrong shape").
    """
    return _client_message_adapter.validate_json(raw)


# ---------------------------------------------------------------------------
# Server -> client
# ---------------------------------------------------------------------------


class ReadyOut(BaseModel):
    """Reply to `hello`. `resumed` and `connection_n` are the visible proof
    a reconnect carried the same session forward -- this block's thesis, on
    the wire."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["ready"] = "ready"
    v: int
    session_id: str
    resumed: bool
    connection_n: int
    rotate_after_ms: int
    hard_max_ms: int
    server_started_at_ms: int
    seq: int
    ts_ms: int


ConversationValue = Literal["idle", "listening", "thinking", "speaking"]


class StateOut(BaseModel):
    """The conversation state machine. Block 1 only ever sends "idle" -- the
    other values are reserved so Block 2 has somewhere to put them, and so
    the reserved space is real rather than promised."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["state"] = "state"
    value: ConversationValue
    seq: int
    ts_ms: int


class PongOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: Literal["pong"] = "pong"
    id: str
    client_ts_ms: int
    seq: int
    ts_ms: int


ErrorCode = Literal["bad_message", "protocol_version", "unsupported", "internal"]


class ErrorOut(BaseModel):
    """A malformed message never closes the socket -- one bad frame must not
    cost a conversation. The one exception is a missing/invalid `hello` as
    the first message, which main.py closes directly rather than erroring."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["error"] = "error"
    code: ErrorCode
    message: str
    recoverable: bool
    seq: int
    ts_ms: int


ClosingReason = Literal["rotate_ceiling", "shutdown", "superseded", "protocol_version"]


class ClosingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: Literal["closing"] = "closing"
    reason: ClosingReason
    reconnect: bool
    seq: int
    ts_ms: int


ServerMessage = ReadyOut | StateOut | PongOut | ErrorOut | ClosingOut
