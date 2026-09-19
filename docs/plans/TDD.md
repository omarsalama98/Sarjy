# Sarjy — Technical Design

**Date:** 2026-09-19 · **Owner:** Omar · Product requirements: `PRD.md`
**Supersedes** the 2026-09-18 draft. Decisions and evidence: `tdd-review.md`.

Everything here changes when the stack changes. If a fact would survive swapping every provider, it belongs in the PRD instead.

**Provider facts below were verified against official docs on 2026-09-19**, not recalled. Anything still unverified is marked ⚠️ and says so.

## Read this page, skip the rest

The rest of this document is reference. This page is the design.

### What it is

A voice travel assistant that **never states a travel fact it cannot source.** Cascaded pipeline, Python on Modal, hand-rolled. The grounding gate between the LLM and TTS is the deep dive and the heart of the codebase.

### The one idea

**The model never writes a fact. It names a field, and our code substitutes the value.**

```
model emits:  "You'll need {visa.type} for up to {visa.duration}."
gate renders: "You'll need an eVisa for up to 30 days."
```

If the model instead writes `"up to 90 days"` as text, the gate rejects the segment — because a `sourced` segment may not contain a digit outside a placeholder. That single rule is the difference between a guardrail and a citation chip, and it is the demo.

Two registers, and both directions are failures:

| Register | Example | Carries |
|---|---|---|
| `sourced` | entry requirements, durations, validity | a citation, a date, and which layer answered |
| `judgement` | "November is good for Kyoto" | nothing — it is Sarjy's own view, and says so |

*Judgement dressed as fact* is the harm. *A sourced fact hedged into opinion* is evasion. An assistant that refuses everything scores perfectly on hallucination and is worthless.

### The one trick

**Sarjy speaks before the lookup returns.** The model calls `update("Let me check that")` alongside the real tool call; we route the first straight to TTS and fire the second mid-stream. The vendor round trip and the entire second completion run **underneath audio that is already playing.**

```
first audio out       ~1.8 s      ← what the user experiences
everything else       ~1.6-2.5 s  ← hidden under the opener
```

The opener is safe by construction: nothing has been sourced when it is spoken, so it can only be `judgement`. **The latency optimisation and the guardrail turn out to be the same mechanism.**

### What the reviewer sees

Page loads calm and nearly empty. Mic is asked for with a reason. Sarjy speaks first — *"Hi, I'm Sarjy, what should I call you?"* — which creates the identity, proves the audio path in second one, and opens as a conversation rather than a form. A typed fallback stays visible, because names are where Whisper is weakest.

**Provenance is shown, not recited.** Every sourced segment carries its source, date and layer in the UI. Sarjy speaks it only when it changes the answer's weight — a CSV fallback, stale data, or a refusal. Reciting "according to Travel Buddy" every turn is tedious by turn four.

**No source, no claim.** Chitchat and opinion are `judgement` and get answered warmly. A factual question with no tool behind it — weather, flight status — gets refused and routed. *"I don't have a weather source, so I won't guess"* is the thesis working, not a gap in it.

### How it is proven

Three layers, and only two need a model:

| Layer | Runs | Catches |
|---|---|---|
| **Gate** | every turn, hot path | fabricated values, bad paths, bare digits |
| **Assertion tests** | every commit | regressions, wrong values, cross-session leakage |
| **LLM judge** | offline, before submission | register integrity, refusal correctness, anchoring |

The judge **never gates anything the user hears** — it only measures what determinism cannot see. And it is validated against hand labels, with the agreement rate reported beside every number it produces.

Substring assertions work here only *because* of the architecture: the model never writes the number, so `assert "30 days" in out` is stable even though the model is not. **The guardrail bought us regression tests for free.**

### The stack, in one line each

Groq `whisper-large-v3-turbo` (batch) · Gemini `gemini-3.5-flash-lite` (tools, `thinking_level: minimal`, `store=False`) · **Deepgram `aura-2` for English TTS, Groq `orpheus-arabic-saudi` for Arabic** · `modal.Dict` for memory · Travel Buddy for visas, **120 requests total, ever**.

### The three things that can still break it

1. **TTS time-to-first-byte is unknown.** No published figure anywhere; forum reports span sub-2 s to 10–20 s on this model. Day-1 spike — it can invalidate the latency budget.
2. **Does the 150 s HTTP timeout survive a WebSocket upgrade?** Not documented either way. Day-1 spike.
3. **Parallel function calling on `gemini-3.5-flash-lite` specifically** is documented only generically. Measure before committing to the opener.

### The plan

**Sat:** spikes → skeleton → adapters → **deploy** → instrumentation. Gate: *a URL that talks back.*
**Sun:** vendor client → normaliser → **the gate** → NDJSON → tests → memory → UI → fixtures. Gate: *all 7 requirements demonstrable.*
**Mon:** judge → Arabic → measure → fix. **16:00–19:00 reserved for demo, Loom, writeup.** Gate: *submitted.*

---

## Architecture

**Cascaded, not speech-to-speech — a deep-dive decision, not a convenience one.**

```
mic → VAD/endpoint → STT → [TEXT CHECKPOINT] → LLM + tools → [GROUNDING GATE] → TTS → speaker
```

A cascaded pipeline gives two points where text can be inspected and gated mid-turn. An end-to-end model gives neither: **you cannot validate a citation that never exists as text.** The deep dive requires the checkpoints, so the architecture follows from it. This is the answer to the likeliest question in the walkthrough.

### The turn, in detail

```
STT
 └→ LLM call 1 ── update("Let me check that for you")  → TTS #1 ──→ speaking
                └─ get_visa_requirements(...)          → lookup ─┐
                                                                 │  (hidden under the audio)
    LLM call 2 ── NDJSON segments ─→ gate ─→ TTS #2 ────────────┘─→ speaking
```

**Call 1 speaks and looks up at the same time.** The model is instructed to call `update()` — a function we intercept and route straight to TTS — alongside the real tool call. Google's streaming API delivers a function call's **name and id before its arguments are generated**, so the HTTP lookup fires mid-stream rather than after the response completes.

