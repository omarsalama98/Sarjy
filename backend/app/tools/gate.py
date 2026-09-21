"""The grounding gate -- the deep dive.

Enforced at the VALUE level, not the citation level. The model never writes a
fact; it either names a field and a placeholder it fills from a stored tool
result (`sourced`), or it names a field and nothing else, letting code copy
the vendor's own words verbatim (`quoted`), or it speaks in its own voice
with no source at all (`judgement`).

That distinction is the whole project. If the model could write "90 days" as
free text while correctly citing a tool that said 30, this would be a
citation chip rather than a guardrail.

Contract: docs/plans/blocks/A-grounded-answers.md (Decisions page) and
.claude/rules/tools/grounding-gate.md.
"""

import functools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.providers.base import ToolResult

Register = Literal["sourced", "quoted", "judgement"]

GateReason = Literal[
    # sourced
    "unknown_tool_call_id",
    "absent_path",
    "field_mismatch",
    "no_placeholder",
    "bare_digit",
    "number_word",
    "value_too_long",
    "field_not_allowlisted",
    "wrong_pair",
    # quoted
    "quote_not_allowlisted",
    "quoted_text_supplied",
    "injection_marker",
    "too_many_quotes",
    # transport -- a line that never became a Segment at all (turn.py counts
    # these; gate() itself never emits this reason, since a malformed line
    # has nothing to render)
    "malformed_line",
]

PLACEHOLDER_RE = re.compile(r"\{([a-z0-9_.]+)\}")
DIGIT_RE = re.compile(r"\d")  # str patterns are Unicode: Arabic-Indic digits match too
NUMBER_WORDS = frozenset(
    {
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
        "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety", "hundred", "thousand",
    }
)
_NUMBER_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")\b", re.IGNORECASE
)

# D14 rule Q6 -- a value addressed to a model is by definition not a travel
# fact, so refusing to quote it costs the user nothing. Lowercased substring
# match. Known limit, stated in the PR: a paraphrased injection passes this
# screen (eval case Q-h / the "paraphrase" injection category).
INJECTION_MARKERS = (
    "ignore previous",
    "ignore all",
    "disregard the",
    "system prompt",
    "you are now",
    "ai language model",
    "ai assistant",
    "attention ai",
    "new instructions",
    "instructions:",
)

# F5 -- three ways to defeat a plain substring search without changing what
# a human hears: a zero-width character hiding inside a word, ASCII
# punctuation splitting a marker phrase ("A.I. LANGUAGE MODELS:" has no
# contiguous "ai language model" substring), and a Cyrillic letter standing
# in for a pixel-identical Latin one ("previous" spelled with U+0440
# CYRILLIC ER instead of "p"). All three are folded away BEFORE matching --
# markers are folded the same way once, at import time, so both sides of
# the comparison go through the identical transform.
_ZERO_WIDTH_CHARS = ("​", "‌", "‍", "﻿")

# Not a general transliteration table -- just the handful of lowercase
# Cyrillic letters that render identically to a Latin one in most fonts,
# which is exactly what makes them useful for disguising a phrase rather
# than for writing Russian. `str.lower()` runs before this table, so only
# lowercase entries are needed.
_CONFUSABLES = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
        "у": "y", "х": "x", "і": "i", "ѕ": "s", "ј": "j", "к": "k",
    }
)


def _fold_for_injection_check(text: str) -> str:
    """Lossy on purpose -- this folded string is ONLY used to decide
    whether Q6 fires, never spoken or stored. Punctuation is DELETED, not
    replaced with a space, specifically so "A.I." collapses to "ai" rather
    than "a i" (which would no longer contain the marker at all)."""
    for zw in _ZERO_WIDTH_CHARS:
        text = text.replace(zw, "")
    text = text.lower().translate(_CONFUSABLES)
    return "".join(ch for ch in text if ch.isascii() and (ch.isalnum() or ch == " "))


# Folded once, at import time -- "instructions:" folds to "instructions",
# so matching folded-against-folded stays correct even though the colon in
# the literal marker above would otherwise never survive the same fold
# applied to a candidate value.
_FOLDED_INJECTION_MARKERS = tuple(_fold_for_injection_check(m) for m in INJECTION_MARKERS)

MAX_SOURCED_VALUE_CHARS = 120
MAX_QUOTED_VALUE_CHARS = 400
MAX_QUOTES_PER_TURN = 1
SENTINEL_NULL = "none"

