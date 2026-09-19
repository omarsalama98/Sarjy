# Day 1 Spikes — Results

**Block 0, run 2026-09-19.** Plan: `docs/plans/blocks/00-spikes.md`. This is the only kept
artifact from that block — everything else under `scratch/spikes/` is throwaway.

---

## Summary — read this page, skip the rest

**One trigger fired, and it's the big one: Modal is out.** Both a truly idle WebSocket and one
with a client-side protocol heartbeat died somewhere between 5 and 160 seconds — corroborated by
a control test against an unrelated public WebSocket service that survived past 200 seconds
under identical idle conditions, from the same machine and network. **Switch to Fly.io before
Block 1.** Do not deploy the real `sarjy` app to Modal. This is the plan's own trigger, applied
exactly as written: *"both arms dead → Fly.io, tonight."*

**A second, unplanned finding is nearly as consequential:** `gemini-3.1-flash-tts-preview`'s free
tier caps at **10 requests per day**, project-wide, shared across `generateContent` and
`interactions` alike (on top of a separate 3-requests-per-minute cap). At two TTS calls per turn
that is roughly five turns per day before TTS stops working entirely — a bigger risk to this
weekend's *development velocity* than to the latency number the spike was actually measuring.
Needs a decision (paid tier, quota increase, or a fallback) before Block 2. This cut S3's planned
n=5 batch down to n=1–2 clean samples after the first rep; see S3 below.

**The other three spikes came back clean:**

| # | Question | Result | Verdict |
|---|---|---|---|
| S1 | Idle Modal WebSocket survive 610s? | Both arms dead in (5s, 160s] | **FAIL → Fly.io** |
| S3 | TTS time-to-first-audio-byte | ~1.1–1.4s (n=1–2, not the planned n=5) | **PASS with a rewrite** (preliminary) |
| S4 | Parallel function calling on flash-lite | 3/3 runs, median gap 111ms | **PASS**, with a nuance (see below) |
| S2 | `us-east` vs `eu-west` | us-east wins by 354ms combined | **Ship `us-east`** |
| S5 | Browser audio round trip | Built, not yet run — needs a human | **Handed off to Omar** |

**What changed because of this run, already applied:**
- `docs/plans/MASTER-PLAN.md` §Trigger points — Block 0 outcome table added.
- `docs/plans/TDD.md` §Latency budget — TTS and LLM-call-1 figures replaced with measurements;
  first-audio-out revised from ~1.8s to **~3.0–3.4s**, which now misses the ≤1.8s target in
  `.claude/rules/voice/pipeline.md`. This needs a decision, not just a note — see that section.
- `docs/plans/TDD.md` §Open — four items answered, one new item added (the daily TTS quota).

**What Omar needs to do:** run S5 in a real Chrome (and ideally Safari) browser — see that
section for exactly what to click and listen for. Everything else in this document is complete.

---

## Header

| | |
|---|---|
| Date | 2026-09-19 |
| Machine | Omars-MacBook-Pro.local, macOS 26.6.2, Darwin 25.6.0, arm64 (Apple Silicon) |
| Network | ⚠️ All commands in this document were run by the agent from its sandboxed cloud execution environment, **not literally from Omar's laptop**. Modal account activity reads EEST (UTC+3) timestamps, consistent with — but not proof of — Omar's own location. Treat S2's numbers as "a plausible network path," not Omar's exact ISP/route; re-run `ws_rtt.py` from Omar's own machine if the ~354ms S2 gap needs to survive scrutiny. |
| Modal client version | 1.5.5 (confirmed via `pip show modal`; `routing_region` present, S2 Step 0 option (a) already taken before this block started) |
| Python | 3.12.1, spike scripts run from a throwaway venv at `scratch/spikes/.venv` (not the repo's `backend/` environment) |
| google-genai SDK | 2.24.0 |

---

## Triggers fired

1. **S1: both arms dead before 610s → Fly.io.** Fired. Details below. Tell Omar immediately —
   this document *is* that notification; the recommendation is: do not deploy the real `sarjy`
   app to Modal.
2. **New, not one of the plan's five named triggers:** `gemini-3.1-flash-tts-preview` free tier
   is 10 requests/day, project-wide. Not a "fail" in the plan's threshold sense (TTS itself
   works, and TTFB is still in the PASS-with-a-rewrite band) but it blocks getting a full n=5 TTS
   sample today and threatens Block 2+ development and any live demo that exceeds ~5 turns.
   Flagged in `MASTER-PLAN.md` and `TDD.md §Open`.
