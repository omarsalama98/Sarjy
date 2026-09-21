"""WebSocket message protocol -- the contract every later block extends.

Every message is JSON on the text channel except audio, which is raw binary
frames on the same socket (PCM16 mono: 16 kHz client->server, 24 kHz
server->client). Server messages always carry `seq` (monotonic per SESSION,
not per connection -- it is the visible proof a reconnect resumed the same
session) and `ts_ms` (wall clock, for display only; Block 3's latency
measurement uses monotonic clocks -- time.monotonic() server-side,
performance.now() client-side -- and never reuses this field).

Validation happens at exactly one boundary: `parse_client_message()`, via a
pydantic v2 discriminated union on `t` with `extra="forbid"`. Nothing else
in this app parses raw client input -- the user's speech is untrusted (see
.claude/rules/tools/grounding-gate.md); so is the user's JSON.

Block 2 adds start/end/barge (client-driven turn boundaries -- the user
taps or releases to end a turn, not the server) and
transcript/reply/audio_start/audio_end/turn_failed (the server's half of a
turn). Binary frames carry no turn id, which is why audio_start/audio_end
exist: they tell the client which turn a run of binary frames belongs to.

Block A (the deep dive) adds `segments` (the gated answer, one entry per
register, kept AND rejected -- rejection visibility is the demo), `quota`
(the vendor request ledger), and `fact_card` (D15's payload; Block A emits
it, Block C renders it -- nothing paints it yet).

Block B (memory) adds three client->server messages (`sign_in`, `sign_out`,
`forget`) and one server->client message (`memory`) -- the "what Sarjy
remembers" panel is driven entirely by that one message, sent after `ready`,
after any sign-in attempt (success or refusal), after sign-out, after a
forget, and after any extraction that changed something. See
app/memory/store.py for the record it is rendered from.

A server->client `timings` message stays reserved and unbuilt: the client
already knows its own headline number (it computed the legs it's sending),
so no round trip back is needed to show it on screen.

Block C adds `lang` to `StartIn` -- Arabic rung 1 (docs/plans/blocks/
C-demoable.md, D5/D6). Additive and defaulted ("en"), so PROTOCOL_VERSION
does NOT move (D7): an old client omitting the field and a new server
reading it are wire-compatible in both directions, and a version bump here
would only add a deadline-day failure mode for no wire-compatibility gain.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

# Bumped from 4: this block adds sign_in/sign_out/forget (c->s) and memory
# (s->c) to the wire. A stale tab left open fails the handshake cleanly ("A
# new version is available -- reload.") instead of sending messages the old
# server half-understands. frontend/src/protocol.ts's own constant moves in
# the SAME commit -- a mismatch here fails every handshake.
PROTOCOL_VERSION = 5

# StartIn.lang stays on the wire (default "en") so a later Arabic pass does
# not bump PROTOCOL_VERSION. The demo UI always sends "en"; get_tts() is
# Deepgram regardless. PROTOCOL_VERSION stays 5 because the field is additive.
Lang = Literal["en", "ar"]


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


class StartIn(BaseModel):
    """Opens a turn. The client has already decided speech began -- the
    user tapped or held the mic -- and `end` arrives when they tap again
    or release. `turn_id` is client-minted and monotonic within a session
    so a stale reply racing a barge can be told apart from the current one."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["start"]
    turn_id: str
    client_ts_ms: int
    lang: Lang = "en"  # additive, defaulted -- see module docstring on PROTOCOL_VERSION


class EndIn(BaseModel):
    """Closes a turn. `samples` is the client's own count of PCM16 samples
    sent, for main.py to cross-check against what actually arrived."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["end"]
    turn_id: str
    samples: int
    client_ts_ms: int


class BargeIn(BaseModel):
    """The user started talking over a response in progress. One code path
    handles this and an implicit barge (a new `start` while a turn is still
    running) -- see main.py."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["barge"]
    turn_id: str


