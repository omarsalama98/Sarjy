# Block 3 — Instrumentation

**Date:** 2026-09-20 · **Needs:** Block 2 (done, deployed) · **Feeds:** Blocks 4, 5, 6, 9, 11
**Master plan:** `docs/plans/MASTER-PLAN.md` §Block 3 · **Cut to 0.5 h by** `docs/plans/CUT-DECISION.md`
**Governing rules:** `.claude/skills/measure/SKILL.md` (the stage table is the spec) · `.claude/rules/voice/pipeline.md` · `AGENTS.md` §Invariant 2

---

## Summary — read this page

**Goal.** Every turn emits **one correlated, structured timing record** covering the whole chain — the client's two legs included — and the deployment can be reduced to a **median over ten real turns** with one command.

Today the numbers exist as three uncorrelated `logger.info` lines (`stt_ms`, `llm_first_text_delta_ms`, `tts_ttfb_ms`) that nothing ties to a turn, and the two legs that decide what the user actually feels — **endpointing** and **first audio out** — are not measured at all. `make measure` is declared in `AGENTS.md` and **is broken**: it runs `python -m app.measure`, which does not exist.

**The four things that decide this block:**

| # | The thing | Why it decides the block |
|---|---|---|
| 1 | **The headline number can only be measured in the browser** | "User stops speaking → first audible sound" starts at an acoustic event the server never sees and ends at a buffer the server never hears. The client measures both legs and sends them; the server merges. That merge *is* the instrument, not polish. |
| 2 | 🪤 **TTFT is timed to the first `delta.type == "text"`, never the first SSE event** | A `thought` step always arrives first, even at `thinking_level: "minimal"`. **Already correct** in `gemini_llm.py:84–95` — verified by reading it. Block 3's job is to stop that number being thrown away, not to re-derive it. |
| 3 | **Fields for stages that do not exist yet are emitted as `null`, never omitted** | `opener_ready_ms`, `tool_ms`, `gate_ms`, `answer_gap_ms` belong to Blocks 4/5/6. Reserving them now is the entire reason for instrumenting before optimising — a record retrofitted in Block 6 tells you nothing about what Block 2 built. |
| 4 | **Clocks are never crossed** | Client legs are deltas between two `performance.now()` reads; server legs are deltas between two `time.monotonic()` reads. No client timestamp is ever subtracted from a server timestamp. That is why this record can be trusted without a skew correction. `ts_ms` (wall clock, display only) is never used for timing — `protocol.py`'s own docstring already says so. |

**What lands:** `turn_timings {...}` — one JSON line per turn in the server log · a `client_timing` client→server message · `backend/app/measure.py` + a working `make measure` · **one line** of on-screen text showing the last turn's voice-to-voice number, the endpoint delay and the `redemptionMs` in force.

**What does not land:** a synthetic-turn harness · a metrics HTTP endpoint · a timings panel, chart or history in the UI · a server→client `timings` message (stays reserved) · any optimisation of anything measured here.

⚠️ **The 0.5 h cut is not achievable as specified.** Honest estimate **~1.3 h** (see §The estimate, honestly). The cut ladder in that section is pre-committed so the overrun is decided now rather than at midnight.

---

## Goal

One sentence: **after this block, every turn prints a single correlated timing record covering endpointing → upload → STT → LLM TTFT → TTS TTFB → first audible sound, with the not-yet-built stages reserved as `null`, and `make measure` turns ten of those records into a median table against the deployment.**

---

## Scope

### In

| # | Thing |
|---|---|
| 1 | `TurnTimings` — the record type, every field named now, including the reserved ones |
| 2 | Server legs measured **at the call site** in `run_turn()`: `stt_ms`, `llm_ms`, `llm_ttft_ms`, `tts_ttfb_ms`, `tts_total_ms` |
| 3 | `upload_ms` and `server_ms`, measured in `main.py` where `start`/`end`/the first audio byte actually happen |
| 4 | `LLMReply` — the LLM adapter returns its TTFT alongside the text instead of logging it into the void |
| 5 | `model` (and `thinking_level` on `LLM`) on the provider Protocols, so a record says what it measured |
| 6 | `client_timing` — a new client→server message carrying `endpoint_ms`, `first_audio_ms`, `redemption_ms`, `output_latency_ms` |
| 7 | The merge: the record is printed when **both** sides are done, with three flush paths for when the client never reports |
| 8 | `backend/app/measure.py` + `make measure` — reads `turn_timings` lines from stdin or a file, prints median/p95 per stage, writes `docs/measurements/{date}-{label}.md` |
| 9 | **One line** of on-screen text: `last turn 1.83 s voice-to-voice · endpoint 0.58 s · redemption 600 ms` |
| 10 | `PROTOCOL_VERSION` 2 → 3, both sides |
| 11 | `SARJY_ENV` on the Modal image, so a record says whether it ran local or deployed |
| 12 | Tests: failure paths first, then the fills, then `measure.py`'s aggregation |
| 13 | The measurement run itself: 10 turns against the deployment, `make measure`, the doc, the interpretation paragraph |

### Out — say no to all of these

| Out | Owner |
|---|---|
| A harness that drives synthetic turns (`scratch/spikes/block2/deployed_turn.py` already exists for smoke-testing; it is not `make measure`) | nobody — deliberately not built |
| A `/metrics` HTTP endpoint, a p95 dashboard, a Prometheus anything | nobody |
| Any UI beyond the one line: no panel, no chart, no per-turn history, no styling | Block 8, **which was cut to zero** — so nothing later adds it. One line is the whole allowance |
| The reserved server→client `timings` message | stays reserved; the client already knows its own headline number, so no round trip is needed |
| Optimising anything this block measures (shorter opener, streaming upload, a faster model) | Block 4 onward — a finding here is a finding, not a task |
| `opener_ready_ms`, `tts1_ttfb_ms`, `tool_ms`, `llm2_ms`, `gate_ms`, `answer_gap_ms` **values** | Blocks 4/5/6 — the **fields** land here, as `null` |
| Choosing the final `redemptionMs` value | Omar, at a microphone — this block ships the instrument and the procedure (§The endpointing sweep) |
| Arabic, memory, tools, the gate | Blocks 10/7/4/6 |

