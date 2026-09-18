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
mic → VAD/endpoint → STT → [TEXT CHECKPOINT] → LLM + tools → [GROUNDING GATE] → TTS → speaker
```

**Cascaded by design, not by convenience.** The two bracketed checkpoints are why. An end-to-end speech-to-speech model gives neither — you cannot validate a citation that never exists as text. If a change would erase a checkpoint, it is changing the deep dive, not the plumbing.

## Instrument every stage, from the first working turn

Retrofitted timing tells you nothing about what you already built. Every turn emits:

`endpointing → STT → LLM TTFT → tool call → TTS TTFB → first audio out`

Voice-to-voice is the headline; the breakdown is the answer to "where does the time go," which gets asked regardless of deep-dive track. Record the model id and conditions with every run — a latency figure without its configuration is not a measurement.

**Report median and p95, against the deployment.** A single local run is an anecdote, and the reviewer gets one try.

Target ≤ 1.5 s p50. Adding a stage, a round trip, or a blocking await to this path without instrumenting it is a blocking review issue.

## Endpointing is the largest controllable term

It runs **client-side** — it saves a network round trip on every turn.

The silence threshold is a **product decision, not a constant**: it trades cutting the user off against making them wait. Whatever value is chosen, the reason is written down. A default threshold can exceed the entire STT+LLM+TTS budget on this stack.

STT here is **batch** (Groq Whisper, 30-second windows), so endpointing gates the whole turn. That is a known constraint, measured at +200–450 ms versus streaming — state it, don't hide it.

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
