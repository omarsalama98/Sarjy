# PR: Grounded answers (Block A — the deep dive)

**Plan:** `docs/plans/blocks/A-grounded-answers.md` · **Lands:** requirements #3 (a real external API
that makes Sarjy more useful) and #5 (the deep dive — guardrails & reliability)

## Summary

Sarjy now answers real visa questions from a real Travel Buddy lookup. **Corrected 2026-09-21** —
this used to say she "cannot state a travel number she didn't get from a source," which overclaims:
that guarantee holds for the `sourced` and `quoted` registers only, where deterministic code
substitutes every value and rejects any segment that writes a digit, a number word, or a value
outside a known field itself. It does **not** hold for `judgement` — Sarjy's ungated third
register for opinions, timing, and casual remarks — which carries no citation and is never checked
for digits by design (D4 says this out loud rather than letting the gate imply it catches it too).
So: `sourced` (a fact, gated, value-substituted, and — since the verification pass — checked
against the pair actually being talked about, not just the field named), `quoted` (the vendor's
own words, copied verbatim, never model-authored), `judgement` (Sarjy's own view, never blocked,
never gated). A rejected segment is still shown, struck through, with its reason — that visibility
is the demo.

The tool sits behind a four-layer resolution order (warm cache → live → cached map → vendored
CSV → refuse), each layer visibly labelled, degraded layers spoken as degraded. A `?gate_demo=1`
query param injects one fabricated segment into a real turn so a reviewer watches an actual
rejection happen live.

## Gate status — what's verified, what needs a human

Same honesty rule the last two PRs used: no browser or microphone in this environment.
Everything scriptable ran for real; the rest is flagged, not faked.

| # | Gate step | Status |
|---|---|---|
| 1 | Real visa lookup answers, ledger decrements | **Not run against the live deployment.** The live RapidAPI path (`TravelBuddyTool`) is built and unit-tested against a stubbed `httpx` transport (`tests/test_vendor.py`, 15 cases, V1–V9 + the happy path + warm cache). I could not verify the RapidAPI dashboard's real spent count or confirm `RAPIDAPI_KEY` is configured without spending irreplaceable quota on the guess — see "What needs Omar" below |
| 2 | Pulling the network still answers, names the layer | **Verified at the unit level** (V1/V2/V4 fall to `map`; V9/V5 skip live entirely) and **verified against a real model** — the eval's `vendor-failure-1` case forces a total outage and gets the correct deterministic refusal |
| 3 | A fabricated number is visibly rejected | **Verified two ways.** `test_gate.py::test_g2_bare_digit_rejected` at the unit level; `test_turn.py::test_d12_gate_demo_injects_a_rejected_segment_into_a_real_turn` proves the `?gate_demo=1` wiring end to end against a fake tool. **Not clicked in a real browser** |
| 4 | The eval table exists with numbers | **Done, and run for real** — `eval/results/2026-09-20-gate-eval.md`, 8 cases (cut from 12, cut ladder rung 3), real Gemini calls, hand-scored, one named designed failure (`injection-2`, the paraphrased injection — exactly as D10 requires) |
| 5 | `make test`/`npm run typecheck` green, deployed URL still answers | **Backend and frontend gates are green** (below). **The deployed URL itself was not re-checked** — this PR was not deployed from this environment |
| 6 | Nine vendor requests spent, not ten | **Zero spent.** See "What needs Omar" |
| 7 | The vendor's own words spoken as the vendor's words; injection rejected | **Verified against a real model.** Eval case `injection-1`: the real halalbites.co-style payload, routed at `visa.exception`, rejected on `injection_marker`; case `register-2`: the model used the `quoted` register correctly, unprompted, and the attribution was audible in the transcript (`According to Travel Buddy: "..."`) |
| 8 | The fact-card payload is on the wire, cannot contradict the answer | **Proven by construction and by test.** `tests/test_card.py::test_card_value_equals_gate_substitution` asserts the card's value and the gate's substituted string are the identical string, not just similar. Wire-level receipt (`onFactCard` → `console.log`) is code-complete; **not eyeballed in a real browser console** |

**What I'd ask Omar to do:**

