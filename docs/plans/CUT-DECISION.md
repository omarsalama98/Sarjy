# What we cut, and why

**Sunday 2026-09-20, 07:00** · Deadline Monday 19:00 · ~17 h of build time left

## Summary

The deliverable floor, plus the deep dive, plus the presentation, **is the entire budget.**
Everything else is fighting over scraps. So this is not "which nice-to-have goes" — it is
"what is the minimum honest version of each thing that is not strictly required."

**Recommended:** canned opener instead of the `update()` architecture · hand-score the eval
instead of building an LLM judge · UI polish to zero · instrumentation to its minimum.

---

## The arithmetic

| Block | Est. | Can it be cut? |
|---|---|---|
| **2 · Voice loop** | 6.5 h | ❌ Requirement #1. Nothing works without it |
| **5 · Vendor client** | 2.25 h | ❌ Requirement #3 |
| **6 · The gate** | 2.0 h | ❌ **This is the submission.** Cutting it means there is no deep dive |
| **7 · Memory + identity** | 2.0 h | ❌ Requirement #2, and graded directly |
| **11 · Deliverables** | 3.0 h | ❌ Graded separately from the build |
| | **15.75 h** | **against ~17 h** |

**That leaves ~1.25 hours for everything else.** Which is: instrumentation, the opener, the UI,
the eval, and Arabic. Five things, one and a quarter hours.

That is the whole problem, stated in one table.

---

## Each candidate, and the call

### Block 4 — the `update()` opener · **2.0 h → 0.5 h**

**Replace, don't cut.** A pre-recorded opener clip, played the instant endpointing fires, does
the same job better on every axis that matters:

| | `update()` opener | Canned clip |
|---|---|---|
| First audio out | ~2.4 s | **~650 ms** |
| Build cost | 2.0 h | **0.5 h** |
| Can it state an unsourced fact? | needs its own gate contract | **impossible — vetted before it ships** |
| Needs parallel function calling | yes | no |

**Why this costs nothing in fidelity:** the opener contract already forbade it from saying
anything substantive — no digits, no entity-specific claims. A generated *"let me check that"* and
a recorded one are the same sentence. We were paying two hours and 1.75 seconds of latency for
the *ability* to be specific, in a place where being specific is banned.

**What we lose:** nothing demonstrable. S4's measurement (3/3 parallel calls, 111 ms apart)
becomes *"I proved the architecture works and then chose the simpler thing"* — which is a better
walkthrough answer than a half-built version of it.

### Block 9 — the LLM judge · **2.5 h → 1.25 h**

**Keep the eval. Cut the judge.** The fixtures and the 12 hand-labelled cases stay — they are the
deep dive's evidence, and without numbers the gate is just an assertion.

The judge bought two things: scale, and a judge-versus-human agreement figure. **At twelve cases,
hand-scoring is not a compromise — it is the more honest method.** There is nothing to scale, and
the agreement number exists to make a judge believable, which is moot if there is no judge.

> *"I hand-scored twelve cases against labels written before the pipeline ran. With more time I'd
> add an LLM judge and report its agreement with those labels."*

That is a real answer, and it is true.

### Block 8 — UI polish · **1.5 h → 0 h**

**Cut entirely.** Most of the UI arrives free from Block 2 (state machine, transcript) and Block 7
(memory panel). What is being cut is *polish above functional* — register styling, provenance
chips, the calm first screen.

⚠️ **This is a real loss, not a free one.** *"Is the UI delightful?"* is a scored line. Visible
state and clarity carry most of it, but not all. **This is the first thing to restore if we run
ahead**, which we will not.

### Block 3 — instrumentation · **1.0 h → 0.5 h**

**Reduce, don't cut.** Invariant 2 says latency is a measured number, and *"where does the time
go"* gets asked regardless of deep-dive track.

Minimum version: per-stage timestamps emitted on every turn and logged. **Not** a measurement
harness, **not** a p95 across runs, **not** a UI panel. Enough to answer the question with
numbers instead of adjectives.

### Block 10 — Arabic · **0.75 h, keep**

**Do not cut this.** It is 45 minutes: `language=ar` on Whisper, and Groq Orpheus for output.

**Sarj were told in writing that this is "a bilingual English/Arabic voice assistant."** Shipping
zero Arabic walks back something they have in an email. One clean Arabic turn honours it, and
naming the Gulf-dialect WER cliff out loud is a better beat than the polish would have been.

---

## Where that lands

| | Hours |
|---|---|
| The floor + deep dive + deliverables | 15.75 |
| Canned opener | 0.5 |
| Eval, hand-scored | 1.25 |
| Instrumentation, minimal | 0.5 |
| Arabic | 0.75 |
| **Total** | **18.75 h** |
| **Available** | **~17 h** |

**Still ~1.75 h over**, which is inside the error bars on these estimates and recoverable by
working later tonight. It is not recoverable by another round of cutting — there is nothing left
that does not cost a graded line.

## The trigger, decided now

**If Block 2 is not done by 15:00 Sunday**, the plan changes again rather than absorbing it
silently: drop Arabic, drop instrumentation to logging only, and shorten the eval to six cases.
Decide it on the clock, not on how it feels at midnight.
