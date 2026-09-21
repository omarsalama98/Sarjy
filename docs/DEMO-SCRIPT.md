# Demo script

The reviewer opens https://vitas7777v--sarjy-fastapi-app.us-east.modal.run in a fresh profile. No README required. Frame: **1280×800**.

If a row breaks live, say the sentence in the last column and keep going. A recovered failure is better evidence than a restart.

| # | Say / do | Should happen | Proves | If this breaks, say |
|---|---|---|---|---|
| 0 | Open the URL cold. **Tap to talk**, allow the mic | Orb reads READY WHEN YOU ARE → HEARING YOU. Tap again to send. The button stays; it is how you talk and how you interrupt | #4, #1 | "Mic permission is in the address bar — Retry is the recovery." |
| 1 | Type name + PIN in **The trip** rail, **Sign in** | Rail reads *Signed in as …* without scrolling on desktop | #2 setup | "Typed sign-in is the reliable path; voice sign-in exists as a fallback." |
| 2 | *"I'm travelling on a Saudi passport and I'm vegetarian."* | Rail gains two facts (passport + diet), each with the **verbatim sentence that taught it** and a timestamp | #2, Invariant 4 | "If the diet didn't land, extract is post-reply — ask the diet question after the next turn." |
| 3 | *"Do I need a visa for Japan? What should I see?"* | Spoken answer · ivory fact card with the same values as the spoken sourced clauses · a place strip · the **Now** pane holds this turn; **The trip** rail shows the pair · quota chip may decrement | #1, #3, #5, the travel-agent surface | "If photos are missing, the note still shows — couldn't source a photo is a visible reject, not a hang." |
| 3b | *"Suggest some cities."* (do **not** re-name Japan) | She stays on Japan. The previous turn collapses to the trail. Cairo / home city must not become the trip | conversation follow-up | "If she switched country, that is the call-2 history bug — stop and say so." |
| 4 | **Hard reload** (⌘⇧R). Sign back in with the same name + PIN. *"Any dietary requirements I mentioned?"* | She says vegetarian — and the rail shows the **original** `learned_at`, not a new one | **#2, the graded one** | "If it forgot, the salt on Modal may have changed — that's a one-way door, named in the README. If they quote the brief's colour question instead: same `Fact` machinery, just teach a colour first." |
| 5 | Open `?gate_demo=1` in a new tab. Sign in. Ask #3 again | One extra segment appears **struck through** with its rejection reason. The spoken answer does not contain it. Audit note: *The model wrote the struck-through line. Deterministic code refused to speak it.* | **#5 — the deep dive, live** | "That's the demo: the model wrote that number; deterministic code refused to let it be spoken." |
| 6 | *"Do I need a visa for Wakanda?"* (or any uncovered pair) | Refusal card, stamp-red, embassy link. **No invented answer.** Trail still holds Japan | Invariant 6 | "Empty card is a bug. Refusal with a route is the product." |
| 7 | Barge in: tap the mic while she is speaking | Audio stops immediately, orb returns to HEARING YOU. Same control as talking | #1, Invariant 7 | "The first 300 ms of her voice is ignored so echo cancellation can't false-barge. If she is silent with text on screen, tap the audio chip." |

If the quota chip still reads `reserve only`, skip any claim that the Japan duration came from live Travel Buddy — unlock first (`docs/outbound/2026-09-21-quota-unlock.md`).

## What not to demo as if it were live

- The CSV/map **fallback layer**. There is no `?force_layer=` toggle. Point at the eval's `vendor-failure-1` and `tests/test_vendor.py`. If a live turn happens to serve `map`/`csv`, the card's `fallback source` badge is the tell.
- Quota hitting zero. If the chip already reads `reserve only`, say so up front — a test once wrote `spent=120` into the live ledger; true committed spend is 3.
- Spoken Arabic. The Orpheus adapter is in tree, unwired. The gate's English `NUMBER_WORDS` list would not cover it.
