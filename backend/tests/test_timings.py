"""TurnTimings and emit() -- the reserved-null contract and the one guarded
call in the whole feature (I1). Aggregation itself is test_measure.py's job.
"""

import json
import logging

import pytest
from pydantic import ValidationError

from app.pipeline.timings import LOG_PREFIX, TurnTimings, emit


def _minimal_record(**overrides: object) -> TurnTimings:
    fields: dict[str, object] = {
        "turn_id": "t-1",
        "session": "abcd1234",
        "connection_n": 1,
        "turn_index": 1,
        "env": "local",
    }
    fields.update(overrides)
    return TurnTimings(**fields)  # type: ignore[arg-type]


def test_reserved_fields_are_emitted_as_null_never_omitted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    record = _minimal_record()

    with caplog.at_level(logging.INFO, logger="sarjy"):
        emit(record)

    lines = [r.message for r in caplog.records if r.message.startswith(LOG_PREFIX)]
    assert len(lines) == 1
    payload = json.loads(lines[0].removeprefix(LOG_PREFIX))

    for reserved in (
        "opener_ready_ms",
        "tts1_ttfb_ms",
        "tool_ms",
        "llm2_ms",
        "gate_ms",
        "answer_gap_ms",
    ):
        assert reserved in payload  # present, not merely absent-and-therefore-falsy
        assert payload[reserved] is None


def test_extra_field_is_rejected() -> None:
    """extra="forbid" -- a typo'd fill must raise at construction time, not
    silently widen the schema measure.py keys off."""
    with pytest.raises(ValidationError):
        TurnTimings(
            turn_id="t-1",
            session="abcd1234",
            connection_n=1,
            turn_index=1,
            env="local",
            not_a_real_field=123,  # type: ignore[call-arg]
        )


def test_i1_emit_swallows_a_raising_serialiser(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A field that won't serialise (or a logging handler blowing up) must
    never propagate out of emit() -- a timing record is diagnostic, never
    load-bearing for the turn it describes."""
    record = _minimal_record()

    def _raise(*args: object, **kwargs: object) -> str:
        raise RuntimeError("serialisation exploded")

    # Patched on the class, not the instance: pydantic's own __setattr__
    # rejects assigning anything that isn't a declared field (which is
    # exactly the guarantee test_extra_field_is_rejected above is proving).
    monkeypatch.setattr(TurnTimings, "model_dump_json", _raise)

    with caplog.at_level(logging.WARNING, logger="sarjy"):
        emit(record)  # must not raise

    assert any("turn_timings emit failed" in r.message for r in caplog.records)
