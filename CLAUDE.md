@AGENTS.md

# Claude Code-specific guidance

Supplements `AGENTS.md` — imported above at session start — with behavior that only applies inside Claude Code.

The assignment brief itself is `Building Sarjy.md`. Read it before any substantive work; it is short and it is the contract.

## Before non-trivial work

For anything touching multiple files, making an architectural decision, or taking more than a couple of edits:

1. **Read the plan.** `docs/plans/PRD.md` (what/why) and `docs/plans/TDD.md` (how) are the plan of record. If the work isn't in them, say so before building it — scope drift is the main risk left.
2. **Check `.claude/skills/`** and invoke the matching skill (routing table below). Skills carry the deepest task-specific guidance.
3. **Rules load themselves.** `.claude/rules/` is path-scoped — domain rules enter context automatically when you touch matching files. Only `workflow.md` is always-on. Don't re-read rules manually unless you're working from a description without touching files yet.
4. **Enter plan mode** for 3+ steps or architectural decisions, and follow `.claude/rules/workflow.md`.

## Task discipline

- **Never commit, never push, never `git init`, never offer to.** Absolute. A `PreToolUse` hook enforces it. Draft the commit message instead — commit history is graded on this project, so good messages are real work.
- **Verify the plan with Omar** before implementing. Don't code from a vague brief.
- **Explain changes as you go** — short summaries at meaningful steps so course-correction is cheap.
- **Track progress** with the task tools; mark items complete as you finish, don't batch.
- **State assumptions out loud.** Several things in the TDD are marked as inference rather than verified fact — the Modal WebSocket lifetime above all. If you assumed a provider behaviour, a latency figure, or an API shape, say so in your summary; don't bury it.
- **Document non-trivial work** in `docs/PRs/PR_{FEATURE_NAME}.md` (Summary, Problem, Solution, Changes, How to Test, Changelog).

## The rubric is the spec

Unusually for a codebase, the grading criteria in `AGENTS.md` §The rubric are *requirements*. Two of them change how you should write code:

- **Omar has to explain this live.** When choosing between implementations, weight "can he defend this under questioning in three weeks" above elegance and above marginal performance. If you use a library's magic, explain the magic in a comment or pick something plainer. **Do not generate code Omar hasn't been walked through.**
- **It has to beat a one-shot.** If what you're about to build is what any model would emit from a one-line prompt, flag that before building it. That's the baseline being scored against, not a contribution.

## Skills routing

| Task | Skill |
|---|---|
| Choose the deep-dive track (the gating decision) | `/plan-deep-dive` |
| Write the PRD / TDD the brief asks for | `/prd` |
| Implement a feature or fix | `/implement` |
| Instrument, run, or interpret a latency measurement | `/measure` |
| Verify the deployment is demo-ready end to end | `/demo-check` |
| Draft a progress update or a question to Sarj | `/update-sarj` |
| Review a diff | `/code-review` |

The deep dive's contract lives in `.claude/rules/tools/grounding-gate.md` and loads itself. The `guardrails-engineer` agent owns it.

## Agents vs skills

- **Skills** are authoritative for *how to do a task* here — file patterns, validation steps, output conventions. Prefer the matching skill when one exists.
- **Agents** (`.claude/agents/`) are specialists for *design and review* depth. Auto-delegated on their `description`, or forced with "use the `<agent-name>` agent":
  - `submission-reviewer` — audits work against the actual rubric: does it beat a one-shot, can Omar explain it, does it satisfy the seven numbered requirements, is the demo narrative coherent. **Run before submission; it is the closest thing here to the real reviewer.**
  - `voice-latency-engineer` — latency budget, per-stage instrumentation, where the time actually goes, what to try next
  - `voice-ux-critic` — turn-taking, barge-in, visible state, failure-path UX; the "is the voice experience delightful" line of the rubric
  - `guardrails-engineer` — **owns the deep dive.** The grounding gate, the two-register contract, refusal correctness, injection resistance, and the adversarial eval. Consult before any claim about how well the guardrails work.
- **Precedence:** skill > agent > ad-hoc. If both match, run the skill.

## Review gates that are never skipped

1. **Any code that touches a provider credential** → the key must be server-side only. A provider key reachable from browser JS is a blocking issue (`AGENTS.md` §Invariant 1). The deployment URL goes to a stranger.
2. **Any change to the voice pipeline** → a measured latency run before it's called done (`AGENTS.md` §Invariant 2). Numbers, not adjectives.
3. **Any external tool call** → defined behavior for failure, timeout, and empty result, and Sarjy must say it doesn't know rather than improvise (`AGENTS.md` §Invariant 6).
4. **Any change to what gets remembered** → prove it survives a fresh session. The "what's my favorite color" test is a graded requirement, not a nice-to-have.
5. **Before any submission or demo** → `/demo-check` plus the `submission-reviewer` agent.

## Verification before done

Never claim work is complete without evidence. Once the project is scaffolded that means `npm run typecheck && npm run lint && npm test` (or the `make` equivalents) **plus an actual end-to-end voice turn** for anything touching the pipeline. Unit tests do not catch a broken microphone path. Show the output; don't assert it passed.

A `Stop` hook runs the validation matrix automatically and blocks the turn if it fails. It no-ops while the project is pre-scaffold and adapts to either a Node or a Python stack.

## Plan mode

- Use it for verification and measurement steps too, not only implementation.
- Write detailed specs upfront — three part-time days means ambiguity resolved late is scope lost.
- If execution drifts from the approved plan, stop and re-plan rather than improvising.

## Subagents

- Use the Agent tool for research, provider comparison, and parallel analysis — especially provider/latency research, which would otherwise flood the main context.
- One focused task per subagent.
- Provider facts move fast. Anything about model ids, pricing, free-tier limits, or published latency must be **researched, not recalled** — the knowledge cutoff is behind the market here.

## Memory

Learn from corrections via auto-memory. High-signal things to record: decisions Omar closes (especially the deep-dive track), provider facts confirmed by measurement rather than marketing, scope boundaries he enforces, and anything Sarj tells him in reply to an update.

## Demand elegance (balanced)

For non-trivial changes, pause and ask "is there a more elegant way?" If a fix feels hacky, re-implement it properly — this code gets read by a reviewer. Skip for trivial, obvious fixes; don't over-engineer a three-day project.

## Path-scoped rules

These load themselves when you touch matching files. Don't re-read them manually.

| Rule | Loads when you touch |
|---|---|
| `rules/workflow.md` | always |
| `rules/tools/grounding-gate.md` | tools, prompts, agent code — **the deep dive's contract** |
| `rules/tools/vendor-client.md` | vendor/provider clients — quota, resolution order, reserve |
| `rules/voice/pipeline.md` | pipeline, STT/TTS, websocket code |
| `rules/voice/browser-audio.md` | frontend TypeScript — capture, playback, permissions |

## Still to be written

- `.claude/skills/` — stack-specific procedures once the tree exists (scaffold, deploy, add-a-tool)

When a decision closes, come back and write the corresponding rule. An outdated rule is worse than a missing one.
