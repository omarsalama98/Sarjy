---
name: block-a-design-choices
description: Block A (the deep dive) — the non-obvious design choices made in its plan and the gate holes found while writing it, 2026-09-20
metadata:
  type: project
---

Block A's plan (`docs/plans/blocks/A-grounded-answers.md`) made several choices that deviate
from the written design. Each was deliberate; do not silently revert one.

**Why:** the plan's Decisions page is the only part Omar reviews before the block runs end to
end, so anything that departs from the TDD or a rule file has to be visible there.

**How to apply:** if a later block or a review contradicts one of these, check the plan's
§Decisions and §Upstream corrections before "fixing" it.

- **Call 2 is a fresh stateless interaction, not a `function_result` replay.** This makes
  `day1-spikes.md` S4 Q3 (which came back inconclusive — `"Invalid input received."`) moot
  rather than open. The tool body goes in as a delimited `<tool_result>` data block.
- **Resolution order was reordered** to warm cache → live → map → CSV → refuse. The rule file's
  cost-only waterfall (map → cache → CSV → live) means the live call never fires, because the
  CSV covers every pair — and requirement #3 is a *live* API call. The rule file was not edited;
  an amendment is drafted in the plan.
- **Two gate holes found while reading the contract.** (1) A `sourced` segment naming a
  free-text vendor field passes all four documented rules and substitutes an injection payload
  verbatim into Sarjy's speech — closed by mapping no free-text field at all, plus a value
  shape check. (2) Rule 3 ("no digit") is bypassed by spelling the number out — closed by a
  number-word check. Both are additions to the documented four rules.
- **`sourced`-as-hedge is not gate-enforceable** and the plan says so out loud. Only a weak
  deterministic proxy exists (a tool result stored + zero sourced segments → flag the turn).
  Do not let the writeup imply the gate catches direction 2.

Related: [[cascaded-is-closed]], [[travel-buddy-api]]