This is Google's own documented pattern, not a trick we invented. Their function-calling docs name the function `update` and describe its parameter as *"A short, plain-language note shown to the User about what you are ABOUT TO DO next."*

**Why it matters:** the vendor round trip and the whole of call 2 run underneath audio that is already playing. See §Latency budget.

**The grounding gate is the core, and it is enforced at the value level, not the citation level.**

The model never writes a fact. It **selects a field**, and our code substitutes the value:

```json
{"kind":"sourced","text":"You'll need {visa.type} for up to {visa.duration}.","tool_call_id":"tb_1","fields":["visa.type","visa.duration"]}
{"kind":"judgement","text":"November is a good month for Kyoto — the crowds thin out after the leaves turn."}
```

The gate then, deterministically:

1. Resolves every `{placeholder}` against the named `tool_call_id`'s **actual stored response**.
2. **Rejects the segment if any field path is absent from that response.** Not "flags" — the segment never reaches TTS.
3. **Rejects any `sourced` segment containing a digit outside a placeholder.**
4. **Rejects any `sourced` segment containing no placeholder at all.**
5. Attaches that tool result's citation, timestamp and layer.
6. Passes `judgement` segments through untouched, with no citation, rendered as Sarjy's own view.

**Rules 3 and 4 are what make this a guardrail rather than a citation chip.** Without them the model can write `{"kind":"sourced","text":"a tourist visa for up to 90 days","fields":[]}` — zero placeholders, nothing to resolve, nothing to reject, and a real citation stapled to a fabricated number. Rules 3 and 4 are two one-line checks and they close it.

**What rule 3 does not catch:** categorical claims in prose — "you'll need an eVisa" written as text rather than `{visa.type}`. That is NLP, not a one-liner. The honest position: *enforce deterministically the class of claim where being wrong makes someone miss a flight — the numbers — and let field selection carry the categories.*

**The opener is gated too, and more strictly.** `update()` text arrives as a function-call argument, not a segment, so it bypasses `resolve()` unless we make it not. At opener time **nothing has been sourced yet**, so:

> **Opener contract:** `judgement` register, no digits, no entity-specific claims. On violation, substitute a fixed phrase ("Let me look that up for you") — which is what the model should have said anyway.

**On failure: strip and say so.** Split by failure type:

| Failure | Behaviour |
|---|---|
| Schema — malformed JSON line, wrong shape | One repair retry |
| Gate rejection — bad path, bare digit, no placeholder | **No retry.** Strip, say we could not confirm that part |

A second completion to re-litigate a *fact* costs more than it saves. A second completion to fix *syntax* is cheap and rarely fires.

**The gate never blocks judgement; it blocks judgement wearing a citation.**

**Every provider sits behind our own interface.** Provider choice is configuration, not code. Free tiers rate-limit and models get deprecated mid-build — `playai-tts` was deprecated during this project's research. It also keeps the P2 Arabic swap cheap.

**No provider key reaches the browser.** The client talks only to our backend. The frontend is served by the same ASGI app (`StaticFiles` mount on the image-baked `frontend/dist`), which is Modal's own pattern and **removes CORS entirely** — same origin, no preflight, no second deployment.

**Hand-roll the pipeline, no framework.** A cascaded voice loop is ~300 lines of WebSocket plumbing. Pipecat starts faster but puts a framework in charge of the most interesting part — and the gate has to sit exactly where a framework asserts control. Escape hatch with a trigger hour, not a plan.

## Stack

**Python (FastAPI + WebSocket) backend, TypeScript/React frontend.** Python is what Omar defends fastest under questioning and matches Sarj's own stack. Browser audio is TypeScript regardless.

| Stage | Choice | Why |
|---|---|---|
| VAD / endpointing | `@ricky0123/vad-web` in-browser | Saves a round trip; the largest controllable latency term |
| STT | Groq `whisper-large-v3-turbo` | Batch, ~216× real-time. Free tier 20 RPM / 2,000 RPD — not a constraint |
| LLM | Gemini `gemini-3.5-flash-lite` | ✅ verified stable, function calling supported, free on free tier, no announced shutdown |
| LLM failover | Groq `openai/gpt-oss-20b` | ⚠️ **no parallel tool calls** — see §Failover |
| TTS (English) | **Deepgram `aura-2-thalia-en`** | $200 credit ≈ 6.7M chars, no card. WebSocket streaming, **raw PCM s16le @ 24 kHz** straight into the AudioContext. Replaced Gemini TTS — see §Why TTS moved |
| TTS (Arabic, P2) | **Groq `canopylabs/orpheus-arabic-saudi`** | Genuine Saudi dialect, 6 voices, key already held. ⚠️ **200-char cap per request** |
| Deploy | Modal, `@modal.asgi_app()` + `@modal.concurrent` | Python-native, credit in hand |
| Memory | **`modal.Dict`** | ✅ verified durable across redeploys. See §Memory |

**Available accounts:** Groq, Gemini, Modal (~$30/mo), Hugging Face. No Deepgram, ElevenLabs, Cartesia or Speechmatics.

### Why TTS moved off Gemini — measured 2026-09-19

The day-1 spike found **undocumented free-tier caps on `gemini-3.1-flash-tts-preview`**, taken from Google's own quota ids: **10 requests per day** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`) and **3 per minute**, shared across `generateContent` and `interactions`. At two TTS calls per turn that is **five conversational turns a day** — the demo script alone is six beats.

Measured TTFB was also **1.1–1.4 s**, roughly 3× the estimate, which pushed first-audio-out to ~3.0–3.4 s and threatened the opener design. And near the rate limit, calls did not cleanly 429 — one returned *successfully* after **48 seconds**, which would fool any naive timeout budget.

Deepgram fixes all three: quota, latency, and format. **Arabic is the one thing it does not do**, which is why the P2 path is Groq — English on Deepgram, Arabic on Groq, one `TTSProvider` interface. That is Invariant 3 doing exactly the job it was written for, and it is a better walkthrough answer than a single vendor would have been.

