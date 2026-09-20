# Block 1 — Skeleton that deploys

**Date:** 2026-09-19 · **Budget:** ~3.5 h (the master plan says 2 h — see §The estimate changed)
**Plan of record:** `docs/plans/MASTER-PLAN.md` §Block 1 · **Design:** `docs/plans/TDD.md` §Deployment, §Architecture
**Depends on:** Block 0 (`docs/measurements/day1-spikes.md`, especially §S1 and the decision under it)
**Lands:** requirement **#4 — a deployed URL a stranger can open.** The one deliverable that scores zero if missing.

---

## Summary — read this page

Block 1 builds the pipe, not what flows through it. A FastAPI **async** WebSocket handler, the
message protocol every later block extends, a React shell that connects and shows its state, the
`StaticFiles` mount that serves that shell from the same origin, and — new since the master plan
was written — **transparent reconnect-and-resume**, because Block 0 measured Modal killing a
WebSocket somewhere inside the first 160 seconds.

**Four things decide whether this block succeeds:**

| # | The thing | Why it decides the block |
|---|---|---|
| 1 | **A turn never spans a connection** | The whole reconnect design collapses to "re-present an id" if this holds, and grows mid-turn resume state if it doesn't. It is an invariant, enforced by the client refusing to start a turn it cannot finish. |
| 2 | **A connection is not a session** | Session identity is server-minted, opaque, and survives the socket. Block 7 hangs memory on exactly this record. |
| 3 | **The server learns about disconnects up to ~120 s late** | Measured in S1. Cleanup driven by the socket closing is therefore wrong, and a late `finally` from a dead connection can tear down the live one. A generation counter closes it. |
| 4 | **Deploy at the 45-minute mark, not at the end** | Requirement #4 is landed by a URL existing, not by the URL being good. Everything after the first deploy is improvement on something already banked. |

**The gate is observational, not a test suite:** open the public URL, the socket connects, a
message round-trips, and the page is still connected six minutes later with the same session id.

---

## What Block 0 changed, and what it costs

### 1. 🚨 Modal WebSockets die inside the first 160 seconds. We stay anyway.

Measured, both idle and with protocol-level pings: alive at t=5.2 s, dead by t=160 s, in both
arms. A control against an unrelated public WebSocket survived past 200 s from the same network,
so this is Modal (or something in front of it), not the network.

The pre-committed trigger said *migrate to Fly.io*. It was **consciously overridden** — reasoning
in `day1-spikes.md` §S1. The override is only correct if this block ships reconnect. If it
doesn't, the demo dies at the ~150-second mark, live, in front of the reviewer, and the override
becomes a mistake with a paper trail.

**Modal Functions are preemptible regardless**, so reconnect was owed either way. This finding
raises it from "handle preemption gracefully" to "rotate the socket on a timer."

⚠️ **The exact death time is unknown** — sampled only at 5 s and 160 s. Everything in §Rotation
depends on a number we do not have yet, so **§Step 6 measures it** against the real deployment
before the interval is fixed. Do not hard-code 75 s on the strength of a 150 s HTTP timeout we
have not observed directly.

### 2. Region: `us-east`

Won the combined figure by 354 ms. `routing_region` **exists in the installed client** — verified
locally: `modal 1.5.5`, `App.function(..., routing_region=...)` present in the signature.

🚨 **It is fixed per Function once deployed.** A change means a new Function and a **new URL**.
That is free until the URL is shared with Sarj, and expensive after. Set it on the first deploy.

🪤 `backend/modal_app.py` line 64 currently carries a commented `routing_region="eu-west"`. That
is the **wrong region** and the wrong client-version note beside it. Uncommenting it as-is ships
the loser of the A/B. Fix the line, don't just uncomment it.

### 3. `@modal.concurrent` is mandatory, and the handler must be `async`

Already scaffolded. One WebSocket is one input; without `@modal.concurrent`, every concurrent
connection gets its own container and `min_containers=1` does not prevent it. With input
concurrency, **a sync handler dies entirely when one input is cancelled** — and a closed browser
tab is a cancellation. One reviewer closing a tab would kill everyone else's session, silently.

`async def` is not a style preference here. It is the difference between a demo and an outage.

---

## The estimate changed

