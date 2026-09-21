# Block 2 — The voice loop

**Date:** 2026-09-20 · **Budget:** ~6.5 h (the master plan says 3.5 h — see §The estimate changed)
**Plan of record:** `docs/plans/MASTER-PLAN.md` §Block 2 · **Design:** `docs/plans/TDD.md` §Architecture, §Stack, §Provider traps, §Latency budget, §Failure modes, §Barge-in
**Depends on:** Block 1 (`docs/plans/blocks/01-skeleton-deploy.md`) and Block 0 §S5 **including its Outcome section**
**Lands:** requirement **#1 — the reviewer speaks, Sarjy speaks back.**

---

## Summary — read this page

**Goal:** speaking to the deployed URL produces a sensible spoken reply, and every way that can fail has a visible state instead of silence.

This block is pure engineering. No model cleverness, no tools, no gate. **The LLM call is deliberately trivial** — one prompt, one text reply. If this block is interesting, it has gone wrong.

**Four things decide whether it succeeds:**

| # | The thing | Why it decides the block |
|---|---|---|
| 1 | 🪤 **The VAD's ONNX + WASM assets must be served from a path we control** | Block 0 §S5 Section C produced no speech events and nothing on the page. `MicVAD.new()` defaults `baseAssetPath` and `onnxWASMBasePath` to `"./"`, which resolves against the *document* URL, not the module — so under Vite they 404. **This is task 1, not a debugging step at hour three.** |
| 2 | **The endpointing number is ours to choose and has never been measured** | `@ricky0123/vad-web` defaults `redemptionMs: 1400`. The TDD's budget assumes ~600 ms. This is the single largest term in the whole latency chain and the only one no provider controls. Task 11 measures it. |
| 3 | 🪤 **`container=none` on the Deepgram URL** | It defaults to `wav` even for `linear16`, putting a RIFF header on *every* chunk. The adapter asserts the first chunk is not `RIFF` so this can never regress silently. |
| 4 | **Failure paths ship before happy paths** | Mic denied, mic revoked, VAD assets missing, empty transcript, STT down, TTS down, socket dropped mid-turn. A voice demo dies of silence, not of wrong answers. |

**The gate is observational:** open the public URL on a phone-free laptop, click *Start talking*, say *"What's the capital of Japan?"*, and hear Sarjy answer in under ~4 s, with the state indicator moving `idle → listening → thinking → speaking → idle` and the transcript and reply visible on screen.

---

## Scope

### In

- Browser capture: one `getUserMedia` stream with `echoCancellation`, `noiseSuppression`, `autoGainControl`; float32 → PCM16 at 16 kHz.
- Client-side VAD and endpointing (`@ricky0123/vad-web`), with the asset problem solved and the end-of-speech delay **measured**.
- STT adapter: Groq `whisper-large-v3-turbo`, batch.
- **A plain LLM call.** Gemini `gemini-3.5-flash-lite`, system prompt + short in-session history, one text reply. No tools.
- TTS adapter: Deepgram `aura-2-thalia-en` over WebSocket, raw PCM16 @ 24 kHz.
- Playback queue with explicit `AudioContext` scheduling, and `stop()` that drops scheduled buffers.
- **Barge-in, the cheap half** — see §Barge-in below for exactly where the line is.
- The visible conversation state machine, end to end.
- Two `logger.info` timing lines (STT duration, TTS TTFB) — the minimum needed to satisfy "measure Deepgram's TTFB in this block".

### Out — say no to all of these

| Out | Owner |
|---|---|
| The `update()` opener, parallel function calling | Block 4 |
| Any tool call, any `function_call` in the LLM request | Block 4 |
| NDJSON segments, Pydantic-per-line validation | Block 4 |
| The grounding gate, `sourced`/`judgement` registers, citations | Block 6 |
| Memory, `modal.Dict`, identity, name + PIN | Block 7 |
| The vendor client, quota ledger, CSV fallback | Block 5 |
| Arabic (`language=ar`, Orpheus, RTL) | Block 10 |
| The `timings` protocol message and per-stage monotonic instrumentation | Block 3 |
| Truncating interrupted assistant turns in history; cancelling an in-flight tool call | Block 4 |
| UI styling beyond "every state is legible" | Block 8 |

**In-session conversation history is in scope and is not memory.** Up to 6 turns of `(user, assistant)` text held on the `Session` object, dropped when the session expires. It exists so the second turn makes sense. Block 7 owns anything that survives a reload, and this list must not be allowed to grow into it.

---

## What Block 0 §S5 left unresolved

Section A **passed**: capture → 48→16 kHz → PCM16 → playback works in Chrome on this machine. That was the risk the spike existed for and it is retired. Sections B and C never ran.

### 1. 🪤 The VAD assets — the single most important trap in this block

**What was observed:** start the VAD, speak, go quiet — no `onSpeechStart`, no `onSpeechEnd`, nothing on the page.

**What the package source actually says** (read at `frontend/node_modules/@ricky0123/vad-web/dist/`, version 0.0.31 — not recalled):

- `getDefaultRealTimeVADOptions()` sets `baseAssetPath: "./"` and `onnxWASMBasePath: "./"`.
- `MicVAD.new()` sets `ort.env.wasm.wasmPaths = onnxWASMBasePath`, then fetches `baseAssetPath + modelFiles[model]`.
- `modelFiles` is `{legacy: "silero_vad_legacy.onnx", v5: "silero_vad_v5.onnx", v6: "silero_vad_v6.onnx"}` — **there is no `silero_vad.onnx`.** `DEFAULT_MODEL = "legacy"`.
- `start()` loads the worklet from `baseAssetPath + "vad.worklet.bundle.min.js"`.
- A relative `"./"` inside an ES module resolves against the **document** URL, so on `/spike.html` it became `/silero_vad_legacy.onnx` → 404 under Vite.

