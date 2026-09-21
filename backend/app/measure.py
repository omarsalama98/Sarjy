"""python -m app.measure -- turns a capture of `turn_timings` log lines into
a stage-by-stage latency table against the deployment.

`AGENTS.md` §Commands has declared `make measure` since before this block --
this module is what makes that command real. Deliberately NOT a
synthetic-turn harness: `scratch/spikes/block2/deployed_turn.py` already
exists for driving turns; this only aggregates records that already
happened, whichever way they were produced.

    modal app logs sarjy --since 30m --tail 2000 \
        | uv run python -m app.measure --label deployed-baseline

Failure paths come before the happy path they protect, same as everywhere
else in this codebase (I5-I9 below match the block plan's numbering).
"""

import argparse
import json
import math
import statistics
import sys
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from app.pipeline.timings import LOG_PREFIX, TurnTimings

# Fixed order, headline (first_audio_ms) reported last -- the table reads as
# building up to the number that matters, not burying it alphabetically.
# `llm_ms`/`llm_ttft_ms` describe CALL 1 (decide()) only; `tool_ms` sits
# between call 1 and call 2 (the vendor lookup, whichever layer served it);
# `llm2_ms` is call 2 (segments()); `gate_ms` is gate() + spoken_text().
STAGE_ORDER = [
    "endpoint_ms",
    "upload_ms",
    "stt_ms",
    "llm_ttft_ms",
    "llm_ms",
    "tool_ms",
    "llm2_ms",
    "gate_ms",
    "tts_ttfb_ms",
    "tts_total_ms",
    "server_ms",
    "first_audio_ms",
]

# Must agree across every record in one run -- a stage table averaged across
# two configurations is the exact anti-pattern the measure skill names.
CONFIG_FIELDS = [
    "env",
    "redemption_ms",
    "stt_model",
    "llm_model",
    "tts_model",
    "llm_thinking_level",
]

# Resolved from this file's location, not the cwd -- `make measure` and a
# manual `python -m app.measure` can run from different directories.
_MEASUREMENTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "measurements"


def _parse_lines(lines: Iterable[str]) -> tuple[list[TurnTimings], int]:
    """I6: a truncated or interleaved log line, or one whose JSON no longer
    matches TurnTimings, is skipped and counted -- aggregation never crashes
    on one bad line."""
    records: list[TurnTimings] = []
    malformed = 0
    for line in lines:
        idx = line.find(LOG_PREFIX)
        if idx == -1:
            continue  # ordinary server log noise, not a turn_timings line
        payload = line[idx + len(LOG_PREFIX) :]
        try:
            records.append(TurnTimings.model_validate_json(payload))
        except (ValidationError, json.JSONDecodeError):
            malformed += 1
    return records, malformed


def _dedupe(records: list[TurnTimings]) -> list[TurnTimings]:
    """Overlapping `--since` windows would otherwise double-weight a turn
    whose line was captured twice."""
    seen: set[tuple[str, str, int]] = set()
    deduped: list[TurnTimings] = []
    for r in records:
        key = (r.session, r.turn_id, r.turn_index)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def _percentile95(values: list[int]) -> int:
    """Nearest-rank p95: sorted[min(len-1, ceil(0.95*len)-1)]."""
    ordered = sorted(values)
    idx = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[idx]


def _stage_stats(values: list[int]) -> dict[str, int] | None:
    if not values:
        return None
    return {
        "n": len(values),
        "median": round(statistics.median(values)),
        "p95": _percentile95(values),
        "min": min(values),
        "max": max(values),
    }


def _residuals(records: list[TurnTimings]) -> list[int]:
    """residual = first_audio_ms - sum(the sequential legs that make it up).
    Only defined where every leg in the sum is present -- a partial sum
    would be meaningless, not merely imprecise. Real unaccounted time in
    THIS block's strictly-sequential chain: onSpeechEnd -> ensureFresh()
    (which can rotate the socket) -> `start` on the wire, plus the
    server->client audio hop and playback scheduling. Stops being valid
    once Block 4 makes the chain concurrent (the opener overlaps the tool
    call and the gated answer) -- noted in the generated doc, not enforced
    here.
    """
    out = []
    for r in records:
        legs = (r.endpoint_ms, r.upload_ms, r.stt_ms, r.llm_ms, r.tts_ttfb_ms)
        if r.first_audio_ms is None or any(leg is None for leg in legs):
            continue
        out.append(r.first_audio_ms - sum(legs))  # type: ignore[arg-type]  # None-checked above
    return out


