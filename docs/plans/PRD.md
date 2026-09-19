# Sarjy — PRD

**Date:** 2026-09-18 · **Owner:** Omar · **Deadline:** 4 calendar days from Thu EOD (~Mon)

Technical design: `TDD.md`. Decisions and their reasoning: `../decisions/deep-dive-track.md` (gitignored).

## Summary

**Sarjy is a voice travel assistant that never states a travel fact it cannot source.**

Ask it "I'm going to Japan next month on a Saudi passport" and it tells you: eVisa, 90 days, passport valid on arrival, a customs declaration is required — each answer carrying the source it came from and the date that source was generated. When something falls outside what its sources cover, it says so and routes you to the embassy rather than guessing.

It also helps you plan: where to go, what to see, whether November is the right month — clearly marked as its judgement rather than as sourced fact.

## The problem

General assistants confidently invent visa requirements. The answer depends on a passport-and-destination pair that changes without notice, it is not the kind of fact a model can hold reliably, and people miss flights because of it.

So the interesting problem is not "can a voice assistant answer travel questions." It is **can it be trusted about facts it got from a tool.**

## The deep dive — guardrails and reliability

Sarjy answers from a live, dated, citable source; falls back to a vendored dataset when that source fails, saying which one answered and how fresh it is; and refuses with a route to the authority when neither covers the question.

The demo is not that it never errs. It is that **you can always see where an answer came from.**

**The bar is *grounded and still useful*.** An assistant that hedges everything has failed this deep dive, not passed it. A refusal is correct only when the sources genuinely do not cover the question — never as a way of avoiding risk.

### Two registers, never blurred

*"Never state a fact it cannot source"* does not mean *"never have an opinion."* It means the two are never mixed.

| Register | Covers | Rule |
|---|---|---|
| **Sourced** | Visa rules, entry requirements, passport validity, place descriptions | Cited, dated, traceable. Never invented. |
| **Judgement** | Where to go, what to see, when to travel, how to spend three days | Marked as Sarjy's own view. Never dressed as a looked-up fact. |

The user always knows which one they are hearing, in the voice line and in the UI. **A visible register switch is a better demo beat than a refusal** — it shows the discipline is real without the assistant being useless.

Getting this wrong in either direction is a failure: a sourced claim presented as opinion is evasive; an opinion presented as sourced is the exact harm this project exists to prevent.

## Requirements

| # | Requirement | Done means |
|---|---|---|
| 1 | Voice in, voice out | Reviewer speaks, Sarjy speaks back. Barge-in works. |
| 2 | Memory across sessions | **Two stores.** A typed travel profile (passport, home city, preferences, past destinations) that drives lookups, and an open key/value store for anything else the user says about themselves — because the brief's own example is *"what's my favorite color?"* and a reviewer will try that exact sentence. Per-person via an anonymous session id, not shared across visitors. Visible in a "what Sarjy remembers" panel. Survives a full reload. |
| 3 | External API | Live visa lookup, with citation and timestamp surfaced to the user. |
| 4 | Deployed URL | Opens cold in a fresh browser. No key, no login, no README. |
| 5 | Deep dive | Cite-or-refuse, visible fallback, injection resistance, vendor-failure degradation, an adversarial eval with numbers. |
| 6 | Presentation | Loom or PDF before the meeting; live demo; codebase walkthrough. |
| 7 | GitHub repo | Private, reviewer granted access before submission. |

## The external API, and why this one