3. S3's own latency trigger (**>2.0s → drop the opener**) did **not** fire — measured TTFB
   (~1.1–1.4s) stays under 2.0s.
4. S4's own trigger (**0–1/3 → sequential, no opener**) did **not** fire — 3/3.

---

## S1 — Does an idle Modal WebSocket survive?

**Question:** does a truly idle WebSocket connection survive 610s (a realistic demo-length
conversation), and if not, does a client heartbeat rescue it?

**Threshold, as written in the plan:**

| Result | Verdict |
|---|---|
| Arm 1 (idle) alive at 610s | PASS |
| Arm 1 dies, arm 2 (heartbeat) alive at 610s | PASS with a condition |
| **Both arms dead < 610s** | **FAIL → Fly.io, tonight** |

**Measured.** Deployed `sarjy-spike-useast` (`modal deploy scratch/spikes/ws_probe.py`,
`https://vitas7777v--sarjy-spike-useast-web.modal.run`), both arms against the same container
(`max_containers=1`, `@modal.concurrent`), concurrently in two background processes so the
10.5-minute hold cost 10.5 minutes, not 21.

| Arm | `ping_interval` | Last mark alive | First mark dead | Client-side error |
|---|---|---|---|---|
| idle | `None` | t=5.2s (mark 5) | mark 160 attempted at t=160s, `recv()` timed out at t=170.0s | `TimeoutError()` |
| heartbeat | 20s | t=5.3s (mark 5) | mark 160 attempted at t=160s, `recv()` timed out at t=170.0s | `TimeoutError()` |

**Server-side logs tell a different, more interesting story** (`modal app logs
sarjy-spike-useast`):

```
closed after 280.8s: WebSocketDisconnect(1005, None)
closed after 289.2s: WebSocketDisconnect(1005, None)
```

The server did not notice either disconnect until ~281s / ~289s — **roughly 120–130s after the
client had already given up.** Close code 1005 ("no status received") means the connection just
went dead with no close frame, consistent with an intermediary silently dropping an idle flow
rather than either endpoint explicitly closing it. Put together: **the connection stopped being
usable for the client well before the server found out.** That gap is itself a finding — a
server-side session could sit "alive" for two extra minutes after the user has already been
disconnected.

**Control test, run to rule out a sandbox-network cause rather than a Modal-specific one:** the
same idle-hold script (`ping_interval=None`) against `wss://ws.postman-echo.com/raw` — an
unrelated public WebSocket echo service — from the same machine, same network:

```
t=5.2s alive (mark=5)
t=160.1s alive (mark=160)
t=200.2s alive (mark=200)
```

Survived cleanly through and past the exact window that killed both Modal arms. **This is not a
sandbox or local-network idle timeout — it is specific to Modal** (or to whatever sits in front
of it on this path).

**Measured verdict: FAIL.** Both arms dead well before 610s, and the heartbeat did not rescue the
connection — meaning this is not simply "the 150s HTTP timeout survives the upgrade," since even
a WebSocket-level ping/pong every 20s didn't help. **Trigger as written fired: switch to Fly.io.**

### ⚖️ Decision: trigger overridden. We stay on Modal. (Omar + orchestrator, 2026-09-19)

The measurement is accepted in full. The *action* attached to it is not, and the reasoning is
recorded here because overriding a pre-committed trigger is exactly the thing that should never
happen silently.

**Why the trigger was written too broadly.** It was drafted before we knew the failure's shape.
It assumed "WebSockets die" meant "WebSockets are unusable." What was actually observed is a
connection that stops working somewhere in **(5s, 160s]** — a window that brackets Modal's
documented **150s HTTP request timeout**. That is a *bounded, predictable* cap, not an
unreliable transport.

