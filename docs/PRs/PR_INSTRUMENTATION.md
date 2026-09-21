# PR: Instrumentation (Block 3)

**Plan:** `docs/plans/blocks/03-instrumentation.md` · **Lands:** Invariant 2 (latency is a measured
number, not an adjective) and makes `make measure` real

## Summary

Every turn now prints **one correlated, structured timing record** — `turn_timings {...}` — that
covers the whole chain, client legs included: endpointing → upload → STT → LLM TTFT → TTS TTFB →
first audible sound. Stages Blocks 4/5/6 haven't built yet (`opener_ready_ms`, `tool_ms`,
`gate_ms`, `answer_gap_ms`, `tts1_ttfb_ms`, `llm2_ms`) are reserved and emitted as explicit
`null`, never omitted. `backend/app/measure.py` turns a capture of these lines into a median/p95
stage table against the deployment, and `make measure` — declared in `AGENTS.md` since before
this block but never implemented — is now real. One line renders the last turn's voice-to-voice
number on screen.

**Deployed URL:** `https://vitas7777v--sarjy-fastapi-app.us-east.modal.run`

## Gate status — what's verified, what needs a human

Same honesty rule the last two PRs used: no browser, no microphone in this environment.
Everything scriptable ran against the **real deployment**; the rest is flagged, not faked.

