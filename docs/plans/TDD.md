# Sarjy — Technical Design

**Date:** 2026-09-18 · **Owner:** Omar · Product requirements: `PRD.md`

Everything here changes when the stack changes. If a fact would survive swapping every provider, it belongs in the PRD instead.

Research behind these choices: `python-stack-research.md`, `travel-api-research.md`, `voice-stack-research.md`, `arabic-voice-research.md` — each with its own "what I could not verify" section.

## Summary

Cascaded voice pipeline, hand-rolled, Python backend on Modal. Groq Whisper for STT, Gemini for both the LLM and TTS, browser-side VAD. The grounding gate between the LLM and TTS is the deep dive and the heart of the codebase.

**Three things to test on day one, before building on top of them:** a 10-minute Modal WebSocket, the Travel Buddy colour legend, and the browser audio loop in isolation.

## Architecture

**Cascaded, not speech-to-speech — a deep-dive decision, not a convenience one.**

```
mic → VAD/endpoint → STT → [TEXT CHECKPOINT] → LLM + tools → [GROUNDING GATE] → TTS → speaker
```

A cascaded pipeline gives two points where text can be inspected and gated mid-turn. An end-to-end model gives neither: **you cannot validate a citation that never exists as text.** The deep dive requires the checkpoints, so the architecture follows from it. This is the answer to the likeliest question in the walkthrough.

**The grounding gate is the core, and it is enforced at the value level, not the citation level.**

The model never writes a fact. It **selects a field**, and our code substitutes the value:

```python
# What the model returns — it names the field, it does not state the value.
{"segments": [
  {"kind": "sourced",    "text": "You'll need an {visa_rules.primary_rule.name} for up to {visa_rules.primary_rule.duration}.",
   "tool_call_id": "tb_1", "fields": ["visa_rules.primary_rule.name", "visa_rules.primary_rule.duration"]},
  {"kind": "judgement",  "text": "November is a good month for Kyoto — the crowds thin out after the leaves turn."}
]}
```

The gate then, deterministically:

1. Resolves every `{placeholder}` against the named `tool_call_id`'s **actual stored response**.
2. **Rejects the segment if any field path is absent from that response.** Not "flags" — the segment never reaches TTS.
3. Attaches that tool result's citation and timestamp.
4. Passes `judgement` segments through untouched, with no citation, rendered as Sarjy's own view.

**This is the difference between a guardrail and a citation chip.** If the model can write "90 days" as free text while correctly citing a tool that said 30, the gate is theatre — and that is precisely the hallucination class this project claims to prevent. Here the model *cannot state a number it did not select from a response*, because it never writes numbers at all.

**On failure: strip and say so.** One code path. No re-ask branch — a second completion on the latency path costs more than it saves, and "I couldn't confirm that part" is an honest sentence.

**The gate never blocks judgement; it blocks judgement wearing a citation.** The model proposes; deterministic code disposes — literally, at the level of the substituted string.

**Every provider sits behind our own interface.** Provider choice is configuration, not code. Free tiers rate-limit and models get deprecated mid-build — `playai-tts` was deprecated during this project's research. It also keeps the P2 Arabic swap cheap.

**No provider key reaches the browser.** The client talks only to our backend.

**Hand-roll the pipeline, no framework.** A cascaded voice loop is ~300 lines of WebSocket plumbing. Pipecat starts faster but puts a framework in charge of the most interesting part, and the rubric asks explicitly whether you understand your own code. *First thing to reconsider if day 1 runs long.*

## Stack

**Python (FastAPI + WebSocket) backend, TypeScript/React frontend.** Python is what Omar defends fastest under questioning and matches Sarj's own stack. Browser audio is TypeScript regardless, so the split costs one extra toolchain and nothing conceptually.

