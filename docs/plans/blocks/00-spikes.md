# Block 0 — Spikes

**Date:** 2026-09-19 · **Start:** Saturday ~17:15 · **Budget:** ~1.5 h wall clock
**Plan of record:** `docs/plans/MASTER-PLAN.md` §Block 0 · **Design:** `docs/plans/TDD.md`
**Output:** `docs/measurements/day1-spikes.md` — five answers. **No code is kept.**

---

## Summary — read this page

Five measurements, run mostly in parallel, that decide whether the architecture in the TDD
survives contact with the providers. Nothing downstream is safe until they answer.

| # | Spike | Question | Pass threshold | On fail |
|---|---|---|---|---|
| **S1** | Modal WebSocket | Does an **idle** connection survive 150 s? 600 s? | Arm 1 (true idle) alive at 610 s | Arm 2 (heartbeat) alive → keep Modal + heartbeat. **Both dead < 150 s → Fly.io tonight** |
| **S3** | TTS TTFB | Time to first **audio** byte, `generateContent` vs `interactions` | Median ≤ 800 ms | 0.8–2.0 s → re-derive budget. **> 2.0 s → drop the opener** |
| **S4** | Parallel FC | Does `gemini-3.5-flash-lite` emit **two** function calls in one response? | 3/3 runs | **Sequential flow, no opener.** Everything else stands |
| **S2** | Region A/B | `us-east` vs `eu-west`, **immutable once the URL is shared** | Winner by ≥ 100 ms combined | Tie or not run → ship `us-east` (the default), permanently |
| **S5** | Browser audio | Does capture → 16 kHz PCM16 → playback work on this machine? | Intelligible round trip in Chrome | Block 2 gets +1 h and a server-side-decode fallback |

**S1, S3 and S4 can invalidate the architecture. S2 and S5 cannot** — S2 is a one-way config
choice, S5 is de-risking the block that is already known to be hardest.

### Order, and why

```
17:15  P0  Omar's prerequisites (4 items, independent — a missing one stalls one spike, not all five)
17:25  S1  deploy two throwaway apps · start the 10-minute idle hold        ── unattended ──┐
17:35  S3  TTS A/B         (scripted, unattended batch, prints a table)                     │
17:55  S4  parallel FC     (scripted, unattended batch, prints a table)                     │  overlap
17:35  S5  browser audio   (hands-on — this is where Omar's attention goes)  ───────────────┤
18:10  S2  region pings, both regions, plus the in-container provider leg   ────────────────┘
18:20      write day1-spikes.md · apply the triggers · `modal app stop` the throwaways
18:35  done
```

S1 is first because it has the **longest unattended wall clock** (10.5 min of deliberate
waiting) and because it is the only spike whose failure changes the deployment target — every
other spike's work is wasted if we move to Fly.io. S2 is last of the deployed spikes because it
reuses S1's two deployments and needs no new infrastructure. S3 and S4 need only an API key, so
they are free to run underneath S1. S5 needs neither Modal nor a key, so it is the one thing
that can occupy Omar while the machines wait.

### Three things Omar must do before anything runs

1. Create `.env` from `.env.example`. **Block 0 only needs `GEMINI_API_KEY`.** (Groq, RapidAPI
   are Block 1+.) Agents never read or write `.env`.
2. `modal profile current` — confirm auth. `~/.modal.toml` exists, so this is probably already
   done; if it errors, `modal token new`.
3. `modal secret create sarjy-secrets --from-dotenv .env` — needed by S2's in-container probe,
   and by Block 1 an hour later regardless.
4. `cd frontend && npm install` — needed by S5, and by Block 1 regardless.

### The one blocking finding, before you start

🚨 **`routing_region` does not exist in Modal 1.4.2** — the installed client. Verified by
inspecting the package: `app.function()` accepts `region`, not `routing_region`. Uncommenting
line 59 of `backend/modal_app.py` today raises `TypeError`. See **S2 · Step 0**; resolve it in
the first five minutes or S2 does not run at all.

Also verified present in 1.4.2 and safe to use as scaffolded: `@modal.concurrent(max_inputs=,
target_inputs=)`, `scaledown_window=`, `min_containers=`, `max_containers=`, `timeout=`,
`secrets=`.

---

## Goal

**One sentence:** when this block is done, the five provider and platform facts that the whole
weekend's design rests on are written down as measured numbers with their conditions, and any
trigger they fire has already been pulled — instead of being discovered at 2 a.m. on Sunday.

---

## Prerequisites