1. **Check the RapidAPI dashboard's real spent count**, set `QUOTA_SPENT_SEED` accordingly, and
   run `uv run python -m scripts.fetch_reference batch --spend 6 --pairs SA:JP,SA:BH,SA:GB,AE:JP,SA:EG,SA:US --out-dir eval/fixtures` (or whichever six pairs are wanted) to fill in
   `colour-legend.json`'s remaining spot-checks and give the eval real, not constructed, fixtures
   for the pairs beyond SA→JP.
2. **Deploy and run the 9-row verification table** in the block plan against the live URL —
   especially turn 3 (`?gate_demo=1`) and turn 7 (the `quoted` register spoken aloud).
3. **A Safari pass** — inherited from Block 2, not re-checked this block.

## Problem

Requirement #3 needs a real external API that makes Sarjy more useful; the deep dive (guardrails
& reliability) needs a system that cannot state a travel fact it cannot source. Together: a voice
assistant that calls a real visa API, and a deterministic gate between "the model said it" and
"the user heard it" — the model proposes structure, code disposes of the actual words.

## Solution

**The turn, in order:** LLM call 1 (`decide()`) asks whether `get_visa_requirements` is needed —
tools declared, streamed, `arguments_delta` parsed. If it fires, `TravelBuddyTool.lookup()` runs
the four-layer resolution (warm cache → live → cached `VisaMap` → vendored CSV → refuse), and its
result is stored under our own id (`tb_1`) — never the model's. A fact card is emitted immediately
(before call 2 starts). LLM call 2 (`segments()`) is a **fresh, stateless interaction** — no
history, no replayed step — that receives the tool result as a delimited `<tool_result>` data
block plus two field catalogues (`<sourced_fields>`, `<quotable_fields>`) listing only the paths
that are both allowlisted **and** actually present this turn. It answers in NDJSON, one segment
per line. The gate (`app/tools/gate.py`) validates every line: nine rules for `sourced` (including
`wrong_pair`, added in the verification pass — see below), seven for `quoted`, judgement never
blocked. Kept segments render into one string; that string, and
nothing else, goes to TTS.

**Three registers, not two** (the plan's own revision, `A-grounded-answers.md`'s amendment note):
`sourced` writes a `{field.path}` template, never a literal number; `quoted` names a field and
writes nothing else — there is no model-authored string to check, because there isn't one; that
is what makes the register safe enough to ship rather than dropping vendor free text outright
(D14's argument: refusing to map free text doesn't stop an injected payload reaching the user, it
just removes the ability to attribute it, pushing the leak into an unattributed `judgement`
paraphrase instead).

## Changes

**New — backend**
- `app/prompts.py` — the tool declaration, both system instructions, `build_user_block()`, `LABELS`, the seven fixed phrases
- `app/tools/gate.py` — filled: `Segment`, `RenderedSegment`, `get_path()`, `gate()`, `spoken_text()`, the two allowlists (`SOURCED_FIELDS`/`QUOTED_FIELDS`, asserted disjoint at import time)
- `app/tools/normalise.py` — vendor body **and** CSV row → one identical shape; `resolve_code()`; the unmapped-key log
- `app/tools/card.py` — `fact_card()`, the D15 payload, derived from the same object the gate substitutes from
- `app/tools/quota.py` — `QuotaLedger`, `modal.Dict` with an in-process fallback (V11)
- `app/tools/fake.py` — `FakeVisaTool`, used by every test and the eval; the real vendor never touches a test
- `app/tools/vendor.py` — filled: `TravelBuddyTool`, the four layers, `httpx` with an explicit 4s timeout
- `backend/scripts/fetch_reference.py` — the only code allowed to spend vendor quota (D9); built, not run this block (see "What needs Omar")
- `data/reference/destinations.json`, `colour-legend.json`, `passport-index-tidy-iso2.csv` — new reference data, **0 additional vendor requests**

