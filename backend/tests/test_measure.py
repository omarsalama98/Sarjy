"""app.measure -- aggregation, de-dupe, and the failure paths I5/I6/I7/I9.
Reused pydantic model for parsing (TurnTimings.model_validate_json) is the
point: a drifted schema is caught here, not silently averaged past."""

import io
from pathlib import Path

import pytest

from app.measure import (
    _dedupe,
    _gate_rejection_rate,
    _malformed_line_rate,
    _parse_lines,
    _percentile95,
    build_report,
    main,
)
from app.pipeline.timings import LOG_PREFIX, TurnTimings

BASE: dict[str, object] = {
    "session": "abcd1234",
    "connection_n": 1,
    "env": "modal",
    "stt_model": "whisper-large-v3-turbo",
    "llm_model": "gemini-3.5-flash-lite",
    "tts_model": "aura-2-thalia-en",
    "llm_thinking_level": "minimal",
    "redemption_ms": 600,
    "outcome": "ok",
    "endpoint_ms": 580,
    "first_audio_ms": 1830,
    "upload_ms": 100,
    "stt_ms": 300,
    "llm_ms": 200,
    "llm_ttft_ms": 30,
    "tts_ttfb_ms": 90,
    "tts_total_ms": 500,
    "server_ms": 1200,
}


def _record(**overrides: object) -> TurnTimings:
    fields: dict[str, object] = dict(BASE, turn_id="t-1", turn_index=1)
    fields.update(overrides)
    return TurnTimings(**fields)  # type: ignore[arg-type]


def _line(record: TurnTimings) -> str:
    return LOG_PREFIX + record.model_dump_json()


def test_percentile95_nearest_rank() -> None:
    # 20 values 1..20 -- ceil(0.95*20)-1 = 18 (0-indexed) -> the 19th value.
    values = list(range(1, 21))
    assert _percentile95(values) == 19


def test_i6_malformed_lines_are_skipped_and_counted() -> None:
    good = _line(_record())
    truncated = 'turn_timings {"turn_id":"t-broken", "session":"abcd1234"'
    schema_violation = LOG_PREFIX + (
        '{"turn_id":"t-x","session":"abcd1234","connection_n":1,'
        '"turn_index":1,"env":"modal","surprise":true}'
    )
    unrelated_noise = "2026-09-20 INFO sarjy: some other log line"

    records, malformed = _parse_lines([good, truncated, schema_violation, unrelated_noise])

    assert len(records) == 1
    assert malformed == 2  # the two turn_timings-prefixed lines that don't parse
    # unrelated_noise doesn't even contain the prefix -- not counted as malformed


def test_dedupe_collapses_the_same_turn_seen_twice() -> None:
    r = _record()
    deduped = _dedupe([r, r])
    assert len(deduped) == 1


def test_dedupe_keeps_different_turns() -> None:
    r1 = _record(turn_id="t-1", turn_index=1)
    r2 = _record(turn_id="t-2", turn_index=2)
    assert len(_dedupe([r1, r2])) == 2


def test_median_is_correct_in_the_generated_table() -> None:
    records = [
        _record(turn_id=f"t-{i}", turn_index=i, stt_ms=v) for i, v in enumerate([100, 300, 200], 1)
    ]
    report = build_report(
        records, label="test", source="stdin", excluded_by_outcome={}, malformed=0
    )
    assert "| stt_ms | 3 | 200 |" in report


def test_i4_failed_turns_are_excluded_from_every_median(tmp_path: Path) -> None:
    ok = _record(turn_id="t-1", turn_index=1)
    failed = _record(
        turn_id="t-2",
        turn_index=2,
        outcome="failed",
        failed_stage="stt",
        stt_ms=None,
        llm_ms=None,
        llm_ttft_ms=None,
        tts_ttfb_ms=None,
        tts_total_ms=None,
        server_ms=None,
        first_audio_ms=None,
        endpoint_ms=None,
    )
    path = tmp_path / "in.log"
    path.write_text(_line(ok) + "\n" + _line(failed) + "\n")

    code = main(["--label", "t", "--out", str(tmp_path / "out.md"), str(path)])

    assert code == 0
    report = (tmp_path / "out.md").read_text()
    assert "**n:** 1 (ok)" in report
    assert "1 failed" in report