**[Travel Buddy Visa Requirements](https://rapidapi.com/TravelBuddyAI/api/visa-requirement)** — 200 passports × 211 destinations, updated daily.

> Visa requirements are the highest-stakes factual question in travel: wrong information means being denied boarding. They're also exactly what general-purpose assistants hallucinate, because the answer depends on a passport/destination pair that changes without notice. This API returns a dated, per-nationality answer with an embassy link, which lets every claim Sarjy makes carry its own provenance instead of resting on model memory.

That is the requirement-#3 justification. It holds because the API was chosen *for* the deep dive rather than bolted on to satisfy a checkbox.

Supporting sources: the maintained passport-index fork (`visualpharm/visa-free-dataset`) as an offline fallback, and the **Wikipedia REST API** for place descriptions and photographs — each carrying its own revision date and page URL.

**Deliberately not used:** GOV.UK (it answers only British-passport questions, which is the wrong traveller) and Aladhan prayer times (out of scope for a thesis about grounded entry requirements). Travel suggestions need no source at all — they are `judgement`, and the register split is what makes saying so honest.

**Images arrive with attribution and a revision date.** That is the same provenance discipline applied to a different medium, not decoration bolted on.

## Priority ladder

Cut from the bottom. **P1 is cut in scope, never in kind** — it is the submission's identity.

1. **P0 — the deliverable floor.** Voice in/out, cross-session memory, live external API, deployed URL.
2. **P1 — guardrails and reliability.** The deep dive.
3. **P2 — Arabic.** At minimum Arabic input, honestly demoed. Code-switching if it holds up.
4. **P3 — presence.** Place imagery with attribution, a calm and attractive UI.

**Arabic sits above imagery, deliberately, and this was reversed once.** The first ordering reasoned that images improve every turn while Arabic only makes some turns possible — true in general, and wrong for this audience. Sarj is a ten-person Saudi company whose entire product is Arabic-dialect-native voice. One honest Arabic turn speaks to them more than every photograph combined. **And they have already been told in writing that this is "a bilingual English/Arabic voice assistant"** — shipping with none is a promise walked back.

**Demo it honestly, including the failure.** Our own research puts Gulf dialect word-error rate at ~68 on open models versus ~35 for Egyptian. Script the demo in Egyptian, then *say the Gulf number out loud* and explain that it is precisely why a company like Sarj trains its own models. Naming the cliff is worth more than pretending it isn't there — it is technical honesty aimed directly at their domain.

**Travel suggestions are not in this trade.** They come with the sourced/judgement register split, which is P1 — the deep dive itself. What P3 risks is the photographs and the polish, not the usefulness.

If Arabic still gets cut, say so in the writeup and describe the architecture that would have carried it. *"What I'd do with another week"* is explicitly invited by the brief.

## Explicitly not building

Flight search or fares · booking of any kind · user accounts or auth · hotel and restaurant reservations · itinerary generation beyond what the grounded sources support · any abstraction for a future this project does not have.

**Flights are excluded on principle, not by accident.** Every free flight API is decommissioned, sandboxed with fictional data, or stale. Showing invented fares in a project about not hallucinating would undermine the whole thesis. This is stated in the writeup, not hidden.

## Demo script

1. **It answers.** *"I'm going to Japan next month on a Saudi passport"* → eVisa, 90 days, passport validity, customs declaration — each sourced and dated.
2. **It remembers.** Reload the page. *"What about Thailand?"* → answered without re-asking the passport.
3. **It refuses well.** A pair outside coverage → names the gap, routes to the embassy, does not guess.
4. **It survives the vendor.** Kill the API mid-demo → the fallback answers, and says it is falling back and how old that data is.
5. **It resists attack.** A real in-the-wild injection payload → treated as data, flagged, not obeyed.
6. **It switches register.** *"Is November a good time?"* → a real recommendation, visibly marked as judgement rather than sourced fact, with a photo of the place and its source.

**Beat 4 is the one most submissions cannot show.**

Then a normal successful turn, so it doesn't only look like a machine that says no.

## Open — product

- **Sarjy's voice and persona.** Which prebuilt voice, and how it talks. Spoken answers are much shorter than written ones; a model's default paragraph is unlistenable. *"Is the voice experience delightful"* is a scored line.
- **What the reviewer sees in the first fifteen seconds.** The UI should feel calm and attractive rather than elaborate — a place photo, a clear transcript, visible state.
- Reviewer's GitHub username, and API keys from Sarj — both asked 2026-09-18.
