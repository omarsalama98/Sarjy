# Sarjy — agent handoff

**Written:** 2026-09-21 ~03:50 Asia/Riyadh · **Deadline:** today **19:00** · **Current block: C (Demoable)**

Read **this file first** when picking up work. Then open **only** the files in the matching row of [Task → files](#task--files). Do not read the PRD, TDD, research dumps, or every block plan “for context.”

`AGENTS.md` is always in the session. Parts of it are **stale** (see [Stale docs](#stale-docs)). This file wins on *where we are*; the brief (`Building Sarjy.md`) wins on *what the assignment is*.

---

## 60-second picture

Sarjy is a **cascaded** (STT → LLM → TTS) voice travel assistant for Gulf travellers. Thesis: **never speak a travel fact that did not come from a sourced tool result this turn.** Deep dive is **guardrails**, not latency.

Live URL (requirement #4, landed in Block 1):  
https://vitas7777v--sarjy-fastapi-app.us-east.modal.run

Turn shape (what actually shipped — **not** the old `update()` opener):

```
mic → client VAD → start/binary/end over WebSocket
  → Groq Whisper (batch)
  → Gemini call 1 decide()  ± Travel Buddy lookup
  → fact_card message (before call 2)
  → Gemini call 2 NDJSON segments
  → gate.py (value substitution + reject)
  → Deepgram Aura-2 (one TTS request for the kept answer)
  → memory extract in the background after the user has heard the reply
```

Registers: `sourced` (templated `{visa.duration}`, code fills the value) · `quoted` (vendor’s own words, copied) · `judgement` (ungated on purpose). A rejected segment is **still sent** and shown struck through — that visibility *is* the demo.

Identity: name + 4-digit PIN, `modal.Dict`. Recalled facts have no `tool_call_id`, so they **cannot** become `sourced`.

---

## Pickup algorithm

1. Identify the **block** (`MASTER-PLAN.md` is the list; you are almost certainly on **C**).
2. Open **that block’s plan** in `docs/plans/blocks/`. The plan is the contract. If the work is not in a plan, **stop** — a `block-planner` writes one first.
3. Open the matching **PR doc** in `docs/PRs/` for *what already landed* and what the human still has to click.
4. Touch code only in the files the plan names. Path-scoped rules under `.claude/rules/` load themselves.
5. Match the **skill**: `/implement` to build, `/measure` for latency, `/demo-check` before sharing the URL, `/code-review` before asking Omar to commit, `/update-sarj` for outbound drafts.
6. **Never commit, never push, never `git init`.** Draft the conventional-commit message. Omar writes git.
7. **Never read `.env`.** Never paste a key. Never fire a live RapidAPI request from an agent (120 total, ledger is already in a bad state — see [Landmines](#landmines)).

---

## Where we are — Block C

Plan: `docs/plans/blocks/C-demoable.md` (authoritative for remaining work).

| Group | What | In git? |
|---|---|---|
| 0 | Preflight: live voice turn, `SARJY_MEMORY_SALT` on Modal, quota unlock | **Omar.** Not done from this environment |
| 1 | Fact card renders (refusal / empty / populated + degraded badge); clear card on new turn | **Yes** — `frontend/src/ui/FactCard.tsx`, `App.tsx` |
| 2 | `frontend/src/index.css` (~120 lines) + import in `main.tsx` | **Yes** — being rewritten by C2 |
| 2b | **Travel-agent UI** — plan: `docs/plans/blocks/C2-ui-pass.md` | **In progress.** Five phases: dossier · shell · orb · Wikimedia places · documents. Phase 5 is never cut |
| 3 | Rewrite `README.md` · write `docs/DEMO-SCRIPT.md` · `docs/LOOM-OUTLINE.md` | **C2 Phase 5. Never cut.** README is still wrong |
| 4 | Arabic | **Cut.** Both rungs. Named as a limit in the README. `StartIn.lang` stays on the wire unused |
| 5 | Amend the three docs to match what actually shipped | C2 Phase 5 |
| 6 | `/demo-check`, Block A/B human tables, `make measure`, `submission-reviewer`, Loom, Ashby | Not started |

Canned opener clip: **cut** (plan D8). Do not build it.

**Working tree was clean** on `master` at `fc08a94` when this was written. That commit bundled Blocks 2–B plus C groups 1–2. **The live Modal bundle may still be older than this commit** — Block B’s verifier last saw a deploy without memory. Confirm before demoing.

---

## Task → files

Open the **Read** column in order. Stop when you can do the task. Do not open the Avoid column “just in case.”

### Continue Block C (default)

| Slice | Read | Then edit | Avoid |
|---|---|---|---|
| **Docs (C2 Phase 5) — start here if the clock is tight** | This file · `C2-ui-pass.md` §Phase 5 · `C-demoable.md` demo-script table · `docs/PRs/PR_GROUNDED_ANSWERS.md` §Gate status · `docs/PRs/PR_MEMORY.md` §Not run here · current `README.md` (so you know what to delete) | `README.md` · **new** `docs/DEMO-SCRIPT.md` · **new** `docs/LOOM-OUTLINE.md` | `eval/` · research `*.md` at repo root |
| **Arabic** | — | **Cut.** Do not build. Name it in the README limits table | `groq_tts.py` · `RoutedTTS` · bumping `PROTOCOL_VERSION` |
| **Fact card / CSS (already built, being restyled)** | `C-demoable.md` Contracts 1–2, F-FC1–F-FC5 | `frontend/src/ui/FactCard.tsx` · `App.tsx` · `index.css` | Re-deriving `degraded` on the client (server sends it) |
| **Travel-agent UI (C2)** | `docs/plans/blocks/C2-ui-pass.md` — D0's ref-safety rule, Contracts 1–8 · `docs/DESIGN-BRIEF.md` for intent | `App.tsx` · `index.css` · `ui/FactCard.tsx` · **new** `ui/Orb.tsx` · **new** `audio/level.ts` · **new** `ui/PlaceStrip.tsx` · `index.html` · `public/fonts/` · `tools/places.py` · `protocol.py` · `protocol.ts` · `connection.ts` · `turn.py` · `prompts.py` · `main.py` | Rewriting any `useRef` · changing the VAD, PCM path, or `reportTurnTiming` · bumping `PROTOCOL_VERSION` · changing the gate |
| **PR writeup** | Plan §Group 5 · this file’s landmines | **new** `docs/PRs/PR_DEMOABLE.md` | |
| **Human gates / submission** | `.claude/skills/demo-check/SKILL.md` · plan §Group 6 / §Gate · `.claude/agents/submission-reviewer.md` | README limits table only, unless a finding is **blocking** | Re-running `eval/` · spending RapidAPI |

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
6. **`get_tts()` stays zero-argument.** Arabic is a `RoutedTTS` *inside* the factory, dispatching on `synthesize(..., language=)`. Do not change the factory arity — it ripples through every fake.
7. **Extraction must not fire on the recall question.** `"what's my favourite colour?"` matches the old heuristic (`my `, `favourite`) and would overwrite `learned_at`. That bug was fixed; do not loosen `looks_self_referential()`.
8. **`persisted` means survives a process restart**, not “the write didn’t raise.” In-process fallback must report `persisted: false`.
9. **Deepgram Aura-2 has no Arabic voice.** That is why a second TTS exists, not the 200-char cap. Cap still matters for Orpheus (chunk in the adapter; do not shrink the gate’s 400-char `quoted` allowance).
10. **`?gate_demo=1`** injects a fabricated sourced segment so the reviewer *sees* a rejection. There is **no** live “pretend vendor down” toggle (plan D9) — do not add `?force_layer=`.
11. **TTFT** is first `text` delta, not first SSE event (a `thought` always arrives first).
12. **Ref-safety (C2).** Everything on a `useRef` stays on a `useRef`. `currentTurnIdRef`, `turnTimingRef`, `turnInFlightRef`, `playbackQueueRef`, `detectorRef` and the barge window are untouched. Only what *renders* moves into the turns array. Timing legs and barge are the two things a state refactor would silently break, and pytest cannot catch either.
13. **Arabic is cut.** Both rungs. Do not thread `StartIn.lang`. Do not add `GroqOrpheusTTS`.
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
| Loom recording, Ashby submit, grant GitHub reviewer access | Requirement #6 / #7 |
| Read or write `.env` | Deny. Names live in `.env.example` |

Add `SARJY_MEMORY_SALT=` to `.env.example` yourself if it is still missing — agents must not open `.env`.

---

## Stale docs — do not treat as current

| Doc | What’s wrong |
|---|---|
| `AGENTS.md` §Status | Still says **Block 2 is next**. False. Use this handoff. |
| `AGENTS.md` §Decided | Several rows describe the **pre-cut** design: `update()` opener, two TTS requests per turn, opener gated separately, 12-case eval + LLM judge. **Shipped:** no opener, **one** TTS of the gated answer, eval is **8 hand-scored cases / 7 pass**, `injection-2` is the labelled fail, **no LLM judge**. TTS English is Deepgram, not Gemini. |
| `README.md` | Live URL `_TBD_` · TTS still Gemini · lists GOV.UK and Aladhan as sources (both **excluded**) · every status checkbox empty. Rewriting it **is** Block C Group 3. |
| `CUT-DECISION.md` | Sunday arithmetic. Useful history; Block C’s own cut ladder in `C-demoable.md` §D3 is the one that fires today. |
| `PRD.md` / `TDD.md` | Design of record for *intent*. Implementation has since cut the opener and collapsed blocks 4/5/6/9 into **A**. Prefer the block plan + PR doc for “what the code does.” |
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
docs/outbound/             drafted messages to Sarj
eval/                      8 adversarial cases + 2026-09-20 results
data/reference/            committed visa fixtures (do not re-fetch)
backend/app/
  main.py                  WS, session, sign-in, extract task, static mount
  pipeline/{protocol,turn,timings,audio}.py
  tools/{gate,vendor,quota,normalise,card,fake,places}.py
  memory/{store,identity,extract}.py
  providers/{base,factory,groq_stt,gemini_llm,deepgram_tts}.py
  prompts.py
  measure.py / config.py / session.py
backend/modal_app.py
frontend/src/
  App.tsx  main.tsx  index.css  protocol.ts
  net/connection.ts  audio/{capture,playback,turn}.ts
  ui/FactCard.tsx  ui/Orb.tsx  ui/PlaceStrip.tsx
  audio/{capture,playback,turn,level}.ts
.claude/skills/            implement · measure · demo-check · code-review · update-sarj
.claude/agents/            block-* · guardrails-engineer · submission-reviewer · …
.claude/rules/             workflow.md (always) · tools/ · voice/
```

---

## Suggested first commit messages (draft only)

From `C-demoable.md` task 31, use only the ones that match what you actually ship:

- `feat(ui): render the fact card — the deep dive's evidence, on screen` *(already in tree; do not re-commit unless Omar never committed it alone)*
- `feat(ui): one stylesheet — the app had none`
- `feat(voice): Arabic input — Whisper language routing` *or* `feat(voice): Arabic — Whisper language routing and a Groq Orpheus voice`
- `docs: README, demo script and Loom outline for submission`

---

## If you only have 20 minutes

Do **C2 Phase 5**: honest README + demo script + Loom outline against **what is true right now** (including “not run” rows). That *is* requirement #6. The orb and the places strip are cuttable; those three documents are not.
