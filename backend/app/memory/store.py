"""Memory -- one durable store, two tiers, one list of Facts per user.

Requirement #2's floor: a fact told in one session must survive a fresh one
after a reload. `Session.memory` (anonymous, in-process) covers a live
connection; this module is the tier that survives a reload -- `modal.Dict`,
keyed by a normalised name, unlocked by a 4-digit PIN (see app/memory/
identity.py for the name/PIN mechanics).

D1's deliberate deviation from TDD.md's "two kinds of memory": one list of
`Fact` records with a three-key allowlist (PROFILE_KEYS), not two separate
stores. `kind` is DERIVED from `key`, never stored -- there is exactly one
place that decides whether a fact is a travel-profile field or an open one.

Three differences from app/tools/quota.py's shape, each a fix, not a
divergence (that module's own docstring is the precedent to compare against):
  1. No seeding. Every write here is an unconditional `put` -- quota.py
     seeds once with skip_if_exists=True and has no way to correct a wrong
     seed in code; memory must not repeat that flaw.
  2. `delete` exists -- the forget button is a real code path to a real
     deletion, not a debug affordance.
  3. `_InProcessStore` is backed by a MODULE-LEVEL dict, not an instance
     attribute, so tests/test_memory.py's cross-session assertion (save,
     then load from a fresh MemoryRecord) can run with no Modal at all.
"""

import asyncio
import functools
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

logger = logging.getLogger("sarjy")

MAX_FACTS = 12
MAX_VALUE_CHARS = 80
MAX_QUOTE_CHARS = 160
DICT_NAME = "sarjy-memory"

# D1 -- the three fields that drive the travel lookup. Everything else a
# user states about themselves is an "open" fact (the favourite-colour
# test). `kind` is derived from membership here, never stored on the Fact
# itself, so there is exactly one place that decides it.
PROFILE_KEYS = frozenset({"name", "passport", "home_city"})


@dataclass(frozen=True)
class Fact:
    """One remembered fact, with its own provenance. `quote` is the
    attribution and the demo (D1): the panel shows the verbatim sentence
    that taught it, so "how do you know that?" is answered on screen."""

    key: str
    value: str
    label: str
    learned_at: str  # ISO 8601 Z
    turn_id: str | None = None
    quote: str | None = None

    @property
    def kind(self) -> Literal["profile", "open"]:
        return "profile" if self.key in PROFILE_KEYS else "open"


