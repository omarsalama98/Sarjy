"""Groq Orpheus Arabic TTS — parked, not on the demo path.

Probed 2026-09-21 (docs/measurements/2026-09-21-orpheus-wav.md): the body
is ffmpeg unsized WAV, PCM s16le mono @ 24 kHz, voice ids lowercase.
Not wired into `get_tts()` because the gate's NUMBER_WORDS / place-name
scan is English-only and Orpheus is batch + 200 chars/request. Shipping
a language chip that spoke ungated Arabic would be a half-feature.

`language` is accepted and ignored: this adapter *is* the Arabic branch.
"""

from __future__ import annotations

import inspect
import struct
from collections.abc import AsyncIterator
from typing import Literal

from groq import AsyncGroq

MODEL = "canopylabs/orpheus-arabic-saudi"
MAX_CHARS = 200  # Groq's hard per-request cap, not a tuning knob
EXPECTED_SAMPLE_RATE: Literal[24000] = 24_000

# Same bounds GroqSTT uses -- never the SDK default on a voice path.
MAX_RETRIES = 1
TIMEOUT_S = 8.0

# Sentence boundaries for Arabic and English. Keep the terminator on the
# sentence so joining chunks reconstructs the original string exactly.
_TERMINATORS = ".؟!۔؛!\n"


def chunk_for_orpheus(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Split `text` into pieces of at most `limit` characters.

    Packs greedily on sentence terminators first. A single sentence longer
    than `limit` splits at the last space at or before `limit`; a run with
    no space hard-splits at `limit`. Never returns a chunk longer than
    `limit` and never drops a character.
    """
    if not text:
        return []
    chunks: list[str] = []
    current = ""
    for sentence in _split_sentences(text):
        for piece in _split_oversize(sentence, limit):
            candidate = current + piece
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    assert all(len(c) <= limit for c in chunks), [len(c) for c in chunks]
    assert "".join(chunks) == text
    return chunks


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if ch in _TERMINATORS:
            parts.append("".join(buf))
            buf = []
    if buf:
        parts.append("".join(buf))
    return parts


def _split_oversize(s: str, limit: int) -> list[str]:
    if len(s) <= limit:
        return [s]
    out: list[str] = []
    rest = s
    while len(rest) > limit:
        window = rest[:limit]
        sp = window.rfind(" ")
        if sp <= 0:
            out.append(rest[:limit])
            rest = rest[limit:]
        else:
            # Keep the space on the left piece so join reconstructs `s`.
            out.append(rest[: sp + 1])
            rest = rest[sp + 1 :]
    if rest:
        out.append(rest)
    return out


def wav_to_pcm16(wav: bytes) -> tuple[bytes, int]:
    """Strip a RIFF/WAVE body to raw s16le PCM and the header's sample rate.

    Raises RuntimeError on a non-RIFF body, non-PCM format, channels ≠ 1,
    or bits-per-sample ≠ 16 — each with the observed value in the message.
    Never guess a rate: streaming the wrong one plays as pitch-shifted noise.
    """
    if len(wav) < 12 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise RuntimeError(f"Orpheus body is not RIFF/WAVE (got {wav[:12]!r})")

    offset = 12
    fmt: bytes | None = None
    data: bytes | None = None
    while offset + 8 <= len(wav):
        cid = wav[offset : offset + 4]
        size = struct.unpack_from("<I", wav, offset + 4)[0]
        start = offset + 8
        end = start + size
        if end > len(wav):
            # Groq (ffmpeg / Lavf) writes unsized WAV: RIFF chunk size and
            # the data chunk size are 0xFFFFFFFF. The PCM is everything
            # after the data header. Treat only that sentinel as truncated;
            # any other overrun is a corrupt body.
            if cid == b"data" and size == 0xFFFFFFFF:
                data = wav[start:]
                break
            raise RuntimeError(f"Orpheus WAV chunk {cid!r} overruns the body")
        payload = wav[start:end]
        if cid == b"fmt ":
            fmt = payload
        elif cid == b"data":
            data = payload
        offset = end + (size % 2)  # word-align
    if fmt is None or len(fmt) < 16:
        raise RuntimeError("Orpheus WAV has no fmt chunk")
    if data is None:
        raise RuntimeError("Orpheus WAV has no data chunk")

    audio_format, channels, sample_rate, _byte_rate, _block, bits = struct.unpack_from(
        "<HHIIHH", fmt, 0
    )
    if audio_format != 1:
        raise RuntimeError(f"Orpheus WAV is not PCM (format={audio_format})")
    if channels != 1:
        raise RuntimeError(f"Orpheus WAV is not mono (channels={channels})")
    if bits != 16:
        raise RuntimeError(f"Orpheus WAV is not 16-bit (bits={bits})")
    return data, sample_rate


class GroqOrpheusTTS:
    """Batch WAV → PCM s16le. Sequential requests, one per 200-char chunk."""

    model = MODEL

    def __init__(self, api_key: str, model: str = MODEL, voice: str = "noura") -> None:
        # noura: female Saudi voice, matching Aura-2 Thalia rather than
        # mixing genders across the English/Arabic boundary. Groq's API
        # wants the lowercase id (`noura`), not the title-case display name.
        self.model = model
        self._voice = voice.lower()
        self._client = AsyncGroq(api_key=api_key, max_retries=MAX_RETRIES, timeout=TIMEOUT_S)

    async def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        # `language` is the turn's lang, accepted so this satisfies TTS;
        # this adapter is only ever selected for Arabic.
        del language
        first = True
        for chunk in chunk_for_orpheus(text):
            response = await self._client.audio.speech.create(
                model=self.model,
                voice=self._voice,
                input=chunk,
                response_format="wav",
                sample_rate=EXPECTED_SAMPLE_RATE,
            )
            wav = await _speech_bytes(response)
            pcm, rate = wav_to_pcm16(wav)
            if first and rate != EXPECTED_SAMPLE_RATE:
                raise RuntimeError(
                    f"Orpheus sample rate is {rate} Hz, expected {EXPECTED_SAMPLE_RATE} Hz"
                )
            first = False
            if pcm:
                yield pcm


async def _speech_bytes(response: object) -> bytes:
    """The groq SDK's speech.create return type has shifted across minor
    versions (bytes, .read(), .aread(), .content). Normalize here so a
    SDK bump is one function, not a silent empty yield."""
    if isinstance(response, (bytes, bytearray)):
        return bytes(response)
    aread = getattr(response, "aread", None)
    if callable(aread):
        data = aread()
        payload = await data if inspect.isawaitable(data) else data
        return bytes(payload)
    read = getattr(response, "read", None)
    if callable(read):
        data = read()
        payload = await data if inspect.isawaitable(data) else data
        return bytes(payload)
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    raise RuntimeError(f"Orpheus speech.create returned {type(response).__name__}, not bytes")