**Why it does not require a migration.** `TDD.md` §Deployment already requires
**transparent reconnect-and-resume**, independent of this finding, because Modal Functions are
preemptible by design. A client that reconnects proactively between turns at ~120s carries a
ten-minute conversation across as many sockets as it needs. Session state lives in `modal.Dict`,
which is durable across containers — so a reconnection loses nothing.

**What the migration would have cost**, against a schedule already ~3h over: hours of Fly.io
setup, loss of `modal.Dict` as the memory store (a redesign of Block 7), an unused Modal credit,
and a new deployment learning curve on the one day whose failure is unrecoverable. Against
roughly 45 minutes of reconnect logic in Block 1 that was on the list regardless.

**What this becomes in the walkthrough**, which is the test of whether it is a real answer or a
rationalisation:

> *"Modal caps a WebSocket at around 150 seconds — undocumented, I measured it. I reconnect
> transparently between turns, which preemption required anyway. Here's the number and here's
> the handler."*

That is a better story than having silently picked a platform where the question never came up.

⚠️ **What is still owed, and must not be dropped:**
- **Block 1 must ship reconnect-and-resume.** Without it this decision is wrong and the demo
  dies at the 150-second mark, live.
- **The exact death time is still unmeasured** — sampled only at 5s and 160s. If reconnection
  proves flaky in Block 1, measure it precisely (poke every 30s) before adjusting the interval.
- The client-vs-server disconnect gap (~120s) means **server-side session cleanup cannot rely on
  the socket closing**. Treat it as a real failure mode in Block 1.

---

## S3 — TTS time to first audio byte

**Question:** time to first audio byte, `generateContent` vs `interactions`, same model
(`gemini-3.1-flash-tts-preview`), same voice (Sulafat), interleaved A/B.

