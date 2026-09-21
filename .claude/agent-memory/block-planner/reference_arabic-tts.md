---
name: arabic-tts
description: Arabic TTS options for Sarjy — Deepgram Aura-2 has no Arabic voice at all, and Groq Orpheus's real constraints, verified 2026-09-21
metadata:
  type: reference
---

Verified 2026-09-21 from the vendors' own docs, not recalled.

**Deepgram Aura-2 has NO Arabic voice.** Languages are English, Spanish, Dutch, French, German,
Italian, Japanese ([voices & languages](https://developers.deepgram.com/docs/tts-models)); the
December 2025 expansion added the European set and Japanese, not Arabic, and Arabic is not on the
published roadmap. This — not the 200-char cap — is the actual reason Sarjy needs a second TTS
provider for Arabic, and it is the one-sentence answer to "why two TTS providers?" in a walkthrough.
`AGENTS.md` §Decided and `MASTER-PLAN.md` §Block C both omit it.

**Groq Orpheus** (`canopylabs/orpheus-arabic-saudi`), from
<https://console.groq.com/docs/text-to-speech/orpheus>:

- Endpoint `https://api.groq.com/openai/v1/audio/speech`, OpenAI-compatible. The `groq` SDK and
  `GROQ_API_KEY` are already in Sarjy for STT — no new dependency, no new secret.
- **200 characters maximum per request.** Collides with the gate's 400-char `quoted` allowance;
  resolve by chunking at the provider boundary, not by capping the register.
- **`response_format` accepts `"wav"` only.** The pipeline wants raw PCM s16le — strip the RIFF
  header. Sample rate is NOT documented; assume nothing, parse the header.
- **Streaming is not documented** — treat it as a batch call. TTFB is full synthesis time and
  chunks are sequential, so an Arabic turn is visibly slower than English.
- Free tier **10 RPM / 100 RPD / 1 200 TPM**. A 400-char answer is 2 requests → ~50 Arabic turns
  per day for the whole org, and 10 RPM 429s mid-conversation. **Arabic is a demo-able turn, not
  a mode.**
- Arabic voices: Abdullah, Fahad, Sultan, Lulwa, Noura, Aisha. Vocal directions (`[cheerful]`) are
  **English-model-only** — never emit one on the Arabic path.
- Listed under **Preview Models**, not Production.

⚠️ **The gate is weaker in Arabic and this is a limit to disclose, not a bug to fix late.**
`DIGIT_RE = re.compile(r"\d")` does catch Arabic-Indic digits, but `_NUMBER_WORD_RE` is English-only
and `wrong_pair`'s place-name scan reads English names from `data/reference/destinations.json` — so
a spelled-out Arabic number or a wrong Arabic country name passes every rule.

Related: [[block-c-design-choices]], [[block-a-design-choices]]