Omar does these himself. They are independent: a missing one stalls one spike, not the block.

| # | Command | Unblocks | Note |
|---|---|---|---|
| P0.1 | Copy `.env.example` → `.env`, fill `GEMINI_API_KEY` | S3, S4 | Block 0 needs **only** this key. `GROQ_API_KEY`, `RAPIDAPI_KEY`, `RAPIDAPI_HOST`, `QUOTA_RESERVE`, `LOG_LEVEL` are Block 1+. **No agent reads or writes this file.** |
| P0.2 | `modal profile current` | S1, S2 | `~/.modal.toml` already exists. Falls back to `modal token new`. |
| P0.3 | `modal secret create sarjy-secrets --from-dotenv .env` | S2b | `--from-dotenv` means the key never passes through a shell history or an agent. Add `--force` to overwrite. |
| P0.4 | `cd /Users/omarsalama/Projects/Sarjy/frontend && npm install` | S5 | Also proves the frontend toolchain installs, which Block 1 needs. |
| P0.5 | Add `scratch/` to `.gitignore` | all | One line. Everything this block writes is throwaway and must not enter the repo. |

**Decision Omar must take at P0 (2 minutes, see S2 Step 0):** upgrade the Modal client to 1.5.5,
or ship on the default region. Do not defer it — it gates S2 and S2's window closes when the
deployment URL is shared.

---

## Scope in / scope out

### In

- Five measurements, each with a threshold fixed **before** it runs.
- Throwaway scripts under `scratch/spikes/`, and one throwaway page under `frontend/`.
- Two throwaway Modal apps, named so they can never be confused with the real one, stopped at
  the end of the block.
- One results document: `docs/measurements/day1-spikes.md`.
- Pulling any trigger the results fire — including telling Omar immediately if the opener dies.

### Out — this is what stops the block expanding

| Not in this block | Where it belongs |
|---|---|
| The real `sarjy` Modal app, `StaticFiles` mount, health route | **Block 1** |
| The WebSocket message protocol, `app/pipeline/protocol.py` | **Block 1** |
| Any STT call, any Groq call at all | **Block 2** |
| Provider adapters, `app/providers/*` | **Block 2** |
| `app/audio` capture/playback as production code | **Block 2** — S5 is a throwaway page, even though Block 2 will lift the resampler from it |
| Per-stage instrumentation, `app/measure.py`, `make measure` | **Block 3** |
| The `update()` opener wired into a turn; NDJSON; `arguments_delta` parsing | **Block 4** — S4 only observes whether the primitives exist |
| Travel Buddy, the quota ledger, the colour legend (~6 requests) | **Block 5** |
| The gate, `resolve`, `get_path`, any Pydantic segment model | **Block 6** |
| `modal.Dict` semantics, memory, identity | **Block 7** |
| Arabic, Orpheus, voice selection between Sulafat/Vindemiatrix/Rasalgethi | **Block 10** |
| Fixing anything a spike reveals as broken | The block that owns it. **Block 0 measures and records; it does not repair.** |

**If a spike passes, resist writing "just a little" of the real thing while the context is
warm.** Every minute here is a minute off Block 1, and Block 1 is the one that lands
requirement #4.

---

## Files

Everything below is deleted or ignored except the last row.

| File | Purpose |
|---|---|
| `scratch/spikes/ws_probe.py` | Throwaway Modal app: one `/ws` echo endpoint + one `/probe` HTTP route. Deployed twice, once per region. |
| `scratch/spikes/ws_hold.py` | Local client. Holds a socket idle and pokes it at fixed marks. Two arms (`idle` / `heartbeat`). |
| `scratch/spikes/ws_rtt.py` | Local client. n=20 send→recv round trips against a deployed region. |
| `scratch/spikes/tts_ab.py` | S3. Interleaved A/B, times to first **audio** byte and to complete audio. Prints a table. |
| `scratch/spikes/parallel_fc.py` | S4. Three runs, asserts two function calls in one response; times name-vs-arguments gap. Prints a table. |
| `frontend/spike.html` + `frontend/src/spike/main.ts` + `frontend/src/spike/worklet.js` | S5. Throwaway capture→resample→playback page, served by the existing vite dev server. **Delete after Block 2 lifts the resampler.** |
| `scratch/spikes/out/` | Raw output: JSON timing dumps, the S5 `.wav`, the S1 terminal logs. Evidence for the results file. |
| **`docs/measurements/day1-spikes.md`** | **The only kept artifact.** The gate. |

---