| | Hours |
|---|---|
| Master plan, Block 1 | ~2.0 |
| Reconnect, rotation, session registry, the late-`finally` defence | +1.0 |
| Tooling debts this block inherits (no eslint config, no `tests/`, `modal` not a dependency) | +0.25 |
| The exact-death-time measurement (mostly unattended, overlapped) | +0.25 |
| **Honest estimate** | **~3.5** |

The master plan was already ~3 h over ~21 h available. This makes it ~4.5 h over. **Overflow cuts
#1 (Wikipedia imagery, 0.75 h) and #2 (UI polish beyond functional, 1.25 h) should be treated as
already taken**, not as decisions still pending. Say so to Omar at the start of the block, not at
the end.

**Cut line, pre-committed:** if rotation is not working at **3 h elapsed**, ship reactive-only
reconnect (§Rotation, reduced scope — roughly 15 minutes of the work) and move to Block 2. Block 2
is the requirement-#1 blocker and it is the longest block on the chain. A demo that reconnects
after a visible half-second stall beats a demo that never reached audio.

---

## Prerequisites — Omar does these himself

| # | Command / action | Blocks | Note |
|---|---|---|---|
| P1.1 | `modal secret list` — confirm `sarjy-secrets` exists | deploy | Created in Block 0 P0.3. `modal.Secret.from_name` fails **at deploy time** if it is missing. Block 1 needs no key *inside* it, but the Function declares it. |
| P1.2 | `modal profile current` | deploy | Should already be good from Block 0. |
| P1.3 | Confirm the deployed URL is **not yet shared with anyone** | region | The region is irreversible once the URL is committed to. |
| P1.4 | *(ahead of Block 2, not this block)* Deepgram account + API key | Block 2 | The TDD's stack line names `aura-2` for English TTS and **no key exists**. Getting one is lead time Omar owns, and Block 2 stalls without it. |

Agents never read or write `.env`. Nothing in Block 1 needs a provider key.

---

## The design

### Two state machines, deliberately separate

| Machine | Values | Owner | Visible as |
|---|---|---|---|
| **Connection** | `connecting · ready · rotating · reconnecting · offline · stale` | client | a small, quiet status line |
| **Conversation** | `idle · listening · thinking · speaking` | server, pushed as `state` | the main UI |

Conflating them is the classic mistake: a reconnect would then look like the assistant started
thinking, and a long "thinking" would look like a dropped connection. **In Block 1 the
conversation machine only ever holds `idle`** — it exists so Block 2 has somewhere to put
`listening`, and so the reserved space is real rather than promised.

### The protocol

Envelope key stays **`t`** (already the de facto contract in `backend/app/pipeline/protocol.py`).
Every message is JSON on the text channel; **binary frames are audio and are rejected in Block 1**
with `error{code:"unsupported"}`.

Every server message carries `seq` and `ts_ms`. `seq` is **monotonic per session, not per
connection** — it continues across a reconnect, which is the visible proof that the session
survived and is this block's thesis on screen. `ts_ms` is wall clock for display only; **Block 3's
latency measurement uses monotonic clocks and must not reuse this field.**

#### Client → server (Block 1 implements all three)

```jsonc
{"t":"hello","v":1,"session_id":null,          "client_ts_ms":1758300000000}
{"t":"ping","id":"c7","client_ts_ms":1758300001000}
{"t":"bye","reason":"rotate"}   // reason: "rotate" | "leave"
```

`hello` is the **first message on every connection, including reconnects.** `session_id` is
`null` on a cold start and the previously issued id on a reconnect.

#### Server → client (Block 1 implements all five)

```jsonc
{"t":"ready","v":1,"session_id":"…","resumed":true,"connection_n":3,
 "rotate_after_ms":75000,"hard_max_ms":110000,"server_started_at_ms":…,"seq":42,"ts_ms":…}
{"t":"state","value":"idle","seq":43,"ts_ms":…}
{"t":"pong","id":"c7","client_ts_ms":…,"seq":44,"ts_ms":…}
{"t":"error","code":"bad_message","message":"…","recoverable":true,"seq":45,"ts_ms":…}
{"t":"closing","reason":"rotate_ceiling","reconnect":true,"seq":46,"ts_ms":…}
```

`error.code` in Block 1 is a closed set: `bad_message · protocol_version · unsupported ·
internal`. `closing.reason`: `rotate_ceiling · shutdown · superseded · protocol_version`.

#### Reserved — named now, built later. **Do not build these payloads in Block 1.**