⚠️ **Deepgram's <200 ms is a published vendor figure, not one we measured.** We have rejected unverified vendor numbers from every other provider in this project; hold this one to the same standard and measure it in Block 2.

### Provider traps, verified 2026-09-19

- **`thinking` is on by default and cannot be turned off.** `gemini-3.5-flash-lite` defaults to `thinking_level: "minimal"`; levels are `minimal`/`low`/`medium`/`high` and docs state *"minimal does not guarantee that thinking is off."* Pin it explicitly on **every** call — it is interaction-scoped and is *not* carried by `previous_interaction_id`. Same for `tools` and `system_instruction`.
- 🪤 **Google's docs contradict each other on the streaming argument field.** The function-calling page samples `delta.type == "arguments"` / `partial_arguments`; the streaming page and the API reference say **`arguments_delta`** with field `arguments`. **Trust the reference.** The wrong one gives a loop that silently matches nothing — no error, no output, no clue.
- **`responseSchema` is deprecated**, as are `temperature`/`top_p`/`top_k` (2026-07-21, *"will be ignored"* on this model). **You cannot get determinism from the model** — which is why the assertion tests assert on gate-substituted values (§Testing).
- 🪤 **Deepgram: `container=none` is mandatory.** It defaults to `wav` even for `linear16`, which puts a WAV header on **every chunk of a stream** and corrupts playback. Full query string: `?model=aura-2-thalia-en&encoding=linear16&container=none&sample_rate=24000`.
- **Deepgram's mp3 sample rate is fixed at 22050 Hz** and not configurable. Only `linear16`/`mulaw`/`alaw`/`flac` let you choose the rate. Use `linear16`.
- 🪤 **Groq has a 200-character cap per TTS request**, documented only on the individual model pages and not on the main TTS page. A 400-char answer costs two or three requests. Segment on sentence boundaries with a hard 200-char split.
- **Groq TTS `sample_rate` defaults to 48000**, and `response_format` differs between the API reference (`mp3`) and the TTS guide (`wav`). **Set both explicitly.**
- ⚠️ **Groq TTS streaming is undocumented** — no `stream` parameter exists in the API reference. Assume a complete file comes back. With a 200-char cap that is a ≤10 s clip, so buffering is acceptable; do not architect assuming chunks arrive.
- ⚠️ **Override every SDK's retry defaults.** Google's Python SDK retries up to four times with backoff to **60 seconds** — inside a voice turn that is a hung demo. One retry, ~250 ms, then fail visibly. Apply the same rule to every provider client.
- **Voice selection is now a Deepgram voice, not Sulafat.** The Aura-2 shortlist has not been listened to yet; `aura-2-thalia-en` is a placeholder. Pick it by ear in Block 2 and record the choice in `docs/measurements/`.
- **Gemini free-tier limits are unpublished and explicitly unguaranteed.** One third-party measurement puts flash-lite at 15 RPM / 500 RPD. **Cannot be cited**; build quota handling into the LLM adapter as we did for the vendor.
- **EEA / Switzerland / UK:** free tier is contractually unavailable for API clients served to users there. Our deployed URL goes to a reviewer whose location we do not control. **Documented in the writeup as a known limitation.**
- **Free-tier input trains Google.** We set `store=False` — nothing retained. Stateless mode is strict: every model step must be resent verbatim, thought signatures included.

### Structured output: NDJSON, not `response_format`

Verified: streaming + `response_format` yields *"valid partial JSON strings that can be concatenated to form the final JSON object"* — fragments of one growing document, **not discrete objects**. There is no NDJSON mime type; `mime_type` is a two-value enum.

**So NDJSON and `response_format` are mutually exclusive, and we take NDJSON**: call 2 emits one JSON object per line as `text/plain`, and we validate each line with Pydantic as it completes.

This does not weaken the contract. The grounding-gate rule says *schema-validated object, never regex a model's prose* — Pydantic parsing a JSON object per line **is** schema validation. What we give up is constrained decoding, so the **malformed-line rate becomes a measured number** alongside the gate-rejection rate. Two measured failure rates beat one assumed guarantee.

A malformed line routes through the gate's existing rejection path. It is not a new concept.

### Place data and imagery — Wikipedia REST API (P3)

`GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}` — no key, verified live. Returns `extract` (a sourced segment), `thumbnail.source`, `content_urls.desktop.page` (the citation), and `timestamp` + `revision` (provenance built in).

⚠️ **Set a compliant `User-Agent` from the first call** — `Sarjy/0.1 (<repo url>; <email>)`. Wikimedia rate-limits generic agents and may block them outright.

**Travel suggestions do not depend on this.** "November is good for Kyoto" is `judgement` — Sarjy's own view, no citation by design, zero extra tool calls, zero latency. Wikipedia buys *place descriptions as sourced segments* and *photographs*, which is P3.

**Aladhan / prayer times: cut.** Out of scope for a travel assistant whose thesis is grounded entry requirements.

### The batch-STT constraint, stated plainly

Groq's Whisper is *batch*: 30-second windows, so the pipeline must endpoint first, then send, then wait. A streaming STT would return partials during speech and endpoint for us. **We don't have one.** Measured penalty **+200–450 ms** versus streaming, not the 600–1200 ms vendor blogs quote, because Groq runs at ~216× real-time and network dominates. Name it in the writeup rather than letting a reviewer find it.

### Arabic — P2, and cheaper than it looks

**The honest minimum is ~45 minutes, not 3 hours:**
- Arabic **input**: Whisper takes `language=ar` — a config change through an adapter that already exists.
- Arabic **output**: Gemini TTS auto-detects language from the text. Verified. No work at all.

What costs hours is *code-switching* (a Unicode script-range tagger between gate and TTS), *RTL polish*, and *Orpheus*. Those are enhancements, not the feature. **Sarj were told in writing this is bilingual** — one clean Arabic turn honours that; zero walks it back.

