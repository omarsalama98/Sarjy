# PR: Memory (Block B)

**Plan:** `docs/plans/blocks/B-memory.md` · **Lands:** requirement #2 (remembers across sessions)

## Summary

Sarjy now has durable, inspectable memory. A user gives a name and a 4-digit PIN (typed, or
spoken — "remember me" starts a deterministic two-turn voice sign-in sub-flow, no LLM involved);
everything they teach Sarjy is stored as a `Fact` — key, value, label, when it was learned, and
the **verbatim sentence that taught it** — in a `modal.Dict` keyed by the normalised name. The
"what Sarjy remembers" panel is driven by one `memory` message, re-sent in full after every
sign-in, sign-out, forget, or background extraction, so there is no client-side memory state to
drift from the server's.

**D7 — the one thing the plan called out as most likely to be shipped broken — is implemented and
tested both ways.** `run_turn`'s spoken answer always comes from call 2 (a fresh, stateless
NDJSON completion); call 1's own text is never spoken. The `<known_about_user>` block therefore
goes into **both** calls: call 1 can fill in a passport from it before deciding whether to call
the visa tool, and call 2 — the only call whose output the user ever hears — is what actually
answers "what's my favourite colour?". `tests/test_turn.py`'s `test_d7_memory_block_reaches_*`
tests assert this against the fake `LLM`, separately for each call, plus a case where a tool
fired too.

**Because a recalled fact carries no `tool_call_id`, it can only ever render as `judgement`.** A
`sourced` segment citing it fails the gate's own rule 1 (`unknown_tool_call_id`) structurally —
free protection against "can a user poison your citations by teaching Sarjy a fake fact," and it
required no new gate code, only one sentence in `SYSTEM_SEGMENTS` naming `<known_about_user>` as
DATA alongside `<user_question>`/`<tool_result>`.

Extraction is its own LLM call, fired **after** the user has already heard the answer
(`asyncio.create_task`, never awaited before `state: idle`), gated by a cheap self-statement
heuristic so it doesn't triple the LLM call rate on every turn. What it proposes is deterministically
filtered — `validate_candidate()` drops a bad key, an oversized value, a value containing `{` or
`}` (the load-bearing rule: a stored fact must never become an unintended template placeholder
later), or a known injection marker — before anything reaches the store.

## Cut ladder — none taken

The plan pre-committed a five-rung cut ladder (drop voice sign-in first, then anonymous→signed-in
migration, then per-fact delete, then the quote in the panel, then the anonymous tier's panel
rendering) for a human working against a 19:00 clock. **I didn't need any of it** — D8 (voice
sign-in), D2 (migration), the quote + `learned_at` in the panel, and the anonymous tier's panel
are all built. The honest trade: most of my own time went into a debugging detour (below), not
feature scope — worth naming plainly rather than claiming a clean run.

## The two things that went wrong building this

**1. `tests/test_ws.py`'s `_FakeLLM.decide()` wasn't updated for the new `memory_block` parameter
— exactly the trap the plan named — and it didn't fail loudly.** `run_turn` calls
`llm.decide(..., memory_block=memory_block)` unconditionally; the old fake's `decide()` had no
such parameter, so every turn in that file raised `TypeError` *inside* `run_turn`'s own
`except Exception` around the call, silently downgrading into a normal `turn_failed`. That, in
turn, made two barge tests hang for real: they expect a slow multi-chunk TTS stream to race a
`barge` message, but with the turn failing at the LLM stage instead, there was no audio stream to
race, and `ws.receive_bytes()` blocked forever waiting for a binary frame that would never come.
Diagnosed with `faulthandler.dump_traceback_later` (no `py-spy`/`sudo` available in this
environment) — the traceback pointed at `ws.receive_json()` inside the test, and a few debug
prints in `_serve()`'s receive loop confirmed the server had genuinely stopped hearing anything
after `end`, not that cancellation itself was broken. Fixed by adding `memory_block: str = ""` to
both fakes in `test_ws.py` (`_FakeLLM.decide()` and the history test's `_RecordingLLM.decide()`).

**2. Worse: `app/memory/store.py`'s `get_store()` successfully constructs a REAL `modal.Dict`
in this dev environment** (the same F3 discovery `app/tools/quota.py` documents for
`import modal` — confirmed live, not assumed) **— so every memory test that didn't explicitly
inject a store was silently reading and writing the real `sarjy-memory` Dict.** Found by a
"Welcome back, Bob Ws" message where "Nice to meet you, Bob Ws" was expected, on a test re-run in
a fresh process — impossible unless the record genuinely persisted somewhere outside the test
process. Confirmed with `modal.Dict.from_name("sarjy-memory").keys()`: eight fake sign-in names
and a cross-session test key were sitting in the real cloud dict. **Cleaned up** (all eight keys
removed, re-verified empty) and **fixed properly**: `tests/conftest.py` now autouse-patches
`_ModalDictStore` to always fail across the whole suite, forcing every test onto the in-process
fallback and clearing it before each test. `sarjy-quota` was never touched (`quota.py`'s
`QuotaLedger()` in these tests always takes its own explicit fake store) — verified directly
after the fact: `spent` is still `None`, i.e. nobody has ever written to it from here.

## Open questions the plan flagged — answered, not guessed

1. **Does `modal.Dict.delete()` exist on the installed client? No.** Checked live:
   `dir(modal.Dict)` has no `delete`; `.pop(key, default)` is the real removal method, and it's
   what `_ModalDictStore.delete()` uses. Not the plan's own suggested fallback (write an empty
   dict over the key) — `.pop()` is a real primitive, not a workaround.
