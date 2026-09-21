# Block 2 — voice loop measurements

**Date:** 2026-09-20 · **Deployment:** `https://vitas7777v--sarjy-fastapi-app.us-east.modal.run` · **Region:** `us-east`

Two things measured here, per the block plan: Deepgram's TTFB claim (task 15) and the
endpointing sweep (task 14). **The endpointing sweep is not done** — it requires a human
speaking into a real microphone, which this agent cannot do. See "Open" below for exactly
what to run.

## Deepgram TTS — time to first byte

**Claim being checked:** Deepgram's published TTFB for Aura-2 is `<200 ms`. Not independently
verified anywhere before this — TDD.md flags it as a vendor claim.

**Method:** `scratch/spikes/block2/deployed_turn.py` drives a real turn against the deployed
WebSocket — `hello → start → binary chunks of a pre-recorded 16 kHz utterance → end` — exactly
the client protocol, with a recording standing in for a live microphone. `tts_ttfb_ms` is
logged server-side in `backend/app/providers/deepgram_tts.py`, timed from `Flush` sent to the
first binary frame received, and read back from `modal app logs sarjy`. n=5, one utterance
("What's the capital of Japan?"), same deployed container throughout (`min/max_containers=1`
means no cross-container variance to worry about).

| Run | `stt_ms` | `llm_first_text_delta_ms` | `tts_ttfb_ms` |
|---|---|---|---|
| 1 | 471 | 30 | 104 |
| 2 | 289 | 30 | 81 |
| 3 | 309 | 29 | 82 |
| 4 | 296 | 30 | 103 |
| 5 | 264 | 30 | 85 |
| **median** | **296** | **30** | **85** |

**Verdict: PASS, comfortably.** Median 85 ms clears the <200 ms claim by a wide margin, and the
spread (81–104 ms) is tight — no outliers, unlike the Gemini TTS spike's quota-driven tail
(`day1-spikes.md` S3). `llm_first_text_delta_ms` is startlingly fast and consistent (29–30 ms);
worth naming in the walkthrough since a reviewer will not expect the LLM leg to be the cheapest
one in the chain.

**Caveat, stated plainly:** this is a scripted turn from this environment, not a browser. It
proves the STT→LLM→TTS pipeline and the WebSocket protocol work end to end against the real
deployment and gives real provider timings — it does **not** exercise VAD, capture, playback, or
endpointing, and it says nothing about what a reviewer's own network conditions would look like.
`t_thinking_ms` (start sent → `state:thinking` received, i.e. the audio upload leg) ranged
660 ms–3.5 s across the 6 runs collected — noisier than the plan's ~130 ms estimate for a 5 s
utterance, most plausibly this sandbox's own network path to `us-east`, not the app. Re-check
this figure from a normal connection before treating it as representative.

## Endpointing sweep — NOT DONE, needs a human

**What's built:** the instrument itself (`frontend/src/audio/turn.ts`) — `onFrameProcessed`
records the last frame classified as speech; `onSpeechEnd` logs
`endpoint delay ${ms}ms (redemptionMs=${value})` to the console. `redemptionMs` reads from
`?redemptionMs=` in the URL (falls back to `DEFAULT_REDEMPTION_MS = 600`), specifically so the
sweep below can be run by ear, live, with no rebuild between trials.

**What's not done, and can't be from here:** this requires a person speaking into a real
microphone, five times per value, and judging by ear whether a natural pause got cut off. That
judgment call — "did it feel like it cut me off" — is the entire point of the exercise
(`.claude/rules/voice/browser-audio.md`: *"the silence threshold is a product decision, not a
constant"*) and has no scripted substitute.

**Omar, run this:**

1. Open the deployed URL (or `npm run dev` locally), append `?redemptionMs=400`, click Start,
   say the same sentence 5 times, letting it fully endpoint each time.
2. Open the browser console — each utterance logs
   `sarjy: endpoint delay {N}ms (redemptionMs=400, segment={M}ms)`. Note the 5 delay values and
   whether any felt like it cut you off mid-sentence (a false cut).
3. Repeat for `?redemptionMs=600` and `?redemptionMs=800`.
4. Say "mhm" five times at whichever value you pick — the console should show
   `VAD: onVADMisfire`-equivalent (no utterance sent, no turn opened) every time, never a turn.
5. Fill in the table below, pick a value, and write down *why* — the trade-off is always
   "cutting the user off" vs. "making them wait," and it is the single largest term in the whole
   latency budget (larger than any provider call above).

| `redemptionMs` | delay₁ | delay₂ | delay₃ | delay₄ | delay₅ | median | false cuts |
|---|---|---|---|---|---|---|---|
| 400 | | | | | | | |
| 600 | | | | | | | |
| 800 | | | | | | | |

**Chosen value:** _pending_ · **Reason:** _pending_

Once chosen, update `DEFAULT_REDEMPTION_MS` in `frontend/src/audio/turn.ts` and `TDD.md`'s
latency budget's endpointing row (currently "~600 ms, still an estimate") with the measured
value and `n`.

## Voice choice — NOT DONE, needs a human (P2.3)

Shipped default: `aura-2-thalia-en` (a placeholder per `TDD.md` §Provider traps, config in
`backend/.env`'s `DEEPGRAM_TTS_MODEL`). Listening to 3 Deepgram Aura-2 English voices and
picking one is a ten-minute task and a real "creative and personal to you" rubric line — an
agent picking a voice by reading its name would be exactly the kind of decision this shouldn't
make. Omar: listen at Deepgram's voice gallery, update `DEEPGRAM_TTS_MODEL` in `backend/.env`
(and the Modal secret), record the choice and the reason here.

## What still needs a human, in one place

Everything below needs a person at a browser with a working microphone and speakers — nothing
here was faked or skipped silently; each is unchecked because there is no scripted way to check it:

- **Task 10** — speak → `listening` fires; go quiet → `end` sent; say "mhm" → misfire, no turn.
- **Task 13** — a full local turn, on speakers, confirming echo cancellation holds (Sarjy must
  not interrupt itself) — Block 0 never tested this; `BARGE_IN_ENABLED` exists specifically in
  case it doesn't.
- **Task 14** — the endpointing sweep above.
- **Task 15's browser half** — the gate's 9 steps against the deployed URL (denial flow, barge
  mid-answer on real speech, a 3-minute idle reconnect, a wifi drop), and the Safari check
  (untested either way until someone runs it).

The backend half of task 15 (deploy succeeded, VAD assets serve correctly from the deployment,
a full turn runs end to end, TTFB measured n=5) is done and is above.
