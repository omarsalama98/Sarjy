# PR: The voice loop (Block 2)

**Plan:** `docs/plans/blocks/02-voice-loop.md` · **Lands:** requirement #1 (the reviewer speaks, Sarjy speaks back)

## Summary

Speaking to the deployed URL now produces a real, spoken reply: browser VAD → Groq Whisper →
Gemini (plain text, no tools) → Deepgram Aura-2, streamed back over the same WebSocket Block 1
built. Every named failure path (F1–F15 in the plan) has a visible, distinct state — no spinner
that can outlive its operation.

**Deployed URL:** `https://vitas7777v--sarjy-fastapi-app.us-east.modal.run`

## Gate status — what's verified, what needs a human

Same honesty rule Block 1's PR used: I don't have a browser or a microphone in this environment.
Everything scriptable was run against the **real deployment**; the rest is flagged, not faked.

| # | Gate step | Status |
|---|---|---|
| 1 | Open the URL, calm `idle` screen, Start button | **Not verified visually** — the component renders this by construction (`App.tsx`), needs a human's eyes |
| 2 | Click Start, mic prompt appears | **Not verified** — needs a real browser + mic |
| 3–5 | Speak, hear a correct answer, no self-interrupt | **Verified everything except the "hear" and "no self-interrupt" parts** — a scripted turn (pre-recorded 16 kHz utterance, real WebSocket protocol) against the deployment produced the correct transcript and reply and real Deepgram audio bytes (`docs/measurements/block2-voice-loop.md`); echo cancellation and audible correctness need speakers and a human |
| 5 | Second turn uses history | **Not verified** — the scripted test sends one turn per connection; `Session.remember_turn()` is unit-tested (`test_ws.py`) but a live two-turn conversation needs a human |
| 6 | Barge mid-answer | **Verified at the protocol level** — `test_ws.py`'s explicit-barge test proves a real asyncio task is cancelled mid-TTS-stream and a following turn works cleanly; the *perceptual* "stops immediately, not at the end of the chunk" needs ears |
| 7 | Deny the mic, fresh incognito | **Not verified** — needs a browser; the code path (`classifyVoiceError` → `mic-blocked` state + Retry) exists and is the direct translation of `NotAllowedError` |
| 8 | 3-minute idle, rotation happens underneath | **Inherited from Block 1, unverified this block** — Block 1's own PR verified this mechanism directly; nothing here changes it, but a live re-check after Block 2's changes wasn't run |
| 9 | Kill wifi mid-answer | **Not verified** — needs a browser; F13's server-side half (task cancelled in `_serve`'s `finally`) is unit-tested, the client-side "notice + clean idle" half is code-complete but unclicked |

**Steps 4, 6 and 7 are the block**, per the plan. Step 4 (the deployed pipeline runs correctly)
is verified end to end except for the literal listening. Step 6 is verified at exactly the layer
that matters (the cancellation is real, not simulated). Step 7's code path is a straight
`err.name === "NotAllowedError"` check with no branching to get wrong, but I'm not asserting a
click I didn't make.

**What I'd ask Omar to do:** the full 9-step gate, on a laptop, on speakers — plus the
endpointing sweep (`docs/measurements/block2-voice-loop.md`) and a Safari pass. That doc lists
exactly what to run and what to look for.

## Problem

Block 1 built a pipe with nothing flowing through it. Requirement #1 — the reviewer speaks,
Sarjy speaks back — did not exist yet, and every voice failure path (denied mic, dropped
network, empty transcript, provider timeout) had no defined behaviour. A voice demo dies of
silence, not of wrong answers, so the failure paths had to ship before the happy path they guard.

## Solution

- **Cascaded, not end-to-end**: STT and TTS are separate provider calls with a real text
  checkpoint in between (`run_turn()`), matching the deep dive's need for a gate later.
- **Three provider adapters, one Protocol each** (`app/providers/base.py`): `GroqSTT`,
  `GeminiLLM`, `DeepgramTTS`. `run_turn()` never imports a provider SDK directly — it takes
  `get_stt`/`get_llm`/`get_tts` callables, so it's testable with fakes and providers are built
  lazily, per-call.