| Stage | Choice | Why |
|---|---|---|
| VAD / endpointing | `@ricky0123/vad-web` in-browser | Saves a round trip; the largest controllable latency term |
| STT | Groq `whisper-large-v3-turbo` | Batch, but ~216× real-time |
| LLM | Gemini `gemini-3.5-flash-lite` | Function-calling reliability; grounding depends on it |
| LLM failover | Groq `openai/gpt-oss-20b` | ⚠️ no parallel tool calls |
| TTS | Gemini `gemini-3.1-flash-tts-preview` | Streams, no char cap, 24 kHz PCM, does Arabic |
| Deploy | Modal, `@modal.asgi_app()` | Python-native, credit in hand, documented WebSocket support |
| Memory | **open** — SQLite on a Modal Volume, or Postgres | See §Memory |

**Available accounts:** Groq, Gemini, Modal (~$30/mo), Hugging Face. No Deepgram, ElevenLabs, Cartesia or Speechmatics — provider choice is constrained accordingly.

### Provider traps, all verified 2026-09-18

- **Groq TTS is unusable.** `playai-tts` deprecated 2025-12-31; its replacement is capped at 10 RPM / 100 requests per day / **200 characters per request**, WAV-only, no streaming. That's two or three conversations *per day*, failing mid-sentence. Hence Gemini TTS.
- **Groq's free LLM tier is 8,000 TPM** → ~3.6 turns/minute with a realistic system prompt. A brisk conversation is 6–8. Failover, not primary.
- **Groq's Llama models were deprecated 2026-08-16** and are absent from the free-tier table.
- **Google no longer publishes free-tier rate limits** — only Tiers 1–3. Check `aistudio.google.com/rate-limit` directly.
- **Hugging Face Spaces is out**: a reproduced, unanswered report of the proxy returning HTTP 404 to WebSocket upgrades on Docker Spaces.

### Place data and imagery — Wikipedia REST API

`GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}` — no key, verified live 2026-09-18. Returns:

| Field | Use |
|---|---|
| `extract` | Place description — a **sourced** segment |
| `thumbnail.source` / `originalimage.source` | Photograph (up to 3840×2581) |
| `content_urls.desktop.page` | The citation URL |
| `timestamp` + `revision` | Provenance, built into the response |
| `coordinates` | Feeds Aladhan's **by-coordinate** endpoint — the one that echoes real coords, unlike `timingsByCity` |

Images therefore arrive with attribution and a revision date, which is the provenance discipline applied to a different medium.

⚠️ **Set a compliant `User-Agent` from the first call** — `Sarjy/0.1 (<repo url>; <email>)`. Wikimedia deployed REST Gateway rate limits in early 2026 aimed at unauthenticated non-browser traffic, and their API usage policy states a generic User-Agent may be throttled or blocked outright. Cheap to set now; confusing to debug later.

Cache aggressively — place data barely changes, and a cached `extract` keeps the image on screen when the network is slow.

### The batch-STT constraint, stated plainly

Groq's Whisper is *batch*: 30-second windows, so the pipeline must endpoint first, then send, then wait for the full transcript. A streaming STT would return partials during speech and endpoint for us, collapsing two stages. **We don't have one** — no Deepgram or Speechmatics account.

Measured penalty: **+200–450 ms** versus streaming, not the 600–1200 ms vendor blogs quote, because Groq runs at ~216× real-time and network dominates. Name this in the writeup rather than letting a reviewer find it.

### Arabic — P2, not an afterthought

**Minimum viable:** Arabic **input** via Groq Whisper, which handles MSA and Egyptian acceptably. No new account, no new provider, and the STT interface makes it a config change. Gemini TTS already speaks Arabic, so the output leg exists.

**If it holds up:** code-switching input needs a Speechmatics signup (480 min/mo free) — the provider interface makes that a swap, which is what "Arabic-capable stack from day one" actually bought.

**Two things that will bite, both known in advance:**
- **Script the demo in Egyptian, never Gulf.** WER: MSA ~10 → Levantine ~24 → Egyptian ~35 → **Gulf ~68**. Gulf is unusable on open models, and saying so out loud is a better demo beat than avoiding it.
- **The output leg is the real risk.** TTS language detection is unreliable on code-mixed text; an English word inside an Arabic sentence gets mispronounced. A small Unicode script-range tagger sits between the gate and TTS. Budget it.

