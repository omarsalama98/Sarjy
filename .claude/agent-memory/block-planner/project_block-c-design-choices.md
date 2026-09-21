---
name: block-c-design-choices
description: Block C (the last block, demo + submission) — the ranking, the deviations from its brief, and the upstream problems found while planning it, 2026-09-21
metadata:
  type: project
---

Block C's plan (`docs/plans/blocks/C-demoable.md`) is the submission block: README, demo script,
Loom outline, the fact card, Arabic. Written 2026-09-21 against a 19:00 same-day deadline.

**Why:** the plan's Decisions page pre-commits a cut ladder with hard clock times specifically so
nobody has to make a scope judgement at 13:00 on deadline day. Reverting one of these silently
re-opens a decision that was closed under better conditions.

**How to apply:** if a later review or a fix contradicts one of these, read the plan's §Decisions
and §What I found upstream before "correcting" it.

- **`frontend/` has no stylesheet at all** — no `.css` file anywhere, browser defaults only. The
  plan **promotes a single ~120-line `index.css` into the never-cut tier**, deviating from the
  caller's ranking which put the UI pass first-to-cut. Reason: the Loom is what most reviewing
  happens against, and "is the UI delightful" is on the rubric verbatim.
- **Arabic ships in two rungs.** Rung 1 (~15 min) is Whisper `language="ar"` + answer in English —
  a real, defensible Gulf-traveller behaviour on its own. Rung 2 is spoken Arabic via Groq Orpheus
  and is cut at 13:00 wherever it stands. The README sentences for both cut outcomes are
  **pre-written in the plan** so nobody drafts an honest self-assessment while exhausted.
- **`PROTOCOL_VERSION` is deliberately NOT bumped** for the new `lang` field. `main.py:881` does a
  strict equality check and hard-closes with `recoverable=False`; an additive optional field with a
  default is compatible both ways, so a bump only adds a deadline-day failure mode.
- **Language routes inside the TTS boundary (`RoutedTTS`), not via `get_tts(lang)`.** Changing
  `get_tts`'s arity means ~12 edits across Block A's and Block B's test fakes for no behavioural
  gain. Cost, accepted and named: `timings.tts_model` becomes a composite string, closed by adding
  `TurnTimings.lang`.
- **The vendor fallback layer has no live demo affordance** and the plan refuses to build one
  (a per-call layer override would touch the `VisaTool` Protocol + `FakeVisaTool` + tests). Block
  A's own gate line — "pulling the network still answers and names which layer served it" — is
  therefore provable only from the eval and `test_vendor.py`. Named in the demo script and in
  "what I'd do with another week" rather than papered over.
- **Honesty rule the README must follow:** an unproven claim is stated with its limit in the same
  sentence, never omitted and never softened to the present tense. Three-column table —
  Capability / Verified how (live-by-hand · live-scripted · unit-tests-only · not-run) / Limit —
  and any non-live row must carry a non-empty limit.

Upstream problems found: `README.md` names the dropped Gemini TTS model, lists two excluded APIs
as supporting sources, has a `_TBD_` live URL, and shows every status box unchecked ·
`setFactCard(null)` is missing from `App.tsx`'s turn-start reset block (a latent stale-evidence bug
that goes live the moment the card renders).

Related: [[arabic-tts]], [[block-a-design-choices]], [[cascaded-is-closed]]
