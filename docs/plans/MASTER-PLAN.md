# Sarjy — Master plan

**Date:** 2026-09-19 17:00 · Deadline **Monday 19:00** · Design of record: `TDD.md`

High-level only. Each block gets its own plan in `docs/plans/blocks/NN-name.md`, written immediately before that block is built — deeper detail, file-by-file, written when we know what the previous block actually produced.

## The budget, honestly

| | Hours |
|---|---|
| Saturday, from 17:00 | ~5 |
| Sunday | ~10 |
| Monday, to 19:00, **less 3 h reserved** | ~6 |
| **Available** | **~21** |
| Plan below, P0 + deep dive + deliverables | **~24** |

**~3 hours over, and that assumes nothing goes wrong in a voice app.** The overflow list at the bottom is what comes out, in order. Deciding now beats discovering it Monday.

## Rules that apply to every block

1. **Plan the block, then build it.** No block starts without its own plan file.
2. **Every block ends deployed and demo-able.** `main` is never broken overnight.
3. **Failure paths before happy paths.** This is a voice app; the failure paths are what break demos.
4. **Walk through the code as it lands, not on Monday.** With AI the bottleneck is comprehension, not typing — and *"do you understand it thoroughly"* is graded.
5. **Never commit.** Omar runs every git write.

## The blocks

### Block 0 — Spikes · ~1.5 h · **Saturday**

Three experiments that can invalidate the architecture. Nothing downstream is safe until they answer.

| Spike | Question | If it fails |
|---|---|---|
| Modal WebSocket | Does an idle connection survive past 150 s? | Fly.io |
| Browser audio | Does capture → 16 kHz PCM → playback work in isolation? | The hard part of Block 2, surfaced early |
| TTS TTFB | How long to first audio byte? `generateContent` vs `/interactions`? | Latency budget is rewritten |
| *(rolled in)* Region A/B | `us-east` vs `eu-west` — **irreversible after first deploy** | — |
| *(rolled in)* Parallel FC | Does `gemini-3.5-flash-lite` emit two function calls at once? | The opener design is dropped |

**Gate:** five answers written into `docs/measurements/day1-spikes.md`. **No code kept.**

---

### Block 1 — Skeleton that deploys · ~2 h · **Saturday** · *needs 0*

FastAPI **async** WebSocket handler, the message protocol, a frontend shell that connects, and the `StaticFiles` mount that serves the frontend from the same origin.

**Gate:** a public Modal URL. Open it, the socket connects, a message round-trips. **Requirement #4 is landed** — the one that scores zero if missing.

---

### Block 2 — The voice loop · ~3.5 h · **Sat → Sun** · *needs 1*

The riskiest block, and the one that is pure engineering with no model cleverness.

Browser capture (AudioWorklet, 48→16 kHz, PCM16, echo cancellation) · client-side VAD and endpointing · STT adapter · **a plain LLM call, no tools, no NDJSON** · TTS adapter · playback queue with explicit scheduling · visible state machine.

**Deliberately simple LLM here.** Tools and the opener come in Block 4. This block's job is proving audio in, audio out.

**Gate:** speak to the deployed URL and hear a sensible spoken reply. **Requirement #1.**

---

### Block 3 — Instrumentation · ~1 h · *needs 2*

Per-stage timings on every turn, emitted and visible: endpointing → STT → LLM → TTS TTFB → first audio out.

⚠️ **TTFT measured to the first `text` delta, not the first SSE event** — a `thought` step always arrives first, and timing to it records a fiction.

**Gate:** real numbers on screen for a real turn, and a median over ten turns against the deployment. **Invariant 2, and retrofitting it later tells you nothing.**

---

### Block A — Grounded answers · *needs 3* · **the deep dive** · requirements #3 and #5

**Restructured 2026-09-20.** Old Blocks 4, 5, 6 and 9 are one block. Seven blocks meant seven
plan→implement→review cycles; the base was never the graded part and it ate the budget.

Four things, in dependency order:

1. **The segmented LLM turn.** Call 2 streams **NDJSON**, one segment per line, validated per line
   with Pydantic. Each segment carries a register: `sourced` (citation, date, layer) or `judgement`
   (Sarjy's own view, no citation). Both directions are failures. Against a **fake** tool first, so
   this is never blocked on vendor quota.
2. **The vendor client.** Travel Buddy visa requirements. Quota ledger and reserve · resolution
   order (cached map → warm cache → CSV → live) · the maintained-fork CSV · the colour-legend
   spike (~6 requests) · normalisation so live and CSV emit one identical shape.
3. **The gate.** `resolve` · `get_path` · value-level substitution (the model names `{visa.duration}`,
   deterministic code substitutes the value) · the **digit rule** (no digit in a `sourced` segment
   outside a placeholder) · the **placeholder rule** (a `sourced` segment contains ≥1 placeholder) ·
   the reject-and-say-so path. **Tier A unit tests written here, not after.**
4. **The eval.** Hand-scored adversarial cases, RAGAS-style, cited as such. Proves the gate catches
   fabrication rather than asserting it.

🪤 `arguments_delta`, not `arguments` — Google's docs contradict each other and the wrong one
silently matches nothing.

**Gate:** a real visa lookup answers and the ledger decrements · pulling the network still answers
correctly and names which layer served it · a deliberately fabricated number is **visibly rejected**
· the eval table exists with numbers in it. **This is the demo.**

---

### Block B — Memory · *needs A* · requirement #2

`modal.Dict` store · two tiers (anonymous session-only / signed-in persisted) · voice-first greeting
with typed fallback · name + PIN · the extraction call fired after dispatch · the "what Sarjy
remembers" panel with a forget button.

**Invariant 4:** persisted facts are structured and inspectable, not a chat blob. The panel *is* the
demo — "what's my favourite colour" must work **because a fact was stored**.

**Gate:** told in one session, answered correctly in a fresh one after a reload. Shown in the panel.

---

### Block C — Demoable · *needs B* · requirements #1, #6

The canned opener clip (the `update()` opener was cut — a pre-recorded clip covers the lookup) ·
the UI pass · **Arabic** (`language=ar` on Whisper, Groq Orpheus out, ⚠️ 200-char cap per request) ·
README · the demo script · the Loom outline.

**Gate:** `/demo-check` passes, the `submission-reviewer` agent has run, and a stranger can open the
URL and have a conversation without being told anything first.

---

## Dependency shape

```
0 ─→ 1 ─→ 2 ─→ 3 ─→ A ─→ B ─→ C
         (done)      ▲     the deep dive is A
```

A straight chain, and deliberately so. **Restructured 2026-09-20 from twelve blocks to six**: the
first four are done, and the remaining three each get one plan → one implementation → one review
instead of seven cycles over the same ground.

Arabic no longer floats — it lives in C. Nothing else can move.

## The overflow list — cut from the bottom

| Cut | Saves | What is lost |
|---|---|---|
| 1. Wikipedia imagery | 0.75 | Already P3. Travel suggestions do not need it — they are `judgement` |
| 2. UI polish beyond functional | 1.25 | Real rubric loss. State and clarity carry most of it |
| 3. Arabic code-switching + RTL | 1.25 | Keep the bare Arabic turn. Name the gap out loud |
| 4. Tier B golden tests | 0.4 | Tier A still covers the gate |
| 5. The LLM judge (Block 9 partial) | 1.5 | **Last thing to cut.** Gate + assertions still give defensible numbers |

Cuts 1–4 close the ~3 h gap. Cut 5 only if Sunday goes badly.

## Trigger points, decided now rather than at 2 a.m.

| If… | Then |
|---|---|
| ~~Block 0 says the Modal WebSocket dies at 150 s~~ | ~~Switch to Fly.io immediately~~ — **FIRED, AND OVERRIDDEN 2026-09-19.** It dies in (5s, 160s]. We stay on Modal and Block 1 ships transparent reconnect between turns. Reasoning in `docs/measurements/day1-spikes.md` §S1 |
| Block 0 says TTS TTFB > 2 s | Drop the opener; re-derive the budget; say so in the writeup |
| Block 0 says no parallel function calling on flash-lite | Sequential flow, no opener. Everything else stands |
| **Saturday ends without a deployed URL** | Sunday drops Blocks 9 and 10 at the start of the day, not the end |
| Sunday ends without the gate working | The deep dive becomes "designed and partially built" — say so honestly, show the tests |
| **Monday 12:00 and Block B is not done** | Memory drops to session-only (no `modal.Dict` persistence) and requirement #2 is answered from the anonymous tier. Say so in the writeup |
| **Monday 15:00 and Block C is not started** | Arabic goes first, then the UI pass. README, demo script and Loom are never cut — they are requirement #6 |

### Block 0 outcome — 2026-09-19, full detail in `docs/measurements/day1-spikes.md`

| Trigger | Fired? | What happened |
|---|---|---|
| Modal WebSocket dies at 150 s → Fly.io | **YES — FIRED.** | Both arms (idle **and** heartbeat) died client-side somewhere in (5 s, 160 s], corroborated by a control test against an unrelated public WebSocket that survived past 200 s under the same idle conditions from the same network. **Switch to Fly.io before Block 1.** This is the block's headline finding. |
| TTS TTFB > 2 s → drop the opener | NO (preliminary) | Clean, isolated samples ~1.1–1.4 s (n=1–2 per arm, not the planned n=5 — a previously-unknown **10 requests/day** free-tier cap on `gemini-3.1-flash-tts-preview` cut the batch short). PASS-with-a-rewrite band. **Re-run at full n=5 once the daily quota resets** before finalizing the budget. |
| No parallel FC on flash-lite → sequential, no opener | NO | 3/3 runs produced both `update` and `get_visa_requirements` in one response. Opener stands. Median name→args gap was ~111 ms (< 150 ms), so the two calls stream back-to-back rather than concurrently — adjust the "hidden under audio" framing to "fires the instant call 1 finishes," not literally mid-generation. |

**New trigger this block surfaced, not in the original table:** `gemini-3.1-flash-tts-preview` free tier caps at **10 requests/day**, shared across `generateContent` and `interactions` alike. At 2 TTS calls/turn this is ~5 turns/day before the model stops working entirely — a demo-day risk bigger than the latency question the table was written for. Needs a decision (paid tier, quota increase, or a fallback voice) before Block 2.
