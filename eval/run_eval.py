#!/usr/bin/env python3
"""Replays eval/cases/cases.jsonl through the REAL pipeline -- a real
GeminiLLM (decide() + segments()), the real gate -- with a FakeVisaTool
standing in for the network (Invariant 3's whole point: the vendor is the
only thing swapped). Zero RapidAPI requests, ever: FakeVisaTool never
touches the network, and it is loaded from `eval/fixtures/*.json`, which
were either fetched once by fetch_reference.py or hand-constructed and
labelled as such (see each fixture's own `_provenance` field).

This DOES spend Gemini API calls -- a small, non-scarce, daily-refreshing
quota, unlike the 120-total-ever RapidAPI budget this project is careful
about everywhere else. Paced at one case per ~4s (Open Question #4: Gemini's
free-tier RPD is unpublished) and resumable -- a 429 mid-run costs one case,
not the whole run.

Usage:
    cd backend && uv run python ../eval/run_eval.py --out ../eval/results/
"""

import argparse
import asyncio
import json
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.pipeline.protocol import (  # noqa: E402
    FactCardOut,
    ReplyOut,
    SegmentsOut,
    TranscriptOut,
    TurnFailedOut,
)
from app.pipeline.timings import TurnTimings  # noqa: E402
from app.pipeline.turn import run_turn  # noqa: E402
from app.providers.base import STT, TTS  # noqa: E402
from app.tools.fake import FakeVisaTool, result_from_live_body  # noqa: E402

CASES_PATH = _EVAL_DIR / "cases" / "cases.jsonl"
FIXTURES_DIR = _EVAL_DIR / "fixtures"

# Open Question #4 -- Gemini's free-tier RPD is unpublished. 2 calls/case
# (decide + segments) at 12 cases max is 24 calls; this spacing is cheap
# insurance against a burst-rate 429, not a measured requirement.
PACE_S = 4.0


class _FixedSTT:
    """Returns the case's question verbatim -- no real transcription is
    involved in this eval; the "speech" leg is not what's being measured."""

    model = "eval-fixed"

    def __init__(self, text: str) -> None:
        self._text = text

    async def transcribe(self, pcm16: bytes, *, language: str | None = None) -> str:
        return self._text


class _SilentTTS:
    """Yields one placeholder chunk and stops -- no real audio is generated
    or judged in this eval, but run_turn() treats ZERO chunks as an F11-style
    TTS failure (correctly, for the real pipeline), which would mask an
    otherwise-successful turn's segments here. One harmless chunk keeps the
    turn's own outcome (ok/failed) about the GATE, not about a fake TTS."""

    model = "eval-silent"

    async def synthesize(self, text: str, *, language: str | None = None) -> AsyncIterator[bytes]:
        yield b"\x00\x00"


@dataclass
class CaseResult:
    case: dict[str, Any]
    transcript: str | None = None
    spoken: str | None = None
    segments: list[dict[str, Any]] = field(default_factory=list)
    hedged: bool | None = None
    failed_stage: str | None = None
    failed_message: str | None = None
    fact_card_covered: bool | None = None
    timings: TurnTimings | None = None


def _load_cases() -> list[dict[str, Any]]:
    cases = []
    with CASES_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


# FakeVisaTool does an EXACT (passport, destination) match -- unlike the
# real TravelBuddyTool, it has no resolve_code() alias step (that's tested
# separately, in test_normalise.py/test_vendor.py). The live model is free
# to pass either an ISO code or a country name (VISA_TOOL's own
# description invites both), and it is NOT deterministic about which one it
# picks turn to turn -- discovered running this eval, not assumed. Register
# the fixture under both forms so a flaky no_coverage never comes from the
# harness rather than the pipeline.
_COUNTRY_NAMES = {
    "SA": "Saudi Arabia", "JP": "Japan", "BH": "Bahrain", "NR": "Nauru", "TV": "Tuvalu"
}


