---
name: measure
description: Instrument, run, or interpret a latency measurement for Sarjy's voice pipeline. Use whenever the voice path changes, whenever a latency claim is about to be made, or when asked where the time goes. Required even when latency is not the chosen deep dive.
argument-hint: [what changed, or what to compare]
---

# Measure

`AGENTS.md` §Invariant 2: **latency is a measured number, not an adjective.** The brief asks "where does the time go" under the Latency track, but the question gets asked regardless — a voice app that can't account for its own delay is a voice app nobody instrumented.

## Instrument before you optimize

Retrofitted timing tells you nothing about what you already built. Every turn emits per-stage timings, stored, not just logged:

| Stage | Measured from → to |
|---|---|
| Endpointing | user stops speaking → VAD declares end of turn |
| STT | audio sent → final transcript available |
| LLM call 1 TTFT | prompt sent → first **text** delta |
| Opener ready | prompt sent → `update()` arguments parsed |
| TTS #1 TTFB | opener text sent → first audio byte |
| **→ first audio out** | user stops speaking → **first audible sound** |
| *— everything below runs underneath that audio —* | |
| Tool round trip | lookup fired → result in hand |
| LLM call 2 | prompt sent → last NDJSON line |
| Gate | segments in → rendered segments out |
| TTS #2 TTFB | answer text sent → first audio byte |
| **Answer gap** | opener audio ends → answer audio starts |

**First audio out is the headline number** — it is what the user experiences. The stage breakdown answers "where does the time go."

**The answer gap is the number that validates the architecture.** It says whether the opener actually covered the work hidden under it. A gap near zero means the design works; a large one means the opener is too short or the hidden work is too slow, and that is a finding, not a failure.

⚠️ **Measure LLM TTFT to the first `delta.type == "text"`, not the first SSE event.** A `thought` step is always emitted, even at `thinking_level: "minimal"`. Timing to the first event records a fiction — a number that looks excellent and describes nothing the user experienced.

Record alongside every run: the provider and **model id** for each stage, `thinking_level`, network conditions, cold vs. warm, and whether it ran locally or against the deployment. A latency figure without its configuration is not a measurement.

## Rules

- **Never report a single run.** Report a distribution — at minimum median and p95 over a real number of turns. One fast run is an anecdote, and a reviewer who tries it once and gets the p95 will not believe the median you quoted.
- **Measure the deployment, not just localhost.** The reviewer uses the deployed URL. Local numbers are a different product. Note the region/geography — it's often the largest single term and it's easy to forget.
- **Change one thing at a time.** A/B across the provider interface, which exists partly so this is possible (`AGENTS.md` §Invariant 3).
- **Record what didn't work.** The brief asks for it by name: *what you tried, what worked, what didn't*. A rejected approach with a number attached is stronger evidence of rigor than another win. Keep the failures in the log.
- **Perceived latency counts too, and is scored separately.** Filler audio, an instant visual state change, streaming the first clause before the sentence completes — these change the experience without changing the stopwatch. Report both; never let one stand in for the other.

## Steps

1. Confirm the harness exists and covers all stages. If a stage isn't instrumented, that's the first task.
2. Run against the deployment, enough turns for a distribution, with a fixed script of utterances so runs are comparable.
3. Write results to `docs/measurements/{date}-{what-changed}.md`: configuration, stage table (median/p95), headline voice-to-voice, and what changed versus the previous run.
4. Interpret: name the largest term and say what you'd do about it. If the largest term is inside a provider you don't control, say that plainly — it's a real finding and a legitimate answer.
5. If this measurement backs a claim going into the presentation, keep the raw data. "We will ask you about it" means the number needs to survive follow-up questions.

## Anti-patterns

- Adjectives instead of numbers ("snappy", "near-instant")
- Best-of-N reported as typical
- Localhost numbers presented as the deployed experience
- No model ids recorded, so the run can't be reproduced or explained
- A stage table that doesn't sum to the headline figure — the gap *is* a finding, chase it
- Discarding the experiments that failed
- Timing TTFT to the first SSE event, which is a `thought` step
- Reporting perceived latency as though it were measured
