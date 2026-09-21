"""Groq Whisper adapter -- batch transcription.

Batch, not streaming: the turn is already endpointed client-side (the user
taps or releases the mic) before this is ever called, so there is nothing
to gain from a streaming API here (TDD.md §The batch-STT constraint).
"""

from groq import AsyncGroq

from app.pipeline.audio import pcm16_to_wav

STT_SAMPLE_RATE = 16_000
MODEL = "whisper-large-v3-turbo"

# The SDK default is 2 -- overridden per TDD.md §Provider traps: a silent
# 60 s backoff loop on a voice call is worse than a fast, visible failure
# (F9 turns this into "my transcription service didn't answer" in one try).
MAX_RETRIES = 1
TIMEOUT_S = 8.0


class GroqSTT:
    model = MODEL

    def __init__(self, api_key: str) -> None:
        self._client = AsyncGroq(api_key=api_key, max_retries=MAX_RETRIES, timeout=TIMEOUT_S)

    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str:
        # Whisper's API needs a container, not raw PCM -- pcm16_to_wav adds
        # the 44-byte RIFF header server-side so the browser never has to
        # know about WAV.
        wav_bytes = pcm16_to_wav(pcm16, sample_rate=STT_SAMPLE_RATE)

        # stt_ms used to be logged here with nothing to correlate it to a
        # turn -- run_turn() now times this call at the call site, into that
        # turn's TurnTimings, instead.
        result = await self._client.audio.transcriptions.create(
            model=MODEL,
            file=("turn.wav", wav_bytes, "audio/wav"),
            response_format="json",
            temperature=0,
            language=language if language is not None else "en",
        )

        return result.text