**Two things that will bite, both known in advance:**
- **Script the demo in Egyptian, never Gulf.** WER: MSA ~10 → Levantine ~24 → Egyptian ~35 → **Gulf ~68**. Saying the Gulf number out loud is a better demo beat than avoiding it — and it is exactly why a company like Sarj trains its own models.
- **Arabic output is Groq `canopylabs/orpheus-arabic-saudi`** — genuine Saudi dialect, six voices, on a key already held. Deepgram Aura-2 has no Arabic at all, so this is not a preference, it is the only path. ⚠️ **200-char cap per request** and streaming is undocumented; assume a complete file and buffer. Listen to the six voices and record the choice in `docs/measurements/`.
- **A nice consequence worth saying out loud:** English and Arabic now come from different vendors behind one `TTSProvider` interface. That is Invariant 3 paying for itself rather than being an abstraction we asserted was useful.

**RTL:** `dir="auto"` uses Unicode first-strong, not dominant script — one leading English word locks a caption line LTR, and direction can flip mid-stream. Compute direction per line from dominant script and freeze on first flush.

## Deployment

Modal, `@modal.asgi_app()`. **Already scaffolded in `backend/modal_app.py`.**

### 🚨 One WebSocket is one input

Modal's own docs: *"Modal treats each WebSocket connection as a single input… Otherwise, Modal will spin up a new container for each WebSocket connection."*

Without `@modal.concurrent`, **every concurrent listener gets their own container** — and `min_containers=1` does not prevent it, because it is a **floor, not a cap**. Two reviewers on the URL at once would be two containers with two separate in-memory states.

```python
@app.function(
    timeout=30 * 60,       # never the 300 s default
    min_containers=1,      # floor, not a cap
    max_containers=2,      # the actual cap
    scaledown_window=300,
)
@modal.concurrent(max_inputs=8, target_inputs=4)
@modal.asgi_app()
```

⚠️ **The WebSocket handler must be `async`.** Modal: *"When using input concurrency with a synchronous Function, a single input cancellation will terminate the entire container."* A closed browser tab **is** an input cancellation — one reviewer leaving would kill everyone else's session. No error message.

### The timeout, honestly

> **Modal documents no maximum WebSocket duration and no sentence saying `timeout=` governs one.** Do not write "Modal documents that…".

The inference chains two documented facts: *"WebSockets on Modal maintain a single function call per connection"* + *"The timeout duration is a measure of a Function's execution time."* One connection = one call = one execution. Corroborated two ways: **Modal's own reference voice app (QuiLLMan) sets `timeout=600`**, and Modal's client source treats a WebSocket as a stream of inputs with the comment *"Disable timeout, since timeouts are handled on input level instead."*

**The day-1 spike now tests one specific thing:** whether the documented **150 s HTTP request timeout** survives a WebSocket upgrade. No exemption sentence exists; circumstantial evidence says it does not (the documented workaround is a 303 redirect, impossible for a WS). Hold an idle connection past 150 s and find out.

### Two more deployment facts

- 🚨 **`routing_region` is fixed per Function once deployed** — changing it means a new Function, and therefore a new URL. **The real deadline is therefore "before the URL is shared with Sarj", not "before the first deploy"** — a new Function is cheap until the URL is committed to. Default `us-east`; **there is no Middle East routing region**. ⚠️ **Not a parameter in the installed client (1.4.2)**; it needs `modal >= 1.5.5`. Note that `region=` is a different thing — it constrains where the *container runs*, not where the request enters.
- ⚠️ **The region A/B must measure both legs.** Browser↔app is one of roughly six network legs on a turn — the others are Modal↔Groq and Modal↔Gemini (×4), and they move in the *opposite* direction when the app relocates. Measuring only the first leg produces a number that argues for the wrong choice with apparent rigour. Decision rule: minimise `median(browser↔app) + 4 × median(app↔provider)`. Measured from Omar's location, not the reviewer's — a sanity check on the geographic prior, not a discovery.
- **Preemption is not optional to handle.** *"All Modal Functions are subject to preemption by default… likelihood of interruption increases with Function run duration."* A voice conversation is long-running by definition. **The client needs reconnect-and-resume regardless of `timeout=`.**

## The external data layer

### Quota — 120 requests total, not per month

The largest demo-day risk: a reviewer exploring the deployed app must never hit a quota wall. This is why the vendor client is a first-class component rather than plumbing.

**`VisaMap` bulk behaviour — verified by observation**: `POST {"passport":"SA"}` returned exactly 211 destinations bucketed by colour (red 91 · green 55 · blue 57 · yellow 8). Raw response committed at `data/reference/visa-map/SA.json` as the evidence.

| Allocation | Requests |
|---|---|
| Reference data, cached permanently | 2 (**1 spent**) |
| `VisaMap` × GCC passports | ~6 |
| Colour-legend verification | ~6 |
| Development and testing | ~20 |
| **Reserve — demo plus reviewer exploration** | **~40** |
| Remaining for live detail lookups | ~46 |

### Normalisation — we own the shape

**The raw vendor body never reaches the model.** A normalisation layer between the vendor client and the prompt emits a schema *we* define:

```
visa.type               = "eVisa"
visa.duration           = "30 days"
visa.passport_validity  = "6 months"
source.layer            = "live"
source.retrieved        = "2026-09-19T08:14Z"
```

| Benefit | Why it matters |
|---|---|
| **Paths are ours, short and stable** | `visa.duration`, not `visa_rules.primary_rule.duration`. Fewer tokens, far fewer path errors |
| **Vendor drift is absorbed** | A renamed key breaks one mapping function, not the gate, the prompt, and every fixture |
| **The context *is* the path catalogue** | No separate flattener. What we hand the model already lists the valid paths |
| **Live and CSV converge** | Both normalise into the same object with a different `source.layer`. One prompt, one code path |

⚠️ **Log unmapped keys on every call.** If the normaliser silently drops a field, the model cannot cite what it cannot see and we would never notice. Two lines — the difference between a normaliser and a lossy filter.