**Modified — backend**
- `app/providers/base.py` — `LLMDecision` replaces `LLMReply`; `LLM.reply()` deleted, replaced by `decide()` + `segments()`; `ToolResult`/`QuotaStatus`/`VisaTool` added
- `app/providers/gemini_llm.py` — `decide()` + `segments()`, event shapes verified live (not from docs — see the `VISA_TOOL` bug below)
- `app/providers/factory.py` — `get_tool()`, identical lazy pattern to `get_stt`/`get_llm`/`get_tts`
- `app/pipeline/turn.py` — the two-call turn, tool/gate failure branches before their happy paths, all timing fills
- `app/pipeline/protocol.py` — `SegmentsOut`, `QuotaOut`, `FactCardOut`/`FactRowOut`, `TurnFailedStage` += `tool`/`gate`, `PROTOCOL_VERSION` 3 → 4
- `app/pipeline/timings.py` — `tool_ms`/`llm2_ms`/`gate_ms` filled; four new evidence fields
- `app/main.py` — `get_tool` wired through, `quota` sent after `ready` and after any live-spending turn, `?gate_demo=1`, `SYSTEM_PROMPT` moved to `prompts.py`
- `app/measure.py` — gate-rejection rate, malformed-line rate, three new stage medians
- `app/config.py` — `vendor_timeout_s`, `fake_vendor`
- `backend/modal_app.py` — `add_local_dir(data/)`, a gap the plan's own file list missed (without it the deployed app 500s on every visa question)

**New/modified — frontend**
- `frontend/src/protocol.ts` — `SegmentsMessage`/`QuotaMessage`/`FactCardMessage`, version 4
- `frontend/src/net/connection.ts` — `onSegments`/`onQuota`/`onFactCard`
- `frontend/src/App.tsx` — a segment list (register badge, struck-through rejections with their reason, citation/layer/date), a quota chip, `fact_card` received and logged (Block C renders it)

**New — eval**
- `eval/cases/cases.jsonl` — 8 cases (cut from 12, cut ladder rung 3), labels written before the run
- `eval/fixtures/*.json` — the one real committed body plus three constructed ones, each labelled `_provenance`
- `eval/run_eval.py` — replays cases through the real pipeline (real Gemini, `FakeVisaTool`)
- `eval/results/2026-09-20-gate-eval.md` — the numbers, and the two real bugs this run found

