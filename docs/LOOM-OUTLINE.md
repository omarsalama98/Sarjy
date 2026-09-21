# Loom outline — 5 minutes

One browser, one tab, mic tested, quota chip read before record. Open `?gate_demo=1` in a **second** tab in advance (signed in) so row 5 is a tab-switch, not a reload surprise.

If a turn fails on camera: **keep rolling and say what happened.** A recovered failure is the deep dive working.

| Time | Shot | Script beat |
|---|---|---|
| 0:00–0:20 | Live URL, cold. Orb idle. | "Sarjy is a voice travel agent that never states a travel fact she cannot source. The screen is the receipt." |
| 0:20–1:50 | Demo script rows 0–3, real-time, no cuts. Linger on the dossier after Japan: card + photos + audit stacked under the earlier memory turn. | Watch the orb through READY → HEARING YOU → CHECKING SOURCES → SPEAKING. Name CHECKING SOURCES as the wait, not a hang. |
| 1:50–3:10 | **The deep dive.** Tab-switch to `?gate_demo=1`. Row 5. Then one screen of `backend/app/tools/gate.py` — value substitution, digit rule, placeholder rule. | "The model wrote that number; deterministic code refused to let it be spoken. The struck-through line is the product." |
| 3:10–3:50 | Row 6 — Wakanda / uncovered pair. Refusal card + embassy. Then: the fallback layer has **no live toggle** (D9). Point at the eval table. | "Outside coverage she refuses with a route. Degraded live answers wear a fallback badge — I will not fake a vendor outage on camera." |
| 3:50–4:25 | Latency numbers from `docs/measurements/2026-09-20-two-corrected-numbers.md`. | "Two earlier numbers were wrong: TTS TTFB was 85 ms until we put the clock before the Deepgram handshake. Honest median is 566 ms. Same story for LLM TTFT, 30 → 890." |
| 4:25–5:00 | README §What I'd do with another week. | Arabic is parked, not half-shipped (gate is English-only; Orpheus probe in `docs/measurements/2026-09-21-orpheus-wav.md`). Structured place picks. Paraphrase injection (`injection-2`, labelled fail). A pretend-vendor-down toggle. |

## Recording notes

- 1280×800. System audio + mic. One tab for the happy path so the dossier accumulates; second tab already on `?gate_demo=1`.
- Do not click Ping, do not narrate diagnostics. The orb and the card are the picture.
- If Wikimedia is slow, the photos arriving *while she is already speaking* is the point — do not wait in silence for them.
- If the quota chip reads `reserve only` before you start, say it in the 0:00–0:20 beat so it isn't a surprise at row 3.
