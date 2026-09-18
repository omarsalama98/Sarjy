"""The grounding gate — the deep dive.

Enforced at the VALUE level, not the citation level. The model never writes a
fact; it names a field, and this module substitutes the value from the stored
tool response.

That distinction is the whole project. If the model could write "90 days" as
free text while correctly citing a tool that said 30, this would be a citation
chip rather than a guardrail.

Contract: .claude/rules/tools/grounding-gate.md
"""

from dataclasses import dataclass
from typing import Any, Literal

Kind = Literal["sourced", "judgement"]


@dataclass(frozen=True)
class Segment:
    """One piece of a response, as the MODEL returns it.

    A `sourced` segment's `text` contains {field.path} placeholders and never
    literal facts. A `judgement` segment carries no tool reference and no
    citation — it is Sarjy's own view, and the gate passes it through untouched.
    """

    kind: Kind
    text: str
    tool_call_id: str | None = None
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderedSegment:
    """One piece of a response, after the gate. This is what may be spoken."""

    kind: Kind
    text: str
    citation: str | None = None
    source_date: str | None = None
    layer: str | None = None  # which resolution layer answered: live | cache | csv


class GateRejection(Exception):
    """A sourced segment named a field its tool response does not contain.

    The segment never reaches TTS. We say we could not confirm that part —
    we do not improvise the value.
    """


def resolve(
    segments: list[Segment],
    tool_results: dict[str, dict[str, Any]],
) -> list[RenderedSegment]:
    """Substitute real values into sourced segments; pass judgement through.

    Raises GateRejection for a sourced segment whose field path is absent from
    the named tool result. On failure the caller strips the segment and says so
    — there is deliberately no re-ask branch (a second completion on the latency
    path costs more than it saves).
    """
    raise NotImplementedError


def get_path(obj: dict[str, Any], path: str) -> Any:
    """Read a dotted path out of a tool response. Raises KeyError if absent.

    Absent must be distinguishable from null — a field that exists and is null
    is a real answer; a field that does not exist is a rejection.
    """
    raise NotImplementedError
