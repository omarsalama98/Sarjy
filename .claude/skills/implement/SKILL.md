---
name: implement
description: Implement a feature or bug fix in Sarjy. Use whenever asked to build, add, or fix anything beyond a trivial edit — it orchestrates the workflow phases, the provider boundary, and the validation matrix.
argument-hint: [feature description]
---

# Implement

Rules auto-load when you touch matching files. Your job is the process.

## Steps

1. **Plan intake.** Identify the governing plan (`docs/plans/PRD.md` or a feature plan) and restate scope in/out. If none exists and the work is non-trivial, write one first (`/prd`) and get sign-off. **If the deep-dive track is still open, stop** — say so rather than building around it.

2. **Check the decisions.** Does this depend on anything open in `AGENTS.md`? If so, build against the provider interface and a fake — don't wait, and don't silently pick a provider's behavior and build on it.

3. **Spec.** For non-trivial work, `{feature-name}.spec.md` per `workflow.md` Phase 2. Track milestones as todos and close them as you go.

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

## Anti-patterns

- Coding before the deep-dive track is chosen
- A provider SDK, model id, or provider DTO outside its adapter
- Any provider key reachable from client code
- An external call with no timeout and no defined failure behavior
- Adding to the latency path without instrumenting it
- Claiming done without the validation output and, for pipeline work, a real voice turn
- Code Omar hasn't been walked through