# D13 -- decision-critical fields only. Being wrong here costs the user a
# flight or money. A resolvable path NOT on this list rejects
# (field_not_allowlisted) rather than silently downgrading -- see the block
# plan's Decisions page for the per-field justification.
SOURCED_FIELDS = frozenset(
    {
        "visa.type",  # visa required / visa free / eVisa -- the decision itself
        "visa.duration",  # overstay is a fine and a ban
        "visa.passport_validity",  # the six-month rule -- the classic denied-boarding cause
        "visa.registration",  # a missed mandatory eTA is a denied boarding (the ESTA cases)
        "visa.cost",  # money. RESERVED -- the vendor exposes no fee field today, so this
        # path is absent in practice and naming it rejects on rule 2 (absent_path).
        "visa.category",  # map layer only: the vendor's own ambiguous colour wording
        "pair.passport_name",  # misidentifying the pair is decision-critical in effect --
        "pair.destination_name",  # correct values, wrong frame, and nothing else would notice.
    }
)

# D14 -- exactly two quotable paths, both short vendor prose, both chosen.
# Disjoint from SOURCED_FIELDS by construction (asserted below) so the two
# registers can never be crossed -- a model naming one from the other
# register always rejects.
QUOTED_FIELDS = frozenset(
    {
        "visa.exception",  # <- data.visa_rules.exception_rule.full_text, when present
        "visa.notes",  # <- any other short vendor prose we choose to map
    }
)

assert not (SOURCED_FIELDS & QUOTED_FIELDS), "sourced and quoted allowlists must never overlap"

_DEGRADED_SOURCE_LABEL = {"map": "my cached visa map", "csv": "a community dataset"}

# F1 -- the wrong-pair hole. All eight original rules pass a template like
# "For Thailand you will need {visa.type}." against an SA->JP tool result,
# because every check above is about WHICH FIELD is named, never about
# whether the template's own prose names a DIFFERENT country than the one
# the field actually describes. Closed by scanning the template for any
# known place name that isn't half of this turn's pair.
_APP_DIR = Path(__file__).resolve().parents[1]  # backend/app, or /root/app under Modal


@functools.lru_cache(maxsize=1)
def _known_place_names() -> tuple[str, ...]:
    """Every country name in data/reference/destinations.json, longest
    first so "Equatorial Guinea" is tried before "Guinea" at the same
    starting position (re's alternation picks the first alternative that
    matches, not the longest). Loaded once, lazily -- a missing file
    degrades to "no names known" (the rule never fires), not a crash;
    gate.py otherwise touches no filesystem at all."""
    two_up = _APP_DIR.parent.parent / "data"  # repo_root/data, local checkout
    one_up = _APP_DIR.parent / "data"  # /root/data, under Modal
    for data_dir in (two_up, one_up):
        path = data_dir / "reference" / "destinations.json"
        if path.is_file():
            body = json.loads(path.read_text())
            names = {d["name"] for d in body.get("destinations", []) if d.get("name")}
            return tuple(sorted(names, key=len, reverse=True))
    return ()


@functools.lru_cache(maxsize=1)
def _place_name_pattern() -> re.Pattern[str] | None:
    names = _known_place_names()
    if not names:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.IGNORECASE)


def _mentions_other_place(text: str, allowed_names: set[str]) -> bool:
    """True if `text` names a known place that is NOT in `allowed_names`
    (this turn's pair). Case-insensitive: the pattern match may return
    different casing than the payload's own names, so both sides are
    compared casefolded rather than as exact strings."""
    pattern = _place_name_pattern()
    if pattern is None:
        return False
    allowed_fold = {n.casefold() for n in allowed_names}
    return any(m.group(0).casefold() not in allowed_fold for m in pattern.finditer(text))


def quoted_shape_ok(value_str: str) -> bool:
    """Q5's value-shape half, on an ALREADY-rendered quoted value. Exported
    (no leading underscore) so card.fact_card() can apply the identical
    check (F4) -- a value the gate would refuse to speak must not reach the
    fact card either, and there is exactly one place this threshold lives."""
    if len(value_str) > MAX_QUOTED_VALUE_CHARS:
        return False
    return "{" not in value_str and "}" not in value_str


def contains_injection_marker(value_str: str) -> bool:
    """Q6's screen, on an ALREADY-rendered quoted value. Exported for the
    same F4 reason as quoted_shape_ok() above."""
    folded = _fold_for_injection_check(value_str)
    return any(marker in folded for marker in _FOLDED_INJECTION_MARKERS)


