---
name: master-plan-estimates-run-low
description: MASTER-PLAN.md block estimates run ~2.5x low once a block is planned in detail; and its Block B "drop to session-only" fallback trigger does not actually work
metadata:
  type: project
---

Two things about `docs/plans/MASTER-PLAN.md` that its own text does not tell you.

**1. Its per-block estimates run roughly 2.5x low once the block is planned file-by-file.**
Block A: estimated in the restructure, planned at ~8.7 h. Block B: estimated ~2 h, planned at
~5.3 h. Both overruns were found at planning time, not during implementation.

**Why:** the master plan was written before the previous block's actual output existed, so it
prices the idea rather than the wiring (protocol bump on both sides, test fakes that must gain a
parameter, a deploy, an end-to-end voice run).

**How to apply:** when planning a block, do the task-by-task arithmetic and put the honest number
on the Decisions page rather than matching the master plan's figure. Pair it with a pre-committed
cut ladder that names a floor which is never cut. Omar reads the Decisions page only, so a buried
overrun is an invisible one.

**2. The Block B trigger "memory drops to session-only, requirement #2 answered from the anonymous
tier" is not a viable fallback.** `frontend/src/net/connection.ts` keeps `sessionId` in a private
field, not `localStorage`, so a page reload mints a brand-new session. Session-only memory
therefore fails the graded "told in one session, answered in a fresh one after a reload" test
outright. The nearest face-saver is persisting `session_id` in `localStorage` (survives a reload,
not a container restart) — and it should be labelled as a face-saver, not an answer.

Related: [[[B-memory plan]]] at `docs/plans/blocks/B-memory.md`.
