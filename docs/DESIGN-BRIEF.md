# Sarjy — UI design brief

**For:** a designer who will not see the codebase. This file is the entire brief.
**Product:** one live web page. Not an app store product, not a marketing site, not a chat SaaS.
**Primary viewer:** a hiring reviewer who opens a URL cold, talks into the mic, and watches a 5-minute Loom at **1280×800**.
**Also:** the same page on a phone. Safari and Chrome. No login, no API key, no README.

---

## 1. What you are designing

**Sarjy** is a **voice travel assistant**. You speak; she speaks back. She answers visa and entry questions for people travelling on Gulf passports (the demo pair is **Saudi Arabia → Japan**).

The product thesis, which the UI must make obvious in five seconds:

> She never states a travel fact she cannot source. When she knows, you see the source. When she doesn’t, she says so and points at the embassy. She does not guess.

This is **not** ChatGPT with a microphone. It is not a booking site. It is not a map. There are no flights, hotels, weather, or trip itineraries. There is one job: **speak, get a grounded visa answer, see the evidence.**

You are designing **one screen** that lives at a public URL. Everything happens on that screen. No routes, no onboarding carousel, no account wall.

---

## 2. Who uses it, in what order

A stranger lands. Within five seconds they must know: this hears you, this is about travel documents, press one button.

Then the demo (design every one of these as a real frame):

1. Click **Start talking**, allow the microphone.
2. Optionally type a name + 4-digit PIN to persist memory (or skip — it still works for this tab).
3. Say: *“I’m travelling on a Saudi passport and my favourite colour is green.”*
4. Say: *“Do I need a visa for Japan?”*
5. See a **document-like fact card** with the visa facts **and** hear her speak.
6. See the **sentence audit**: each clause tagged sourced / quoted / her view; a fake clause may appear **struck through** with a reason (that is the product, not a bug).
7. Hard-reload, sign in again, ask *“What’s my favourite colour?”* — the memory panel still shows green and the **original** sentence that taught it.
8. Ask *“Do I need a visa for Wakanda?”* — refusal + embassy link. Empty card is forbidden.
9. Interrupt her mid-answer (barge-in) — audio stops, state returns to listening.

If a frame does not support one of those beats, the design failed.

---

## 3. Visual job (read this before picking a palette)

**Do not design a chatbot.** No message list of rounded bubbles as the hero. No pulsing orb. No Inter / system-font / purple-gradient “AI product.” No cream + terracotta “tasteful startup.” No airline booking chrome. No stock palm-tree hero photo.

**Do design a speaking document.** The emotional reference is: a **passport visa foil**, an **embassy letter**, a **departures board**. Night, Gulf, official — warm metal on dark, not neon cyber.

Suggested direction (you may push it, do not flatten it into a generic dark dashboard):

| Token | Role | Starting point (you may refine) |
|---|---|---|
| Night ink | Page | `#0B1220` |
| Document ivory | Fact card surface (the one light object) | `#F4EFE4` |
| Foil brass | Accent, listening, links on dark | `#C9A227` |
| Stamp red | Refusal, rejection, mic blocked | `#B42318` |
| Board green | She is speaking | `#3D9B74` |
| Board amber | She is thinking | `#D4A017` |
| Quiet slate | Secondary text, diagnostics | `#8B96A8` |

Typography: **one display face with authority** (a modern grotesque with slightly condensed caps for the live status word — think a departure board, not a fashion magazine) + **one readable text face**. Do not use Inter, Roboto, Arial, or Times as the character of the page. Arabic will appear in transcripts later; pick a pair that has a credible Arabic companion or leave a specified Arabic fallback (`Noto Naskh Arabic` / `IBM Plex Sans Arabic`) for `dir="rtl"` lines.

**One memorable object:** the **fact card as a visa/entry document** — paper-colored, stamped pair `SAUDI ARABIA → JAPAN`, foil rule, fields like a form. Everything else is quieter than that card.

Motion: almost none. State color changes instantly (perceived latency). No staggered fade-in on every block. A listening indicator may breathe **gently**; thinking and speaking must not look like a loading spinner that might never end.

---

## 4. Layout — one page, two regions

**Desktop (1280×800 — the Loom frame, design this first)**