def _tool_for_case(case: dict[str, Any]) -> FakeVisaTool:
    tool = FakeVisaTool(force_reason=case.get("force_reason"))
    fixture_name = case.get("fixture")
    if fixture_name:
        body = json.loads((FIXTURES_DIR / fixture_name).read_text())
        result = result_from_live_body(body, retrieved="2026-09-20T09:00:00Z", layer="live")
        passport, destination = case["passport"], case["destination"]
        for p in {passport, _COUNTRY_NAMES.get(passport, passport)}:
            for d in {destination, _COUNTRY_NAMES.get(destination, destination)}:
                tool.add(p, d, result)
    return tool


async def _run_one(case: dict[str, Any], get_llm: Any) -> CaseResult:
    result = CaseResult(case=case)
    tool = _tool_for_case(case)
    timings = TurnTimings(
        turn_id=case["id"], session="eval0000", connection_n=1, turn_index=1, env="eval"
    )

    def get_stt() -> STT:
        return _FixedSTT(case["question"])

    def get_tts() -> TTS:
        return _SilentTTS()

    def get_tool() -> FakeVisaTool:
        return tool

    async for item in run_turn(
        turn_id=case["id"],
        pcm16=b"\x00\x00" * 100,  # never read -- _FixedSTT ignores it
        history=[],
        next_seq=lambda: 0,
        now_ms=lambda: 0,
        get_stt=get_stt,
        get_llm=get_llm,
        get_tts=get_tts,
        get_tool=get_tool,
        timings=timings,
    ):
        if isinstance(item, TranscriptOut):
            result.transcript = item.text
        elif isinstance(item, SegmentsOut):
            result.spoken = item.spoken
            result.hedged = item.hedged
            result.segments = [s.model_dump() for s in item.segments]
        elif isinstance(item, ReplyOut):
            pass  # equals SegmentsOut.spoken by contract -- not re-recorded
        elif isinstance(item, TurnFailedOut):
            result.failed_stage = item.stage
            result.failed_message = item.message
        elif isinstance(item, FactCardOut):
            result.fact_card_covered = item.covered
        # AudioStartOut/AudioEndOut/bytes: _SilentTTS never yields any, so
        # these never arrive -- nothing to record.

    result.timings = timings
    return result


async def _run_all(cases: list[dict[str, Any]]) -> list[CaseResult]:
    from app.providers import factory

    results: list[CaseResult] = []
    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] {case['id']} ({case['category']})...", file=sys.stderr)
        r = await _run_one(case, factory.get_llm)
        results.append(r)
        if i < len(cases) - 1:
            await asyncio.sleep(PACE_S)
    return results


def _format_results(results: list[CaseResult]) -> str:
    lines = []
    for r in results:
        lines.append(f"## {r.case['id']} ({r.case['category']})")
        lines.append(f"question: {r.case['question']}")
        lines.append(f"pass_bar: {r.case['pass_bar']}")
        lines.append(f"label_written_first: {r.case['label_written_first']}")
        if r.failed_stage:
            lines.append(f"turn_failed: stage={r.failed_stage} message={r.failed_message!r}")
        if r.spoken is not None:
            lines.append(f"spoken: {r.spoken!r}")
            lines.append(f"hedged: {r.hedged}")
            for s in r.segments:
                reason = s["reason"]
                lines.append(f"  - {s['kind']} ok={s['ok']} reason={reason} text={s['text']!r}")
        if r.fact_card_covered is not None:
            lines.append(f"fact_card.covered: {r.fact_card_covered}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(_EVAL_DIR / "results"))
    args = parser.parse_args(argv)

    cases = _load_cases()
    t0 = time.monotonic()
    results = asyncio.run(_run_all(cases))
    print(f"ran {len(results)} cases in {time.monotonic() - t0:.1f}s", file=sys.stderr)

    raw = _format_results(results)
    print(raw)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"{date.today().isoformat()}-gate-eval-raw.txt"
    raw_path.write_text(raw)
    print(f"wrote raw output to {raw_path}", file=sys.stderr)
    print(
        "NOTE: this raw output is the evidence; the scored table in "
        "<date>-gate-eval.md is written BY HAND from it, per the eval's "
        "own hand-scoring methodology (CUT-DECISION.md).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