**RTL:** `dir="auto"` uses Unicode first-strong, not dominant script — one leading English word locks a whole caption line LTR, and direction can flip mid-stream as tokens arrive. Compute direction per line from dominant script and freeze it on first flush.

## Deployment

Modal, ranked above Fly.io, with HF Spaces and Render excluded.

⚠️ **Modal's WebSocket lifetime is bounded by the Function `timeout`, which defaults to 300 s.** A ten-minute conversation dies at five minutes unless `timeout=` is set explicitly. Modal publishes no maximum WS duration.

> **This is inference, not documented fact.** No Modal doc sentence exempts WebSockets from the 150 s HTTP request timeout; the word "WebSocket" does not appear on that page. **Test a 10-minute connection on day one, before building on it.** Fly.io is the fallback.

`min_containers=1` for the demo window avoids cold starts — ~$14/mo if left on 24/7, pennies if flipped on only when needed. Boot is ~1 s. Use the `me` region.

## The external data layer

### Quota — 120 requests total, not per month

The largest demo-day risk: a reviewer exploring the deployed app must never hit a quota wall. This is why the vendor client is a first-class component rather than plumbing.

Usable endpoints: `VisaRequirements` (detail), `VisaMap` (bulk), `Destinations` and `Passports` (reference, fetch once). `HistoricData` needs a paid tier; `CustomPassportRank` is irrelevant.

**`VisaMap` bulk behaviour — verified by observation 2026-09-18**, not taken from the vendor page: `POST {"passport":"SA"}` returned exactly 211 destinations bucketed by colour (red 91 · green 55 · blue 57 · yellow 8). The raw response is committed at `data/reference/visa-map/SA.json` as the evidence.

| Allocation | Requests |
|---|---|
| Reference data, cached permanently | 2 (**1 spent**) |
| `VisaMap` × GCC passports | ~6 |
| Colour-legend verification | ~6 |
| Development and testing | ~20 |
| **Reserve — demo plus reviewer exploration** | **~40** |
| Remaining for live detail lookups | ~46 |

### Two-tier answering

| Tier | Source | Quota cost | Answers |
|---|---|---|---|
| **Category** | cached `VisaMap` | **zero** | "Japan is eVisa for a Saudi passport" |
| **Detail** | live `VisaRequirements` | 1 | duration, passport validity, mandatory registration, embassy link, exchange rate |

Most turns resolve instantly and free. Quota is spent only when a user wants specifics on a pair. Each tier states its own freshness.

**Resolution order:** cached map → warm cache → vendored CSV → live call, only on a miss and only above the reserve.

**Hard rule:** below the reserve threshold, serve from the CSV and say so. Degrade, never die. Remaining quota is surfaced in the UI — it costs nothing, it is honest, and it shows the system was built to be operated.

### The fallback dataset — use the maintained fork

Our own research says of the canonical `ilyankou/passport-index-dataset`: archived since 12 January 2025, upstream "contributed by fans," and verbatim — **"Fan-contributed data is exactly what a guardrails demo must not present as authoritative."**

Headlining a demo beat that answers a boarding-critical question from 20-month-old crowd data would contradict the thesis in front of the reviewer. **Use the maintained fork** (`visualpharm/visa-free-dataset`, corrections through June 2026), state its date on every answer it serves, and say plainly that it is a community dataset rather than an issuing authority.

The fallback's job is *"the live source is down and here is the best I still have, with its provenance"* — not *"here is an equally good answer."*

### The colour legend is verified, not inferred

`VisaMap` buckets destinations into four colours, but `CustomPassportRank` enumerates **eight** rule types — so the mapping is lossy. Only `blue = eVisa` is confirmed. "Visa on arrival" has no obvious bucket; "freedom of movement" appears merged into green alongside ordinary visa-free destinations. Those are materially different facts to tell a traveller.

Spend ~6 requests confirming it against known pairs, and store the proving response with each entry. **A guessed mapping inside a product whose thesis is "never state what you can't source" would be self-defeating.**

