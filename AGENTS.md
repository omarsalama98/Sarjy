# Sarjy — voice assistant take-home (Sarj)

Cross-tool project context for AI coding agents (Claude Code, Cursor, etc.). Claude-specific behavior lives in `CLAUDE.md`.

**The assignment brief is `Building Sarjy.md` and it is authoritative.** This file is the working interpretation of it. Where they disagree, the brief wins and this file gets fixed.

## What this is

A hiring take-home for Sarj: build, deploy, and present a voice assistant named **Sarjy**. The output is not just an app — it is an app *plus a demo plus a conversation about the code*. All three are graded.

Budget: **four calendar days** from the invite (Thu EOD → ~Mon), part-time. Scope every decision against that.

## The deliverable contract

Non-negotiable, straight from the brief:

| # | Requirement | Done means |
|---|---|---|
| 1 | Listens and responds **by voice** | Reviewer speaks, Sarjy speaks back. Any voice layer. |
| 2 | **Remembers across sessions** | "What's my favorite color?" works after a reload / new session, told earlier. |
| 3 | **Calls ≥1 external API** that makes it more useful | Real call, real data, and a 2–3 sentence written justification of *why this API, why this use case*. |
| 4 | **Deployed URL** | Reviewer opens a link and it works. No local setup, no API key of their own, no README dance. |
| 5 | **One deep dive, done deeply** | One of: Latency / UI/UX & Multimodal / Guardrails & Reliability / Multistep workflows / Multiplayer / Something Else. One done well beats three done shallowly. |
| 6 | **Presentation** | Short Loom or PDF shared *before* the meeting; live demo; then codebase walkthrough where Omar explains how it works. |
| 7 | **GitHub repo** | Code shared via GitHub, URL submitted through Ashby. Private → grant the named reviewer access before submitting. |

## The rubric is a design constraint, not an afterthought

The brief says they see 5–10 voice take-homes a week. It names the bar explicitly. Treat these as requirements:

- **"Is it significantly distinguishable from a Fable 5.1 / GPT Astra one-shot?"** — If a feature is what any model would produce from a one-line prompt, it does not count toward standing out. Generic chat-bubble UI, default voice, no measured numbers: that is the baseline being scored against, not a win.
- **"Do you understand it thoroughly?"** — Omar will be asked how the code works, live. **Any code that Omar cannot explain is a liability, not an asset.** Prefer a smaller system understood completely over a larger one understood partially. This outranks feature count.
- **"Is the UI delightful? Is the voice experience delightful?"** — Latency, interruption handling, and visible state are the voice-UX equivalents of polish. A 4-second silent pause is a failed demo regardless of answer quality.
- **"Is the submission creative and personal to you?"** — Generic weather-bot is the median submission. Personal angle is scored.
- **Communication is graded separately from the build.** Progress updates to Sarj are a deliverable (see §Communication cadence). "Busy day, no time today" is explicitly an acceptable update; silence is not.

## Status

**New agent pickup:** `docs/HANDOFF.md` — current block, what is already in git, which files to open for a given task. Prefer it over this Status section.