⚠️ **The source does throw on model-load failure** (`console.error("Encountered an error while loading model file …"); throw e`). So "completely silent" is probably "silent *on the page*" — the spike page logged only to its own `<pre>`, and the failure path never wrote to it. **Do not resolve this by argument.** Task 1 makes the load state visible on screen and asserts the assets are reachable, so the question stops mattering.

**The fix, and it has to work in three places:**

| Where | Mechanism |
|---|---|
| Vite dev (`npm run dev`, port 5173) | Vite serves `frontend/public/**` at `/` |
| Production bundle (`npm run build`) | Vite copies `frontend/public/**` into `frontend/dist/**` |
| Modal (`StaticFiles` mount on `frontend/dist`) | `modal_app.py`'s `add_local_dir(frontend/dist)` carries it; `make deploy` already runs `build-frontend` first |

One directory, `frontend/public/vad/`, populated by a build-time copy script. **No CDN** — a third-party fetch at demo time is a demo that can fail on someone else's network.

### 2. Section B was a playback bug, not an echo-cancellation finding

Nothing was audible, including a locally generated 440 Hz tone, so it never tested anything. The likely cause is that it played through the **capture** `AudioContext` (constructed at 16 kHz) rather than a fresh one.

**This block's answer: two `AudioContext`s, never one.** `captureCtx` at 16 kHz for mic + VAD, `playbackCtx` at 24 kHz for Deepgram output. That is also the answer to "audio arrives at 24 kHz but capture is 16 kHz" — each context runs at its own source's native rate, so there is no resampling on either hot path.

**Echo cancellation is proven the moment a real turn runs through laptop speakers** (task 10, explicitly on speakers, not headphones). If Sarjy interrupts itself, the fix is in §Barge-in's guard, not an architecture change.

### 3. The endpointing number is still unmeasured

`redemptionMs` default is **1400 ms** (read from `defaultFrameProcessorOptions`, alongside `positiveSpeechThreshold: 0.3`, `negativeSpeechThreshold: 0.25`, `preSpeechPadMs: 800`, `minSpeechMs: 400`). The TDD budget assumes ~600 ms. Shipping the default would add ~800 ms of pure dead air to every single turn.

Task 11 measures it properly and records the value **and the reason**, per `.claude/rules/voice/browser-audio.md`.

---

## The estimate changed

The master plan's 3.5 h assumed S5 had de-risked capture, VAD and playback. Two of those three came back unresolved.

| | Hours |
|---|---|
| Master plan, Block 2 | 3.5 |
| VAD assets + visible load state + serving in three environments | +0.75 |
| Deepgram WebSocket TTS adapter (no prior art in this repo; the `container` trap; TTFB measurement) | +0.5 |
| Endpointing measurement sweep, which S5 was supposed to deliver | +0.5 |
| Playback queue + barge-in stop, which Section B never validated | +0.5 |
| Failure paths as real tasks rather than a tidy-up | +0.75 |
| **Honest estimate** | **~6.5** |

After Block 1's own overrun the master plan was ~4.5 h over ~21 h available. This puts it **~7.5 h over**.

**Say this to Omar at the start of the block, not at the end.** Overflow cuts #1–#4 (Wikipedia imagery, UI polish beyond functional, Arabic code-switching + RTL, Tier B golden tests — 3.65 h) should be treated as **already taken**. Block 10 (Arabic, 0.75 h) is now the next candidate and needs a decision Sunday, not Monday.

### Pre-committed cuts, with trigger times

`T0` = the moment the block starts.

| Trigger | Cut | Saves |
|---|---|---|
| **T+2 h 30 m** — the VAD is not firing in a real browser, or a recorded WAV has not produced a transcript | **Stop and escalate to Omar.** Do not keep debugging quietly. This is the S5 debt and if it is alive at 2.5 h the block is in trouble | — |
| **T+4 h 30 m** — no full local voice turn (speak → hear) | Cut the **server half of barge-in** (client stops audio and starts a new turn; the old server turn runs to completion and its audio is discarded by turn id). Cut the endpointing sweep to 3 utterances at one value. Cut the Safari check and record it as untested | ~50 m |
| **T+6 h** | **Deploy whatever works and walk the gate.** A partially working deployed turn beats a perfect local one — requirement #4 is already banked and must not be put at risk | — |

**Never cut:** the failure paths, and the end-to-end turn *against the deployed URL*. Those two are the gate.

---

## Prerequisites — Omar does these himself

| # | Action | Blocks | Note |
|---|---|---|---|
| P2.1 | Confirm `DEEPGRAM_API_KEY` is in the `.env` the backend actually loads (see the trap below) | tasks 6, 10 | Agents never read `.env`. |
| P2.2 | `modal secret create sarjy-secrets --force` (or the console) so `DEEPGRAM_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY` are all in the deployed secret | task 12 | A local `.env` is invisible to Modal. The deploy will succeed and the first turn will fail with a missing key if this is skipped. |
| P2.3 | Listen to 3 Deepgram Aura-2 English voices and pick one | task 12 | `aura-2-thalia-en` is the shipped default and a placeholder (`TDD.md` §Provider traps). The voice is a "creative and personal to you" rubric line, it is a config change, and it takes ten minutes. Record the choice and the reason in `docs/measurements/block2-voice-loop.md`. |
| P2.4 | Run the end-to-end turn **on laptop speakers, not headphones** | task 10 | This is the echo-cancellation test Section B never ran. |
| P2.5 | Every commit | — | Agents draft, Omar commits. |

🪤 **Two `.env` files now exist** — `/.env` (repo root) and `/backend/.env`. `config.py` calls bare `load_dotenv()`, which searches upward from `backend/app/` and **stops at the first hit**, i.e. `backend/.env`. If the Groq and Gemini keys live only in the root file, `load_settings()` will raise on a key that is plainly sitting on disk. Task 4 makes both paths explicit; P2.1 confirms which file has what.