@dataclass
class MemoryRecord:
    """One user's whole remembered state. `signed_in` (no `name_key`) is the
    anonymous shape too -- Session.memory holds a bare MemoryRecord with no
    identity attached, and gains one once sign-in succeeds (D2's tier
    boundary is "does this record have a name_key", not two different
    classes)."""

    name: str | None = None  # display name, as given
    name_key: str | None = None  # normalised; the Dict key suffix
    pin_hash: str | None = None
    facts: list[Fact] = field(default_factory=list)  # oldest first
    created_at: str = ""
    updated_at: str = ""
    persisted: bool = False  # this record is backed by modal.Dict right now
    degraded: bool = False  # the last durable write failed

    @property
    def signed_in(self) -> bool:
        return self.name_key is not None

    def remember(self, fact: Fact) -> bool:
        """Upsert by key, last write wins. Returns True if an OPEN fact was
        evicted to make room (M8) -- profile keys are never evicted, since
        they drive the travel lookup and there are at most three of them."""
        self.facts = [f for f in self.facts if f.key != fact.key]
        self.facts.append(fact)

        evicted = False
        open_keys = [f.key for f in self.facts if f.kind == "open"]
        while len(self.facts) > MAX_FACTS and open_keys:
            oldest_open_key = open_keys.pop(0)
            self.facts = [f for f in self.facts if f.key != oldest_open_key]
            evicted = True
        return evicted

    def forget(self, key: str | None) -> bool:
        """`key=None` clears every fact but keeps name/pin_hash -- signing
        out is a separate action from forgetting what was learned. Returns
        False (a no-op, M9) when the key never existed; never an error."""
        if key is None:
            if not self.facts:
                return False
            self.facts = []
            return True
        before = len(self.facts)
        self.facts = [f for f in self.facts if f.key != key]
        return len(self.facts) != before

    def context_facts(self) -> list[Fact]:
        """Profile keys first (they drive the lookup), then open facts
        newest-first -- the order build_memory_block() renders in."""
        profile = [f for f in self.facts if f.kind == "profile"]
        open_facts = [f for f in self.facts if f.kind == "open"]
        return profile + list(reversed(open_facts))

    def to_json(self) -> dict[str, Any]:
        """A JSON-safe dict of primitives and lists -- deliberately, not a
        pickled dataclass, since modal.Dict's own cross-version pickling
        behaviour is unverified for anything richer than the plain int
        quota.py stores (block plan's Open Question #2)."""
        return {
            "name": self.name,
            "name_key": self.name_key,
            "pin_hash": self.pin_hash,
            "facts": [
                {
                    "key": f.key,
                    "value": f.value,
                    "label": f.label,
                    "learned_at": f.learned_at,
                    "turn_id": f.turn_id,
                    "quote": f.quote,
                }
                for f in self.facts
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "MemoryRecord":
        facts = [
            Fact(
                key=f["key"],
                value=f["value"],
                label=f["label"],
                learned_at=f["learned_at"],
                turn_id=f.get("turn_id"),
                quote=f.get("quote"),
            )
            for f in raw.get("facts", [])
        ]
        return cls(
            name=raw.get("name"),
            name_key=raw.get("name_key"),
            pin_hash=raw.get("pin_hash"),
            facts=facts,
            created_at=raw.get("created_at", ""),
            updated_at=raw.get("updated_at", ""),
            persisted=True,  # it was loaded FROM the durable store
        )


class _Store(Protocol):
    # Does a successful save() actually SURVIVE this container? The M1
    # fallback answers save() with True while storing in a process-local
    # dict, so "the write succeeded" and "the write persisted" are different
    # questions and only this property answers the second one. Without it,
    # an unreachable modal.Dict reports persisted=True/degraded=False -- the
    # panel claims everything is fine, and the facts vanish on the next
    # container restart. That is the most expensive failure this app has.
    durable: bool

    def load(self, name_key: str) -> dict[str, Any] | None: ...
    def save(self, name_key: str, raw: dict[str, Any]) -> None: ...
    def delete(self, name_key: str) -> None: ...


# Module-level, not an instance attribute: a fresh _InProcessStore() must see
# what an earlier one wrote, the same way two containers sharing a real
# modal.Dict would -- that is what lets test_memory.py's cross-session
# assertion run with no Modal at all (difference #3 above).
_in_process_records: dict[str, dict[str, Any]] = {}


class _InProcessStore:
    """Local dev, tests, and M1's fallback if modal.Dict is unreachable."""

    durable = False

    def load(self, name_key: str) -> dict[str, Any] | None:
        return _in_process_records.get(name_key)

    def save(self, name_key: str, raw: dict[str, Any]) -> None:
        _in_process_records[name_key] = raw

    def delete(self, name_key: str) -> None:
        # Open question #1: modal.Dict.delete()'s exact name is unverified
        # against the installed client (quota.py never calls it). The
        # in-process fallback mirrors the SAME contract either backend must
        # satisfy -- "forget must leave nothing readable" -- rather than one
        # that happens to be easier locally.
        _in_process_records.pop(name_key, None)


class _ModalDictStore:
    """Shared across every container sharing this Modal app -- so a name
    signed in on one container is found on another. Constructed lazily:
    `import modal` happens here, not at module level, the same reason
    quota.py's _ModalDictStore does it (this module must stay importable
    from a local dev run with no Modal image at all).

    No seeding (difference #1 above) -- every write is unconditional."""

    durable = True

    def __init__(self) -> None:
        import modal  # may raise ImportError -- caller (get_store) catches it

        self._d = modal.Dict.from_name(DICT_NAME, create_if_missing=True)

    def load(self, name_key: str) -> dict[str, Any] | None:
        value = self._d.get(name_key)
        return value if isinstance(value, dict) else None

    def save(self, name_key: str, raw: dict[str, Any]) -> None:
        self._d.put(name_key, raw)

    def delete(self, name_key: str) -> None:
        # Open question #1, resolved (not guessed): the installed modal
        # client (checked live via `dir(modal.Dict)`) has no `.delete()` at
        # all -- `.pop(key, default)` is the real removal method. `default`
        # makes this a no-op, not a KeyError, when the key was never there.
        self._d.pop(name_key, None)


@functools.lru_cache(maxsize=1)
def get_store() -> _Store:
    """modal.Dict, falling back to an in-process store with a warning if it
    can't be reached (M1) -- a turn is never blocked on this, and sign-in
    still succeeds into a record that just won't survive a container
    restart (reported via MemoryRecord.degraded, not raised)."""
    try:
        store: _Store = _ModalDictStore()
        logger.info("memory_store backend=modal.Dict")
        return store
    except Exception:
        logger.warning(
            "memory_store: modal.Dict unavailable, falling back to in-process "
            "(memory will not survive a container restart)",
            exc_info=True,
        )
        return _InProcessStore()


def store_is_durable() -> bool:
    """Whether the store actually in use survives a container restart.

    `save_record()` returning True only means the write did not raise -- the
    M1 fallback writes happily into a process-local dict. Callers that set
    `persisted` must AND the two together, or a Modal outage at container
    start produces a session where sign-in works, facts appear, the panel
    reports no problem, and everything is gone after the next reload.
    """
    return get_store().durable


async def load_record(name_key: str) -> MemoryRecord | None:
    """modal.Dict.get() is a BLOCKING sync call and the WebSocket handler is
    async, sharing a container with up to 16 inputs (modal_app.py) -- every
    call into the store goes through asyncio.to_thread so one slow Dict read
    never stalls every other connection's turn."""
    raw = await asyncio.to_thread(get_store().load, name_key)
    return MemoryRecord.from_json(raw) if raw is not None else None


async def save_record(record: MemoryRecord) -> bool:
    """Returns False (and the caller sets record.degraded) rather than
    raising -- M2: a failed durable write must never lose the fact from the
    in-memory record the user just heard confirmed, and it must never crash
    a turn that has nothing to do with memory."""
    if record.name_key is None:
        return False  # nothing to key the write on -- anonymous tier, never persisted
    try:
        await asyncio.to_thread(get_store().save, record.name_key, record.to_json())
        return True
    except Exception:
        logger.warning("memory_store: save_record failed for a signed-in user", exc_info=True)
        return False


async def delete_record(name_key: str) -> bool:
    """Backs the Forget-everything button's proof step (verification step
    8): a delete that only ever touched the in-process copy would still
    look correct after a reload, until the demo has already ended."""
    try:
        await asyncio.to_thread(get_store().delete, name_key)
        return True
    except Exception:
        logger.warning("memory_store: delete_record failed", exc_info=True)
        return False
