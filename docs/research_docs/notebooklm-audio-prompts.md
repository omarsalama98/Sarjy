# NotebookLM Audio Overview prompts

**Purpose:** turn the research docs into listenable briefings for someone **building** a voice assistant this week and defending it in an interview — not for someone writing a survey.

Start with **Audio 1**. It covers everything. The other three are optional deep cuts for the areas you'll actually be questioned on.

Paste each block into NotebookLM's Audio Overview → *Customize* box.

---

## Audio 1 — The working engineer's tour ⭐ start here

Target ~25–30 min. This is the one that gets you from zero to building-and-explaining.

```
Audience: one senior full-stack engineer who is building a real-time voice
assistant THIS WEEK and will have to defend every architectural choice in a live
technical interview with people who build voice agents professionally. He is not
a researcher and is not writing a paper.

Goal: by the end he should be able to (a) build a cascaded voice pipeline without
guessing at any stage, and (b) answer "why did you do it that way?" for each one.

Cover in this order:
1. A 60-second map of the whole problem: what has to happen between someone
   finishing a sentence and hearing a reply.
2. How audio becomes something a model can consume — only as much as he needs.
   Land one number hard: audio token rates versus text token rates, and why that
   single ratio explains most architectural decisions in the field.
3. The two architectures — cascaded STT→LLM→TTS versus end-to-end
   speech-to-speech. What each preserves, what each throws away, what each costs.
4. Then walk the cascaded pipeline stage by stage. For every stage: what it does,
   what it costs in milliseconds, what it discards, and how it fails in production.
5. Endpointing in its own section — it deserves one. Why the silence threshold is
   usually the largest controllable number in the whole budget.
6. Streaming and overlapping: what can start before the previous stage finishes,
   and what genuinely cannot.
7. Where a guardrail or validation step can sit in this pipeline, and why the
   architecture choice in point 3 determines whether that is even possible.
8. What actually breaks in production: barge-in, echo, vendor timeouts, cold
   starts, rate limits.

Rules:
- Mechanism and numbers over history. Never say "researchers have explored" —
  say what the thing does and what it costs.
- Every latency figure: say where it came from, and whether the sources agree.
- Skip entirely: paper genealogies, model leaderboards, training these models
  from scratch, and anything he cannot act on this week.
- Where the sources support a claim only weakly, SAY SO. He would much rather
  hear "only one blog claims this" than a confident wrong number.
- Be concrete. "A 500 ms default silence threshold can exceed your entire
  inference budget" beats "endpointing matters."
- End with the 10 things he should be able to say cold, without notes.

Tone: two experienced engineers explaining this to a colleague who is smart but
new to audio. Dense. No filler, no recap loops, no throat-clearing.
```

---

## Audio 2 — The architecture defence

Target ~15 min. **The single likeliest interview question**, and your weakest-sourced doc. Worth doing even if you skip the rest.

```
Audience: an engineer who has chosen a CASCADED pipeline (STT → LLM → TTS) over
an end-to-end speech-to-speech model, for one specific reason: his project's
whole point is that the assistant never states a fact it cannot source, and a
cascaded pipeline gives him a text checkpoint where he can inspect and gate what
the model is about to say. An end-to-end model gives him nothing to inspect —
you cannot validate a citation that never exists as text.

He has to defend that choice to people who build voice agents for a living.

Do this:
1. Steelman the OPPOSITE choice first. Make the strongest possible case for
   end-to-end speech-to-speech — latency, paralinguistics, naturalness, what
   cascaded genuinely loses at the ASR boundary.
2. Then give the honest rebuttal, and be clear about what it costs him.
3. Be specific about what a cascaded pipeline throws away: tone, emotion,
   emphasis, hesitation, speaker identity. What can he recover, and how?
4. What are the sharpest follow-up questions an expert would ask him about this
   decision? Ask them out loud, then answer them.
5. Where do the sources in this notebook disagree on this, and which claims rest
   on a single weak source?

Rules: no history, no survey. This is rehearsal for a conversation. Assume he
has already decided — the job is to make him unembarrassable about it, including
naming what he gave up.
```

---

## Audio 3 — Where the time actually goes

Target ~15 min. For the "where does the time go" question, which gets asked regardless of deep-dive track.

```
Audience: an engineer instrumenting a voice pipeline who must present a latency
breakdown and say what he tried, what worked, and what did not.

Cover:
1. The full budget from "user stops speaking" to "first audio out" — every stage,
   with realistic millisecond ranges, and say which are typical versus best-case.
2. Rank the stages by how much of the total they usually own. Be explicit about
   which are controllable by him and which live inside a vendor.
3. Endpointing in depth: silence thresholds, neural VAD, semantic turn detection.
   The real trade-off is cutting the user off versus making them wait — treat
   that as a product decision, not a constant.
4. What can be overlapped, and the actual mechanics: streaming ASR into the LLM,
   LLM tokens into TTS, TTS into playback. Where does true streaming break down?
5. Perceived versus measured latency. What buys tolerance without changing the
   stopwatch — and be honest that these are different things.
6. Why published vendor latency numbers are not comparable, and what to measure
   yourself instead.

Rules: numbers throughout, with their source and whether sources agree. No
vendor rankings — he will measure his own. End with the 5 things he should
instrument from the very first working turn.
```

---

## Audio 4 — Arabic and code-switching

Target ~12 min. Only if the bilingual feature survives the cut. Use the `arabic-voice-research` doc as the main source — it's better sourced than the others.

```
Audience: an engineer adding Arabic to an English voice assistant, for users who
code-switch constantly — Arabic sentences carrying English technical terms and
proper nouns mid-sentence. Native Arabic speaker, so skip anything about the
language itself; this is purely about what the systems do.

Cover:
1. Why dialect matters enormously for ASR, with the actual error-rate gap between
   Modern Standard Arabic and the major dialects. Name which dialects are
   currently usable and which are not.
2. Why intra-sentence code-switching is architecturally hard, and what happens in
   practice when a system cannot do it.
3. The output leg — why it is the bigger risk than the input. Language detection
   on mixed text, and why an English word inside an Arabic sentence gets
   mispronounced.
4. Why word error rate overstates failure on code-switched speech, and what to
   look at instead.
5. Bidirectional text in a UI: what breaks when Arabic and English share a line.

Rules: practical throughout. Every number with its source and date. Say plainly
where the evidence is vendor-claimed rather than independently measured.
```

---

## Using these

**Do Audio 1 first, then Audio 2.** Those two cover what you'll actually be asked. 3 and 4 are for if the build leaves you time.

**Before generating, add the arXiv papers** listed in `SOURCES.md` as notebook sources — especially **Moshi (`arXiv:2410.00037`)** for Audio 2. Three of your eight docs cite zero primary sources, and two of those three are exactly what Audio 1 and Audio 2 cover. Without the papers, NotebookLM is confidently summarising blog posts.

**Listen with a notepad for the "10 things to say cold" section** at the end of Audio 1. Write them in your own words afterwards — that's the part that survives to the interview.

**If an audio comes out too shallow**, regenerate with this appended:

```
That was too high-level. Go deeper on mechanism: specific architectures, specific
numbers, specific failure modes. Assume the listener already knows what ASR and
TTS mean. Cut all definitional preamble.
```