```
┌──────────────────────────────────────────────────────────────┐
│  SARJY                         EN | العربية     quota  quiet │
│  A voice for the document.     [connection: live · 42ms]     │
├──────────────────────────────────────────────┬───────────────┤
│                                              │  REMEMBERS    │
│           STATUS WORD                        │  Signed in as │
│           LISTENING                          │  Omar         │
│           (the biggest thing until a card)   │               │
│                                              │  Favourite    │
│   [ Start talking ]   or   live mic hint     │  colour green │
│                                              │  “you said…”  │
│   YOU  “Do I need a visa for Japan?”         │  2 / 20       │
│                                              │  [Sign out]   │
│   ┌─ FACT CARD (document) ────────────────┐  │  [Forget]     │
│   │ SAUDI ARABIA → JAPAN                  │  │               │
│   │ Visa type     eVisa                   │  │  Name [    ]  │
│   │ Maximum stay  90 days                 │  │  PIN  [    ]  │
│   │ Travel Buddy · 20 Sep 2026 · live     │  │  [Sign in]    │
│   └───────────────────────────────────────┘  │               │
│                                              │               │
│   SHE  spoken answer (same facts, prose)     │               │
│                                              │               │
│   AUDIT  sourced · quoted · view · REJECTED  │               │
│                                              │               │
│   last turn 1.83 s · diagnostics, tiny       │               │
└──────────────────────────────────────────────┴───────────────┘
```

- Main column ~ 60–65%; memory panel sticky on the right, not a modal.
- Page width is not a 760px blog column. Use the Loom width. Do not require horizontal scroll at 1280×800 with a long answer, a 400-character quote, and a 10-row card.
- The fact card sits **above** the spoken paragraph and **above** the audit list. Evidence first, then the sentence, then how the sentence was built.

**Mobile (~390×844)**

- Same content, stacked: identity/status → primary control → transcript → fact card → spoken answer → audit → memory (collapsible, default open enough to sign in).
- Thumb-reachable **Start talking**.
- No horizontal scroll. `overflow-wrap` everywhere speech can be long.

**Do not add:** nav, footer sitemap, settings page, history drawer of old chats, avatar, waveform visualizer as the product, “new conversation,” file upload, or a second screen.

---

## 5. Every region, in detail

### 5.1 Identity (always visible)

- Wordmark: **Sarjy** (that spelling).
- One-line purpose a stranger understands: e.g. *“Ask by voice. Every visa fact is sourced.”* Not a paragraph. Not a slogan about “AI.”
- Language control (two options only): **English** and **العربية**. Disabled while a turn is in flight. Arabic means *she understands Arabic*; answers may still be English depending on what engineering ships — do not design a fully Arabic chrome, fully RTL app, or mixed-script editor. Transcript/reply/audit lines get `dir="rtl"` when Arabic is selected; the memory panel and buttons stay English for this version.

### 5.2 Conversation state (the live status)

This is the voice-UX equivalent of a play/pause button. It must be readable from across a desk. Four **normal** states, mutually exclusive, plus error states that must **not** look like idle.

| State | When | What the human should feel | Color family |
|---|---|---|---|
| **Idle** | Mic on, waiting | She is ready. Not broken, not thinking. Copy like *Listening for you…* | Quiet |
| **Listening** | User is speaking (VAD) | She hears you **now**. | Brass / accent |
| **Thinking** | Speech ended, answer not yet playing | Work is happening. Must not look frozen. | Amber |
| **Speaking** | Audio is playing | She is talking; you may interrupt. | Green |
| **Interrupted** | User barged in | A small mark on listening, e.g. *Listening (you interrupted)* | Listening + a quiet flag |

Show **one** large status word plus **one** short hint sentence. Do not show the raw enum (`idle`). Do not put connection state in this same badge — connection is a different machine (see 5.9). A reconnect must never look like “thinking.”

### 5.3 Primary control

Before mic is granted:

- Button label: **Start talking** (not Start, not Enable microphone, not Connect).
- While VAD assets load (~16MB, can take a few seconds on first visit): button **disabled**, label **Loading voice detection…**
- While the click is in flight: **Starting…**
- After success: the button **goes away**. The status region takes over. There is no Stop. Closing the tab stops. (Do not invent a hang-up button.)

Mic problems — each is its own UI, never a spinner:

| Kind | Copy (use this, you may tighten but keep the meaning) | Control |
|---|---|---|
| Permission denied | *Sarjy needs the microphone to hear you. Allow it in the address bar, then press Retry.* | **Retry** |
| No microphone | *No microphone was found on this device.* | **Retry** |
| Voice engine failed to load | Show the exact error string from the app (placeholder: *Voice detection failed to load.*) | Start talking **disabled**, with the error visible |

Mid-session mic revoke uses the same blocked message + Retry.

### 5.4 Transcript (“You”)

The last thing the user said, as text, once speech-to-text returns. One turn, not a chat log of the whole session. Label **You**. If empty, omit the block — do not show a ghost bubble.

On a new utterance, **clear** the previous you/her/card/audit **immediately** (otherwise Japan’s card sits under a Thailand answer). Design the empty-during-thinking frame: status = thinking, previous card gone, not a blank page crash.

