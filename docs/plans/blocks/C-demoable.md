# Block C — Demoable

**Date:** 2026-09-21 · **Needs:** Block B · **Lands:** requirement #6 (presentation) and finishes
requirement #1 (voice) · **Deadline: today, 19:00**

**The last block.** Everything after this is recording, committing and submitting.

---

## Goal

A stranger can open `https://vitas7777v--sarjy-fastapi-app.us-east.modal.run`, understand what
Sarjy is within five seconds, have a grounded conversation whose evidence is visible on screen, and
— separately — a reviewer who never opens the URL can read one README and watch one Loom and know
exactly what was built, what works, and what does not.

---

## Decisions — read this page, then the block runs

### D1 — The clock is the design. These times are pre-committed, not aspirational

It is 2026-09-21. Submission closes at **19:00**. Omar still has to sleep, run the human browser
gates that Blocks A and B both left open, record a Loom, and submit through Ashby.

Master-plan estimates on this project have run **~2.5× low** once planned in detail. This plan
assumes the same and is scoped to roughly **4 hours of build time**, not a day.

| Clock | What happens | Hard? |
|---|---|---|
| 09:00–09:20 | **Preflight (human).** Deploy is live · `SARJY_MEMORY_SALT` set on Modal · `QUOTA_SPENT_SEED` set from the RapidAPI dashboard · one voice turn works | — |
| 09:20–10:00 | **Group 1** — the fact card renders | — |
| 10:00–10:25 | **Group 2** — the minimum stylesheet | — |
| 10:25–11:45 | **Group 3** — README, demo script, Loom outline, written against what is true *right now* | — |
| 11:45–13:00 | **Group 4** — Arabic. Rung 1, then rung 2 | 🚨 **STOP at 13:00 wherever it is** |
| 13:00–13:20 | **Group 5** — amend the three documents to match what actually shipped | — |
| **14:00** | 🚨 **CODE FREEZE.** Nothing but doc edits and blocker fixes after this | 🚨 |
| 14:00–15:30 | Human gates: `/demo-check`, Block A's 9-row table, Block B's 9-step table, one `make measure` run | — |
| 15:30–16:00 | `submission-reviewer` agent. Fix **blocking** findings only | — |
| **16:00** | 🚨 **Loom recording starts** regardless of state | 🚨 |
| 17:00–18:00 | Commit, push, repo access to the reviewer, Ashby | — |
| 18:00–19:00 | Reserve | — |

### D2 — The ranking, and where this plan disagrees with its brief

| Rank | Item | Status |
|---|---|---|
| 1 | **README · demo script · Loom outline** | **Never cut.** They *are* requirement #6 |
| 2 | **The fact card renders** | Near-never cut. The deep dive's only visible surface; Block A already put `fact_card` on the wire and nothing paints it |
| 3 | **A minimum stylesheet** (~20 min) | **Promoted into the never-cut tier — a deviation from the brief, argued below** |
| 4 | **Arabic** | Promised to Sarj in writing. Two rungs (D5); rung 1 is ~15 min |
| 5 | The UI *pass* (polish beyond the stylesheet) | First to cut |
| 6 | The canned opener clip | **Cut now, before starting** (D8) |

**The deviation.** `frontend/` contains **no stylesheet of any kind** — no `.css` file anywhere,
no CSS-in-JS, nothing. `App.tsx` renders bare `<h1>`, `<p>`, `<ul>`, `<button>` against browser
defaults. Every screenshot in the Loom, and the reviewer's first five seconds, is Times New Roman
on white with an unstyled bulleted list of gate segments.

The rubric asks *"Is the UI delightful?"* by name. Twenty minutes of one flat stylesheet moves that
line further than any other twenty minutes available in this block, and it moves the Loom — which
is what most of the reviewing actually happens against — more than Arabic does. So a **single
`frontend/src/index.css`, ~120 lines, no new dependency, no component restructuring** is treated as
never-cut. The *UI pass* (transitions, a waveform, a layout rework) stays first-to-cut and is
explicitly out of scope.

### D3 — The cut ladder, with the clock time each rung fires

| Rung | Fires at | Cut | What the README then says |
|---|---|---|---|
| 0 | now | The canned opener clip | Nothing — it was already cut in the master plan |
| 1 | 13:20 | The UI pass (anything past `index.css`) | Nothing — `index.css` is the UI pass we claim |
| 2 | **13:00** | Arabic rung 2 (spoken Arabic) | *"Sarjy understands spoken Arabic and answers in English. Arabic voice output is not shipped — Deepgram Aura-2 has no Arabic voice, and the Arabic alternative (Groq Orpheus) caps a request at 200 characters and 100 requests/day, which does not survive a conversation. See §What I'd do with another week."* |
| 3 | **11:45** | Arabic entirely, if groups 1–3 are not done | *"Bilingual English/Arabic was scoped and not built. The STT and TTS interfaces both already carry a `language` parameter; nothing implements it. This is the single biggest gap between what was promised and what shipped, and it is named here rather than omitted."* |
| 4 | 15:00 | Any un-run human gate | The README's §Verified / §Not verified table carries it — see D4 |

**Rungs 2 and 3 have their README sentence written in advance, in this plan, deliberately.** At
13:00 nobody is in a state to write an honest sentence about their own unfinished work. It is
already written; paste it.

### D4 — The README states unproven claims as unproven. It never omits them

Several things in this codebase are built and tested but have **never been exercised by a human**,
and at least one — the live Travel Buddy call with real quota — may still be unexercised at
submission (`PR_GROUNDED_ANSWERS.md` §Gate status: "Zero spent").

The rule for this block: **an unproven claim is stated with its limit attached, in the same
sentence.** It is never dropped, and it is never softened into the present tense.

Concretely, the README carries a table with exactly three columns and no fourth:

| Capability | Verified how | Limit |
|---|---|---|