class ClientTimingIn(BaseModel):
    """The two legs only the browser can see -- endpointing and first audio
    out -- plus the VAD setting that produced them. Sent once per turn, at
    the first of: first audio buffer scheduled, or turn_failed (App.tsx's
    reportTurnTiming enforces exactly one send). `endpoint_ms` and
    `first_audio_ms` are nullable because a barge before any audio ever
    played means neither leg completed -- the record still gets sent so
    main.py's merge has something to key off `turn_id` with."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["client_timing"]
    turn_id: str
    endpoint_ms: int | None
    first_audio_ms: int | None
    redemption_ms: int
    output_latency_ms: int | None


class SignInIn(BaseModel):
    """Typed sign-in -- name + 4-digit PIN, the minimum identity needed to
    demonstrate requirement #2 across a reload (D3). Voice sign-in (D8) is a
    deterministic sub-flow in app/pipeline/turn.py; this message is the
    reliable path either way, since a spoken PIN is the weaker channel."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["sign_in"]
    name: str = Field(min_length=1, max_length=32)
    pin: str = Field(pattern=r"^\d{4}$")


class SignOutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: Literal["sign_out"]


class ForgetIn(BaseModel):
    """`key=None` forgets every fact but keeps the signed-in identity (name/
    pin_hash) -- the panel's "Forget everything" button. A per-fact `x` was
    cut (D9's cut ladder item 3); this message's `key` field already
    supports it if that ever gets added back."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["forget"]
    key: str | None = Field(default=None, max_length=32)


ClientMessage = Annotated[
    HelloIn
    | PingIn
    | ByeIn
    | StartIn
    | EndIn
    | BargeIn
    | ClientTimingIn
    | SignInIn
    | SignOutIn
    | ForgetIn,
    Field(discriminator="t"),
]

_client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def parse_client_message(
    raw: str | bytes,
) -> (
    HelloIn
    | PingIn
    | ByeIn
    | StartIn
    | EndIn
    | BargeIn
    | ClientTimingIn
    | SignInIn
    | SignOutIn
    | ForgetIn
):
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


class TranscriptOut(BaseModel):
    """What Groq heard. Sent before the LLM is called, so the reviewer sees
    proof of what was transcribed even if everything after this fails."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["transcript"] = "transcript"
    turn_id: str
    text: str
    seq: int
    ts_ms: int


class ReplyOut(BaseModel):
    """The LLM's text answer -- sent before audio_start. F11's whole point:
    if TTS then fails, the reviewer already has the answer on screen."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["reply"] = "reply"
    turn_id: str
    text: str
    seq: int
    ts_ms: int


class AudioStartOut(BaseModel):
    """Arms the client's playback queue. Binary frames carry no turn id, so
    this and audio_end are how the client knows which turn a run of binary
    frames belongs to, and at what sample rate to schedule them."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["audio_start"] = "audio_start"
    turn_id: str
    sample_rate: int
    seq: int
    ts_ms: int


class AudioEndOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: Literal["audio_end"] = "audio_end"
    turn_id: str
    samples: int
    seq: int
    ts_ms: int


TurnFailedStage = Literal["audio", "stt", "llm", "tool", "gate", "tts"]