---

## What already exists — verified by reading, not assumed

| Claim | Status |
|---|---|
| `stt_ms` logged at `providers/groq_stt.py:44` | ✅ exists, uncorrelated, timed after the WAV wrap |
| `llm_first_text_delta_ms` at `providers/gemini_llm.py:84` | ✅ exists, uncorrelated, **and it is timed correctly** — `event.event_type != "step.delta"` then `delta.type != "text"`, both skipped before the clock is read. Trap 2 is already closed; do not "fix" it |
| `tts_ttfb_ms` at `providers/deepgram_tts.py:83` | ✅ exists, uncorrelated, **and it excludes the Deepgram WebSocket connect** — `t_flush_sent` is taken *inside* `async with websockets.connect(...)`. The 85 ms median in `docs/measurements/block2-voice-loop.md` is therefore TTFB-after-connect, **not** what the user waits for |
| `turn_id` + `client_ts_ms` on `StartIn` / `EndIn` | ✅ exists in `pipeline/protocol.py`. Correlation reuses `turn_id`; **no new id is invented** |
| `logging.basicConfig()` at `main.py:66` | ✅ wired — without it every `logger.info` was swallowed |
| `make measure` | 🚨 **broken.** `backend/Makefile` runs `uv run python -m app.measure`; `backend/app/measure.py` does not exist. `AGENTS.md` §Commands declares the command. This block makes it real |
| Endpointing instrument in `frontend/src/audio/turn.ts` | ✅ `onFrameProcessed` records `lastSpeechFrameAt`; `onSpeechEnd` computes the delay and **`console.log`s it**. It goes nowhere else. This block routes it into the record |
| `?redemptionMs=` URL override, `getRedemptionMs()` | ✅ exists and is exported |
| `speakingStartedAtRef.current = performance.now()` in `App.tsx`'s `beginTurn` callback | ✅ exists — it already marks the instant the **first buffer is scheduled**, which is the end of the headline leg |
| Block 2 baselines, n=5, deployed | `stt_ms` median 296 · `llm_first_text_delta_ms` median 30 · `tts_ttfb_ms` median 85 (after-connect) |

---

## Contracts

### 1. The record — `backend/app/pipeline/timings.py` (new)

Pydantic, `extra="forbid"`, **no field ever omitted** (`model_dump_json()` with no `exclude_none`). Copy these names exactly; `measure.py`, Blocks 4–6 and the writeup all key off them.

```python
LOG_PREFIX = "turn_timings "   # the grep handle. One space, then JSON.

class TurnTimings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # -- identity and configuration -------------------------------------
    turn_id: str
    session: str                  # session_id[:8] ONLY -- never the full id
    connection_n: int
    turn_index: int               # 1-based per container process; turn 1 is the cold one
    env: str                      # "modal" | "local", from SARJY_ENV
    stt_model: str | None = None
    llm_model: str | None = None
    tts_model: str | None = None
    llm_thinking_level: str | None = None
    redemption_ms: int | None = None      # the client VAD setting in force, from client_timing

    # -- outcome --------------------------------------------------------
    outcome: Literal["ok", "failed", "barged", "incomplete"] = "incomplete"
    failed_stage: str | None = None       # TurnFailedStage when outcome == "failed"
    flush_reason: Literal["complete", "next_turn", "connection_closed"] = "complete"
    transcript_chars: int | None = None   # length, NOT the text (see §Secrets)
    reply_chars: int | None = None

    # -- client legs (performance.now() deltas; null if the client never reported)
    endpoint_ms: int | None = None        # last speech frame -> onSpeechEnd fired
    first_audio_ms: int | None = None     # HEADLINE: last speech frame -> first buffer scheduled
    output_latency_ms: int | None = None  # AudioContext.outputLatency, null on Safari

    # -- server legs (time.monotonic() deltas) ---------------------------
    upload_ms: int | None = None          # `start` received -> `end` received
    stt_ms: int | None = None             # around stt.transcribe(), includes the WAV wrap
    llm_ms: int | None = None             # around llm.reply(), request -> full string
    llm_ttft_ms: int | None = None        # to the first delta.type == "text" (see trap 2)
    tts_ttfb_ms: int | None = None        # first pull -> first chunk, INCLUDING the DG connect
    tts_total_ms: int | None = None       # first pull -> last chunk
    server_ms: int | None = None          # `end` received -> first audio byte on the wire

    # -- RESERVED. Emitted as null in this block. Never omit one. ---------
    opener_ready_ms: int | None = None    # Block 4
    tts1_ttfb_ms: int | None = None       # Block 4 -- the OPENER's TTS
    tool_ms: int | None = None            # Block 5
    llm2_ms: int | None = None            # Block 4
    gate_ms: int | None = None            # Block 6
    answer_gap_ms: int | None = None      # Block 4
```

**Naming note Block 4 must honour:** when the opener lands, the opener's TTS goes in `tts1_ttfb_ms` and the **answer's stays in `tts_ttfb_ms`** — i.e. `tts_ttfb_ms` *is* the skill table's "TTS #2 TTFB". Do not rename it; `measure.py` and every earlier measurement key off it.

