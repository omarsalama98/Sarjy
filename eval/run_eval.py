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

# Open Question #4 -- Gemini's free-tier RPD is unpublished. 2 calls/turn
# (decide + segments). 8 single-turn + 5 two-turn cases ≈ 36 calls; this
# spacing is cheap insurance against a burst-rate 429, not a measured requirement.
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
class TurnSnap:
    question: str
    transcript: str | None = None
    spoken: str | None = None
    segments: list[dict[str, Any]] = field(default_factory=list)
    hedged: bool | None = None
    failed_stage: str | None = None
    failed_message: str | None = None
    fact_card_covered: bool | None = None


@dataclass
class CaseResult:
    case: dict[str, Any]
    turns: list[TurnSnap] = field(default_factory=list)
    timings: TurnTimings | None = None

    @property
    def spoken(self) -> str | None:
        return self.turns[-1].spoken if self.turns else None

    @property
    def segments(self) -> list[dict[str, Any]]:
        return self.turns[-1].segments if self.turns else []

    @property
    def hedged(self) -> bool | None:
        return self.turns[-1].hedged if self.turns else None

    @property
    def failed_stage(self) -> str | None:
        return self.turns[-1].failed_stage if self.turns else None

    @property
    def failed_message(self) -> str | None:
        return self.turns[-1].failed_message if self.turns else None

    @property
    def fact_card_covered(self) -> bool | None:
        return self.turns[-1].fact_card_covered if self.turns else None

    @property
    def transcript(self) -> str | None:
        return self.turns[-1].transcript if self.turns else None


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
    "SA": "Saudi Arabia",
    "JP": "Japan",
    "BH": "Bahrain",
    "NR": "Nauru",
    "TV": "Tuvalu",
    "EG": "Egypt",
    "DE": "Germany",
}


def _turns_spec(case: dict[str, Any]) -> list[dict[str, Any]]:
    """A multi-turn case carries `turns: [{question, ...}]`. A single-turn
    case keeps `question` at the top level so the original 8 cases run
    unchanged."""
    if "turns" in case:
        return list(case["turns"])
    return [case]


def _register_fixture(tool: FakeVisaTool, spec: dict[str, Any]) -> None:
    fixture_name = spec.get("fixture")
    passport, destination = spec.get("passport"), spec.get("destination")
    if not fixture_name or not passport or not destination:
        return
    body = json.loads((FIXTURES_DIR / fixture_name).read_text())
    result = result_from_live_body(body, retrieved="2026-09-20T09:00:00Z", layer="live")
    for p in {passport, _COUNTRY_NAMES.get(passport, passport)}:
        for d in {destination, _COUNTRY_NAMES.get(destination, destination)}:
            tool.add(p, d, result)


def _tool_for_case(case: dict[str, Any]) -> FakeVisaTool:
    tool = FakeVisaTool(force_reason=case.get("force_reason"))
    _register_fixture(tool, case)
    for turn in _turns_spec(case):
        _register_fixture(tool, turn)
    return tool


async def _run_turn(
    *,
    case_id: str,
    turn_index: int,
    question: str,
    history: list[tuple[str, str]],
    memory_block: str,
    tool: FakeVisaTool,
    get_llm: Any,
) -> tuple[TurnSnap, TurnTimings]:
    snap = TurnSnap(question=question)
    timings = TurnTimings(
        turn_id=f"{case_id}-t{turn_index}",
        session="eval0000",
        connection_n=1,
        turn_index=turn_index,
        env="eval",
    )

    def get_stt() -> STT:
        return _FixedSTT(question)

    def get_tts() -> TTS:
        return _SilentTTS()

    def get_tool() -> FakeVisaTool:
        return tool

    async for item in run_turn(
        turn_id=f"{case_id}-t{turn_index}",
        pcm16=b"\x00\x00" * 100,
        history=history,
        next_seq=lambda: 0,
        now_ms=lambda: 0,
        get_stt=get_stt,
        get_llm=get_llm,
        get_tts=get_tts,
        get_tool=get_tool,
        timings=timings,
        memory_block=memory_block,
    ):
        if isinstance(item, TranscriptOut):
            snap.transcript = item.text
        elif isinstance(item, SegmentsOut):
            snap.spoken = item.spoken
            snap.hedged = item.hedged
            snap.segments = [s.model_dump() for s in item.segments]
        elif isinstance(item, ReplyOut):
            if snap.spoken is None:
                snap.spoken = item.text
        elif isinstance(item, TurnFailedOut):
            snap.failed_stage = item.stage
            snap.failed_message = item.message
        elif isinstance(item, FactCardOut):
            snap.fact_card_covered = item.covered
    return snap, timings


async def _run_one(case: dict[str, Any], get_llm: Any) -> CaseResult:
    result = CaseResult(case=case)
    tool = _tool_for_case(case)
    history: list[tuple[str, str]] = []
    last_timings: TurnTimings | None = None

    for i, spec in enumerate(_turns_spec(case), start=1):
        for injected in spec.get("history_inject") or []:
            history.append((injected[0], injected[1]))
        memory_block = spec.get("memory_block") or case.get("memory_block") or ""
        snap, timings = await _run_turn(
            case_id=case["id"],
            turn_index=i,
            question=spec["question"],
            history=history,
            memory_block=memory_block,
            tool=tool,
            get_llm=get_llm,
        )
        result.turns.append(snap)
        last_timings = timings
        if snap.transcript and snap.spoken:
            history.append((snap.transcript, snap.spoken))
        if i < len(_turns_spec(case)):
            await asyncio.sleep(PACE_S)

    result.timings = last_timings
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
        if "turns" in r.case:
            lines.append(f"turns: {len(r.turns)}")
        else:
            lines.append(f"question: {r.case['question']}")
        lines.append(f"pass_bar: {r.case['pass_bar']}")
        lines.append(f"label_written_first: {r.case['label_written_first']}")
        for i, snap in enumerate(r.turns, start=1):
            if len(r.turns) > 1:
                lines.append(f"### turn {i}")
                lines.append(f"question: {snap.question}")
            if snap.failed_stage:
                lines.append(f"turn_failed: stage={snap.failed_stage} message={snap.failed_message!r}")
            if snap.spoken is not None:
                lines.append(f"spoken: {snap.spoken!r}")
                lines.append(f"hedged: {snap.hedged}")
                for s in snap.segments:
                    reason = s["reason"]
                    lines.append(f"  - {s['kind']} ok={s['ok']} reason={reason} text={s['text']!r}")
            if snap.fact_card_covered is not None:
                lines.append(f"fact_card.covered: {snap.fact_card_covered}")
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