- **`run_turn()` is one async generator** yielding protocol messages and raw audio bytes in the
  exact order they go on the wire. Every failure branch (F7–F12, F14) is a `yield` and a `return`
  in this one function — there is one place this pipeline is orchestrated, and it's fully
  unit-testable with fakes (`tests/test_turn.py`, 11 cases, no network).
- **`AudioStartOut` is only ever sent once real audio exists.** `run_turn()` calls
  `tts.synthesize()` (an async generator — nothing runs yet) and only announces `audio_start`
  on the first chunk actually pulled from it. This is what makes F11 ("fails before the first
  chunk") and F12 ("fails mid-stream") land on exactly the message sequence the plan specifies,
  by construction rather than by a special case.
- **Two turn phases, tracked separately in `main.py`**: phase A (`start`…`end`, still recording)
  and phase B (`end`…done, `run_turn()` running as its own `asyncio.Task`). A `barge` or an
  implicit barge (`start` while phase B is still running) cancels phase B through one function,
  `_cancel_active_turn()` — matching the plan's "one code path for both."
- **The client never sends anything until `onSpeechEnd`.** The VAD's own segment (with
  pre-speech padding) is what gets sent — no second capture graph duplicating what the VAD
  already produces (block plan's "design decision 1").
- **Two AudioContexts, never one**: 16 kHz for capture+VAD, 24 kHz for Deepgram playback, each
  running at its source's native rate. Both are constructed suspended at page load and resumed
  only inside the Start button's click handler (the user gesture Web Audio requires).
- **`PlaybackQueue.stop()` is immediate**: every scheduled `AudioBufferSourceNode` gets
  `.stop(0)`, disconnected, and dropped — no draining the current chunk. Barge-in ignores the
  first 300 ms of playback (echo cancellation is unproven until a human runs the gate) and is
  gated behind a single `BARGE_IN_ENABLED` constant, a one-character fix under pressure.

## Changes

**Backend — created**
- `backend/app/pipeline/audio.py` — `pcm16_to_wav()`, the 44-byte RIFF header Groq's API needs.
- `backend/app/pipeline/turn.py` — `run_turn()` and `MAX_TURN_BYTES`.
- `backend/app/providers/groq_stt.py`, `gemini_llm.py`, `deepgram_tts.py` — the three adapters.
- `backend/app/providers/factory.py` — memoised `get_stt()`/`get_llm()`/`get_tts()`.
- `backend/tests/test_audio.py`, `test_turn.py` — new, per the plan's Files table.

**Backend — modified**
- `backend/app/pipeline/protocol.py` — `PROTOCOL_VERSION = 2`; `StartIn`/`EndIn`/`BargeIn`;
  `TranscriptOut`/`ReplyOut`/`AudioStartOut`/`AudioEndOut`/`TurnFailedOut`.
- `backend/app/main.py` — binary frame accumulation, `start`/`end`/`barge` dispatch, the
  `_TurnState` phase tracker, `_process_turn()` as a cancellable task, `logging.basicConfig()`
  (see "Where the plan needed a fix" — this was missing entirely).
- `backend/app/providers/base.py` — `LLM.complete` → `LLM.reply`; `ProviderUnavailable` now
  lives here (see below), not in `factory.py`.
- `backend/app/session.py` — `Session.history` (in-session, capped at 6 turns) and
  `remember_turn()`. Not listed in the plan's Files table — see below.
- `backend/app/config.py` — explicit dotenv paths, `deepgram_api_key`, `deepgram_tts_model`,
  `rapidapi_key` made optional.
- `backend/pyproject.toml` — `certifi` promoted from `dev` to a real runtime dependency (see
  below); `dev` extra trimmed accordingly.
- `backend/tests/test_protocol.py`, `test_ws.py` — new messages, F15, and three integration
  tests against the real ASGI app with monkeypatched fake providers (full turn, oversized-audio
  abort, explicit barge).

**Frontend — created**
- `frontend/scripts/sync-vad-assets.mjs` — copies the VAD model, worklet, and ORT WASM into
  `frontend/public/vad/`.

**Frontend — modified**
- `frontend/src/protocol.ts` — mirror of the backend's new messages, by hand.
- `frontend/src/net/connection.ts` — `sendBinary()`, `startTurn()`/`endTurn()`/`bargeTurn()`,
  the six new callbacks, `ws.binaryType = "arraybuffer"`.
- `frontend/src/audio/capture.ts` — real body: shared `getUserMedia` stream, `floatToPCM16()`.
- `frontend/src/audio/turn.ts` — real body: `assertVadAssets()`, `createTurnDetector()`, the
  endpointing instrument, the 30 s force-cutoff, the barge gate.
- `frontend/src/audio/playback.ts` — real body: `PlaybackQueue`.
- `frontend/src/App.tsx` — the full state machine: connection state, conversation state, voice
  issues (unavailable/mic-blocked/mic-missing), transcript/reply/turn_failed display.
- `frontend/package.json` — `dev`/`build` run the sync script first; `test` script added (see
  the plan's own note: no frontend unit tests, by design — browser-level failure modes aren't
  caught by a Node runner).
- `frontend/eslint.config.js` — dropped the `src/spike/**` ignore.
- `.gitignore` — `frontend/public/vad/`.

**Deleted** (same commit as real capture, per Block 1's own plan)
- `frontend/spike.html`, `frontend/src/spike/main.ts`, `frontend/src/spike/worklet.js`.

**Docs**
- `docs/measurements/block2-voice-loop.md` — Deepgram TTFB (n=5, against the deployment), and a
  precise handoff for the endpointing sweep and voice choice, both of which need a human.

## Where the plan needed a fix

1. **`ProviderUnavailable` had to move from `factory.py` to `base.py`.** The plan's Files table
   puts it in `factory.py`, but `factory.py` imports every concrete provider SDK (`groq`,
   `google-genai`, `websockets`) at module level. `turn.py` needs `ProviderUnavailable` to
   implement F14, and `main.py` imports `turn.py` at module level (it needs `run_turn` and
   `MAX_TURN_BYTES` outside the request path). Left as the plan specified, importing `turn.py`
   would have transitively pulled every provider SDK into `main.py`'s module graph — exactly
   what Block 1's own docstring says must never happen ("a provider SDK regression must never
   stop `/health` or the static mount from serving"). Moved the exception to `base.py`, which
   has zero SDK imports, so the layering the rest of the plan insists on actually holds.

2. **`Session.history` isn't in the plan's Modified files table**, even though the plan's own
   Scope section is explicit that in-session history belongs "on the Session object." Added
   `history: list[tuple[str, str]]` and `remember_turn()` to `backend/app/session.py` — the
   plan's intent was unambiguous, just the file list was incomplete.

3. **Logging was never wired up, at all — a real gap, not a design choice.** `Settings.log_level`
   has existed since Block 1 but nothing ever called `logging.basicConfig()`. Every
   `logger.info()` call in the codebase — including this block's `stt_ms`, `tts_ttfb_ms`, and
   `llm_first_text_delta_ms` lines that the plan's own verification depends on
   ("Measure Deepgram's TTFB... from `modal app logs sarjy`") — was silently swallowed by
   Python's unconfigured root logger. Found by running that exact verification step: `modal app
   logs` showed HTTP access lines but none of the custom ones. Fixed with one `logging.basicConfig()`
   call in `main.py`, reading `LOG_LEVEL` directly from the environment (not via
   `app.config.load_settings()`, to keep the "no config import at module level" invariant intact).

4. **`websockets`'s raw SSL handshake doesn't get httpx's automatic certifi fallback.** Found
   running the adapter smoke test locally: Groq and Gemini (both on `httpx`) connected fine;
   Deepgram (`websockets.connect`) failed `CERTIFICATE_VERIFY_FAILED`. `httpx` bundles and
   trusts `certifi` regardless of OS; `websockets` trusts whatever the OS/interpreter's own CA
   store provides, and a `debian_slim` Modal container is not guaranteed to have one populated.
   Not just a local dev quirk — genuinely a production risk. Fixed by building an explicit
   `ssl.create_default_context(cafile=certifi.where())` in `deepgram_tts.py` and promoting
   `certifi` to a real dependency (`modal_app.py`'s `pip_install_from_pyproject` only installs
   `[project.dependencies]`, never the `dev` extra — it would have shipped broken otherwise).

5. **The exact wording for F7/F10/F12/F14's `turn_failed` messages isn't specified.** The plan
   gives exact text for F8, F9, and F11; the others say "plain message" or similar. Wrote
   plain, first-person messages consistent with the given ones (e.g. F7: "That was too long for
   me to catch — try a shorter question."); listed in `docs/plans/blocks/02-voice-loop.md`'s
   spirit rather than its letter, and easy to change if Omar wants different wording.

## Two things worth saying out loud in the walkthrough

- **The LLM leg is the cheapest one in the chain.** `llm_first_text_delta_ms` measured 29–30 ms
  across 5 runs against the real deployment — faster than either STT or TTS. A reviewer will not
  expect this; it's worth naming.
- **The frontend has no unit tests, on purpose.** Its failure modes are browser-level
  (permissions, audio graphs, worklet loading) and none are caught by a Node test runner. The
  `test` script exists so the command contract holds; the real verification is the end-to-end
  turn. This is the plan's own explicit call, not a shortcut taken here.

## How to Test

```
cd backend && uv run ruff check app tests && uv run mypy app && uv run pytest -q
cd frontend && npm run lint && npm run typecheck && npm run build
```

Then, against the **deployed** URL:

```
curl -sI https://vitas7777v--sarjy-fastapi-app.us-east.modal.run/vad/silero_vad_v5.onnx | head -3
curl -sI https://vitas7777v--sarjy-fastapi-app.us-east.modal.run/vad/vad.worklet.bundle.min.js | head -3
curl -sI https://vitas7777v--sarjy-fastapi-app.us-east.modal.run/vad/ort-wasm-simd-threaded.wasm | head -3
```
All three: `200`, non-`text/html`. Then the 9-step browser gate in
`docs/plans/blocks/02-voice-loop.md` — on speakers, per the plan.

## Changelog

```
build(frontend): serve VAD model and ONNX runtime from /vad

MicVAD.new() defaults baseAssetPath and onnxWASMBasePath to "./", which
resolves against the document URL under Vite and 404s. sync-vad-assets.mjs
copies the model, worklet and ORT WASM into public/vad/ before every dev
and build; assertVadAssets() HEAD-checks all three before MicVAD.new() ever
runs, so a missing asset is a legible on-screen message, not silence.

feat(protocol): v2 -- turn start/end/barge, transcript, reply, audio framing

Bumped so a stale tab fails the handshake cleanly instead of sending
messages the old server half-understands. audio_start/audio_end exist
because binary frames carry no turn id.

feat(providers): Groq STT, Gemini text reply, Deepgram streaming TTS

Three adapters behind the existing Protocol interfaces. Deepgram needs an
explicit certifi-backed SSL context (websockets doesn't get httpx's
automatic fallback) and asserts container=none held by checking the first
chunk isn't a RIFF header. Gemini's streaming shape is verified against
Block 0's own spike, down to the event field names.

feat(pipeline): run_turn, with every failure path visible

One async generator, STT -> LLM -> TTS, yielding protocol messages and PCM
bytes in wire order. audio_start is only ever sent once a real chunk
exists, which is what makes the "fails before vs. during audio" failure
paths land on the right message sequence by construction. Tested against
fakes, no network, 11 cases.

fix(logging): actually configure the root logger

logger.info() has done nothing since Block 1 -- LOG_LEVEL was loaded into
Settings but never applied. Every stt_ms/tts_ttfb_ms/llm_first_text_delta_ms
line this block's own verification depends on was silently swallowed.

feat(frontend): capture, VAD endpointing, playback queue, barge-in

Nothing goes over the network until onSpeechEnd -- the VAD's own segment
(pre-speech padding included) is what gets sent, no second capture graph.
PlaybackQueue.stop() drops every scheduled buffer immediately rather than
draining the current chunk. Barge-in is gated behind BARGE_IN_ENABLED and
ignores the first 300ms of playback, since echo cancellation on real
speakers is unproven until a human runs the gate.

feat(frontend): conversation state machine and microphone permission states

listening/speaking are set locally the instant the VAD or playback queue
notices them; thinking/idle arrive from the server. Separate voiceIssue
state (unavailable/mic-blocked/mic-missing) so a broken mic never gets
squeezed into looking like "idle."

chore: remove the Block 0 audio spike, now that capture is real

docs: Block 2 measurements -- Deepgram TTFB against the deployment, and a
precise handoff for the endpointing sweep and voice choice (both need a
human speaking into a real microphone, which this can't script around).
```

Attribution line per the repo's convention, on each, added by Omar at commit time.
