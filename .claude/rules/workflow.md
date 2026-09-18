# Workflow

Always loaded. The process discipline for non-trivial work on Sarjy.

**When to use:** feature work, architecture decisions, anything touching the voice pipeline.
**Skip for:** trivial edits (typos, a one-line fix, doc tweaks).

## Phases: Plan → Spec → Build → Measure → Document

**1. Plan.** The brief recommends a short PRD/TDD *before* implementation, and grades planning. Non-trivial work belongs to a plan in `docs/plans/`. If there is no plan, write one and get Omar's sign-off before coding. Plans state: what we're building, what we're explicitly not, which open decisions it depends on, and how it will be demonstrated.

**2. Spec.** For a discrete feature, `{feature-name}.spec.md` (gitignored, repo root): scope in / scope out, files it will touch, failure modes, and how it will be verified. Break it into tracked todos and mark them complete as you go, not in a batch.

**3. Build.** Types and interfaces first, then signatures with doc comments, then bodies one function at a time. Failure paths before happy paths — this is a voice app, and the failure paths are what break demos.

**4. Measure.** Not "test" — *measure*. Every turn through the voice pipeline emits per-stage timings. A feature isn't done until you've shown what it did to the numbers. Latency regressions are bugs even when the chosen deep dive isn't latency.

**5. Document.** `docs/PRs/PR_{FEATURE_NAME}.md` — Summary, Problem, Solution, Changes, How to Test, Changelog. Anything demo-relevant also gets a line in the running demo script. **Do not commit — ever. Omar commits.**

## Three days, part-time

Time is the binding constraint, and it is the reason most take-homes fail.

- **Cut scope, never cut the deliverable contract.** The seven numbered requirements in `AGENTS.md` are the floor. Polish above the floor is negotiable; the floor is not.
- **Deploy on day one, before the app is good.** A working deployment of a bad app de-risks requirement #4 entirely. A great app that has never been deployed is a zero.
- **Timebox the deep dive** and stop when the evidence is good enough to present. "What I'd do with another week" is an explicitly invited answer — an unfinished thread you can articulate beats a finished thread nobody asked for.
- When a task grows past its estimate, say so and re-plan. Don't silently absorb it.

## Open decisions are not yours to close

Everything in `AGENTS.md` §Open decisions is genuinely undecided, starting with the deep-dive track.

- **Prefer the path that doesn't need the answer.** Build against the provider interface with a fake; the real provider slots in later.
- **If you must assume, state the assumption in your summary** and add it to `docs/decisions/` as an open item.
- **If proceeding under any assumption would make the work useless if wrong, stop and ask.** The deep-dive track is the main case of this — almost nothing substantial should be built before it's chosen.

## Every turn is a demo

The reviewer will use this live, and Omar will be asked how it works.

- Prefer the implementation you can explain over the one that scores marginally better. **Understandability outranks cleverness here** — it is literally on the rubric.
- If a library does something magic, know what the magic is or don't use it.
- Keep a running demo script: what to say to Sarjy, in what order, to show each requirement. Update it as features land.
- After a change to the pipeline, actually run a voice turn end-to-end. Unit tests don't catch a broken microphone path.

## Anti-patterns

- Coding before the deep-dive track is chosen
- Building a second deep dive instead of finishing the first
- Retrofitting instrumentation at the end
- A provider SDK imported outside its adapter
- A provider API key reachable from the browser
- Claiming "it's fast" / "it works" without the output
- Leaving the deployed URL broken overnight
- Silence toward Sarj for more than a day of work