| `t` | Direction | Block | Shape sketch |
|---|---|---|---|
| `start` / `end` / `barge` | c→s | 2 | `{"t":"start","turn_id":"…"}` — client VAD drives all three |
| *(binary)* | both | 2 | 16 kHz PCM16 in, 24 kHz PCM out |
| `transcript` | s→c | 2 | `{"text":…,"final":bool,"turn_id":…}` |
| `state` values `listening/thinking/speaking` | s→c | 2 | already in the union, unused |
| `timings` | s→c | 3 | `{"turn_id":…,"stages":{"endpoint_ms":…,"stt_ms":…,"llm_ttft_ms":…,"tool_ms":…,"tts_ttfb_ms":…,"first_audio_ms":…}}` |
| `segments` | s→c | 4/6 | `[{"kind":"sourced\|judgement","text":…,"citation":{…}\|null,"layer":…}]` |
| `quota` | s→c | 5 | `{"remaining":int,"reserve":int}` |
| `memory` | s→c | 7 | the "what Sarjy remembers" panel |

The envelope accommodates every one of these without a redesign: a new `t`, a new model in the
union, a new branch in the dispatcher. **That is the whole point of spending time on this now.**

#### Validation, both ends

- **Server:** pydantic v2 discriminated union on `t`, `model_config = ConfigDict(extra="forbid")`,
  decoded through a single `TypeAdapter`. One boundary function, nothing else parses raw input.
  *(§Invariant 5 — the user's speech is untrusted; so is the user's JSON.)*
- **Client:** a hand-rolled `parseServerMessage(raw): ServerMessage | null` — a `switch` on `t`
  with explicit field checks. **No zod.** Twenty lines Omar can read out loud beats a dependency
  whose failure modes he'd have to explain.
- **Forward compatibility, in the direction that matters** (the server is newer than a cached
  browser bundle): an unknown `t` is logged once and ignored, never thrown; an unknown
  `error.code` renders `message` and respects `recoverable`. A *version* mismatch is the hard
  stop — see below.
- **Version handshake:** `hello.v` must equal the server's `PROTOCOL_VERSION`. Mismatch →
  `error{code:"protocol_version", recoverable:false}` then `closing{reconnect:false}`, and the
  client shows **"A new version is available — reload."** We will redeploy repeatedly this
  weekend with tabs left open; this turns a baffling failure into a legible one for five lines.
- **A malformed message does not close the socket.** `error{recoverable:true}` and carry on. One
  bad frame must not cost a conversation. The exception is a missing or invalid `hello` as the
  first message → close.

### Session identity

```
Session = {session_id, created_at_ms, last_seen_ms, connection_n, generation, seq, live: WS|None}
```

- **Server-minted `uuid4`, opaque, high entropy.** The client never proposes an id. A guessable id
  would let one browser resume another's session — which is exactly the cross-session leakage
  Block 7's gate asserts against. One unguessable id is the whole defence; **no second resume
  token** — that is ceremony Omar would have to justify.
- Never log the full id. Log `session_id[:8]`. The UI may show the short form — it is the visible
  proof of continuity.
- **Registry is an in-process `dict` in Block 1.** `modal.Dict` arrives in Block 7 with memory.
  This is why `max_containers` drops to **1** (§Modal config): a reconnect that lands on a second
  container would find no session and silently start a new one.
- **TTL sweep, not socket-driven cleanup.** Records expire on `last_seen_ms` older than
  `SESSION_TTL = 15 min`, swept lazily on each `hello` (no background task — cheaper, and one
  fewer thing to explain). **This is the direct consequence of S1's ~120 s client/server
  disconnect gap: the socket closing is not a reliable signal, so it is not the signal.**

#### ⚠️ The late-`finally` bug, and the generation counter

S1 measured the server not noticing a dead client for **~281 s — about 120 s after the client gave
up.** By then the client has already reconnected, twice. The handler's `finally` block for the
*dead* connection then runs and tears down state belonging to the *live* one.

```
t=0     conn A  → session S, generation 1
t=75    client rotates → conn B → session S, generation 2
t=150   client rotates → conn C → session S, generation 3
t=195   conn A's finally FINALLY runs  ← must be a no-op, not a teardown
```

**Rule:** every connection captures its `generation` at `hello`. On disconnect, it clears
`session.live` **only if `session.generation == my_generation`.** Any write attempted from a
superseded generation is dropped. On a `hello` for a session that already has a live connection,
the server increments `generation`, sends `closing{reason:"superseded"}` on the old socket and
closes it.