- *Verified how* is one of: **live, by hand** · **live, scripted** · **unit tests only** ·
  **not run**.
- A row whose *Verified how* is "unit tests only" or "not run" **must** have a non-empty *Limit*.
- No row is deleted because it looks bad. A "not run" row costs less than a reviewer finding it.

This is the graded behaviour. The brief's own deep-dive text asks what *"didn't"* work, by name.

### D5 — Arabic ships in two rungs, and rung 1 is worth having on its own

**Rung 1 — Sarjy *understands* Arabic. ~15 minutes.**
A language toggle in the UI → `lang` on the `start` message → `stt.transcribe(pcm16, language="ar")`
→ one line in the user block telling the model the user spoke Arabic and to answer in English.
Answer text and voice stay English. For a Gulf traveller this is a real, defensible product
behaviour, not a stub.

**Rung 2 — Sarjy *speaks* Arabic. ~60 minutes, and genuinely risky.**
Deepgram Aura-2 has **no Arabic voice** — verified 2026-09-21, Aura-2 covers English, Spanish,
Dutch, French, German, Italian, Japanese only ([Deepgram voices &
languages](https://developers.deepgram.com/docs/tts-models)). So Arabic needs a second TTS
provider, and the decided one is Groq Orpheus.

🪤 **Every one of these is a trap that will cost the implementer time if it is discovered at
12:30 instead of read here.** Verified 2026-09-21 against
[console.groq.com/docs/text-to-speech/orpheus](https://console.groq.com/docs/text-to-speech/orpheus):

| Fact | Consequence |
|---|---|
| **200 characters maximum per request** | The answer must be chunked. `quoted` segments alone are allowed 400 chars (Q5) — the collision `PR_GROUNDED_ANSWERS.md` flagged for this block |
| **`response_format` accepts `"wav"` only** | The playback path expects raw PCM s16le. The adapter must strip the RIFF header |
| **Streaming is not documented** | It is a batch call. `tts_ttfb_ms` for Arabic is full synthesis time, and chunks are sequential. An Arabic turn will be visibly slower. **Measure it, quote it, do not hide it** |
| **Free tier: 10 RPM / 100 RPD / 1 200 TPM** | A 400-char answer is 2 requests. ~50 Arabic turns per day for the whole org, and 10 RPM will 429 you mid-conversation. **Arabic is a demo-able turn, not a mode** — say exactly that in the README |
| **Listed under Preview Models** | It can change under us. Not a reason to skip it; a reason to name it |
| Endpoint | `https://api.groq.com/openai/v1/audio/speech`, OpenAI-compatible. The `groq` SDK is **already a dependency** (`GroqSTT` uses `AsyncGroq`) and `GROQ_API_KEY` is **already configured**. No new secret, no new package |
| Arabic voices | `Abdullah`, `Fahad`, `Sultan`, `Lulwa`, `Noura`, `Aisha`. Pick one, put it in `config.py`, say why in a comment |
| Vocal directions (`[cheerful]`) | **English model only.** Never emit a bracketed direction on the Arabic path |

**AR-0 is a 5-minute probe and it runs before any adapter code is written** — see the task list.
If the probe says the WAV is not 24 kHz mono 16-bit, rung 2 is cut on the spot and rung 1 ships.

### D6 — Language routes inside the TTS boundary, not through the factory signature

`TTS.synthesize(text, *, language: str | None = None)` **already has the parameter** (`base.py`);
nothing implements it and `turn.py` hardcodes `language=None` at both call sites.

`factory.get_tts()` stays **zero-argument** and returns a small `RoutedTTS` that holds both adapters
and dispatches on `language`. It does not become `get_tts(lang)`.

**Why:** `get_tts` is typed `Callable[[], TTS]` through `run_turn`'s signature, `main.py`'s
pass-through, and every fake in `test_turn.py` / `test_ws.py`. Changing its arity is ~12 mechanical
edits across Block A's and Block B's test contracts, at 12:00 on deadline day, for no behavioural
gain. The router is one class, one dispatch line, and one sentence to explain out loud: *"Deepgram
has no Arabic voice, so the TTS boundary picks the voice from the language the turn is in."*

**The cost, named:** `timings.tts_model` will read the router's composite string rather than the
voice that actually spoke. Closed by adding `TurnTimings.lang: str = "en"` — the pair
(`tts_model`, `lang`) is unambiguous, and `lang` is a field `measure.py` wants anyway.

### D7 — `PROTOCOL_VERSION` is **not** bumped

`main.py:881` does a strict `hello.v != PROTOCOL_VERSION` equality check and hard-closes the socket
with `recoverable=False` on mismatch. A bump on deadline day adds a hard-failure mode for any client
holding a stale bundle and buys nothing here, because **`lang` is an additive optional field with a
default** — an old client omitting it and a new server reading it are wire-compatible in both
directions.

Stays at **5**. Record the additive change in `protocol.py`'s module docstring instead. If a future
block removes or retypes a field, that one bumps.

### D8 — The canned opener clip is cut now, and the README says what replaced it

The master plan's opener story has already moved twice: the `update()` opener was cut, and a
pre-recorded clip was to cover the lookup. That clip is cut too, at rung 0, before this block
starts. It is a recording session, an asset pipeline, a playback-queue interaction with barge-in,
and a new failure mode ("the clip plays over the answer") for a perceived-latency win that
`state: thinking` already half-delivers.

What the README says instead: the visible state machine flips to `thinking` within one round trip,
the fact card paints **before call 2 starts** (Block A's send-order contract), so the reviewer is
reading real data while the answer is still being written. That is the honest perceived-latency
story and it is already built.

### D9 — The deep dive's fallback layer cannot be demonstrated live, and the demo script says so

Block A's gate line reads *"pulling the network still answers correctly and names which layer served
it."* There is **no live affordance for this.** `SARJY_FAKE_VENDOR=1` is an environment variable
(redeploy), and `TravelBuddyTool.lookup()` has no per-call layer override — adding one means a new
keyword on the `VisaTool` Protocol, `FakeVisaTool`, and their tests.

**That is scope-out.** The demo script proves the fallback with the artefacts that already exist:
the fact card's own `layer` badge (which reads `map` or `csv` whenever live misses), the eval's
`vendor-failure-1` case, and `tests/test_vendor.py`. A one-click *"pretend the vendor is down"*
toggle goes in §What I'd do with another week — where it reads as a considered omission rather
than a hole.

---

## Scope

### In

1. **`fact_card` renders** — the card, the refusal card, the degraded badge, and the stale-card fix.
2. **`frontend/src/index.css`** — one flat stylesheet, ~120 lines, no dependency.
3. **`README.md`, rewritten** — currently describes a stack that no longer exists (D-upstream-1).
4. **`docs/DEMO-SCRIPT.md`** — the ordered utterance list.
5. **`docs/LOOM-OUTLINE.md`** — a 5-minute shot list with timings.
6. **Arabic rung 1** — toggle → `lang` on `start` → Whisper `language="ar"` → one prompt line.
7. **Arabic rung 2** — `GroqOrpheusTTS`, the 200-char chunker, WAV→PCM, `RoutedTTS`. Timeboxed.
8. **`docs/PRs/PR_DEMOABLE.md`** — per `.claude/rules/workflow.md` phase 5.

### Out — do not expand into these

- **Any new external API, any new dependency, any new secret.** Arabic reuses `GROQ_API_KEY`.
- **Spending RapidAPI quota.** The ledger is locked and its real spent count is unresolved. No task
  here fires a live vendor request. `scripts/fetch_reference.py` is Omar's to run, or not.
- **`?force_layer=` or any live fallback toggle** (D9).
- **Arabic code-switching, RTL layout beyond `dir="rtl"` on the transcript line, an Arabic UI.**
  Master plan overflow rung 3 already cut this: *"Keep the bare Arabic turn. Name the gap out loud."*
- **Widening the gate for Arabic.** `NUMBER_WORDS` and the `wrong_pair` place-name list are both
  English-only. Making them bilingual is a change to Block A's contract on deadline day. It is a
  **named limit in the README**, not a task (F-AR4).
- **The canned opener clip** (D8).
- **Any UI work past `index.css`** — no animation, no avatar, no waveform, no component library.
- **Re-running the eval**, re-measuring anything already measured, or touching `eval/`.
- **`git add` / `git commit` / `git push` / any `gh` write.** Agents draft messages. Omar commits.

---

## Files

| File | Purpose |
|---|---|
| `frontend/src/ui/FactCard.tsx` | **New.** The card component. `ui/` already exists and is empty — it was scaffolded for this |
| `frontend/src/index.css` | **New.** The only stylesheet. Imported once, from `main.tsx` |
| `frontend/src/App.tsx` | Renders `<FactCard>`; clears the card on turn start (F-FC4); the language toggle; `dir` on the transcript/reply/segments |
| `frontend/src/main.tsx` | One line: `import "./index.css";` |
| `frontend/src/protocol.ts` | `lang` on the start message; `Lang` type |
| `frontend/src/net/connection.ts` | `startTurn(turnId, lang)` |
| `backend/app/pipeline/protocol.py` | `StartIn.lang: Lang = "en"`; module docstring notes the additive change (D7) |
| `backend/app/pipeline/turn.py` | `run_turn(..., lang)`; `_speak(..., lang)`; `language=lang` at both provider call sites; deterministic phrases pinned to `"en"` (F-AR5) |
| `backend/app/pipeline/timings.py` | `lang: str = "en"` |
| `backend/app/main.py` | Reads `msg.lang`, passes it to `run_turn` |
| `backend/app/prompts.py` | `build_user_block(..., lang)` → the `<reply_language>` block |
| `backend/app/providers/groq_tts.py` | **New.** `GroqOrpheusTTS` — chunker, WAV→PCM, the rate assertion |
| `backend/app/providers/factory.py` | `RoutedTTS` |
| `backend/app/providers/base.py` | Docstring only: what `language` now means |
| `backend/app/config.py` | `groq_tts_model`, `groq_tts_voice` |
| `backend/app/measure.py` | `lang` in the record fields |
| `backend/tests/test_groq_tts.py` | **New.** Chunking + WAV parsing + the rate assertion. No network |
| `backend/tests/test_turn.py`, `test_ws.py`, `test_protocol.py` | `lang` threading |
| `README.md` | **Rewritten.** The front door |
| `docs/DEMO-SCRIPT.md` | **New.** Ordered utterances |
| `docs/LOOM-OUTLINE.md` | **New.** The 5-minute shot list |
| `docs/PRs/PR_DEMOABLE.md` | **New.** Summary · Problem · Solution · Changes · How to Test · Changelog |
| `scratch/spikes/orpheus_probe.py` | **New, not committed.** AR-0's 5-minute probe |

---

## Contracts

### 1 — The fact card, already on the wire (`frontend/src/protocol.ts`, unchanged)

Copy these field names exactly. They are what Block A emits.

```ts
export interface FactRowWire {
  path: string;        // "visa.duration" — the same path the gate substitutes from
  label: string;       // "Maximum stay"
  value: string;       // the SAME string the gate would have substituted
  kind: "sourced" | "quoted";
}

export interface FactCardMessage {
  t: "fact_card";
  turn_id: string;
  passport: string;            // "SA"
  passport_name: string;       // "Saudi Arabia"
  destination: string;         // "JP"
  destination_name: string;    // "Japan"
  covered: boolean;            // false = pair resolved, no layer had it → the refusal card
  facts: FactRowWire[];
  layer: ToolLayer | null;     // "cache" | "live" | "map" | "csv"
  degraded: boolean;           // layer in {map, csv}
  source_name: string | null;
  source_url: string | null;
  source_date: string | null;  // the SOURCE's own date, never ours
  retrieved: string | null;    // ours, ISO 8601 Z
  embassy_url: string | null;  // the refusal route
  seq: number;
  ts_ms: number;
}
```

### 2 — `FactCard.tsx`

```tsx
export function FactCard({ card }: { card: FactCardMessage }): JSX.Element
```

Renders exactly three shapes, chosen in this order:

1. **`covered === false`** → the refusal card. Header `{passport_name} → {destination_name}`, the
   line *"No source covers this pair."*, and — when `embassy_url` is non-null — an
   `<a target="_blank" rel="noreferrer">` to it labelled *"Embassy page"*. **Never an empty box.**
2. **`covered === true` and `facts.length === 0`** → header plus the provenance footer, plus
   *"Nothing to show for this pair."* Reachable when no `LABELS` path is present on this layer.
3. **`covered === true` and `facts.length > 0`** → header, one `<li>` per fact
   (`{label} — {value}` plus a `kind` badge whose class matches the existing segment badge), then
   the provenance footer.

Provenance footer, in this order, omitting any null: `{source_name}` · `{source_date}` ·
`retrieved {retrieved}` · `{layer}`. When `degraded === true`, prepend a visible
`<span className="card-degraded">` reading **"fallback source"**.

`source_url` wraps `source_name` as a link when non-null.

### 3 — Wire: `lang`

```python
# backend/app/pipeline/protocol.py
Lang = Literal["en", "ar"]

class StartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t: Literal["start"]
    turn_id: str
    client_ts_ms: int
    lang: Lang = "en"      # additive, defaulted. PROTOCOL_VERSION stays 5 (D7)
```

```ts
// frontend/src/protocol.ts
export type Lang = "en" | "ar";
// connection.ts
startTurn(turnId: string, lang: Lang = "en"): void
//   → this.send({ t: "start", turn_id: turnId, client_ts_ms: Date.now(), lang })
```

### 4 — The turn

```python
async def run_turn(*, ..., lang: str = "en") -> AsyncIterator[TurnItem]: ...

async def _speak(text, turn_id, get_tts, failed, next_seq, now_ms, timings, *, lang: str) -> ...
```

- `turn.py:223` — `await stt.transcribe(pcm16, language=lang)` (was `language=None`).
- `turn.py:537` — `tts.synthesize(text, language=lang)` (was `language=None`).
- `timings.lang = lang`, set next to `timings.stt_model`.
- **Every deterministic fixed-phrase call site passes `lang="en"` explicitly** — the sign-in
  sub-flow, the `NO_COVERAGE` refusal, the gate's rejection phrase (F-AR5).

### 5 — The Arabic prompt line (`backend/app/prompts.py`)

`build_user_block(..., lang: str = "en")` appends this block, and **only** when `lang == "ar"`:

```
<reply_language>
The user is speaking Arabic. Write every segment's `text` in Arabic.
Field placeholders such as {visa.duration} must be copied EXACTLY as written, in Latin
characters, with their braces — never translated, never transliterated, never reformatted.
Keep each segment under 25 words.
</reply_language>
```

🪤 **The second sentence is load-bearing.** If the model translates a placeholder or its braces,
`PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_.]+)\}")` matches nothing, the `placeholder` rule fires,
and **every sourced segment in the turn is rejected**. The failure looks like "the gate is broken in
Arabic"; it is the prompt.

The third sentence is the 200-char cap pushed upstream: short segments mean fewer Orpheus requests.

### 6 — `GroqOrpheusTTS` (`backend/app/providers/groq_tts.py`)

```python
MODEL = "canopylabs/orpheus-arabic-saudi"
MAX_CHARS = 200          # Groq's hard per-request cap, not a tuning knob
EXPECTED_SAMPLE_RATE = 24_000

class GroqOrpheusTTS:
    model: str
    def __init__(self, api_key: str, model: str, voice: str) -> None: ...
    async def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        ...

def chunk_for_orpheus(text: str, limit: int = MAX_CHARS) -> list[str]: ...
def wav_to_pcm16(wav: bytes) -> tuple[bytes, int]: ...   # (pcm_s16le, sample_rate_hz)
```

- `chunk_for_orpheus` splits on sentence terminators first (`.`, `؟`, `!`, `۔`, `؛`, newline),
  packing greedily up to `limit`. A single sentence longer than `limit` splits at the **last space
  at or before `limit`**; a run with no space at all hard-splits at `limit`. It **never returns a
  chunk longer than `limit`** and **never drops a character** — both are asserted in tests.
- `wav_to_pcm16` reads the RIFF/`fmt `/`data` chunks, returns the `data` payload and the header's
  sample rate. It raises `RuntimeError` on a non-RIFF body, on non-PCM format, on channels ≠ 1, and
  on bits-per-sample ≠ 16 — each with the observed value in the message.
- `synthesize` calls `client.audio.speech.create(model=..., voice=..., input=chunk,
  response_format="wav")` **once per chunk, sequentially**, and yields each chunk's PCM. If the
  first chunk's sample rate ≠ `EXPECTED_SAMPLE_RATE` it raises `RuntimeError` naming both numbers
  (F-AR3).
- Timeout and retries are **explicit**, never the SDK default — same rule `GroqSTT` follows
  (`max_retries=1`, `timeout=8.0`). Copy those constants.
- `language` is accepted and ignored: this adapter *is* the Arabic branch. Say so in a comment.

### 7 — `RoutedTTS` (`backend/app/providers/factory.py`)

```python
class RoutedTTS:
    """Deepgram Aura-2 has no Arabic voice (verified 2026-09-21), so the TTS
    boundary picks the voice from the language the turn is in. `TTS.synthesize`
    always carried `language`; this is the first thing to implement it."""
    model: str  # "routed(en=<deepgram model>, ar=<orpheus model>)" — see D6 on why, and `TurnTimings.lang`

    def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        return (self._ar if language == "ar" else self._en).synthesize(text, language=language)
```

`get_tts()` keeps `@functools.lru_cache(maxsize=1)` and its zero-argument signature.

---

## Failure paths — build these before the happy path they protect

| # | Failure | Visible behaviour |
|---|---|---|
| **F-FC1** | `covered === false` | The refusal card: the pair, *"No source covers this pair."*, and the embassy link when known. **Never an empty box, never a blank card area** |
| **F-FC2** | `degraded === true` | A **"fallback source"** badge next to the layer name. A degraded answer must never look identical to a live one — this is the visible half of Invariant 7 |
| **F-FC3** | `covered === true`, `facts === []` | Header + provenance footer + *"Nothing to show for this pair."* No empty `<ul>` |
| **F-FC4** | A new turn starts while last turn's card is on screen | The card is cleared in `handleUtterance`, in the same block as `setSegments([])` (App.tsx ~line 232). **`setFactCard(null)` is missing there today — this is a live bug, not a hypothetical.** A card describing Japan must never sit under an answer about Thailand |
| **F-FC5** | `source_url` / `embassy_url` present | `target="_blank" rel="noreferrer"`. A demo that navigates away from the WebSocket mid-turn kills the turn |
| **F-CSS1** | A long transcript, a 400-char `quoted` segment, or a 10-row card | No horizontal scroll, no overlap, nothing pushed off-screen at 1280×800 — the Loom's frame |
| **F-AR1** | Arabic answer > 200 chars | `chunk_for_orpheus` splits it. Sequential requests, concatenated PCM, one `audio_start`/`audio_end` pair for the whole turn. **Never truncate** |
| **F-AR2** | Groq 429 (10 RPM) part-way through the chunks | If audio already started: emit `audio_end` for what played, then `turn_failed("tts", "My Arabic voice hit its rate limit partway through — the answer above is still correct.")`. If not: `turn_failed("tts", "The Arabic voice is rate-limited right now. Switch to English and try again.")`. `_speak`'s existing `audio_started` branch already has this shape — reuse it, do not write a second one |
| **F-AR3** | Orpheus returns a WAV that is not 24 kHz mono 16-bit | `RuntimeError` naming the observed value → `turn_failed` with a legible message. **Never** stream it at the wrong rate — that plays as pitch-shifted noise and looks like a broken app |
| **F-AR4** | A fabricated Arabic number in a `sourced` segment | ⚠️ **Passes.** `_NUMBER_WORD_RE` is English-only and `wrong_pair`'s place-name scan reads English names from `destinations.json`. `DIGIT_RE = re.compile(r"\d")` **does** catch Arabic-Indic digits (gate.py:51 says so) — so numerals are caught, number *words* and wrong-country names are not. **This is a named limit, not a bug to fix here** (scope out). It goes in the README's limits table and in §What I'd do with another week, and the demo script's Arabic turn does **not** claim gate coverage |
| **F-AR5** | A deterministic fixed phrase fires during an Arabic turn | The seven fixed phrases are English strings. They are spoken by the **English** voice — every deterministic call site passes `lang="en"`. An Arabic voice reading English text is the worst possible demo artefact |
| **F-AR6** | The user toggles to Arabic and speaks English | Whisper with `language="ar"` will mistranscribe or translate. Accepted and user-driven. The toggle's label is the affordance; no code |
| **F-AR7** | The model translates a placeholder (`{مدة_التأشيرة}`) | Every sourced segment is rejected for `placeholder` and the turn hedges. Mitigated by Contract 5's second sentence. If it is still seen during verification, **cut to rung 1** rather than debugging a prompt at 13:00 |

---

## Task list

Ordered. Each item is independently checkable.

### Group 0 — Preflight (human, 09:00)

1. Open the deployed URL. Confirm it loads, the socket connects, and **one voice turn works** before
   any code is touched. If it does not, that is the whole morning — stop and fix it.
2. Confirm `SARJY_MEMORY_SALT` is set on the Modal deployment (`PR_MEMORY.md` asks for this by
   name; unset, it silently defaults to `"sarjy-dev-salt"`).
3. Check the RapidAPI dashboard's real spent count and set `QUOTA_SPENT_SEED` to it. ⚠️ The default
   is **120** (the whole budget), which means an unseeded deployment **never fires a live request**
   and every visa answer is served degraded from the CSV. Getting this wrong makes the demo look
   broken in a way that is hard to diagnose live.

### Group 1 — The fact card (09:20, ~40 min)

4. **F-FC4 first.** Add `setFactCard(null)` to `handleUtterance`'s reset block, beside
   `setSegments([])`. Change `const [, setFactCard]` to `const [factCard, setFactCard]`.
5. Write `FactCard.tsx` handling **F-FC1 (refusal) and F-FC3 (empty) before** the populated case.
6. Add F-FC2's degraded badge and F-FC5's link attributes.
7. Render `{factCard && <FactCard card={factCard} />}` in `App.tsx`, **above** the segment list — the
   card is the evidence, the segments are the audit trail of the sentence built from it.
8. `npm run typecheck && npm run lint && npm run build`.

### Group 2 — The stylesheet (10:00, ~25 min, hard 25)

9. `frontend/src/index.css` + `import "./index.css";` in `main.tsx`. One flat file. No framework,
   no dependency, no component restructuring, no CSS modules.
10. Cover, and nothing else: a page container capped around 760 px with real padding · a legible
    system font stack · one dark surface and one accent · the four conversation states as four
    distinguishable colours on `.conversation-state` · `.segment-rejected` unmistakably struck and
    dimmed · `.segment-kind` / card `kind` badges as small pills · the fact card as a bordered
    panel with a visually distinct `.card-degraded` badge · the memory panel as a sidebar or a
    second panel · buttons that look like buttons · `.metrics` and `.status-line` small and
    monospace.
11. **F-CSS1** at 1280×800: a long transcript, a 400-char quoted segment, a 10-row card. No
    horizontal scroll, nothing clipped.

### Group 3 — The three documents (10:25, ~80 min) — **NEVER CUT**

12. **`README.md`, rewritten.** It is currently wrong in four separate ways (see §What I found
    upstream). Sections, in order:
    - One-paragraph what-and-why, then the **live URL** — not `_TBD_`.
    - **What a reviewer should do in 90 seconds** — three utterances, lifted from the demo script.
    - **The deep dive**: three registers, the nine `sourced` rules, value-level substitution, the
      `?gate_demo=1` affordance, the eval's headline (**7/8, with `injection-2` a labelled,
      predicted failure**) and a link to `eval/results/2026-09-20-gate-eval.md`.
    - **The external API, and why this one** — keep the existing justification paragraph; it is
      good. **Delete GOV.UK and Aladhan from "supporting sources"** — they were excluded
      (`AGENTS.md` §Decided).
    - **How it works** — keep the pipeline diagram and the cascaded-vs-speech-to-speech paragraph;
      both are still exactly true and both are strong.
    - **Measured latency**, from `docs/measurements/2026-09-20-two-corrected-numbers.md`:
      `upload 1195 ms · stt 149 ms · llm_ttft 890 ms · tts_ttfb 566 ms · server 1822 ms`. Quote the
      caveat in the same breath — **scripted from a sandbox, not a browser; `endpoint_ms` and
      `first_audio_ms` are null because a script has no VAD and no speaker.** Include the story that
      two of these numbers were wrong and got corrected; it is the best evidence in the repo that
      the measurement is real.
    - **§Verified / §Not verified**, the three-column table from D4. Populate it from
      `PR_GROUNDED_ANSWERS.md` §Gate status and `PR_MEMORY.md` §Not run here, plus whatever Group 6
      actually lands. The live vendor row is **"not run"** until Omar runs it.
    - **§What I'd do with another week.** Minimum five entries, each one sentence of what and one of
      why: (a) speech-to-speech is off the table while the gate needs a text checkpoint — here is
      the latency that costs, measured; (b) the paraphrased injection (`injection-2`) still gets
      through, by design and by admission; (c) `judgement` is ungated by design — the honest
      boundary of the claim; (d) `NUMBER_WORDS` and `wrong_pair` are English-only, so the Arabic
      register is weaker than the English one; (e) a one-click *"pretend the vendor is down"*
      toggle, because the fallback currently has no live demo (D9); (f) `sourced`-as-hedge is not
      gate-enforceable and only a weak proxy exists.
    - **Stack table** — `aura-2-thalia-en`, **not** `gemini-3.1-flash-tts-preview`.
    - **Status** — every box reflecting reality on the day.
13. **`docs/DEMO-SCRIPT.md`.** An ordered table: **Say this · What should happen · Proves**. Exactly
    this sequence (Arabic line added by task 24, or replaced by rung 2's README sentence):

    | # | Say / do | Should happen | Proves |
    |---|---|---|---|
    | 0 | Open the URL cold. Click **Start talking**, allow the mic | State reads `idle` → `Listening for you…` | #4, #1 |
    | 1 | Type name + PIN in the panel, **Sign in** | Panel reads *"Signed in as …"* | #2 setup |
    | 2 | *"I'm travelling on a Saudi passport and my favourite colour is green."* | Panel gains two facts, each with the **verbatim sentence that taught it** and a timestamp | #2, Invariant 4 |
    | 3 | *"Do I need a visa for Japan?"* | Spoken answer · a `sourced` segment per claim with citation, layer and date · **the fact card paints with the same values** · the quota chip decrements | #1, #3, #5 |
    | 4 | **Hard reload** (⌘⇧R). Sign back in with the same name + PIN. *"What's my favourite colour?"* | *"Green"* — and the panel shows the **original** `learned_at`, not a new one | **#2, the graded one** |
    | 5 | Reload with `?gate_demo=1`. Ask #3 again | One extra segment appears **struck through with its rejection reason**. The spoken answer does not contain it | **#5 — the deep dive, live** |
    | 6 | *"Do I need a visa for Wakanda?"* (or any uncovered pair) | *"I don't have a source for that"* + the embassy link, on screen and in the card. **No invented answer** | Invariant 6 |
    | 7 | Barge in: start a question, then interrupt mid-answer | Audio stops immediately, state returns to `listening` | #1, Invariant 7 |
    | 8 | Toggle to **العربية**, ask a visa question in Arabic | *(rung 2)* answer spoken in Arabic · *(rung 1)* Arabic understood, answered in English | #1, the bilingual promise |

    Each row also carries **"if this breaks, say ___"** — one honest sentence Omar can use live,
    because the reviewer is watching either way. Row 5 additionally carries the sentence that makes
    the demo: *"the model wrote that number; deterministic code refused to let it be spoken."*
14. **`docs/LOOM-OUTLINE.md`** — a **5-minute** shot list with per-section timings:
    - 0:00–0:20 what Sarjy is, in one sentence, and the live URL on screen.
    - 0:20–1:40 demo script rows 0–4, real-time, no cuts.
    - 1:40–3:00 **the deep dive** — row 5, then one screen of `gate.py`'s nine `sourced` rules.
    - 3:00–3:45 row 6 (refusal + embassy), and the honest sentence about the fallback layer having
      no live demo (D9).
    - 3:45–4:20 the measured latency slide, **including that two numbers were wrong and corrected**.
    - 4:20–5:00 §What I'd do with another week — the brief asks for it by name.
    - Then: recording notes (one browser, one tab, mic tested, quota checked, `?gate_demo=1` opened
      in a second tab in advance) and **what to do if a turn fails on camera: keep rolling and say
      what happened.** A recovered failure is better evidence than a clean take.

### Group 4 — Arabic (11:45, 🚨 **stop at 13:00**)

15. **AR-0, the probe. 5 minutes, before any adapter code.** `scratch/spikes/orpheus_probe.py`
    (not committed): one `AsyncGroq.audio.speech.create` call, ~20 Arabic characters,
    `response_format="wav"`. Print: the response object's type and how the bytes come off it
    (`.read()` / `.content` / `.write_to_file`), the first 4 bytes, and the header's sample rate,
    channels and bits-per-sample. **If it is not 24 000 / 1 / 16, cut to rung 1 now.** Record the
    outcome in `docs/PRs/PR_DEMOABLE.md` either way — a five-minute probe that kills a feature is a
    good outcome, not a wasted one.
16. **Rung 1.** `StartIn.lang` (Contract 3) · `run_turn(..., lang)` and `_speak(..., lang)`
    (Contract 4) · `timings.lang` · `main.py` passes `msg.lang` · **F-AR5 first**: pin every
    deterministic phrase call site to `lang="en"` before anything else routes · the
    `<reply_language>` block (Contract 5) · the toggle in `App.tsx` (two buttons, `English` /
    `العربية`, disabled while a turn is in flight) · `startTurn(turnId, lang)` · `dir="rtl"` on the
    transcript, reply and segment text when `lang === "ar"`.
17. Update the `lang` fakes in `test_turn.py` / `test_ws.py`. 🪤 **`PR_MEMORY.md` records exactly
    this trap costing hours in Block B**: a fake whose signature did not match was swallowed by
    `run_turn`'s own `except Exception` and surfaced as a generic `turn_failed`, and two barge tests
    then hung forever. `lang` has a **default**, so the fakes will not break — but confirm by running
    the suite, not by reasoning about it.
18. `make typecheck && make lint && make test` — everything green. **Rung 1 is now shippable. If the
    clock reads 12:20 or later, stop here and go to Group 5.**
19. **Rung 2.** `wav_to_pcm16` and `chunk_for_orpheus` first, with `test_groq_tts.py` written
    alongside — no network in any test. Cases: empty string · exactly 200 chars · 201 chars ·
    a 600-char single sentence with no terminator · a 300-char run with no spaces · Arabic
    punctuation (`؟` `،` `؛`) · a non-RIFF body · 48 kHz · stereo · 8-bit. Assert **no chunk exceeds
    200** and **`"".join(chunks)` loses no character**.
20. `GroqOrpheusTTS.synthesize` — sequential per chunk, **F-AR3's rate assertion on the first chunk
    before any yield**, explicit timeout and `max_retries=1`.
21. `RoutedTTS` in `factory.py` (Contract 7) · `groq_tts_model` / `groq_tts_voice` in `config.py`
    with a comment saying which voice and why.
22. F-AR2: confirm `_speak`'s existing `audio_started` branch produces the right two messages for a
    mid-stream Groq failure. Do not write a second failure branch.
23. **Verification turn**: toggle to Arabic on the deployed URL, ask a visa question, confirm it is
    Arabic audio at the right pitch. Record `tts_ttfb_ms` and `tts_total_ms` for that turn and put
    both numbers in the PR doc. **They will be worse than English. That is the finding, not a
    problem to hide.**

### Group 5 — Amend the documents (13:00, ~20 min) — **NEVER CUT**

24. Set the Arabic line in the README, the demo script row 8, and the Loom outline to whichever rung
    actually landed. The sentences for rungs 2 and 3 are **already written in D3** — paste the one
    that applies.
25. Fill the README's §Verified / §Not verified table with what Group 6 actually observed. **Every
    "not run" row keeps its limit sentence.**
26. `docs/PRs/PR_DEMOABLE.md` — including AR-0's outcome, the Arabic latency numbers if rung 2
    landed, and which cut-ladder rungs fired.

### Group 6 — Gates (14:00, human)

27. Run `/demo-check` against the deployed URL **in a fresh browser profile**, Chrome and Safari.
    Every unchecked box is a finding and goes in the README's table — not silently dropped.
28. Run Block A's 9-row verification table and Block B's 9-step table. These are the human gates
    both blocks left open; this is the last chance.
29. `modal app logs sarjy --since 30m --tail 2000 | make measure ARGS="--label deployed-final"` →
    `docs/measurements/`. If the headline number moved from the README's quoted figure, **the README
    changes, not the number.**
30. Run the `submission-reviewer` agent. Fix **blocking** findings only; everything else goes into
    the README's limits table or §What I'd do with another week.
31. Draft the commit messages (never run a git write):
    - `feat(ui): render the fact card — the deep dive's evidence, on screen`
    - `feat(ui): one stylesheet — the app had none`
    - `feat(voice): Arabic — Whisper language routing and a Groq Orpheus voice` *(or)*
      `feat(voice): Arabic input — Whisper language routing`
    - `docs: README, demo script and Loom outline for submission`

---

## Verification

Run in this order. Output, not assertion.

```bash
cd /Users/omarsalama/Projects/Sarjy/backend
make typecheck && make lint && make test
cd ../frontend
npm run typecheck && npm run lint && npm run build
```

**Proves it worked:** `mypy` clean · `ruff` clean · pytest reports **≥ 269 passed** (Block B's
baseline) plus whatever `test_groq_tts.py` adds, **zero failures** · `tsc --noEmit` silent ·
`eslint --max-warnings 0` silent · `vite build` succeeds with only the pre-existing chunk-size
warning.

**The end-to-end voice turn is mandatory** (`AGENTS.md` §Verification before done). Against the
**deployed URL**, in a fresh profile, not localhost:

| # | Do | Proves |
|---|---|---|
| V1 | Demo script rows 0–4 straight through, no restarts | #1, #2, #3 and that two turns in a row work |
| V2 | Row 3 — read the card and the segments side by side. **Every value on the card appears identically in a spoken segment, or is absent from the answer entirely.** Never a third value | The card and the answer cannot contradict each other |
| V3 | Row 5, `?gate_demo=1` | The struck-through segment is on screen **and** absent from the audio. The deep dive, live |
| V4 | Row 6, an uncovered pair | Refusal card, embassy link, no invented answer (Invariant 6) |
| V5 | Start a new turn while a card from the previous one is showing | **The old card disappears before the new answer arrives** (F-FC4) |
| V6 | Deny the mic, then Retry | Legible message, recoverable, no dead end |
| V7 | Row 7, barge in mid-answer | Audio stops now; state returns to `listening` |
| V8 | 1280×800, a long answer and a 400-char quoted segment | No horizontal scroll, nothing clipped (F-CSS1) |
| V9 | *(rung 2 only)* Row 8, Arabic | Arabic audio, correct pitch, no English phrase spoken by the Arabic voice (F-AR5). Record `tts_ttfb_ms` |
| V10 | *(rung 1 only)* Row 8, Arabic in | The transcript is Arabic; the answer is English, spoken in English |

---

## Gate

Restated from `MASTER-PLAN.md` §Block C, as observations:

1. **`make typecheck && make lint && make test` green in `backend/`, and
   `npm run typecheck && npm run lint && npm run build` green in `frontend/`.** pytest prints
   `269 passed` or more, zero failures. Output pasted into `PR_DEMOABLE.md`, not asserted.
2. **A stranger opens the deployed URL and completes demo script rows 0–6 without being told
   anything** — no README, no instructions, no Omar. Run it on someone if one is available; if not,
   run it in a fresh profile and say in the PR doc that no second human was available.
3. **The fact card paints on a real visa turn, and V2 holds** — every value on it also appears in a
   spoken segment, or nowhere.
4. **`?gate_demo=1` produces a visibly struck-through segment that is not spoken** (V3).
5. **`/demo-check` has been run against the deployed URL in a fresh profile, and every unchecked box
   is written down** — in the README's limits table, not dropped.
6. **The `submission-reviewer` agent has run and its blocking findings are resolved or named.**
7. **`README.md`, `docs/DEMO-SCRIPT.md` and `docs/LOOM-OUTLINE.md` exist**, and the README's
   §Verified / §Not verified table has a limit sentence on every "unit tests only" and "not run"
   row (D4).
8. **The Loom is recorded and shared before the meeting** (brief §Presentation). Not part of this
   block's build, but it is the thing the block exists for.

---

## Open questions the implementer will hit

1. **How do bytes come off `AsyncGroq.audio.speech.create()`?** The Groq docs' sample is
   `response.write_to_file(path)`; the async binary-response object may need `await response.aread()`
   rather than `.read()` or `.content`. **AR-0 answers this in five minutes.** Do not guess it
   inside the adapter.
2. **Is Orpheus's WAV 24 kHz mono 16-bit?** Inferred from Orpheus's SNAC decoder, **not verified**.
   AR-0 answers it. If not, rung 2 is cut (D3 rung 2).
3. **Does Groq's 10 RPM cap bite during a normal demo?** One 400-char Arabic answer is 2 requests;
   two Arabic turns inside a minute is 4. Should be fine for the scripted demo and is **not fine for
   a conversation** — which is exactly what the README says.
4. **Does Whisper `language="ar"` transcribe Gulf dialect acceptably?** Unverified against real
   speech. Only a human at a microphone answers it, in V10.
5. **Will `gemini-3.5-flash-lite` keep placeholders intact when writing Arabic?** Unverified.
   Contract 5's second sentence is the mitigation; F-AR7 is the fallback if it is not enough.
6. **Is `QUOTA_SPENT_SEED` correct on the deployment?** Unresolved at the time of writing. Task 3.
   Getting it wrong makes every visa answer silently degraded.

---

## What I found upstream

1. **`README.md` is wrong in four ways and is currently the project's front door.** It names
   **`gemini-3.1-flash-tts-preview`** as the TTS (dropped for a 10-requests/day cap — `AGENTS.md`
   §Decided); it lists **GOV.UK and Aladhan** as supporting sources (both explicitly excluded); its
   live URL is **`_TBD_`** although the deployment has been live since Block 1; and every box in
   §Status is unchecked although six of the seven are done. Rewritten in task 12.
2. **`setFactCard(null)` is missing from `handleUtterance`'s reset block** (`App.tsx` ~line 232,
   beside `setSegments([])`). Harmless today because nothing renders the card — a live
   stale-evidence bug the moment task 7 lands. Fixed first, as F-FC4.
3. **`frontend/` has no stylesheet at all.** Not a thin one — none. This is the basis for D2's
   promotion of `index.css` into the never-cut tier.
4. **The master plan's Block C line and `AGENTS.md` §Decided both still carry Arabic as
   "Groq Orpheus out, 200-char cap"** without recording that **Deepgram has no Arabic voice at all**
   (verified 2026-09-21). That is the actual reason a second TTS provider is needed, and it is the
   one-sentence answer to *"why two TTS providers?"* in the walkthrough. Worth a line in
   `AGENTS.md` when the decision closes.
5. **Block A's gate line "pulling the network still answers correctly and names which layer served
   it" has no live affordance** (D9). It is provable from tests and the eval, not from the
   deployed UI. Named in the demo script and in §What I'd do with another week rather than papered
   over.
6. **The `quoted` 400-char allowance vs Orpheus's 200-char cap** — flagged by
   `PR_GROUNDED_ANSWERS.md` for this block. Resolved by **chunking in the adapter** rather than by a
   language-aware ceiling in the gate: the cap is a property of one provider's HTTP endpoint, not of
   what Sarjy is allowed to quote, so it belongs at the provider boundary. Contract 6.