## S1 — Does an idle Modal WebSocket survive?

**Blast radius: total.** If this fails both arms, the deployment target changes and every other
spike's result is about a platform we are not using. It runs first for that reason and because
it is 10.5 minutes of deliberate waiting that everything else hides underneath.

### What is actually being asked

The TDD (§Deployment, *The timeout, honestly*) is careful and correct here: Modal documents a
**150 s HTTP request timeout** and says nothing about whether it survives a WebSocket upgrade.
`timeout=30*60` is an *inference* from two documented facts, not a documented guarantee. So:

1. Does a **truly idle** connection — no traffic in either direction — die at ~150 s?
2. If it does, does a **client heartbeat** rescue it?
3. Does it reach 600 s, which is the length of a realistic demo conversation?

### ⚠️ The trap that would make this spike lie

The `websockets` Python client sends protocol pings **every 20 s by default**
(`ping_interval=20`). That is traffic. Run arm 1 with `ping_interval=None` or the spike measures
a heartbeat while claiming to measure idleness.

### Method

Deploy `ws_probe.py` (see S2 for the two-region deploy — the same app serves both spikes).
Sketch, ~20 lines, for the implementer to fill in:

```python
# scratch/spikes/ws_probe.py  — SKETCH
import modal
image = modal.Image.debian_slim(python_version="3.12").pip_install("fastapi[standard]", "google-genai")
app = modal.App("sarjy-spike-useast", image=image)   # second deploy: -euwest

@app.function(timeout=30*60, min_containers=1, max_containers=1, scaledown_window=300,
              secrets=[modal.Secret.from_name("sarjy-secrets")])
@modal.concurrent(max_inputs=8, target_inputs=4)
@modal.asgi_app()
def web():
    import time
    from fastapi import FastAPI, WebSocket
    api = FastAPI()

    @api.websocket("/ws")
    async def ws(sock: WebSocket):            # async — a sync handler makes one
        await sock.accept()                   # cancellation kill the container
        t0 = time.monotonic()
        try:
            while True:
                m = await sock.receive_text()          # no server-side keepalive
                await sock.send_text(f"{m} t={time.monotonic()-t0:.1f}")
        except Exception as e:
            print(f"closed after {time.monotonic()-t0:.1f}s: {e!r}")

    @api.get("/probe")                        # used by S2b, not by S1
    async def probe() -> dict: ...
    return api
```

```python
# scratch/spikes/ws_hold.py  — SKETCH
# usage: python ws_hold.py wss://<host>/ws idle       (arm 1)
#        python ws_hold.py wss://<host>/ws heartbeat  (arm 2)
MARKS = (5, 160, 310, 610)     # 160 straddles the documented 150 s HTTP timeout
ping  = None if sys.argv[2] == "idle" else 20
# connect once with ping_interval=ping; sleep to each mark; send "poke"; await recv with a
# 10 s timeout; print "t=…s alive" or "t=…s DEAD <exc>" and exit. Append to scratch/spikes/out/.
```

### Commands

```bash
cd /Users/omarsalama/Projects/Sarjy
modal deploy scratch/spikes/ws_probe.py            # prints the URL

# two terminals, same deployment — max_containers=1 + @modal.concurrent means
# both connections land in ONE container, so the two arms cost 10.5 min, not 21
python scratch/spikes/ws_hold.py wss://<url>/ws idle      | tee scratch/spikes/out/s1-idle.log
python scratch/spikes/ws_hold.py wss://<url>/ws heartbeat | tee scratch/spikes/out/s1-hb.log
```

### Threshold — fixed before it runs

| Result | Verdict |
|---|---|
| Arm 1 alive at 610 s | **PASS.** The TDD's inference holds. No heartbeat needed; add one anyway in Block 1, it is five lines and preemption exists regardless. |
| Arm 1 dies 150–610 s, arm 2 alive at 610 s | **PASS with a condition.** Keep Modal. The client heartbeat becomes mandatory in Block 1, and the interval goes in the results file. |
| Arm 1 dies < 160 s, arm 2 alive at 610 s | **PASS with a condition, and the 150 s timeout is confirmed to survive the upgrade** — a genuinely useful finding for the writeup. Heartbeat mandatory. |
| **Both arms dead < 610 s** | **FAIL → Fly.io, tonight.** Tell Omar immediately; do not start Block 1 on Modal. |

