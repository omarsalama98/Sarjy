---
name: plan-deep-dive
description: Choose Sarjy's deep-dive track and the stack that follows from it. Use at the start of the project, or whenever the choice is being revisited — this is the gating decision that unblocks everything else in AGENTS.md §Open decisions.
argument-hint: [candidate track, if Omar already has one in mind]
---

# Choose the deep dive

The brief offers six tracks: **Latency**, **UI/UX & Multimodal**, **Guardrails and Reliability**, **Multistep workflows**, **Multiplayer**, **Something Else**. It also says, in its own words: *one done well is better than three done shallowly.*

This decision determines the architecture, the stack, what "done" means, and the entire demo narrative. It is Omar's to make. Your job is to make it a well-informed decision quickly, not to make it for him.

## Do not

- Pick a track yourself and start building.
- Default to Latency because it's the most measurable. It's also the most crowded — the brief's own list puts it first, which means the reviewer has seen it many times.
- Treat "Something Else" as the weird option. The brief actively invites it and says to pursue whatever is most interesting. Personal and creative are **on the rubric**.

## Steps

1. **Re-read the brief.** `Building Sarjy.md`, specifically §The Deep Dive and §Standing Out. Quote the track descriptions back accurately — don't paraphrase from memory.

2. **Research the landscape, don't recall it.** `voice-stack-research.md` is the current survey (Sept 2026) — start there rather than re-running it. Model ids, pricing, and free-tier limits move faster than any knowledge cutoff, so re-verify anything a decision will rest on, and dispatch subagents for whatever the survey doesn't cover. Every latency or pricing claim in the decision sheet needs a source and a date.

   Three constraints from that survey shape the option space before you start scoring:
   - **Endpointing, not inference, tends to dominate the latency budget.** A default VAD silence threshold can exceed the entire STT+LLM+TTS budget on a fast stack.
   - **Serverless function hosts can't hold a call.** A platform that caps function duration will drop the socket mid-conversation regardless of how good the rest of the stack is. Deployment is a hard filter on architecture, not a last step.
   - **Free tiers have quota traps that only surface during a demo** — per-minute token caps and low daily request limits on exactly the TTS and LLM endpoints a voice loop hammers.

3. **Score each candidate track against four axes**, honestly:
   - **Differentiation** — how far is a good version of this from what a one-shot produces? The rubric asks this by name.
   - **Feasibility in 3 part-time days** — including deployment, which is easy to under-budget.
   - **Demo legibility** — can the reviewer *feel* it in 90 seconds of live use? A deep dive that only shows up in a README is a weak deep dive.
   - **Explainability** — can Omar defend the hard parts live? A track built mostly on a framework's magic scores badly here.

4. **Look for the personal angle.** The brief says *creative and personal to you* twice, in different words. What does Omar actually find interesting, and what does he have unusual context on? Bilingual/Arabic support, a domain he knows, a use case from his own life — these convert a median submission into a memorable one. Ask; don't assume.

5. **Name what the track forces.** Each track implies architecture. Latency pushes toward a tight cascaded pipeline with instrumentation at every hop (or a realtime speech-to-speech API, which caps how much of the latency story is *yours*). Multiplayer forces shared state and a transport that supports it. Guardrails needs an adversarial eval set to prove anything. Say the implication out loud so the cost is visible before the choice.

6. **Write the decision sheet.** `docs/decisions/deep-dive-track.md` — options, trade-offs on the four axes, what each forces, the recommendation and why, and the open questions that remain either way. Omar ticks and annotates; his notes beat the checkboxes. Render it with `~/Projects/decision-sheet-html.mjs` and publish it.

7. **Once it's chosen, cascade.** Close the dependent rows in `AGENTS.md` §Open decisions, write `.claude/rules/voice/` to match the real architecture, and add the stack-specific skills `CLAUDE.md` §Still to be written is holding a slot for.

## Output

A decision sheet, not a recommendation buried in chat. One page. Recommendation at the top.

## Anti-patterns

- A recommendation with no sourced numbers behind it
- Scoring feasibility without counting deployment and the presentation
- Choosing a track that only shows up in the writeup, never in the live demo
- Leaving `AGENTS.md` §Open decisions stale after the call is made