def _gate_rejection_rate(records: list[TurnTimings]) -> tuple[int, int] | None:
    """(rejected, total) segments across every turn that ran the gate at
    all -- `segments_ok`/`segments_rejected` are null on a turn where the
    tool never ran and no segment was ever produced isn't possible (call 2
    always runs, D6), but a turn that failed before the gate leaves both
    null, so it's excluded rather than counted as a zero."""
    with_gate = [
        r for r in records if r.segments_ok is not None and r.segments_rejected is not None
    ]
    if not with_gate:
        return None
    rejected = sum(r.segments_rejected for r in with_gate if r.segments_rejected is not None)
    total = rejected + sum(r.segments_ok for r in with_gate if r.segments_ok is not None)
    return rejected, total


def _malformed_line_rate(records: list[TurnTimings]) -> tuple[int, int] | None:
    """malformed lines as a fraction of every line call 2 actually
    produced (kept + rejected + malformed) -- the honest denominator named
    in the block plan, not just "malformed / turns"."""
    with_gate = [r for r in records if r.lines_malformed is not None]
    if not with_gate:
        return None
    malformed = sum(r.lines_malformed for r in with_gate if r.lines_malformed is not None)
    ok = sum(r.segments_ok or 0 for r in with_gate)
    rejected = sum(r.segments_rejected or 0 for r in with_gate)
    return malformed, malformed + ok + rejected


def _rate_row(label: str, rate: tuple[int, int] | None) -> str:
    if rate is None or rate[1] == 0:
        return f"| {label} | 0 | — |"
    numerator, denominator = rate
    pct = round(100 * numerator / denominator, 1)
    return f"| {label} | {denominator} | {numerator}/{denominator} ({pct}%) |"


def _distinct(records: list[TurnTimings], field_name: str) -> list[object]:
    values = {getattr(r, field_name) for r in records}
    return sorted(values, key=lambda v: (v is None, str(v)))


def _format_distinct(values: list[object]) -> str:
    return ", ".join("null" if v is None else str(v) for v in values)