> ⚠️ **This splits the master plan's trigger deliberately.** MASTER-PLAN says *"dies at 150 s →
> switch to Fly.io immediately."* That is too blunt: a five-line client heartbeat is a far
> cheaper fix than a platform migration, and the spike is designed to tell those two cases
> apart. Only **both arms failing** justifies the switch.

Regardless of the result, Block 1 ships client **reconnect-and-resume** — the TDD notes all
Modal Functions are preemptible and *"likelihood of interruption increases with Function run
duration."* A voice call is long-running by definition. S1 does not change that.

### Recorded

Arm, `ping_interval`, the last mark that answered, the first that did not, the close code and
exception text, container logs from `modal app logs sarjy-spike-useast`, and the Modal client
version.

---

## S3 — TTS time to first audio byte

**Blast radius: the latency budget and possibly the opener.** The TDD is explicit that every
figure in §Latency budget is a derived estimate and that this is the largest unknown: no
published Google figure, no third-party benchmark, and one forum reporter swinging between
sub-2 s and 10–20 s on this model within three weeks.

### The A/B, and why both arms must be identical

| Arm | Path | Bet |
|---|---|---|
| **A** | `generateContent`, streamed | The reportedly faster endpoint |
| **B** | `interactions`, streamed | The path the LLM adapter is already committed to |

**Identical method or the comparison is worthless:** same model
(`gemini-3.1-flash-tts-preview`), same voice (**Sulafat**), same two input strings, same
machine, same network, **interleaved A/B/A/B/A/B…** so that drift in Google's backend hits both
arms equally. n=5 per arm, 10 calls total, paced ~5 s apart — the free tier is reportedly ~15
RPM and unpublished.

Two input strings, because the turn makes two TTS requests of very different lengths:

- `OPENER` = `"Let me check that for you."`
- `ANSWER` = a ~45-word paragraph — roughly what a gated answer will be.

### 🚨 Measure to the first *audio* delta

The same trap as the LLM path, in a different costume. A stream's first chunk may carry
metadata, a role marker, or an empty inline-data envelope. **`t_first_audio` is the timestamp of
the first chunk whose inline audio payload has non-zero length.** Timing to the first SSE event
records a fiction.

Record **two** numbers per call, not one:

- `t_first_audio` — matters if the opener streams into the playback queue.
- `t_complete` — matters if the opener is played as one buffered clip, which is the simpler
  Block 2 implementation and the one that avoids a mid-clip seam.

Whichever the implementation turns out to be, the number that governs perceived latency is in
the table. Guessing now which one matters would be the mistake.

### Method

```python
# scratch/spikes/tts_ab.py — SKETCH
# The exact SDK call shape for each arm comes from the google-genai docs — CHECK IT, do not
# guess. What is specified here is the harness, which is the part that must be identical.
for i in range(5):
    for arm in ("generateContent", "interactions"):
        for label, text in (("OPENER", OPENER), ("ANSWER", ANSWER)):
            t0 = time.perf_counter()
            first_audio = None; total_bytes = 0
            for chunk in <arm's streaming call>(model=TTS_MODEL, voice="Sulafat", text=text):
                audio = <extract inline audio bytes from chunk>     # arm-specific
                if audio and first_audio is None:
                    first_audio = time.perf_counter() - t0          # <- the number
                total_bytes += len(audio or b"")
            row(arm, label, i, first_audio, time.perf_counter()-t0, total_bytes, err=None)
            time.sleep(5)
# print median + p95 per (arm, label); dump every row to scratch/spikes/out/s3.json
```

Also write **one** clip per arm to `scratch/spikes/out/` and listen to both. A fast arm that
sounds wrong is not a win, and the TDD warns the model *"may not always strictly match the
selected speaker."*

### Threshold — fixed before it runs

**Which arm wins:** the arm faster by ≥ 150 ms on median `t_first_audio` for `OPENER`. Inside
150 ms, take **`generateContent`** — the TDD's own research found it recommended *"for stable
production deployments"*, and the simpler path is the one Omar defends more easily.

**Whether the design survives**, on the winning arm's median `t_first_audio` for `OPENER`:

| Median | Verdict |
|---|---|
| ≤ 800 ms | **PASS.** §Latency budget's 500 ms estimate is optimistic but the ~1.8 s first-audio-out target holds. |
| 0.8 – 2.0 s | **PASS with a rewrite.** The opener survives — it is still faster than waiting for the lookup — but re-derive §Latency budget with the measured figure and state the new first-audio-out target in the writeup. |
| **> 2.0 s** | **FAIL → drop the opener.** MASTER-PLAN's trigger. Re-derive the budget, and **tell Omar the same hour**: the opener is the TDD's "one trick" and the demo narrative changes with it. Block 4 shrinks; the latency story becomes "here is where the time goes and why we could not hide it," which is still a defensible answer. |