def test_i9_mixed_configuration_warns_but_still_prints_the_table() -> None:
    r1 = _record(turn_id="t-1", turn_index=1, redemption_ms=600)
    r2 = _record(turn_id="t-2", turn_index=2, redemption_ms=800)
    report = build_report([r1, r2], label="t", source="stdin", excluded_by_outcome={}, malformed=0)

    assert "MIXED CONFIGURATION" in report
    assert "redemption_ms" in report.split("MIXED CONFIGURATION")[1].split("\n")[0]
    assert "| endpoint_ms |" in report  # the table still printed


def test_i7_zero_ok_records_exits_1_and_writes_no_document(tmp_path: Path) -> None:
    failed = _record(outcome="failed", failed_stage="llm")
    path = tmp_path / "in.log"
    path.write_text(_line(failed) + "\n")
    out_path = tmp_path / "out.md"

    code = main(["--label", "t", "--out", str(out_path), str(path)])

    assert code == 1
    assert not out_path.exists()


def test_i7_no_records_at_all_exits_1(tmp_path: Path) -> None:
    path = tmp_path / "empty.log"
    path.write_text("nothing here\n")

    code = main(["--out", str(tmp_path / "out.md"), str(path)])

    assert code == 1


def test_i5_stdin_attached_to_a_tty_prints_usage_and_exits_2_without_blocking(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_stdin = io.StringIO("")
    monkeypatch.setattr(fake_stdin, "isatty", lambda: True)
    monkeypatch.setattr("sys.stdin", fake_stdin)

    code = main([])

    assert code == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_redemption_filter_keeps_only_matching_records() -> None:
    r1 = _record(turn_id="t-1", turn_index=1, redemption_ms=600)
    r2 = _record(turn_id="t-2", turn_index=2, redemption_ms=800)
    records, _ = _parse_lines([_line(r1), _line(r2)])
    filtered = [r for r in records if r.redemption_ms == 800]
    assert len(filtered) == 1
    assert filtered[0].turn_id == "t-2"


def test_gate_rejection_rate_sums_across_turns() -> None:
    r1 = _record(turn_id="t-1", turn_index=1, segments_ok=2, segments_rejected=0, lines_malformed=0)
    r2 = _record(turn_id="t-2", turn_index=2, segments_ok=1, segments_rejected=1, lines_malformed=0)
    assert _gate_rejection_rate([r1, r2]) == (1, 4)  # 1 rejected out of 4 total segments


def test_gate_rejection_rate_none_when_no_turn_ran_the_gate() -> None:
    r1 = _record(turn_id="t-1", turn_index=1, segments_ok=None, segments_rejected=None)
    assert _gate_rejection_rate([r1]) is None


def test_malformed_line_rate_counts_against_every_line_produced() -> None:
    r1 = _record(turn_id="t-1", turn_index=1, segments_ok=1, segments_rejected=0, lines_malformed=1)
    assert _malformed_line_rate([r1]) == (1, 2)  # 1 malformed out of 2 total lines


def test_build_report_includes_the_gate_rates_section() -> None:
    r1 = _record(turn_id="t-1", turn_index=1, segments_ok=2, segments_rejected=1, lines_malformed=0)
    report = build_report([r1], label="t", source="x", excluded_by_outcome={}, malformed=0)
    assert "## Grounding gate rates (Block A)" in report
    assert "gate-rejection rate" in report
    assert "malformed-NDJSON-line rate" in report


def test_reserved_fields_survive_the_round_trip(tmp_path: Path) -> None:
    """measure.py parses via TurnTimings itself -- a reserved field staying
    null through the whole pipeline is a property of reusing the model, not
    something this module has to special-case."""
    r = _record()
    path = tmp_path / "in.log"
    path.write_text(_line(r) + "\n")

    records, malformed = _parse_lines(path.read_text().splitlines())

    assert malformed == 0
    assert records[0].gate_ms is None
    assert records[0].tool_ms is None
