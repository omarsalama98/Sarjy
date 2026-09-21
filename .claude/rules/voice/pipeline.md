---
description: "Voice pipeline — stage contract, instrumentation, barge-in, provider boundary"
paths:
  - "**/pipeline/**"
  - "**/voice/**"
  - "**/stt/**"
  - "**/tts/**"
  - "**/ws/**"
  - "**/websocket*"
  - "backend/**"
  - "src/**"
---

# The voice pipeline

```
mic → user endpoint → STT → [TEXT CHECKPOINT] → LLM + tools → [GROUNDING GATE] → TTS → speaker
```

**Cascaded by design, not by convenience.** The two bracketed checkpoints are why. An end-to-end speech-to-speech model gives neither — you cannot validate a citation that never exists as text. If a change would erase a checkpoint, it is changing the deep dive, not the plumbing.

## The turn speaks before the lookup returns

```
LLM call 1 ── update("Let me check that") → TTS #1 → speaking
            └─ get_visa_requirements(...)  → lookup ─┐  (hidden under the audio)
LLM call 2 ── NDJSON segments → gate → TTS #2 ──────┘→ speaking
```

`step.start` delivers a function call's **name and id before its arguments generate**, so the HTTP lookup fires mid-stream. The vendor round trip and the whole of call 2 run underneath audio already playing.

**Two TTS requests per turn — one opener, one whole answer. Never one per segment.** Gemini TTS has no continuity primitive (no session, no acoustic context, no working seed) and the docs warn that output *"may not always strictly match the selected speaker."* Across five clips that becomes an audible seam mid-sentence. The opener/answer boundary is a natural prosodic pause, where a seam is inaudible.

**Keep per-segment gating; drop per-segment synthesis.** Validate incrementally, speak once.

## Instrument every stage, from the first working turn

Retrofitted timing tells you nothing about what you already built. Every turn emits:

`endpointing → STT → LLM TTFT → tool call → TTS TTFB → first audio out`

Voice-to-voice is the headline; the breakdown is the answer to "where does the time go," which gets asked regardless of deep-dive track. Record the model id and conditions with every run — a latency figure without its configuration is not a measurement.

⚠️ **Measure TTFT to the first `delta.type == "text"`, not the first SSE event.** A `thought` step is always emitted, even at `thinking_level: "minimal"`. Timing to the first event records a fiction — a number that looks excellent and describes nothing the user experienced.

**Report median and p95, against the deployment.** A single local run is an anecdote, and the reviewer gets one try.

Target ≤ 1.8 s to **first audio out** — which is the opener, not the answer. Adding a stage, a round trip, or a blocking await to this path without instrumenting it is a blocking review issue.

## Endpointing is user-controlled

It runs **client-side** as tap/hold-to-talk, not as a silence threshold.
A pause mid-sentence no longer ends the turn. Interrupting Sarjy is the
same tap, not an acoustic guess.

STT here is **batch** (Groq Whisper, 30-second windows), so the user's
release still gates the whole turn. That is a known constraint.

## Barge-in is not optional

A user interrupting is the most common real interaction in voice.

- Audio stops **immediately** — not at the end of the current chunk.
- In-flight generation is cancelled, not left running to completion.
- The interrupted turn is recorded honestly in conversation state; never pretend it completed.
- Echo cancellation comes from `getUserMedia` constraints. Without it the assistant hears itself and interrupts itself.

## Every provider sits behind our own interface

STT, LLM, TTS, and each data source. Provider choice is **configuration, not code**.

Free tiers rate-limit and models get deprecated mid-build — `playai-tts` was deprecated during this project's own research week. The interface is what makes a provider swap a config change, and what makes A/B latency comparison possible.

A provider SDK, model id, or provider-shaped payload outside its adapter is a blocking issue.

## No provider key reaches the browser

The client talks only to our backend. A key in client JS is a key published to the world, and the deployment URL goes to a stranger. Only short-lived server-minted session tokens may cross, and only if a transport demands it.

## Silence is the worst failure mode

At every moment the user must know which state they are in: idle, listening, thinking, speaking. State changes are **instant** even when the response is not — that is the cheapest latency win available.

A tool call sits on the latency path here. Speak an acknowledgement before the lookup returns rather than leaving dead air. Report perceived latency separately from the measured number — never as a substitute for it.

## Anti-patterns

- A stage on the latency path with no instrumentation
- Barge-in that finishes the current audio chunk first
- A silence threshold chosen by default rather than decided
- A provider SDK imported outside its adapter
- A spinner that can outlive its operation
- Claiming a latency number from a single local run
