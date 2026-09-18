---
description: "Browser audio — capture, resampling, playback scheduling, permissions"
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/audio/**"
  - "**/hooks/**"
  - "frontend/**"
  - "client/**"
  - "web/**"
---

# Browser audio

The fiddliest part of this project and the place voice demos usually break. It is pure engineering — no model involved — which means every bug here is fixable and none of them are mysterious.

## Capture

- **`AudioWorklet`, not `ScriptProcessor`.** The latter is deprecated and janky under load, and it runs on the main thread.
- `getUserMedia` delivers **48 kHz float**; STT wants **16 kHz PCM16**. Resample explicitly and deliberately — do not assume the browser or the provider will do it.
- **Enable echo cancellation, noise suppression and auto gain in the constraints.** Without echo cancellation the assistant hears its own output and interrupts itself. This is a one-line fix for a bug that looks like a deep architectural problem.
- Frame size is a latency/overhead trade. Pick one, write down why.

## Playback

- Schedule chunks into an `AudioContext` with explicit timing. **Never point an `<audio>` element at a stream** — you get neither low latency nor clean interruption.
- Barge-in must stop audio *now*: kill scheduled buffers, don't wait for the current chunk to drain.
- An `AudioContext` starts suspended until a user gesture. Resume it on the first interaction, and make sure the first thing the user does provides one.

## Permissions

- Ask for the microphone **at a sensible moment, with context for why** — not on page load with no explanation.
- Denied, and revoked mid-session, are different states. Both need a clear, recoverable message. Neither is a dead end.
- Test in **Safari as well as Chrome.** Safari's autoplay and microphone behaviour differ, and it breaks voice apps specifically.

## VAD

Runs client-side (`@ricky0123/vad-web`) — it saves a network round trip on every single turn.

The silence threshold is a product decision (see `pipeline.md`). Expose it while developing so it can be tuned by feel, then fix a value and record the reason.

Backchannels — "mhm", "yeah" — must not end a turn.

## State must be visible and instant

Idle, listening, thinking, speaking. The user should never wonder which one is true. **State changes are immediate even when the response is not** — this is the cheapest perceived-latency win in the project, and it costs nothing.

No spinner may outlive its operation. Silence with no visual state is the worst thing this UI can do.

## Images

Place photos come from Wikipedia with attribution and a revision date (`../tools/vendor-client.md`).

- Reserve layout space before the image loads — no shifting text.
- A failed image must not produce a broken-image icon or a collapsed card.
- **Never substitute a different place's photo.** An image is a claim like any other; a wrong one is a wrong claim.

## Anti-patterns

- `ScriptProcessor`
- Assuming the sample rate
- Missing echo cancellation, then debugging "the assistant interrupts itself"
- `<audio src=…>` for streamed output
- A mic prompt on page load with no explanation
- Testing only in Chrome
- Layout that shifts when an image arrives