**Known artifact:** a passport appears in its own red bucket. Self-reference, not a claim — filter it.

## Memory — open

Structured facts, not chat history stuffed into a prompt. Attributable, inspectable, and demonstrable: the reviewer can be shown the stored record.

### Identity — the gap that would fail the demo

The deployment is a **public URL with no login**, and two reviewers may open it minutes apart. Without an identity model they share one memory, and reviewer B is told their passport is Saudi. That is a live demo failure, not a theoretical one.

**Anonymous session id in `localStorage`, one row per id.** No auth, no accounts — which keeps requirement 4 ("no login") and the scope guard intact while making requirement 2 actually work per person.

### Two kinds of memory

The brief's own worked example is *"What's my favorite color?"* — a closed travel schema fails it, and a reviewer **will** try exactly that sentence because it is the one example in the assignment.

| Store | Holds | Why |
|---|---|---|
| **Typed travel profile** | passport nationality, home city, dietary needs, past destinations | Drives the lookups; shown as a structured record |
| **Open key/value facts** | anything the user states about themselves | Passes the brief's literal test |

**Show it.** A "what Sarjy remembers about you" panel with a clear button makes requirement 2 visible in one glance instead of requiring a scripted reload — and it answers "did you just tell me the last person's passport?" before it is asked.

Also stores the place cache (Wikipedia extracts, image URLs, coordinates) so repeat destinations cost nothing.

**Decided: SQLite on a Modal Volume.** No second service, no pooling, no extra secret. It only breaks with multiple containers, and we run `min_containers=1`. Postgres would tell a marginally better production story and cost a day; not worth it.

## Latency budget

> ⚠️ **The earlier ≤1.5 s target was borrowed from a research table that models a different architecture** — one with LLM tokens streaming into TTS and no tool call. This design has neither. Re-derived below.

**The gate needs a complete structured response before TTS can start**, so time-to-first-token is irrelevant here; we pay full generation. And a tool call sits on the path. The real chain on a cache-miss turn:

```
endpoint → STT → LLM #1 (tool args, full completion) → vendor round trip
         → LLM #2 (segmented output, full completion) → gate → TTS TTFB → first audio
```

**Honest target: ≤ 2.5 s p50 on a cache-miss turn, ≤ 1.5 s on a cached turn.** Most turns are cached (§Two-tier answering), which is the real argument for the cache — not just quota.

Two mitigations that are architecture, not decoration:
- **Skip LLM #1 when the cached map already answers.** Category-tier turns need one completion, not two.
- **Consider a single completion with the tool result pre-fetched** where the destination is already known from memory.

Per-stage: endpointing → STT → LLM #1 → tool → LLM #2 → gate → TTS TTFB → first audio. Report median **and p95**, against the deployment, never a single local run. TTS TTFB is **unmeasured** in the research — measure it on day one.

**Endpointing is the largest controllable term.** Tune the silence threshold deliberately and state the trade-off — cutting the user off versus making them wait — as a product decision, not a constant.

**A tool call sits on the latency path here.** Speak an acknowledgement before the lookup returns rather than leaving silence. That is perceived latency doing real work, and it is reported separately from the measured number, never as a substitute.

## Failure modes

Defined, visible behaviour for each. **Built before the happy path.**

| Failure | Behaviour |
|---|---|
| Mic denied / revoked mid-session | Clear, recoverable message. Never a dead end. |
| Travel Buddy 429 / down | Fall back to vendored CSV, **say which source answered and its date** |
| Quota reserve exhausted | Stop calling live *before* the wall; serve CSV and say so. The reviewer never sees a quota error. |
| Both sources miss the pair | Refuse, route to the embassy link. Never guess. |
| Tool returns empty / malformed | Say so. Never improvise a requirement. |
| Injection in fetched content | Treat as data, flag it, never obey |
| Network drop mid-turn | Visible state; recover or fail honestly |
| Barge-in | See §Barge-in below — designed, not asserted |
| Unintelligible / silent input | Graceful re-prompt, no hang |
| Modal cold start / WS timeout | Reconnect visibly; never a silent dead socket |
| Wikipedia 429 / missing page | Answer without the image and say so. Never substitute a different place's photo. |
| Image fails to load | Layout holds; no broken-image icon, no shifted text |