**Also recorded, free:** how many of the 10 calls returned a `500` or `PROHIBITED_CONTENT`. The
TDD cites Google's own docs saying the model *"occasionally returns text tokens instead of audio
tokens"*. This is the first real data point on that rate and it sets Block 2's retry budget —
which must be **one retry, ~250 ms, then fail visibly**, never the SDK's default of four
retries backing off to 60 s.

### Recorded

Per arm and per input string: median and p95 `t_first_audio`, median `t_complete`, total audio
bytes, error count and error kinds, model id, voice, date, network, n. **A latency figure
without its configuration is not a measurement.**

> **Do not harmonise this with the LLM adapter.** TDD §Open records *"Decision: Interactions,
> pinned `Api-Revision: 2026-05-20`"* for the LLM. If S3 picks `generateContent` for TTS, those
> are two different calls and they may legitimately differ. Both sit behind our own interface.

---

## S4 — Parallel function calling on `gemini-3.5-flash-lite`

**Blast radius: the opener, and with it the TDD's headline argument.** The TDD flags this
explicitly: parallel function calling is *"documented generically and demonstrated only on
`gemini-3.8-flash`"*. The entire "Sarjy speaks before the lookup returns" design rests on this
model doing it.

### Three questions, one script

| # | Question | Why it matters |
|---|---|---|
| **Q1** | Does one response contain **two** function calls — `update` **and** `get_visa_requirements`? | If not, there is no opener. |
| **Q2** | Does the tool call's **name and id arrive before its arguments finish generating**? | This is what lets the HTTP lookup fire mid-stream. Without it the opener still hides call 2, but not the vendor round trip. |
| **Q3** *(free, if it falls out)* | Does the turn survive if `update()` gets no `function_result`? | TDD §Open. Costs one extra call and unblocks Block 4. |

### n=3, not n=1

Parallel function calling is a **model behaviour, not an API guarantee**. One sample cannot tell
"supported" from "happened to this time". Three runs, same prompt:

- 3/3 → **yes**, build the opener.
- 2/3 → **supported but unreliable.** Build the opener with a fallback path for the turns where
  only one call arrives — and say the rate out loud in the writeup.
- 0–1/3 → **no.**

### Method

```python
# scratch/spikes/parallel_fc.py — SKETCH
# Pin explicitly on EVERY call — thinking_level is interaction-scoped and is NOT carried by
# previous_interaction_id, and the docs say "minimal does not guarantee that thinking is off".
CONFIG = dict(thinking_level="minimal", store=False, tools=[UPDATE_TOOL, VISA_TOOL],
              system_instruction=SYS)   # SYS mandates calling update() alongside any lookup
PROMPT = "Do I need a visa for Japan on an Egyptian passport?"

for run in range(3):
    t0 = time.perf_counter(); seen = {}      # name -> (t_name, t_args_complete)
    for ev in stream(model="gemini-3.5-flash-lite", contents=PROMPT, **CONFIG):
        # record the delta type verbatim for EVERY event — see the note below
        log(ev.type, time.perf_counter() - t0)
        ...  # capture: t at which each call's name+id is known; t at which its arguments close
    row(run, names=list(seen), gap_ms=seen["get_visa_requirements"].args - seen[...].name)
```

🪤 **Log every delta type verbatim and keep the dump.** TDD §Provider traps: Google's own docs
contradict each other — the function-calling page samples `delta.type == "arguments"` /
`partial_arguments`, while the streaming page and the API reference say **`arguments_delta`**.
The wrong one gives a loop that silently matches nothing: no error, no output, no clue.
**Observing the real field name here saves an hour in Block 4 and costs nothing.** Record it.

### Threshold — fixed before it runs

| Result | Verdict |
|---|---|
| **Q1 3/3** and **Q2 gap ≥ 150 ms** | **PASS.** Build the opener as designed. The gap is the headroom the architecture spends — record the median. |
| **Q1 3/3**, **Q2 gap < 150 ms** | **PARTIAL.** Keep the two-call turn; stop claiming the lookup fires mid-stream. The opener still hides the whole of call 2, which is most of the benefit. Adjust §Latency budget's "hidden" column, do not panic. |
| **Q1 2/3** | **CONDITIONAL.** Opener with a single-call fallback branch. Report the rate. |
| **Q1 0–1/3** | **FAIL → sequential flow, no opener.** MASTER-PLAN's trigger. Tool call first, then answer. Slower and visibly so, and it still satisfies every numbered requirement. Block 4 shrinks; say so in the writeup. |

