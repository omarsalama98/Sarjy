# TDD walkthrough — open decisions

**Date:** 2026-09-19 · **Status:** live document, updated as we walk the TDD section by section
**Source:** `docs/plans/TDD.md` · **Contract:** `.claude/rules/tools/grounding-gate.md`

## Summary

### Decided

| # | Decision | §ated |
|---|---|---|
| 1 | Gate gains a **placeholder rule + digit rule** — no bare digits in a `sourced` segment | §1 |
| 2 | Retry split: schema failure → one repair · gate rejection → none | §1 |
| 3 | **We normalise the vendor response ourselves**; we own the field paths | §2 |
| 4 | LLM judge **in the eval only** — hand-rolled, RAGAS-style, paper cited | §2 |
| 5 | Judge validated against hand labels; **agreement rate reported** beside every figure | §2 |
| 6 | Eval locked at 12 hand-labelled cases, 4 judge categories | §2 |
| 7 | **Deterministic assertion tests** — Tier A (no model, every commit) + Tier B (golden prompts) | §3 |
| 8 | **Gate per segment, not per response** — NDJSON out, ~800 ms recovered | §4 |
| 9 | **TTS buffered per segment** — settles streamed-vs-buffered by dissolving it | §4 |
| 10 | Both Gemini model IDs verified correct — **no rework** | §5 |
| 11 | EEA/UK free-tier exposure → **document in the writeup**, do not raise with Sarj | §5 |
| 12 | Spike Groq `orpheus-arabic-saudi` before committing P2 Arabic to it | §5 |
| 13 | Memory: **two tiers** — anonymous session-only, signed-in persisted | §6 |
| 14 | Store: spike `modal.Dict` vs Volume — **on day 2, not day 1** | §6, §7 |
| 15 | Day 1 runs **three** spikes, not six: WebSocket · browser audio · TTS TTFB | §7 |
| 16 | Identity: **voice-first greeting + name/PIN sign-in**, typed fallback always visible | §6 |
| 17 | **NDJSON over `response_format`** — the only way to get per-segment gating | §10 |
| 18 | `routing_region`: **measure `us-east` vs `eu-west` on day 1** before the irreversible pick | §11 |
| 19 | `@modal.concurrent` + async handler — **scaffold bug, already fixed** | §11 |
| 20 | `modal.Dict` confirmed durable; SQLite-on-Volume ruled out — **day-2 spike retired** | §11 |

### Still open

| Open | Blocks | Who decides |
|---|---|---|
| Sarjy's voice and persona | Demo feel | **Omar** |
| Sarjy's voice and persona | Demo feel | **Omar** |
| Reviewer's GitHub username · API keys | Submission | Sarj — email drafted, **unsent** |

### 🚨 The honest status

**The design is materially better than it was. The schedule is materially worse.**

This review closed a real hole in the deep dive, verified every provider fact, and found ~800 ms
of latency. It also added roughly **seven hours of work** to a plan the viability review already
put at about **2× over**:

| Added | Est. |
|---|---|
| Normalisation layer | 1.5 h |
| Assertion tests (Tier A + B) | 1.75 h |
| LLM judge + agreement check | 2.3 h |
| Identity tiers | 0.75 h |
| Per-segment gating + TTS retry handling | ~1 h |

**The cut list from the viability review was never applied.** Until it is, the plan is a wish.
That is the next action — not more design.

---

## §0 — The map

| # | Item | Kind |
|---|---|---|
| 1 | **Sourced segments can still contain free-text facts** | 🚨 hole in the deep dive |
| 2 | Memory store: "open" in the stack table, "**Decided:** SQLite" in §Memory | stale contradiction |
| 3 | Gate failure: rule says "one repair retry", TDD says "deliberately no re-ask" | stale contradiction |
| 4 | Aladhan still wired in via Wikipedia coordinates; cut list says drop it | cut list not applied |
| 5 | Images read as P0-ish in the TDD, P3 in the PRD | cut list not applied |
| 6 | Eval: 30 cases in the TDD, 12 in `eval/README.md` | cut list not applied |
| 7 | How does the model learn which field paths exist? | undesigned |
| 8 | Expected **rejection rate** of the gate | unmeasured, demo-critical |
| 9 | One LLM call or two? (cache hit vs miss) | latency decision |
| 10 | TTS streamed vs buffered | latency vs barge-in trade |
| 11 | Silence threshold — 600 ms in `turn.ts`, reason not recorded | product decision |
| 12 | Model IDs `gemini-3.5-flash-lite` / `gemini-3.1-flash-tts-preview` | needs verifying; knowledge cutoff is behind |
| 13 | ≤ 2.5 s p50 vs two full completions + a vendor call | probably optimistic |
| 14 | Modal WS lifetime, colour legend, `language=ar`, Gemini free tier | day-1 spikes, already flagged |

---

## §1 — The gate has a gap you can drive a truck through

The TDD's claim is strong, and correct in spirit:

> the model **cannot state a number it did not select from a response**, because it never
> writes numbers at all.

Nothing in the spec enforces that. Consider this model output:

```json
{"kind": "sourced",
 "text": "You'll need a tourist visa for up to 90 days.",
 "tool_call_id": "tb_1",
 "fields": []}
```

Zero placeholders → nothing to resolve → `resolve()` finds nothing absent → **it passes, and
we staple a real citation onto it.** The tool said 30.

This is exactly the citation-chip failure the TDD says it prevents. The gate as specified
validates *the fields the model declared*. It never validates *the text the model wrote*.

It is also the first thing a sharp reviewer pokes, because the TDD advertises the guarantee
in bold.

### The fix: two more deterministic rules, both one-liners

1. **A `sourced` segment must contain at least one placeholder.**
   No placeholder means it is not sourced — it is judgement, or it is invention.

2. **No digit may appear in a `sourced` segment outside a placeholder.**
   Numbers are where the harm lives: durations, passport validity months, fees.
   `"for up to 90 days"` dies at the gate. `"for up to {…primary_rule.duration}"` lives.

Rule 2 is the demo beat. You can *show* it: feed a turn where the model writes the number
itself, watch the gate kill the segment, then run the same turn where it selects the field.
That is a twenty-second clip that makes the difference between a guardrail and a citation
chip visible — otherwise a hard thing to convey in a Loom.

### What the digit rule does not catch

Categorical claims written as prose — "you'll need an **eVisa**" as free text rather than
`{…primary_rule.name}`. Catching that is NLP, not a one-liner.

The honest line is better than a fuzzy matcher you cannot defend under questioning:

> I enforce the class of claim where being wrong makes someone miss a flight — the numbers —
> deterministically. Categories go through field selection too, but the digit rule is the
> hard backstop.

### Item 7 — nobody has designed how the model learns the paths

For the model to write `{visa_rules.primary_rule.duration}`, it has to know that path exists.
Going from nested JSON to a correct dotted path is an inference step models fumble, and every
fumble is a rejected segment. A demo full of *"I couldn't confirm that part"* reads as broken,
not as rigorous.

So don't make it infer. Flatten the response ourselves and hand it the literal catalog:

```
visa_rules.primary_rule.name      = "eVisa"
visa_rules.primary_rule.duration  = "30 days"
visa_rules.passport_validity      = "6 months"
```

Same information, zero inference.

**The counter-argument for measuring first:** raw JSON costs nothing to try, and the flattener
is machinery we might not need. If the model gets paths right 95% of the time, the catalog is
premature. If it gets them right 60% of the time, we needed it and now we have the number that
proves it.

### Item 8 — rejection rate is the number that decides the deep dive

Whichever path we take, **measure it on day 2**. Rejection rate is arguably the most important
figure in the whole project: it is the *"grounded and still useful"* axis. A gate that rejects
nothing is theatre; a gate that rejects a third of segments is a broken product. The number is
the evidence that it is neither.

### Item 3 — the retry contradiction, resolved

The rule file says "one repair retry". The TDD and `gate.py` say "deliberately no re-ask".
Both are half right. Split by failure type:

| Failure | Behaviour | Why |
|---|---|---|
| **Schema** — malformed JSON, wrong shape | One repair retry | Rare with `responseSchema`, cheap, and this is what the rule file means |
| **Gate rejection** — bad path, stray digit | No retry. Strip and say so | A second completion to re-litigate a fact is exactly what the TDD is right to refuse |

Reconciles all three documents without weakening either position.

---

## §2 — Normalised context, and an LLM judge that never touches the hot path

Two proposals from Omar, both accepted, one with a change.

### Proposal 2 (taken as-is): we format the context ourselves

We know the vendor's structure and we know how the data should be presented, so the raw
Travel Buddy body never reaches the model. A normalisation layer sits between the vendor
client and the prompt and emits a schema **we** define:

```
visa.type               = "eVisa"
visa.duration           = "30 days"
visa.passport_validity  = "6 months"
visa.registration       = null
source.layer            = "live"
source.retrieved        = "2026-09-19T08:14Z"
```

This quietly settles item 7 — *how does the model learn the valid field paths* — and settles it
better than either option I offered:

| Benefit | Why it matters |
|---|---|
| **Paths are ours, stable and short** | `visa.duration`, not `visa_rules.primary_rule.duration`. Fewer tokens, far fewer path errors |
| **Vendor schema changes are absorbed** | A renamed key breaks one mapping function, not the gate, the prompt, and every eval fixture |
| **Eval fixtures survive** | Recorded fixtures are in our shape, so they stay valid across vendor drift |
| **The catalogue *is* the context** | No separate flattener to build. The thing we hand the model already is the path list |
| **CSV fallback and live API converge** | Both normalise into the same shape, so the gate and prompt do not care which layer answered |

That last row is the real prize: the vendored CSV fallback and the live vendor response become
the *same object* with a different `source.layer`. One code path, one prompt, one set of paths.

⚠️ **The one new failure surface:** if the normaliser silently drops a field the vendor
returned, the model cannot cite what it cannot see — and we would never notice. Log unmapped
keys on every call. Two lines, and it is the difference between a normaliser and a lossy filter.

### Proposal 1 (accepted, with a change): LLM-as-judge, in the eval only

The instinct is right and it fills a real gap. The digit rule is deterministic and unfoolable,
but it is blind to exactly the failures that are most interesting to talk about:

| Failure | Caught by | Why |
|---|---|---|
| `"visa for up to 90 days"` | **Digit rule** | Bare digit in a sourced segment |
| `"you'll need an eVisa"` as prose | **Judge** | Categorical claim, no digit, NLP problem |
| Recommendation dressed as a sourced fact | **Judge** | Register integrity |
| Refusing a pair the sources *do* cover | **Judge** | Refusal correctness, the evasion direction |
| Holding position against a confident false assertion | **Judge** | Anchoring |

### The framing that makes this strong rather than self-defeating

The obvious objection, and a reviewer will raise it: *"your guardrail against model
hallucination is validated by… another model?"*

The answer is that they operate at different layers, and the boundary is absolute:

> **Deterministic code gates what the user hears. The judge only measures, offline, the
> things determinism cannot see. The judge never blocks a segment and never sits on the
> latency path.**

That is a better answer than either alternative. "I only have a regex" is thin; "my guardrail
is an LLM" is the thing this project exists to argue against. Two layers with a hard boundary
is the sophisticated position, and it is one sentence long.

### RAGAS the library, or RAGAS-style hand-rolled?

**Recommendation: hand-rolled, borrowing the concepts, citing the paper.**

Three reasons:

1. **Half of RAGAS is inapplicable by construction.** `context_precision` and `context_recall`
   measure a *retriever* returning k chunks. We make one deterministic API call. There is no
   retrieval to evaluate. Only `faithfulness` and `answer_relevancy` map onto what we do.

2. **Our most interesting metrics are not in RAGAS.** Register integrity and refusal
   correctness — including the evasion direction — come from our two-register contract. They
   do not exist in a generic RAG framework, and they are the deep dive.

3. **Explainability is a graded requirement.** `CLAUDE.md`: *"If you use a library's magic,
   explain the magic in a comment or pick something plainer."* RAGAS's faithfulness is a
   specific claim-decomposition prompt chain. Under questioning, "I ran RAGAS" is a weaker
   answer than "I decompose each answer into claims and ask a judge whether each is entailed
   by the context — the RAGAS faithfulness formulation — and here is the prompt."

Cost is also against it: a judge runner is roughly two hours; RAGAS is three to four once the
dependency and its retrieval-shaped assumptions are wrestled into place, on a plan already
running about 2× over.

**Say "RAGAS-style faithfulness" in the writeup and cite the paper.** That earns the
recognition without the dependency or the explainability debt.

### The thing that makes the judge credible: validate the judge

An unvalidated LLM judge is just a second unverified opinion with a percentage attached.

The fix is nearly free, because the labels already exist in the plan: the eval's cases are
hand-labelled **before** the pipeline runs against them. Run the judge against those same
labels and report **judge-versus-human agreement** alongside every judge-derived number.

> *"The judge agrees with my hand labels on 11 of 12 cases. Here is the one it got wrong, and
> why."*

That single sentence is worth more than any score the judge produces, and it is the difference
between a number a grader believes and one they treat as circular.

### What else we want — and what we deliberately do not

**In:**

| Component | Cost | Why it earns its place |
|---|---|---|
| Normalisation layer | ~1.5 h | Owns the paths, unifies live + CSV, absorbs vendor drift |
| Digit + placeholder rules | ~20 min | Closes the §1 hole; the visible demo beat |
| Offline judge, 4 categories | ~2 h | Measures what determinism cannot see |
| Judge-vs-human agreement | ~20 min | The only thing that makes judge numbers believable |
| Untrusted-input delimiting | already planned | Injection category |

**Out, deliberately:**

| Not doing | Why |
|---|---|
| RAGAS as a dependency | Retrieval metrics do not apply; explainability debt |
| Embeddings / semantic similarity scoring | Nothing to embed. One API call, not a corpus |
| Judge anywhere on the latency path | Contradicts the thesis; adds a full completion per turn |
| Judge as a second gate | Same. The gate is deterministic or it is not a gate |
| More than ~12 eval cases | Viability cut list. 12 hand-labelled beats 30 unlabelled |

**The shape in one line:** deterministic enforcement where the harm is binary, an offline judge
where it is not, and a stated agreement rate so the judge's numbers are not taken on faith.

---

## §3 — The assertion layer, and why the gate is what makes it possible

Omar's addition, and it completes the picture: **deterministic tests we can verify ourselves.**
A fixed prompt, a recorded fixture, and an assertion that the answer contains a specific
substring or number.

This sits *under* the judge and is the layer that runs on every commit.

### The non-obvious part: an LLM pipeline is not normally substring-testable

Assertion tests usually fail against a language model because phrasing varies run to run. Here
they do not, and the reason is the architecture itself:

> **The model never writes the number. The gate substitutes it from the fixture.**
> So the number in the output is deterministic even though the model is not.

`assert "30 days" in rendered` is stable across runs, across phrasings, across temperature —
because `"30 days"` came from `fixtures/tb_SA_JP.json`, not from the model's mouth. The same
design decision that makes the guardrail real is what makes it testable.

That is a strong walkthrough beat on its own: *the guardrail bought us regression tests for
free.*

### Three layers, and only two of them need a model

| Layer | Runs | Model in the loop? | Catches |
|---|---|---|---|
| **1 · Gate** | Runtime, hot path | No | Fabricated values, bad field paths, bare digits |
| **2 · Assertions** | Every commit, `make test` | Tier A: no · Tier B: yes | Regressions, structural violations, wrong values |
| **3 · Judge** | Offline, before submission | Yes | Register integrity, refusal correctness, anchoring |

Layer 2 splits into two tiers with very different costs:

**Tier A — pure unit tests, no model, instant and free.** Hand-construct `Segment` objects,
feed them into `resolve()` with a fixture, assert the outcome. This is where the digit rule,
path resolution, and the absent-vs-null distinction get tested. Dozens of these, milliseconds,
zero tokens.

```python
def test_bare_digit_in_sourced_is_rejected():
    seg = Segment(kind="sourced", text="visa for up to 90 days", tool_call_id="tb_1")
    with pytest.raises(GateRejection):
        resolve([seg], fixtures.SA_JP)

def test_substituted_value_comes_from_the_fixture():
    seg = Segment(kind="sourced", text="visa for up to {visa.duration}",
                  tool_call_id="tb_1", fields=("visa.duration",))
    assert resolve([seg], fixtures.SA_JP)[0].text == "visa for up to 30 days"

def test_absent_path_rejects_but_null_path_resolves():
    ...  # null is an answer; missing is a rejection
```

**Tier B — golden prompt tests, model in the loop, a handful only.** Fixed prompt + recorded
vendor fixture → real completion → gate → assert. Slower and costs tokens, but it is the only
thing that catches a prompt regression.

```python
def test_sa_to_japan_states_the_real_duration():
    out = run_turn("Do I need a visa for Japan?", fixture="tb_SA_JP")
    assert "30 days" in out.text          # from the fixture, via the gate
    assert "90 days" not in out.text      # the plausible wrong answer
    assert all(s.citation for s in out.segments if s.kind == "sourced")
```

### Keeping Tier B from becoming flaky

One rule, and it is the whole trick:

> **Assert only on strings the gate substituted. Never assert on the model's own prose.**

`"30 days"` is guaranteed. `"You'll need an eVisa for up to 30 days"` is not — the model may
open with "Japan's rules are straightforward" tomorrow and the test breaks for no reason. Every
flaky assertion test in this project will come from forgetting that line.

Structural assertions are also fully deterministic and need no model behaviour at all:

- every `sourced` segment carries a citation
- every citation's `tool_call_id` exists in this turn's tool results
- `source.layer` is stated on every answer
- no `judgement` segment carries a citation

### Negative assertions are where the value is

The positive case is easy and the model usually gets it right. Encode the *wrong* answers:

| Assertion | Guards against |
|---|---|
| `"90 days" not in out` | The plausible fabricated duration |
| `"visa-free" not in out` for a pair that is not | Category inversion |
| Another country's fixture value absent | Cross-turn contamination |
| Reviewer B's passport absent after a session switch | The identity bug in §Memory |

That last one is worth a test on its own — a shared-memory failure between two anonymous
sessions is a live demo death, and it is trivially assertable.

### Where this lands in the plan

`make test` runs Tier A and the structural assertions on every commit — fast, free,
deterministic. Tier B runs on demand and before submission. The judge runs once, before the
writeup, and its numbers go in the writeup with the agreement rate beside them.

**Cost:** Tier A ~1 h, Tier B ~45 min, and it buys back time immediately — every gate change
after that is verified in seconds instead of by hand.

---

## §4 — Latency: where the deep dive actually costs you, and how to get most of it back

> **Numbers below are derived estimates, not measurements.** Provider facts are being verified
> separately; TTS time-to-first-byte is unmeasured in our research and is the single largest
> unknown. Every figure here gets replaced by a measured one after the day-1 spike.

### The chain, and the honest arithmetic

A cache-miss turn is five provider round trips in strict series:

```
endpoint → STT → LLM#1 (tool args) → vendor → LLM#2 (segments) → gate → TTS → audio
```

| Stage | Estimate | Note |
|---|---|---|
| Endpointing | ~600 ms | Pure waiting. A product decision, not a technical cost |
| STT | ~300 ms | Groq runs ~216× real-time; this is almost entirely network |
| LLM #1 — tool args | ~450 ms | Short output (~30 tokens), so mostly TTFT |
| Vendor round trip | ~300–800 ms | External API, no CDN guarantee. Wide band |
| **LLM #2 — segments** | **~1,200 ms** | **~200 tokens of structured output, generated in full** |
| Gate | < 5 ms | Deterministic substitution |
| TTS TTFB | ~500 ms *(assumed)* | 🚨 **Now known to be unknowable from docs.** Anecdotal reports span sub-2 s to 10–20 s. See §5 |
| **Total** | **~3.4–3.9 s** | Against a stated target of ≤ 2.5 s |

🚨 **The TTS row is now the whole ballgame.** Verified research (§5) found no published Gemini
TTS latency figure and forum reports ranging from sub-2 s to 10–20 s on the same model within
two weeks. If TTFB is 2 s, every number in this table is wrong and the architecture needs
rethinking. **This is the day-1 spike that matters most** — it is a fourth spike, added to the
three the TDD already names.

A cached turn drops LLM #1 and the vendor call: **~2.6 s**, against a stated target of ≤ 1.5 s.

**Both targets are optimistic.** Not by a little — the cached case misses by ~1.1 s.

### The dominant term is the deep dive itself

After endpointing, the largest cost is LLM #2 generating its *complete* structured response
before anything can be spoken. That is not incidental — it is the gate's requirement. The gate
cannot validate a citation inside a sentence that has not finished arriving.

So the honest framing, and it is a good answer to *"what did your guardrail cost you?"*:

> The gate needs complete text before TTS can start, so I pay full generation instead of
> time-to-first-token. That is roughly 800 ms. Here is how I got most of it back.

### The fix: gate per segment, not per response

The response is already a *list* of segments. Nothing requires waiting for the last one to
gate the first.

Have the model emit **one segment per line** rather than a single JSON array:

```
{"kind":"sourced","text":"You'll need {visa.type} for up to {visa.duration}.","tool_call_id":"tb_1"}
{"kind":"judgement","text":"November is a good month for Kyoto — the crowds thin after the leaves turn."}
```

Then: split on newline → validate the complete line → gate it → hand it to TTS, while the next
segment is still generating.

