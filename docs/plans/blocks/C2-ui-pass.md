# Block C2 — The travel-agent UI

**Written:** 2026-09-21 · **Parent:** `C-demoable.md` · **Source design:** `docs/design/` (Framer export) · **Brief:** `docs/DESIGN-BRIEF.md`

The screen is a **trip dossier that grows**. Turns append. Two visually distinct kinds of thing land in it, and the contrast between them *is* the guardrail, visible on every successful turn:

- **Documents** — sourced visa facts. Ivory, stamped, provenance footer.
- **Sarjy's picks** — her recommendations, each carrying a Wikimedia photo, the source's own one-line description, and a revision date. Her *choice* is judgement; the *photo and words* are sourced.

Five phases, cut from the bottom. **Phase 5 is never cut.** If Phase 4 is mid-flight two hours before the deadline, revert it rather than leave `main` broken.

---

## D0 — Safety rule (overrides `C-demoable.md` D2)

D2 capped the UI at *"a single `frontend/src/index.css`, ~120 lines, no new dependency, no component restructuring."* This block goes past it: the stylesheet is rewritten, `App.tsx` gains a turns array and layout wrappers, and new components (`Orb`, `PlaceStrip`) land.

**The safety rule for the whole block:**

> **Everything on a `useRef` stays on a `useRef`.** `currentTurnIdRef`, `turnTimingRef`, `turnInFlightRef`, `playbackQueueRef`, `detectorRef` and the barge window are untouched. Only what *renders* moves into the turns array. No change to the VAD, the WebSocket framing, the PCM path, or `reportTurnTiming`.

This matters because the timing legs and the barge guard are the two things a state refactor would silently break, and pytest cannot catch either.

---

## D1 — Places with sourced photos (reverses the earlier cut)

The earlier C2 D1 cut the suggestions strip because there was no backend behind it. That is no longer true.

`en.wikipedia.org/w/api.php` with `prop=pageimages|extracts|info&pithumbsize=800&redirects=1` returns an 800px lead image, a one-line description, a canonical URL and a revision date. **No key, no quota.** `httpx` is already a dependency.

Safety rejects: `type != "standard"` (disambiguation), HTTP 404, missing thumbnail, timeout. This is entity lookup, not image search — the inappropriate-content surface is a place article's encyclopedic lead image. Stated honestly in the README, not claimed as sanitised.

Fetches run **after the answer is handed to TTS**, concurrently via `asyncio.gather`. They must not appear in the first-audio path.

`place` only ever appears on a `judgement` line. **No gate change.**

---

## D2 — The orb is the persona, driven by real audio

Concentric SVG rings whose radius, stroke width and opacity are driven from a `requestAnimationFrame` loop writing CSS custom properties on a ref'd element — never `setState` at 60fps.

Mic level from an additive `AnalyserNode` on `getSharedMicStream()`. Speaking level computed from the Int16 PCM already passing through `onAudioChunk`. `playback.ts` and `capture.ts` are not touched.

States: `idle` slow breathe · `listening` rings expand with your voice, brass · `thinking` rotating dashed arc, amber · `speaking` rings pulse with her voice, green · error red and static. Under `prefers-reduced-motion` the rAF loop never starts.

---

## D3 — Four copy corrections that are truth, not taste

| Design says | Problem | Ships as |
|---|---|---|
| `PRESS TO TALK · interrupt anytime` | There is **no push-to-talk.** Client-side VAD listens continuously | `Start talking` before permission; after permission the button is gone and the orb carries state. The interrupt affordance is stated in the `speaking` sub-line: *Interrupt any time.* |
| `I'M LISTENING` as a fixed headline | Conflates four states and is wrong during `speaking` | The headline **is** the state (table in §Contract 2) |
| `YOUR TRAVEL AGENT · LIVE VOICE` | She books nothing. Invites questions she must refuse | `A VOICE FOR THE DOCUMENT · LIVE VOICE` |
| `LIVE` in the header **and** `LIVE` in the card footer | Same word, two meanings | Header reads `CONNECTED`; the card footer keeps `live` for the layer |

The visa quota chip ships. Arabic is **cut** — both rungs — and named as a limit. The header does not reserve a language slot.

---

## D4 — `sourced` rows carry no badge; `quoted` rows do

Badging every fact row `[sourced]` is noise when it is the norm. A `quoted` row gets a visible pill. The audit below keeps all three register pills (`sourced` / `quoted` / `view`).

---

## D5 — Two deep dives, argued as one system

Guardrails and reliability (the gate, the eval, the registers) **and** UI/UX and multimodal (the dossier, the orb, the imagery). The second exists to make the first legible — a reviewer can see what was sourced without reading a struck-through line.

---

## Scope

### In

1. **Phase 1** — turns array; sticky stage over scrolling dossier.
2. **Phase 2** — copy truth, tokens, fonts, header / stage / rail grid, ivory fact card, audit block, diagnostics, rail.
3. **Phase 3** — audio-reactive orb.
4. **Phase 4** — Wikimedia place lookup + `PlaceStrip`.
5. **Phase 5** — README, demo script, Loom outline. **Never cut.**