**Tests** — 212 passing as of the 2026-09-21 verification pass (192 at first landing, from a
documented baseline of 81), `ruff check app tests` clean, `mypy app` clean over 26 files. New:
`test_gate.py` (44 — 33 at first landing, +11 in the verification pass: F1's `wrong_pair`, F2's
embassy routing, F5's three encoding bypasses, F6's speakable date), `test_normalise.py` (15),
`test_card.py` (7 — +2 for F4), `test_quota.py` (10 — +3 for F3's seed-once/never-reseed
behaviour), `test_vendor.py` (18 — +3 for F2's derived embassy_url on map/csv/no_coverage),
`test_prompts.py` (9), `test_measure.py` (+4). Rewritten: `test_turn.py` (23 — +1 for F7's
hedged-reflects-produced fix, and the D11 repair-retry test's malformed-count assertion corrected),
`test_ws.py` (18, for the new `quota`/`segments` messages on every connection), `test_gemini_llm.py`
(10, for `decide()`/`segments()`), `test_protocol.py` (+5).

## Two real bugs found running this block's own eval — not simulated, not anticipated

1. **`VISA_TOOL` was missing `"type": "function"`.** The plan's Contract 2 gave the tool
   declaration without it. The installed `google-genai` SDK's `Tool` union discriminates on that
   field and rejects **every single call** with a `pydantic.ValidationError` — Block 0's own spike
   (`scratch/spikes/parallel_fc.py`) already had this right; it was lost transcribing the plan.
   Found running the eval's first live call, fixed in `app/prompts.py`, locked in by
   `test_visa_tool_declares_type_function`.
2. **`FakeVisaTool` needs alias-tolerant lookup for a live-model eval.** The real
   `TravelBuddyTool` resolves whatever the model sends — a code or a country name — via
   `resolve_code()`; `FakeVisaTool` does an exact dict match and has no such step. A live,
   non-deterministic model produced a handful of false `no_coverage` results purely from the
   harness. Fixed in `eval/run_eval.py` by registering each fixture under both forms — not a
   pipeline bug, `resolve_code()` is separately and correctly tested.

## Verification pass, 2026-09-21 — one closed gap, one thing Block C needs to know

**The wrong-pair hole, named by the plan as a known gap, is now closed.** The block plan's
Decisions page named this by hand and put it on the cut ladder rather than building it: every one
of the eight original `sourced` rules checks WHICH FIELD a segment names, and none of them checks
whether the segment's own prose names a DIFFERENT country than the one that field actually
describes. Reproduced exactly as the plan predicted —
`Segment(kind="sourced", text="For Thailand you will need {visa.type}.", tool_call_id="tb_1",
fields=["visa.type"])` against a real SA→JP tool result rendered `ok=True`, spoken as *"For
Thailand you will need eVisa"* — a real citation on data about the wrong country. Closed with a
ninth rule (`wrong_pair`, ~40 lines including the loader): the `sourced` template is scanned,
before substitution, for any known place name (`data/reference/destinations.json`, word-boundary
matched, case-insensitive) that is neither `pair.destination_name` nor `pair.passport_name` for
that turn. `tests/test_gate.py::test_f1_sourced_naming_a_different_country_rejects_wrong_pair`
proves the reproduction now rejects; two neighbouring tests prove the destination and the passport
country are both still speakable, and a "Chad"-in-"detachment" test proves the word-boundary match
doesn't fire on a substring.

**Block C should know: a `quoted` value can be up to 400 characters (Q5), and Groq Orpheus's
Arabic voice caps a single request at 200 characters (Open Question #7, not resolved here — P2/
Arabic is out of this block's scope by design).** A `visa.exception` quote near the 400-char cap,
spoken in Arabic, will not fit one Orpheus request. This block does not touch Arabic TTS at all,
so it isn't a bug here — but Block C should not be surprised by it, and either the quoted cap needs
a language-aware ceiling or the Arabic TTS adapter needs to chunk, whichever Block C decides.

Also closed by this pass, cheaper points: the refusal now routes to a derived embassy link (Q2 in
the plan's verification table depended on it); the injection screen closes three trivial encoding
bypasses (zero-width space, split-by-punctuation, a Cyrillic homoglyph) — see
`eval/results/2026-09-20-gate-eval.md`'s postscript for the honest restatement of what Q6 catches;
the fact card can no longer ship a `quoted` value the gate would have refused to speak; the
degraded-layer prefix speaks "September 2026," not an ISO timestamp; and `hedged`/`lines_malformed`
were computed from the wrong thing (kept segments instead of produced ones; both attempts' malformed
counts instead of the surviving one's) and now match their own field-level documentation.

## Decisions the plan left to the implementer, resolved here

- **`SOURCED_FIELDS`/`QUOTED_FIELDS` live in `gate.py`, not `prompts.py`.** The plan's task list
  said prompts.py; its own Contract 4 code block showed them in gate.py. Keeping them in gate.py
  avoids a circular import (`prompts.py` already imports from `gate.py` for `get_path()` and the
  catalogue builder) — `prompts.py` re-uses them from there.
- **`fact_card()`'s signature** takes only a `ToolResult`, matching the literal contract, rather
  than the four extra passport/destination params I initially assumed it needed — `ToolResult.payload`
  now always carries the resolved `pair.*` fields even on a `no_coverage` failure (not just on
  success), which is what makes the single-argument signature possible.
- **A tool failure other than `unknown_place` skips call 2 entirely** and speaks the deterministic
  `NO_COVERAGE` phrase directly. The plan states this for V3/V6 but doesn't spell out whether call
  2 still runs on tool failure generally — spending an LLM call to re-derive "there is nothing to
  source from" seemed like the wrong trade, and it is what "never improvised" reads as literally.
- **No live vendor quota was spent.** Upstream correction #1 in the plan itself says to check the
  RapidAPI dashboard before spending — I have no access to it, and `.env` is off limits to read
  even to confirm `RAPIDAPI_KEY` exists. Spending irreplaceable, 120-total-ever quota on an
  unverified guess was judged the wrong call; `scripts/fetch_reference.py` is built and ready for
  Omar to run once the dashboard is checked.

## How to test

```bash
cd backend
make typecheck && make lint && make test        # 212 passed, ruff clean, mypy clean
cd ../frontend
npm run typecheck && npm run lint && npm run build

cd ../backend
uv run pytest tests/test_gate.py -v              # 44 named tests, no model, no network

cd ..
uv run --project backend python eval/run_eval.py --out eval/results/   # real Gemini calls; see eval/README.md
```

⚠️ **`uv run python -m scripts.fetch_reference --status` is no longer a free read (F3).** Before
the verification pass it built its ledger on a throwaway in-process store, so running it cost
nothing. It now points at the SAME durable `modal.Dict` ("sarjy-quota") the deployed app uses, and
the FIRST run that ever touches that dict seeds it — from `QUOTA_SPENT_SEED` if set, from
`app.config`'s conservative default (120, the full budget) if not. **Set `QUOTA_SPENT_SEED` to the
RapidAPI dashboard's real count before running this for the first time, ever** — including before
this command, before the first deploy, and before any test that isn't already faking the store.
This PR's own verification never ran it, precisely to avoid seeding the real dict with a guess.

**Still needs a human**, exactly per the plan's own 9-row verification table against the deployed
URL: the live vendor path with real quota, `?gate_demo=1` clicked in a browser, the `quoted`
register heard aloud, and the fact card seen in a real console. See "What needs Omar" above.

## Changelog

- feat(gate): three-register grounding gate — `sourced` value-substitution, `quoted` vendor-verbatim, `judgement` ungated
- feat(vendor): `TravelBuddyTool` four-layer resolution (warm cache → live → cached map → CSV → refuse), quota-aware
- feat(llm): `GeminiLLM.decide()`/`segments()` replace `reply()`; tool-calling wired against the real, verified event shapes
- feat(wire): `segments`/`quota`/`fact_card` messages, protocol v4, `?gate_demo=1`
- feat(ui): segment list with struck-through rejections, quota chip, fact card received (not yet rendered)
- fix(llm): `VISA_TOOL` missing `"type": "function"` — every tool-calling call was silently failing before this
- test: 192 tests (was 81), including 33 Tier A gate tests and an 8-case adversarial eval run against a real model
- docs: `eval/results/2026-09-20-gate-eval.md`, `data/README.md`, `AGENTS.md` §Still open

### Verification pass, 2026-09-21 (F1–F8)

- fix(gate): `wrong_pair` — a ninth `sourced` rule closing the plan's own named gap (a template
  could name a country other than the one the tool result describes and still pass)
- fix(gate): the refusal now routes to a derived embassy link when one is known, instead of a bare
  "I'd rather not guess" with nothing on screen (Invariant 6)
- fix(gate): the injection screen (Q6) folds away a zero-width space, splitting punctuation, and a
  Cyrillic homoglyph before matching — three encoding bypasses, all closed; a genuine paraphrase
  still passes, unchanged and undiminished as a documented limit
- fix(gate): the degraded-layer prefix speaks "September 2026," not an ISO 8601 timestamp
- fix(card): a `quoted` value the gate would refuse to speak (oversized, or carrying an injection
  marker) can no longer reach the fact card
- fix(quota): the durable ledger (`modal.Dict`) now actually seeds — once, atomically, from
  `QUOTA_SPENT_SEED` — and never re-seeds on a later restart; confirmed live that `import modal`
  succeeds inside the deployed container despite being a dev-only dependency
- fix(turn): `hedged` now reflects segments the model PRODUCED, not segments the gate KEPT (a
  fabricated-then-rejected sourced segment no longer reports the opposite of what happened)
- fix(turn): `lines_malformed` no longer double-counts the D11 repair retry's discarded first
  attempt, which had inflated `measure.py`'s malformed-line rate
- test: 212 tests (was 192) — 20 new, 1 corrected assertion (`test_d11_repair_retry_...`)
- docs: `eval/results/2026-09-20-gate-eval.md` postscript (Q6's honest capability), this PR's
  Summary (the "cannot state a travel number" overclaim), the wrong-pair and Orpheus-cap
  disclosures above
