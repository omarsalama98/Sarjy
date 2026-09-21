"""pcm16_to_wav — the 44-byte RIFF header Groq's API needs, added server-side
so the browser never has to know about WAV.
"""

import wave
from io import BytesIO

from app.pipeline.audio import pcm16_to_wav


def test_header_declares_the_right_format() -> None:
    pcm = b"\x00\x01" * 100  # 100 fake PCM16 samples
    wav_bytes = pcm16_to_wav(pcm, sample_rate=16_000)

    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"

    with wave.open(BytesIO(wav_bytes)) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2  # PCM16
        assert w.getframerate() == 16_000
        assert w.getnframes() == 100


def test_round_trips_the_exact_samples() -> None:
    pcm = bytes(range(0, 200, 2)) * 2  # arbitrary but deterministic bytes
    wav_bytes = pcm16_to_wav(pcm, sample_rate=24_000)

    with wave.open(BytesIO(wav_bytes)) as w:
        assert w.readframes(w.getnframes()) == pcm


def test_empty_pcm_still_produces_a_valid_header() -> None:
    """An empty turn (F8's near-silence case) must not crash the wrapper —
    the empty-transcript check happens after STT, not before."""
    wav_bytes = pcm16_to_wav(b"", sample_rate=16_000)

    with wave.open(BytesIO(wav_bytes)) as w:
        assert w.getnframes() == 0