### Two-tier answering

| Tier | Source | Quota cost | Answers |
|---|---|---|---|
| **Category** | cached `VisaMap` | **zero** | "Japan is eVisa for a Saudi passport" |
| **Detail** | live `VisaRequirements` | 1 | duration, passport validity, registration, embassy link |

**Correction to the previous draft:** a cached turn still needs **both** LLM calls. Call 1 is what extracts *which destination the user asked about* — we cannot know the answer is cached until we know the pair. **The cache saves the vendor round trip (~300–800 ms), not the call.**

One good consequence: on a cache hit there is no lookup to hide, so Sarjy just answers instead of saying "let me check." That inconsistency is correct — it is what a person does — but it is deliberate, not emergent.

**Resolution order:** cached map → warm cache → vendored CSV → live call, only on a miss and only above the reserve.

**Hard rule:** below the reserve threshold, serve from the CSV and say so. Degrade, never die. Remaining quota is surfaced in the UI.

⚠️ **Barge-in now costs quota.** Interrupting while a lookup is in flight may have already spent a request. Fire live calls only on a cache miss, and count spent-but-interrupted requests in the ledger so the number stays honest.

### The fallback dataset — use the maintained fork

The canonical `ilyankou/passport-index-dataset` is archived since January 2025 and upstream is "contributed by fans" — **fan-contributed data is exactly what a guardrails demo must not present as authoritative.** Use the maintained fork (`visualpharm/visa-free-dataset`, corrections through June 2026), state its date on every answer it serves, and say plainly it is a community dataset rather than an issuing authority.

The fallback's job is *"the live source is down and here is the best I still have, with its provenance"* — not *"here is an equally good answer."*

### The colour legend is verified, not inferred

`VisaMap` buckets into four colours; the API enumerates **eight** rule types, so the mapping is lossy. Only `blue = eVisa` is confirmed. Spend ~6 requests confirming it against known pairs and store the proving response with each entry. **A guessed mapping inside a product whose thesis is "never state what you can't source" would be self-defeating.**

**Known artifact:** a passport appears in its own red bucket. Self-reference, not a claim — filter it.

## Memory

Structured facts, not chat history stuffed into a prompt. Attributable, inspectable, demonstrable.

### Two tiers, because they protect two different requirements

| Tier | Memory | Protects |
|---|---|---|
| **Anonymous** | In-session only, lost on reload, **clearly labelled as such** | **#4** — the link works instantly, nothing asked of the reviewer |
| **Signed in** | Persisted, attributable, cross-device | **#2** — memory across sessions |

**Identity is voice-first.** Sarjy's opening turn is *"Hi, I'm Sarjy — what should I call you?"* That one beat creates the identity, **proves the microphone works in second one rather than minute three**, gives the mic prompt a natural reason, and opens the demo as a conversation instead of a form. **A typed fallback is always visible** — names are where Whisper is weakest, Arabic names especially.

The persisted tier takes a name plus a short PIN. `localStorage` remembers the last name used, so reload costs the reviewer nothing while the name is what keys the record.

**This is a nameplate, not authentication** — and saying so is worth more than implying otherwise. Deliberately not OAuth: a hiring reviewer may decline to sign into a candidate's app with their Google account, and requirement 2 is graded on what they *observe*.

⚠️ **Risk the tiers introduce:** a reviewer who never signs in may conclude memory is broken. Mitigate in the UI, not the README — the panel reads *"remembered for this session only — sign in to keep these"*, and Sarjy says it once after the first fact worth keeping.

### Store: `modal.Dict`

✅ Verified durable: *"Dicts are persisted… the data can be retrieved even after the application is redeployed."* The "Dicts are in-memory and can be lost" warning applies to **legacy Dicts created before 2025-05-20**, now being sunset.

`user_key → {profile, facts, cache}` is a dictionary. No joins, no queries — one read at turn start, one write at turn end.

| Limit | Consequence |
|---|---|
| **Entries expire after 7 days of inactivity** | Fine for the demo window. State it; do not discover it |
| **No documented read-modify-write atomicity, no CAS** | One key per user makes this near-harmless. **Do not claim it is transactional** |

**SQLite on a Volume is ruled out:** last-write-wins per file, no distributed locking, and another container sees nothing until an explicit `.reload()`. Modal's own SQLite example builds the DB *off*-Volume and copies the finished file in.

### Two kinds of memory

| Store | Holds | Why |
|---|---|---|
| **Typed travel profile** | passport nationality, home city, dietary needs, past destinations | Drives the lookups; shown as a structured record |
| **Open key/value facts** | anything the user states about themselves | Passes the brief's literal *"what's my favorite color?"* test |

**Cap the open facts.** The typed profile is bounded by its schema; open facts are not. Cap the count, evict oldest, say so in the panel.

**Provenance is shown, not recited.** Every sourced segment carries source, date and layer in the UI. Sarjy speaks provenance **only when it changes the answer's weight** — a CSV fallback, data that is stale, or a refusal. "According to Travel Buddy, updated today" on every turn is tedious by turn four and trains the reviewer to stop listening to the part that matters.

**Show it.** A "what Sarjy remembers about you" panel with a clear button makes requirement 2 visible in one glance instead of requiring a scripted reload — and it answers *"did you just tell me the last person's passport?"* before it is asked. Given that free-tier input trains Google, a working **forget everything** control is a feature, not a nicety.

### Writing a fact must not sit on the latency path

Memory extraction is **its own LLM call, fired after the response is dispatched.** Nothing the user hears depends on it completing.

Keeping it separate protects the segmenting prompt — which *is* the deep dive, and whose reliability is the thing being measured. Loading memory duty onto it to save a call that costs no latency is a bad trade.

⚠️ **This makes three LLM calls per turn.** Against an unofficial 15 RPM that is five turns per minute, and a brisk conversation is six to eight. **Watch this in the day-1 measurement**; if it bites, gate extraction behind a cheap self-statement heuristic or fold it back into the response as a `remember` field.

