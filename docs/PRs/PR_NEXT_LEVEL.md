# PR_NEXT_LEVEL — grounded, controllable, demoable

## Summary

Unlock path for live visa data (operator-only), silent-playback recovery, user-controlled mic instead of VAD, a now/trail/dossier surface, conversation-level evals, and Arabic input + spoken Arabic behind RoutedTTS.

## Problem

The visa layer was correct and gated off (ledger seeded at 120). Playback could go silent with no error after a suspended AudioContext. VAD cut turns after 600 ms of pause. History stamped four debug boxes per turn. Eval was single-turn, so "suggest cities" after Germany had no coverage. Whisper was hardcoded `en`.

## Solution

- **Live grounding:** dead-ledger warning at construction; `data/cache/` README; Omar-only unlock notes. Agents never write the dict.
- **Audio health:** resume-before-schedule, `onstatechange`, frozen-clock recreate, header chip.
- **Mic:** `MicRecorder` + worklet streams PCM while hot. Toggle / hold Space. Tap barges. VAD deleted.
- **Surface:** Now pane, trail, accumulating trip dossier. Existing audio `useRef`s untouched.
- **Eval:** `run_eval.py` threads history through `build_user_block`. Five multi-turn cases, labels written first.
- **Arabic:** `StartIn.lang` → Whisper; `<reply_language>` on call 2; `GroqOrpheusTTS` + 200-char chunker + `RoutedTTS`. Fixed phrases stay English TTS. Gate gap named in the README.

PROTOCOL_VERSION stays 5.

## How to Test

```bash
cd backend && make typecheck && make lint && make test
cd frontend && npm run typecheck && npm run lint && npm run build
cd backend && uv run python ../eval/run_eval.py --out ../eval/results/
```

Human: quota unlock (`docs/outbound/2026-09-21-quota-unlock.md`); then a spoken Egypt→Germany → "suggest cities" → barge → reload recall, plus one Arabic turn. **Redeploy** — the live URL is still yesterday's VAD bundle until `make deploy`.

**Orpheus probe (2026-09-21, after terms accepted):** WAV is ffmpeg unsized (`RIFF`/`data` size `0xFFFFFFFF`, LIST/ISFT `Lavf61.7`), PCM s16le mono @ 24 kHz. SDK bytes via `await read()`, not `aread()`. Voice ids lowercase (`noura`). Short 21-char line: ttfb **805 ms**. 232-char / 2-chunk paragraph: ttfb **2 894 ms**, total **4 550 ms**. Details in `docs/measurements/2026-09-21-orpheus-wav.md`.

## Changelog

Draft commits (Omar runs git; agents never commit):

- `fix(audio): resume playback context so a silent turn cannot look like a success`
- `feat(mic): replace VAD endpointing with toggle/hold; barge is a tap`
- `feat(ui): now pane, trail, and accumulating trip dossier`
- `feat(tts): route Arabic to Orpheus behind the existing TTS interface`
- `test(eval): multi-turn conversation cases for origin vs destination`
- `docs: quota-unlock notes, Arabic gate gap, demo script for the new mic`

**2026-09-21:** backend mypy/ruff clean, pytest **306 passed**; frontend tsc/eslint/vite build clean. Eval raw at `eval/results/2026-09-21-gate-eval-raw.txt`.
