---
name: prd
description: Write or update the PRD/TDD for Sarjy before implementation. Use once the deep-dive track is chosen and before any substantial code — the brief explicitly recommends a short PRD/TDD and grades how the work was planned.
argument-hint: [scope, if narrower than the whole project]
---

# PRD / TDD

The brief, under §Communication in the rubric: *"How did you plan out your work? We recommend first writing up a short PRD / TDD that plans your work before you get into it."*

This is graded. It is also the cheapest way to make the build coherent. **Short** is doing real work in that sentence — this is a three-day project, not a quarter.

## Prerequisite

The deep-dive track must be chosen (`/plan-deep-dive`). A PRD written before that is a guess.

## Structure

Write `docs/plans/PRD.md`. Target two pages. Lead with the summary — Omar doesn't read long documents end to end, and neither will the reviewer.

1. **What Sarjy is** — one paragraph. The product, not the tech. Include the personal/creative angle if there is one.
2. **The deep dive** — which track, why this one, in three sentences. This is the spine of the submission; make it the spine of the document.
3. **Requirements** — the seven from `AGENTS.md` §The deliverable contract, each with a concrete "done means" for *this* build. Vague acceptance criteria here become vague features later.
4. **The external API** — which one, and the 2–3 sentence justification the brief asks for: *why this API, why this use case*. Draft it now, while the reasoning is fresh; it goes in the final writeup nearly verbatim. A weak justification is a visible tell that the API was chosen to tick a box.
5. **Memory model** — what Sarjy remembers, when it decides to remember, where it's stored, how it's retrieved, and how you'd show a reviewer the stored record. "What's my favorite color?" is the acceptance test.
6. **Architecture** — one diagram's worth of prose: client, backend, the voice path, the provider boundary. Name every provider and where its key lives. Every provider key is server-side (`AGENTS.md` §Invariant 1); say so explicitly.
7. **Latency budget** — the target end-to-end figure and the per-stage allocation, *even if latency isn't the track*. You will be asked where the time goes.
8. **Failure modes** — mic denied, network drop, provider 429 or outage, empty transcription, barge-in mid-response, external API down. Defined, visible behavior for each. This table is what separates a demo that survives a reviewer from one that doesn't.
9. **Plan of record** — day-by-day against three part-time days, with deployment on day one. Mark what gets cut first if time runs short. Decide the cut list now, calmly, rather than at 2am on day three.
10. **Explicitly not building** — the scope guard, written down so it can be pointed at later.
11. **Open questions for Sarj** — API keys needed, reviewer's GitHub handle, anything worth brainstorming. The brief invites these; asking is a rubric line, not an imposition.

## Steps

1. Confirm the track and re-read `AGENTS.md` §The deliverable contract and §Invariants.
2. Draft the document. Summary first.
3. Render: `node ~/Projects/spec-html.mjs docs/plans/PRD.md`, then publish the HTML and give Omar the link.
4. Get sign-off before implementation starts.
5. Keep it current. When a decision changes, update the PRD **and** the affected `.claude/rules/` file in the same pass — a stale PRD is worse than none, and this one may be shared with Sarj.

## Anti-patterns

- Writing it after the code, to look planned
- A requirements section that restates the brief without deciding anything
- Skipping the failure-mode table because the happy path works
- No cut list, so scope gets cut in a panic on the last day
- Letting it drift out of date once building starts