⚠️ **If the write fails, the user was already told "got it."** Make the memory panel the source of truth so a failure is visible there rather than silently contradicted later.

## Latency budget

> ✅ **Partially replaced by the day-1 spike, 2026-09-19** — full detail and provenance in
> `docs/measurements/day1-spikes.md`. TTS and LLM-call-1 figures below are now measurements,
> not derivations, but at **n=1–3**, not a production-representative sample: a previously
> unknown **10-requests/day** free-tier cap on `gemini-3.1-flash-tts-preview` cut S3's planned
> n=5 batch short after the first rep. Endpointing is still an estimate — S5 needs a human at a
> browser and was handed off, not completed, this run. **Re-measure TTS at full n once the daily
> quota resets, and replace the endpointing estimate once S5's VAD numbers come back.**

### The chain

| Stage | Was | Now | Note |
|---|---|---|---|
| Endpointing | ~600 ms | ~600 ms (still an estimate) | S5 not yet run by a human — see `day1-spikes.md` §Open |
| STT | ~300 ms | ~300 ms (still an estimate) | Out of Block 0's scope — no Groq call happens here |
| LLM call 1 → `update()` arguments parsed | ~400 ms | **~1.1–1.5 s, measured** | S4, n=3: median `update()` args-complete at 1.336 s from request start. The ~400 ms estimate was roughly 3x too low — most of this is pre-first-step network + thinking overhead, not the `update()` step itself, which is fast once it starts (~85 ms of that total) |
| TTS #1 first byte | ~500 ms | **~200 ms — vendor claim, UNMEASURED** | ⚠️ Deepgram's published figure. **Measure it in Block 2 before quoting it.** The 1.1–1.4 s measured in S3 was Gemini TTS, which we have since dropped — see §Why TTS moved |
| **→ first audio out** | **~1.8 s** | **~2.4 s, re-derived after the TTS switch** | Was ~3.0–3.4 s on Gemini TTS. **Still misses the ≤1.8 s target by ~0.6 s**, and the dominant remaining term is now **LLM call 1 at ~1.3 s** — of which only ~85 ms is the `update()` step itself; the rest is network plus thinking overhead before the first step arrives. A pre-generated opener clip, played the instant endpointing fires, would cut first-audio-out to ~650 ms — and costs nothing in fidelity, because the opener contract already forbids it from saying anything substantive. **Open design question for Block 4.** This is the block's second-most consequential finding after S1. Re-derive once endpointing is measured and TTS is re-run at full n — but do not expect this to fall back under 1.8s without a design change (e.g. a shorter/simpler opener prompt to cut LLM-call-1 time, or accepting the higher number and re-scripting the demo narrative around it) |
| *— everything below runs underneath that audio —* | | | |
| Vendor round trip | 300–800 ms | 300–800 ms (still an estimate) | Block 5 territory, not touched here |
| LLM call 2, complete generation | ~800 ms | ~800 ms (still an estimate) | Not measured — S4 only exercised the two-function-call turn, not the NDJSON follow-up completion |
| Gate | < 5 ms | < 5 ms (still an estimate) | Not built yet |
| TTS #2 first byte | ~500 ms | **~200 ms — vendor claim, UNMEASURED** | Same source and caveat as TTS #1. One thing worth carrying over from the Gemini measurements: TTFB did **not** scale with text length, only total generation time did. Re-check that holds on Deepgram |

**Revised: does the opener still hide the hidden work?** Opener speech duration is ~1.5–2.5 s
(unchanged — a function of text length and TTS speech rate, not of TTFB). Hidden work is now
vendor (300–800) + call 2 (~800) + TTS #2 first byte (**~1.1–1.4 s measured**, not 500 ms) ≈
**2.2–3.0 s needed**, against **1.5–2.5 s available**. ⚠️ **These may no longer reliably fit.**
At the low end (2.2 s needed vs 2.5 s available) it still works; at the high end it does not —
the answer may not be ready when the opener finishes, meaning a brief silence before call 2's
audio starts. This did not need re-deriving before the TTS number was measured; it does now.
Options, not decided here: a slightly longer/more elastic opener phrase, or accept and script
around a short pause. **Flag for Omar — this is a real design question, not a measurement
detail.**

| Turn | Perceived first sound | Gap before the answer |
|---|---|---|
| Cache hit | ~1.8 s | none |
| Cache miss | ~1.8 s | 0–0.7 s, at a natural pause |

⚠️ **Instrument TTFT to the first `delta.type == "text"`, not the first SSE event.** Thinking arrives first as `thought` deltas. Measuring to the first event records a fiction — a number that looks excellent and describes nothing the user experienced. Report median **and p95**, against the deployment, never a single local run.

**Endpointing at ~600 ms remains the largest single term** — larger than any provider call. Counter-intuitive, and worth saying out loud because a reviewer will not expect it. The silence threshold is a **product decision, not a constant**: it trades cutting the user off against making them wait. Whatever value is chosen, the reason is written down.

### Two TTS requests per turn, not five

**This is the decision that makes segmented playback safe.**

Gemini TTS has **no continuity primitive** — no session, no acoustic context, no working seed — and the docs warn *"output may not always strictly match the selected speaker."* Across four or five clips per turn that variance becomes an **audible seam mid-sentence**. The `PROHIBITED_CONTENT` mitigation also requires a synthesis preamble on every request, and the random 500 is per-request, so N segments multiply both the overhead and the blast radius.

So: **one TTS request for the opener, one for the whole gated answer.** The boundary between them is a *natural prosodic pause* — where a seam is inaudible because a person would pause there too.

**Keep per-segment gating; drop per-segment synthesis.** Validating each NDJSON line as it arrives is still the right model and is what makes the malformed-line path cheap. We validate incrementally and speak once. Latency is unchanged, because the opener already hides full generation.