@dataclass(frozen=True)
class Segment:
    """One piece of a response, as the MODEL returns it.

    A `sourced` segment's `text` contains {field.path} placeholders and never
    literal facts, and `fields` names exactly those placeholders. A `quoted`
    segment carries no `text` at all -- `field` names the ONE vendor field
    whose words code will copy verbatim; there is no model-authored string
    to check, because there isn't one. A `judgement` segment carries no tool
    reference and no citation -- it is Sarjy's own view, passed through
    untouched (any tool_call_id/fields/field it carries are stripped, not
    honoured -- the gate blocks judgement wearing a citation, not judgement).
    """

    kind: Register
    text: str | None = None
    tool_call_id: str | None = None
    fields: tuple[str, ...] = ()
    field: str | None = None


@dataclass(frozen=True)
class RenderedSegment:
    """One piece of a response, after the gate. `ok=False` is still SENT to
    the browser, struck through -- that visibility is the demo. `text` is:
    substituted (sourced, ok), the vendor's verbatim value (quoted, ok),
    untouched (judgement), or the model's raw, unsubstituted template
    (anything rejected) -- so a struck-through segment still shows what the
    model tried to say."""

    kind: Register
    text: str
    ok: bool
    reason: GateReason | None = None
    attribution: str | None = None  # quoted only: the "According to X:" prefix
    field: str | None = None  # quoted only: the path the words came from (kept or rejected)
    citation: str | None = None
    source_url: str | None = None
    source_date: str | None = None
    layer: str | None = None
    embassy_url: str | None = None  # F2 -- carried through even on rejection, so a turn
    # where every segment was rejected can still route spoken_text()'s refusal to it


def get_path(obj: dict[str, Any], path: str) -> Any:
    """Dotted read. Raises KeyError when ANY component is absent. A present
    key whose value is None returns None -- that is an answer, not a miss
    (rule 2's absent-vs-null distinction, proved by test_g9_null_renders_as_none)."""
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(path)
        cur = cur[part]
    return cur


def render_value(value: Any) -> str:
    """The sourced-register substitution rule -- null becomes the literal
    word "none", everything else stringifies. Factored out so card.py's
    fact_card() can produce the identical string without re-deriving the
    rule: that is what makes D15's "cannot contradict by construction"
    claim a fact rather than a hope (test_card_value_equals_gate_substitution)."""
    return SENTINEL_NULL if value is None else str(value)


def render_quoted_value(value: Any) -> str:
    """The quoted-register value shaping -- whitespace collapsed to single
    spaces. Shared with card.py for the same non-drift reason as render_value()."""
    return " ".join(str(value).split())


def _reject(
    seg: Segment,
    reason: GateReason,
    *,
    layer: str | None = None,
    embassy_url: str | None = None,
) -> RenderedSegment:
    return RenderedSegment(
        kind="sourced", text=seg.text or "", ok=False, reason=reason, layer=layer,
        embassy_url=embassy_url,
    )