Q3 has no threshold — it is either answered or recorded as still open. Do not spend more than
five minutes on it.

### Recorded

Runs, calls seen per run, median name→arguments gap in ms, **the observed streaming delta field
name**, whether an unanswered `update()` invalidates the turn, model id, `thinking_level`, date.

---

## S2 — Region A/B: `us-east` vs `eu-west`

**Blast radius: one configuration value, permanently.** The lowest of the five — but the window
is narrow, so it runs today rather than never.

### 🚨 Step 0, before anything else: `routing_region` does not exist in Modal 1.4.2

Verified by inspecting the installed package (`modal 1.4.2`, PyPI latest is `1.5.5`):

```
app.function() accepts:  timeout ✅  min_containers ✅  max_containers ✅
                         scaledown_window ✅  secrets ✅  region ✅  experimental_options ✅
                         routing_region ❌  <-- not a parameter
@modal.concurrent(max_inputs=…, target_inputs=…)  ✅  exists, exactly as scaffolded
```

`backend/modal_app.py` line 59 carries `routing_region` as a commented-out kwarg. **Uncommenting
it on the installed client raises `TypeError`.** `region=` exists but is a different thing —
it constrains *where the container runs*, not *where the request enters Modal's network* — and
the TDD's immutability claim is about `routing_region`.

Pick one, in under five minutes:

| Option | Command | Consequence |
|---|---|---|
| **(a) Recommended — upgrade the client** | `python3 -m pip install -U modal` → 1.5.5, then verify | The client then matches the docs Omar will read all weekend. Upgrading now, before the first real deploy, is safer than upgrading Sunday night. |
| (b) Stay on 1.4.2, use `region=` | — | Measures a different thing. Do not label the result "routing region". |
| (c) Skip S2 | — | **This is a decision to ship on `us-east` forever**, not a deferral. Legitimate; record it as such. |

Verification after an upgrade — one line, run it, do not assume:

```bash
python3 -c "import inspect, modal, modal.app as A; s=inspect.signature(A._App.function).parameters; \
print({k: k in s for k in ['routing_region','scaledown_window','min_containers','timeout']}); \
print(inspect.signature(modal.concurrent))"
```

If the upgrade breaks `@modal.concurrent` or `scaledown_window`, **roll back to 1.4.2 and take
option (c)**. Block 1 matters more than this A/B.

### The correction to the TDD's design

⚠️ **A WebSocket round trip from Omar's machine is one of about six network legs in a turn.**
The others are Modal → Groq (STT), Modal → Gemini (LLM ×2), Modal → Gemini (TTS ×2). Moving the
app to `eu-west` shortens the browser↔app legs and may *lengthen* the four-to-five
app↔provider legs. Measuring only the first leg would produce a number that argues for the
wrong choice with apparent rigour.

So S2 measures two legs and combines them.

| | What | n |
|---|---|---|
| **S2a** | Browser↔app: WebSocket send→recv round trip, from Omar's machine to each region | 20 |
| **S2b** | App↔provider: one small Gemini `generateContent` text call timed **from inside the container**, via `/probe` | 5 |

**Decision rule, fixed before it runs:** choose the region minimising
`median(S2a) + 4 × median(S2b)`. The weight of 4 is the approximate number of provider round
trips on a turn's critical path — write the weight and its justification into the results file
so the arithmetic is auditable. **If the two regions land within 100 ms of each other on that
combined figure, take `us-east`** — the default, no client upgrade required, fewer moving parts.

⚠️ **The measurement is from Omar's location, not the reviewer's.** Sarj is Saudi, so the likely
reviewer is in the Gulf, and the TDD confirms **there is no Middle East routing region**.
Geography already favours `eu-west` for a Gulf reviewer; this measurement is a sanity check on
that prior, not a discovery. Say so in the results file rather than implying the number is the
reviewer's experience.

### Commands

```bash
# same throwaway app source, two names, two regions — NEVER the real "sarjy" app
modal deploy scratch/spikes/ws_probe.py            # app name: sarjy-spike-useast
#   edit app name -> sarjy-spike-euwest, add the region kwarg, redeploy
modal deploy scratch/spikes/ws_probe.py

python scratch/spikes/ws_rtt.py wss://<useast>/ws  | tee scratch/spikes/out/s2a-useast.log
python scratch/spikes/ws_rtt.py wss://<euwest>/ws  | tee scratch/spikes/out/s2a-euwest.log
for i in 1 2 3 4 5; do curl -s https://<useast>/probe; done
for i in 1 2 3 4 5; do curl -s https://<euwest>/probe; done
```

