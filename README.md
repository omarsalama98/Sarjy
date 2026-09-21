# Sarjy

**A voice travel assistant that never states a travel fact it cannot source.**

You speak. She speaks back. The screen is a trip dossier that grows: sourced visa documents on ivory paper, her recommendations as Wikipedia-attributed photo picks, and a running audit of every sentence she was allowed to say. When she does not have a source, she says so and points at the embassy rather than guessing.

🔗 **Live:** https://vitas7777v--sarjy-fastapi-app.us-east.modal.run

---

## Why this

General assistants confidently invent visa requirements. The answer depends on a passport-and-destination pair that changes without notice, it is not the kind of thing a model can hold reliably, and people miss flights because of it.

So the interesting problem here isn't "can a voice assistant answer travel questions" — it's **can it be trusted about facts it got from a tool**, and can a reviewer *see* that trust without reading a log. The deep dive is **guardrails and reliability**: the model proposes, deterministic code disposes, and a rejected clause is still sent and shown struck through. The trip dossier exists to make that visible, not as a second deep dive.

The bar is *grounded **and still useful***. An assistant that hedges everything has failed this, not passed it.

## What it does

- **Answers from a dated, citable source.** Every factual claim maps to a tool result held in that turn. Claims that don't map don't get spoken.
- **Shows the evidence while she talks.** The fact card paints before the gated answer; place photos arrive after TTS has started, never on the first-audio path.
- **Falls back visibly.** When the live visa source is unavailable, it answers from a vendored dataset and says which source answered and how old it is.
- **Refuses with a route.** Outside coverage, it names the gap and gives you the embassy link rather than improvising.
- **Remembers you across sessions.** Name + 4-digit PIN. Persisted facts are structured, attributable, and viewable in the trip dossier — "what's my favourite colour?" works because a fact was stored.

## The external APIs, and why these