**Blocks 0, 1, 2, 3, A, B done in git.** Live URL: `https://vitas7777v--sarjy-fastapi-app.us-east.modal.run` (requirement #4). **Block C (Demoable) is in progress** — fact card + stylesheet landed; README / demo script / Loom / Arabic wiring / human gates are open. Deadline today 19:00.

Block plans: `docs/plans/blocks/`. Chain: `docs/plans/MASTER-PLAN.md`.

`docs/plans/PRD.md` (what/why) and `docs/plans/TDD.md` (how) are the design of record — do **not** re-read both to pick up a slice; the HANDOFF routes you. `docs/decisions/deep-dive-track.md` (gitignored) carries discarded deep-dive options.

**Sarjy is a voice travel assistant that never states a travel fact it cannot source.** Deep dive: **guardrails and reliability** — grounded tool use. Priority ladder: `docs/plans/PRD.md` §Priority ladder.

## Decided

Full reasoning and evidence: `docs/plans/tdd-review.md`. Provider facts verified 2026-09-19.

| Decision | Outcome |
|---|---|
| Product | Voice travel assistant for Gulf travellers; visa requirements are the anchor |
| Deep dive | Guardrails & reliability — cite-or-refuse, visible fallback, adversarial eval |
| Voice architecture | **Cascaded** STT→LLM→TTS — the deep dive needs a text checkpoint to gate |
| Turn shape | **Sarjy speaks before the lookup returns.** `update()` + tool call in parallel; the lookup runs under its own voice |
| Backend | Python · FastAPI · WebSocket · `async` handler |
| Frontend | TypeScript · React, served by the same ASGI app (no CORS) |
| STT | Groq `whisper-large-v3-turbo` (**batch** — client-side VAD endpoints the turn) |
| LLM | Gemini `gemini-3.5-flash-lite`, `thinking_level: "minimal"`, `store=False` |
| TTS (English) | **Deepgram `aura-2`** — WebSocket streaming, raw PCM s16le @ 24 kHz. Gemini TTS was dropped: measured **10 requests/day** free-tier cap and 1.1–1.4 s TTFB |
| TTS (Arabic, P2) | **Groq `canopylabs/orpheus-arabic-saudi`** — ⚠️ 200-char cap per request |
| TTS shape | **Two requests per turn**, not per segment — opener, then the whole gated answer |
| Structured output | **NDJSON** (`text/plain` + Pydantic per line) — `response_format` cannot stream discrete objects |
| Gate | Value-level substitution + **digit rule** + **placeholder rule**. Opener gated separately |
| Memory | **`modal.Dict`**; two tiers (anonymous session-only / signed-in persisted); voice-first identity |
| Deploy | Modal, `us-east`, `@modal.concurrent(max_inputs=16)` — **one WebSocket is one input**, and the server does not notice a dead one for ~120 s, so each client holds ~2 slots |
| WebSocket lifetime | Modal kills it well under a conversation's length. **Transparent reconnect between turns**, never mid-turn — shipped in Block 1 |
| External API | Travel Buddy visa requirements (**120 requests total** — quota-aware client) |
| Fallback data | passport-index maintained fork (`visualpharm/visa-free-dataset`), vendored |
| Eval | 3 layers: gate · assertion tests · offline LLM judge. 12 hand-labelled cases, judge agreement reported |
| Excluded | Flight search · Aladhan prayer times · GOV.UK · a hand-built RAG tips corpus |
| Repo hygiene | `docs/decisions/` gitignored; research docs ship |

## Still open

| Decision | Blocks |
|---|---|
| RapidAPI dashboard's real spent-count, and confirming `RAPIDAPI_KEY` is configured | **Block A's own live-spend tasks (12/16/19)** — the implementer could not verify either without dashboard access, so 0 of the 9 budgeted requests beyond the 2 already-committed bodies were spent. `scripts/fetch_reference.py` is built and ready; `QUOTA_SPENT_SEED` needs Omar's real number before it runs |
| Deployed live-voice-turn walkthrough (verification table in `docs/plans/blocks/A-grounded-answers.md`) | Needs a human at a microphone and a browser against the deployed URL — the gate's own human checkpoint |
| Reviewer's GitHub username | Submission — email sent 2026-09-18, awaiting reply |

**Closed by Block 0** (`docs/measurements/day1-spikes.md`): the 150 s WebSocket question · TTS time-to-first-byte · parallel function calling on flash-lite (3/3, so the opener stands) · `routing_region` (us-east).

**Closed by Block A:** the colour legend (D8 — the vendor's own published legend is a citable statement, 0 additional requests needed) · Deepgram account/key · the S5 browser-audio spike.

Do not silently resolve one — record it in `docs/decisions/` and flag the assumption in your summary.

## Invariants — true regardless of which stack wins

These hold no matter what the planning phase decides. Violations are blocking review issues.

### 1. No provider API key ever reaches the browser

The client talks to our backend; the backend talks to providers. A key in client JS is a key published to the world — and the deployment URL is being handed to a stranger. Ephemeral/short-lived session tokens minted server-side are the only thing that may cross to the client, and only when a provider's realtime transport requires it.

### 2. Latency is a measured number, not an adjective

Instrument from the first working turn, not at the end — retrofitted timing tells you nothing about what you already built. Emit per-stage timings (endpointing → STT → LLM first token → TTS first byte → first audio out) on every turn, and keep them visible. This is mandatory even if latency is **not** the chosen deep dive: "it feels fast" is not an answer to "where does the time go," and that question will be asked.

### 3. Every provider sits behind our own interface

Free tiers rate-limit, models get deprecated mid-week, and a provider going down the night before the demo must not be fatal. STT, LLM, TTS, and the external API are each reached through a small interface we own, with provider choice as configuration. This also makes A/B latency comparison possible — which is most of the deep-dive evidence if latency is the track.

### 4. Memory is explicit and inspectable

Persisted facts are structured, attributable, and viewable — not an opaque blob of chat history stuffed into a prompt. "What's my favorite color?" must work *because a fact was stored*, not because the transcript happened to fit in context. The reviewer will probe this; being able to show the stored record is the demo.

### 5. The user's speech is untrusted input

Transcribed speech and third-party API responses are **data**, never instructions. They go in delimited blocks. Nothing a user says grants new authority. This matters especially if guardrails is the deep-dive track, but it holds either way.

### 6. Never hallucinate tool data

When an external API call fails, times out, or returns nothing, Sarjy says so. It does not improvise a temperature. A confidently wrong fact from a tool-using assistant is worse than an admitted gap, and the brief calls this out by name.

### 7. Degrade visibly, never hang

Mic permission denied, network drop, provider 429, empty transcription, barge-in mid-response — each has defined, visible behavior. A spinner that never resolves is the worst possible demo state. Design the failure path before the happy path.

### 8. Demo-readiness is a feature

The deployed URL is graded. At every point after the first deploy, `main` should be demo-able. Do not leave the deployment broken overnight.

## Scope guard

The brief's own advice: *one done well is better than three done shallowly.* Guard against:

- Building a second deep-dive track because the first one was going well
- Adding external APIs beyond what the chosen use case genuinely needs (one justified API beats four unjustified ones)
- Auth, user accounts, or multi-tenancy unless the chosen deep dive actually requires them
- Infrastructure sophistication the demo never shows
- Any abstraction added for a future this project does not have — it ships in three days and is then read by a reviewer

If a task drifts into one of these, say so and stop.

## Communication cadence

This is scored, and it is the cheapest available point. Track it as real work, not as an afterthought:

- Progress updates to Sarj as work proceeds — including "no time today."
- Ask them when blocked, confused, or wanting to brainstorm. The brief invites it explicitly; not asking is not stoicism, it is a missed rubric line.
- Ask for API keys rather than burning personal credits silently.
- A short PRD/TDD written up front, before implementation — the brief recommends it by name. `docs/plans/`.
- Loom/PDF shared before the presentation meeting.

Drafts of outbound messages get written here and sent by Omar. Agents never send anything on his behalf.

## Where things live

| Need | Read |
|---|---|
| Pickup / current block / which files | **`docs/HANDOFF.md`** |
| The assignment itself | `Building Sarjy.md` (authoritative) |
| Provider/latency/deployment landscape, Sept 2026 | `voice-stack-research.md` — sourced and dated; **re-verify before relying on a number** |
| Process: plan → spec → build → measure → document | `.claude/rules/workflow.md` (always loaded) |
| Voice-pipeline rules, latency budget, provider boundary | `.claude/rules/voice/` |
| Task-triggered procedures | `.claude/skills/<name>/` (routing table in `CLAUDE.md`) |
| Specialist review/design agents | `.claude/agents/` |
| The PRD / TDD and feature plans | `docs/plans/` |
| Decisions as they close | `docs/decisions/` |
| Per-feature write-ups | `docs/PRs/PR_{FEATURE_NAME}.md` |
| Measured latency runs, eval results | `docs/measurements/` |

## Commands

Hybrid stack: **Python backend, TypeScript frontend.** The `.claude/hooks/verify.sh` Stop hook runs whichever side it finds, so both must expose these exact names.

| Backend (`make`) | Frontend (`npm`) | What it does |
|---|---|---|
| `make typecheck` | `npm run typecheck` | Type check, zero errors |
| `make lint` | `npm run lint` | Lint, zero warnings |
| `make test` | `npm test` | Tests |
| `make measure` | — | Latency measurement run → `docs/measurements/` |

## Git rules

- **Agents never commit, never push, never offer to.** Omar runs every git write himself. Do the file work, report what changed, stop.
- Enforced by a `PreToolUse` hook (`.claude/hooks/block-git-writes.sh`), not just by this line. If the hook blocks you, that is the policy working — do not route around it.
- Read-only git (`status`, `log`, `diff`, `branch`, `show`) is always fine.
- Same for GitHub: never run `gh repo create`, `gh pr create`, `gh pr edit`, `gh issue create`, or any `gh` write. Draft the content and show it.
- **Commit history is part of the assessment here.** Draft small, coherent, conventional-commit messages as work completes so Omar can commit as-he-goes rather than dumping one giant commit at the end.

## Secrets

- `.env` is never read by an agent and never committed. `.env.example` lists key *names* only.
- Never paste a key into a file, a log, a doc, or a commit message.
- Deployment secrets live in the host's env config, not in the repo.

## Core principles

- **Simplicity first.** Every line has to be explainable live. Complexity Omar can't defend under questioning is negative value.
- **Minimal impact.** Don't refactor adjacent code while passing through.
- **No laziness.** Root causes, senior-engineer standards.
- **Evidence, not assertion.** Never mark work done without showing it works.