def _render_sourced(seg: Segment, tool_results: dict[str, ToolResult]) -> RenderedSegment:
    # Rule 1 -- the named tool result was actually stored this turn.
    if seg.tool_call_id is None or seg.tool_call_id not in tool_results:
        return _reject(seg, "unknown_tool_call_id")
    result = tool_results[seg.tool_call_id]
    text = seg.text or ""

    # Rule 4 -- at least one placeholder. Without this a segment with zero
    # placeholders and a real citation attached could smuggle prose through.
    placeholders = tuple(PLACEHOLDER_RE.findall(text))
    if not placeholders:
        return _reject(seg, "no_placeholder", layer=result.layer, embassy_url=result.embassy_url)

    # Rule 3 -- `fields` and the template's placeholders are the same set.
    if set(seg.fields) != set(placeholders):
        return _reject(seg, "field_mismatch", layer=result.layer, embassy_url=result.embassy_url)

    # Rules 5 & 6 -- checked on the TEMPLATE, with placeholders stripped out
    # first. Checking the rendered string instead is the classic bug: it
    # rejects every correct answer ("30 days" is a digit). D1/D2.
    template_stripped = PLACEHOLDER_RE.sub("", text)
    if DIGIT_RE.search(template_stripped):
        return _reject(seg, "bare_digit", layer=result.layer, embassy_url=result.embassy_url)
    if _NUMBER_WORD_RE.search(template_stripped):
        return _reject(seg, "number_word", layer=result.layer, embassy_url=result.embassy_url)

    # Rule 9 (wrong_pair, F1) -- the template must not name a country that
    # is neither half of THIS turn's pair. Checked on the template, same as
    # rules 5/6: a resolved {field.path} value is vendor data, never a
    # place name to second-guess. Skipped, not rejected, when the payload
    # itself carries no pair names to check against -- e.g. some hand-built
    # test fixtures -- because a real ToolResult always has both (Contract 3).
    destination_name = _optional(result.payload, "pair.destination_name")
    passport_name = _optional(result.payload, "pair.passport_name")
    allowed_names = {n for n in (destination_name, passport_name) if n}
    if allowed_names and _mentions_other_place(template_stripped, allowed_names):
        return _reject(seg, "wrong_pair", layer=result.layer, embassy_url=result.embassy_url)

    # Rule 8 -- every named field is decision-critical enough to be
    # allowlisted. Checked BEFORE resolving (rule 2) on purpose: a field
    # like visa.cost is allowlisted but the vendor never populates it, so
    # naming it must reject on absent_path (rule 2), not silently pass an
    # allowlist check it never reached. Checking allowlist first here means
    # a field that is neither allowlisted NOR present still reports the
    # more specific reason: field_not_allowlisted.
    for f in seg.fields:
        if f not in SOURCED_FIELDS:
            return _reject(
                seg, "field_not_allowlisted", layer=result.layer, embassy_url=result.embassy_url
            )

    # Rule 2 (+ rule 7's value shape) -- resolve every field from the ACTUAL
    # stored result. Absent rejects; null resolves to the literal "none".
    rendered_values: dict[str, str] = {}
    for f in seg.fields:
        try:
            value = get_path(result.payload, f)
        except KeyError:
            return _reject(seg, "absent_path", layer=result.layer, embassy_url=result.embassy_url)
        rendered = render_value(value)
        too_long = len(rendered) > MAX_SOURCED_VALUE_CHARS
        if too_long or "\n" in rendered or "{" in rendered or "}" in rendered:
            return _reject(
                seg, "value_too_long", layer=result.layer, embassy_url=result.embassy_url
            )
        rendered_values[f] = rendered

    rendered_text = text
    for f, v in rendered_values.items():
        rendered_text = rendered_text.replace("{" + f + "}", v)

    return RenderedSegment(
        kind="sourced",
        text=rendered_text,
        ok=True,
        citation=result.citation,
        source_url=result.source_url,
        source_date=result.source_date,
        layer=result.layer,
    )


def _optional(payload: dict[str, Any], path: str) -> str | None:
    try:
        value = get_path(payload, path)
    except KeyError:
        return None
    return None if value is None else str(value)


def _render_quoted(
    seg: Segment, tool_results: dict[str, ToolResult], quotes_used: list[int]
) -> RenderedSegment:
    shown = seg.field or ""

    def reject(
        reason: GateReason, *, layer: str | None = None, embassy_url: str | None = None
    ) -> RenderedSegment:
        return RenderedSegment(
            kind="quoted", text=shown, ok=False, reason=reason, field=seg.field, layer=layer,
            embassy_url=embassy_url,
        )

    # Q1 -- the named tool result was stored this turn.
    if seg.tool_call_id is None or seg.tool_call_id not in tool_results:
        return reject("unknown_tool_call_id")
    result = tool_results[seg.tool_call_id]

    # Q4 -- a model that wrote its own words is rejected, not corrected. The
    # channel exists BECAUSE there is structurally no model string to check
    # against (D14 property 1) -- if one arrived anyway, that guarantee has
    # already been violated and the segment cannot be trusted.
    if seg.text is not None or seg.fields:
        return reject("quoted_text_supplied", layer=result.layer, embassy_url=result.embassy_url)

    # Q2 -- exactly one path, and it is on the (small, deliberately narrow) allowlist.
    if seg.field is None or seg.field not in QUOTED_FIELDS:
        return reject("quote_not_allowlisted", layer=result.layer, embassy_url=result.embassy_url)

    # Q3 -- resolves, and is not null/empty. Nothing to quote otherwise.
    try:
        value = get_path(result.payload, seg.field)
    except KeyError:
        return reject("absent_path", layer=result.layer, embassy_url=result.embassy_url)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return reject("absent_path", layer=result.layer, embassy_url=result.embassy_url)

    value_str = render_quoted_value(value)  # newlines/whitespace collapsed (Q5)

    # Q5 -- value shape. Shared with card.fact_card() (F4) via quoted_shape_ok().
    if not quoted_shape_ok(value_str):
        return reject("value_too_long", layer=result.layer, embassy_url=result.embassy_url)

    # Q6 -- the injection screen. Narrow and named as such (D14): it catches
    # the literal in-the-wild shape and its trivial disguises (F5 -- a
    # zero-width character, ASCII punctuation, a Cyrillic homoglyph), not a
    # genuine paraphrase. Shared with card.fact_card() via contains_injection_marker().
    if contains_injection_marker(value_str):
        return reject("injection_marker", layer=result.layer, embassy_url=result.embassy_url)

    # Q7 -- at most one quote per turn.
    if quotes_used[0] >= MAX_QUOTES_PER_TURN:
        return reject("too_many_quotes", layer=result.layer, embassy_url=result.embassy_url)
    quotes_used[0] += 1

    from app.prompts import QUOTE_PREFIX  # deferred: prompts.py imports THIS module

    try:
        source_name = get_path(result.payload, "source.name")
    except KeyError:
        source_name = "Travel Buddy"

    return RenderedSegment(
        kind="quoted",
        text=value_str,
        ok=True,
        attribution=QUOTE_PREFIX.format(source=source_name),
        field=seg.field,
        citation=result.citation,
        source_url=result.source_url,
        source_date=result.source_date,
        layer=result.layer,
    )