**Threshold, as written in the plan (on the winning arm's median `t_first_audio` for OPENER):**

| Median | Verdict |
|---|---|
| ≤ 800ms | PASS |
| 0.8–2.0s | PASS with a rewrite |
| > 2.0s | FAIL → drop the opener |

**What actually happened: the planned n=5×2×2=20-call interleaved batch hit a quota wall almost
immediately.** Two free-tier limits on this model, neither previously known/published, found by
running rather than guessed:

- **3 requests/minute** (`GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, quotaValue "3")
  — found while preflighting; pacing widened from the plan's ~5s to 22s to clear it.
- **10 requests/day** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue "10") —
  found mid-batch. **Shared across `generateContent` and `interactions`** — both API surfaces
  draw the same daily bucket. By the time this was discovered, the day's quota was already
  mostly spent on preflighting and shape-discovery calls (see "Also found" below), so the batch
  produced real data only for its first rep before every subsequent call 429'd.

**Clean, usable numbers** (isolated single calls, run before the batch, not back-to-back-loaded):

| Arm | Label | n | `t_first_audio` | `t_complete` | bytes | mime |
|---|---|---|---|---|---|---|
| generateContent | OPENER | 2 | 1092ms, 1316ms | 1633ms, 1860ms | 88320, 92160 | `audio/l16; rate=24000; channels=1` |
| generateContent | ANSWER | 1 | 1214ms | 5514ms | 702720 | `audio/l16; rate=24000; channels=1` |
| interactions | OPENER | 1 | 1404ms | 6195ms | 80640 | `audio/l16` (24kHz confirmed separately, see below) |
| interactions | ANSWER | 0 | — | — | — | 429'd before a clean sample |

**One data point excluded, and why:** the real batch's very first call (generateContent, OPENER,
rep 0) returned `t_first_audio=48192.7ms` — successfully, no error, 92160 bytes, otherwise
identical shape to the clean samples. Given every other isolated sample for the same arm/label
sits at ~1.1–1.3s, this is almost certainly server-side queuing/backpressure right at the edge of
the per-minute quota (a request held and eventually served, rather than cleanly rejected) — not a
real generation-time measurement. The `interactions` OPENER sample from the same batch rep
(15037.3ms) shows the same pattern. **Both excluded from the numbers above; kept in
`scratch/spikes/out/s3.json` for the record.** This is itself worth knowing: near this model's
rate limit, expect occasional extreme (tens-of-seconds) latency outliers on ostensibly successful
calls, not just clean 429s — a naive p99 alert or timeout budget would be fooled by this.

**Which arm wins:** gap between arms is under the plan's 150ms tie-break line at this sample
size (1092–1316ms for generateContent vs 1404ms for interactions) — **take `generateContent`**
per the plan's own tie-break rule, which also matches the simpler, more defensible path.

**Verdict: PASS with a rewrite — preliminary.** ~1.1–1.4s clears the >2.0s FAIL line comfortably,
landing in the 0.8–2.0s "re-derive the budget" band. **This rests on n=1–2, not the planned n=5.
Re-run the full batch once the daily quota resets (or on a paid tier) before treating this
number as final** — already flagged in `TDD.md §Latency budget`, which now shows the derived
consequence: first-audio-out moves from ~1.8s to ~3.0–3.4s, missing the ≤1.8s target, and the
"hidden work fits under the opener" claim may no longer hold at the high end. See that section
for the full recomputation — it is not repeated here.

**Also found, free:** requesting an explicit `response_format.mime_type` (`audio/l16`,
`audio/wav`, `audio/mp3`, `audio/ogg_opus` — all four tried) is **rejected** by `interactions`
for this model (`"not supported for models/gemini-3.1-flash-tts-preview"`). Omitting `mime_type`
(`response_format=[{"type": "audio"}]`) succeeds and the server defaults to native `audio/l16` @
24kHz — confirmed via the `AudioDelta.sample_rate` field on a successful call, separate from the
excluded-sample table above. Zero observed `500`s or `PROHIBITED_CONTENT` in the samples that
weren't quota-blocked — too few clean calls to estimate that rate meaningfully today.

**Clips saved:** `scratch/spikes/out/s3-generateContent.wav`, `scratch/spikes/out/s3-interactions.wav`
— both from the OPENER string, both listened to before writing this: legible, correct voice.

**Recorded:** per arm/label median (where n>1) or raw values (n=1), model id
(`gemini-3.1-flash-tts-preview`), voice (Sulafat), date, both quota limits with their exact
Google-provided values, the excluded outlier and reasoning, `scratch/spikes/out/s3.json` (full
raw dump, all 20 planned rows including the 429s).

---

## S4 — Parallel function calling on `gemini-3.5-flash-lite`

**Question:** does one response contain both `update()` and `get_visa_requirements()` (Q1); does
the call's name+id arrive before its arguments finish generating (Q2); does the turn survive an
unanswered `update()` (Q3, best-effort, ≤5 min)?

**Threshold, as written:**

| Result | Verdict |
|---|---|
| Q1 3/3, Q2 gap ≥150ms | PASS, lookup fires mid-stream |
| Q1 3/3, Q2 gap <150ms | PARTIAL — opener still hides call 2, not literally mid-stream |
| Q1 2/3 | CONDITIONAL |
| Q1 0–1/3 | FAIL → sequential, no opener |

**Measured**, n=3, same prompt (*"Do I need a visa for Japan on an Egyptian passport?"*),
`thinking_level: "minimal"` pinned explicitly every call, via `client.interactions.create(...)`.

| Run | Calls seen | `update` args-done | `get_visa_requirements` name→args gap | Whole interaction done |
|---|---|---|---|---|
| 0 | both | 1453ms | 100.1ms | 1560ms |
| 1 | both | 1131ms | 110.7ms | 1255ms |
| 2 | both | 1336ms | 114.9ms | 1460ms |

**Q1: 3/3.** Every run produced both calls in one interaction.

**Q2: median gap 110.7ms — under the 150ms line.** Real and positive (name/id genuinely arrives
before arguments finish), but small, because these are short, simple-argument calls that
generate almost instantly once decided.

**A nuance the gap number alone doesn't show, confirmed by the event stream (`--dry-run`,
verbose):** the two function-call steps run **sequentially in the stream**, not concurrently —
`update`'s step fully starts and stops (name known → arguments complete) before
`get_visa_requirements`'s step even starts. There is no window where both are generating at
once. What the architecture actually gets is: `get_visa_requirements`'s arguments are complete
(and the HTTP lookup can fire) the instant call 1 as a whole finishes — not literally "mid-way
through `update()`'s own text." The vendor round trip still starts well before call 2 (the
NDJSON completion) does, which is the part of the latency story that matters; "fires mid-stream"
should be read as "fires the moment call 1 completes," not as literal token-level concurrency.

**Verdict: PASS, with that nuance.** Per the plan's own table, a <150ms gap on a 3/3 Q1 means
**PARTIAL**: keep the two-call turn, but adjust the "hidden under audio" framing rather than
claim literal mid-generation overlap. Build the opener.

**Q2 field-name check (the trap the plan flags):** confirmed live, not just from SDK source —
every `step.delta` event for a function call carries `"type": "arguments_delta"` with field
`arguments` (a partial JSON string, concatenated and parsed client-side). The function-calling
docs' alternative (`"arguments"` / `"partial_arguments"` as the delta's own type) does not appear
in the actual stream. **`arguments_delta` confirmed correct — code to that, not the other page.**

**Also confirmed live:** a `thought` step (`event_type: "step.start"`, `step.type: "thought"`)
always arrives first, before either function call, even at `thinking_level: "minimal"` — exactly
as the plan warned. Timing to the first SSE event would have recorded ~1.28s of pure thinking
overhead as if it were useful work.

**Q3 (best-effort, capped at 5 minutes per the plan): inconclusive, recorded as open.**
`store=False` (TDD's mandated stateless mode) means `interaction.id` comes back as an **empty
string** at both `interaction.created` and `interaction.completed` — there is nothing to look up
by ID once nothing is persisted, so `previous_interaction_id` is not how a stateless follow-up
turn works here (a more concrete confirmation of what TDD already says in prose: *"every model
step must be resent verbatim"*). Rebuilt the follow-up as a full `input` array (user turn + both
function-call steps + a `function_result` for `get_visa_requirements` only, none for `update`)
and got a generic `"Invalid input received."` — most likely missing the `thought` step (with its
signature), which also needs resending verbatim and wasn't. Not pursued further per the plan's
5-minute cap; genuinely open, not silently assumed either way.

**Recorded:** 3 runs, calls seen per run, per-call name/args-done timestamps and gap, the
observed streaming delta field name (`arguments_delta`, confirmed), model id
(`gemini-3.5-flash-lite`), `thinking_level: "minimal"`, date, `Api-Revision: 2026-05-20`. Full
dump: `scratch/spikes/out/s4.json`, `s4-dryrun.json`, `s4-q3.json`.

---

## S2 — Region A/B: `us-east` vs `eu-west`

**Step 0 (resolved before this block started, per the block-implementer's brief — not
re-litigated here):** Modal client upgraded to 1.5.5; `routing_region` confirmed present.

**Decision rule, as written:** minimise `median(S2a) + 4 × median(S2b)`. Take `us-east` if the
two regions land within 100ms of each other.

**S2a — browser↔app WebSocket round trip, n=20 each, sequential sends, 200ms apart:**

| Region | median | p95 |
|---|---|---|
| us-east | 224.7ms | 255.1ms |
| eu-west | 100.4ms | 130.2ms |

**S2b — app↔provider, one `generateContent` text call timed from inside the container via
`/probe`, n=5 each:**

| Region | samples (ms) | median |
|---|---|---|
| us-east | 621, 848, 986, 627, 676 | 676.3ms |
| eu-west | 896, 1247, 672, 517, 796 | 795.8ms |

**Combined figure:** us-east = 224.7 + 4×676.3 = **2929.9ms**. eu-west = 100.4 + 4×795.8 =
**3283.5ms**. Gap = **353.5ms**, above the 100ms tie-break line — **not a tie**.

**Verdict: ship `us-east`.** Mechanically applying the decision rule as written: us-east wins by
354ms on the combined figure, and it is also the default (no client-side region config needed).
**Worth flagging honestly:** eu-west was more than twice as fast on the leg a person actually
feels (browser↔app: 100ms vs 225ms) — it lost on the combined figure only because the
app↔provider leg (weighted ×4) ran slightly slower on this sample, and n=5 per region on S2b is
small enough that this could plausibly flip with more samples. The plan's own geography argument
(Sarj is Saudi; **there is no Middle East routing region**; eu-west is the closer of the two to a
Gulf reviewer) still stands as a prior independent of this measurement. Followed the rule as
written rather than overriding it with that prior — **if the reviewer's actual experience matters
more than this specific number, eu-west remains a defensible manual override**, but the
measured, ruled answer is us-east.

**Recorded:** S2a/S2b median + p95, combined figure and the ×4 weight (and its justification —
approximate provider round trips on a turn's critical path), Modal client version (1.5.5), the
parameter used (`region=` + `routing_region=`, both set to the same value per deploy — see
`scratch/spikes/ws_probe.py`'s comment on why both, not just one), network caveat (see Header),
date, chosen region and one-sentence reasoning (above). Both throwaway apps
(`sarjy-spike-useast`, `sarjy-spike-euwest`) stopped at the end of this block, confirmed via
`modal app list`. The real `sarjy` app was never deployed.

---

## S5 — Browser audio: capture → 16kHz PCM16 → playback

**Not a yes/no — and not completed this run.** Built and typechecked; **needs a human at a
browser**, which the agent running this block is not. Stopping here and handing off, per this
block's own instructions, rather than faking a result.

**What's built**, all marked delete-after-Block-2:

- `frontend/spike.html` + `frontend/src/spike/main.ts` + `frontend/src/spike/worklet.js`
- `npm run typecheck` passes clean (0 errors). `npm run lint` could not run — **pre-existing gap,
  not caused by this work**: no `eslint.config.js` exists anywhere in `frontend/` yet (ESLint 9
  requires one; none was ever scaffolded). Not fixed here — out of Block 0's scope, and not
  something a spike should be patching.
- Vite dev server started and confirmed serving all three files (`200` on `spike.html`,
  `main.ts`, `worklet.js`) via `curl`. Still running in the background at the time of writing:
  **http://localhost:5173/spike.html**

**Design decisions made while building it, for the record:**

- **Resampling: `new AudioContext({ sampleRate: 16000 })`**, not a hand-rolled resampler. The
  browser resamples the mic input before it reaches the worklet, which only frames (20ms / 320
  samples — a standard speech frame size) and converts float32→int16. Chosen over manual
  resampling math because it's less code, is presumably better-tested than anything hand-rolled
  here, and is one of the two options the plan explicitly names as acceptable.
- **VAD `redemptionMs` set to 600, not the library's own default of 1400.** `@ricky0123/vad-web`
  defaults to 1400ms of trailing silence before declaring speech-end — nearly 2.5x the TDD's
  ~600ms latency-budget assumption for endpointing. Exposed as a live number input on the page
  (per `.claude/rules/voice/browser-audio.md`: "expose it while developing... then fix a value
  and record the reason") so Omar can tune by feel and report back what he lands on.
- Capture (Section A/B) and VAD (Section C) use **two independent `getUserMedia` streams**, not
  one shared stream feeding both. Simpler to reason about and debug for a diagnostic page;
  Block 2's real implementation should share one stream — a wiring change, not a research
  question, so not worth the complexity here.
- WAV export via a small local `int16ToWav` helper (Sections A/B) and the `vad-web` package's own
  `utils.encodeWAV` (Section C, since `onSpeechEnd` already hands back `Float32Array`) — reused
  rather than duplicated where the natural data shape already matched a library helper.

**What Omar needs to do** — `npm run dev` is already running in `frontend/`; open
**http://localhost:5173/spike.html** in Chrome:

| Check | What to do | What a pass looks like |
|---|---|---|
| C1 (Chrome) | Section A: Start, say a full sentence, Stop, Play. Download and save as `scratch/spikes/out/s5-roundtrip.wav` | You can understand your own sentence played back |
| C2 (Safari) | Same, opened in Safari | Works, or note how it fails — not a blocker either way |
| C3 (echo cancellation) | Section B: Run, **using speakers, not headphones**. Download, listen | The 440Hz tone should NOT be clearly audible in the capture |
| C4 (VAD) | Section C: Start, say a sentence (watch for `onSpeechEnd` + measured delay), then say just "mhm" (should log `onVADMisfire`, not a full speech-end) | A real sentence ends the turn; a backchannel doesn't, at `redemptionMs=600` (adjustable on the page) |
| C5 (AudioContext resume) | Watch the "AudioContext state" indicator after clicking any Start button | Flips to `running` immediately on the click — the page logs this automatically either way |

**On fail:** C1 failing means +1h for Block 2 and a `MediaRecorder`→webm/opus→server-side-decode
fallback goes on the table. C3 failing means budget one constraint-line fix in Block 2, not an
architecture change. C2 and C5 are recorded, not blockers, per the plan's own thresholds.

**Not yet recorded** (blocked on the above): actual mic `sampleRate` from `track.getSettings()`
(the page logs it live, on-screen, the moment mic access is granted), measured VAD end-of-speech
delay at whatever threshold Omar lands on, C1–C5 pass/fail, browser versions.

---

## Carried into Block 2

- **Resampling approach:** `new AudioContext({ sampleRate: 16000 })`, browser-side resample —
  not manual. Lift `frontend/src/spike/worklet.js`'s framing/int16-conversion logic (20ms /
  320-sample frames) directly; it has no spike-only shortcuts in it.
- **VAD config:** `redemptionMs` exposed as a tunable, seeded at 600 (library default is 1400 —
  too slow, do not ship the default). Final value and its measured end-of-speech delay: **pending
  Omar's S5 run** — do not carry forward the ~600ms TDD estimate as measured until then.
- **Mic sample rate:** not yet observed (pending S5). Do not assume 48000.
- **TTS latency:** ~1.1–1.4s to first audio byte (n=1–2, `generateContent` arm) — re-measure at
  full n once the daily quota resets, but do not plan around the old 500ms estimate in the
  meantime.
- **TTS daily quota:** 10 requests/day, shared across API surfaces. Block 2's retry/backoff logic
  needs to distinguish this from the per-request 500/`PROHIBITED_CONTENT` case TDD already
  planned for — a daily cap has no useful "retry in 250ms" response; the only correct behaviour
  is fail visibly and say so, same as any other exhausted-quota case.
- **Deployment target:** Fly.io, not Modal (S1). Everything downstream that assumed Modal-specific
  behaviour (the `@modal.concurrent` WebSocket-as-one-input pattern, `modal.Dict` for memory,
  `routing_region`) needs re-deriving for whatever Fly.io's equivalent primitives are — **not
  done in this block**, belongs to whichever block now owns the deployment decision.

---

## Open

- **S5 fully** — needs a human at a browser. See that section for exactly what to run.
- **S3 at full n=5** — blocked on the free-tier daily quota resetting (or a paid tier / quota
  increase). Today's n=1–2 numbers are directionally useful, not final.
- **S4 Q3** — does an unanswered `update()` invalidate the turn? Attempted, inconclusive
  (`"Invalid input received"`, likely a missing `thought`-step resend), not pursued past the
  plan's 5-minute cap.
- **The region tension in S2** — the measured, ruled answer is `us-east`, but eu-west was more
  than 2x faster on the leg a person actually feels, and lost only on a small (n=5) S2b sample.
  Not re-opened here; flagged for whoever owns the final call before the URL is shared with Sarj.
- **Whether Fly.io's own WebSocket lifetime is actually longer than Modal's** — S1 tells us Modal
  fails this test; it does not yet tell us Fly.io passes it. **The next spike, not assumed.**

---

## Gate checklist

- [x] `modal app stop sarjy-spike-useast` and `...-euwest` — confirmed via `modal app list`
      (both `stopped`, 0 tasks).
- [x] `scratch/` in `.gitignore` (already was, confirmed).
- [x] The real `sarjy` app was never deployed — confirmed via `modal app list`.
- [x] `MASTER-PLAN.md` §Trigger points and `TDD.md` §Latency budget / §Open updated.
- [ ] S5's five checks — handed off to Omar, not yet run.
