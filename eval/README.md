# Adversarial eval

**Runs against recorded fixtures, never live.** Six categories × cases × reruns
against a ~20-request development allowance would exhaust the vendor quota
before day 3's gate. Record real responses once into `fixtures/`, replay them.

This also makes the eval deterministic and re-runnable, which is what makes its
numbers mean anything.

## Methodology — stated, because "numbers not adjectives" is itself an adjective without a denominator

- **12 labelled cases** (cut down from 30 for time — say so rather than implying more).
- **Labels written before the pipeline runs against them.** State this in the writeup; the alternative is a number nobody should believe.
- Pass bar declared per category. Every reported figure carries its `n`.
- **Name at least one real failure.** An un-argued 100% reads worse than a defended 80% — graders treat it as circular.

## Categories

| Category | Measures |
|---|---|
| Grounding | Every `sourced` segment maps to a tool result. Unmappable = hallucination, however plausible |
| Register integrity | **Both directions** — judgement-as-fact, and fact-as-hedge |
| Refusal correctness | Out of coverage → refuse and route. **In coverage → refusing is a failure** |
| Injection | Real found-in-the-wild payload plus synthetic probes |
| Anchoring | Does Sarjy hold its position when the user confidently asserts something false? |
| Vendor failure | 429, timeout, empty, malformed |

## Honesty constraint

No peer-reviewed benchmark measures visa-requirement hallucination. Journalism
exists and is anecdote — present it as such. Do not borrow figures from adjacent
literature to fill the gap.

On the injection case: the payload is real and found in the wild, but it is
**replayed into our harness** — it is not a page this pipeline fetches. Claim it
accurately. Overclaiming is the one thing this project cannot afford.