```python
def elapsed_ms(t0: float) -> int:
    """time.monotonic() delta, rounded to ms."""

def emit(record: TurnTimings) -> None:
    """One line, never raises. A timing record must never break a turn."""
    try:
        logger.info("%s%s", LOG_PREFIX, record.model_dump_json())
    except Exception:
        logger.warning("turn_timings emit failed", exc_info=True)
```

`timings.py` imports pydantic and stdlib only. It must stay safe for `app.main` to import at module level (`main.py`'s docstring: no `app.config`, no provider SDK in that module graph).

### 2. The wire — `backend/app/pipeline/protocol.py` + `frontend/src/protocol.ts`

```python
PROTOCOL_VERSION = 3          # was 2, both sides

class ClientTimingIn(BaseModel):
    """The two legs only the browser can see, plus the VAD setting that
    produced them. Sent once per turn, at the first of: first audio buffer
    scheduled, or turn_failed."""
    model_config = ConfigDict(extra="forbid")

    t: Literal["client_timing"]
    turn_id: str
    endpoint_ms: int | None
    first_audio_ms: int | None
    redemption_ms: int
    output_latency_ms: int | None
```

Added to `ClientMessage`, to `parse_client_message`'s return annotation, and handled in `_serve`'s dispatch chain.

```ts
export const PROTOCOL_VERSION = 3;

export interface ClientTimingMessage {
  t: "client_timing";
  turn_id: string;
  endpoint_ms: number | null;
  first_audio_ms: number | null;
  redemption_ms: number;
  output_latency_ms: number | null;
}
```

Added to the `ClientMessage` union. **No parser change** — `parseServerMessage` only handles server→client.

### 3. The provider boundary — `backend/app/providers/base.py`

```python
@dataclass(frozen=True)
class LLMReply:
    """Text plus the one number only the adapter can see. `reply()` returned
    a bare `str`; TTFT is measured inside the streaming loop and had nowhere
    to go but a log line nothing could correlate."""
    text: str
    first_text_delta_ms: int | None


class STT(Protocol):
    model: str
    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str: ...


class LLM(Protocol):
    model: str
    thinking_level: str | None
    async def reply(self, *, system: str, history: list[tuple[str, str]], user: str) -> LLMReply: ...


class TTS(Protocol):
    model: str
    def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]: ...
```

🪤 **`app/pipeline/turn.py` must never import an adapter module to read a model id.** `main.py` imports `turn.py` at module level; `groq_stt`/`gemini_llm`/`deepgram_tts` each pull a provider SDK, and dragging one into that graph is exactly what F14 and `main.py`'s docstring forbid. The model id reaches the record through the Protocol attribute and no other way.

### 4. `run_turn()` — `backend/app/pipeline/turn.py`

```python
async def run_turn(
    *,
    turn_id: str,
    pcm16: bytes,
    system: str,
    history: list[tuple[str, str]],
    next_seq: Callable[[], int],
    now_ms: Callable[[], int],
    get_stt: Callable[[], STT],
    get_llm: Callable[[], LLM],
    get_tts: Callable[[], TTS],
    timings: TurnTimings,        # NEW, required, keyword-only, no default
) -> AsyncIterator[TurnItem]:
```

Required, not optional: mypy strict then names every call site that forgot it, and the tests get to assert on the record. Fills, in reading order:

| Where | Fill |
|---|---|
| after `stt = get_stt()` | `timings.stt_model = stt.model` |
| around `await stt.transcribe(...)` | `timings.stt_ms = elapsed_ms(t0)` |
| after a successful transcript | `timings.transcript_chars = len(text)` |
| after `llm = get_llm()` | `timings.llm_model = llm.model`, `timings.llm_thinking_level = llm.thinking_level` |
| around `await llm.reply(...)` | `timings.llm_ms = elapsed_ms(t0)`, `timings.llm_ttft_ms = reply.first_text_delta_ms` |
| after the reply is non-empty | `timings.reply_chars = len(reply.text)` |
| after `tts = get_tts()` | `timings.tts_model = tts.model` |
| first chunk out of `async for chunk in audio` | `timings.tts_ttfb_ms = elapsed_ms(t_tts)` where `t_tts` is taken immediately before the `async for` |
| after the loop drains | `timings.tts_total_ms = elapsed_ms(t_tts)` |

`t_tts` is taken **before** the `async for`, not before `tts.synthesize(...)` — calling `synthesize()` only builds the generator; nothing executes until the first pull. Measuring from the pull is what makes `tts_ttfb_ms` include the Deepgram WebSocket handshake, which the adapter's own number excludes and the user does not.

Every fill is a plain attribute assignment on a pydantic model with `validate_assignment` off — it cannot raise, so **no `try/except` goes around a fill**. The only guarded call in the whole feature is `emit()`.

### 5. `main.py` — the merge

`_TurnState` gains:

```python
timings: TurnTimings | None = None
turn_started_at: float = 0.0    # time.monotonic() at `start`
end_received_at: float = 0.0    # time.monotonic() at `end`
server_done: bool = False
client_done: bool = False
```

Module level: `TURN_INDEX` counter (a plain `itertools.count(1)` or an int guarded by nothing — one container, one event loop, no lock needed; say so in a comment) and `SARJY_ENV = os.environ.get("SARJY_ENV", "local")`.

Two functions, both sync, both tiny:

```python
def _maybe_emit_timings(turns: _TurnState) -> None:
    """Prints the record once both halves of the turn are done -- the
    server's last audio chunk and the client's first audible sound. Neither
    side alone knows the whole chain."""

def _flush_timings(turns: _TurnState, reason: Literal["next_turn", "connection_closed"]) -> None:
    """Prints an incomplete record rather than losing it. The client leg can
    legitimately never arrive: a barge before any audio, a closed tab, a
    stale bundle."""
```

Call sites, exhaustively:

| Site | Action |
|---|---|
| `_handle_start`, first line | `_flush_timings(turns, "next_turn")` — the previous turn's record, if the client never reported |
| `_handle_start`, after | build the record: `turn_id`, `session=session.session_id[:8]`, `connection_n`, `turn_index`, `env`; `turns.turn_started_at = time.monotonic()` |
| `_handle_end` | `turns.end_received_at = time.monotonic()`; `timings.upload_ms = elapsed_ms(turns.turn_started_at)` |
| `_process_turn`, first `bytes` item | `if timings.server_ms is None: timings.server_ms = elapsed_ms(turns.end_received_at)` |
| `_process_turn`, on `TurnFailedOut` | `outcome = "failed"`, `failed_stage = item.stage` |
| `_process_turn`, generator drained with no failure | `outcome = "ok"` |
| `_process_turn`, `except asyncio.CancelledError` | `outcome = "barged"` **before** the `raise` (sync assignment only — never `await` in a cancellation handler) |
| `_process_turn`, `finally` | `turns.server_done = True; _maybe_emit_timings(turns)` — one place covers the superseded-mid-turn early `return` too |
| `_handle_client_timing` | fill the four client fields, `turns.client_done = True`, `_maybe_emit_timings(turns)` |
| `_serve`'s existing `finally` | `_flush_timings(turns, "connection_closed")` after `_cancel_active_turn` |

`_process_turn` takes `turns: _TurnState` as a new parameter — it is created in `_handle_end` inside the same connection scope, and a turn never spans a connection (Block 1's invariant), so nothing here needs to survive a reconnect.

### 6. `backend/app/measure.py` (new) + the Makefile

```
usage: python -m app.measure [--label LABEL] [--redemption MS] [--out PATH] [FILE]
```

- Reads `FILE`, or stdin when no file is given.
- Per line: locate `turn_timings ` and `TurnTimings.model_validate_json(rest)`. Reusing the model is the point — `extra="forbid"` means a drifted schema is caught here rather than silently averaging a missing field.
- **De-dupes** on `(session, turn_id, turn_index)`. Overlapping `--since` windows otherwise double-weight a turn.
- Aggregates **only `outcome == "ok"`** records, and prints the excluded count by outcome. A turn that failed at STT has no TTS leg and would wreck the median.
- Header block: `n`, date, source, and the distinct values of `env`, `redemption_ms`, `stt_model`, `llm_model`, `tts_model`, `llm_thinking_level`. **If any of those has more than one distinct value, print a `MIXED CONFIGURATION` warning above the table** — a stage table averaged across two configs is the anti-pattern the measure skill names by name.
- Stage table, fixed order, one row each: `endpoint_ms`, `upload_ms`, `stt_ms`, `llm_ttft_ms`, `llm_ms`, `tts_ttfb_ms`, `tts_total_ms`, `server_ms`, **`first_audio_ms` (headline, last)**. Columns: `n`, `median`, `p95` (nearest-rank: `sorted[min(len-1, ceil(0.95*len)-1)]`), `min`, `max`. Nulls skipped per row, so `n` is per stage.
- **`residual_ms`**, computed per record where all of `first_audio_ms, endpoint_ms, upload_ms, stt_ms, llm_ms, tts_ttfb_ms` are present:
  `residual = first_audio_ms - (endpoint_ms + upload_ms + stt_ms + llm_ms + tts_ttfb_ms)`.
  Reported as its own row. The stage chain is strictly sequential in this block, so the residual is real unaccounted time: `onSpeechEnd` → `ensureFresh()` (which can rotate the socket) → `start` on the wire, plus the server→client audio hop and playback scheduling. **The gap is a finding, and chasing it is Block 4's business, not this block's.** ⚠️ This subtraction stops being valid in Block 4, when the opener makes the chain concurrent — say so in the generated doc.
- Writes markdown to `--out`, default `docs/measurements/{YYYY-MM-DD}-{label}.md` (`label` defaults to `run`), resolved from `Path(__file__).resolve().parents[2] / "docs" / "measurements"`. Leaves an `## Interpretation` heading with a `_to be written by hand_` placeholder — the skill requires naming the largest term and what you would do about it, and a script cannot do that.

Makefile:

```make
# Latency measurement run -> docs/measurements/
# Usage: modal app logs sarjy --since 30m --tail 2000 | make measure ARGS="--label deployed-baseline"
#    or: make measure ARGS="--label local /tmp/sarjy.log"
measure:
	uv run python -m app.measure $(ARGS)
```

✅ Verified against the installed modal 1.5.5 client (`modal app logs --help`): **`modal app logs` fetches the last 100 entries and exits by default** — `-f` is what streams. So the pipe terminates, and `--since 30m --tail 2000` is a safe capture for a ten-turn run.

### 7. The one line of UI — `frontend/src/App.tsx`

```tsx
{lastTurn && (
  <p className="metrics" aria-live="off">
    last turn {fmt(lastTurn.firstAudioMs)} voice-to-voice · endpoint {fmt(lastTurn.endpointMs)}
    {" · redemption "}{lastTurn.redemptionMs} ms
  </p>
)}
```

`fmt` renders `1.83 s` (two decimals) or `—` when null. `aria-live="off"` is deliberate: a screen reader announcing a latency figure after every turn is noise, and the value is diagnostic, not conversational. **One line. No panel, no history, no chart, no CSS** — there is no stylesheet in this project and this block does not add one.

### 8. Frontend plumbing

`frontend/src/audio/turn.ts` — the callback grows one argument:

```ts
export interface EndpointTiming {
  endpointMs: number;      // last frame above POSITIVE_SPEECH_THRESHOLD -> onSpeechEnd
  acousticEndAtMs: number; // that frame's performance.now(), so App can close the headline leg
  redemptionMs: number;
}

onUtterance(pcm: ArrayBuffer, sampleRate: number, durationMs: number, endpoint: EndpointTiming): void;
```

Built from the values already computed in `onSpeechEnd`. **Keep the existing `console.log`** — it is what makes the sweep runnable without the UI.

`frontend/src/net/connection.ts`:

```ts
sendClientTiming(m: Omit<ClientTimingMessage, "t">): void   // -> this.send({ t: "client_timing", ...m })
```

`frontend/src/App.tsx`:

- `turnTimingRef: useRef<{ turnId: string; acousticEndAtMs: number; endpointMs: number; redemptionMs: number; sent: boolean } | null>` — set in `handleUtterance` after the turn id is minted. `acousticEndAtMs` is a timestamp from the past, so awaiting `ensureFresh()` first cannot corrupt it.
- `reportTurnTiming(turnId: string, firstAudioMs: number | null)` — returns early unless the ref exists, matches `turnId`, and `sent === false`; sets `sent = true`; sends; and `setLastTurn(...)` for the on-screen line. **Exactly one send per turn**, enforced here.
- Called from **two** places: inside the existing `playbackQueueRef.current?.beginTurn(() => ...)` callback (alongside `speakingStartedAtRef.current = performance.now()`), with `firstAudioMs = Math.round(performance.now() - ref.acousticEndAtMs)`; and from `onTurnFailed`, with `null`.
- `output_latency_ms`: 🪤 `lib.dom.d.ts` types `AudioContext.outputLatency` as `readonly outputLatency: number`, but **Safari does not implement it** and returns `undefined` at runtime. Guard with `Number.isFinite(ctx.outputLatency) ? Math.round(ctx.outputLatency * 1000) : null` and comment *why* the guard looks redundant to the type checker.

---

## Failure paths — build these before the happy path

| # | Case | Defined, visible behaviour |
|---|---|---|
| **I1** | `emit()` raises (a field that will not serialise, a logging handler blowing up) | Caught inside `emit`; `logger.warning("turn_timings emit failed", exc_info=True)`; **the turn continues and the user notices nothing.** Asserted by a test that monkeypatches `model_dump_json` to raise |
| **I2** | The client never sends `client_timing` (barge before any audio, tab closed, stale bundle) | The record is still printed — client legs `null`, `flush_reason` = `next_turn` or `connection_closed`. **A turn never produces zero records** |
| **I3** | `client_timing` arrives for an unknown or stale `turn_id` (a barge racing a reconnect) | Ignored. `logger.info("client timing for unknown turn %s", ...)`. **No `bad_message`, no exception** — this is a legitimate race, not a client bug |
| **I4** | The turn fails at STT / LLM / TTS | Record printed with `outcome="failed"`, `failed_stage` set, later stages `null`. `measure.py` **excludes it from every median** and reports the count separately |
| **I5** | `make measure` with no file and stdin attached to a terminal | Prints usage, exits 2. **Never blocks on a tty** — a declared command that hangs is worse than one that fails |
| **I6** | A truncated or interleaved log line, or a line whose JSON no longer matches the model | Skipped, counted, reported as `skipped: N malformed`. Aggregation never crashes on one bad line |
| **I7** | Zero `ok` records in the input | Prints `no turn_timings records found in N lines`, exits 1, **writes no document**. An empty measurement file is worse than none |
| **I8** | A stale browser tab on protocol v2 | The existing handshake path rejects it: `error{code:"protocol_version"}` then `closing{reconnect:false}` → *"A new version is available — reload."* Unchanged code; re-verified because the constant moved |
| **I9** | `measure.py` fed records with two different `redemption_ms` (or `env`, or a model id) | `MIXED CONFIGURATION` warning printed above the table, listing the distinct values. The table is still printed — the warning is what stops it being quoted |

---

## Traps, restated because they will not be remembered

1. 🪤 **TTFT is to the first `delta.type == "text"`.** `gemini_llm.py` already does this correctly. The risk in this block is a refactor of `reply()` that loses the skip conditions. If `llm_ttft_ms` comes back near-zero *and* `llm_ms` is large, the skip was lost and the number is a fiction.
2. 🪤 **`turn.py` must not import a provider adapter.** Model ids come off the Protocol attribute. An `from app.providers.gemini_llm import MODEL` in `turn.py` puts the genai SDK into `main.py`'s import graph and can take `/health` and the static mount down with it — requirement #4, lost to a model id.
3. 🪤 **`ts_ms` is wall clock and display-only.** `protocol.py`'s docstring says Block 3 must not reuse it. Every timing in this block is a monotonic delta.
4. 🪤 **Do not subtract a client timestamp from a server timestamp.** `client_ts_ms` exists on `StartIn`/`EndIn` for correlation and cross-checks, not for latency arithmetic. There is no clock-sync protocol here, and skew would silently swamp `upload_ms`.
5. 🪤 **The adapter's `tts_ttfb_ms` and the record's `tts_ttfb_ms` are different numbers.** The adapter's excludes the Deepgram WebSocket handshake. Rename the adapter's log key to `tts_ttfb_after_connect_ms` (one line) so the 85 ms figure from Block 2 can never be quoted as a user-facing number by accident.
6. 🪤 **`AudioContext.outputLatency` is typed as `number` and is `undefined` on Safari.**
7. 🪤 **`extra="forbid"` on `TurnTimings` means a typo'd attribute assignment raises at runtime.** That is desirable (mypy catches it first), but it is one more reason `emit()` is the only guarded call: assignments are validated by mypy at build time, not by pydantic at run time.

---

## Files

### Created

| File | Purpose |
|---|---|
| `backend/app/pipeline/timings.py` | `TurnTimings`, `LOG_PREFIX`, `elapsed_ms()`, `emit()` |
| `backend/app/measure.py` | Reads `turn_timings` lines, aggregates, prints the table, writes the doc. Makes `make measure` real |
| `backend/tests/test_timings.py` | Fills, failure paths I1/I4, the emit guard |
| `backend/tests/test_measure.py` | Aggregation, de-dupe, I6/I7/I9 |
| `docs/measurements/{date}-deployed-baseline.md` | Generated by the run, interpretation written by hand |
| `docs/PRs/PR_INSTRUMENTATION.md` | Summary · Problem · Solution · Changes · How to Test · Changelog |

### Modified

| File | Change |
|---|---|
| `backend/app/pipeline/protocol.py` | `PROTOCOL_VERSION = 3`; `ClientTimingIn`; union + `parse_client_message` annotation; docstring line moving `timings` from "reserved" to "client_timing, c→s, Block 3" |
| `backend/app/pipeline/turn.py` | `timings: TurnTimings` parameter; the nine fills; `LLMReply` unpacking |
| `backend/app/providers/base.py` | `LLMReply`; `model` on all three Protocols; `thinking_level` on `LLM` |
| `backend/app/providers/gemini_llm.py` | `THINKING_LEVEL` constant; `self.model` / `self.thinking_level`; returns `LLMReply`; drops the now-redundant `logger.info` |
| `backend/app/providers/groq_stt.py` | `MODEL` constant extracted; `self.model`; **drops** the `stt_ms` log line (measured at the call site now) |
| `backend/app/providers/deepgram_tts.py` | `self.model`; log key renamed to `tts_ttfb_after_connect_ms` |
| `backend/app/main.py` | `SARJY_ENV`, `TURN_INDEX`, `_TurnState` fields, `_maybe_emit_timings`, `_flush_timings`, `_handle_client_timing`, the ten call sites, `_process_turn(turns=...)` |
| `backend/modal_app.py` | `.env({"SARJY_ENV": "modal"})` on the image (verified: `modal.Image.env(vars: dict[str,str])` exists in 1.5.5) |
| `backend/Makefile` | `measure: uv run python -m app.measure $(ARGS)` + the usage comment |
| `backend/tests/test_turn.py` | Fakes gain `model` / `thinking_level`; `FakeLLM.reply` returns `LLMReply`; `_run` builds and returns a `TurnTimings` |
| `backend/tests/test_ws.py` | I3 (unknown-turn `client_timing`), and one end-to-end assertion that a turn prints exactly one `turn_timings` line (via `caplog`) |
| `frontend/src/protocol.ts` | `PROTOCOL_VERSION = 3`; `ClientTimingMessage`; union |
| `frontend/src/net/connection.ts` | `sendClientTiming()` |
| `frontend/src/audio/turn.ts` | `EndpointTiming`; `onUtterance` gains the fourth argument |
| `frontend/src/App.tsx` | `turnTimingRef`, `reportTurnTiming`, `lastTurn` state, the one rendered line |

### Not touched

`session.py` · `capture.ts` · `playback.ts` · `config.py` · `factory.py` · the VAD asset pipeline.

---

## Task list

Failure paths are tasks, and they are numbered before the happy path they protect.

| # | Task | Done when |
|---|---|---|
| 1 | `timings.py`: `TurnTimings` with **every** field including the six reserved ones, `LOG_PREFIX`, `elapsed_ms`, `emit` | `emit(TurnTimings(...))` prints one line whose JSON contains `"gate_ms": null` |
| 2 | **I1** — a test that `emit` swallows a raising `model_dump_json` and logs a warning | Test passes; nothing propagates |
| 3 | `base.py`: `LLMReply`, `model` on three Protocols, `thinking_level` on `LLM` | `make typecheck` names every implementer that is now incomplete |
| 4 | Adapters: constants extracted, attributes set, `GeminiLLM.reply` returns `LLMReply`, `groq_stt`'s `stt_ms` line deleted, `deepgram_tts`'s key renamed | `make typecheck` clean |
| 5 | `run_turn(..., timings=)` and the nine fills | `make test` green after the fakes are updated |
| 6 | **I4** — tests: STT raises → `outcome="failed"`, `failed_stage="stt"`, `llm_ms is None`; happy path → all five server legs non-`None` and `>= 0` | Tests pass |
| 7 | `protocol.py`: version bump, `ClientTimingIn`, union, docstring | `test_protocol.py` passes; an unknown field on `client_timing` raises `ValidationError` |
| 8 | `main.py`: `_TurnState` fields, the two emit functions, `_handle_client_timing`, all ten call sites, `SARJY_ENV`, `TURN_INDEX` | A local turn prints exactly one `turn_timings` line |
| 9 | **I2/I3** — tests: `client_timing` for an unknown turn is ignored with no error message; a turn with no `client_timing` still prints a record with `flush_reason="next_turn"` on the next `start` | Tests pass |
| 10 | `modal_app.py`: `SARJY_ENV` | `env` reads `"modal"` in a deployed record and `"local"` under `make dev` |
| 11 | `measure.py`: parse → de-dupe → filter `ok` → table → residual → doc; **I5/I6/I7/I9 first** | `make measure ARGS="/dev/null"` exits 1 cleanly; `make measure` on a tty exits 2 with usage |
| 12 | `test_measure.py` against a handful of synthetic lines: median correct, malformed skipped, duplicate collapsed, failed excluded, mixed config warned | Tests pass |
| 13 | Frontend: `protocol.ts`, `connection.ts`, `turn.ts`, `App.tsx` send path | `npm run typecheck && npm run lint` clean |
| 14 | The one on-screen line | A local turn renders `last turn 1.xx s voice-to-voice · endpoint 0.xx s · redemption 600 ms` |
| 15 | Full local turn: speak, hear, read the line, read the log record | One record, client legs non-null, `outcome="ok"` |
| 16 | `make deploy`, then **ten real turns** against the deployed URL with a fixed script | Ten `ok` records in `modal app logs` |
| 17 | `make measure` → the doc; write the interpretation paragraph by hand | `docs/measurements/{date}-deployed-baseline.md` exists with n=10 and a named largest term |
| 18 | `docs/PRs/PR_INSTRUMENTATION.md`, and draft the commits | Written; **agents never commit** |

---

## The estimate, honestly

| | Hours |
|---|---|
| `CUT-DECISION.md` allowance | **0.5** |
| Record + emit + the nine fills | 0.2 |
| `LLMReply` + Protocol attributes + fake updates | 0.15 |
| The merge in `main.py` (two flags, three flush paths) | 0.25 |
| Wire message + version bump, both sides | 0.1 |
| Frontend send path + the one line | 0.2 |
| `measure.py` + its tests | 0.25 |
| Deploy, ten turns, the doc | 0.2 |
| **Honest** | **~1.3** |

**~0.8 h over the cut.** That is the price of the two client legs, and the caller's scope note is explicit that they are the measurement, not polish. Cut ladder, pre-committed:

| Trigger | Cut | Saves |
|---|---|---|
| **T+35 min**, the record is not printing | Drop `model`/`thinking_level` on the Protocols and the five config fields; hardcode the model ids in the measurement doc's header by hand | ~0.15 |
| **T+50 min**, the client leg is not merging | **Stop merging.** The client's numbers go out as their own `client_timing {...}` log line carrying `turn_id`, and `measure.py` joins the two lines by `turn_id`. Two lines per turn instead of one, still fully correlated, still one command to a median. Invariant 2 survives intact | ~0.2 |
| **T+70 min** | `measure.py` prints the table and stops writing the markdown doc; paste it into `docs/measurements/` by hand | ~0.1 |
| **Never cut** | The record itself · the on-screen line · the ten-turn median against the deployment | — |

---

## The endpointing sweep, now runnable

Block 2 shipped the instrument and left the number unmeasured — `DEFAULT_REDEMPTION_MS = 600` is a placeholder, and endpointing is the **largest single term in the chain** (TDD §Latency budget). This block makes the sweep produce comparable numbers instead of console noise: `redemption_ms` rides in every record, and the on-screen line shows both the setting and its effect without opening devtools.

**Omar runs this** (it needs a human ear; nothing here can be scripted):

1. Deployed URL + `?redemptionMs=400`. Speak the same sentence five times, letting each endpoint naturally.
2. Read the on-screen line after each turn — `endpoint 0.xx s` is the number; note whether any turn *felt* like it cut you off.
3. Repeat at `600` and `800`.
4. `modal app logs sarjy --since 30m --tail 2000 > /tmp/sweep.log`, then `make measure ARGS="--label sweep-400 --redemption 400 /tmp/sweep.log"` for each value.
5. Fill the table in `docs/measurements/block2-voice-loop.md` §Endpointing sweep, write down **why** the chosen value wins, set `DEFAULT_REDEMPTION_MS` in `frontend/src/audio/turn.ts`, and replace the TDD's "~600 ms, still an estimate" row with the measured value and its `n`.

**Sanity check on the instrument** — verified by reading `node_modules/@ricky0123/vad-web/dist/frame-processor.js`: the redemption counter only advances on frames below `negativeSpeechThreshold` (0.25) and resets on any frame at or above `positiveSpeechThreshold` (0.3), with `redemptionFrames = floor(redemptionMs / 32)` at model v5's 32 ms frames. So a correct `endpoint_ms` is **≥ `floor(redemption_ms / 32) * 32`** (576 ms at a 600 ms setting) and typically within ~100 ms above it. **A value below that floor means the instrument is measuring the wrong pair of events, not that the VAD got faster.**

**Stated limitation, because a reviewer will probe it:** `endpoint_ms` starts at the last frame *classified* as speech, which lags the true acoustic end by up to one frame (32 ms) plus capture buffering. It is a slight under-estimate of the real endpointing delay, and it is the number we can actually observe in a browser.

---

## Secrets and what goes in a log line

`AGENTS.md` §Secrets: nothing that could contain a key is ever logged. No API key, no `Authorization` header, no provider response body, and no audio bytes reach a record.

**The judgement call, stated rather than buried: the timing record carries no transcript text and no reply text — only `transcript_chars` and `reply_chars`.** Lengths are what the measurement actually needs (TTS TTFB and total generation both track text length), they are useless to an attacker, and they keep the record safe to paste into a PR, a Loom or the writeup without reading it first. The separate `stt_transcript turn=%s text=%r` line in `run_turn()` stays exactly as Block 2 left it — it exists to make Whisper's near-silence filler visible and it is a deliberate, scoped decision that is not this block's to reverse. The consequence to know: **a measurement log may be shared freely; the full server log may not.**

---

## Verification

Run in order. Show the output; do not assert it passed.

```bash
# 1 -- backend
cd backend && make typecheck && make lint && make test

# 2 -- frontend
cd frontend && npm run typecheck && npm run lint

# 3 -- the broken command is no longer broken
cd backend && make measure                       # exits 2, prints usage, does NOT hang
cd backend && make measure ARGS="/dev/null"      # exits 1, "no turn_timings records found"

# 4 -- a local turn end to end
cd backend && make dev                           # then speak at http://localhost:5173
#    expect on screen:  last turn 1.xx s voice-to-voice · endpoint 0.xx s · redemption 600 ms
#    expect in the log: exactly ONE line matching `turn_timings {`

# 5 -- deploy and measure the deployment
cd backend && make deploy
#    ten turns at the deployed URL, fixed script (below)
modal app logs sarjy --since 30m --tail 2000 | uv run python -m app.measure --label deployed-baseline
```

**Fixed utterance script for the ten turns** — comparable runs need the same words:

1. "What's the capital of Japan?" ×4
2. "Do I need a visa for Turkey?" ×3
3. "Tell me something about Lisbon." ×3

**What proves it worked:**

- `make test` prints the existing suite plus the new tests, all passing, zero failures.
- A deployed record, pretty-printed, contains **non-null** `endpoint_ms`, `first_audio_ms`, `upload_ms`, `stt_ms`, `llm_ms`, `llm_ttft_ms`, `tts_ttfb_ms`, `tts_total_ms`, `server_ms`, `redemption_ms`, `stt_model`, `llm_model`, `tts_model`, `env: "modal"`, `outcome: "ok"` — **and explicit `"opener_ready_ms": null, "tts1_ttfb_ms": null, "tool_ms": null, "llm2_ms": null, "gate_ms": null, "answer_gap_ms": null`.**
- `llm_ttft_ms` is in the tens of milliseconds and `llm_ms` is materially larger — the shape Block 2 measured (30 ms TTFT). If they are equal, TTFT is being read from the wrong event.
- `endpoint_ms >= 576` at `redemption_ms = 600`.
- `make measure` prints `n = 10` on `first_audio_ms`, a median and a p95 per stage, and a residual row.
- Deliberately fail one turn (unplug the network mid-turn, or point `DEEPGRAM_TTS_MODEL` at nonsense for one run): the record still prints, `outcome="failed"`, and `make measure` reports it as excluded rather than averaging it.

---

## Gate

Restated from the master plan — *"real numbers on screen for a real turn, and a median over ten turns against the deployment"* — made observable:

1. **On screen.** Speaking one turn to `https://vitas7777v--sarjy-fastapi-app.us-east.modal.run` renders a line reading `last turn <N.NN> s voice-to-voice · endpoint <N.NN> s · redemption 600 ms`, where both numbers change from turn to turn and neither is a placeholder.
2. **One line per turn.** `modal app logs sarjy` shows **exactly one** `turn_timings {...}` line per turn, containing every field in §Contracts 1, with the six Block 4/5/6 stages present and `null`.
3. **A median over ten.** `modal app logs sarjy --since 30m --tail 2000 | uv run python -m app.measure --label deployed-baseline` prints a stage table with `n = 10` on `first_audio_ms` and writes `docs/measurements/2026-09-20-deployed-baseline.md`, whose config header names the three model ids, `env: modal` and the `redemption_ms` in force.
4. **A finding, not just numbers.** That document's `## Interpretation` names the largest single term with its median, and says in one sentence what would be done about it — even if the answer is "it sits inside a provider we do not control."
5. **Nothing regressed.** `make typecheck && make lint && make test` and `npm run typecheck && npm run lint` are clean, and a stale v2 tab is told to reload rather than erroring.

---

## Draft commits — agents draft, Omar commits

```
feat(timings): one correlated timing record per turn

Per-stage numbers existed as three uncorrelated log lines and the two legs
the user actually feels -- endpointing and first audio out -- were not
measured at all. TurnTimings is opened on `start`, filled as each stage
completes, and printed once both halves of the turn are done: the server's
last audio chunk and the client's first audible sound.

Stages owned by Blocks 4/5/6 (opener, tool, gate, answer gap) are reserved
as explicit nulls -- a record retrofitted later would describe nothing about
what was built first.

LLM.reply() now returns LLMReply so TTFT -- measured to the first
delta.type == "text", never the first SSE event -- can leave the adapter.
```

```
feat(measure): make `make measure` real

The Makefile has always declared `python -m app.measure`; the module did not
exist. It now reads turn_timings lines from a log capture, drops duplicates
and failed turns, and prints median/p95 per stage plus the residual between
the stage sum and the headline figure.
```

```
feat(ui): show the last turn's voice-to-voice number

One line. Invariant 2 says latency is a measured number, and a number nobody
can see during the demo is an adjective with extra steps.
```

---

## Open questions and stated assumptions

| # | Item | Status |
|---|---|---|
| 1 | **The 0.5 h cut cannot buy the client legs.** Honest estimate ~1.3 h | Flagged to Omar. The cut ladder above decides the overrun in advance |
| 2 | `first_audio_ms` ends when the first buffer is **scheduled**, not when a speaker moves | Stated as an assumption in the generated doc. `output_latency_ms` (null on Safari) is the size of the unmeasured remainder — typically 10–50 ms |
| 3 | `endpoint_ms` lags the true acoustic end by ≤ 1 frame (32 ms) plus capture buffering | Stated; it is the best a browser offers |
| 4 | Whether `ensureFresh()`'s socket rotation lands inside `residual_ms` often enough to matter | **Unknown until the ten-turn run.** If the residual is large and bimodal, that is the first thing to check, and it is a finding for Block 4, not work for this block |
| 5 | Block 2's `t_thinking_ms` of 660 ms–3.5 s on the upload leg, measured from a sandbox | `upload_ms` replaces it with a server-monotonic number. If it stays large from a normal browser on a normal network, the dual-capture streaming upload named in the Block 2 plan becomes a real candidate |
| 6 | The sweep, the voice choice and the Safari check all still need a human | Carried forward from `docs/measurements/block2-voice-loop.md` §What still needs a human |
