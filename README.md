# Sarjy

**A voice travel assistant that never states a travel fact it cannot source.**

Ask it about travelling somewhere and it tells you what you need — visa type, how long you can stay, whether your passport has to be valid on arrival, what else you have to file on entry. Every answer carries the source it came from and the date that source was generated. When a question falls outside what its sources actually cover, it says so and points you at the embassy rather than guessing.

🔗 **Live:** _TBD_

---

## Why this

General assistants confidently invent visa requirements. The answer depends on a passport-and-destination pair that changes without notice, it is not the kind of thing a model can hold reliably, and people miss flights because of it.

So the interesting problem here isn't "can a voice assistant answer travel questions" — it's **can it be trusted about facts it got from a tool.** That's the deep dive.

The bar is *grounded **and still useful***. An assistant that hedges everything has failed this, not passed it.

## What it does

- **Answers from a dated, citable source.** Every factual claim maps to a tool result held in that turn. Claims that don't map don't get spoken.
- **Falls back visibly.** When the live source is unavailable, it answers from a vendored dataset and says which source answered and how old it is.
- **Refuses with a route.** Outside coverage, it names the gap and gives you the embassy link rather than improvising.
- **Remembers you across sessions.** Your passport, home city, where you've asked about before — so "do I need a visa for Thailand?" doesn't start with "which passport?"
- **Speaks English and Arabic**, including the code-switching real Gulf travellers use. _(Planned — see Status.)_

## The external API, and why this one

**[Travel Buddy Visa Requirements](https://rapidapi.com/TravelBuddyAI/api/visa-requirement)** — 200 passports × 211 destinations, updated daily.

> Visa requirements are the highest-stakes factual question in travel: wrong information means being denied boarding. They're also exactly what general-purpose assistants hallucinate, because the answer depends on a passport/destination pair that changes without notice. This API returns a dated, per-nationality answer with an embassy link, which lets every claim Sarjy makes carry its own provenance instead of resting on model memory.

Supporting sources: [passport-index](https://github.com/ilyankou/passport-index-dataset) (MIT) as an offline fallback · [GOV.UK Content API](https://www.gov.uk/api/content) for destination safety and local-law guidance · [Aladhan](https://aladhan.com/prayer-times-api) for prayer times at destination.

**Deliberately excluded: flights.** Every free flight API is decommissioned, sandboxed with fictional data, or stale. Showing invented fares in a project about not hallucinating would undermine the whole thing.

## How it works

```
mic → VAD/endpoint → STT → [text checkpoint] → LLM + tools → [grounding gate] → TTS → speaker
```

**Cascaded, not speech-to-speech — and that follows from the deep dive rather than from convenience.** A cascaded pipeline gives two points where text can be inspected and gated mid-turn. An end-to-end speech-to-speech model gives neither: you cannot validate a citation that never exists as text.

**The grounding gate** is the core. Every factual claim in a response must map to a tool result from that turn. The model proposes; deterministic code disposes.

**Quota-aware vendor client.** The upstream free tier is 120 requests *total*, so resolution runs cached map → warm cache → vendored dataset → live call, and only spends a live request on a miss with budget remaining. Remaining quota is visible in the UI.

## Stack

| | |
|---|---|
| Backend | Python · FastAPI · WebSocket |
| Frontend | TypeScript · React |
| STT | Groq `whisper-large-v3-turbo` |
| LLM | Gemini `gemini-3.5-flash-lite` |
| TTS | Gemini `gemini-3.1-flash-tts-preview` |
| VAD | `@ricky0123/vad-web`, in-browser |
| Deploy | Modal |

Every provider sits behind an interface we own — provider choice is configuration, not code.

## Running locally

```bash
cp .env.example .env              # fill in your keys

cd backend && make install && make dev     # FastAPI on :8000
cd frontend && npm install && npm run dev  # Vite on :5173, proxies /ws to the backend
```

Checks: `make typecheck && make lint && make test` in `backend`, `npm run typecheck` in `frontend`.

No provider key ever reaches the browser. The client talks only to this backend.

## Status

- [ ] Voice in / voice out
- [ ] Cross-session memory
- [ ] Grounded visa lookup with citation
- [ ] Fallback + refusal behaviour
- [ ] Adversarial eval
- [ ] Deployed
- [ ] Arabic

## Docs

`docs/plans/PRD.md` — what and why · `docs/plans/TDD.md` — how · `docs/research_docs/` — the research behind the stack choices, including what could not be verified.

---

Built for the Sarj take-home, September 2026.
