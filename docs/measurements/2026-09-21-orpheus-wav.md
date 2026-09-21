# Orpheus Arabic TTS — live probe 2026-09-21

**Parked.** This is why Arabic is not on the demo path. The adapter
(`backend/app/providers/groq_tts.py`) is in tree; `get_tts()` returns
Deepgram. Re-wire only after the gate covers Arabic number-words.

Groq `canopylabs/orpheus-arabic-saudi`, voice `noura`, `response_format=wav`,
`sample_rate=24000`. Terms accepted on the org (a prior call 400'd
`model_terms_required`). SDK return type is `AsyncBinaryAPIResponse`;
bytes come off `await response.read()` — there is no `aread()`.

## Body layout (not a 44-byte canonical WAV)

First 64 bytes of a 53 830-byte body for `"مرحبا"`:

```
RIFF size=0xFFFFFFFF WAVE
fmt  16  PCM  channels=1  rate=24000  byte_rate=48000  block=2  bits=16
LIST 26  INFO/ISFT  "Lavf61.7"   (ffmpeg)
data size=0xFFFFFFFF  then the rest of the file is s16le PCM
```

The RIFF and `data` sizes are the unsized-WAV sentinel `0xFFFFFFFF`,
not the real payload length. `wav_to_pcm16` treats that sentinel as
"PCM is the remainder of the body." A real overrun on any other chunk
still raises.

## Numbers

n=1 each, a format/adapter probe — not a latency distribution. Do not quote
these as the Arabic TTFB in the Loom.

| Input | chars | chunks | ttfb_ms | total_ms | pcm bytes | audio_s |
|---|---|---|---|---|---|---|
| `مرحبا، هل أحتاج فيزا؟` | 21 | 1 | 805 | 805 | 126 712 | 2.64 |
| two-sentence visa-style paragraph | 232 | 2 (155+77) | 2 894 | 4 550 | 1 328 616 | 27.68 |

TTFB is whole-first-chunk, not a stream. A ~150-character first chunk
costs ~3 s before any PCM yields. The second request added ~1.7 s.
English Aura-2 will beat this; that is the finding, not a bug.

Voice ids on the wire are lowercase (`noura`, not `Noura`). Title-case
400s with `voice must be [fahad sultan noura lulwa aisha abdullah]`.
`noura` kept to match Aura-2 Thalia (female) across the language switch.
