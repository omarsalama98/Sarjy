# Sarjy — UI v2 (now / trail / dossier)

**For:** the implementation pass that follows. Not a rebrand. Same night/brass/ivory language as `docs/DESIGN-BRIEF.md`.
**Problem:** every turn stamps four boxes (fact card, places, audit, timings). History grows linearly and the newest turn looks identical to the oldest. It reads as a debug log, not a travel agent working a file.

## What a reviewer notices in fifteen seconds

1. **What to do.** One mic control. Tap or hold Space. Not “Start talking” then wait for VAD.
2. **Whether she can hear / is thinking / is speaking.** The sticky stage (orb + headline) is the only live status. It must never be buried under history.
3. **The trip, not the log.** Passport, destination, visa status with provenance, places, remembered facts — one accumulating panel. The conversation is how that file got filled in.

Voice UX (the critic’s order, not visual order):

- Turn-taking is an explicit tap. Silence does not end a turn. Interrupting her is the same tap.
- State is instant: listening the moment the mic is hot, speaking the moment a buffer is scheduled, audio-blocked is a chip not silence.
- Failure is labelled: mic blocked, connection drop, audio dead, short utterance, visa fallback. No spinner that can outlive the operation.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│  SARJY     A voice for the document     live · quota · audio │
├─────────────────────────────────────────┬────────────────────┤
│  STAGE (sticky)                         │  TRIP DOSSIER      │
│  orb + HEARING YOU / CHECKING / SPEAKING│  Egypt → Germany   │
│  [ Tap to talk · hold Space ]           │  visa required     │
│                                         │  fallback · csv    │
│  NOW — this turn only                   │  Berlin · photo    │
│  you said / fact card / places / reply  │  Remembered        │
│  audit collapsed unless something refused│  Home city · dest  │
│                                         │  sign in           │
│  TRAIL — older turns, one line each     │                    │
│  You: …  ·  Sarjy: …                    │                    │
└─────────────────────────────────────────┴────────────────────┘
```

- **Now pane:** current turn, full treatment. Fact card and places live here, not on every historical row.
- **Trail:** older turns are one line (`You` / `Sarjy`). Click expands the same audit/card the reviewer needs. Default collapsed.
- **Trip dossier:** replaces the memory-only rail. Accumulates pair, visa row + provenance, unique places, remembered facts, sign-in. Memory is part of the trip, not a side quest.

## Out of scope

- New palette, new type, new orb.
- Rewriting any `useRef` on the audio path.
- PROTOCOL_VERSION bump.
- A second page or onboarding carousel.