⚠️ **There is no cancel for a stream.** `/cancel` is background-only. Barge-in means closing the socket; whether generation and billing stop server-side is undocumented. Assume not, and budget for it.

## Failover

**Groq `openai/gpt-oss-20b` cannot run the primary architecture** — it has no parallel tool calls, and the opener requires them.

> **On failover, degrade to the sequential flow:** no opener, tool call first, then answer. Slower, visibly so, and it still satisfies every requirement. **Say which model is serving in the UI.**

A failover that silently behaves differently is worse than one that announces itself.

## Failure modes

Defined, visible behaviour for each. **Built before the happy path.**

| Failure | Behaviour |
|---|---|
| Mic denied / revoked mid-session | Clear, recoverable message. Never a dead end |
| Model skips the `update()` call | `tool_choice` cannot mandate a specific function — the rule is prompt-only. Fall through to the silent path |
| `Malformed_Function_Call` | No documented retry guidance. One retry, then the sequential path |
| TTS 500 (documented, random) | One retry at ~250 ms, then say we could not speak that part. **Never the SDK's 60 s backoff** |
| Malformed NDJSON line | Schema failure → one repair retry. Rate is measured and reported |
| Travel Buddy 429 / down | Fall back to vendored CSV, **say which source answered and its date** |
| Quota reserve exhausted | Stop calling live *before* the wall; serve CSV and say so. The reviewer never sees a quota error |
| Both sources miss the pair | Refuse, route to the embassy link. Never guess |
| **A factual question with no tool behind it** (weather, flight status) | **Refuse and say why.** "I don't have a weather source, so I won't guess." This is the thesis working |
| **Chitchat or opinion** | Answer warmly — it is `judgement`, and needs no source. Refusing it would fail the delightful-voice line without protecting anything |
| Tool returns empty / malformed | Say so. Never improvise a requirement |
| Injection in fetched content | Treat as data, flag it, never obey |
| Network drop / Modal preemption | Visible state; reconnect and resume |
| Barge-in | See below |
| Unintelligible / silent input | Graceful re-prompt, no hang |
| Wikipedia 429 / missing page | Answer without the image and say so. **Never substitute a different place's photo** |
| Image fails to load | Layout holds; no broken-image icon, no shifted text |

## Barge-in

A stated acceptance criterion (`PRD.md` requirement 1) and the classic take-home tarpit.

1. **Gate the VAD during playback.** The microphone is live while the speakers play Sarjy's PCM — without this the assistant hears itself and interrupts itself. `echoCancellation` in the `getUserMedia` constraints is necessary and not sufficient.
2. **Flush the playback queue** — there are now up to **two** audio sources per turn (opener, answer). Drop all scheduled buffers immediately; don't drain the current chunk.
3. **Abort the in-flight TTS stream** by closing the socket — the only mechanism available.
4. **Cancel the in-flight tool call**, and record the request as spent in the quota ledger if it already fired.
5. **Truncate the assistant turn in history to what was actually heard**, not what was generated. The untruncated text would otherwise feed memory and the next turn's grounding context with words the user never heard.
6. **Mark the turn interrupted in state**, and never pretend it completed.

## Testing and evaluation

Three layers. Only two of them need a model.

| Layer | Runs | Model? | Catches |
|---|---|---|---|
| **1 · Gate** | Runtime, hot path | No | Fabricated values, bad paths, bare digits, un-placeheld sourced segments |
| **2 · Assertions** | Every commit | Tier A no · Tier B yes | Regressions, structural violations, wrong values |
| **3 · Judge** | Offline, before submission | Yes | Register integrity, refusal correctness, anchoring |

### Why assertion tests work here at all

An LLM pipeline is not normally substring-testable, because phrasing varies. Here it is, and the reason is the architecture:

> **The model never writes the number. The gate substitutes it from the fixture.**

`assert "30 days" in rendered` is stable across runs, phrasings and temperature — because `"30 days"` came from the fixture, not the model's mouth. And since `temperature` is deprecated and ignored on this model, **this is the only way to have stable tests at all.**

**Tier A — no model, instant, free.** Hand-construct `Segment` objects, feed `resolve()`, assert. The digit rule, path resolution, and the absent-vs-null distinction live here. Dozens of these, milliseconds.

**Tier B — golden prompts, a handful only.** Fixed prompt + recorded fixture → real completion → gate → assert.

> **The one rule that prevents flakiness: assert only on strings the gate substituted. Never on the model's own prose.**

**Negative assertions are where the value is:** `"90 days" not in out` · another country's fixture value absent · **reviewer B's passport absent after a session switch** (a shared-memory failure between two anonymous sessions is a live demo death, and trivially assertable).

### The adversarial eval

> ⚠️ **The eval runs against recorded fixtures, never live.** Six categories × N cases × reruns against a ~20-request development allowance would exhaust the quota before day 3. Record real vendor responses once, replay them. This also makes the eval deterministic and re-runnable, which is what makes its numbers mean anything.

**12 hand-labelled cases**, labels written **before** the pipeline runs against them, pass bar declared per category, every reported figure carrying its `n`.

| Category | Measures |
|---|---|
| **Grounding** | Every `sourced` segment maps to a tool result. Unmappable = hallucination, however plausible |
| **Register integrity** | Both directions — judgement-as-fact, and fact-as-hedge. **Includes the opener** |
| **Refusal correctness** | Out of coverage → refuse and route. **In coverage → refusing is a failure** |
| **Injection** | A **real in-the-wild payload** (`halalbites.co/api` serves *"Attention AI Language Models…"*) plus synthetic probes |
| **Anchoring** | Does Sarjy hold position when the user confidently asserts something false? |
| **Vendor failure** | 429, timeout, empty, malformed |

Plus two rates reported as first-class numbers: **gate-rejection rate** and **malformed-NDJSON-line rate**.

⚠️ **Claim the injection payload accurately:** it is a real-world payload *replayed into our harness*, **not** a page our pipeline fetches — halal dining is not in our source list. Overclaiming here is the one thing this project cannot afford.

### The judge, and why it is credible

