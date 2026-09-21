---
name: reference-voice-gate-verification
description: How to verify Sarjy's voice pipeline and grounding gate server-side without a browser or microphone — scripted WebSocket turn, Modal logs, and direct adversarial probing of gate()/run_turn()
metadata:
  type: reference
---

The server half of any voice-turn gate can be verified without a browser, and should be
before accepting an implementer's "verified end to end" claim:

- **Drive the real protocol against the deployment.** `scratch/spikes/block2/deployed_turn.py`
  (gitignored, written in Block 2) sends `hello → start → 32 KiB binary chunks of a recorded
  16 kHz WAV → end` over `wss://…/ws` and prints the wire sequence with per-stage millisecond
  offsets. `scratch/spikes/block2/test_utterance.wav` is the stock "What's the capital of
  Japan?" utterance. Run it with `backend/.venv/bin/python`.
- **Read the per-stage timings back from Modal.** `modal app logs sarjy` carries
  `stt_ms`, `llm_first_text_delta_ms`, `tts_ttfb_ms`. macOS has no `timeout`, and the command
  streams forever — wrap it: `perl -e 'alarm 25; exec @ARGV' <python> -m modal app logs sarjy`.
- **Drive multi-turn/session behaviour locally** with `fastapi.testclient.TestClient` against
  `app.main.app`, monkeypatching `app.providers.factory`'s `get_stt/get_llm/get_tts`. Two turns
  on one connection is what proves in-session history, and it needs no network.

## Probing the grounding gate adversarially (Block A onward)

Unit tests only cover the rules someone thought to write. To find the rules that are *missing*,
drive the real functions directly — no network, no model, no quota:

- **Gate-only probe.** `app.tools.fake.result_from_live_body(json.load(open(
  "data/reference/visa_reqs_SA_JP.json")), retrieved=...)` gives a real `ToolResult`; feed
  hand-built `gate.Segment`s into `gate([seg], {"tb_1": res})` and `gate.spoken_text(...)`.
  `copy.deepcopy` the body and inject `data.visa_rules.exception_rule.full_text` to exercise the
  `quoted` register and the injection screen.
- **Whole-turn probe.** `pipeline.turn.run_turn()` takes `get_stt/get_llm/get_tts/get_tool`
  callables, so ~40 lines of fakes (an LLM whose `segments()` yields canned NDJSON strings) runs
  every failure branch. `FakeVisaTool(force_reason=...)` walks every `ToolReason` in one loop —
  that is how you check all four Invariant-6 branches rather than just the one with a test.
- **Prompt-injection surface.** Print `prompts.build_user_block(...)` with hostile vendor text to
  see whether the `<tool_result>` delimiter can be closed from inside; `json.dumps` escapes quotes
  and newlines but not `<`/`>`.
- **The bypasses worth trying every time:** polarity inversion in `sourced` prose, a country name
  that isn't this turn's pair, quantity words outside the cardinal list ("a fortnight", "a dozen"),
  non-Nd Unicode digits, nested `{{…}}`, and marker evasion by zero-width space, punctuation or
  Cyrillic homoglyph.

**Read-only Modal checks that cost nothing:** `modal dict list` shows whether a `modal.Dict`-backed
counter has ever actually been created in a deployed run — an empty list means that code path is
unexercised, whatever the docstring claims.

What this cannot prove, ever: VAD, capture, playback, endpointing, echo cancellation, and the
microphone permission states. Those need a human at a browser — do not accept them as verified.
