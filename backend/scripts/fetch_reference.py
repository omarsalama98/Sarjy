#!/usr/bin/env python3
"""The ONLY code in this repo allowed to spend Travel Buddy quota (D9).

120 requests, total, ever -- not per day, not per month. Every mutating
subcommand below prints the ledger before and after, and refuses to run
unless `--spend N` matches exactly how many live requests it is about to
make. Nothing in `app/` calls the vendor outside `TravelBuddyTool.lookup()`
(the per-turn path, cache-aware); nothing in `tests/` or `eval/` reaches the
network at all. This script exists for the handful of one-time or
periodic fetches those two paths deliberately never do themselves.

Usage:
    uv run python -m scripts.fetch_reference --status

    uv run python -m scripts.fetch_reference check SA JP --spend 1 \\
        --out ../data/reference/visa_reqs_SA_JP.json

    uv run python -m scripts.fetch_reference map SA --spend 1 \\
        --out ../data/reference/visa_map_SA.json

    uv run python -m scripts.fetch_reference batch --spend 6 \\
        --pairs SA:JP,SA:BH,SA:GB,AE:JP,SA:EG,SA:US \\
        --out-dir ../eval/fixtures

`--status` never spends and needs no `--spend` flag -- it only reads the
ledger (seeded from `QUOTA_SPENT_SEED`, see below) and the reference
directory's own file listing.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `from app...` works under -m

from app.config import load_settings  # noqa: E402
from app.tools.quota import QuotaLedger  # noqa: E402

logging.basicConfig(level="INFO", format="%(message)s")
logger = logging.getLogger("fetch_reference")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_DIR = _REPO_ROOT / "data" / "reference"

# Upstream correction #1 (block plan): the real spent-so-far count lives on
# the RapidAPI dashboard, which this script cannot read. Seed it from an
# env var Omar sets after checking that dashboard -- app.config's own
# default (F3) is the FULL budget, the conservative direction, not 0.
QUOTA_TOTAL = 120


def _ledger() -> QuotaLedger:
    """F3 -- points at the SAME durable modal.Dict the deployed app uses
    (QuotaLedger's own default `dict_name="sarjy-quota"`, reached from here
    because modal.Dict is addressable by name from anywhere authenticated,
    not just from inside a container). Before this fix the ledger was built
    on a throwaway `_InProcessStore` discarded at exit -- correct arithmetic,
    theatre for a before/after print, since nothing it recorded outlived the
    process."""
    settings = load_settings()
    if "QUOTA_SPENT_SEED" not in os.environ:
        logger.warning(
            "QUOTA_SPENT_SEED is not set -- seeding spent=%d (the full budget, "
            "app.config's conservative default -- see F3). Check the RapidAPI "
            "dashboard's real count first (Upstream correction #1) and set the "
            "env var, or this ledger will refuse to spend anything it doesn't "
            "strictly need to. NOTE: the FIRST run that ever touches the durable "
            "dict locks this number in -- set QUOTA_SPENT_SEED before that run.",
            settings.quota_spent_seed,
        )
    return QuotaLedger(
        total=QUOTA_TOTAL, reserve=settings.quota_reserve, seed_spent=settings.quota_spent_seed
    )


def _print_status(ledger: QuotaLedger, label: str) -> None:
    s = ledger.status()
    print(f"{label}: total={s.total} spent={s.spent} reserve={s.reserve} remaining={s.remaining}")


def _require_spend_matches(claimed: int, actual: int) -> None:
    if claimed != actual:
        print(
            f"--spend {claimed} does not match the {actual} request(s) this command "
            "is about to make. Refusing to run -- fix the flag or the command.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _live_post(settings: Any, path: str, body: dict[str, Any]) -> dict[str, Any]:
    url = f"https://{settings.rapidapi_host}{path}"
    headers = {"X-RapidAPI-Key": settings.rapidapi_key, "X-RapidAPI-Host": settings.rapidapi_host}
    with httpx.Client(timeout=settings.vendor_timeout_s) as client:
        resp = client.post(url, headers=headers, json=body)
    resp.raise_for_status()
    result: dict[str, Any] = resp.json()
    return result


def cmd_status(_args: argparse.Namespace) -> int:
    ledger = _ledger()
    _print_status(ledger, "status")
    committed = sorted(p.name for p in _REFERENCE_DIR.glob("*") if p.is_file())
    print(f"data/reference/ contains: {', '.join(committed)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    _require_spend_matches(args.spend, 1)
    settings = load_settings()
    ledger = _ledger()
    _print_status(ledger, "before")

    ledger.spend(1)  # counted before the call, same barge-safe rule the tool itself follows (V7)
    body = _live_post(
        settings, "/v2/visa/check", {"passport": args.passport, "destination": args.destination}
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")
    _print_status(ledger, "after")
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    _require_spend_matches(args.spend, 1)
    settings = load_settings()
    ledger = _ledger()
    _print_status(ledger, "before")

    ledger.spend(1)
    body = _live_post(settings, "/v2/visa/map", {"passport": args.passport})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")
    _print_status(ledger, "after")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    pairs = [p.split(":") for p in args.pairs.split(",") if p]
    _require_spend_matches(args.spend, len(pairs))
    settings = load_settings()
    ledger = _ledger()
    _print_status(ledger, "before")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for passport, destination in pairs:
        ledger.spend(1)
        body = _live_post(
            settings, "/v2/visa/check", {"passport": passport, "destination": destination}
        )
        out_path = out_dir / f"{passport}_{destination}.json"
        out_path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {out_path}")

    _print_status(ledger, "after")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.fetch_reference")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser(
        "status", help="print the ledger and committed reference files; spends nothing"
    )
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("check", help="one /v2/visa/check call, saved raw")
    p_check.add_argument("passport")
    p_check.add_argument("destination")
    p_check.add_argument("--spend", type=int, required=True)
    p_check.add_argument("--out", required=True)
    p_check.set_defaults(func=cmd_check)

    p_map = sub.add_parser("map", help="one /v2/visa/map call, saved raw")
    p_map.add_argument("passport")
    p_map.add_argument("--spend", type=int, required=True)
    p_map.add_argument("--out", required=True)
    p_map.set_defaults(func=cmd_map)

    p_batch = sub.add_parser("batch", help="several /v2/visa/check calls, one file each")
    p_batch.add_argument(
        "--pairs", required=True, help="comma-separated PASSPORT:DESTINATION, e.g. SA:JP,SA:BH"
    )
    p_batch.add_argument("--spend", type=int, required=True)
    p_batch.add_argument("--out-dir", required=True)
    p_batch.set_defaults(func=cmd_batch)

    # `--status` alone (no subcommand) is what the block plan's verification
    # literally shows -- support it as a top-level alias.
    if argv is None:
        argv = sys.argv[1:]
    if argv == ["--status"]:
        argv = ["status"]

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
