---
name: cascaded-is-closed
description: Cascaded STT→LLM→TTS is a closed decision; speech-to-speech was reconsidered 2026-09-20 and rejected because the deep dive needs a text checkpoint
metadata:
  type: project
---

**Cascaded STT→LLM→TTS is closed and is not open for re-litigation.** Omar reconsidered
switching to Gemini Live API / speech-to-speech on 2026-09-20 and decided against it.

**Why:** `output_audio_transcription` transcribes audio the model has *already emitted*, so
there is no point at which text can be inspected and refused. The text checkpoint between LLM
and TTS is the entire reason this architecture exists — the grounding gate (the deep dive)
cannot run without it. "You cannot validate a citation that never exists as text."

**How to apply:** never plan or suggest anything that removes the text checkpoint, including
"just use the realtime API for lower latency." The latency cost of cascading is a known,
accepted trade. If latency comes up, the answer is a pre-recorded opener clip (Block C), not
a different architecture.

Related: [[block-a-design-choices]]
