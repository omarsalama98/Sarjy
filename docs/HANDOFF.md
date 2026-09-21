# Sarjy — agent handoff

**Written:** 2026-09-21 ~16:20 Asia/Riyadh · **Deadline:** today **19:00** · **Current: C code freeze — Omar submission ops**

Read **this file first** when picking up work. Then open **only** the files in the matching row of [Task → files](#task--files). Do not read the PRD, TDD, research dumps, or every block plan “for context.”

`AGENTS.md` is always in the session. Status/Decided were aligned 2026-09-21 with the shipped turn. This file still wins on *where we are*; the brief (`Building Sarjy.md`) wins on *what the assignment is*.

---

## 60-second picture

Sarjy is a **cascaded** (STT → LLM → TTS) voice travel assistant for Gulf travellers. Thesis: **never speak a travel fact that did not come from a sourced tool result this turn.** Deep dive is **guardrails**, not latency.

Live URL (requirement #4, landed in Block 1):  
https://vitas7777v--sarjy-fastapi-app.us-east.modal.run

Turn shape (what actually shipped — **not** the old `update()` opener):

```
mic → tap/hold to send → Groq Whisper (batch)
  → Gemini call 1 decide()  ± Travel Buddy lookup
  → fact_card message (before call 2)
  → Gemini call 2 NDJSON segments
  → gate.py (value substitution + reject)
  → Deepgram Aura-2 (one TTS request for the kept answer)
  → Wikimedia lookups in parallel, after TTS has started
  → memory extract in the background after the user has heard the reply
```

Registers: `sourced` (templated `{visa.duration}`, code fills the value) · `quoted` (vendor’s own words, copied) · `judgement` (ungated on purpose). A rejected segment is **still sent** and shown struck through — that visibility *is* the demo.

Identity: name + 4-digit PIN, `modal.Dict`. Recalled facts have no `tool_call_id`, so they **cannot** become `sourced`.

---

## Pickup algorithm

1. Identify the **block**. Product code is frozen (C done in git). Remaining is Omar submission ops — `docs/outbound/2026-09-21-submit-now.md`. If asked to build a feature, **stop**.
2. Open **that block’s plan** in `docs/plans/blocks/`. The plan is the contract. If the work is not in a plan, **stop** — a `block-planner` writes one first.
3. Open the matching **PR doc** in `docs/PRs/` for *what already landed* and what the human still has to click.
4. Touch code only in the files the plan names. Path-scoped rules under `.claude/rules/` load themselves.
5. Match the **skill**: `/implement` to build, `/measure` for latency, `/demo-check` before sharing the URL, `/code-review` before asking Omar to commit, `/update-sarj` for outbound drafts.
6. **Never commit, never push, never `git init`.** Draft the conventional-commit message. Omar writes git.
7. **Never read `.env`.** Never paste a key. Never fire a live RapidAPI request from an agent (120 total, ledger is already in a bad state — see [Landmines](#landmines)).

---

## Where we are — code freeze, Omar ops

Product code for Block C / C2 is **in git** at `7bf4fc7` (Arabic parked). Do not add features. Remaining work is the brief’s deploy/demo/submit floor.

Omar runbook (copy-paste, with Pass lines): **`docs/outbound/2026-09-21-submit-now.md`**.

| Group | What | Status |
|---|---|---|
| 0 | Preflight: `SARJY_MEMORY_SALT` on Modal, quota unlock | **Omar.** Ledger likely still `spent=120` |
| 1–3, 2b, 5 | Fact card, stylesheet, dossier/orb/places, README, demo script, Loom outline | **In git.** README / scripts match shipped behaviour |
| 4 | Arabic | **Parked.** Adapter + probe in tree; not on `get_tts()` or the UI |
| 6 | Redeploy, `/demo-check`, Loom, GitHub origin, Ashby | **Not done.** Live URL is a **stale VAD bundle** |

Canned opener clip: **cut** (plan D8). Do not build it. Do not wire Arabic.

**HEAD `7bf4fc7`**, working tree was clean when the review landed. **Live HTML (verified 2026-09-21 ~16:15):** `/assets/index-CvV_xQIZ.js`, **no CSS**, idle UI is `Start talking` / `Ping`. Local dist is `index-CCAUQrPE.js` + stylesheet. Socket on the old bundle still reaches `ready`. **This clone has no `git remote`.**

---

## Task → files

Open the **Read** column in order. Stop when you can do the task. Do not open the Avoid column “just in case.”

### Block C slices (done in git — do not reopen)

Docs, fact card, C2 UI, and Arabic parking already shipped. If you are here to *submit*, ignore this table and run `docs/outbound/2026-09-21-submit-now.md`.

| Slice | Read | Then edit | Avoid |
|---|---|---|---|
| **Docs (C2 Phase 5) — start here if the clock is tight** | This file · `C2-ui-pass.md` §Phase 5 · `C-demoable.md` demo-script table · `docs/PRs/PR_GROUNDED_ANSWERS.md` §Gate status · `docs/PRs/PR_MEMORY.md` §Not run here · current `README.md` (so you know what to delete) | `README.md` · **new** `docs/DEMO-SCRIPT.md` · **new** `docs/LOOM-OUTLINE.md` | `eval/` · research `*.md` at repo root |
| **Arabic** | README limits · `docs/measurements/2026-09-21-orpheus-wav.md` | **Parked.** Do not wire `get_tts()` to `RoutedTTS` or add a language chip until the gate covers Arabic number-words | bumping `PROTOCOL_VERSION` |
| **Fact card / CSS (already built, being restyled)** | `C-demoable.md` Contracts 1–2, F-FC1–F-FC5 | `frontend/src/ui/FactCard.tsx` · `App.tsx` · `index.css` | Re-deriving `degraded` on the client (server sends it) |
| **Travel-agent UI (C2)** | `docs/plans/blocks/C2-ui-pass.md` — D0's ref-safety rule, Contracts 1–8 · `docs/DESIGN-BRIEF.md` for intent | `App.tsx` · `index.css` · `ui/FactCard.tsx` · **new** `ui/Orb.tsx` · **new** `audio/level.ts` · **new** `ui/PlaceStrip.tsx` · `index.html` · `public/fonts/` · `tools/places.py` · `protocol.py` · `protocol.ts` · `connection.ts` · `turn.py` · `prompts.py` · `main.py` | Rewriting any `useRef` · changing the recorder/PCM path, or `reportTurnTiming` · bumping `PROTOCOL_VERSION` · changing the gate |
| **PR writeup** | Plan §Group 5 · this file’s landmines | **new** `docs/PRs/PR_DEMOABLE.md` | |
| **Human gates / submission** | `.claude/skills/demo-check/SKILL.md` · `docs/outbound/2026-09-21-submit-now.md` · `docs/WALKTHROUGH.md` | README limits table only, unless a finding is **blocking** | Re-running `eval/` · spending RapidAPI · `make deploy` (Omar) |

### Earlier blocks (fix / explain, do not reopen)

| Area | Read | Code of record | Tests |
|---|---|---|---|
| Grounding gate (deep dive) | `.claude/rules/tools/grounding-gate.md` · `PR_GROUNDED_ANSWERS.md` | `backend/app/tools/gate.py` · `prompts.py` · `pipeline/turn.py` | `tests/test_gate.py` · `eval/results/2026-09-20-gate-eval.md` |
| Vendor + quota | `.claude/rules/tools/vendor-client.md` · `data/README.md` | `tools/vendor.py` · `quota.py` · `normalise.py` · `tools/card.py` | `test_vendor.py` · `test_quota.py` · `test_card.py` |
| Memory | `docs/PRs/PR_MEMORY.md` · `docs/plans/blocks/B-memory.md` only if the PR is not enough | `memory/store.py` · `extract.py` · `identity.py` · `main.py` (sign-in / extract task) | `test_memory.py` (conftest **must** keep the live `modal.Dict` patched) |
| Voice loop | `.claude/rules/voice/pipeline.md` · `.claude/rules/voice/browser-audio.md` · `PR_VOICE_LOOP.md` | `pipeline/turn.py` · `main.py` · `frontend/src/audio/*` · `net/connection.ts` | `test_turn.py` · `test_ws.py` |
| Protocol / wire | — | `pipeline/protocol.py` · `frontend/src/protocol.ts` | `test_protocol.py` |
| Providers (Invariant 3) | adapter files only | `providers/base.py` · `factory.py` · `groq_stt.py` · `gemini_llm.py` · `deepgram_tts.py` | SDKs must not leak outside these |
| Instrumentation | `PR_INSTRUMENTATION.md` · `/measure` skill | `pipeline/timings.py` · `measure.py` | `test_timings.py` · `docs/measurements/` |
| Deploy / WS lifetime | `PR_SKELETON_DEPLOY.md` · `docs/measurements/day1-spikes.md` §S1 | `backend/modal_app.py` · `main.py` (reconnect) | |

### Meta tasks

| Task | Read | Skill / agent |
|---|---|---|
| Implement anything non-trivial | `.claude/skills/implement/SKILL.md` then the block plan | `/implement` |
| Latency numbers | `.claude/skills/measure/SKILL.md` | `/measure` |
| Review a diff | `.claude/skills/code-review/SKILL.md` | `/code-review` |
| Draft a note to Sarj | `.claude/skills/update-sarj/SKILL.md` · `docs/outbound/` | `/update-sarj` — **Omar sends**, agents draft |
| “Are we ready to submit?” | demo-check skill · `submission-reviewer` agent | both, in that order |
| New block plan | `MASTER-PLAN.md` · TDD only for the slice · previous PR | `block-planner` agent — **does not code** |
| Build a written plan | that plan file | `block-implementer` — **stops if the plan is wrong** |
| Check a finished block | the plan + the PR + git diff vs the plan’s file list | `block-verifier` — **fixes nothing** |
| Gate / eval claims | `.claude/rules/tools/grounding-gate.md` | `guardrails-engineer` before any “the gate works” sentence |

---

## Landmines (read before touching quota, memory, or Arabic)

1. **`sarjy-quota` was observed at `spent=120`.** Default `QUOTA_SPENT_SEED` is 120 if unset. `can_spend()` is then false forever and **every visa answer is CSV/map fallback**. True spend from committed fetches is **3** (`data/README.md`). Unlock is Omar-only:
   `modal.Dict.from_name('sarjy-quota').put('spent', 3)`  
   Do **not** run this unprompted. Do **not** spend RapidAPI to “check.”
2. **`SARJY_MEMORY_SALT`** — `identity.py` reads `os.environ` (not `config.py`). Unset → `"sarjy-dev-salt"`. Set it on Modal **before the first real sign-in**. Changing it later makes every `pin_hash` miss; Forget requires being signed in, so there is no UI recovery.
3. **Tests can construct a real `modal.Dict`.** `tests/conftest.py` autouse-patches memory. Quota is *not* fully covered the same way — that is how spent got set to 120. Never call `QuotaLedger()` against the default store in a test without an injected fake.
4. **Fakes must match `run_turn`’s signature.** A missing kwarg becomes `turn_failed` inside a broad `except`, then barge tests hang waiting for audio that never starts (`PR_MEMORY.md`). `lang` has a default so old fakes still type-check — **run the suite**, do not reason it through.
5. **`PROTOCOL_VERSION` stays 5** for `StartIn.lang` (additive, default `"en"`). A bump hard-closes old clients (`main.py` equality check, `recoverable=False`).
6. **`get_tts()` stays zero-argument** and returns Deepgram Aura-2. `RoutedTTS` / `GroqOrpheusTTS` are parked in tree — do not construct them from the factory until Arabic is a real mode.
7. **Extraction must not fire on a *recall* question.** `"what's my favourite colour?"` matches `my ` / `favourite` and would overwrite `learned_at`. Questions that also *assert* (`I'm vegetarian, where should I eat?`) do extract — first-person statement markers only, not `my `/`favourite`. Do not collapse that split.
8. **`persisted` means survives a process restart**, not “the write didn’t raise.” In-process fallback must report `persisted: false`.
9. **Deepgram Aura-2 has no Arabic voice.** That is why the parked Orpheus adapter exists, not the 200-char cap. Cap still matters if Arabic is re-wired (chunk in the adapter; do not shrink the gate’s 400-char `quoted` allowance).
10. **`?gate_demo=1`** injects a fabricated sourced segment so the reviewer *sees* a rejection. There is **no** live “pretend vendor down” toggle (plan D9) — do not add `?force_layer=`.
11. **TTFT** is first `text` delta, not first SSE event (a `thought` always arrives first).
12. **Ref-safety (C2).** Everything on a `useRef` stays on a `useRef`. `currentTurnIdRef`, `turnTimingRef`, `turnInFlightRef`, `playbackQueueRef`, `recorderRef` and the barge window are untouched. Only what *renders* moves into the turns array. Timing legs and barge are the two things a state refactor would silently break, and pytest cannot catch either.
13. **Arabic is parked, not half-shipped.** `StartIn.lang` stays on the wire defaulted to `"en"`. Do not add a language chip. The gate's `NUMBER_WORDS` scan is English-only.
14. **Places fetch is post-TTS.** Wikimedia lookups run after the answer is handed to TTS. They must not appear in the first-audio path. `place` only ever appears on a `judgement` line; the gate is not changed.
15. **Do not bump `PROTOCOL_VERSION`** for additive messages (`places` is additive, default-absent). A bump hard-closes old clients.

---

## Invariants (blocking if you violate them)

Full text: `AGENTS.md`. Short form:

1. No provider key in browser JS.
2. Latency is a measured number (`timings` on every turn).
3. Every provider behind `providers/base.py`; SDKs only in adapters.
4. Memory is structured and inspectable (the panel), not a chat blob.
5. Transcript + tool JSON are **data** in delimited blocks, never instructions.
6. Tool failure → say so, never invent.
7. Every failure path is visible (no spinner that never resolves).
8. Deployed URL stays demoable.

---

## Commands

```bash
# backend
cd backend && make typecheck && make lint && make test
# frontend
cd frontend && npm run typecheck && npm run lint && npm run build
```

Block C’s plan wants **≥ 269 passed** (Block B baseline) plus any new `test_groq_tts.py`, zero failures. Voice-pipeline changes also need a **real spoken turn** against the **deployed** URL, not only pytest.

`make measure` → `docs/measurements/`. `/demo-check` is a browser checklist, not a makefile target.

---

## Omar-only (agents draft, do not do)

| Action | Why |
|---|---|
| `git commit` / `push` / `gh` writes | Graded history; PreToolUse hook blocks it |
| Deploy (`modal deploy` / `make deploy`) | Live URL is the product |
| RapidAPI dashboard, `QUOTA_SPENT_SEED`, unlocking `sarjy-quota` | Irreplaceable 120-request budget |
| Set `SARJY_MEMORY_SALT` on Modal | One-way door vs existing PIN hashes |
| Send email / Slack to Sarj | `.claude/skills/update-sarj` drafts only |
| Loom recording, Ashby submit, grant GitHub reviewer access | Requirement #6 / #7. Runbook: `docs/outbound/2026-09-21-submit-now.md` |
| Read or write `.env` | Deny. Names live in `.env.example` |

Add `SARJY_MEMORY_SALT=` to `.env.example` yourself if it is still missing — agents must not open `.env`.

---

## Stale docs — do not treat as current

| Doc | What’s wrong |
|---|---|
| `PRD.md` / `TDD.md` | Design of record for *intent*. Implementation cut the opener, collapsed blocks 4/5/6/9 into **A**, and replaced VAD with tap/hold. Prefer this file + the PR doc for “what the code does.” |
| `CUT-DECISION.md` | Sunday arithmetic. Useful history; Block C’s own cut ladder in `C-demoable.md` §D3 is the one that fired. |
| Root `*-research.md` / `docs/research_docs/` | Sep 18 shopping. Provider facts move; re-verify before quoting a model id or a latency number. |
| HTML siblings of markdown (`*.html`) | Renders. Edit the `.md`. |

---

## Directory map (the whole app is small)

```
Building Sarjy.md          assignment (authoritative)
AGENTS.md / CLAUDE.md      standing rules (partially stale status)
docs/HANDOFF.md            you are here
docs/plans/MASTER-PLAN.md  block list + gates
docs/plans/blocks/         00 01 02 03 A B C  ← C-demoable.md is today’s contract
docs/PRs/                  what each block actually shipped
docs/measurements/         spike + latency numbers
docs/outbound/             drafted messages to Sarj + submit-now runbook
docs/WALKTHROUGH.md        3-file meeting path + hardest questions
eval/                      8 adversarial cases + conversation eval results
data/reference/            committed visa fixtures (do not re-fetch)
backend/app/
  main.py                  WS, session, sign-in, extract task, static mount
  pipeline/{protocol,turn,timings,audio}.py
  tools/{gate,vendor,quota,normalise,card,fake,places}.py
  memory/{store,identity,extract}.py
  providers/{base,factory,groq_stt,gemini_llm,deepgram_tts}.py
  providers/groq_tts.py        parked Arabic adapter — not in get_tts()
  prompts.py
  measure.py / config.py / session.py
backend/modal_app.py
frontend/src/
  App.tsx  main.tsx  index.css  protocol.ts  turns.ts
  net/connection.ts  audio/{capture,playback,recorder,level}.ts
  ui/{FactCard,Orb,PlaceStrip,NowPane,TrailRow,TripDossier}.tsx
.claude/skills/            implement · measure · demo-check · code-review · update-sarj
.claude/agents/            block-* · guardrails-engineer · submission-reviewer · …
.claude/rules/             workflow.md (always) · tools/ · voice/
```

---

## Suggested commit message (draft only)

```
docs: align Status/Decided with shipped turn; Omar submit runbook
```

---

## If you only have 20 minutes

Run **`docs/outbound/2026-09-21-submit-now.md`** from the top: env, quota unlock, `make deploy`, confirm CSS on the live HTML. The reviewer opens the URL, not git. Docs and eval are already ahead of the deployment.