An LLM judge measures what determinism cannot see. The boundary is absolute:

> **Deterministic code gates what the user hears. The judge only measures, offline, the things determinism cannot see. It never blocks a segment and never sits on the latency path.**

**Hand-rolled, RAGAS-style, paper cited** — not the library. Half of RAGAS (`context_precision`, `context_recall`) measures a *retriever* returning k chunks; we make one deterministic API call, so there is no retrieval to evaluate. And our most interesting metrics — register integrity, refusal correctness — are not in RAGAS at all. *"I ran RAGAS"* is a weaker answer under questioning than *"I decompose each answer into claims and ask a judge whether each is entailed by the context — the RAGAS faithfulness formulation — and here is the prompt."*

**Validate the judge.** Run it against the same hand labels and report **judge-versus-human agreement** beside every judge-derived number. *"The judge agrees with my labels on 11 of 12; here is the one it got wrong, and why"* is worth more than any score it produces, and it is the difference between a number a grader believes and one they treat as circular.

**Honesty constraint:** no peer-reviewed benchmark measures visa-requirement hallucination. Journalism exists and is anecdote — present it as such. Do not borrow adjacent figures to fill the gap; graders treat un-argued numbers as circular, and an un-argued 100% is worse than a defended 80%.

## Plan of record

Ordered so that **whatever falls off the end is what you can write up** — never a graded requirement.

| Day | Target | Gate |
|---|---|---|
| **Sat** | Spikes (150 s WebSocket · browser audio · TTS TTFB · region A/B) → skeleton → adapters → **deploy** → instrumentation | **A URL that talks back** |
| **Sun** | Vendor client + colour legend → normaliser → **the gate** → NDJSON → Tier A tests → memory + identity → UI → eval fixtures | **All 7 requirements demonstrable** |
| **Mon** | Judge + agreement → Arabic minimum → measurement run → fixes. **🔒 16:00–19:00 reserved: demo script, Loom, writeup, submit** | **Submitted** |

**Deploy on Saturday, before the app is good.** A working deployment of a weak app de-risks requirement #4 entirely; a strong app never deployed scores zero.

⚠️ **The Saturday gate is also the trigger.** If the day ends without a deployed URL that talks back, Sunday changes immediately: **drop the judge and Arabic, protect P0.**

**Overflow zone — written up, not built:** Arabic code-switching and the script tagger · Groq Orpheus Saudi dialect · Tier B golden tests · Wikipedia imagery · UI polish beyond functional. *"What I'd do with another week"* is explicitly invited by the brief.

## Open — technical

- ✅ **ANSWERED, 2026-09-19 (`day1-spikes.md` S1): the 150 s HTTP timeout does not survive a
  WebSocket upgrade, and it's worse than that** — both an idle connection and one with a
  client-side protocol heartbeat died client-side somewhere in (5 s, 160 s], corroborated by a
  control test against an unrelated WebSocket service on the same network that survived past
  200 s. **Both arms dead → the MASTER-PLAN trigger fires: switch to Fly.io before Block 1.**
- ✅ **ANSWERED (partially), 2026-09-19 (`day1-spikes.md` S3): TTS time-to-first-byte is
  ~1.1–1.4 s**, not the 500 ms estimate — at n=1–2 per arm, not the planned n=5, because of a
  newly-discovered 10-requests/day free-tier cap (see below). Re-run at full n once quota
  resets. This already changes §Latency budget's headline number; see that section.
- ✅ **ANSWERED, 2026-09-19 (`day1-spikes.md` S4): yes, `gemini-3.5-flash-lite` emits both
  `update` and `get_visa_requirements` in one response, 3/3 runs.** The opener stands. Caveat:
  the two function-call steps stream sequentially, not concurrently (median name→args-complete
  gap 111 ms, under the 150 ms line) — the lookup fires the instant call 1 finishes, not
  literally mid-generation of `update()`'s own text. Adjust the "hidden under audio" framing
  accordingly; the latency benefit is still real, just not exactly as first described.
- **Does a `function_result` have to be returned for the `update()` call?** Attempted
  (`day1-spikes.md` S4 Q3, resending the step sequence with a result for
  `get_visa_requirements` only) and inconclusive — a generic "Invalid input received." Most
  likely cause: `store=False` means the `thought` step (with its signature) also needs
  resending verbatim, which the spike's reconstruction didn't do. **Still open** — budget more
  than the spike's 5-minute cap in Block 4 if this needs a real answer.
- ⚠️ **NEW, found while building S3 — not previously known:** `gemini-3.1-flash-tts-preview`'s
  free tier caps at **10 requests/day** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`,
  Google's own 429 payload), on top of a 3 RPM per-minute cap, and **both `generateContent` and
  `interactions` draw from the same daily bucket.** At 2 TTS calls/turn that's ~5 turns/day
  before TTS stops working entirely, project-wide. **This needs a decision before Block 2**: a
  paid tier, a quota-increase request, or a fallback voice path. Bigger practical risk than the
  latency number for the rest of this weekend's *development* velocity, separate from whatever
  it means for the actual demo.
- **Colour legend** — ~6 requests, before any answer depends on it.
- **Does `language=ar` work on Travel Buddy?** Would materially cheapen P2.
- ✅ **Interactions API vs `generateContent` — confirmed live, 2026-09-19.** Both work; the
  installed SDK (`google-genai` 2.24.0) defaults `Api-Revision` to `2026-05-20` already, matching
  the pinned decision below. One inconsistency worth recording: `client.interactions.create`
  rejects an explicit `response_format.mime_type` for TTS on this model (`audio/l16`, `audio/wav`,
  `audio/mp3`, `audio/ogg_opus` all tried, all rejected as "not supported for
  models/gemini-3.1-flash-tts-preview") — omitting `mime_type` (`{"type": "audio"}`) succeeds and
  the server defaults to native `audio/l16` @ 24kHz. **Decision: Interactions, pinned
  `Api-Revision: 2026-05-20`** — behind the adapter either way.