def build_report(
    ok_records: list[TurnTimings],
    *,
    label: str,
    source: str,
    excluded_by_outcome: dict[str, int],
    malformed: int,
) -> str:
    """The one function that turns aggregated numbers into the markdown
    doc -- also printed to stdout as-is, so `make measure`'s console output
    and the file it writes are never two different reports to keep in sync."""
    today = date.today().isoformat()
    lines: list[str] = [f"# {today} — {label} latency measurement", ""]
    lines.append(f"**n:** {len(ok_records)} (ok) · **source:** {source} · **generated:** {today}")
    lines.append("")

    config_line = " · ".join(
        f"{field}={_format_distinct(_distinct(ok_records, field))}" for field in CONFIG_FIELDS
    )
    lines.append(f"**Configuration:** {config_line}")
    lines.append("")

    mixed = [field for field in CONFIG_FIELDS if len(_distinct(ok_records, field)) > 1]
    if mixed:
        lines.append(
            f"**MIXED CONFIGURATION** — {', '.join(mixed)} vary within this run. "
            "The table below still prints, but averaging across configurations "
            "is the anti-pattern this warning exists to stop you quoting."
        )
        lines.append("")

    excluded_bits = [f"{count} {outcome}" for outcome, count in sorted(excluded_by_outcome.items())]
    excluded_text = ", ".join(excluded_bits) if excluded_bits else "none"
    lines.append(
        f"**Excluded from every median:** {excluded_text} · "
        f"**malformed lines skipped:** {malformed}"
    )
    lines.append("")

    lines.append("## Stage table")
    lines.append("")
    lines.append("| stage | n | median | p95 | min | max |")
    lines.append("|---|---|---|---|---|---|")
    for field_name in STAGE_ORDER:
        values = [v for r in ok_records if (v := getattr(r, field_name)) is not None]
        stats = _stage_stats(values)
        display_name = field_name + (" (headline)" if field_name == "first_audio_ms" else "")
        if stats is None:
            lines.append(f"| {display_name} | 0 | — | — | — | — |")
        else:
            lines.append(
                f"| {display_name} | {stats['n']} | {stats['median']} | "
                f"{stats['p95']} | {stats['min']} | {stats['max']} |"
            )
    lines.append("")

    residuals = _residuals(ok_records)
    lines.append("## Residual (first_audio_ms − sum of endpoint/upload/stt/llm/tts_ttfb)")
    lines.append("")
    lines.append("| n | median | p95 | min | max |")
    lines.append("|---|---|---|---|---|")
    residual_stats = _stage_stats(residuals)
    if residual_stats is None:
        lines.append("| 0 | — | — | — | — |")
    else:
        lines.append(
            f"| {residual_stats['n']} | {residual_stats['median']} | "
            f"{residual_stats['p95']} | {residual_stats['min']} | {residual_stats['max']} |"
        )
    lines.append("")
    lines.append(
        "⚠️ Valid only while the chain is strictly sequential. Block A adds "
        "`tool_ms`/`llm2_ms`/`gate_ms` to the chain but keeps it sequential end to "
        "end; once Block C's opener makes STT/LLM/TTS overlap the tool call and "
        "the gated answer, this subtraction stops meaning what it means here."
    )
    lines.append("")

    lines.append("## Grounding gate rates (Block A)")
    lines.append("")
    gate_rate = _gate_rejection_rate(ok_records)
    malformed_rate = _malformed_line_rate(ok_records)
    lines.append("| rate | n (denominator) | value |")
    lines.append("|---|---|---|")
    lines.append(_rate_row("gate-rejection rate", gate_rate))
    lines.append(_rate_row("malformed-NDJSON-line rate", malformed_rate))
    lines.append("")
    hedged_n = sum(1 for r in ok_records if r.hedged)
    hedged_total = sum(1 for r in ok_records if r.hedged is not None)
    lines.append(
        f"`hedged` (a tool result existed and call 2 produced zero sourced/quoted "
        f"segments -- D4, never gate-enforced, scored by hand): {hedged_n}/{hedged_total}."
    )
    lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    lines.append("_to be written by hand_")
    lines.append("")

    return "\n".join(lines)


def _read_input(file_arg: str | None, stdin: TextIO) -> list[str] | None:
    """I5: never block on an interactive terminal. Returns None (caller
    prints usage and exits 2) when there's nothing to read."""
    if file_arg is not None:
        return Path(file_arg).read_text().splitlines()
    if stdin.isatty():
        return None
    return stdin.read().splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.measure",
        description="Aggregate turn_timings log lines into a median/p95 stage table.",
    )
    parser.add_argument("file", nargs="?", default=None, help="log file; omit to read stdin")
    parser.add_argument("--label", default="run", help="used in the output filename and heading")
    parser.add_argument(
        "--redemption", type=int, default=None, help="keep only records at this redemption_ms"
    )
    parser.add_argument(
        "--out", default=None, help="output path; default docs/measurements/{date}-{label}.md"
    )
    args = parser.parse_args(argv)

    raw_lines = _read_input(args.file, sys.stdin)
    if raw_lines is None:
        parser.print_usage(sys.stderr)
        return 2

    records, malformed = _parse_lines(raw_lines)
    records = _dedupe(records)
    if args.redemption is not None:
        records = [r for r in records if r.redemption_ms == args.redemption]

    # I7: zero ok records -- whether because nothing parsed at all, or
    # everything parsed but failed/barged/got filtered out by --redemption --
    # is the same outcome: no document to write, no median to quote.
    ok_records = [r for r in records if r.outcome == "ok"]
    if not ok_records:
        print(f"no turn_timings records found in {len(raw_lines)} lines")
        return 1

    excluded_by_outcome: dict[str, int] = {}
    for r in records:
        if r.outcome != "ok":
            excluded_by_outcome[r.outcome] = excluded_by_outcome.get(r.outcome, 0) + 1

    source = args.file if args.file is not None else "stdin"
    report = build_report(
        ok_records,
        label=args.label,
        source=source,
        excluded_by_outcome=excluded_by_outcome,
        malformed=malformed,
    )
    print(report)

    out_path = (
        Path(args.out)
        if args.out
        else _MEASUREMENTS_DIR / f"{date.today().isoformat()}-{args.label}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"\nwrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
