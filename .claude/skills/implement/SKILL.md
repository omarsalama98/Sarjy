---
name: implement
description: Build a block from its plan, or make a fix outside the block flow. Use whenever asked to build, add, or fix anything beyond a trivial edit — it carries the process, the provider boundary, and the validation matrix.
argument-hint: [feature description]
---

# Implement

Rules auto-load when you touch matching files. Your job is the process.

## Steps

1. **Find the plan.** Work here belongs to a block: `docs/plans/blocks/NN-name.md` is the contract, `docs/plans/MASTER-PLAN.md` says which block and what its gate is. **If there is no block plan for this work, stop and say so** — the plan gets written first, by the `block-planner` agent.

2. **Restate scope in / scope out** from the plan before touching anything. "Scope out" is what stops the work expanding.

3. **Check the open decisions.** Does this depend on anything still open in `AGENTS.md` or the TDD's §Open? If so, build against the provider interface and a fake — don't wait, and don't silently adopt a provider behaviour and build on it.

4. **Types and interfaces first.** Domain types, provider interfaces, closed unions for pipeline state. Schema-validated shapes at every boundary — especially anything crossing to the client or coming back from a model. No function bodies yet.

5. **Signatures and contracts.** Planned signatures with doc comments: purpose, inputs, outputs, **failure modes and timeouts**. Step-by-step TODO comments in the bodies. No logic yet.

6. **Checkpoint — pause and verify before writing logic:**
   - Do the types model the conversation state honestly, including the in-between states (listening, thinking, speaking, interrupted)?
   - Is any provider SDK imported outside its adapter?
   - Could any provider key reach the browser? (Blocking — `AGENTS.md` §Invariant 1.)
   - Does every external call have a timeout and a defined empty/failure result?
   - Is the new work on the latency path? If so, where does its instrumentation go?

   Ask if something is off. This checkpoint is cheaper than the rework.

7. **Failure paths first, then the happy path.** Voice apps break in the demo at exactly the places nobody implemented. Mic denied, permission revoked mid-session, socket drop, 429, empty transcript, barge-in.

8. **Implement.** One function at a time, following the auto-loaded rules. Keep it explainable — Omar walks a reviewer through this code (`CLAUDE.md` §The rubric is the spec).

9. **Validate.**
   - `npm run typecheck && npm run lint && npm test` (or the `make` equivalents)
   - Touched the voice pipeline → **run an actual end-to-end voice turn** and a `/measure` run. Unit tests don't catch a broken microphone path.
   - Touched memory → prove a fact survives a fresh session.
   - Touched a tool call → verify the failure path says "I don't know" rather than improvising.
   - Touched anything credential-adjacent → confirm the key is server-side only.

10. **Document.** `docs/PRs/PR_{FEATURE_NAME}.md`, and update the demo script if the change is demo-visible. Draft a conventional-commit message for Omar. **Do not commit — ever.**

11. **Report against the gate.** The block's gate is an observation, not a feeling. Show the output that proves it, or say plainly which part of it is not met yet.

## Anti-patterns

- Building without a block plan
- Improvising around a plan that turned out wrong, instead of stopping and saying so
- A provider SDK, model id, or provider DTO outside its adapter
- Any provider key reachable from client code
- An external call with no timeout and no defined failure behavior
- Adding to the latency path without instrumenting it
- Claiming done without the validation output and, for pipeline work, a real voice turn
- Code Omar hasn't been walked through
