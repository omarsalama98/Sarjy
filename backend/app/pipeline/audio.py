"""Raw PCM <-> WAV. The one piece of audio format knowledge the browser is
kept out of: the client sends bare PCM16 frames, and this module wraps them
in the 44-byte RIFF header Groq's transcription API needs a *container* to
parse. Never generate a WAV client-side — that would mean shipping this same
logic twice, in two languages, with two chances to get the header wrong.
"""

import struct

BYTES_PER_SAMPLE = 2  # PCM16
CHANNELS = 1


def pcm16_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap raw little-endian PCM16 mono samples in a canonical 44-byte WAV
    header. No compression, no metadata chunks — the minimum a decoder needs.
    """
    byte_rate = sample_rate * CHANNELS * BYTES_PER_SAMPLE
    block_align = CHANNELS * BYTES_PER_SAMPLE
    data_size = len(pcm)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,  # RIFF chunk size: everything after this field
        b"WAVE",
        b"fmt ",
        16,  # fmt chunk size (PCM)
        1,  # audio format: 1 = PCM
        CHANNELS,
        sample_rate,
        byte_rate,
        block_align,
        BYTES_PER_SAMPLE * 8,  # bits per sample
        b"data",
        data_size,
    )
    return header + pcm