Ten lines, one paragraph of explanation, and it is the difference between "reconnect works" and
"reconnect works until the ghost arrives."

### Reconnect and rotation

**Rotate proactively between turns. Never reactively, mid-utterance.** A socket that dies during
a turn loses the turn; a socket replaced between turns costs ~200 ms nobody perceives.

**The invariant that keeps this small:**

> **A turn never spans a connection.**

Because of it, "resume" carries identity and nothing else — no audio buffer replay, no mid-turn
tool state, in this block or any later one. It is enforced by two rules, not by hope:

1. **Rotate only when the conversation state is `idle`.** If the timer fires mid-turn, set
   `rotatePending` and rotate on the next `idle`.
2. **Refuse to start a turn that cannot finish.** The connection manager exposes
   `ensureFresh(): Promise<void>` — if `elapsed > rotateAfterMs − TURN_BUDGET_MS` it rotates
   first, then resolves. Block 2 awaits it before sending `start`. **Implement it in Block 1**
   (it is connection logic and it is testable); Block 2 is the first caller.
   `TURN_BUDGET_MS = 30_000` — a long utterance plus the full pipeline plus the answer audio.

**The rotation itself is an ordinary close.** Client sends `bye{reason:"rotate"}`, sets
`rotating = true`, calls `socket.close(1000)`. The `onclose` handler is the *only* reconnect path;
`rotating` decides whether it backs off and shows an error (no) or reconnects immediately (yes).
**One reconnect code path, one flag** — and because rotation exercises it every ~75 seconds, the
reconnect path is the best-tested code in the app by the time of the demo.

`bye` is not politeness — it is capacity. A server-side `await ws.close()` ends the Modal input
immediately; without it the zombie holds one of the container's concurrent input slots for ~2
minutes (§Modal config).

**Reactive path** (real drop, preemption, redeploy): attempt at 0 ms, then 250 ms → 500 ms → 1 s →
2 s → 4 s, capped at 5 s, ±20 % jitter, retrying indefinitely. After 5 consecutive failures the UI
stops implying progress and offers a manual **Retry**. **Never a spinner that can outlive its
operation** (`rules/voice/browser-audio.md`).

**Liveness:** `ping` every 15 s with a 3 s `pong` deadline; a missed deadline marks the connection
`stale` and reconnects immediately, rather than waiting for TCP to notice.
⚠️ **Write in the comment that this is detection, not a keepalive** — S1 measured a 20 s
protocol-level ping failing to save the connection. Someone will otherwise "optimise" it later
into a keepalive it never was.

🪤 **Backgrounded tabs throttle timers to ≥ 1 min in Chrome**, which can push a rotation past the
death window while Omar is showing the reviewer the code in another tab. On
`visibilitychange → visible`: if `elapsed > rotateAfterMs`, rotate immediately; otherwise send a
ping and wait for the pong before trusting the socket.

**Server ceiling.** The client owns rotation because the client owns the VAD and therefore knows
when a turn is really in flight. The server holds a backstop: a connection alive past
`hard_max_ms` (= `rotate_after_ms + 35 s`) gets `closing{reason:"rotate_ceiling", reconnect:true}`
and is closed, so a stale bundle or a buggy client cannot sit on a doomed socket forever.

#### Fixing the interval — a decision rule, not a guess

After §Step 6 measures the first-failure time **D** against the real deployment:

| Measured D | `rotate_after_ms` | Then |
|---|---|---|
| **D ≥ 140 s** (consistent with the documented 150 s HTTP cap) | **75 s** | Ship it. Write D into `day1-spikes.md` §S1 and quote it in the walkthrough. |
| **60 s ≤ D < 140 s** | `⌊D/2⌋` rounded down to 5 s | Ship it. Note the tighter margin in the PR doc. |
| **D < 60 s** | 20 s, **and escalate to Omar** | Rotation churn becomes user-visible at this rate. The Fly.io trigger un-overrides — this is a different finding from the one that was overridden, and it deserves a fresh decision, not an inherited one. |

The constant lives **once**, server-side, and reaches the client in `ready`. Retuning is a
one-line change, not a coordinated two-end change.

### Serving the frontend from the same ASGI app

`StaticFiles` on `frontend/dist`, same origin, **no CORS anywhere in this project.**

```python
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
```

🪤 **Four traps, all cheap, all demo-fatal if missed:**