class TurnFailedOut(BaseModel):
    """`message` is user-facing prose, shown on screen verbatim -- not
    spoken in this block (that would need a TTS call inside the TTS failure
    path). See docs/plans/blocks/02-voice-loop.md, Failure paths."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["turn_failed"] = "turn_failed"
    turn_id: str
    stage: TurnFailedStage
    message: str
    seq: int
    ts_ms: int


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


GateReasonOut = Literal[
    "unknown_tool_call_id",
    "absent_path",
    "field_mismatch",
    "no_placeholder",
    "bare_digit",
    "number_word",
    "value_too_long",
    "field_not_allowlisted",
    "wrong_pair",
    "quote_not_allowlisted",
    "quoted_text_supplied",
    "injection_marker",
    "too_many_quotes",
    "malformed_line",
]

ToolLayerOut = Literal["live", "cache", "map", "csv"]


class SegmentOut(BaseModel):
    """One rendered segment, kept OR rejected -- `ok=False` is still sent
    and shown struck through with its `reason`. That visibility is the
    demo (F3 in the block plan's Gate section)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["sourced", "quoted", "judgement"]
    text: str
    ok: bool
    reason: GateReasonOut | None
    attribution: str | None  # quoted only: 'According to Travel Buddy:'
    field: str | None  # quoted only: the path the words came from
    citation: str | None
    source_url: str | None
    source_date: str | None
    layer: ToolLayerOut | None


class SegmentsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: Literal["segments"] = "segments"
    turn_id: str
    segments: list[SegmentOut]
    spoken: str  # EXACTLY the string handed to TTS -- the proof, on screen
    hedged: bool  # a tool result existed and zero sourced AND zero quoted segments came back (D4)
    seq: int
    ts_ms: int


class QuotaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: Literal["quota"] = "quota"
    total: int
    spent: int
    reserve: int
    remaining: int
    seq: int
    ts_ms: int


class FactRowOut(BaseModel):
    """D15. Named `FactRowOut` (not `FactRow`) to keep this module's
    convention -- every wire type ends in `Out` -- consistent; app.tools.card
    has its own plain-dataclass `FactRow` that this mirrors at the boundary."""

    model_config = ConfigDict(extra="forbid")

    path: str  # "visa.duration" -- the SAME path the gate substitutes from
    label: str  # "Maximum stay"
    value: str  # the SAME string the gate would substitute
    # `kind`, not `register`: it matches Segment.kind's vocabulary on the same
    # wire, and `register` shadows ABCMeta.register on BaseModel's metaclass,
    # which made Pydantic print a UserWarning on every single app start.
    kind: Literal["sourced", "quoted"]


class FactCardOut(BaseModel):
    """Block A emits this. Block C renders it -- nothing paints it yet
    (see the block plan's Out table: rendering the card is explicitly not
    in scope here)."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["fact_card"] = "fact_card"
    turn_id: str
    passport: str
    passport_name: str
    destination: str
    destination_name: str
    covered: bool  # False = pair resolved, no layer had it (refusal card)
    facts: list[FactRowOut]
    layer: ToolLayerOut | None
    degraded: bool  # layer in {map, csv}
    source_name: str | None
    source_url: str | None
    source_date: str | None  # the SOURCE's own date
    retrieved: str | None  # ours, ISO 8601 Z
    embassy_url: str | None  # the refusal route
    seq: int
    ts_ms: int


PlaceReasonOut = Literal["not_found", "disambiguation", "no_image", "timeout", "http_error"]


class PlaceCardOut(BaseModel):
    """One Wikimedia lookup. `ok=False` is still sent -- never a silent drop,
    never a broken image. Additive: old clients ignore an unknown `t`."""

    model_config = ConfigDict(extra="forbid")

    name: str
    title: str | None
    description: str | None
    image_url: str | None
    page_url: str | None
    revision_date: str | None
    ok: bool
    reason: PlaceReasonOut | None


class PlacesOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t: Literal["places"] = "places"
    turn_id: str
    places: list[PlaceCardOut]
    seq: int
    ts_ms: int


class FactOut(BaseModel):
    """One stored fact, on the wire -- the panel's whole reason to exist
    (D1). `quote` is the attribution: the verbatim sentence that taught it,
    so "how do you know that?" is answered on screen, not in a console.

    `kind`, not `register`: matching FactRowOut's own note above -- `register`
    shadows ABCMeta.register on Pydantic's BaseModel metaclass and prints a
    UserWarning on every app start."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: str
    kind: Literal["profile", "open"]
    learned_at: str  # ISO 8601 Z
    turn_id: str | None
    quote: str | None


class MemoryOut(BaseModel):
    """Drives the ENTIRE "what Sarjy remembers" panel -- there is no
    client-side memory state to drift, because every change (sign-in,
    sign-out, forget, extraction) re-sends this whole record rather than a
    diff. Sent after `ready`, and again after each of those four events."""

    model_config = ConfigDict(extra="forbid")

    t: Literal["memory"] = "memory"
    tier: Literal["anonymous", "signed_in"]
    name: str | None  # display name; null when anonymous
    facts: list[FactOut]
    used: int
    capacity: int
    persisted: bool  # this record is backed by modal.Dict right now
    degraded: bool  # the last durable write failed
    message: str | None  # panel line: sign-in refused, degraded, too many tries
    seq: int
    ts_ms: int


ServerMessage = (
    ReadyOut
    | StateOut
    | PongOut
    | ErrorOut
    | ClosingOut
    | TranscriptOut
    | ReplyOut
    | AudioStartOut
    | AudioEndOut
    | TurnFailedOut
    | SegmentsOut
    | QuotaOut
    | FactCardOut
    | PlacesOut
    | MemoryOut
)
