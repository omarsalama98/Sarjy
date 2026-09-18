---
name: update-sarj
description: Draft a progress update, a question, or an API-key request to the Sarj team. Use at natural checkpoints, when blocked, and when a day passes with little progress — communication is a separately graded part of this take-home.
argument-hint: [what happened since the last update]
---

# Update Sarj

The rubric has a whole Communication section. It says, in its own words: *"Please give us updates of how the work is progressing (even if the update is, busy day! No time to work today)"* and *"Ask if you blocked / confused / need to brainstorm with us."*

This is the cheapest scoring opportunity in the assignment and the easiest to forget while heads-down. **Silence is the only wrong answer.**

## When to draft one

- After the deep-dive track is chosen — tell them what you picked and why
- After the first deploy — give them the URL early, let them poke at it
- Whenever blocked, and immediately rather than after a day of struggling
- Whenever an API key is needed. The brief says to ask, and names Groq / Gemini / SambaNova / Cerebras as easier for them. Asking is the intended path; quietly burning personal credits is not.
- After a day with little or no progress — this is explicitly invited and costs nothing
- Before the presentation, with the Loom/PDF

## Shape

Short. A few lines, not a report. They are reading many of these.

- **What moved** since last time, concretely
- **What's next**, briefly
- **Anything you need from them** — a key, a GitHub handle, a decision, a sanity check
- A link if there's something to look at

Optional and often worth it: one thing you're genuinely unsure about. Asking a good question reads as engineering judgment, not as weakness — and the brief invites brainstorming directly.

## Tone

Omar's own voice — a peer sending a working update, not a candidate performing diligence. Specific beats enthusiastic. No status-report padding, no manufactured confidence about things that aren't working yet.

Be honest about setbacks. "Tried X for latency, it was worse than Y, here's the number, going with Y" is a *better* update than silence followed by a polished result — it shows the process the rubric is trying to see.

## Steps

1. Check `docs/PRs/` and recent work for what actually moved since the last update.
2. Draft it. Keep it short.
3. Show it to Omar. **Never send anything on his behalf** — no email, no Slack, no message anywhere. He sends it.
4. Once sent, note the date so the next update knows where it starts.

## Anti-patterns

- Going quiet during the hard part — exactly when an update is most valuable
- Padding an update to sound busy
- Claiming something works before `/demo-check` says it does
- Burning personal API credits instead of asking, when the brief says to ask
- Sending anything yourself