---

## Contracts

### Protocol v2

**Bump `PROTOCOL_VERSION` to `2`** in both `backend/app/pipeline/protocol.py` and `frontend/src/protocol.ts`. Block 1's handshake requires exact equality, so a stale tab left open over the weekend gets *"A new version is available — reload."* instead of a baffling failure. That is the mechanism working.

Everything Block 1 defined stays unchanged. These are added.

#### Client → server

```jsonc
{"t":"start","turn_id":"t-1","client_ts_ms":1758300000000}
// …then one or more BINARY frames: raw PCM16 LE, mono, 16 000 Hz, ≤32 KiB each…
{"t":"end","turn_id":"t-1","samples":48000,"client_ts_ms":1758300003000}
{"t":"barge","turn_id":"t-1"}
```

- `turn_id` is client-minted, `t-<n>`, monotonic within a session.
- A binary frame arriving with no open turn → `error{code:"bad_message", recoverable:true}`, frame discarded.
- A `start` while a turn is already running is treated as an **implicit barge**: cancel the running turn, log it, begin the new one. One code path with `barge`.

#### Server → client

```jsonc
{"t":"transcript","turn_id":"t-1","text":"what's the capital of japan","seq":47,"ts_ms":…}
{"t":"reply","turn_id":"t-1","text":"Tokyo — and it's a great first stop.","seq":48,"ts_ms":…}
{"t":"audio_start","turn_id":"t-1","sample_rate":24000,"seq":49,"ts_ms":…}
// …then BINARY frames: raw PCM16 LE, mono, 24 000 Hz…
{"t":"audio_end","turn_id":"t-1","samples":72000,"seq":50,"ts_ms":…}
{"t":"turn_failed","turn_id":"t-1","stage":"stt","message":"I didn't catch that — say it again?","seq":51,"ts_ms":…}
```