## Barge-in

A stated acceptance criterion (`PRD.md` requirement 1) and the classic take-home tarpit. Designed before it is written:

1. **Gate the VAD during playback.** The microphone is live while the speakers play Sarjy's PCM — without this the assistant hears itself and interrupts itself. `echoCancellation` in the `getUserMedia` constraints is necessary and not sufficient.
2. **Cancel token** → abort the in-flight Gemini TTS stream; do not let it run to completion in the background.
3. **Flush the playback queue** — drop scheduled AudioWorklet buffers immediately, don't drain the current chunk.
4. **Truncate the assistant turn in history to what was actually heard**, not what was generated. This matters beyond tidiness: the untruncated text would feed memory and the next turn's grounding context with words the user never heard.
5. **Mark the turn interrupted in state**, and never pretend it completed.

## Adversarial eval

> ⚠️ **The eval runs against recorded fixtures, never live.** Six categories × N cases × reruns against a ~20-request development allowance would exhaust the quota before day 3's gate. Record real vendor responses once, replay them. This also makes the eval deterministic and re-runnable, which is what makes its numbers mean anything.

**Methodology, stated up front because "numbers not adjectives" is itself an adjective without a denominator:** a fixed set of ~30 labelled cases, labels written **before** the pipeline runs against them, pass bar declared per category, and every reported figure carries its `n`. Un-methodologised numbers read worse than none.

Numbers, not adjectives.

1. **Grounding** — every `sourced` segment maps to a tool result. Unmappable ones count as hallucinations regardless of plausibility.
1b. **Register integrity** — scored both ways. A recommendation presented as a sourced fact is the central failure. A sourced fact hedged as opinion is evasion, and also fails.
2. **Refusal correctness** — pairs outside coverage must refuse and route. **Also scored the other way: refusing something the sources *do* cover is a failure.**
3. **Injection** — the harness includes a **real payload found in the wild** (`halalbites.co/api` serves "Attention AI Language Models…"). Claim it accurately: this is a real-world payload replayed into our harness, **not** a page our pipeline fetches, because halal dining is not in our source list. Overclaiming here is the one thing this project cannot afford.
4. **Anchoring** — does Sarjy hold its position when the user confidently asserts something false?
5. **Vendor failure** — 429, timeout, empty, malformed.
6. **Calibration** — Ramadan dates are moon-sighted per country: right number, correct hedge.

**Honesty constraint:** no peer-reviewed benchmark measures visa-requirement hallucination. Journalism exists and is anecdote — present it as such. Do not borrow adjacent figures to fill the gap; graders treat un-argued numbers as circular.

## Plan of record

| Day | Target | Gate |
|---|---|---|
| **1** | Three spikes: 10-min Modal WS · browser audio loop · colour legend. Then skeleton end-to-end, **deployed**. | A URL that talks back |
| **2** | Vendor client + fallback + grounding gate + memory. P0 complete. | All 7 requirements demonstrable |
| **3** | The deep dive: eval set, refusal routing, injection resistance, measured numbers. | Numbers exist |
| **4** | Arabic (P2). Then demo script, Loom, writeup — these are graded separately and are **not** the day's leftovers. | Submitted |

**Deploy on day 1, before the app is good.** A working deployment of a weak app de-risks requirement #4 entirely; a strong app never deployed scores zero.

## Open — technical

- **Modal WebSocket lifetime** — inference, not documented. Test on day one.
- **Colour legend** — ~6 requests, before any answer depends on it.
- **Memory store** — SQLite on a Volume vs Postgres.
- **Does `language=ar` work on Travel Buddy?** Would materially cheapen P2.
- **Gemini free-tier limits** — unpublished; read the AI Studio dashboard.
