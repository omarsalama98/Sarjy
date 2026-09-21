# Code walkthrough — what to open, what to say

Three minutes of files. Do not open research dumps, PRD/TDD, or `AGENTS.md` §Decided from memory — those rows used to describe the cut opener. This page matches what shipped.

Live thesis: **the model proposes structure; deterministic code writes the travel facts the user hears.**

---

## Path (in this order)

1. **`backend/app/tools/gate.py`** (module docstring + `Register` / `GateReason`)
   - Three registers: `sourced` (placeholder, code substitutes), `quoted` (vendor words copied, model supplies no `text`), `judgement` (ungated on purpose).
   - Digit rule, number-word rule, placeholder rule, `wrong_pair`, injection markers.
   - A rejected segment is still sent and shown struck through. That visibility is the demo (`?gate_demo=1`).

2. **`backend/app/pipeline/turn.py` → `run_turn`**
   - Client already endpointed (tap / Space release, not VAD).
   - Call 1 `decide()` ± Travel Buddy → fact card **before** call 2.
   - Call 2 NDJSON segments → `gate.py` → **one** Deepgram TTS of the kept string.
   - Wikimedia places **after** TTS is handed the answer.
   - Memory extract is a background task after the user has heard the reply.

3. **`frontend/src/ui/FactCard.tsx`** (and the struck-through segments in the Now pane)
   - Card values are the same strings the gate substituted, not a parallel summary.
   - `degraded` comes from the server. Fallback badge is how a CSV/map answer is labelled.

Stop there unless they ask. Identity/memory: `backend/app/memory/` — a `Fact` has key, value, verbatim teaching sentence, `learned_at`. Recalled facts have no `tool_call_id`, so they cannot become `sourced`.

---

## Hardest questions (have the answer before they ask)

**Why cascaded, not speech-to-speech?**
The deep dive needs a text checkpoint mid-turn. S2S gives none. README §How it works.

**Why no spoken opener while the lookup runs?**
Cut. Two TTS requests fought the latency story and the gate (opener had nothing to cite). She is silent through CHECKING SOURCES, then one gated answer. Honest wait > a hedged opener.

**The gate binds values, not polarity.**
A sourced template can say “you don’t need a visa for {pair.destination_name}” while `visa.type` is “visa required” and still pass: placeholders resolve, digits are absent, pair matches. Named in README Limits. The fact card would contradict it. Not closed.

**Judgement can contain digits.**
By design (D4). Opinions, timing, “I’d go for a week.” Only `sourced` / `quoted` are value-gated. Do not claim the gate catches every number Sarjy says.

**`injection-2` (paraphrase) is a designed miss.**
Substring markers catch the real payload (`injection-1`). A paraphrase of “ignore previous instructions” can ride through `quoted`. Eval labelled it DESIGNED TO FAIL before the run. Widen the screen is “another week,” not a surprise bug.

**Quota chip says reserve only / every answer looks like CSV.**
A test wrote `spent=120` into the live `modal.Dict`. True committed spend is 3. Unlock is `docs/outbound/2026-09-21-quota-unlock.md`. If you did not unlock before the meeting, say so and point at the fallback badge + eval `vendor-failure-1`. Do not pretend it is live Travel Buddy.

**Diet after reload (requirement #2).**
The demo teaches *"I'm vegetarian"*, not a favourite colour — a travel agent using that is in-character; the brief's colour sentence is the same `Fact` record if they ask it. Works because extract stored a structured fact, not because chat history fit in context. Hard reload, sign in, ask. Panel must show the **original** `learned_at`. If it forgot: salt changed on Modal (one-way door). Do not riff on the vendor map's red/green/blue buckets as "the visa is blue" — that mapping is lossy and the client refuses to treat a colour as a visa type.

**Why Travel Buddy, not weather?**
Visa answers are high-stakes and exactly what general models invent. Dated per-nationality body + embassy link lets every spoken claim carry provenance. README has the 2–3 sentences. Wikimedia is the same contract on photos, not a second deep dive.