### 5.5 Fact card (the product)

This is the deep dive, on screen. Three shapes. Never an empty box.

**A. Covered, with facts** (happy path)

Header: `{passport_name} → {destination_name}`  
Example: **Saudi Arabia → Japan**

Rows (example — design with this exact content so type sizes are real):

| Kind badge | Label | Value |
|---|---|---|
| sourced | Visa type | eVisa |
| sourced | Maximum stay | 90 days |
| sourced | Passport validity | Valid on arrival |
| sourced | Also required | Customs declaration |

Footer, omit nulls, this order:

- Source name (link if URL present) — e.g. **Travel Buddy**
- Source date — e.g. **2026-09-20**
- `retrieved {timestamp}`
- Layer name: `live` | `cache` | `map` | `csv`

If `degraded` is true (layer is `map` or `csv`): a badge **fallback source** that cannot be mistaken for a live answer. Different border, different badge, not a tiny grey tag.

The card is a **document**. Ivory/paper on the dark page. Kind badges are small pills: `sourced` vs `quoted` (quoted = the vendor’s own wording).

**B. Covered, zero facts**

Same header + provenance footer + the line: **Nothing to show for this pair.** No empty list.

**C. Not covered** (`covered === false`) — refusal

Same header. Line: **No source covers this pair.**  
If embassy URL exists: a link **Embassy page**, `target="_blank"` `rel="noreferrer"` (leaving the tab kills the voice session).  
Border/stamp in refusal red. Still a card, not a toast.

External links always open a new tab. Never navigate this page away.

### 5.6 Spoken answer (“Sarjy”)

The full sentence she actually speaks (the TTS string). Label **Sarjy**. This can be long. It must **not contradict** the card: same numbers, same visa type. You are not writing this copy; you are laying out a variable-length paragraph.

### 5.7 Sentence audit (segments)

A list, one row per clause, **including failures**. This is how we prove we didn’t just prompt “don’t hallucinate.”

Each row:

- Kind pill: **sourced** | **quoted** | **judgement** (in the UI you may label judgement **view** if it reads clearer — pick one word and stick to it; internally it is `judgement`).
- The clause text.
- If quoted and kept: attribution prefix like *According to Travel Buddy:* then the quote.
- If kept and sourced: quiet provenance `(Travel Buddy, live, 2026-09-20)`.
- If **rejected**: text **struck through and dimmed**, plus reason in refusal color, e.g. `— rejected: digit`. The spoken answer must **not** contain that clause. A reviewer will look at this row and listen.

Example rejected row to design with:

> ~~Japan allows stays of 30 days.~~ — rejected: digit  
> (The model invented 30; code refused to let it be spoken. The card still says 90 days.)

If a hedge notice is on: *A tool result came back but nothing was sourced or quoted from it — flagged for review.*

Do not style this like a developer console. It is a public audit trail. Rejected must be unmistakable at a glance (strikethrough + dim + reason), not a red outline that looks like an error in the app.

### 5.8 Memory panel — “What Sarjy remembers”

Title: **What Sarjy remembers**

This is how we pass “what’s my favourite colour after a reload.” Facts are structured. Each fact shows:

- **Label** — e.g. Favourite colour  
- **Value** — e.g. green  
- **learned** time (display as a short local time)  
- **you said:** the verbatim sentence that taught it, in quotes  

Capacity: `2 / 20` (used / max).

**Anonymous tier** (default):  
Line: *Remembered for this session only — sign in to keep these*

Form:

- Name — text, max 32 characters  
- PIN — 4 digits only, `password` type, numeric keypad on mobile  
- Button: **Sign in**

This is a **nameplate**, not real security. Do not add email, OAuth, “Forgot PIN,” or captcha. Do not look like a bank login.

**Signed-in tier:**  
*Signed in as {name}*  
Button: **Sign out**

Always: **Forget everything** — disabled when there are no facts. No per-fact delete.

Server messages appear in this panel (success, wrong PIN, name clash). Design a message slot. Empty state: *Nothing remembered yet.*

PIN is cleared from the field after submit; do not echo it back.

### 5.9 Connection + diagnostics (quiet)

A small monospace strip, not competing with the status word:

- Connection: `connecting` · `ready` (show as **live**) · `rotating` · `reconnecting` · `offline` · `stale`
- When **offline**: button **Retry connection**
- Optional: last ping RTT (`42ms`)
- **Visa quota:** `{remaining} left above reserve (spent {spent}/{total})` — example `71 left above reserve (spent 9/120)`. This is a scarce live API. Visible, not a progress bar celebrating spend.
- Last turn: `last turn 1.83 s voice-to-voice · endpoint 0.42 s · redemption 300 ms` — visible, **not** announced by screen readers (`aria-live="off"`).