| # | Gate step | Status |
|---|---|---|
| 1 | On screen: `last turn N.NN s voice-to-voice · endpoint N.NN s · redemption NNN ms` | **Not verified visually** — the component renders this by construction (`App.tsx`'s `lastTurn` state + the one `<p className="metrics">` line); `npm run typecheck && npm run lint` and `npm run build` are clean, but nobody has looked at a screen yet |
| 2 | One `turn_timings {...}` line per turn, every field present, six Block 4/5/6 fields `null` | **Verified against the deployment**, twice (`modal app logs sarjy`) — see below |
| 3 | A median over ten, via `make measure` against the deployment | **Not done — needs a human.** Two scripted turns ran (see below); the fixed ten-turn script needs a person speaking into a real microphone through a real browser, which this agent cannot do |
| 4 | A finding in the generated doc's `## Interpretation` | **Not done** — blocked on #3 |
| 5 | `make typecheck && make lint && make test` / `npm run typecheck && npm run lint` clean | **Verified** — `mypy app`: 21 source files clean; `ruff check app tests`: clean; `pytest -q`: 81 passed; frontend `tsc --noEmit`, `eslint`, and `npm run build` all clean |

**What actually ran against the deployment:** two scripted turns via
`scratch/spikes/block2/deployed_turn.py` (updated to speak protocol v3), driving
`hello → start → binary PCM → end` exactly like the browser, using a pre-recorded utterance
instead of a live microphone. Both produced a correct transcript, a correct reply, real Deepgram
audio, and — the point of this block — exactly one `turn_timings` line each, server legs filled,
client legs `null` (a scripted turn has no browser to report `client_timing` from), flushed via
`flush_reason="connection_closed"` when the script sent `bye` and disconnected. **That null/flush
combination is the correct, designed-for result for a scripted turn, not a bug** — it's I2 from
the block plan (`"a turn never produces zero records"`) doing exactly what it's for.

```
turn_timings {"turn_id":"t-smoke-0","session":"667248e5","connection_n":1,"turn_index":1,
"env":"modal","stt_model":"whisper-large-v3-turbo","llm_model":"gemini-3.5-flash-lite",
"tts_model":"aura-2-thalia-en","llm_thinking_level":"minimal","redemption_ms":null,
"outcome":"ok","failed_stage":null,"flush_reason":"connection_closed","transcript_chars":29,
"reply_chars":30,"endpoint_ms":null,"first_audio_ms":null,"output_latency_ms":null,
"upload_ms":789,"stt_ms":258,"llm_ms":1168,"llm_ttft_ms":964,"tts_ttfb_ms":650,
"tts_total_ms":1637,"server_ms":4486,"opener_ready_ms":null,"tts1_ttfb_ms":null,
"tool_ms":null,"llm2_ms":null,"gate_ms":null,"answer_gap_ms":null}
```

**A finding worth flagging, not fixing (this block doesn't optimise anything it measures):**
`llm_ttft_ms` came back 964 ms and 774 ms on the two runs — nowhere near Block 2's baseline of a
30 ms median. The gap between `llm_ttft_ms` and `llm_ms` (~200 ms both times) is real and
consistent, which rules out the trap this block worries about by name (TTFT silently regressing
to "the whole completion" would show `llm_ttft_ms ≈ llm_ms`, which this isn't). The likelier
explanation is turn 1 of a **freshly redeployed** container (the docstring on `TurnTimings`
literally calls turn 1 "the cold one") plus this sandbox's own network path to `us-east` — the
same caveat Block 2's PR raised about `t_thinking_ms`. Worth a clean n≥10 run from a normal
connection before anyone quotes the 30 ms figure again.

**What I'd ask Omar to do:** the ten-turn script (fixed utterances, §Verification in the block
plan) against the deployed URL, then `modal app logs sarjy --since 30m --tail 2000 | make measure
ARGS="--label deployed-baseline"`, then write the `## Interpretation` paragraph by hand. Also the
endpointing sweep (`docs/plans/blocks/03-instrumentation.md` §"The endpointing sweep, now
runnable") — it needs a human ear and was already flagged as open after Block 2.

## Problem

Latency numbers existed as three `logger.info` lines (`stt_ms`, `llm_first_text_delta_ms`,
`tts_ttfb_ms`) nothing tied to a turn — no `turn_id`, no correlation, no way to compute a median
without hand-grepping a live log during a call. The two legs that decide what a reviewer actually
feels — endpointing and first audio out — weren't measured at all, because they only exist in the
browser. And `make measure`, declared in `AGENTS.md` since Block 1, ran `python -m app.measure`,
which didn't exist — a broken command that would have been caught mid-demo, not before it.

## Solution

- **`TurnTimings` (`app/pipeline/timings.py`)** — one Pydantic model, `extra="forbid"`, every
  field named up front including the six Block 4/5/6 stages that don't exist yet. `emit()` is the
  **only** guarded call in the whole feature: every fill elsewhere is a plain attribute
  assignment mypy already validated at build time (`validate_assignment` is off), so a timing
  record can never break the turn it's describing.
- **Server legs measured at the call site, not inside the adapter.** `run_turn()` times
  `stt.transcribe()`, `llm.reply()`, and the `tts.synthesize()` pull directly — the adapter's own
  internal number (`tts_ttfb_after_connect_ms`, renamed from `tts_ttfb_ms` this block) excludes
  the Deepgram WebSocket handshake; the timing that matters to a user does not get to exclude it.
- **`LLMReply` replaces a bare `str` return from `LLM.reply()`.** TTFT — timed to the first
  `delta.type == "text"`, never the first SSE event, unchanged from Block 2 and re-verified, not
  "fixed" — now travels with the text instead of dying in a log line nothing could correlate.
- **The merge lives in `main.py`, not `run_turn()`.** `run_turn()` only knows the server side;
  `_maybe_emit_timings()` prints once both `server_done` and `client_done` are true, and
  `_flush_timings()` covers the three cases where the client half never arrives (the next `start`,
  a barge, the connection closing) so **a turn never produces zero records** (I2).
- **`client_timing` (protocol v2 → v3, both sides)** carries the two legs only the browser can
  see — `endpoint_ms` (last VAD-classified speech frame → `onSpeechEnd`) and `first_audio_ms`
  (that same instant → the first playback buffer actually *scheduled*, the headline number) —
  plus the `redemption_ms` setting in force. `App.tsx`'s `reportTurnTiming()` enforces exactly one
  send per turn via a `sent` flag on `turnTimingRef`.
- **`app/measure.py` reuses `TurnTimings` for parsing** (`model_validate_json`), not a second
  schema — a drifted field is caught by the same model that produced it, not silently averaged
  past. De-dupes on `(session, turn_id, turn_index)`, excludes non-`ok` outcomes from every
  median and reports the excluded count separately, and warns `MIXED CONFIGURATION` (rather than
  silently averaging across two setups) if `env`/`redemption_ms`/any model id varies within one
  run.
- **`turn.py` still never imports a provider adapter** (Invariant 3) — the model ids that land in
  `TurnTimings` come off the `model`/`thinking_level` Protocol attributes in `app/providers/base.py`,
  never a direct import. `main.py` imports `turn.py` at module level, so this is the trap the
  plan calls out twice, closed the same way Block 2 closed it for the SDKs themselves.
- **No transcript or reply text in the record — only lengths.** `transcript_chars`/`reply_chars`
  are what the measurement actually needs (TTS TTFB and generation both track text length); a
  measurement log built from these records is safe to paste into a PR or a Loom without reading
  it first.

## Changes

**Created**
- `backend/app/pipeline/timings.py` — `TurnTimings`, `LOG_PREFIX`, `elapsed_ms()`, `emit()`
- `backend/app/measure.py` — parses, de-dupes, aggregates, writes the doc; makes `make measure` real
- `backend/tests/test_timings.py`, `backend/tests/test_measure.py`
- `docs/PRs/PR_INSTRUMENTATION.md` (this file)

**Modified**
- `backend/app/pipeline/protocol.py` — `PROTOCOL_VERSION` 2 → 3, `ClientTimingIn`
- `backend/app/pipeline/turn.py` — `timings: TurnTimings` (required, keyword-only), nine fills
- `backend/app/providers/base.py` — `LLMReply`; `model` on all three Protocols; `thinking_level` on `LLM`
- `backend/app/providers/gemini_llm.py` — `THINKING_LEVEL` constant, returns `LLMReply`
- `backend/app/providers/groq_stt.py` — `MODEL` constant, drops the now-redundant `stt_ms` log line
- `backend/app/providers/deepgram_tts.py` — `self.model`; log key renamed to `tts_ttfb_after_connect_ms`
- `backend/app/main.py` — `SARJY_ENV`, `_TURN_INDEX`, `_TurnState` timing fields, `_maybe_emit_timings`,
  `_flush_timings`, `_handle_client_timing`, all call sites
- `backend/modal_app.py` — `.env({"SARJY_ENV": "modal"})` on the image (moved before `add_local_*` —
  Modal treats those as the end of an image's build steps)
- `backend/Makefile` — `measure: uv run python -m app.measure $(ARGS)`
- `backend/tests/test_turn.py`, `backend/tests/test_ws.py` — fakes gain `model`/`thinking_level`,
  `LLMReply`; new I2/I3 tests and a one-record-per-turn assertion
- `frontend/src/protocol.ts` — `PROTOCOL_VERSION` 3, `ClientTimingMessage`
- `frontend/src/net/connection.ts` — `sendClientTiming()`
- `frontend/src/audio/turn.ts` — `EndpointTiming`, `onUtterance` gains a fourth argument
- `frontend/src/App.tsx` — `turnTimingRef`, `reportTurnTiming`, `lastTurn` state, the one rendered line
- `scratch/spikes/block2/deployed_turn.py` (gitignored, not shipped) — hello's `v` bumped 2 → 3 so
  the smoke script still speaks the current protocol

## How to test

```bash
cd backend
uv run mypy app                 # 21 source files, clean
uv run ruff check app tests     # clean
uv run pytest -q                # 81 passed
```

```bash
cd frontend
npm run typecheck               # clean
npm run lint                    # clean
npm run build                   # clean
```

```bash
# the broken command is no longer broken
cd backend
uv run python -m app.measure                 # exits 2, prints usage, does not hang
uv run python -m app.measure /dev/null       # exits 1, "no turn_timings records found"

# against the deployment
uv run modal deploy modal_app.py
uv run python scratch/spikes/block2/deployed_turn.py \
    wss://vitas7777v--sarjy-fastapi-app.us-east.modal.run/ws 1
uv run modal app logs sarjy --since 5m | grep turn_timings
```

## For Omar

- **`.env.example` needs `SARJY_ENV` added as a documented name** (optional, defaults to
  `"local"`) — I don't have write access to that file by design (`CLAUDE.md`'s deny rule), so
  this line is the handoff.
- The ten-turn deployed run, `make measure`, and the `## Interpretation` paragraph are the three
  outstanding gate items — all need a human at a microphone, none can be scripted from here.
- The endpointing sweep (`?redemptionMs=400/600/800`, by ear) is still open from Block 2 and this
  block is what finally makes it measurable end to end.

## Changelog

- feat(timings): one correlated timing record per turn
- feat(measure): make `make measure` real
- feat(ui): show the last turn's voice-to-voice number
