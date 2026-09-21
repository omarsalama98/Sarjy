"""chunk_for_orpheus and wav_to_pcm16 -- no network.

The adapter's synthesize() talks to Groq; these two functions are the
whole of the 200-char cap and the WAV-format probe, and they must hold
without a key.
"""

import struct

import pytest

from app.pipeline.audio import pcm16_to_wav
from app.providers.groq_tts import (
    EXPECTED_SAMPLE_RATE,
    MAX_CHARS,
    chunk_for_orpheus,
    wav_to_pcm16,
)


def test_chunker_empty() -> None:
    assert chunk_for_orpheus("") == []


def test_chunker_short_is_one_piece() -> None:
    assert chunk_for_orpheus("hello") == ["hello"]


def test_chunker_never_exceeds_limit_and_never_drops_characters() -> None:
    text = ("Berlin is worth a slower visit. " * 20) + "Go."
    chunks = chunk_for_orpheus(text)
    assert "".join(chunks) == text
    assert all(len(c) <= MAX_CHARS for c in chunks)
    assert len(chunks) > 1


def test_chunker_splits_arabic_and_english_terminators() -> None:
    text = "مرحبا. كيف حالك؟ أنا بخير!"
    chunks = chunk_for_orpheus(text, limit=12)
    assert "".join(chunks) == text
    assert all(len(c) <= 12 for c in chunks)


def test_chunker_hard_splits_a_run_with_no_space() -> None:
    text = "a" * 250
    chunks = chunk_for_orpheus(text, limit=100)
    assert "".join(chunks) == text
    assert chunks == ["a" * 100, "a" * 100, "a" * 50]


def test_chunker_splits_at_last_space_not_mid_word() -> None:
    text = "one two three four five"
    chunks = chunk_for_orpheus(text, limit=10)
    assert "".join(chunks) == text
    assert all(len(c) <= 10 for c in chunks)
    # No chunk should start mid-word after a dropped space — join is exact.
    assert " ".join(c.strip() for c in chunks).split() == text.split()


def test_wav_to_pcm16_accepts_unsized_ffmpeg_data_chunk() -> None:
    """Groq's Orpheus body (2026-09-21): RIFF size 0xFFFFFFFF, a LIST/INFO
    encoder tag, then data size 0xFFFFFFFF. Observed live; not assumed."""
    pcm = b"\x01\x00\x02\x00\x03\x00\x04\x00"
    fmt = struct.pack("<HHIIHH", 1, 1, 24000, 48000, 2, 16)
    list_payload = b"INFOISFT\x0d\x00\x00\x00Lavf61.7.0\x00"
    wav = b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE"
    wav += b"fmt " + struct.pack("<I", 16) + fmt
    wav += b"LIST" + struct.pack("<I", len(list_payload)) + list_payload
    if len(list_payload) % 2:
        wav += b"\x00"
    wav += b"data" + struct.pack("<I", 0xFFFFFFFF) + pcm
    out, rate = wav_to_pcm16(wav)
    assert rate == 24000
    assert out == pcm


def test_wav_to_pcm16_round_trips_our_own_header() -> None:
    pcm = b"\x01\x00\x02\x00\x03\x00"
    wav = pcm16_to_wav(pcm, sample_rate=EXPECTED_SAMPLE_RATE)
    out, rate = wav_to_pcm16(wav)
    assert out == pcm
    assert rate == EXPECTED_SAMPLE_RATE


def test_wav_to_pcm16_rejects_non_riff() -> None:
    with pytest.raises(RuntimeError, match="not RIFF/WAVE"):
        wav_to_pcm16(b"not a wav")


def test_wav_to_pcm16_rejects_wrong_channels() -> None:
    # Minimal WAVE with channels=2, 16-bit PCM, empty data.
    fmt = struct.pack("<HHIIHH", 1, 2, 24000, 24000 * 2 * 2, 4, 16)
    wav = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
    wav += b"fmt " + struct.pack("<I", 16) + fmt
    wav += b"data" + struct.pack("<I", 0)
    with pytest.raises(RuntimeError, match="not mono"):
        wav_to_pcm16(wav)


def test_wav_to_pcm16_rejects_wrong_bits() -> None:
    fmt = struct.pack("<HHIIHH", 1, 1, 24000, 24000 * 1 * 1, 1, 8)
    wav = b"RIFF" + struct.pack("<I", 36) + b"WAVE"
    wav += b"fmt " + struct.pack("<I", 16) + fmt
    wav += b"data" + struct.pack("<I", 0)
    with pytest.raises(RuntimeError, match="not 16-bit"):
        wav_to_pcm16(wav)


def test_voice_id_is_lowercased() -> None:
    from app.providers.groq_tts import GroqOrpheusTTS

    tts = GroqOrpheusTTS(api_key="x", voice="Noura")
    assert tts._voice == "noura"