**Ping** is an engineering leftover. Hide it (details/summary “Diagnostics” or omit from the visual design). Do not put Ping next to Start talking.

Session id can live in diagnostics only.

Notice line for reconnect-during-answer: *Connection dropped mid-answer — ask again.*

Turn failure: `({stage}) {message}` e.g. `(tts) The voice service is unavailable.` Distinct from mic-blocked. Recoverable — they can speak again.

---

## 6. Copy you may use (do not invent a different product voice)

**Tone:** calm, specific, official-but-human. Like a well-run embassy counter, not a startup landing page and not a robot.

| Place | Copy |
|---|---|
| Purpose | Ask by voice. Every visa fact is sourced. |
| CTA | Start talking |
| Idle | Listening for you… |
| Listening | Hearing you… |
| Thinking | Checking sources… *(prefer this over “Thinking…” — it matches the thesis)* |
| Speaking | Speaking… |
| Refusal | No source covers this pair. |
| Empty facts | Nothing to show for this pair. |
| Embassy | Embassy page |
| Degraded | fallback source |
| Hedge | A tool result came back but nothing was sourced or quoted from it — flagged for review. |
| Memory empty | Nothing remembered yet. |
| Anonymous | Remembered for this session only — sign in to keep these |

Do not write “powered by AI,” “hallucination-free,” “100% accurate,” or legal disclaimers longer than one quiet line. If you want a legal whisper: *Visa rules change. Confirm with the embassy before you fly.* — footer-small, not a hero.

---

## 7. States to deliver as frames

Deliver **separate frames** (Figma or equivalent), named exactly:

1. `01-cold` — first paint, assets still loading (disabled CTA)
2. `02-ready` — Start talking enabled, memory empty anonymous
3. `03-mic-blocked` — retry
4. `04-listening` — user speaking, no card yet
5. `05-thinking` — previous card cleared
6. `06-answer-japan` — full happy path (card + speech + audit), quota visible
7. `07-gate-reject` — same as 06 plus one struck-through invented number
8. `08-refusal-wakanda` — refusal card + embassy link
9. `09-signed-in-memory` — panel with colour = green and quote
10. `10-offline` — retry connection
11. `11-desktop-1280x800` — frame 06 cropped to exact Loom size
12. `12-mobile-390` — frame 06 stacked

Optional: `13-arabic-transcript` — one RTL user line, English chrome.

---

## 8. What you are not designing

- A second page, blog, docs, or marketing site
- Chat history, threads, or “share this answer”
- Maps, photos of destinations, flags as decoration (a small ISO code `SA` / `JP` on the card is fine; cartoon flags are not)
- Voice waveform, 3D orb, talking avatar
- Dark/light toggle (ship **dark page + light document card**)
- User settings, API keys, model picker
- Onboarding tooltips that the reviewer must dismiss before talking
- Illustration of a woman in an abaya or any stereotyped “Gulf travel” collage
- New features (calendar, packing list, prayer times, flights)

Engineering will implement your layout in the **existing** React page (`App.tsx`). Prefer **named regions and states**, not a forest of new components that imply new product behavior. A flat hierarchy is better: header, status, stage, document, audit, rail.

---

## 9. Accessibility and voice constraints

- Status word: `aria-live="polite"`. Latency numbers: `aria-live="off"`.
- Contrast: ivory card text on ivory is a trap — dark ink on the card, light text on the night page. Rejected text still needs readable contrast even when dimmed.
- Visible focus rings on Start, Retry, Sign in, links.
- `prefers-reduced-motion`: no breathing indicator.
- Do not autoplay anything on load. Audio starts only after **Start talking**.
- Hitting a source/embassy link must not replace this tab.

---

## 10. Deliverable

1. Figma (or equivalent) file with the frames in §7.
2. A short **annotation** layer: font names, hex, spacing scale (8px grid is fine), which state color maps to which CSS class conceptually (`idle` / `listening` / `thinking` / `speaking`).
3. Export: desktop 1280×800 PNG of frames 02, 06, 07, 08 and mobile PNG of 06 — so engineering can implement without interpreting vibe.

If you produce HTML/CSS instead of Figma: **static mock**, no need to wire a microphone. Dummy content from §5.5 and §7 is enough.

Success is: a reviewer who has never heard of Sarjy understands the page in five seconds, the visa answer looks like a **document with a source**, a rejected clause is obviously refused, and the Loom at 1280×800 does not look like a student CSS exercise or a ChatGPT skin.