### 🚨 Throwaway names, and the real deadline

**These are `sarjy-spike-useast` and `sarjy-spike-euwest`, never `sarjy`.** Block 1 deploys the
real app and its Function's region is fixed from that point — changing it later requires a **new
Function**, which means **a new URL**.

> **The true deadline is not "before the first deploy" — it is "before the URL is shared with
> Sarj."** A new Function is cheap until the URL is committed to. This is slightly more generous
> than TDD §Deployment implies, and it is the accurate statement.

Stop both throwaway apps at the end of the block:

```bash
modal app stop sarjy-spike-useast && modal app stop sarjy-spike-euwest && modal app list
```

### Recorded

Per region: S2a median and p95, S2b median, the combined figure and the weight used, the
`modal` client version, the parameter actually used (`routing_region` / `region` / default),
Omar's location and network, the date, and **the chosen region with one sentence of reasoning**.

---

## S5 — Browser audio: capture → 16 kHz PCM16 → playback

**Not a yes/no.** Block 2 is the riskiest block in the project and is pure engineering with no
model cleverness — every bug in it is fixable and none are mysterious, which is exactly why
finding them tonight costs an hour and finding them tomorrow costs a day. This spike's job is to
produce **numbers and a resampler that Block 2 lifts unchanged.**

### Where it runs

Inside the existing `frontend/` vite scaffold, as a throwaway second page —
`frontend/spike.html` + `frontend/src/spike/`. Reasons: `@ricky0123/vad-web` is already a
declared dependency, TypeScript is configured, and `npm run dev` exists. `http://localhost` is a
secure context, so `getUserMedia` works with no TLS (it would **not** on a LAN IP — do not test
from a phone).

Mark the files delete-after-Block-2. They are a spike that happens to live in the frontend tree,
not the beginning of Block 2.

### The loop

1. `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })`
2. **Log `track.getSettings().sampleRate` and record it.** Do not assume 48000 — the rule file
   names "assuming the sample rate" as an anti-pattern for a reason.
3. `AudioWorklet` (never `ScriptProcessor`) — accumulate 128-frame render quanta to a chosen
   frame size, downsample to 16 kHz, float32 → int16, `port.postMessage` to the main thread.
4. Main thread buffers ~3 s, then schedules it back through an `AudioContext` with explicit
   `AudioBufferSourceNode` timing. **Never an `<audio>` element.**
5. Say a sentence. Hear it back. Save the PCM as a `.wav` in `scratch/spikes/out/`.

### Five checks, each with a threshold

| # | Check | Pass | On fail |
|---|---|---|---|
| **C1** | Round trip is **intelligible** in **Chrome** | A listener can transcribe the sentence from the saved `.wav` | **Block 2 gets +1 h**, and the fallback goes on the table: `MediaRecorder` → webm/opus → server-side decode, moving the 16 kHz conversion off the browser. Tell Omar. |
| **C2** | Same in **Safari** | Works | **Not a blocker.** Record it. The reviewer's browser is unknown, so the consequence is either a detect-and-warn in Block 8 or a line in the submission note. Safari's autoplay and mic behaviour break voice apps specifically. |
| **C3** | Echo cancellation is genuinely on | With loopback playing **through speakers, not headphones**, the captured signal does not contain the playback | The assistant will interrupt itself in Block 2 — a bug that looks architectural and is one constraint line. Record which constraint failed. |
| **C4** | VAD fires correctly | `@ricky0123/vad-web` emits speech-start and speech-end on a sentence, and **a backchannel ("mhm") does not end the turn** at the chosen threshold | Record the threshold that does work. This is a **product decision, not a constant** — whatever value is chosen, the reason is written down. |
| **C5** | `AudioContext` resumes after a user gesture | First click resumes; playback then works | Trivial to fix, classic silent failure. Record it so Block 2 does not rediscover it. |

### The number that matters most

**C4's measured end-of-speech delay replaces the ~600 ms estimate in TDD §Latency budget** — the
single largest term in the whole chain, larger than any provider call. It is also the one term
that is entirely ours to choose. Measure it, do not carry the estimate forward.

### Recorded — this is the transfer into Block 2