| | Before | After |
|---|---|---|
| Time to first audio (LLM#2 portion) | full completion ~1,200 ms | first segment ~400 ms |
| **Recovered** | | **~800 ms** |

Two reasons this is the right shape rather than a trick:

1. **Incremental JSON-array parsing is fiddly; newline-delimited is not.** Split, parse,
   validate against the segment model. Roughly twenty lines, and every one of them is
   explainable live.
2. **Per-line validation is stronger than per-response validation,** not weaker — each segment
   is schema-checked on its own, and a malformed line fails in isolation rather than taking the
   whole response with it.

⚠️ **Check before committing to this:** whether Gemini's structured-output mode (`responseSchema`)
can be made to emit newline-delimited objects, or whether we drop `responseSchema` at runtime and
validate each line with Pydantic instead. The second is fine and arguably better — but it is an
assumption until tested.

### This also settles item 10 — buffered or streamed TTS

It dissolves the question. **Buffer per segment.**

A single segment is one or two sentences, so its audio is short enough that buffering it costs
almost nothing — and we avoid true streaming's complexity entirely while capturing nearly all
of its benefit, because the *next* segment is generating while the current one plays.

It makes barge-in cleaner too: the playback queue is a list of short, complete buffers. Dropping
them is trivial, and there is no mid-stream cancellation to get wrong.

> Simplicity and speed usually trade against each other. Here segmentation gives both, and it
> falls out of the guardrail design rather than being bolted on.

### Revised, defensible targets

| Turn | Estimate | Was |
|---|---|---|
| Cached, segment-streamed | **~1.8 s** | ≤ 1.5 s claimed |
| Cache-miss, segment-streamed | **~2.8 s** | ≤ 2.5 s claimed |
| **Perceived first sound** (acknowledgement during lookup) | **~1.0 s** | — |

State all three. Never let the perceived number stand in for the measured one — report it beside,
never instead.

### The other levers, ranked

| Lever | Saving | Verdict |
|---|---|---|
| Gate per segment | ~800 ms | **Do it.** Biggest win, falls out of the design |
| Acknowledgement during lookup | 0 ms real, huge perceived | **Do it.** Already in the TDD |
| Skip LLM #1 on cached turns | ~450 ms + vendor | **Do it.** Already in the TDD |
| Silence threshold 600 → 400 ms | 200 ms | **Tune by feel, then freeze and record why.** Risks cutting people off |
| Speculative vendor prefetch | ~300–800 ms | **No.** Burns quota on a guess, and quota is the demo-day risk |
| Overlap STT with endpointing | — | **Impossible.** Batch STT needs the complete utterance |

**Endpointing remains the largest single term at ~600 ms** — larger than any provider call.
That is worth saying out loud in the walkthrough, because it is counter-intuitive and it is the
one number a reviewer will not expect.

---

## §5 — Verified provider facts, 2026-09-19

Researched against official docs, not recalled. Full source URLs and dates are in the research
report; the load-bearing ones are repeated here.

### The good news: nothing needs renaming

| Claim in the TDD | Verdict |
|---|---|
| `gemini-3.5-flash-lite` | ✅ **Real, stable, not preview.** Function calling supported. Free of charge on free tier. No announced shutdown |
| `gemini-3.1-flash-tts-preview` | ✅ **Real, current, newest Gemini TTS.** Arabic supported. Still `-preview` |
| 24 kHz PCM output | ✅ **Exactly right** — 24 kHz, 16-bit, mono, signed little-endian PCM |
| TTS streams | ✅ **Yes — and this is the only Gemini TTS model that does.** Docs: *"TTS does not support streaming, except when using `gemini-3.1-flash-tts-preview`"* |
| Groq `whisper-large-v3-turbo` | ✅ **Still live**, free tier 20 RPM / 2,000 RPD / 28,800 audio-sec per day. Not remotely a constraint |

A widely-circulated claim that Gemini 3.1 Flash TTS *cannot* stream is **out of date** — it
traces to April 2026 posts, before streaming shipped. Worth knowing, because it is the kind of
stale fact that gets repeated in an interview.

### 🚨 Four exposures, ranked by what they do to us

#### 1. TTS time-to-first-byte is genuinely unknown — and it decides the architecture

No published Google figure. No third-party benchmark with methodology. Artificial Analysis
ranks the model #2 on quality Elo but **publishes no latency metric for it at all.**

The only evidence is one Google forum thread, and it is not reassuring:

| Date | Report |
|---|---|
| 2026-07-25 | sub-2 s on an AI Studio default key; **10–20 s** on a personal Tier-2 key |
| 2026-07-26 | improved to sub-2 s |
| 2026-08-06 | degraded again to "unusable latencies" |

Same model, same reporter, three-week swing. And separately: a sibling model
(`gemini-3.1-flash-live-preview`) regressed from ~1 s to 9–15 s starting 2026-09-05, with ~1 in
3 sessions returning no audio, reproduced across two projects and two networks, still
unresolved. Different model, same infrastructure family, **two weeks ago.**

> **Add TTS TTFB to the day-1 spikes.** The TDD names three; this is a fourth, and on current
> evidence it is the one most likely to invalidate the design.

#### 2. …and there is a specific A/B to run, which our design already sets up

The same reporter notes the streaming `/v1beta/interactions` path is **significantly slower
than `generateContent` streaming.**

That interacts directly with §4's per-segment decision. Because each segment is only a sentence
or two, we may be able to use the *faster non-streaming* endpoint per segment and beat the
streaming one outright:

| Option | Path | Bet |
|---|---|---|
| **A** | `generateContent`, buffered, one call per segment | Short segments make buffering cheap; avoids the slow endpoint |
| **B** | `/v1beta/interactions`, streamed | Lower TTFB *within* a segment, on the reportedly slower path |

**Measure both on day 1.** This is a real measurement with a real decision behind it — exactly
the kind of thing worth a line in the writeup, whichever way it lands.

#### 3. The deployed URL may breach the free-tier terms

Gemini API Additional Terms, effective 2026-03-23, verbatim:

> You may use only Paid Services when making API Clients available to users in the European
> Economic Area, Switzerland, or the United Kingdom.

**We hand a public URL to a reviewer whose location we do not control.** Sarj is Saudi, so the
likely reviewer is in the Gulf — but "likely" is not a basis for a terms compliance decision,
and the email to Sarj asking for API keys is already drafted and unsent.

Related, and worth a sentence in the writeup on its own merits: **free-tier input is used to
train Google**, and human reviewers may read it. The terms say *"Do not submit sensitive,
confidential, or personal information to the Unpaid Services."* We persist user facts —
favourite colour, nationality, travel plans — and speak them through TTS. Naming that
constraint unprompted is the kind of thing that reads well.

#### 4. The preview TTS model has documented random failures

Google's own limitations page, verbatim: the model *"occasionally returns text tokens instead
of audio tokens, causing the server to fail the request with a `500` error… you should
implement automated retry logic."*

Straight into Invariant 7 — a 500 mid-turn must degrade visibly, not hang. Also documented:
`PROHIBITED_CONTENT` false rejections on vague prompts, and quality drift past a few minutes.
**Budget the retry; it is not optional, it is in the vendor's own docs.**

### The free tier is real but uncontractual

The rate-limits page publishes **no RPM/TPM/RPD table for any tier**, and disclaims the whole
subject: *"Specified rate limits are not guaranteed and actual capacity may vary."*

One third-party measurement (reading quota values out of 429 bodies, 2026-09-02) puts
`gemini-3.5-flash-lite` at **15 RPM / 500 RPD**. At ~2 LLM calls per turn that is ~250
turns/day — probably fine. **But it cannot be cited in the writeup**, and the LLM adapter needs
the same quota-exhaustion handling the vendor client already has.

### 🎁 The finding that changes a decision: Groq now has Saudi-dialect TTS

Our earlier research concluded Groq TTS was unusable. **That conclusion is now out of date** —
it was about the deprecated `playai-tts` and its 200-character cap. Groq now hosts:

| Model | Note |
|---|---|
| `canopylabs/orpheus-arabic-saudi` | Groq's description: *"authentic Saudi dialect synthesis"* |
| `canopylabs/orpheus-v1-english` | English counterpart |

Free tier, **10 RPM / 100 RPD**, default format WAV. Sample rate, streaming support and TTFB
are **undocumented** — they would have to be measured.

**Why this matters more than it looks:** Sarj is a ten-person Saudi company whose entire product
is Arabic-dialect-native voice. An Arabic demo that *speaks back in Saudi dialect* lands
differently from one that speaks Modern Standard Arabic, and it costs one API key we already
hold.

It also resolves cleanly against the PRD's existing Arabic plan rather than fighting it:

> **Egyptian in, Saudi out.** Input is scripted in Egyptian because that is where open-model
> word-error rate still holds up (Gulf WER ~68 vs Egyptian ~35). Output is Saudi dialect because
> that is who we are talking to. Two different constraints, each honestly named.

⚠️ **The catch: 100 requests per day is the tightest quota in the entire project** — tighter
than Travel Buddy's 120-request *total* budget, and it resets daily rather than being a lifetime
cap. A single demo rehearsal could burn a meaningful share. It would need the same reserve
discipline the vendor client already has.

### Two smaller notes

- **`gemini-3.5-transcribe`** now exists — a dedicated low-latency STT model with diarization
  and word timestamps. A same-vendor alternative to Groq Whisper if collapsing to one provider
  ever becomes attractive. Not proposing it; recording it.
- **`gemini-3.5-flash` is labelled "our legacy Flash model"** in Google's own docs. Not
  deprecated, but do not build on it. Flash-Lite 3.5 is the live path, and it is what the TDD
  already names.

---

## §6 — Memory: one contradiction, one unverified assumption, one path off the latency budget

### The contradiction (item 2)

The TDD says both of these:

| Where | Says |
|---|---|
| §Stack table | Memory — **open** — SQLite on a Modal Volume, or Postgres |
| §Memory | **Decided: SQLite on a Modal Volume.** No second service, no pooling, no extra secret |

The §Memory reasoning is sound as far as it goes. But it rests on a claim worth checking before
it becomes load-bearing.

### 🚨 The unverified assumption underneath it

> *"It only breaks with multiple containers, and we run `min_containers=1`."*

**`min_containers=1` sets a floor, not a ceiling.** It guarantees at least one warm container —
it does not prevent Modal from starting a second one under concurrent load. Two reviewers
opening the URL minutes apart is exactly the scenario §Memory's own identity section is written
to handle, and it is the scenario that could produce a second container.

Two SQLite writers on one shared volume file is corruption, not a race you lose occasionally.

⚠️ **And a second concern, which I am flagging as inference rather than fact:** Modal Volumes
have commit/reload semantics rather than behaving like an ordinary POSIX filesystem, and my
understanding is that they are not intended for live database files with concurrent writers. **I
have not verified this against Modal's current docs.** It belongs in the same bucket as the
WebSocket timeout — an assumption the plan leans on that nobody has tested.

### The alternative that removes the whole class of problem

Look at what we actually store:

```
session_id → { travel_profile, open_facts, place_cache }
```

That is a key-value store. We are not querying it, joining it, or aggregating over it. We read
one key at the start of a turn and write one key at the end.

**`modal.Dict` fits the shape exactly** — Modal's own distributed key-value store. No volume
flush semantics, no concurrent-writer corruption, no schema migration, no second service, and it
is safe if Modal ever runs two containers.

| | SQLite on a Volume | `modal.Dict` |
|---|---|---|
| Matches our access pattern | Over-powered | Exactly |
| Safe with 2+ containers | ❌ corruption | ✅ |
| Volume commit/reload semantics | ⚠️ unverified | Not applicable |
| Lines of code | ~60 + schema | ~15 |
| Inspectable (Invariant 4) | Query the file | Read the key; the UI panel is the real answer either way |
| Tangible in a walkthrough | A table you can `SELECT` from | A JSON blob you can print |

The one honest argument for SQLite is that last row — showing a table reads well. But Invariant 4
is satisfied by the *"what Sarjy remembers about you"* panel, which is the demo either way, and
which we are building regardless.

**Recommendation: `modal.Dict`.** It removes an unverified assumption and a corruption mode for a
data shape that is literally a dictionary, and it is fewer lines to defend live.

### The design gap: how does a fact get written?

The TDD says *what* is stored and never says *how it gets there.* The model has to decide that
"my favourite colour is green" is worth persisting, which means a tool call — and a tool call on
the response path is another round trip on a budget §4 already showed is tight.

**It must not sit on the latency path.** Two ways, and the second is better:

| Approach | Cost |
|---|---|
| Sequential: model calls `remember_fact`, waits, then answers | +1 full round trip on every turn that stores anything |
| **Parallel: emit the fact alongside the answer, write it fire-and-forget after the response is dispatched** | **Zero** |

The second works because the segmented response is already a structured object. Add an optional
`remember` field beside `segments`, and write it *after* the audio is on its way. Nothing the
user hears depends on the write completing.

⚠️ **One consequence to handle:** if the write fails, the user was already told "got it." Either
don't claim to have remembered until the write lands, or make the memory panel the source of
truth so a failure is visible there rather than silently contradicted later.

### Identity — right call, with one limit worth naming

Anonymous session id in `localStorage`, one record per id. This correctly solves the shared-memory
failure between two reviewers and keeps requirement 4's "no login" intact.

What it does **not** cover, and should be said out loud rather than discovered:

| Scenario | Result |
|---|---|
| Reload, new tab, browser restart | ✅ Memory persists — this is the brief's actual test |
| Incognito window | ❌ New identity. Correct behaviour, but a reviewer "starting fresh" gets a blank slate |
| Different browser or device | ❌ New identity |
| `localStorage` blocked or cleared | ❌ New identity |

All defensible. The one that matters is the demo script: **the reviewer must state a fact and
then reload in the same browser profile.** If the script says "open it fresh" the requirement
appears broken when it is working correctly.

### Two smaller things

**Cap the open facts.** The typed profile is bounded by its schema; open key/value facts are not.
A long conversation could push unbounded text into every subsequent prompt. Cap the count, evict
oldest, and say so in the panel.

**The forget button is a feature, not a nicety.** `forget_all` is already stubbed in
`store.py`. Given §5's finding that free-tier input is used for training, being able to point at
a working "forget everything" control while saying *"and here is why that matters on a free
tier"* is a stronger beat than the button alone.

### Addendum — Omar's proposal: a lightweight identity prompt

> *"Maybe we add a small login modal to the interface so different reviewers get assigned to
> different actual users in a db."*

**This is better than the `localStorage`-token design, and for a reason the token version cannot
match: it makes isolation demonstrable.**

With an anonymous token, proving that two reviewers do not share memory requires opening a second
browser and narrating what the audience cannot see. With a name, it is a fifteen-second beat:

> Switch to a different name → Sarjy knows nothing about you → switch back → *"your favourite
> colour is green."*
> **Persistence and isolation, proven in one move, in front of the reviewer.**

That is requirement 2 demonstrated rather than asserted.

#### The version I would build: voice-first, not a modal

A login modal is friction in front of requirement 4 (*"reviewer opens a link and it works"*). But
the same identity can be collected by the product doing the thing it is for:

> **"Hi, I'm Sarjy — what should I call you?"**

Spoken, as the first turn. That single beat does four jobs at once:

| Job | Why it lands here |
|---|---|
| Creates the identity | The answer is the key |
| **Proves the mic works before anything else matters** | A broken audio path surfaces in second one, not minute three |
| Gives the microphone prompt a reason | `browser-audio.md`: ask *"at a sensible moment, with context"*, never on page load |
| Opens the demo naturally | A conversation, not a form |

**With a typed fallback**, and that is not optional — names are exactly where Whisper is weakest,
Arabic names especially. A mis-transcribed name on turn one is a bad first impression and an
orphaned memory record.

#### Combine it with the token rather than replacing it

| Layer | Role |
|---|---|
| `localStorage` | Remembers the **last name used** → returning in the same browser skips the question entirely. Zero friction on reload |
| The name | The actual **record key** → works across devices, browsers, and incognito |
| A "not you? switch" affordance | The isolation demo, and an escape hatch from a mis-heard name |

Reload — the brief's literal test — costs the reviewer nothing. Cross-device works. And the
demo beat exists.

#### Say plainly what it is not

**This is a nameplate, not authentication.** Anyone who types "Omar" gets Omar's record. For a
demo holding a favourite colour and a passport nationality, that is the correct amount of
security — and naming it is worth more than quietly implying otherwise:

> *"This is identity, not auth — deliberately. Requirement 4 says no login, and the deep dive is
> guardrails, not access control. Here is exactly what I would add if this held real data."*

#### On the scope guard

`AGENTS.md` warns against *"auth, user accounts, or multi-tenancy unless the chosen deep dive
actually requires them."* Worth answering directly rather than stepping around:

The deep dive does not require it — **requirement 2 does.** Shared memory between two reviewers
is a P0 failure in the deliverable floor, not a polish item. The guard exists to stop OAuth,
password resets and sessions; a name field and a dictionary key are the *minimum* that makes a
graded requirement correct. That line is defensible, and the distinction is worth stating in the
walkthrough.

#### What it does to the store decision

Nothing. `name → { travel_profile, open_facts, place_cache }` is the same key-value shape as
`session_id → {...}`, so `modal.Dict` still fits and SQLite is still over-powered. Named keys make
the stored record *more* legible in the memory panel, not less.

**Cost:** roughly 45 minutes, most of it the switch-user affordance and the typed fallback. It
buys a demo beat that otherwise does not exist.

### Addendum 2 — the two-tier proposal, and the one thing to change

> *"Maybe not a modal but an actual login — if the user isn't signed in they get a generic model
> answering and can only remember within the session, no proper backend saves."*

**The two-tier structure is right and I would build it.** What I would change is what "login"
means.

#### Why the two tiers are good design, not just a compromise

| Tier | Memory | Requirement it protects |
|---|---|---|
| **Anonymous** | In-session only, lost on reload, clearly labelled | **#4** — the link works instantly, nothing asked of the reviewer |
| **Signed in** | Persisted, attributable, cross-device | **#2** — memory across sessions |

It also happens to restate the project's own thesis in a second place: *ephemeral versus
persisted-and-attributable* is the same distinction as *judgement versus sourced*. Invariant 4
asks memory to be attributable; the tiers make attribution visible in the product rather than
only in the schema.

And it gives the demo a real arc instead of a feature list:

```
1. Open the link cold          → it just works          (req 1, 3)
2. "Sign in so I remember you" → identity, visibly      (req 4 intact)
3. "My favourite colour is green"
4. Reload                      → still remembered       (req 2)
5. Switch user                 → knows nothing about you (isolation)
```

#### 🚨 The thing to change: not OAuth

An "actual login" almost always means Google OAuth, and there is a specific reason not to here:

> **A hiring reviewer may not want to sign into a candidate's take-home with their real Google
> account.** If they decline, they never see requirement 2 working — and requirement 2 is graded.

The security we would be buying is irrelevant (the protected data is a favourite colour and a
passport nationality), while the cost is real: OAuth client setup, redirect URIs that must match
the deployed URL exactly, and a classic day-4 breakage where the callback is misconfigured in
production and the demo dies at step 2.

**Build the tiers. Make the upper tier a name plus an optional short PIN.**

| | Name + optional PIN | Google OAuth |
|---|---|---|
| Build time | ~45 min | ~2 h + deployment config |
| Reviewer friction | Types a name | Hands over a Google account |
| Fails on demo day if… | nothing | redirect URI mismatch on the deployed URL |
| Security actually needed | ✅ enough | Far beyond the data |
| Requirement 2 demonstrable | ✅ always | ❌ only if they agree to sign in |

The PIN is what makes it feel like signing in rather than typing a nickname, and it stops casual
collision if two people both pick "Omar". It is four characters of state, not an auth system.

And it converts cleanly into a walkthrough answer rather than something to be defensive about:

> *"I deliberately didn't use OAuth. I didn't want a reviewer to have to sign into a stranger's
> app to see the memory feature work, and the data here doesn't justify it. This is identity, not
> authentication — here's the line where I'd swap in real auth."*

#### One risk the two-tier design introduces

**If memory only persists when signed in, a reviewer who never signs in may conclude memory is
broken.** Requirement 2 is graded on what they observe, not on what the code supports.

Mitigate in the UI, not in the README:

- The memory panel, while anonymous, reads *"remembered for this session only — sign in to keep
  these."*
- Sarjy says it once, naturally, after the first fact worth keeping: *"I'll forget that when you
  close the tab unless you tell me your name."*
- The stored-facts panel stays visible in both tiers, so the difference is legible at a glance.

**Cost is unchanged from the previous addendum — ~45 min** — because the anonymous tier is the
same store interface backed by a non-persisted dict. Roughly ten extra lines, not a second
subsystem.

---

## §7 — The spike budget has a problem

Day 1 in the TDD is: *three spikes, then skeleton end-to-end, deployed.* This review has added
three more:

| # | Spike | Blocks | Really day 1? |
|---|---|---|---|
| 1 | Modal 10-minute WebSocket | The entire architecture | ✅ **Yes** |
| 2 | Browser audio loop in isolation | The entire architecture | ✅ **Yes** |
| 3 | **TTS TTFB**, plus `generateContent` vs `/interactions` | The latency budget and possibly the design | ✅ **Yes** (§5) |
| 4 | Travel Buddy colour legend | Day 2's vendor client | ❌ Day 2 |
| 5 | `modal.Dict` vs Volume semantics | Day 2's memory | ❌ Day 2 |
| 6 | Groq Orpheus Arabic | Day 4's P2 | ❌ Day 4 |

**Six spikes plus a deployed skeleton is not a day.** The viability review already put the plan
at roughly 2× over; this is where that shows up first.

**Run 1–3 on day 1 and move the rest to the day they actually block.** Each of 4, 5 and 6 gates
work that does not start until later, so running them early buys nothing and costs the one day
whose failure is unrecoverable.

The three that stay share a property the others do not: **each can invalidate the architecture.**
If the WebSocket dies at five minutes, if the browser audio path does not work, or if TTS
time-to-first-byte is two seconds, the design changes. That is what a day-1 spike is for.

---

## §8 — The inventory, and the arithmetic nobody has done

**Corrected by Omar:** the deadline is **Monday 19:00** — all Saturday, all Sunday, most of
Monday. The invitation email said four days from Thursday night; the assignment doc said three.
**Target the doc's three.** When two sources disagree, the tighter one is the safe read, and it
is the one written into the brief.

Realistic working hours, with Monday's last block reserved for submission rather than build:

| Day | Build hours |
|---|---|
| Saturday (after sleep — it is 02:50 now) | ~10 |
| Sunday | ~10 |
| Monday, to 19:00, **less ~3 h reserved for Loom + submission** | ~6 |
| **Available for building** | **~26 h** |

Here is everything the plan currently contains. Estimates, not measurements.

### P0 — the deliverable floor (the 7 requirements)

| Task | Est. |
|---|---|
| Day-1 spikes: Modal WebSocket · browser audio · TTS TTFB | 2.0 |
| Browser capture + playback + VAD wiring | 3.0 |
| WebSocket protocol + FastAPI pipeline skeleton | 2.0 |
| STT adapter (Groq Whisper) | 1.0 |
| LLM adapter (Gemini) + tool-calling loop | 2.0 |
| TTS adapter + retry for the documented 500s (§5) | 1.5 |
| Deploy to Modal + secrets + verify | 1.5 |
| Vendor client: quota, reserve, resolution order | 2.5 |
| Normalisation layer (§2) | 1.5 |
| Memory store + two tiers + identity UX | 2.0 |
| UI: state, transcript, memory panel | 2.5 |
| Per-stage instrumentation (Invariant 2) | 1.0 |
| **Subtotal** | **22.5 h** |

### P1 — the deep dive

| Task | Est. |
|---|---|
| Gate: `resolve`, `get_path`, digit + placeholder rules | 2.0 |
| NDJSON segmented prompt + per-line parsing (§4) | 1.5 |
| Assertion tests, Tier A — no model, every commit | 1.0 |
| Assertion tests, Tier B — golden prompts | 0.75 |
| Eval harness + 12 labelled cases + recorded fixtures | 2.0 |
| LLM judge, 4 categories | 2.0 |
| Judge-vs-human agreement | 0.3 |
| Injection delimiting + refusal routing | 1.25 |
| **Subtotal** | **10.8 h** |

### P2 / P3 / deliverables

| Task | Est. |
|---|---|
| Arabic — **bare minimum**: Whisper `language=ar`, Gemini TTS auto-detects | **0.75** |
| Arabic — code-switching script tagger + RTL handling | 2.0 |
| Groq Orpheus Saudi-dialect spike + wiring | 0.75 |
| Wikipedia client + place imagery | 1.5 |
| UI polish — calm, attractive, beyond functional | 2.0 |
| **Demo script + rehearsal** | 1.0 |
| **Loom / PDF** | 1.5 |
| **Writeup: API justification, deep-dive numbers, what I'd do next** | 1.5 |
| **Progress updates to Sarj** | 0.5 |
| **Subtotal** | **11.5 h** |

### 🚨 The arithmetic

| | Hours |
|---|---|
| Everything above | **~44.8** |
| Available for building | **~26** |
| **Over by** | **~1.7×** |

Better than the 2× the viability review found, but still comfortably over. **Roughly a third of
this plan is not going to happen. The only question is whether you choose which third or discover
it at 4 a.m. on Monday.**

### The one genuinely good discovery in this table

**Arabic is not a 3.5-hour feature. The honest minimum is ~45 minutes.**

- Whisper takes `language=ar` — a config change through an adapter that already exists
- Gemini TTS auto-detects Arabic from the text — verified in §5, no work at all

What costs hours is *code-switching* (the script tagger), *RTL polish*, and *Orpheus*. Those are
the enhancements, not the feature.

That matters because **Sarj were told in writing this is "a bilingual English/Arabic voice
assistant."** Shipping zero Arabic walks that back. Shipping one clean Arabic turn — and saying
out loud that code-switching is where it gets hard, with the WER numbers — honours the promise
and makes a better talking point than the polish would have.

### The cut ladder, in the order I would cut

| Cut | Saves | Cost of cutting |
|---|---|---|
| 1. UI polish beyond functional | 2.0 | Rubric says "delightful UI" — real loss, but state + clarity carry most of it |
| 2. Wikipedia imagery | 1.5 | Already P3 in the PRD. The TDD just never removed it |
| 3. Arabic code-switching + RTL | 2.0 | Keep the bare Arabic turn. Name the gap out loud |
| 4. Orpheus Saudi-dialect spike | 0.75 | Lovely beat, entirely optional |
| 5. Assertion tests Tier B | 0.75 | Tier A covers the gate; Tier B covers the prompt |
| 6. LLM judge + agreement | 2.3 | **The last thing I would cut.** Deterministic layers still give defensible numbers |
| **Total available from cuts** | **9.3 h** | |

That lands at **~35.5 h against ~26**. Still ~1.4× over — and that assumes nothing goes wrong,
in a voice app, where something always does.

### The committed core, and what it actually costs

Strip it to what is genuinely unavoidable:

| Block | Est. |
|---|---|
| P0 floor — all 7 requirements | 22.5 |
| Deep dive, minimum: gate · NDJSON · Tier A tests · fixtures + 12 cases · injection + refusal | 7.75 |
| Arabic, bare minimum | 0.75 |
| Deliverables — demo script, Loom, writeup, updates | 4.5 |
| **Committed core** | **~35.5 h** |

**Against ~26 h of build time, the core itself is ~1.4× over.** Cuts cannot fix that, because
everything above is either a graded requirement or the deep dive itself.

### On Pipecat — I would not take it

It is the obvious lever (−3 to −4 h off the browser-audio and WebSocket plumbing) and I think it
is a trap here:

- **The learning curve lands exactly when you cannot afford it.** Learning a framework under
  deadline routinely costs more than the 300 lines it replaces.
- **It wants to own the pipeline,** and the grounding gate has to sit between LLM and TTS —
  precisely where a framework asserts control. Fighting that costs the saving back.
- **The plumbing is the least differentiated part.** Spending the framework's complexity budget
  there, and then having to explain its internals live, trades the wrong thing away.

Keep it as an escape hatch with a trigger hour. Do not make it the plan.

### What actually closes the gap: sequence, not cuts

You cannot make 35 hours fit in 26. You *can* decide, in advance and while rested, **which hours
fall off the end.**

Order the work so that overflow is automatically the least damaging thing:

| # | Block | If it is missing |
|---|---|---|
| 1 | Three spikes | Architecture is wrong — unrecoverable |
| 2 | **Deploy a skeleton** | Requirement 4 scores **zero** |
| 3 | Voice loop end to end | Requirement 1 |
| 4 | Memory + identity | Requirement 2 |
| 5 | Vendor client + normaliser + **the gate** | Requirement 3 + the entire deep dive |
| 6 | Instrumentation | Invariant 2, and "where does the time go" gets asked regardless |
| 7 | Eval fixtures + 12 cases + Tier A tests | The deep dive's numbers |
| 8 | 🔒 **Deliverables — a reserved block, not leftovers** | Graded separately. Never the remainder |
| — | *Overflow zone* | Judge · Arabic polish · Tier B · imagery · UI polish |

**Block 8 is reserved time, not what is left over.** The brief grades the presentation separately
from the build, and the single most common way a good take-home scores badly is arriving with
working code and no demo.

Everything below the line becomes *"what I'd do with another week"* — which the assignment names
explicitly as something they want to hear. An unfinished thread you can articulate beats a
finished thread nobody asked about.

⚠️ **And set the Pipecat trigger hour now, before you are tired.** A pre-committed decision point
— *"if the audio loop is not working by 6 p.m. Saturday, I switch"* — is a decision made by
today's judgement instead of Sunday-night panic. That is the entire value of it, and it expires
the moment you are too invested to use it.

---

## §9 — Recalibrated: what AI-assisted work actually compresses

> *"I think with AI usage I will be pretty fast, especially if we plan thoroughly and deeply."*

Fair, and the §8 estimates were calibrated to hand-coding. But the compression is **not uniform**,
and which half compresses matters more than the average.

### What compresses (roughly 2×) and what does not (0×)

| Compresses ~2× — generative work | Does not compress — wall clock or empirical |
|---|---|
| Provider adapters (STT/LLM/TTS) | **The three spikes** — a 10-minute WebSocket test takes ten minutes |
| Store, memory, identity | **Deployment cycles** — Modal deploy, secrets, verify the URL |
| Normalisation layer | **Browser audio debugging** — AudioWorklet, echo cancellation, Safari |
| Vendor client + quota logic | **Latency measurement runs** |
| **Tier A unit tests** — the biggest win of all | **Prompt engineering** — the gate and judge prompts are iterative |
| UI scaffolding | **Labelling the 12 eval cases** — human judgement by definition |
| Eval harness, judge runner | **Demo rehearsal and the Loom** — usually two or three takes |
| Writeup first drafts | **Tuning by feel** — silence threshold, voice, persona |

### The recalibrated total

| Block | §8 est. | Recalibrated |
|---|---|---|
| P0 floor | 22.5 | **14.5** |
| P1 deep dive | 10.8 | **7.0** |
| P2 / P3 / deliverables | 11.5 | **7.9** |
| **Total** | **44.8** | **~29.4 h** |

**Against ~26 h available, that is ~1.13× over** — and the cut ladder closes it with room:

| Cut | Saves |
|---|---|
| Wikipedia imagery | 0.75 |
| UI polish beyond functional | 1.25 |
| Arabic code-switching + RTL | 1.25 |
| **Lands at** | **~26.2 h** |

**It fits.** Not comfortably, but it fits — which the §8 numbers said it could not.

### Why it compresses is the work we just did

This is not optimism about typing speed. A vague brief does not compress at all — an AI given
"build a grounding gate" produces something plausible and wrong. What compresses is a spec with
**defined contracts, named file paths, explicit failure modes, and decided trade-offs**, which is
precisely what §1–§8 produced.

The nine hours of planning bought the compression. That is worth knowing because it argues for
finishing the plan properly before Saturday morning, not for skipping ahead.

### 🚨 But the risk profile got worse, not better

Incompressible work is now **~11 of the ~26 hours — over 40% of the budget.** Spikes, deployment,
audio debugging, measurement, rehearsal and the Loom do not care how fast the code gets written.

Two consequences:

1. **Schedule the incompressible work first and protect it.** It is the part that cannot be
   recovered by working faster later. If Saturday's spikes slip, nothing downstream can absorb it.
2. **A single bad surprise in the incompressible half eats the entire buffer.** If TTS
   time-to-first-byte comes back at two seconds, or the Modal WebSocket dies at five minutes,
   there is no faster typing that fixes it.

### ⚠️ And the real ceiling is not typing speed

`CLAUDE.md`, and the rubric behind it:

> **Do not generate code Omar hasn't been walked through.** *"Do you understand it thoroughly?"*
> is a graded criterion, and any code you cannot explain live is a liability rather than an asset.

**With AI, the binding constraint shifts from writing code to understanding it.** Generation is
no longer the bottleneck; your review time is. That is a real budget line, not a platitude — and
it is the one thing in this plan that must not be compressed, because compressing it converts
finished features into demo liabilities.

Practically: walk through each module as it lands rather than batching comprehension to Sunday
night. The `/implement` skill and the explain-as-you-go cadence in `CLAUDE.md` exist for exactly
this, and they are now load-bearing rather than nice-to-have.

---

## §10 — Gemini structured output: the NDJSON plan survives, but only one way

Researched against official docs 2026-09-19. **§4's per-segment recommendation rests on an
assumption I flagged as untested. It is now tested, and the answer is "yes, but not the easy
way."**

### 🚨 The finding that matters

> **Streaming + `response_format` does not give you discrete objects.** Google's docs, verbatim:
> *"The streamed chunks are valid partial JSON strings that can be concatenated to form the final
> JSON object."*

So the chunks are fragments of **one growing document**, not complete objects. Splitting those
deltas on `\n` gets you fragments of a JSON array, not parseable lines.

**There is no NDJSON mime type.** `mime_type` is a two-value enum: `application/json` or
`text/plain`. "JSONL" appears in Google's docs only as a Batch API *input* format.

**Therefore: NDJSON and `response_format` are mutually exclusive.** Pick one.

### The trade, stated plainly

| | **A · NDJSON** (`text/plain`, prompted) | **B · `response_format`** (one JSON doc) |
|---|---|---|
| Per-segment gating | ✅ Yes — the §4 design works | ❌ No — full completion first |
| Latency | **~800 ms faster to first audio** | Pays full generation |
| JSON validity | Prompt-enforced. **We own every malformed line** | Guaranteed syntactically valid by constrained decoding |
| Validation | Pydantic per line — still schema validation, not regex | Pydantic on one object |
| New failure mode | Malformed line mid-response | None |

**Recommendation: A.** Three reasons:

1. **The machinery already exists.** A malformed line is just another rejection — and the gate's
   rejection path (*"I couldn't confirm that part"*) is already built and already the honest
   sentence. It is not a new concept, it is one more input to an existing branch.
2. **It does not violate the grounding-gate rule.** That rule says *schema-validated object, never
   regex a model's prose*. Pydantic parsing a JSON object per line **is** schema validation. We
   are not pattern-matching text; we are parsing JSON and rejecting what fails.
3. **800 ms is a lot in a voice app**, and §8 shows we have no latency to spare.

**Cost to name honestly:** without constrained decoding, the malformed-line rate is unknown. So
**measure it** — it joins gate-rejection rate as a reported number. Two measured failure rates
beats one assumed guarantee.

### 🚨 Thinking is on by default, cannot be turned off, and will corrupt your latency numbers

`gemini-3.5-flash-lite` defaults to `thinking_level: "minimal"`. Levels are `minimal` / `low` /
`medium` / `high` — **there is no off.** Docs: *"`minimal` does not guarantee that thinking is
off."*

Two consequences:

1. **Set `thinking_level: "minimal"` explicitly on every call.** It is interaction-scoped and is
   *not* carried by `previous_interaction_id` — omit it and you silently get the model default.
   Same for `tools` and `system_instruction`.
2. ⚠️ **Instrument TTFT to the first `delta.type == "text"`, not the first SSE event.** Thinking
   arrives first as `thought` deltas. Measuring to the first event records a fiction — a number
   that looks great and describes nothing the user experienced. This is Invariant 2's exact
   failure mode, and it would have been very easy to get wrong.

### Five more things that change the code

| Finding | What to do |
|---|---|
| **`generateContent` is legacy.** The Interactions API has been GA since June 2026 and is "recommended for all new projects" | Build the adapter on `client.interactions.create`. Needs `google-genai >= 2.3.0` — **pin it** |
| **`responseSchema` is deprecated** | Any snippet using `response_schema=` / `response_mime_type=` is writing against a deprecated field. Do not build the adapter around it |
| **`temperature`, `top_p`, `top_k` deprecated 2026-07-21**, and on 3.5 Flash-Lite custom values *"will be ignored"* | **You cannot get determinism from the model.** Which is exactly why §3's assertion tests assert on *gate-substituted* values — that design is now not merely convenient, it is the only way to have stable tests on this model |
| **Free tier stores interactions for 1 day** (`store=true` is the default) | Set `store=False` deliberately. Ties directly to §5's finding that free-tier input trains Google, and we persist personal facts |
| **Stateless mode is strict** — with `store=False` you must resend every model step *"exactly as received"*, thought signatures included | Real work, not `history.append(text)`. Budget ~20 min and write it once, carefully |

### One piece of good news: the two-call split is now validated by the docs

Google documents a failure mode that matches our architecture exactly: requiring the model to
emit structured text *immediately before* a tool call *"may occasionally fail with
`Malformed_Function_Call`."*

**Our two-call split avoids it by construction** — call 1 is tools only, call 2 is segments only.

> **Do not later "optimise" by merging the segmenting prompt into the tool-calling call.** It is
> the obvious-looking saving, it is documented to break, and this note is here so that at 1 a.m.
> on Sunday you remember why the split exists.

Also confirmed: `tool_choice: "none"` on call 2 documentedly prohibits further tool calls —
exactly what we want.

### Still unverified, and worth knowing

- **Whether `tools` + `response_format` + `stream=True` work as a triple.** Each pair is
  documented; the combination never is. Moot if we take option A.
- **Whether `gemini-3.5-flash-lite` is covered by "Structured outputs with tools"** — the current
  page says "Gemini 3 series", the legacy page narrows it to three other models. Conflicting, and
  it is a Preview feature. Again moot under option A.
- **No published TTFT figure for this model.** DeepMind quotes 350 output tokens/sec throughput,
  which is not the same thing. Measure it.

---

## §11 — Modal: one real bug in the scaffold, and one decision that is irreversible

Researched against Modal's full docs corpus, their client source, and their own reference voice
app. **Already fixed in `backend/modal_app.py`.**

### 🚨 The bug: one WebSocket = one input = one container

Modal's own WebSocket launch post, verbatim:

> *Modal treats each WebSocket connection as a single input, so you will want to set your function
> to allow for concurrent inputs… **Otherwise, Modal will spin up a new container for each
> WebSocket connection.***

The scaffold had no `@modal.concurrent`. So **every concurrent listener would have got their own
container** — and `min_containers=1` does not prevent it, because §6 was right that it is a floor,
not a cap. It is worse than §6 assumed: not "under load", but *per connection*.

Two reviewers on the URL at once would have been two containers with two separate in-memory
states. Fixed:

```python
@app.function(
    timeout=30 * 60,       # never the 300 s default
    min_containers=1,      # floor, not a cap
    max_containers=2,      # the actual cap
    scaledown_window=300,
)
@modal.concurrent(max_inputs=8, target_inputs=4)   # ← the fix
@modal.asgi_app()
```

⚠️ **And write the WebSocket handler `async`.** Modal: *"When using input concurrency with a
synchronous Function, a single input cancellation will terminate the entire container."* A
WebSocket disconnect **is** an input cancellation — so one reviewer closing their tab would kill
everyone else's session. A sync handler plus concurrency is a trap with no error message.

### 🚨 `routing_region` cannot be changed after the first deploy

> *"To change the routing region, a new Function should be created."*

Default is `us-east`. **There is no Middle East routing region** — `me` exists as a *container*
region only, at a 1.75× price multiplier. For a Gulf reviewer, `eu-west` is the closest ingress.

This is a **now-or-never decision on day 1**, and it is genuinely two-sided: `eu-west` shortens
the reviewer's round trip to us, `us-east` shortens ours to Groq and Gemini — and every turn pays
the provider hop twice while the reviewer pays theirs twice too. Without measurements it is a
coin-flip, which argues for the default rather than a guess dressed as a decision.

### The WebSocket timeout: assumption confirmed, justification replaced

**Keep the assumption. Change the basis, and never write "Modal documents that…"** — because it
does not. There is no sentence anywhere in Modal's docs about WebSocket duration.

The inference chains two documented facts:

1. *"WebSockets on Modal maintain a single function call per connection."*
2. *"The timeout duration is a measure of a Function's execution time."*

One connection = one call = one execution, so `timeout` bounds it. Corroborated two ways:
**Modal's own reference voice app (QuiLLMan) sets `timeout=600`** on both its WebSocket functions,
and Modal's client source treats a WebSocket as a stream of inputs on one call, with the comment
*"Disable timeout, since timeouts are handled on input level instead."*

**Still worth the ten-minute spike**, but now it tests one specific thing: whether the documented
**150 s HTTP request timeout** survives a WebSocket upgrade. No exemption sentence exists.
Circumstantial evidence says it does not — the documented workaround is a 303 redirect, which is
impossible for a WebSocket. Hold an idle connection past 150 s and find out.

### `modal.Dict` is confirmed — and the caveat people remember no longer applies

§6 recommended it. Verified:

> *"Dicts are persisted… the data can be retrieved even after the application is redeployed."*
> *"The Dict entries are written to durable storage."*

The "Dicts are in-memory and can be lost" warning is real but applies to **legacy Dicts created
before 2025-05-20**, which are being sunset. Current Dicts are durable.

Three limits to design around, none blocking:

| Limit | Consequence |
|---|---|
| **Entries expire after 7 days of inactivity** | Fine for the demo window. State it; do not discover it |
| **No documented read-modify-write atomicity, no CAS** | Our turn is read → mutate → write. One key per user makes this near-harmless; **do not claim it is transactional** |
| ≤100 MiB per value, <5 MiB recommended | Irrelevant at our size |

**And SQLite-on-a-Volume is now firmly ruled out:** last-write-wins per file, no distributed
locking, and another container sees nothing until an explicit `.reload()`. Modal's own SQLite
example builds the database *off*-Volume and copies the finished file in. **That retires the day-2
spike** — the question is answered.

### Two more things worth having

**Serve the frontend from the same ASGI app.** A `StaticFiles` mount on the image-baked
`frontend/dist` is Modal's own pattern, and it **removes CORS entirely** — same origin, no
preflight, no second deployment. Saves time and deletes a class of demo-day bugs.

**Preemption is not optional to handle.** *"All Modal Functions are subject to preemption by
default… likelihood of interruption increases with Function run duration."* A voice conversation
is a long-running function by definition. **The client needs reconnect-and-resume regardless of
`timeout=`** — this is Invariant 7, and it is now a documented certainty rather than a
defensive nicety.

### Renamed parameters — old names in any snippet are a smell

| Old | Current |
|---|---|
| `allow_concurrent_inputs=N` | `@modal.concurrent(max_inputs=N)` |
| `keep_warm` | `min_containers` |
| `concurrency_limit` | `max_containers` |
| `container_idle_timeout` | `scaledown_window` |
| `@modal.web_endpoint` | `@modal.fastapi_endpoint` |

---

## §12 — The plan: priority-ordered, with gates

Ordered so that **if you run out of time, what falls off the end is what you can write up** —
never a graded requirement. Every block below is sequenced by *"what is unrecoverable if
missing"*, not by what is interesting.

### Saturday — ~10 h · Gate: **a deployed URL that talks back**

Incompressible and unrecoverable work first. Nothing here gets faster by typing faster.

| | Block | h |
|---|---|---|
| 1 | **Spikes.** Hold an idle Modal WS past 150 s · deploy twice (`us-east` / `eu-west`), time a turn through each · measure TTS TTFB (`generateContent` vs `/interactions`) | 1.5 |
| 2 | **Browser audio loop, in isolation.** AudioWorklet, 48→16 kHz, PCM16, playback scheduling, echo cancellation. The riskiest empirical hour in the project | 2.5 |
| 3 | WebSocket protocol + FastAPI skeleton — **`async` handler**, `@modal.concurrent` | 1.0 |
| 4 | STT · LLM · TTS adapters, thin, behind the Protocols that already exist | 1.5 |
| 5 | 🎯 **Deploy it. End to end. Talking.** Requirements 1 and 4 land here | 1.5 |
| 6 | Instrumentation — from the first working turn, **TTFT to first `text` delta** (§10) | 1.0 |
| 7 | Buffer | 1.0 |

**Send Sarj a progress update before bed.** It is graded, it costs five minutes, and "deployed a
working voice loop today" is a good one to send.

⚠️ **The Saturday gate is also the trigger.** If the day ends without a deployed URL that talks
back, Sunday changes immediately: **drop the judge and Arabic, protect P0.** Decide that now, not
on Sunday night.

### Sunday — ~10 h · Gate: **all 7 requirements demonstrable**

| | Block | h |
|---|---|---|
| 1 | Vendor client: quota, reserve, resolution order + **colour-legend spike** (~6 requests) | 1.5 |
| 2 | Normalisation layer — live API and CSV into one shape (§2) | 0.75 |
| 3 | 🎯 **The gate.** `resolve`, `get_path`, placeholder rule, digit rule | 1.5 |
| 4 | NDJSON prompt + per-line Pydantic validation + malformed-line path (§10) | 1.25 |
| 5 | **Tier A unit tests** — cheapest, fastest, highest-leverage hour on the board | 0.5 |
| 6 | Memory + two identity tiers on `modal.Dict` | 1.0 |
| 7 | UI: state, transcript, memory panel, **which layer answered and how fresh** | 1.25 |
| 8 | Injection delimiting + refusal routing | 0.75 |
| 9 | Eval fixtures + 12 hand-labelled cases (**labels written before the pipeline runs**) | 1.25 |
| 10 | Redeploy, verify, buffer | 0.25 |

### Monday — ~6 h build, then a hard stop · Gate: **submitted**

| | Block | h |
|---|---|---|
| 1 | Judge, 4 categories + judge-vs-human agreement. **Run the eval, get the numbers** | 1.5 |
| 2 | Arabic, bare minimum: `language=ar`, Gemini TTS auto-detect | 0.5 |
| 3 | Measurement run against the **deployment** — median and p95, never one local run | 1.0 |
| 4 | Fix whatever the numbers expose | 1.0 |
| 5 | Overflow / buffer | 1.0 |
| 🔒 | **16:00–19:00 RESERVED — demo script · rehearsal · Loom · writeup · submit** | 3.0 |

**Block 🔒 is not negotiable and not "whatever is left".** The presentation is graded separately
from the build, and the most common way a good take-home scores badly is arriving Monday evening
with working code and no demo.

### The overflow zone — what you write up instead of building

If these do not happen, say so and describe them. *"What I'd do with another week"* is explicitly
invited by the brief.

Arabic code-switching + the script tagger · Groq Orpheus Saudi dialect · Tier B golden tests ·
Wikipedia imagery · UI polish beyond functional · streaming TTS within a segment

### Three things to do before Saturday starts

1. **Send the email to Sarj.** It is drafted and unsent, and it asks for the reviewer's GitHub
   username — which you need before you can submit, not after.
2. **Decide Sarjy's voice and persona.** Two minutes of choosing, and it is on the latency path
   of nothing.
3. **Sleep.** It is 03:00. The incompressible half of Saturday is debugging browser audio, which
   is exactly the work that goes worst when tired.

---

## §13 — Omar's mental model vs the TDD

Comparing what you described against what is written down. **Three things match, one is a real
improvement, two are traps, and one should stay cut.**

### What matches

| Your model | TDD |
|---|---|
| Speech → STT → LLM with tool-calling → respond | ✅ Identical |
| Visa requirements as the tool | ✅ The anchor use case |
| Save user data **in parallel, not on the response path** | ✅ §6 reached the same conclusion independently |

That last one is worth noting: you arrived at the fire-and-forget write from a latency instinct,
and §6 arrived at it from a round-trip count. Same answer, two directions — that usually means it
is right.

### 🎯 The real improvement: speak *before* the tool returns, not after

**This is better than what is in the TDD, and it is the biggest latency idea in this review.**

The TDD's flow spends LLM call #1 producing *nothing the user hears* — it emits tool arguments,
and the user sits in silence through it and through the vendor round trip:

```
STT → LLM#1 (450ms, silent) → vendor (300-800ms, silent) → LLM#2 → TTS → first sound
```

Your version has the model open its mouth immediately and do the lookup *behind its own voice*:

```
STT → LLM#1 emits opener + tool call → TTS starts speaking
                                     ↘ vendor round trip runs underneath the audio
      LLM#2 continues with the real data → speaks on
```

| | Silent before first sound |
|---|---|
| TDD as written | ~1.9 s (LLM#1 + vendor + LLM#2 + TTS) |
| **Your model** | **~1.2 s** (STT + LLM#1 to first speakable token + TTS TTFB) |

And the ~1.1 s of vendor round trip plus LLM#2 now runs *underneath* two seconds of speech. **If
the opener is a normal sentence, the user may perceive no gap at all.**

It also composes with §4's per-segment gating rather than competing with it — one hides the tool
call, the other shortens generation.

### 🎁 And it aligns with the guardrail rather than fighting it

The obvious worry: *if the model speaks before the data arrives, what stops it inventing?*

**The two-register split already answers this, exactly.** Before the tool returns, the only thing
the model *can* legitimately say is `judgement` or conversational framing — because no `sourced`
segment exists yet to reference. The gate does not need a new rule; **the register a segment can
carry is determined by whether its tool result has landed.**

> The opener is safe by construction, not by prompt discipline.

That is a good answer to a sharp question, and it is worth saying out loud in the walkthrough:
the latency optimisation and the guardrail turn out to be the same mechanism.

### ⚠️ Trap 1 — Google documents this exact pattern failing

From the function-calling docs: requiring the model to emit structured text **immediately before a
tool call** *"may occasionally fail with `Malformed_Function_Call`."*

That is your design, described by the vendor, with a failure mode attached.

**Their documented fix is the one to take:** wrap the pre-tool speech in its own function call
rather than raw text. Define a tool we intercept:

```python
update(text: str)                 # we route this straight to TTS
get_visa_requirements(passport, destination)
```

The model calls both **in parallel** (parallel function calling is supported). We speak the
`update` while the lookup runs. Same behaviour you described, no malformed-call risk, and it is
Google's own recommended pattern rather than a workaround we invented.

### ⚠️ Trap 2 — do not speak the model's thoughts

You suggested using the model's own thinking as the filler. **Don't.** Three reasons:

1. Thoughts are **ungated** — they are not segments, carry no register, and routinely contain
   half-formed factual claims. Speaking them opens a hole straight through the deep dive.
2. In stateless mode, thought signatures must be **passed back verbatim**; they are protocol, not
   content.
3. `thinking_level: "minimal"` produces very little to work with anyway.

The *instinct* — let the user hear what the system is doing — is right. The `update()` call gives
you that, under control, in the register system, gated like everything else.

**Showing thoughts in the UI** (not speaking them) is a different question and a reasonable polish
item. Overflow zone.

### ⚠️ Trap 3 — barge-in now costs quota

If the model is speaking while a vendor call is in flight and the user interrupts, you have to
cancel both — and the request may already be spent. At **120 requests total**, an interrupted turn
that burned one is a real cost, not a rounding error.

Not a reason to drop the design. A reason to: fire the lookup only when the cached map misses
(§Two-tier answering already does this), and count interrupted-but-spent requests in the quota
ledger so the number stays honest.

### The memory extraction call — your version may be better than §6's

Two options, both off the latency path:

| | §6: a `remember` field in the response | Yours: a separate extraction model |
|---|---|---|
| Cost | Free — rides the existing call | +1 LLM call per turn (quota, not latency) |
| Prompt load | Adds memory duty to a prompt already doing two registers, NDJSON, and field paths | Keeps the segmenting prompt focused |

**I now lean toward yours.** The segmenting prompt *is* the deep dive, and its reliability is the
thing we are measuring. Loading memory extraction onto a small model's most important prompt risks
degrading the thing being graded, to save a call that costs no latency at all.

Fire it after the response is dispatched. If free-tier limits bite, fold it back into the main
response as a field — but start separated.

### The RAG knowledge base — stay cut, and for a better reason than time

You said *"maybe that's too deep, maybe not now."* Agreed, but the stronger argument is not time:

> **A hand-built corpus of "travel tips" is unsourced content wearing the costume of retrieval.**

Where would the chunks come from? If we write them, it is our judgement rendered as retrieved
fact — the precise failure the whole project exists to prevent. If we scrape them, provenance is
murky. In a product whose thesis is *never state a fact you cannot source*, a tips corpus is a
loaded gun pointed at the thesis.

**Wikipedia is the right version of this idea** — and it is already planned (P3). It comes with an
attribution URL and a revision date, so a retrieved `extract` can be a genuine `sourced` segment.

So: no tips corpus. If retrieval happens, it retrieves things that carry citations.

### What this changes in the TDD

| § | Change |
|---|---|
| Architecture | LLM #1 emits `update()` + tool call in parallel; TTS starts on the `update` |
| Latency budget | Perceived first sound ~1.2 s; vendor round trip moves off the perceived path |
| Grounding gate | Add one line: a segment's register is bounded by whether its tool result has landed |
| Memory | Separate extraction call, fired after dispatch |
| Barge-in | Cancel in-flight tool calls; count spent-but-interrupted requests |
| Failure modes | `Malformed_Function_Call` → the `update()` pattern is the mitigation |

---

## §14 — Consistency audit: five conflicts between decisions we already made

Before folding any of this into the TDD. Each of these is a place where a later decision
invalidated an earlier one without anybody noticing.

### 1. 🚨 The opener bypasses the gate entirely

**This is the serious one.** §13 puts a spoken opener in front of the answer — but that text
arrives as a **function-call argument**, not as an NDJSON segment. It never touches `resolve()`.

So nothing currently stops:

```python
update(text="Sure — you'll need a tourist visa for up to 90 days, let me confirm the details.")
```

The model has just stated a visa duration, out loud, **before any tool has been called at all.**
That is a worse failure than the §1 hole, because at that point there is not even a tool result to
contradict it.

**Fix, and it is stricter than the segment rule:** at opener time nothing has been sourced, so the
opener may carry **no factual content whatsoever** — it is pure framing. Run it through the same
digit check plus a hard rule that it cannot be `sourced`:

> **Opener contract:** `judgement` register, no digits, no entity-specific claims. Reject and fall
> back to a fixed phrase if violated.

A fixed fallback ("Let me look that up for you") is the right failure mode — it is what the model
should have said anyway.

### 2. 🚨 "Skip LLM #1 on cached turns" does not work

The TDD's latency section claims cached turns need only one completion. **They need two.**

LLM #1 is what extracts *which destination the user asked about*. We cannot know the answer is
cached until we know the pair — and we cannot know the pair without the model reading the
transcript. The cache saves the **vendor round trip**, not the call.

| | TDD claim | Actual |
|---|---|---|
| Cached turn | 1 LLM call, ~1.8 s | **2 LLM calls**, vendor RTT saved (~300–800 ms) |

Not fatal — the saving is still real, and the opener design hides what remains. But the stated
reasoning is wrong and it inflates the cached-turn estimate. Fix the claim, keep the cache.

**One good consequence:** on a cache hit there is no lookup to hide, so Sarjy just answers instead
of saying "let me check." That inconsistency is *correct* — it is what a person does — but it
should be deliberate rather than emergent.

### 3. 🚨 The failover model cannot run the architecture

The stack table names Groq `openai/gpt-oss-20b` as LLM failover, flagged **"no parallel tool
calls."**

The opener design **requires** parallel tool calls — speak and look up at the same time. So the
failover path cannot execute the primary flow.

That is survivable, but it has to be designed rather than discovered at 2 a.m.:

> **On failover, degrade to the sequential flow:** no opener, tool call first, then answer. Slower,
> visibly so, and it still satisfies every requirement. Say which model is serving in the UI.

That is a better story than a failover that silently behaves differently.

### 4. ⚠️ A third LLM call per turn may hit the rate ceiling

§13 moved memory extraction to its own call. Good for prompt hygiene — but it makes **three LLM
calls per turn**, and the only free-tier figure we have (unofficial, §5) is **15 RPM** for
flash-lite.

Three calls per turn = **five turns per minute**. The TDD's own note says a brisk conversation is
six to eight. **We could hit the ceiling during the demo**, which is the one moment it must not
happen.

Three ways out, cheapest first:

| Option | Cost |
|---|---|
| **Gate extraction behind a cheap heuristic** — only fire when the transcript contains "I", "my", "I'm" etc. | ~5 lines. Most turns never trigger it |
| Extract once at session end rather than per turn | Memory not available next turn — breaks the demo beat |
| Fold it back into the response as a `remember` field | Free, but re-loads the segmenting prompt |

**Recommendation: the heuristic.** It keeps §13's clean separation and removes the ceiling risk
for five lines of code.

### 5. ⚠️ Travel suggestions do not need Wikipedia at all

§13 called Wikipedia "the right version of RAG" — true, but it created an implied dependency that
is not there.

**Travel suggestions are `judgement`.** "November is good for Kyoto, the crowds thin after the
leaves turn" is Sarjy's own view, carries no citation by design, and needs no source. That is the
register split working exactly as intended.

So travel suggestions cost **zero extra tool calls, zero extra latency, and zero new sources to
gate.** They are already P1 and already free.

Wikipedia only buys *place descriptions as sourced segments* and *images* — which is P3, where the
PRD already put it. **No change needed; just do not let the TDD imply suggestions depend on it.**

### Also worth fixing while we are in there

| Issue | Fix |
|---|---|
| Barge-in now has to flush **three** audio sources (opener + N segments), not one | Single playback queue, flush-all on interrupt |
| Eval has no category for "opener contained an unsourced fact" | Add cases to the register-integrity category |
| The region A/B will be measured **from Omar's location**, not the reviewer's | Still a useful proxy, but name it in the writeup |

---

## §15 — Two verifications: one vindicates the design, one nearly kills it

### ✅ The `update()` pattern is not a workaround — it is Google's named, preferred solution

Better than expected. Google's function-calling docs **literally name the function `update`**, and
ship a parameter whose description is our use case word for word:

> `external` — *"A short, plain-language note shown to the User about what you are ABOUT TO DO
> next."*

And the sentence that validates the whole architecture:

> *"Then the model will make two calls in the same step: the `update()` call that replaces the
> structured XML, and the actual function call it wants to make."*

Their prescribed system instruction, verbatim:

> *"Before calling any other tool, in every response you MUST first call `update` with all required
> parameters."*

**One correction to §13:** the failure it avoids is narrower than I said. `Malformed_Function_Call`
is triggered by **structured** text (XML/YAML/JSON) before a tool call, not prose. So plain text
plus a function call is structurally fine. We take `update()` anyway — it is the documented path,
it gives the opener a typed home, and it costs nothing.

**And the latency claim holds:** `step.start` delivers the function *name and id before any
argument token is generated*, so we can fire the lookup mid-stream rather than waiting for the
response to finish. The design saves real time.

#### 🪤 A landmine worth an hour of your Sunday

**Google's own docs contradict each other on the streaming field name.** The function-calling page
samples `delta.type == "arguments"` with `delta.partial_arguments`. The streaming page *and* the
API reference both say `arguments_delta` with field `arguments`.

**Trust the reference.** Copying the function-calling sample gives you a loop that silently matches
nothing and accumulates an empty string — no error, no output, no clue.

#### Three things to handle

| Issue | Consequence |
|---|---|
| **`tool_choice` cannot express "must call `update()`, may call the lookup."** `any` forces *at least one* call, not *which* | The must-call rule is prompt-only — a soft guarantee. **Handle "model skipped the opener"**: fall through to the silent path |
| **Parallel function calling is undocumented for `gemini-3.5-flash-lite` specifically** — every example uses `gemini-3.8-flash` | **Measure on our model before committing.** Day 1 |
| Call 2 likely needs a `function_result` for **both** calls, `update()` included | An unanswered call may invalidate the turn |
| A `thought` step is emitted even at `thinking_level: "minimal"` | Confirms §10: measure TTFT to the first **text** delta |

### 🚨 The TTS finding that nearly kills per-segment playback

**Gemini TTS has no continuity primitive. None.** No session, no acoustic context, no documented
seed for TTS. Every request is an independent generation — and the docs warn in exactly the wrong
direction:

> *"The model's output may not always strictly match the selected speaker, causing the audio to
> sound different than expected."*

Across four requests in one turn, that per-request variance becomes **an audible seam mid-sentence.**
Three more multipliers:

- The `PROHIBITED_CONTENT` mitigation requires a preamble instructing synthesis — so every short
  segment pays that prompt's tokens and processing latency. On a six-word opener the overhead
  ratio is brutal.
- The documented random `500` is **per request**, so a four-segment turn fails at roughly 4×, and
  a retry lands mid-utterance with a *fresh voice sample* — precisely where the seam is loudest.
- **There is no cancel for a stream.** `/cancel` is background-only. Barge-in means closing the
  socket, and whether generation and billing stop is undocumented.

§4 chose "buffer per segment" and §13 layered an opener on top. **Both assume several TTS requests
per turn concatenate into one voice. Nothing in the docs supports that.**

### ✅ The resolution: the opener already buys us the time, so stop segmenting TTS

Work the arithmetic and the problem dissolves.

The opener is ~1.5–2.5 s of speech. Underneath it we need: vendor round trip (0.3–0.8 s) + LLM #2
**complete** generation (~0.8 s) + gate (~0 s) + TTS first byte for the answer (~0.5–0.9 s) ≈
**1.6–2.5 s.**

**That fits under the opener.** So:

> **Two TTS requests per turn, not five.** One for the opener, one for the whole gated answer —
> and the boundary between them is a *natural prosodic pause*, which is where a seam is inaudible
> because a person would pause there too.

| | Per-segment TTS | **Opener + one answer** |
|---|---|---|
| TTS requests per turn | ~5 | **2** |
| Seam risk | Mid-sentence, audible | At a natural pause — expected |
| `PROHIBITED_CONTENT` preamble overhead | ×5 | ×2 |
| Random-500 blast radius | ~5p | ~2p |
| Latency | Fastest on paper | **Same in practice** — the opener hides full generation |

**Keep per-segment *gating*** — validating each NDJSON line as it arrives is still the right model,
and it is what makes the malformed-line path cheap. **Drop per-segment *synthesis*.** Validate
incrementally, speak once.

This is simpler, safer, and costs nothing. It is the best trade in this entire review, and it only
appeared because two separate research passes collided.

### Sarjy's voice: **Sulafat**

30 prebuilt voices, each with a one-word label from Google. **`Sulafat` is the only voice Google
labels *Warm*** — which is the brief, literally. Alternates: `Vindemiatrix` (*Gentle*) if Sulafat
reads too soft delivering a visa fact; `Rasalgethi` (*Informative*) for a more authoritative
register.

⚠️ **The labels are English-flavoured and nothing says they hold in Arabic.** Listen to all three
in both languages — that listening test is a legitimate entry in `docs/measurements/`.

Also: **no SSML.** Style is steered by natural-language prompt plus inline audio tags
(`[whispers]`, `[very slow]`). And Google's guidance is to keep audio tags in English *even for
non-English transcripts*.

### Two more things to carry into the build

**Override the SDK's retry defaults.** Google's Python SDK retries transient errors up to four
times with backoff to **60 seconds**. Inside a voice turn that is a hung demo. One retry, ~250 ms,
then fail visibly.

**A conflict between our own two research passes, flagged not resolved:** the first said the
Interactions API is GA and recommended for new projects; the second found it labelled Beta with a
live breaking-change migration, and `generateContent` recommended *"for stable production
deployments."* Both stream on this model. **Recommendation: stay on Interactions, pin
`Api-Revision: 2026-05-20`** — it is where the current docs are, and a breaking change inside a
three-day window is near-zero risk. Behind the provider adapter either way.
