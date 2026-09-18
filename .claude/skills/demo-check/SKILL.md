---
name: demo-check
description: Verify the deployed Sarjy is demo-ready end to end. Use before sharing the URL, before recording the Loom, before the presentation, and after any deploy — the deployment is a graded deliverable and a stranger will open it cold.
---

# Demo check

Requirement #4 is *a working deployment URL the reviewer can open without special setup.* This skill is the gate on that.

Run it **against the deployed URL in a fresh browser profile** — not localhost, not your logged-in tab with a warm cache and granted permissions. You are simulating a reviewer who has never seen this before and will not debug it for you.

## The checklist

**Cold open**
- [ ] URL loads with no console errors and no visible layout break
- [ ] It is obvious what to do within five seconds, with no instructions from Omar
- [ ] Mic permission is requested at a sensible moment, with context for why
- [ ] Works on a second browser (Safari and Chrome both — Safari's audio autoplay and mic behavior differ, and it breaks voice apps specifically)
- [ ] Nothing requires an API key, a login, an env file, or a README from the reviewer

**The seven requirements, each actually exercised**
- [ ] Speak → Sarjy responds by voice (#1)
- [ ] Tell it a fact → **reload / new session** → ask for it back and get it (#2). Do the actual reload; don't trust in-session recall.
- [ ] Trigger the external API and get real data back (#3)
- [ ] The deep-dive feature is visible and legible in live use, not just in the writeup (#5)

**Failure paths — deliberately break each one**
- [ ] Deny mic permission → clear, recoverable message, no dead end
- [ ] Interrupt mid-response (barge-in) → sane behavior, no overlapping audio
- [ ] Say something unintelligible / stay silent → graceful handling, no hang
- [ ] Force the external API to fail → Sarjy says it doesn't know, invents nothing (`AGENTS.md` §Invariant 6)
- [ ] Kill the network mid-turn → visible state, recovers or fails honestly
- [ ] No spinner anywhere that can outlive its operation

**Under a reviewer's hands**
- [ ] Two turns in a row work — most voice demos break on turn two
- [ ] A long rambling utterance doesn't break endpointing
- [ ] Rapid consecutive turns don't desync audio or state
- [ ] The off-script question gets a sane answer (reviewers always ask one)
- [ ] Nothing in the UI leaks a key, a raw prompt, or a stack trace

**Numbers**
- [ ] A `/measure` run against this exact deployment, recent enough to quote
- [ ] The quoted latency figure matches what the deployment actually does today

**Cost and quota — the silent demo killer**
- [ ] Free-tier quota remaining is enough for the presentation plus the reviewer's own exploration beforehand
- [ ] Rate-limit behavior is graceful, not a crash
- [ ] Nothing is about to expire (trial credits, a temporary tunnel URL, a preview deployment that gets garbage-collected)

## Steps

1. Run the checklist honestly against the deployed URL. Every unchecked box is a finding.
2. Report what failed, with specifics. **Do not report "demo-ready" with open boxes** — that's exactly the assertion-without-evidence this project forbids.
3. Fix blockers, redeploy, re-run. A partial re-run after a fix is not a pass.
4. Update the demo script: what to say, in what order, to show each requirement inside a few minutes.

## Anti-patterns

- Testing on localhost and calling the deployment verified
- Testing in the tab that already has mic permission and warm caches
- Only walking the happy path
- Checking requirement #2 without an actual fresh session
- Quoting a latency number measured against an older build
- Discovering the free tier is exhausted during the presentation