Actual mic sample rate · chosen frame size **and the reason** · measured capture→playback round
trip · measured VAD end-of-speech delay at the chosen threshold, and the threshold · whether
resampling was manual or via `new AudioContext({ sampleRate: 16000 })` · C1–C5 pass/fail per
browser · browser versions and OS.

---

## Gate

**The block is done when `docs/measurements/day1-spikes.md` exists and contains all five
answers.** Concretely, a complete file has:

1. **A header** with date, machine, OS, network, Modal client version, and Omar's location.
2. **One section per spike**, each containing:
   - the question, in one sentence;
   - the threshold **as it was written in this plan, before the run**;
   - the measured numbers with their `n`, median and p95 where there is more than one sample;
   - pass / fail / conditional, against that threshold;
   - the consequence, named — and if a trigger fired, what was actually done about it.
3. **A "triggers fired" section** at the top, even if it says *none*. If S1 failed both arms, or
   S3 exceeded 2.0 s, or S4 came back 0–1/3, the entry says what changed and whether Omar was
   told.
4. **A "carried into Block 2" section** — S5's numbers, in the form Block 2 needs them: sample
   rate, frame size, VAD threshold and delay, resampling approach.
5. **An "open" section** — anything that could not be answered, stated as an open question
   rather than quietly assumed. Q3 and any region caveat belong here.
6. **A provenance line per number:** model id, endpoint, date, conditions. A latency figure
   without its configuration is not a measurement.

**Also required to close the block:**

- `modal app stop sarjy-spike-useast` and `…-euwest`, confirmed with `modal app list`.
- `scratch/` in `.gitignore`.
- The real `sarjy` app has **not** been deployed — that is Block 1.
- `docs/plans/MASTER-PLAN.md` §Trigger points and `docs/plans/TDD.md` §Latency budget /
  §Open updated with any measured figure that replaces an estimate. **The estimates must not
  survive the measurements.**

Render and publish per the usual pipeline:

```bash
node ~/Projects/spec-html.mjs docs/measurements/day1-spikes.md
```

---

## If the clock runs out — de-scope in this order

The 1.5 h has roughly 10 minutes of slack and the first thing that goes wrong eats it.

| Order | Cut | What is actually lost |
|---|---|---|
| **1st** | **S2 entirely** | We ship on `us-east`. Say it as a decision, not a deferral. A marginal latency optimisation, on a leg that is one of six. |
| 2nd | **S5 · C2** (Safari) | A demo risk we then carry knowingly. Chrome-only is a defensible submission note. |
| 3rd | **S3 arm B** (`interactions`) | Take `generateContent`. We lose the comparison, keep the absolute number — and the absolute number is what fires the trigger. |
| 4th | **S4 · Q3** | Stays an open question. It costs Block 4 maybe twenty minutes to discover. |

**S1, S3 arm A, and S4 Q1 are never cut.** They are the three that can invalidate the
architecture, and discovering any of them on Sunday costs more than the whole of Saturday.

---

## Known conflicts with the design documents

Recorded here so the implementer does not silently plan around them.

| # | Where | Issue | Handled by |
|---|---|---|---|
| 1 | `backend/modal_app.py:59`, TDD §Deployment | `routing_region` is **not a parameter in Modal 1.4.2**, the installed client. `region` is, and means something else. | S2 Step 0 |
| 2 | MASTER-PLAN §Trigger points | *"Dies at 150 s → Fly.io immediately"* skips the cheap fix. A client heartbeat is five lines. | S1's two arms |
| 3 | TDD §Deployment | Region A/B as specified measures browser↔app only — one of ~six legs, and the one that moves in the *opposite* direction to the other five. | S2a + S2b combined rule |
| 4 | TDD §Deployment | *"Cannot be changed after the first deploy"* — true of the Function, but a new Function is cheap. The real deadline is **before the URL is shared.** | S2, noted |
| 5 | TDD §Open vs S3 | *"Decision: Interactions"* is about the **LLM**. If S3 picks `generateContent` for **TTS**, those are different calls and may differ. | S3, noted |
| 6 | `tdd-review.md` §5 arm A | *"one call per segment"* is stale — §Latency budget already settled on **two TTS requests per turn**. The arms are now streamed-vs-streamed on opener-length and answer-length strings. | S3's two input strings |
| 7 | MASTER-PLAN §Block 0 | ~1.5 h is achievable at ~80 minutes **only** because S1, S3 and S4 are unattended batch runs. Written as five sequential spikes it is closer to 3 h. | The schedule, and the de-scope order |