- `stage` is `"audio" | "stt" | "llm" | "tts"`.
- `message` is **user-facing prose**, shown on screen verbatim. It is not spoken in Block 2 (that would need a TTS call inside the TTS failure path). Block 8 may add a pre-rendered clip.
- `audio_start` / `audio_end` exist because binary frames carry no turn id. The client uses them to arm the playback queue and to know when a turn is over.
- `state` values `listening`/`thinking`/`speaking` are already in the union from Block 1. No new model needed.
- Every server message keeps `seq` (monotonic **per session**) and `ts_ms` (wall clock, display only — Block 3's timing must not reuse it).

Validation stays where Block 1 put it: one pydantic discriminated union behind `parse_client_message()` with `extra="forbid"`, and one hand-rolled `switch` in `parseServerMessage()`. **Add branches; do not add a schema library.**

### Who owns which conversation state

State changes must render **immediately**, so the client renders locally-observable facts without waiting for a round trip. The server still pushes all four, so the protocol stays honest.

| State | Rendered on | Authoritative source |
|---|---|---|
| `listening` | VAD `onSpeechStart` (client, local) | client |
| `thinking` | server `state` after `end` is received | server |
| `speaking` | first audio buffer actually scheduled (client), armed by `audio_start` | client |
| `idle` | server `state` after `audio_end`, and on any `turn_failed` | server |

### Provider interfaces (`backend/app/providers/base.py`)

```python
class STT(Protocol):
    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str: ...

class LLM(Protocol):
    async def reply(self, *, system: str, history: list[tuple[str, str]], user: str) -> str: ...

class TTS(Protocol):
    def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]: ...
```

`STT` and `TTS` are **unchanged from Block 1**. `LLM.complete(messages, tools) -> dict` is **replaced** by `reply(...) -> str` — the old signature cannot express "give me a sentence", and Block 4 adds a separate streaming/tools method rather than overloading this one. That is the only change to this file.

`history` is `[(user_text, assistant_text), …]`, oldest first, capped at 6.

⚠️ mypy note: an `async def synthesize(...) -> AsyncIterator[bytes]` generator is structurally compatible with the `def … -> AsyncIterator[bytes]` in the Protocol. If mypy disagrees, make it a plain `def` returning an inner async generator rather than changing the Protocol.

### Deepgram TTS adapter

```
wss://api.deepgram.com/v1/speak?model=aura-2-thalia-en&encoding=linear16&container=none&sample_rate=24000
```

- Header: `Authorization: Token <DEEPGRAM_API_KEY>`. (If that 401s, `Bearer` is the documented alternative — try it before assuming the key is wrong.)
- 🪤 **`container=none` is mandatory.** It defaults to `wav` even for `linear16`, which puts a RIFF header on **every chunk** of the stream and corrupts playback. The adapter asserts `first_chunk[:4] != b"RIFF"` and raises a legible error if it ever does — so this cannot come back silently after a URL edit.
- 🪤 `websockets` 16.1.1 uses **`additional_headers=`**, not `extra_headers=` (verified against the installed signature). The old name is legacy-API-only and raises `TypeError`.
- Client → server: `{"type":"Speak","text":"…"}`, then `{"type":"Flush"}`, then `{"type":"Close"}`.
- Server → client: **binary** frames are audio. JSON frames are `{"type":"Metadata"|"Flushed"|"Cleared"|"Warning", …}`. Stop yielding when `Flushed` arrives; close the socket.
- **Published TTFB <200 ms is a vendor claim we have not verified.** Measure it: `t_flush_sent → first binary frame`, as `logger.info("tts_ttfb_ms=%d …")`, n≥5 from the deployment.
- Model id comes from config (`DEEPGRAM_TTS_MODEL`, default `aura-2-thalia-en`) — a voice swap is a config change, per Invariant 3.
- `open_timeout=5`, and a hard cap on total synthesis time. **Never** leave a provider default retry/backoff in place (`TDD.md` §Provider traps).

### Groq STT adapter

- `AsyncGroq(api_key=…, max_retries=1, timeout=8.0)` — the SDK default retry count is overridden, per the same trap.
- `client.audio.transcriptions.create(model="whisper-large-v3-turbo", file=("turn.wav", wav_bytes, "audio/wav"), response_format="json", temperature=0, language=…)`.
- The API needs a **container**, not raw PCM. `backend/app/pipeline/audio.py::pcm16_to_wav(pcm: bytes, sample_rate: int) -> bytes` writes the 44-byte RIFF header server-side. This is ~15 lines, it is unit-tested, and it keeps the browser from having to know about WAV.
- Free tier 20 RPM / 2 000 RPD — not a constraint for this block.

### Gemini LLM adapter

The exact call shape below is **verified working** (Block 0 §S4, `scratch/spikes/parallel_fc.py`), including the event field names. Do not re-derive it.

```python
client = genai.Client(
    api_key=settings.gemini_api_key,
    http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
)
stream = await client.aio.interactions.create(
    model="gemini-3.5-flash-lite",
    input=user_text_with_history,
    stream=True,
    store=False,
    system_instruction=SYSTEM_PROMPT,
    generation_config={"thinking_level": "minimal"},
    extra_headers={"Api-Revision": "2026-05-20"},
)
async for event in stream:
    if event.event_type == "step.delta" and event.delta.type == "text":
        chunks.append(event.delta.text)
```

- **Streaming, even though Block 2 only needs the final string.** Two reasons: the non-streaming response shape is unverified, and the streaming `delta.type == "text"` shape *is* verified — and it gives Block 3 its TTFT probe for free.
- 🪤 A `thought` step **always arrives first**, even at `thinking_level: "minimal"`. Ignore every step that is not a text delta. Log `llm_first_text_delta_ms` measured to the first `text` delta — never to the first SSE event, which records a fiction (`MASTER-PLAN.md` §Block 3).
- 🪤 `thinking_level`, `system_instruction` and `tools` are **interaction-scoped** and must be pinned on every call.
- `store=False` is mandatory (free-tier input otherwise trains Google).
- ⚠️ Minor unknown: whether `client.aio.interactions.create(...)` must be awaited before `async for`, or is itself async-iterable. The type signature says it returns `AsyncStream[...]` from an async method, so `await` first. If that is wrong it is a 30-second discovery, not a design risk.

**System prompt, Block 2 version** — deliberately plain, and it gets replaced wholesale in Block 4:

> You are Sarjy, a voice travel assistant. You are being spoken to out loud and your reply will be read aloud. Answer in one or two short sentences. No markdown, no lists, no emoji, no stage directions. If you don't know something, say so.

🔒 **Invariant 5:** the transcript is untrusted input. It goes into the request as a delimited user turn, never concatenated into `system_instruction`.

---

## Barge-in — the line, decided here

**Client half ships in Block 2. Server half ships in Block 2. History truncation and tool cancellation are Block 4's.**

Why not defer it all: a playback queue that can stop *now* is a design property of the queue, not a feature bolted on later. Retrofitting it is the classic tarpit, and `.claude/rules/voice/pipeline.md` calls it non-optional.

Why not do all of it: Block 4 introduces two TTS requests and an in-flight tool call per turn. Truncating an assistant turn to what was actually *heard* only becomes meaningful once there is grounding context and memory to protect. That belongs where it bites.

**In Block 2:**

1. `onSpeechRealStart` (not `onSpeechStart`) while state is `speaking` → barge. `onSpeechRealStart` fires only after `minSpeechMs` of confirmed speech, which is exactly the anti-self-interrupt primitive.
2. Playback `stop()`: call `.stop(0)` on every scheduled `AudioBufferSourceNode`, disconnect, clear the set, reset `nextStartTime`. **Do not let the current chunk drain.**
3. Send `{"t":"barge","turn_id":…}`. Server cancels the turn task, closes the Deepgram socket, stops forwarding frames.
4. Client drops any binary frame whose turn is no longer current — the race is real, since frames can already be in flight.
5. The turn is marked interrupted in the UI. Never shown as completed.

**Two guards, because echo cancellation is unproven until task 10:**

- Ignore barge for the first **300 ms** of playback.
- A module constant `BARGE_IN_ENABLED = true`. If the demo shows Sarjy interrupting itself, this is a one-character fix under pressure. Its existence is a stated trade-off, not a hedge.

---

## Failure paths — build these before the happy path

Each has a **named visible behaviour**. A spinner that outlives its operation is the worst state this UI can reach.

| # | Failure | Visible behaviour |
|---|---|---|
| F1 | **VAD assets missing / 404 / wrong content type** | Before `MicVAD.new()`, `HEAD` each asset URL. Non-200 or `text/html` → state `unavailable`, on-screen: *"Voice detection failed to load (`/vad/silero_vad_v5.onnx` returned 404)."* The Start button is disabled with that reason attached. **Never a silent no-op.** |
| F2 | **`MicVAD.new()` throws** | Same `unavailable` state, message = the caught error. A `try/catch` around it, always. |
| F3 | **Mic permission denied** (`NotAllowedError`) | State `mic-blocked`: *"Sarjy needs the microphone to hear you. Allow it in the address bar, then press Retry."* Plus a Retry button. Not a dead end. |
| F4 | **No microphone present** (`NotFoundError`) | State `mic-missing`, distinct message. Different cause, different fix. |
| F5 | **Permission revoked mid-session** | `track.addEventListener("ended", …)` plus `navigator.permissions.query({name:"microphone"}).onchange` where available (wrap in `try/catch` — Safari lacks it). → `mic-blocked`, VAD torn down, Retry offered. |
| F6 | **`AudioContext` refuses 16 kHz** | Fall back to `new AudioContext()` at the device rate. vad-web's own resampler handles any rate ≥ 16 kHz; it only errors below. Log which path was taken. |
| F7 | **Utterance longer than 30 s** | Client timer from `onSpeechStart`; at 30 s force-close the turn and send what it has. Server independently caps accumulated audio at `MAX_TURN_BYTES = 960_000` (30 s × 16 kHz × 2 B) → `turn_failed{stage:"audio"}`. Groq's Whisper window is 30 s; this is not a guess. |
| F8 | **Empty / whitespace-only transcript** | `turn_failed{stage:"stt", message:"I didn't catch that — say it again?"}`, state back to `idle`, no LLM call, no TTS call. Log the raw transcript — Whisper emits filler on near-silence and we want the pattern visible, not a hard-coded blocklist guessed at now. |
| F9 | **STT raises / times out** | `turn_failed{stage:"stt", message:"I couldn't hear that clearly — my transcription service didn't answer."}`. One retry at most (SDK `max_retries=1`), never a 60 s backoff. |
| F10 | **LLM raises / times out / returns empty** | `turn_failed{stage:"llm"}`, plain message. No improvised reply. |
| F11 | **TTS fails before the first chunk** | `turn_failed{stage:"tts", message:"I have an answer but couldn't speak it."}` — **and the `reply` text is already on screen**, because `reply` is sent before `audio_start`. The reviewer still gets the answer. This ordering is the point. |
| F12 | **TTS fails mid-stream** | Send `audio_end` with what was produced, then `turn_failed{stage:"tts"}`. Playback must never be left hanging waiting for an `audio_end` that never comes. |
| F13 | **Socket drops mid-turn** | Block 1's reconnect handles the socket. The turn is abandoned: client clears playback, state → `idle`, notice *"Connection dropped mid-answer — ask again."* Server's turn task is cancelled when the handler exits. |
| F14 | **Provider key missing at runtime** | Providers are built **lazily on first turn**, not at import. A missing key gives `turn_failed{stage:…, message:"…is not configured"}` — it must never stop `/health` or the static mount from serving. **Requirement #4 stays banked even with a broken key.** |
| F15 | **Binary frame with no open turn** | `error{code:"bad_message", recoverable:true}`, frame discarded, socket stays up. |

---

## Files

### Created

| File | Purpose |
|---|---|
| `frontend/scripts/sync-vad-assets.mjs` | Copies the VAD model, worklet and ORT WASM from `node_modules` into `frontend/public/vad/`. ~25 lines, zero dependencies. |
| `frontend/public/vad/` *(generated, gitignored)* | Where the assets are served from, in dev and in `dist/` alike. |
| `backend/app/pipeline/audio.py` | `pcm16_to_wav()` — the RIFF header Groq's API needs. |
| `backend/app/pipeline/turn.py` | `run_turn()` — the one place STT → LLM → TTS is orchestrated, against the Protocols, so it is testable with fakes. |
| `backend/app/providers/groq_stt.py` | `GroqSTT` |
| `backend/app/providers/gemini_llm.py` | `GeminiLLM` |
| `backend/app/providers/deepgram_tts.py` | `DeepgramTTS` |
| `backend/app/providers/factory.py` | Memoised `get_stt() / get_llm() / get_tts()`; raises `ProviderUnavailable` rather than crashing the app. |
| `backend/tests/test_audio.py` | WAV header correctness |
| `backend/tests/test_turn.py` | Every row of §Failure paths that lives server-side, against fakes |
| `docs/measurements/block2-voice-loop.md` | Endpointing sweep, Deepgram TTFB, voice choice |
| `docs/PRs/PR_VOICE_LOOP.md` | Summary · Problem · Solution · Changes · How to Test · Changelog |

### Modified

| File | Change |
|---|---|
| `backend/app/pipeline/protocol.py` | `PROTOCOL_VERSION = 2`; `StartIn`/`EndIn`/`BargeIn`; `TranscriptOut`/`ReplyOut`/`AudioStartOut`/`AudioEndOut`/`TurnFailedOut` |
| `backend/app/main.py` | Binary frames accepted into a per-connection turn buffer; `start`/`end`/`barge` dispatch; turn task lifecycle and cancellation; optional `GZipMiddleware` |
| `backend/app/providers/base.py` | `LLM.complete` → `LLM.reply` (see §Contracts) |
| `backend/app/config.py` | Explicit dotenv paths; `deepgram_api_key`; `deepgram_tts_model`; **`rapidapi_key` becomes optional** — Block 5 re-tightens it in its own adapter. Today a missing RapidAPI key would stop Block 2's app dead. |
| `backend/tests/test_protocol.py`, `test_ws.py` | New messages; F15 |
| `frontend/src/protocol.ts` | Mirror of the above, by hand, no zod |
| `frontend/src/net/connection.ts` | `sendBinary()`; callbacks `onTranscript`, `onReply`, `onAudioStart`, `onAudioChunk`, `onAudioEnd`, `onTurnFailed`; `ws.binaryType = "arraybuffer"` |
| `frontend/src/audio/capture.ts` | Real body: shared mic stream, constraints, `floatToPCM16()` (the conversion math lifted verbatim from the spike worklet) |
| `frontend/src/audio/turn.ts` | Real body: asset guard, `MicVAD` construction and options, endpointing instrumentation, the gate flag |
| `frontend/src/audio/playback.ts` | Real body: `PlaybackQueue` class with explicit scheduling and immediate `stop()` |
| `frontend/src/App.tsx` | The state machine, the permission states, Start/Stop, transcript + reply display |
| `frontend/package.json` | `dev` and `build` run the sync script first; add a `test` script |
| `frontend/eslint.config.js` | Drop the `src/spike/**` ignore once the spike is deleted |
| `.gitignore` | `frontend/public/vad/` |
| `.env.example` | `DEEPGRAM_API_KEY`, `DEEPGRAM_TTS_MODEL` |

### Deleted — in the same commit that lands real capture

`frontend/spike.html`, `frontend/src/spike/main.ts`, `frontend/src/spike/worklet.js`. Block 1's plan committed to this ("not later, or they become permanent"). The int16 conversion math survives, in `capture.ts`.

---

## Task list

Ordered. Each item is independently checkable.

| # | Task | Verification | Est |
|---|---|---|---|
| 1 | **VAD assets.** `sync-vad-assets.mjs` copies `vad.worklet.bundle.min.js`, `silero_vad_v5.onnx`, `silero_vad_legacy.onnx` from `@ricky0123/vad-web/dist`, and `ort-wasm-simd-threaded.mjs` + `ort-wasm-simd-threaded.wasm` from `onnxruntime-web/dist`, into `frontend/public/vad/`. Wire it into `dev` and `build` with `&&` (explicit, not an npm `pre` lifecycle hook). `.gitignore` the output | `npm run dev`, then `curl -sI http://localhost:5173/vad/silero_vad_v5.onnx` → `200` and `content-length` ≈ 2 327 524, **not** `content-type: text/html` | 30 m |
| 2 | **F1 + F2 first.** `assertVadAssets()` HEAD-checks each URL and throws a legible error naming the URL and status. `App` renders that error as the `unavailable` state with the Start button disabled | Rename `public/vad/` temporarily → the page says exactly which file is missing and offers no dead Start button. Rename back | 15 m |
| 3 | **Protocol v2**, both ends, plus `test_protocol.py` cases | `make test` — new messages parse, `extra="forbid"` rejects an unknown field, an unknown `t` is ignored client-side | 30 m |
| 4 | **Config.** Explicit dotenv paths (`backend/.env` then repo-root `.env`, `override=False`); `deepgram_api_key`, `deepgram_tts_model`; `rapidapi_key` optional | `uv run python -c "from app.config import load_settings; print(load_settings().deepgram_tts_model)"` from `backend/` | 15 m |
| 5 | **`run_turn()` + every server-side failure path (F7–F12, F14) against fakes.** No real provider yet | `make test` — one test per failure row, each asserting the exact message sequence | 45 m |
| 6 | **STT adapter + `pcm16_to_wav`** | `make test` for the header; then a throwaway script sends a WAV of Omar's voice and prints the transcript | 25 m |
| 7 | **LLM adapter** (streaming, text deltas only, `thought` ignored) | Throwaway script: prompt in, sentence out, and `llm_first_text_delta_ms` logged | 25 m |
| 8 | **TTS adapter** — Deepgram WS, `container=none`, the `RIFF` assertion, `tts_ttfb_ms` log | Throwaway script writes a `.wav` (header added locally) from the returned PCM; play it and hear it. The RIFF assertion does not fire | 45 m |
| 9 | **Wire `main.py`**: binary buffer, `start`/`end`/`barge`, turn task + cancellation, F13/F15 | `make test` extended `test_ws.py`; binary-with-no-turn returns `error` and the socket survives | 30 m |
| 10 | **Client capture + VAD + endpointing.** One stream, `getStream` override; `startOnLoad: false`; **override `pauseStream`/`resumeStream`** (see trap below); gate flag during playback; F3–F6 | Browser: speak → `listening`; go quiet → `end` sent; say "mhm" → `onVADMisfire`, no turn | 45 m |
| 11 | **Playback queue + barge-in stop** | Browser: a synthetic PCM stream plays gaplessly; `stop()` silences it within one frame | 35 m |
| 12 | **UI state machine and permission states** | Every state in §Failure paths is reachable and legible. No spinner without an operation behind it | 30 m |
| 13 | 🚩 **Full local turn, on speakers.** Say *"What's the capital of Japan?"* and hear the answer | The gate's happy path, locally. Echo cancellation confirmed: Sarjy does not interrupt itself | 30 m |
| 14 | **Endpointing sweep.** See §Measuring endpointing | `docs/measurements/block2-voice-loop.md` has a table, a chosen value, and a written reason | 30 m |
| 15 | 🚩 **Deploy and walk the gate against the public URL.** Collect Deepgram TTFB n≥5 from `modal app logs sarjy`. Try Safari; record the result either way | §The gate, in order | 35 m |
| 16 | **Delete the spike**, drop the eslint ignore, PR doc, commit drafts, walkthrough with Omar | `npm run lint` clean with no ignore; `docs/PRs/PR_VOICE_LOOP.md` exists | 30 m |

≈ **7 h 15 m** at task level; call it **6.5–7.5 h**, with tasks 5–9 compressing if nothing surprises.

### 🪤 Traps inside task 10, all read from the installed package source

- **`getStream` override is mandatory.** vad-web's default `getStream` calls its own `getUserMedia`, which would open a *second* mic stream — exactly what Block 0 noted the spike did and said Block 2 must not.
- 🚨 **`pauseStream` default calls `track.stop()` on every track.** With a shared stream that permanently kills the mic, and the default `resumeStream` then re-prompts via a fresh `getUserMedia`. Override both to no-ops that return the shared stream. **Better still: never call `vad.pause()` during a conversation** — gate with a boolean instead. The VAD must keep running during playback, because that is what makes barge-in possible.
- **`startOnLoad: false`.** The default is `true`, which fires `getUserMedia` inside `MicVAD.new()` — a mic prompt on page load with no explanation, which `browser-audio.md` names as an anti-pattern. Construct at page load (downloads the ~16 MB of assets while the reviewer reads the screen), prompt on the Start click.
- **`processorType: "AudioWorklet"`**, never `"auto"`. `ScriptProcessor` is deprecated and main-thread.
- **`model: "v5"`**, not the package default `"legacy"`. v5 uses 512-sample frames (32 ms) against legacy's 1536 (96 ms), so endpointing granularity is 3× finer — and endpointing is the largest term in the budget. `silero_vad_legacy.onnx` is copied too (1.8 MB) so falling back is a one-word change if v5 misfires on breaths.
- **`ortConfig: (ort) => { ort.env.wasm.numThreads = 1; ort.env.logLevel = "warning"; }`.** Without cross-origin isolation `SharedArrayBuffer` is unavailable and the threaded build falls back anyway; pinning it removes a worker-spawn path that can fail obscurely. `logLevel` stays loud enough to see problems during the build.
- **The AudioContext is created at page load (suspended) and passed in as `audioContext`** — options are frozen at `new()`. `captureCtx.resume()` and `playbackCtx.resume()` both happen **inside the Start button's click handler**, which is the user gesture the Web Audio spec requires.

### 🪤 Traps inside task 15

- `frontend/dist/vad/*` must actually reach the container. `modal_app.py` reads the *local* `dist/` tree at deploy time and **will not tell you it is stale** — `make deploy` runs `build-frontend` first, so use `make deploy`, never a bare `modal deploy`.
- Python's `mimetypes` maps `.wasm` → `application/wasm` and `.mjs` → `text/javascript` (verified locally), so Starlette's `StaticFiles` serves both correctly. `.onnx` has **no** registered type and falls back to `application/octet-stream`, which is fine — it is fetched with `fetch()`, not `instantiateStreaming`.
- The ORT WASM blob is ~14 MB. `app.add_middleware(GZipMiddleware, minimum_size=1024)` roughly quarters the first load, costs two lines, and does not touch the WebSocket scope. **This is the first thing to cut if the block runs long.**

---

## Measuring endpointing (task 14)

The spike measured speech-**start** → speech-end, which includes the utterance itself and is not the latency term. The term we want is **acoustic end of speech → `onSpeechEnd` fires**.

**The instrument, and it is four lines:**

```
onFrameProcessed(probs, frame):
    if probs.isSpeech > positiveSpeechThreshold: tLastSpeechFrame = performance.now()
onSpeechEnd(audio):
    endpointDelayMs = performance.now() - tLastSpeechFrame
```

**The sweep:** `redemptionMs` ∈ {400, 600, 800}, five utterances each, same sentence, same room.

Record per value: **median `endpointDelayMs`**, and the **false-cut count** (times Sarjy endpointed while Omar was mid-sentence, e.g. across a natural comma pause). Then say "mhm" five times at the chosen value and confirm every one produces `onVADMisfire`, not a turn.

**Write the chosen value and the reason down.** `.claude/rules/voice/browser-audio.md` and `pipeline.md` both require it: *"the silence threshold is a product decision, not a constant."* It trades cutting the user off against making them wait, and it is the largest single term in the chain — larger than any provider call, which is worth saying out loud in the walkthrough because a reviewer will not expect it.

Then **update `TDD.md` §Latency budget**, replacing the "~600 ms (still an estimate)" endpointing row with the measurement and its `n`.

---

## Two deliberate design decisions, recorded because they will be questioned

### 1. The audio that reaches STT comes from the VAD, not from a second capture worklet

`onSpeechEnd` hands back a `Float32Array` at 16 kHz that already includes `preSpeechPadMs` of lead-in — the exact segment we want. Running our own parallel `AudioWorklet` capture graph and slicing a ring buffer by VAD timestamps would produce the same bytes with twice the moving parts, on the tightest day of the schedule.

**What is lifted from the spike** is the float32 → int16 conversion (clamp to [-1, 1], `s < 0 ? s * 0x8000 : s * 0x7fff`) and the 16 kHz `AudioContext` decision that Section A proved. What is dropped is a second capture graph the VAD already provides.

**The cost, stated plainly:** the whole utterance uploads *after* speech ends — roughly 160 KB for 5 s, ~130 ms on a decent uplink, more on bad conference wifi. Streaming during speech would hide that, but it requires the second capture graph *and* it would break Block 1's "a turn never spans a connection" invariant by starting the network work before `ensureFresh()` can run. **Block 3 measures this leg. If it turns out to matter, the dual-capture path is the named upgrade.**

### 2. Nothing goes over the network until `onSpeechEnd`

```
onSpeechStart → state "listening" (local only, no network)
onSpeechEnd   → await connection.ensureFresh()   ← Block 1's contract, here
              → send {"t":"start"} + binary chunks + {"t":"end"}
```

Because STT is batch (Groq's Whisper is a 30 s window; the turn must be endpointed before it is sent — `TDD.md` §The batch-STT constraint), there is nothing to gain from streaming during speech. And awaiting `ensureFresh()` here makes *"a turn never spans a connection"* true by construction rather than by care: a socket rotation can only happen while idle or while the user is speaking, never between `start` and `audio_end`.

`ensureFresh()` already exists in `frontend/src/net/connection.ts` and rotates the socket if less than `TURN_BUDGET_MS` (30 s) of its life remains. **This is the single call that keeps Block 1's reconnect design intact.** It goes on the first line of the `onSpeechEnd` handler.

---

## Verification

Run all of these. Show the output; do not assert it passed.

```bash
# Backend
cd /Users/omarsalama/Projects/Sarjy/backend
make typecheck        # mypy strict, 0 errors
make lint             # ruff, 0 warnings
make test             # pytest -q

# Frontend
cd /Users/omarsalama/Projects/Sarjy/frontend
npm run typecheck     # 0 errors
npm run lint          # 0 warnings, and no src/spike ignore left
npm run build         # then: ls -la dist/vad/  -> 5 files present

# The VAD assets are actually served
curl -sI http://localhost:5173/vad/silero_vad_v5.onnx | head -3
curl -sI http://localhost:5173/vad/vad.worklet.bundle.min.js | head -3
curl -sI http://localhost:5173/vad/ort-wasm-simd-threaded.wasm | head -3
#  -> HTTP/1.1 200 OK on all three, and NOT content-type: text/html

# Same three against the deployment, after `make deploy`
curl -sI https://<deployed-url>/vad/silero_vad_v5.onnx | head -3
```

**What proves it worked, in order:**

1. `make test` prints `N passed` with a test for **every row** of §Failure paths that is server-side (F7–F15).
2. `npm run build` produces `dist/vad/` containing the model, the worklet and the two ORT files.
3. The three `curl -sI` calls return `200` with a binary content type — locally **and** against the deployment.
4. **An end-to-end voice turn against the deployed URL**, on speakers: state moves `idle → listening → thinking → speaking → idle`, the transcript and reply appear on screen, and the answer is audible and correct.
5. `modal app logs sarjy` shows `tts_ttfb_ms=…` for at least 5 turns, with a median recorded in `docs/measurements/block2-voice-loop.md` **beside the vendor's <200 ms claim**.
6. `docs/measurements/block2-voice-loop.md` has the endpointing table, the chosen `redemptionMs`, and the reason.

---

## The gate — walked in order, against the deployed URL

Master plan: *"speak to the deployed URL and hear a sensible spoken reply. Requirement #1."* Concretely:

| # | Do | Pass looks like |
|---|---|---|
| 1 | Open the public URL in a fresh Chrome window | Calm screen, state `idle`, one Start button with a reason for the mic attached. No mic prompt yet |
| 2 | Click Start | Mic prompt appears. Allow it. State stays `idle`, and the page says it is listening for you |
| 3 | Say *"What's the capital of Japan?"*, then stop | `listening` while speaking; within the measured endpointing delay of going quiet it moves to `thinking` |
| 4 | Wait | Transcript appears, then the reply text, then audio — **audible on speakers**, correct, and Sarjy does **not** interrupt itself |
| 5 | Say *"and what about Korea?"* | It answers coherently — in-session history is working |
| 6 | Start a long answer, then talk over it | Audio stops **immediately**, not at the end of the chunk, and the new turn starts |
| 7 | Deny the mic in a fresh incognito window | A legible recoverable message and a Retry button. Not a dead end, not a spinner |
| 8 | Leave the tab open 3 minutes, then speak again | Still works — Block 1's rotation happened underneath and a turn never spanned it |
| 9 | Kill wifi mid-answer, restore it | Playback clears, a notice explains, state returns to `idle`, and the next turn works |

**Steps 4, 6 and 7 are the block.** Step 4 is requirement #1. Step 6 is the voice-UX rubric line. Step 7 is Invariant 7.

---

## Draft commits

Small and coherent; Omar commits. Suggested boundaries:

1. `build(frontend): serve VAD model and ONNX runtime from /vad` — sync script, `.gitignore`, package scripts, asset guard
2. `feat(protocol): v2 — turn start/end/barge, transcript, reply, audio framing`
3. `feat(providers): Groq STT, Gemini text reply, Deepgram streaming TTS`
4. `feat(pipeline): run_turn, with every failure path visible`
5. `feat(frontend): capture, VAD endpointing, playback queue, barge-in`
6. `feat(frontend): conversation state machine and microphone permission states`
7. `chore: remove the Block 0 audio spike, now that capture is real`
8. `docs: Block 2 measurements — endpointing sweep and Deepgram TTFB`

---

## Carried into Block 3

- `llm_first_text_delta_ms`, `stt_ms`, `tts_ttfb_ms` already exist as `logger.info` lines. Block 3 turns them into the `timings` message with monotonic clocks, adds `endpoint_ms` (measured client-side, sent on `end`) and `first_audio_ms`.
- The measured endpointing value — Block 3's budget starts from it, not from the ~600 ms estimate.
- The upload-after-endpoint leg (§Design decision 1). If it is material, dual-capture streaming is the named upgrade.
- `run_turn()` is the seam Block 4 splits into call 1 / opener / call 2.
- `PlaybackQueue` already handles two sources per turn; Block 4's opener needs no change to it.

---

## Open / assumed, stated rather than buried

- **Unverified:** Deepgram's <200 ms TTFB. That is why task 15 measures it. If the measured median is above ~600 ms, the TDD's opener arithmetic (§Latency budget) needs re-deriving *again* and Omar should hear about it the same day.
- **Assumed:** `await client.aio.interactions.create(..., stream=True)` then `async for`. The sync form is verified from Block 0; the async form is inferred from the installed type signature. A 30-second discovery if wrong.
- **Assumed:** ORT 1.30 requests `ort-wasm-simd-threaded.{mjs,wasm}` and not the `.jsep` variant, because we import `onnxruntime-web/wasm`. **Verify in the browser's Network tab in task 1.** If it asks for `.jsep`, that file is 28 MB and the trade-off needs a decision rather than a reflex copy.
- **Assumed:** Safari accepts `new AudioContext({sampleRate})` for both 16 kHz and 24 kHz. F6 covers the capture side. If playback's context lands at a different rate, `createBuffer(1, n, 24000)` still resamples on playback — degraded, not broken.
- **Open:** whether echo cancellation holds on Omar's laptop speakers. Unknown until task 13, and Block 0 never tested it. `BARGE_IN_ENABLED` exists because of this.
- **Deliberate:** the frontend has no unit tests. Its failure modes are browser-level — permissions, audio graphs, worklet loading — and none of them are caught by a Node test runner. The verification is the end-to-end turn. A `test` script exists so the command contract in `AGENTS.md` holds; adding vitest for one pure function is not worth the dependency on this schedule. **Say this out loud in the walkthrough rather than letting it be found.**
- **Not re-litigated here:** the region tension in Block 0 §S2. `us-east` is deployed and the URL is not yet shared. Task 15 is the last cheap moment to change it.