### Out

- Arabic, both rungs.
- A CSS framework, CSS modules, Tailwind, a component library, an npm dependency.
- Motion beyond the orb (and the orb is suppressed under `prefers-reduced-motion`).
- Re-measuring latency. This block cannot move `first_audio_ms`; it renders it.
- Changing the VAD, WebSocket framing, PCM path, or `reportTurnTiming`.
- `git add` / `commit` / `push`.

---

## Files

| File | Change | Phase |
|---|---|---|
| `frontend/src/App.tsx` | Turns array, layout wrappers, state-label mapping, quota chip, audit, diagnostics | 1 + 2 |
| `frontend/src/index.css` | Rewritten | 2 + 3 + 4 |
| `frontend/src/ui/FactCard.tsx` | One row per fact; `quoted` pill only; refusal stamp | 2 |
| `frontend/src/ui/Orb.tsx` | **New.** Concentric SVG rings | 3 |
| `frontend/src/audio/level.ts` | **New.** AnalyserNode + PCM RMS | 3 |
| `frontend/src/ui/PlaceStrip.tsx` | **New.** Up to three sourced photo cards | 4 |
| `frontend/src/protocol.ts` | `PlacesMessage` / `PlaceCard` | 4 |
| `frontend/src/net/connection.ts` | `onPlaces` callback | 4 |
| `frontend/index.html` | Font preload | 2 |
| `frontend/public/fonts/` | Vendored Big Shoulders 600/700 | 2 |
| `backend/app/tools/places.py` | **New.** Wikimedia lookup | 4 |
| `backend/app/pipeline/turn.py` | `SegmentLine.place`; post-TTS fetch | 4 |
| `backend/app/pipeline/protocol.py` | `PlacesOut` / `PlaceCardOut` | 4 |
| `backend/app/prompts.py` | One paragraph on `place` | 4 |
| `backend/app/main.py` | Emit `places` after TTS starts | 4 |
| `backend/tests/test_places.py` | **New.** MockTransport | 4 |
| `README.md` | Rewrite | 5 |
| `docs/DEMO-SCRIPT.md` | **New** | 5 |
| `docs/LOOM-OUTLINE.md` | **New** | 5 |
| `docs/PRs/PR_DEMOABLE.md` | **New** | 5 |

---

## Fonts — vendored, not linked

Display face is **Big Shoulders** (Google, SIL OFL), weights **600** and **700** only. Body is the system stack.

Vendored into `frontend/public/fonts/`. `@font-face` with `font-display: swap` and fallback `"Big Shoulders", "Haettenschweiler", "Arial Narrow", system-ui, sans-serif`. If the two woff2 files cannot be fetched, fall back to a Google Fonts `<link>` and say so in the PR doc.

---

## Contracts

### 1 — Layout

```
.app                 max-width 1200px; margin auto; padding 28px 24px 56px
                     display grid; grid-template-columns minmax(0,1fr) 300px; gap 28px
  .app-header        grid-column 1 / -1
  .stage             grid-column 1; sticky; orb + headline + CTA
  .dossier           grid-column 1; scrolling; newest turn last
  .rail              grid-column 2; position sticky; top 28px
@media (max-width: 900px)  → one column; .rail follows .dossier
```

`minmax(0, 1fr)` on the main column is load-bearing.

Stage order inside a turn, top to bottom — **evidence before prose before audit**:

```
.transcript    "You"
.fact-card     the document
.place-strip   her pick, sourced photo
.reply         "Sarjy"
.audit         the segment list + counts + the note
.diagnostics   this turn's timings
```

### 2 — State labels

| Condition | Ring class | Headline | Sub-line |
|---|---|---|---|
| `!started`, assets not ready | `ring-loading` | `WARMING UP` | Loading voice detection… |
| `!started`, ready | `ring-idle` | `READY WHEN YOU ARE` | Press start, then just talk. |
| `idle` (started) | `ring-idle` | `READY` | Speak whenever you like. |
| `listening` | `ring-listening` | `HEARING YOU` | Keep going — I'll answer when you stop. |
| `thinking` | `ring-thinking` | `CHECKING SOURCES` | Looking for a source for this. |
| `speaking` | `ring-speaking` | `SPEAKING` | Interrupt any time. |
| `interrupted` flag | (unchanged) | (unchanged) | ` · you interrupted` appended |
| `mic-blocked` | `ring-error` | `MICROPHONE BLOCKED` | `voiceIssue.message` |
| `mic-missing` | `ring-error` | `NO MICROPHONE` | `voiceIssue.message` |
| `unavailable` | `ring-error` | `VOICE UNAVAILABLE` | `voiceIssue.message` |

### 3 — Connection labels

`connecting → CONNECTING` · `ready → CONNECTED` · `rotating → REFRESHING` ·
`reconnecting → RECONNECTING` · `offline → OFFLINE` · `stale → STALE`.