1. **Mount last.** Starlette matches routes in registration order and a mount at `/` swallows
   everything beneath it. `/health` and `/ws` are registered first; the mount is the last line of
   `main.py`.
2. **A missing `dist/` raises at startup** and takes `/health` and `/ws` down with it. Guard:
   `if DIST.is_dir(): mount(...)` `else:` log a warning and register a plain-text route at `/`
   saying the frontend is not built. This also makes `make dev` usable without a build.
3. **`index.html` must not be cached.** Vite hashes asset filenames, so JS/CSS are safe forever,
   but a cached `index.html` after a redeploy serves an old bundle against a new protocol — mid
   demo. Subclass `StaticFiles` and set `Cache-Control: no-cache` on `text/html` responses. Four
   lines.
4. **`html=True` is not SPA fallback.** It serves `index.html` for directory paths. We have no
   client-side routing, so this is correct — just don't promise more than it does.

**`npm run build` must precede `modal deploy`, every time.** `add_local_dir` reads the local tree
at deploy time; a stale `dist/` deploys a stale UI with no error anywhere. Make it structural:
`make deploy` depends on the frontend build.

✅ **Verified locally, not assumed:** `npm run build` succeeds today (vite 6.4.3, 25 modules,
`dist/index.html` + one hashed chunk) and — importantly — **`spike.html` is not an entry point, so
the Block 0 spike files do not reach `dist/`.** See §Spike files.

### Modal function config

Verified against the **installed** client (1.5.5) by inspecting the signatures, not from memory:
`timeout`, `min_containers`, `max_containers`, `buffer_containers`, `scaledown_window`, `region`,
`routing_region`, `secrets` all present on `App.function`; `modal.concurrent(max_inputs=,
target_inputs=)` present; `Image.add_local_dir(local_path, remote_path, *, copy=False, ignore=[])`
present.

```python
@app.function(
    timeout=30 * 60,
    min_containers=1,
    max_containers=1,        # CHANGED from 2 — see below
    scaledown_window=300,
    routing_region="us-east",  # Block 0 S2. Fixed per Function once deployed: a change = a new URL.
    secrets=[modal.Secret.from_name("sarjy-secrets")],
)
@modal.concurrent(max_inputs=16, target_inputs=8)   # RAISED from 8/4 — see below
@modal.asgi_app()
```

