"""TurnTimings -- one correlated timing record per turn.

Before this, stt_ms/llm_first_text_delta_ms/tts_ttfb_ms were three
uncorrelated log lines nothing tied to a turn, and the two legs the user
actually feels -- endpointing and first audio out -- weren't measured at
all. This is the record that fixes both: opened on `start`, filled as each
stage completes, and printed once (see main.py's _maybe_emit_timings) when
both the server's and the client's halves of the turn are done.

Fields owned by Blocks 4/5/6 (opener, tool, gate, answer gap) are declared
here now and always emitted as `null` -- a record retrofitted after those
land would describe nothing about what Block 2/3 actually built.

Imports pydantic and stdlib only. app.main imports this at module level, and
main.py's own docstring forbids a provider SDK entering that import graph --
see app/providers/base.py's matching note on `LLMReply`.
"""

import logging
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("sarjy")

# The grep handle: `modal app logs sarjy | grep "turn_timings "`. One space,
# then a JSON object -- never JSON embedded earlier in the line, so a plain
# split(LOG_PREFIX, 1) is enough to recover it.
LOG_PREFIX = "turn_timings "


class TurnTimings(BaseModel):
    """extra="forbid" so a typo'd attribute assignment raises at runtime --
    mypy catches the typo first (validate_assignment is off, see the note by
    the fills in turn.py), but a schema that silently accepted a drifted
    field name is worse than one that occasionally raises loudly.

    No field is ever omitted from the emitted JSON (model_dump_json() with
    no exclude_none): measure.py, and every later block, key off a field
    always being present, even if it's null.
    """

    model_config = ConfigDict(extra="forbid")

    # -- identity and configuration -------------------------------------
    turn_id: str
    session: str  # session_id[:8] ONLY -- never the full id (see §Secrets)
    connection_n: int
    turn_index: int  # 1-based per container process; turn 1 is the cold one
    env: str  # "modal" | "local", from SARJY_ENV
    lang: str = "en"  # Block C, Arabic rung 1 -- the StartIn.lang this turn ran with
    stt_model: str | None = None
    llm_model: str | None = None
    tts_model: str | None = None
    llm_thinking_level: str | None = None
    redemption_ms: int | None = None  # unused (was VAD setting); always 0 on user-ended turns

    # -- outcome --------------------------------------------------------
    outcome: Literal["ok", "failed", "barged", "incomplete"] = "incomplete"
    failed_stage: str | None = None  # TurnFailedStage when outcome == "failed"
    flush_reason: Literal["complete", "next_turn", "connection_closed"] = "complete"
    transcript_chars: int | None = None  # length, NOT the text (see §Secrets)
    reply_chars: int | None = None

    # -- client legs (performance.now() deltas; null if the client never reported)
    endpoint_ms: int | None = None  # user-hold duration (was last speech frame -> VAD onSpeechEnd)
    first_audio_ms: int | None = None  # HEADLINE: last speech frame -> first buffer scheduled
    output_latency_ms: int | None = None  # AudioContext.outputLatency, null on Safari

    # -- server legs (time.monotonic() deltas) ---------------------------
    upload_ms: int | None = None  # `start` received -> `end` received
    stt_ms: int | None = None  # around stt.transcribe(), includes the WAV wrap
    llm_ms: int | None = None  # around llm.reply(), request -> full string
    llm_ttft_ms: int | None = None  # to the first delta.type == "text" (see trap 2)
    tts_ttfb_ms: int | None = None  # first pull -> first chunk, INCLUDING the DG connect
    tts_total_ms: int | None = None  # first pull -> last chunk
    server_ms: int | None = None  # `end` received -> first audio byte on the wire

    # `llm_ms`/`llm_ttft_ms` above now describe CALL 1 (decide()) only.
    # `llm2_ms` below describes call 2 (segments()) -- two different calls,
    # never averaged together. Misreading this three weeks from now is the
    # one thing this comment exists to prevent.

    # -- Block A (the deep dive): filled below ---------------------------
    tool_ms: int | None = None  # around tool.lookup() -- whichever layer served it
    llm2_ms: int | None = None  # call 2 (segments()), full drain
    gate_ms: int | None = None  # gate() + spoken_text()
    tool_layer: str | None = None  # live | cache | map | csv | null (no tool ran)
    segments_ok: int | None = None
    segments_rejected: int | None = None
    lines_malformed: int | None = None
    hedged: bool | None = None  # a tool result existed and 0 sourced AND 0 quoted came back (D4)

    # -- RESERVED. Emitted as null until Block C. Never omit one. ---------
    opener_ready_ms: int | None = None  # Block C -- the opener is cut here (see the block plan)
    tts1_ttfb_ms: int | None = None  # Block C -- the OPENER's TTS
    answer_gap_ms: int | None = None  # Block C

    # -- Block B (memory) -------------------------------------------------
    # `memory_extracted`/`memory_dropped` are filled by a task that OUTLIVES
    # this turn (D4 -- extraction fires after dispatch, never awaited before
    # `state: idle`). They may land on the record AFTER _maybe_emit_timings
    # has already printed it -- accepted, not a bug: extraction fills the
    # NEXT record instead, or none. The emit is never delayed to wait for
    # it; that would put a third LLM call back on the measured latency path,
    # which is the one thing D4 exists to prevent.
    memory_facts: int | None = None  # facts rendered into <known_about_user> this turn
    memory_extracted: int | None = None  # facts accepted by validate_candidate
    memory_dropped: int | None = None  # candidates rejected
    memory_persisted: bool | None = None  # the durable write succeeded


def elapsed_ms(t0: float) -> int:
    """time.monotonic() delta, rounded to ms. Never a client timestamp minus
    a server one -- see protocol.py's docstring on `ts_ms`."""
    return round((time.monotonic() - t0) * 1000)


def emit(record: TurnTimings) -> None:
    """One line, never raises. A timing record must never break a turn --
    the only guarded call in this whole feature, because every fill is a
    plain attribute assignment that mypy already validated at build time."""
    try:
        logger.info("%s%s", LOG_PREFIX, record.model_dump_json())
    except Exception:
        logger.warning("turn_timings emit failed", exc_info=True)