def _render_judgement(seg: Segment) -> RenderedSegment:
    # D10 -- the gate never blocks judgement; it strips a citation that
    # judgement should never have carried in the first place.
    return RenderedSegment(kind="judgement", text=seg.text or "", ok=True)


def gate(
    segments: list[Segment],
    tool_results: dict[str, ToolResult],
) -> list[RenderedSegment]:
    """Never raises. Every input segment produces exactly one output segment,
    in order, `ok` True or False. The caller decides what to speak."""
    quotes_used = [0]
    rendered: list[RenderedSegment] = []
    for seg in segments:
        try:
            if seg.kind == "sourced":
                rendered.append(_render_sourced(seg, tool_results))
            elif seg.kind == "quoted":
                rendered.append(_render_quoted(seg, tool_results, quotes_used))
            else:
                rendered.append(_render_judgement(seg))
        except Exception:
            # Defense in depth for the "never raises" contract -- every
            # branch above is already exception-safe (KeyError is caught
            # explicitly), so reaching here would itself be a bug worth
            # seeing in the logs, not a turn worth losing.
            rendered.append(
                RenderedSegment(
                    kind=seg.kind, text=seg.text or "", ok=False, reason="malformed_line"
                )
            )
    return rendered


_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _speakable_date(value: str) -> str:
    """ISO date or datetime -> "Month YYYY" (F6) -- "last updated
    2026-09-20T14:28:07+00:00" is not a sentence to read aloud; "last
    updated September 2026" is. Falls back to the raw string, unparsed, if
    it doesn't look like an ISO date -- a slightly odd-sounding date is a
    safer failure than the whole prefix silently vanishing."""
    try:
        year, month, day = value.split("T", 1)[0].split("-")
        return f"{_MONTH_NAMES[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return value


def spoken_text(rendered: list[RenderedSegment]) -> str:
    """The exact string handed to TTS. Kept segments joined by ' ', in order;
    a kept `quoted` segment rendered as its `attribution` + the verbatim
    value in quotes; the degraded-layer prefix prepended when any kept
    segment's layer is 'map' or 'csv'; the one caveat sentence appended when
    any segment was rejected; the full refusal returned alone when nothing
    was kept -- routed to REFUSAL_WITH_EMBASSY (F2) when any rejected
    segment's tool result carried a known embassy_url, since the destination
    is known even when coverage of it is not."""
    from app.prompts import CAVEAT, DEGRADED_PREFIX, REFUSAL, REFUSAL_WITH_EMBASSY

    kept = [r for r in rendered if r.ok]
    any_rejected = any(not r.ok for r in rendered)

    if not kept:
        embassy_url = next((r.embassy_url for r in rendered if r.embassy_url), None)
        return REFUSAL_WITH_EMBASSY if embassy_url else REFUSAL

    parts: list[str] = []
    degraded = next((r for r in kept if r.layer in ("map", "csv")), None)
    if degraded is not None and degraded.layer is not None:
        parts.append(
            DEGRADED_PREFIX.format(
                source=_DEGRADED_SOURCE_LABEL[degraded.layer],
                date=_speakable_date(degraded.source_date) if degraded.source_date
                else "an earlier date",
            )
        )

    for r in kept:
        if r.kind == "quoted":
            parts.append(f'{r.attribution} "{r.text}"')
        else:
            parts.append(r.text)

    if any_rejected:
        parts.append(CAVEAT)

    return " ".join(parts)
