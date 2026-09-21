# Demo script

The reviewer opens https://vitas7777v--sarjy-fastapi-app.us-east.modal.run in a fresh profile. No README required. Frame: **1280×800**.

If a row breaks live, say the sentence in the last column and keep going. A recovered failure is better evidence than a restart.

| # | Say / do | Should happen | Proves | If this breaks, say |
|---|---|---|---|---|
| 0 | Open the URL cold. Click **Start talking**, allow the mic | Orb reads READY WHEN YOU ARE → HEARING YOU / READY. One button, then it disappears | #4, #1 | "Mic permission is in the address bar — Retry is the recovery." |
| 1 | Type name + PIN in the rail, **Sign in** | Rail reads *Signed in as …* without scrolling on desktop | #2 setup | "Typed sign-in is the reliable path; voice sign-in exists as a fallback." |
| 2 | *"I'm travelling on a Saudi passport and my favourite colour is green."* | Rail gains two facts, each with the **verbatim sentence that taught it** and a timestamp | #2, Invariant 4 | "If the colour didn't land, the extract call is post-reply — ask the colour question after the next turn." |
| 3 | *"Do I need a visa for Japan? What should I see?"* | Spoken answer · ivory fact card with the same values as the spoken sourced clauses · a place strip ("Her pick, sourced photo") with Wikipedia + a revision date · the dossier now holds this turn under the previous one · quota chip may decrement | #1, #3, #5, the travel-agent surface | "If photos are missing, the note still shows — couldn't source a photo is a visible reject, not a hang." |
| 4 | **Hard reload** (⌘⇧R). Sign back in with the same name + PIN. *"What's my favourite colour?"* | *"Green"* — and the rail shows the **original** `learned_at`, not a new one | **#2, the graded one** | "If it forgot, the salt on Modal may have changed — that's a one-way door, named in the README." |
| 5 | Open `?gate_demo=1` in a new tab. Sign in. Ask #3 again | One extra segment appears **struck through** with its rejection reason. The spoken answer does not contain it. Audit note: *The model wrote the struck-through line. Deterministic code refused to speak it.* | **#5 — the deep dive, live** | "That's the demo: the model wrote that number; deterministic code refused to let it be spoken." |
| 6 | *"Do I need a visa for Wakanda?"* (or any uncovered pair) | Refusal card, stamp-red, embassy link. **No invented answer.** Dossier still holds Japan above it | Invariant 6 | "Empty card is a bug. Refusal with a route is the product." |
| 7 | Barge in: start a Japan question, then talk over her | Audio stops immediately, orb returns to HEARING YOU | #1, Invariant 7 | "The first 300 ms of her voice is ignored so echo cancellation can't false-barge." |

There is no Arabic row. Bilingual support was scoped and not built; named in the README limits table.

## What not to demo as if it were live

- The CSV/map **fallback layer**. There is no `?force_layer=` toggle. Point at the eval's `vendor-failure-1` and `tests/test_vendor.py`. If a live turn happens to serve `map`/`csv`, the card's `fallback source` badge is the tell.
- Quota hitting zero. If the chip already reads `reserve only`, say so up front — a test once wrote `spent=120` into the live ledger; true committed spend is 3.