### 4 — The quota chip

```
visa quota · {remaining} left
```

When `remaining === 0`, the chip turns warn-colour and reads `visa quota · reserve only`.

### 5 — The audit block

```
What she was allowed to say
{kept} spoken · {rejected} refused
```

Register pills: `sourced` → `sourced`, `quoted` → `quoted`, `judgement` → **`view`**.

When `rejected > 0`: *The model wrote the struck-through line. Deterministic code refused to speak it.*

### 6 — `FactCard.tsx`

Ivory surface, one row per fact, `quoted` pill only. Refusal: stamp-red border, **No source covers this pair.**, embassy link.

### 7 — Tokens

```css
--night: #0B1220;
--panel: #121C2D;
--panel-2: #162033;
--hairline: #223047;
--ivory: #F4EFE4;
--ink: #1A2334;
--brass: #C9A227;
--stamp: #B42318;
--board-green: #3D9B74;
--board-amber: #D4A017;
--slate: #8B96A8;
--paper-line: #DDE3ED;
```

### 8 — Places wire

```
PlacesOut { t: "places", turn_id, places: PlaceCardOut[], seq, ts_ms }
PlaceCardOut { name, title, description, image_url, page_url, revision_date, ok, reason }
```

`reason` is one of `not_found` · `disambiguation` · `no_image` · `timeout` · `http_error`.

PROTOCOL_VERSION stays 5 (additive).

---

## Failure paths

| # | State | Must look like |
|---|---|---|
| U1 | `covered === false` | Refusal card, stamp-red, embassy link |
| U2 | `degraded === true` | `fallback source` badge + different card border |
| U3 | Mic denied / missing | Red orb, legible headline, Retry present |
| U4 | `offline` | `OFFLINE` chip + Retry connection |
| U5 | Rejected segment | Struck through AND dimmed AND reason in stamp colour |
| U6 | Place lookup failed | Text note, visible "couldn't source a photo", never a broken img |
| U7 | Long content at 1280×800 | No horizontal scroll |
| U8 | 390 px | One column, rail last |

---

## Task list

### Phase 1 — The dossier

1. Replace per-turn scalars with `Turn[]`. `handleUtterance` pushes; callbacks patch by id.
2. Layout: sticky stage over scrolling dossier. Newest turn last, auto-scrolled into view.
3. Diff review: every `useRef` is untouched. `reportTurnTiming` is untouched.

### Phase 2 — The shell

4. State-label and connection-label mapping. Quota chip. Copy truth (D3).
5. Vendor the two woff2 files; `@font-face` + preload.
6. Rewrite `index.css`. Wrappers in `App.tsx`. `FactCard.tsx` → Contract 6. Audit → Contract 5.

### Phase 3 — The orb

7. `audio/level.ts` — AnalyserNode on the shared mic stream; PCM RMS from Int16 chunks.
8. `ui/Orb.tsx` — rAF writing CSS custom properties. `prefers-reduced-motion` path.

### Phase 4 — Places

9. `tools/places.py` with the four reject rules, injectable transport, 2.5 s timeout, in-process cache.
10. `SegmentLine.place`; prompt paragraph; `PlacesOut`; post-TTS concurrent fetch.
11. `tests/test_places.py` on MockTransport: happy path, 404, disambiguation, no thumbnail, timeout.
12. `PlaceStrip.tsx`. Wire types + `onPlaces`.

### Phase 5 — Documents (never cut)

13. Rewrite `README.md`. Write `docs/DEMO-SCRIPT.md` and `docs/LOOM-OUTLINE.md`.
14. `docs/PRs/PR_DEMOABLE.md`.

---

## Hard trigger

**Phase 5 starts no later than two hours before the deadline, whatever else is unfinished.** Documents are requirement #6. If Phase 4 is mid-flight it gets reverted to Phase 3's state rather than left broken.

---

## Cut, and named in the README

Arabic, both rungs · C2's original full state sweep, reduced to refusal, degraded, mic-blocked and rejected-row contrast · mobile beyond one coarse `@media (max-width: 900px)` · re-measuring latency.

---

## Gate

1. `typecheck` / `lint` / `build` green in `frontend/`; `make test` still green in `backend/`.
2. A four-turn spoken conversation against the **deployed** URL: the dossier grows, the orb moves with real speech, a places strip appears with photos and dates, an uncovered pair produces a refusal card, `?gate_demo=1` produces a legible struck-through rejection.
3. No `useRef` that existed before this block was rewritten. `git diff` shows it.
4. Every failure in the table above is written into the README's limits table rather than dropped.

---

## Draft commit messages

- `feat(ui): the trip dossier — turns accumulate, the screen is the receipt`
- `feat(ui): audio-reactive orb — the persona is driven by the real graph`
- `feat(places): Wikimedia lookups for sourced photo picks`
- `docs: README, demo script and Loom outline for submission`
