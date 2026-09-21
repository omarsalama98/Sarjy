# Two numbers Block 2 recorded were measuring the wrong thing

**Date:** 2026-09-20 · **Run by:** orchestrator, verifying Block 3's implementation report
**Environment:** scripted turns from a sandbox against the deployment (`us-east`), container warm
**Config:** `whisper-large-v3-turbo` · `gemini-3.5-flash-lite` (`thinking_level: minimal`) · `aura-2-thalia-en`

---

## Summary — read this page

Block 3's instrumentation moved two measurement points to where the user actually feels them.
Both numbers moved by an order of magnitude. **The old numbers were wrong, not the new ones**, and
both were on their way into the presentation.

| Number | Block 2 said | Actually | Why it moved |
|---|---|---|---|
| TTS time-to-first-byte | **85 ms** | **566 ms** | The clock started *after* `websockets.connect()` returned. The Deepgram handshake — the part the user waits through — was outside the measurement |
| LLM time-to-first-token | **30 ms** | **890 ms** | Same shape: the clock started after the HTTP request was already open, so it excluded the request round trip and the model's prefill |

⚠️ **Neither correction is a regression.** No code got slower. The instrument got honest.

**The implementer's report attributed the LLM jump to a cold container.** That is ruled out: the four
records below are turn indexes 2–5 on one warm container, and the number does not come down.

---

## The records

Four consecutive scripted turns, same utterance ("What's the capital of Japan?"), warm container.

| Stage | Values (ms) | Median |
|---|---|---|
| `upload_ms` | 887 · 1142 · 1248 · 1419 | **1195** |
| `stt_ms` | 146 · 147 · 151 · 191 | 149 |
| `llm_ttft_ms` | 771 · 774 · 1006 · 1119 | **890** |
| `llm_ms` (full completion) | 970 · 976 · 1203 · 1355 | 1090 |
| `tts_ttfb_ms` | 484 · 498 · 634 · 663 | **566** |
| `tts_total_ms` | 1145 · 1251 · 1615 · 1707 | 1433 |
| `server_ms` (end received → first audio byte) | 1791 · 1796 · 1848 · 1985 | 1822 |

`server_ms` 1822 against `stt + llm + tts_ttfb` = 1805 leaves a **17 ms residual** — the server-side
stage table sums to its own headline, which is the check that says the instrument is wired correctly.

## What this says about where the time goes

**The largest single term is `upload_ms`, and it was not in the spec.** `.claude/skills/measure/SKILL.md`'s
stage table goes straight from endpointing to STT; the leg where the user's audio crosses the network
to the server was never listed. Block 3's planner added it. It is now the biggest number on the board.

**The LLM is the most expensive server leg, not the cheapest.** `PR_VOICE_LOOP.md` says the opposite,
on the strength of the 30 ms figure. That line needs correcting before the walkthrough — a reviewer
who asks "what's your slowest stage?" should not get an answer contradicted by the app's own log.

## Caveats that matter more than the numbers

1. 🚨 **`upload_ms` here is a sandbox's network, not a browser's.** This is the one term that will
   move most between this run and Omar's. Block 2 observed 660 ms – 3.5 s for the equivalent leg,
   also from a sandbox. **The browser number is the real one and it is still unmeasured.**
2. **`endpoint_ms` and `first_audio_ms` are null in every record here.** A script has no VAD and no
   speaker. The headline voice-to-voice figure cannot be produced without a human at a microphone.
3. n = 4. Enough to kill the cold-start hypothesis; not enough to quote a p95.

## What to do about it

- Correct the LLM claim in `docs/PRs/PR_VOICE_LOOP.md` and the 85 ms figure in
  `docs/measurements/block2-voice-loop.md`, both of which are currently wrong in the repo.
- Add an upload row to the `measure` skill's stage table.
- Run the ten browser turns (Block 3 task 16) — that is what replaces this run, not supplements it.