| Change | Why |
|---|---|
| `max_containers=2 → 1` | The session registry is in-process until Block 7. With two containers a reconnect can land on the wrong one and silently lose the session — the exact failure this block exists to prevent. Revisit when the registry moves to `modal.Dict`. |
| `max_inputs=8 → 16` | Each client holds one live input plus up to two **zombie** inputs for ~2 minutes (S1's 120 s server-side gap × a 75 s rotation). Two viewers ≈ 6–9 slots against a cap of 8. Headroom is free for an I/O-bound handler; being at the cap is a silent hang. `bye` + a server-side close is the primary fix; this is the belt. |
| Image | `.add_local_dir(<repo>/frontend/dist, remote_path="/root/frontend/dist")`. Default `copy=False` mounts at container start rather than baking a layer — faster deploys, same result. The TDD says "image-baked"; either is fine, but **choose deliberately and note it**, because `copy=True` rebuilds the image on every UI change. |
| Paths | `pip_install_from_pyproject("pyproject.toml")` and the new `add_local_dir` both resolve relative to the **deploy cwd**. Derive both from `Path(__file__)` so `modal deploy backend/modal_app.py` from the repo root behaves identically to `make deploy` from `backend/`. |

**`backend/app/main.py` must not import `app.config`, `groq`, or `google-genai`.** Block 1 needs
no provider key and no provider SDK; keeping them out means the deploy cannot be broken by a
missing key or a provider SDK change, and the container starts faster. `load_settings()` raises on
a missing key — do not put that on the boot path this week.

---

## Build order

Deploy early. Everything after step 5 is improvement on a requirement already banked.

| # | Step | Files | Est |
|---|---|---|---|
| 1 | **Tooling debts** (§Inherited debts) | `frontend/eslint.config.js`, `backend/tests/`, `backend/pyproject.toml` | 15 m |
| 2 | **Protocol, server side** — models, union, `TypeAdapter`, `PROTOCOL_VERSION` | `backend/app/pipeline/protocol.py` | 25 m |
| 3 | **Session registry** — record, mint, resume, generation, TTL sweep | `backend/app/session.py`, tests | 25 m |
| 4 | **Handler + health + static mount** — failure paths first | `backend/app/main.py`, tests | 20 m |
| 5 | 🚩 **Deploy #1.** `npm run build && make deploy`. Open the URL. **Requirement #4 is banked here.** | `backend/modal_app.py`, `Makefile` | 15 m |
| 6 | **Start the lifetime probe in the background** (§Step 6) | `backend/scripts/ws_lifetime.py` | 10 m attended |
| 7 | **Protocol + connection manager, client side** | `frontend/src/protocol.ts`, `frontend/src/net/connection.ts` | 35 m |
| 8 | **React shell** — both state machines visible | `frontend/src/App.tsx`, `main.tsx` | 25 m |
| 9 | **Rebuild, redeploy, walk the gate** | — | 20 m |
| 10 | **Walkthrough with Omar · PR doc · commit drafts** | `docs/PRs/PR_SKELETON_DEPLOY.md` | 20 m |

≈ **3 h 30 m.** Steps 2–4 collapse to ~45 m if nothing surprises; steps 7–9 are where the time
actually goes, and they are where a demo breaks.

### Inherited debts (step 1) — none of these are optional, all are pre-existing

| Debt | Effect if skipped | Fix |
|---|---|---|
| **No `frontend/eslint.config.js`** (flagged in Block 0 S5, never fixed) | `npm run lint` fails → the `Stop` hook blocks every turn | Flat config, ESLint 9: `npm i -D @eslint/js typescript-eslint`, recommended rulesets, `ignores: ["dist/**", "src/spike/**"]` |
| **No `backend/tests/`** | `make lint` (`ruff check app tests`) errors on a missing path; `make test` exits non-zero with nothing collected | Create it in step 1, with the step-2/3/4 tests landing into it |
| **`modal` is not a dependency** but `make deploy` runs `uv run modal deploy` | Falls through to the global client, or fails outright | Add `modal>=1.5.5` to `[project.optional-dependencies].dev` |

---

## Step 6 — measure the exact death time

The rotation interval is a number Omar will be asked to defend. Right now it would be a guess
bracketed by (5 s, 160 s]. This makes it a measurement, for ~10 attended minutes.

`backend/scripts/ws_lifetime.py` — kept, not throwaway, because it is the evidence behind a
constant we ship:

1. Connect to the **deployed** `wss://…/ws` (the real app, not a throwaway probe).
2. `hello` → expect `ready`.
3. `ping` every **10 s**, 5 s pong deadline, printing `t=NNs ok`.
4. On the first failure, print **last-ok** and **first-fail** and exit.
5. `n = 2`, run concurrently in the background while steps 7–8 proceed. ~6 minutes wall clock.

**Output:** append to `docs/measurements/day1-spikes.md` §S1 as a dated *Block 1 addendum* — same
document, one source of truth for that fact. Then apply §Rotation's decision table.

⚠️ **If the two runs disagree by more than 30 s**, the cap is not a fixed timeout and the interval
needs a bigger safety margin (use the lower value, halved). Say so rather than averaging them.

---

## Failure paths — build these before the happy path

| Failure | Defined, visible behaviour |
|---|---|
| Rotation timer fires mid-turn | `rotatePending`; rotate on the next `idle`. Never mid-utterance |
| Turn would start with < 30 s of socket life | `ensureFresh()` rotates first, then the turn starts. Invisible to the user |
| Socket dies anyway (preemption, real drop) | Connection state → `reconnecting`, backoff, auto-resume. If a turn was in flight: mark it interrupted and say **"connection dropped — say that again."** Never a hang |
| Server has no record of the session (restart, TTL, redeploy) | `ready{resumed:false}` with a **new** id. UI states plainly that a new session started. Never pretend continuity we don't have |
| A superseded (zombie) connection's `finally` runs late | No-op via the generation counter. Never tears down the live connection |
| Two tabs, same session id | Second `hello` supersedes the first; the first gets `closing{reason:"superseded"}`. Defined, not a race |
| Protocol version mismatch (stale bundle after a redeploy) | `error{protocol_version}` → `closing{reconnect:false}` → **"A new version is available — reload."** |
| Malformed JSON / unknown `t` / extra field | `error{bad_message, recoverable:true}`, **socket stays open** |
| Binary frame arrives | `error{unsupported}`. Audio is Block 2 |
| First message is not a valid `hello` | Close. The handshake is the one place a bad message is fatal |
| `frontend/dist` missing at startup | App still boots; `/health` and `/ws` work; `/` explains the frontend is not built |
| Unhandled exception in the handler | Caught, `error{internal}` with **no traceback to the client**, logged server-side, socket closed cleanly |
| Tab backgrounded past the rotation window | On `visibilitychange`, rotate immediately or ping-verify before trusting the socket |
| Browser offline / network down | `offline` state, retry loop with jitter, manual **Retry** after 5 failures. No infinite spinner |
| **Mic permission** | **Not requested in Block 1.** The mic affordance renders visibly disabled with "voice arrives next" — a deliberate placeholder, not a dead control, and not a `getUserMedia` call |

---

## Tests (`make test`)

Unit, fast, no network. They are not the gate — the gate is observational — but they are what
stops Block 2 from breaking this silently.

**`backend/tests/test_protocol.py`**
- every Block 1 client message parses; field values survive the round trip
- unknown `t` → rejected; an extra field → rejected (`extra="forbid"` is doing work)
- `hello` with `v != PROTOCOL_VERSION` → rejected
- every server message serialises with exactly the documented keys

**`backend/tests/test_session.py`**
- cold `hello` mints an id; `resumed=False`; `connection_n == 1`
- `hello` with a known id → same record, `resumed=True`, `connection_n` and `seq` **continue**
- `hello` with an unknown id → new session, `resumed=False` (never trust a client-supplied id)
- generation increments per connection; **a stale-generation disconnect does not clear `live`** —
  the late-`finally` case, asserted directly
- TTL sweep drops a record past `SESSION_TTL` and keeps a fresh one

**`backend/tests/test_ws.py`** — `fastapi.testclient.TestClient.websocket_connect`
- hello → ready; ping → pong; malformed text → `error` **and the socket is still usable**
- binary frame → `error{unsupported}`
- reconnect with the returned id → `ready{resumed:true}` — the whole block's thesis, in a test

---

## The gate — observational, walked in order

Against the **public Modal URL**, not localhost. Record the result in the PR doc.

| # | Do | Pass |
|---|---|---|
| 1 | `curl https://…/health` | `{"status":"ok", …}` |
| 2 | Open the URL in Chrome | Page renders, **zero console errors**, connection state reaches `ready` |
| 3 | Click **Ping** | Round-trip ms displayed. **This is the master plan's "a message round-trips."** |
| 4 | Wait past one rotation, touching nothing | `connection #2`, **same session id**, `resumed: true`, no error state shown |
| 5 | Leave the tab open **6 minutes** | Still connected, session unchanged. This is the S1 finding being beaten |
| 6 | Switch tabs for 2 minutes, come back | Recovers within a second; no stale socket |
| 7 | Redeploy while the tab is open | `reconnecting` → recovers; new session **announced**, not hidden |
| 8 | DevTools → Network → Offline, then back | `offline` state, then automatic recovery |
| 9 | DevTools console: `ws.send("{")` on the live socket | `error` received, **socket still open** |
| 10 | Open the URL in a second browser | Both work. Same container, independent sessions |
| 11 | Open in Safari | Works, or the failure is written down (`browser-audio.md` — Safari breaks voice apps specifically, and finding out now is free) |

**Block 1 is done when 1–10 pass and the deployed URL is one Omar would send to a stranger.**

---

## Out of scope — say no to all of these

Audio capture · audio playback · AudioWorklet · VAD · **any** `getUserMedia` call · STT · LLM ·
TTS · Deepgram (no key exists) · the opener · the grounding gate · tools · the vendor client ·
memory · `modal.Dict` · identity / name / PIN · per-stage instrumentation (a `ts_ms` on each
message is the entire allowance) · UI polish beyond visible state · authentication · Arabic.

**Block 1 proves the pipe, not what flows through it.** If a step starts to need one of these,
that is the signal to stop and re-plan, not to press on.

---

## Spike files — keep until Block 2

`frontend/spike.html`, `frontend/src/spike/main.ts`, `frontend/src/spike/worklet.js` **stay.**

1. **S5 has not been run by a human.** C1–C5 are still owed (`day1-spikes.md` §S5). Deleting the
   page destroys the only artifact that can answer them.
2. **They do not ship.** Verified by running the build: `vite build` takes only `index.html` as an
   entry, and `dist/` contains `index.html` plus one hashed chunk. The spike costs the deployed
   bundle nothing.
3. **Block 2 lifts code from them** — the 20 ms / 320-sample framing and float32→int16 conversion
   in `worklet.js`, per Block 0's carry-forward.

**Condition:** add `src/spike/**` to the new eslint `ignores` (throwaway code should not gate the
lint that guards shipping code). **Delete both in Block 2, in the same commit that lands the real
capture path** — not later, or they become permanent.

---

## What Omar must do himself

1. **P1.1–P1.3** above, before step 5.
2. **Decide the region is final** — after deploy #1 the URL is real; sharing it freezes `us-east`.
   §S2's honest caveat still stands: eu-west was 2× faster on the leg a human feels and lost only
   on a small n=5 sample. This is the last cheap moment to override.
3. **Run S5's C1–C5** in Chrome and Safari — still outstanding from Block 0, and Block 2 is
   planned on its answers.
4. **Get a Deepgram key** before Block 2 (P1.4).
5. **Every commit.** Agents draft, Omar commits.

---

## Draft commits

Small and coherent, so the history reads like a build rather than a dump.

```
chore(frontend): add ESLint 9 flat config

npm run lint has never run — no config existed, so the Stop hook's lint
step was passing on nothing. Ignores dist/ and the Block 0 spike tree.

feat(protocol): typed WebSocket message union, validated at the boundary

Closed discriminated union on "t", extra="forbid", one TypeAdapter as the
only entry point for client input. Reserves transcript/segments/timings/
quota without building them. Mirrored by hand in TypeScript — no zod, so
the parse path stays readable.

feat(session): server-minted sessions that outlive their connection

A connection is not a session. Sessions are minted server-side (uuid4,
never client-proposed), resumed by id on reconnect, and expired by a TTL
sweep rather than by the socket closing — Block 0 measured the server
learning about a disconnect ~120s after the client did. A generation
counter makes a superseded connection's late teardown a no-op.

feat(ws): async conversation handler, health, and same-origin static UI

Handler is async: with input concurrency a sync function dies entirely
when one input is cancelled, and a closed tab is a cancellation. The
frontend is served by this same ASGI app, which removes CORS from the
project. Failure paths first: bad message, binary, missing dist, version
mismatch.

feat(client): reconnect-and-resume with proactive rotation

Modal kills a WebSocket inside the first 160s (measured, Block 0 S1). The
client rotates the socket between turns on a timer well under that, and
refuses to start a turn that could not finish before the next rotation —
so a turn never spans a connection and resume carries identity only.

chore(deploy): pin us-east, one container, build the UI before deploying

routing_region is fixed per Function once deployed. max_containers drops
to 1 while the session registry is in-process. make deploy now depends on
the frontend build, because add_local_dir reads the local tree.

docs(measure): exact WebSocket death time, n=2, against the deployment
```

Attribution line per the repo's convention, on each.

---

## Carried into Block 2

- `rotate_after_ms`, and the measured **D** it came from.
- `ensureFresh()` — await it before sending `start`. This is the contract that keeps a turn inside
  one connection.
- The conversation state machine exists and is wired; Block 2 fills in
  `listening/thinking/speaking`, and **state changes are sent before the work that follows them.**
- `start`/`end`/`barge` and binary audio are named in the protocol table; add the models and the
  dispatcher branches — no envelope change.
- Delete `spike.html` and `src/spike/` in the commit that lands real capture.
- The mic affordance is a deliberate disabled placeholder. Block 2 replaces it with a permission
  request **that has a reason attached** (`browser-audio.md`).

---

## Open / assumed, stated rather than buried

- **Assumed:** `StaticFiles` mounted last is reached after `/health` and `/ws` because Starlette
  matches routes in registration order. Confident, unverified by running — it will be obvious at
  step 5 if wrong, and the fix is line order.
- **Assumed:** a server-side `ws.close()` releases the Modal input immediately. Consistent with
  "one WebSocket is one input", **not directly measured**. If container input slots still fill up,
  that assumption is where to look.
- **Unknown until step 6:** the exact death time D. Everything about the rotation interval is
  provisional until then, and the §Rotation table is the instruction, not the number.
- **Deliberately deferred:** the session registry is in-process, so `max_containers=1`. If Block 7
  does not move it to `modal.Dict`, this app cannot scale past one container — which is fine for
  a demo and must be said out loud rather than discovered.