**[Travel Buddy Visa Requirements](https://rapidapi.com/TravelBuddyAI/api/visa-requirement)** — 200 passports × 211 destinations, updated daily.

> Visa requirements are the highest-stakes factual question in travel: wrong information means being denied boarding. They're also exactly what general-purpose assistants hallucinate, because the answer depends on a passport/destination pair that changes without notice. This API returns a dated, per-nationality answer with an embassy link, which lets every claim Sarjy makes carry its own provenance instead of resting on model memory.

**[Wikimedia / Wikipedia](https://www.mediawiki.org/wiki/API:Main_page)** — no key, no quota. Entity lookup (`pageimages|extracts|info`), not image search.

> A travel agent who only recites visa rules is a lookup, not an agent. When Sarjy recommends a place, her *choice* is judgement (ungated, labelled as her view). The *photo and words* are sourced: Wikipedia's lead image, a one-line extract, a canonical URL, and the article's revision date. That is the same provenance contract as the visa card, applied to imagery. Disambiguation pages, missing articles, missing images, and timeouts are rejected and shown as "couldn't source a photo" — never a broken image, never a silent drop.

**Deliberately excluded: flights.** Every free flight API is decommissioned, sandboxed with fictional data, or stale. Showing invented fares in a project about not hallucinating would undermine the whole thing.

## How it works

```
mic → tap/hold to send → Groq Whisper
  → Gemini decide()  ± Travel Buddy lookup
  → fact card (before the gated answer)
  → Gemini NDJSON segments → gate.py
  → Deepgram Aura-2 (one TTS request for the gated answer)
  → Wikimedia lookups in parallel, after TTS has started
  → memory extract in the background
```

**Cascaded, not speech-to-speech — and that follows from the deep dive rather than from convenience.** A cascaded pipeline gives two points where text can be inspected and gated mid-turn. An end-to-end speech-to-speech model gives neither.

**The grounding gate** is the core. `sourced` segments contain `{field.path}` placeholders; deterministic code substitutes the value. A bare digit in a sourced segment is rejected. `quoted` copies the vendor's own words. `judgement` is her view, passed through, and is the only register that may carry a `place` title.

**Quota-aware vendor client.** The upstream visa free tier is 120 requests *total*, so resolution runs warm cache → live (only above a reserve) → cached map → vendored CSV. Remaining quota is visible in the header chip.

## Stack

| | |
|---|---|
| Backend | Python · FastAPI · WebSocket |
| Frontend | TypeScript · React |
| STT | Groq `whisper-large-v3-turbo` (batch; the user taps or releases to end the turn) |
| LLM | Gemini `gemini-3.5-flash-lite`, `thinking_level: "minimal"` |
| TTS | Deepgram `aura-2` (streaming PCM s16le @ 24 kHz) |
| Mic | Tap to talk, tap to send. Interrupting her is the same tap. No VAD. |
| Deploy | Modal, `us-east` |

Every provider sits behind an interface we own — provider choice is configuration, not code. No provider API key ever reaches the browser.

## The eval

8 original single-turn cases plus 5 conversation-level cases. Labels written before the run. **2026-09-21:** of the turns that completed, the original set held (6/6 scored) and the conversation set held (4/4 scored) — `conv-origin-1` stayed in Germany, not Cairo. Three turns died on a Gemini timeout (`injection-2`, `anchoring-1`, `conv-contradict-1` turn 2) and are reported as timeouts, not as gate misses. The designed `injection-2` miss is still the 2026-09-20 result. Full tables: [`eval/results/2026-09-20-gate-eval.md`](eval/results/2026-09-20-gate-eval.md), [`eval/results/2026-09-21-conversation-eval.md`](eval/results/2026-09-21-conversation-eval.md). Live demo of a rejection: open with `?gate_demo=1`.

## Running locally

```bash
cp .env.example .env              # fill in your keys

cd backend && make install && make dev     # FastAPI on :8000
cd frontend && npm install && npm run dev  # Vite on :5173, proxies /ws to the backend
```

Checks: `make typecheck && make lint && make test` in `backend`, `npm run typecheck && npm run lint && npm run build` in `frontend`.

## Limits (honest)

| Limit | What that means |
|---|---|
| Arabic is not in this demo | Groq Orpheus was probed (unsized ffmpeg WAV, 24 kHz s16le, ~800 ms TTFB on a short line, ~3 s on a 150-character chunk — `docs/measurements/2026-09-21-orpheus-wav.md`). The adapter is in tree, unwired. The gate's `NUMBER_WORDS` / place-name scan is English-only; shipping a language chip that spoke ungated Arabic would be a half-feature. |
| Wikimedia is entity lookup, not a sanitised image API | The photo is the Wikipedia article's lead image. Disambiguation / 404 / no-image / timeout are rejected. It is not claimed as content-moderated beyond that. |
| Eval is 13 hand-scored cases, no LLM judge | Methodology over denominator. `injection-2` is a named, predicted miss (observed 2026-09-20; this week's rerun timed out before the gate). Three 2026-09-21 turns died on a Gemini timeout and are reported as such. |
| The gate binds values, not polarity | A sourced template can say "you don't need a visa for {pair.destination_name}" while `visa.type` is "visa required" and still pass every rule — placeholders resolve, digits are absent, the pair matches. The fact card would contradict it. Named, not closed. |
| Fallback layer has no live "pretend vendor down" toggle | Proven by `tests/test_vendor.py`, the eval's `vendor-failure-1`, and the card's `fallback source` badge when map/CSV served. |
| Quota ledger may read 0 remaining | A test once wrote `spent=120` into the live `modal.Dict`. True committed spend is 3 (`data/README.md`). Unlock is operator-only (`docs/outbound/2026-09-21-quota-unlock.md`). |
| Cross-session memory needs `SARJY_MEMORY_SALT` set on Modal before the first real sign-in | Unset, it uses a dev default. Changing it later makes every PIN hash miss. |
| Measured latency, not a latency deep dive | Median TTS TTFB **566 ms**, LLM TTFT **890 ms** (instrument was corrected — earlier 85 ms / 30 ms figures were measuring the wrong clock). After the mic change, `endpoint_ms` is hold duration, not VAD redemption — do not read a ~600 ms improvement as a speedup. See `docs/measurements/2026-09-20-two-corrected-numbers.md`. |

## What I'd do with another week

- Arabic as a real mode: widen `NUMBER_WORDS` / the wrong-country scan, then wire `RoutedTTS` + Orpheus (`backend/app/providers/groq_tts.py` is parked for that).
- A dedicated suggestions call for structured place picks (name, one-line reason, stay length) instead of parsing `place` off a judgement line.
- A one-click "pretend the vendor is down" toggle so the fallback layer is demoable live.
- Widen the injection screen to paraphrases (`injection-2`).

## Docs

[`docs/DEMO-SCRIPT.md`](docs/DEMO-SCRIPT.md) — ordered utterances · [`docs/LOOM-OUTLINE.md`](docs/LOOM-OUTLINE.md) — 5-minute shot list · [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) — files to open in the meeting · [`docs/plans/PRD.md`](docs/plans/PRD.md) — what and why · [`docs/plans/TDD.md`](docs/plans/TDD.md) — how.

---

Built for the Sarj take-home, September 2026.