2. **Does `modal.Dict` pickle a plain nested dict cleanly? Yes, observed on the REAL dict** (by
   accident, before the conftest fix landed) — `MemoryRecord.to_json()`'s nested
   dict-of-primitives-and-lists round-tripped correctly through a genuine `modal.Dict.put`/`.get`
   cycle (that's exactly how "Bob Ws" came back as "Welcome back" with his facts intact). Real
   evidence, not a guess, even though it arrived as a side effect of a mistake.
3. **Will `gemini-3.5-flash-lite` reliably emit nothing when there's no fact? Unverified.** No
   real Gemini calls were made anywhere in this block — everything above is proven against fakes.
   Watch the first few real turns' `memory_dropped` counts in `modal app logs`.
4. **Does the third LLM call trip an unpublished rate limit? Unverified**, same reason.
5. **The spoken PIN and Whisper. Unverified against real STT.** `parse_spoken_pin()` is
   unit-tested against the exact transcript shapes the plan names (numerals, spelled-out words,
   "oh" for zero) — not against what Whisper actually returns for a real spoken PIN. This is the
   plan's own named cut-ladder-item-1 risk if it doesn't hold up live.

## Things worth knowing before the demo

- **D8's voice sign-in speaks its confirmation optimistically.** `run_turn` cannot await the
  store without importing it (Invariant 3), so "Got it, Omar — pin four seven one two" is spoken
  the instant a valid-shaped name+PIN is *heard*, before `main.py` resolves identity against the
  store afterward. If that resolution turns out to be an M3 clash (a different Omar already
  exists under that PIN), the voice already said "I'll remember you" and the **panel** is where
  the correction actually shows up (`SIGNIN_CLASH`, tier stays anonymous) — never contradicted by
  voice, but not confirmed by it either. Same trade-space the TDD accepts for extraction ("we
  never say 'got it' by voice at all").
- **`_handle_forget`'s "everything" always calls `save_record()` with an emptied fact list, never
  `delete_record()`.** `delete_record()` is real and unit-tested (`test_m1_...` isn't the one —
  see `test_memory.py`'s store section) but wiring it into "forget everything" would mean a
  reload afterward hits the "no record found → create fresh" path, silently accepting *any* PIN
  rather than refusing on a mismatch — a worse property for a nameplate whose whole job is
  refusing on mismatch. Kept simple; `delete_record` is there if a real "delete my account"
  action is ever wanted.
- **A "remember me" sign-in request also fires a (usually empty) extraction LLM call**, because
  "remember" is itself one of `looks_self_referential()`'s own trigger words. Harmless — the
  model has nothing to extract from that sentence and the heuristic's whole job is a false-positive
  filter, not a precise one — but it's one more real LLM call per sign-in flow, worth knowing if
  the unofficial rate limit ever bites.
- **A typed `sign_in` racing a voice sign-in's post-turn resolution** (both mutating
  `session.memory`/`session.pin_attempts` concurrently) is unhandled — the same category of edge
  case M12 already accepts as "documented, not fixed" for an ordinary `sign_in` mid-turn. Not a
  realistic demo scenario (one person, one mouth, one keyboard, at once).
- **New environment variable: `SARJY_MEMORY_SALT`.** Read directly from `os.environ` in
  `app/memory/identity.py` (never through `app.config.load_settings()`, which raises on a missing
  *provider* key — memory must not inherit that failure mode). Defaults to `"sarjy-dev-salt"` if
  unset, which is fine for a local dev PIN hash but **should be set to a real secret on the Modal
  deployment** before the demo — `.env.example` is off limits to me (deny rule); please add
  `SARJY_MEMORY_SALT` there and to the Modal secret yourself.

## Problem

Requirement #2: "remembers across sessions" — told once, recalled after a reload, in a fresh
session, and demonstrable in one glance (Invariant 4: structured, attributable, inspectable, not
an opaque blob of chat history).

## Solution

- **One store, two key classes** (D1) — `Fact` records with a three-key `PROFILE_KEYS` allowlist
  (`name`, `passport`, `home_city`), `kind` derived from membership, never stored. A deliberate,
  documented deviation from the TDD's "two kinds of memory" (two stores, a typed `TravelProfile`)
  — one list, one panel, one wire type, one cap, at roughly half the code.
- **Two tiers** (D2) — `Session.memory` (in-process, survives a reconnect, not a reload) and the
  signed-in tier (`modal.Dict`, survives everything). Anonymous facts migrate into the signed-in
  record on every sign-in, union by key, higher `learned_at` wins.
- **Identity as a nameplate, not auth** (D3) — name + 4-digit PIN, salted hash only, refuse on a
  mismatch rather than silently opening an empty record. Five failed attempts per session, then
  locked until reload. Explicitly *not* a security boundary; the write-up says so.
- **Extraction after dispatch** (D4) — `app/memory/extract.py`, gated by
  `looks_self_referential()`, filtered by `validate_candidate()`, at most 3 facts/turn.
- **D7** — the memory block into both LLM calls (above).
- **D8** — voice sign-in as a two-turn deterministic sub-flow in `run_turn`, no LLM call, driven
  by two parameters (`awaiting_pin` in, `on_sign_in` callback out) rather than a `Session`
  reference, so `run_turn` still never imports `app.session`.
- **The panel** (D5) — one `MemoryOut` message, one `aside`, class names only (Block C owns the
  styling pass).

## Changes

| File | What changed |
|---|---|
| `backend/app/memory/store.py` | Replaced wholesale — `Fact`, `MemoryRecord`, `_ModalDictStore` (`.pop()`, not `.delete()`), module-level `_InProcessStore`, `get_store()`, `load_record()`/`save_record()`/`delete_record()` (all via `asyncio.to_thread`) |
| `backend/app/memory/extract.py` | New — `SYSTEM_EXTRACT`, `looks_self_referential()`, `build_extract_block()`, `validate_candidate()`, `extract_facts()` |
| `backend/app/memory/identity.py` | New — `normalise_name()`, `pin_hash()`, `parse_sign_in_request()`/`parse_spoken_pin()`/`spoken_digits()`, the D8 fixed phrases |
| `backend/app/pipeline/protocol.py` | `PROTOCOL_VERSION` 4→5; `SignInIn`/`SignOutIn`/`ForgetIn`, `FactOut`/`MemoryOut` |
| `backend/app/session.py` | `Session.memory`/`awaiting_pin`/`pin_attempts`; docstring de-staled ("Block 7" no longer exists) |
| `backend/app/main.py` | `_send_memory()`, `_resolve_sign_in()`, `_handle_sign_in`/`_handle_sign_out`/`_handle_forget`, the background `_extract_memory()` task, `_process_turn`'s D8 resolution block |
| `backend/app/pipeline/turn.py` | `memory_block`/`awaiting_pin`/`on_sign_in` params; `_handle_sign_in_turn()` (D8) |
| `backend/app/prompts.py` | `build_memory_block()`; `memory_block` on `build_user_block()`; two prompt sentences |
| `backend/app/providers/base.py` + `gemini_llm.py` | `memory_block` on `LLM.decide()`; `segments()` docstring notes its second caller |
| `backend/app/pipeline/timings.py` | `memory_facts`/`memory_extracted`/`memory_dropped`/`memory_persisted` |
| `backend/tests/test_memory.py` | New — 35 tests: store, record, identity, extraction, the cross-session load-bearing assertion |
| `backend/tests/conftest.py` | New — autouse fixture forcing every test onto the in-process memory store |
| `backend/tests/test_ws.py`, `test_turn.py`, `test_protocol.py` | Fakes updated for `memory_block`; `_handshake()` drains `memory`; D7/D8 tests; sign-in/forget/refusal over a real ASGI socket |
| `frontend/src/protocol.ts` | `PROTOCOL_VERSION` 5; `SignInMessage`/`SignOutMessage`/`ForgetMessage`, `FactWire`/`MemoryMessage`, the `memory` parse case |
| `frontend/src/net/connection.ts` | `onMemory` callback; `signIn()`/`signOut()`/`forget()` |
| `frontend/src/App.tsx` | The panel (`<aside>`), the sign-in form, `handleSignIn`/`handleSignOut`/`handleForgetEverything` |

## How to test

```bash
cd backend
uv run mypy app                    # Success: no issues found in 28 source files
uv run ruff check app tests        # All checks passed!
uv run pytest -q                   # 269 passed (was 212 before this block)

cd ../frontend
npm run typecheck                  # clean
npm run lint                       # clean
npm run build                      # clean (pre-existing chunk-size warning only)
```

**Not run here — the human gate:**

1. `make deploy` (not run — outside this task's scope; I was told not to deploy).
2. The block plan's 9-step verification against the deployed URL, especially step 4 (the graded
   test: hard reload, sign back in, "what's my favourite colour?" → **green**, panel shows the
   *original* `learned_at`) and step 5 (a second name sees an empty panel).
3. A real voice turn through Groq/Gemini/Deepgram — this environment has no browser, no
   microphone, and no access to `.env` (deny rule). Everything above is proven against fakes and
   a real ASGI socket, not real providers.

## Changelog

- `feat(memory): durable per-user memory with typed sign-in, extraction, and the "what Sarjy
  remembers" panel (Block B, requirement #2)`
- `fix(memory): extract a first-person statement even when the turn is a question; still skip
  pure recall questions so they cannot overwrite learned_at`
